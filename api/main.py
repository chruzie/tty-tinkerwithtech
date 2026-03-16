"""FastAPI application — tty-theme web API."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

# Load .env in development before anything else
from security.secrets import load_dotenv_if_dev

load_dotenv_if_dev()

# ── Repository factory (SQLite in dev, Firestore in prod) ──────────────────────

def _get_repo():
    """Return the appropriate ThemeRepository implementation."""
    if os.environ.get("FIRESTORE_PROJECT") and os.environ.get("ENVIRONMENT") != "development":
        from cache.firestore_db import FirestoreThemeRepository
        repo = FirestoreThemeRepository()
    else:
        from cache.db import ThemeRepository
        repo = ThemeRepository()
    repo.init_db()
    return repo


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate DAILY_SPEND_CAP at startup so misconfiguration fails fast
    _cap_raw = os.environ.get("DAILY_SPEND_CAP", "10.0")
    try:
        _cap = float(_cap_raw)
        if _cap <= 0:
            raise ValueError("must be positive")
    except ValueError as exc:
        raise RuntimeError(
            f"Invalid DAILY_SPEND_CAP={_cap_raw!r}: {exc}. "
            "Set a positive float (e.g. DAILY_SPEND_CAP=10.0)."
        ) from exc

    # Initialise DB on startup
    repo = _get_repo()
    app.state.repo = repo

    # Pre-load MiniLM embedding model so first request has no cold-start delay
    try:
        import cache.embeddings as _embeddings

        app.state.embedding_model = _embeddings._get_model()
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).warning(
            "sentence-transformers not available; tier-2 similarity cache disabled"
        )
        app.state.embedding_model = None

    yield


# ── App factory ────────────────────────────────────────────────────────────────

_ALLOWED_ORIGINS = (
    os.environ.get("CORS_ORIGINS", "http://localhost:5000,http://localhost:3000").split(",")
    if os.environ.get("ENVIRONMENT") == "development"
    else ["https://tty-theme.dev"]
)

app = FastAPI(
    title="tty-theme API",
    description="Generate terminal colour themes from prompts or images.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Api-Key"],
)

# Register rate-limit + audit middleware
from api.middleware import AuditLogMiddleware, RateLimitMiddleware  # noqa: E402

app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuditLogMiddleware)


# ── Prometheus metrics ─────────────────────────────────────────────────────────


def _metrics_auth(request: Request) -> None:
    """Require Authorization: Bearer <METRICS_TOKEN> when the env var is set."""
    token = os.environ.get("METRICS_TOKEN")
    if not token:
        return  # local dev — no auth required
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {token}":
        raise HTTPException(status_code=403, detail="Forbidden")


try:
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest  # type: ignore[import]

    @app.get("/metrics", include_in_schema=False)
    async def metrics(request: Request, _auth: None = Depends(_metrics_auth)):
        from fastapi.responses import Response
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

except ImportError:
    pass  # prometheus_client not installed — metrics endpoint disabled


# ── Request / response models ──────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    prompt: str | None = None
    image_url: str | None = None
    target: str = "ghostty"
    refine: bool = False
    provider: str | None = None

    @field_validator("target")
    @classmethod
    def valid_target(cls, v: str) -> str:
        if v not in ("ghostty", "iterm2"):
            raise ValueError("target must be 'ghostty' or 'iterm2'")
        return v


class GenerateResponse(BaseModel):
    theme: str
    provider: str
    tier_used: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/v1/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest, request: Request):
    if not req.prompt and not req.image_url:
        raise HTTPException(status_code=422, detail="Provide 'prompt' or 'image_url'.")

    # Check spend cap
    repo = request.app.state.repo
    if repo.get_daily_spend() >= float(os.environ.get("DAILY_SPEND_CAP", "10.0")):
        raise HTTPException(
            status_code=503,
            detail={"error": "service_temporarily_unavailable", "reason": "spend_limit"},
        )

    try:
        from providers.registry import resolve_provider
        provider = resolve_provider(preferred=req.provider)

        if req.prompt:
            from modes.prompt_mode import generate_from_prompt
            theme_str, tier = generate_from_prompt(
                req.prompt, provider=provider, target=req.target, repo=repo
            )
        else:
            from modes.image_mode import generate_from_image
            theme_str, tier = generate_from_image(
                req.image_url,  # type: ignore[arg-type]
                target=req.target,
                refine=req.refine,
                provider=provider,
                repo=repo,
            )

    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        if "spend" in str(exc).lower():
            raise HTTPException(status_code=429, detail=str(exc)) from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return GenerateResponse(
        theme=theme_str,
        provider=getattr(provider, "name", "unknown"),
        tier_used=tier,
    )
