"""FastAPI application — tty-theme web API (v1.3 web-only)."""

from __future__ import annotations

import hashlib
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

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
    repo = _get_repo()
    app.state.repo = repo

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
    description="Generate terminal colour themes from prompts.",
    version="1.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

from api.middleware import AuditLogMiddleware, RateLimitMiddleware  # noqa: E402

app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuditLogMiddleware)


# ── Prometheus metrics ─────────────────────────────────────────────────────────

def _metrics_auth(request: Request) -> None:
    token = os.environ.get("METRICS_TOKEN")
    if not token:
        return
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {token}":
        raise HTTPException(status_code=403, detail="Forbidden")


try:
    from fastapi import Depends
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest  # type: ignore[import]

    @app.get("/metrics", include_in_schema=False)
    async def metrics(request: Request, _auth: None = Depends(_metrics_auth)):
        from fastapi.responses import Response
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

except ImportError:
    pass


# ── Helpers ────────────────────────────────────────────────────────────────────


def _ip_hash(request: Request) -> str:
    host = request.client.host if request.client else "unknown"
    return hashlib.sha256(host.encode()).hexdigest()[:16]


def _parse_theme_colors(theme_data: str) -> dict[str, str]:
    """Parse Ghostty key=value theme_data into a dict of color keys → hex values.

    Handles both 3-part palette lines ("palette = 0 = #hex") and
    2-part semantic lines ("background = #hex").
    """
    colors: dict[str, str] = {}
    for line in theme_data.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("palette = "):
            # "palette = 0 = #hex" → key "palette = 0", value "#hex"
            parts = line.split("=", 2)
            if len(parts) == 3:  # noqa: PLR2004
                colors["palette = " + parts[1].strip()] = parts[2].strip()
        elif "=" in line:
            key, _, val = line.partition("=")
            colors[key.strip()] = val.strip()
    return colors


# ── Request / response models ──────────────────────────────────────────────────


class GenerateRequest(BaseModel):
    prompt: str


class GenerateResponse(BaseModel):
    theme_data: str
    slug: str
    cached: bool
    provider: str


class PublishRequest(BaseModel):
    name: str
    theme_data: str


# ── Endpoints ─────────────────────────────────────────────────────────────────


@app.get("/v1/health")
@app.get("/health")  # legacy alias
async def health():
    return {"status": "ok"}


@app.post("/v1/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest, request: Request):
    """Generate a Ghostty theme from a natural-language prompt."""
    from security.input_sanitizer import sanitize_prompt

    # 1. Validate length
    try:
        clean_prompt = sanitize_prompt(req.prompt)
    except ValueError as exc:
        if "prompt_too_long" in str(exc):
            raise HTTPException(
                status_code=400, detail={"error": "prompt_too_long", "max_length": 200}
            ) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    repo = request.app.state.repo
    ip_hash = _ip_hash(request)

    # 2. Tier 1 — exact hash cache
    import hashlib as _hl

    from generator.prompt import SYSTEM_PROMPT, build_user_prompt

    query_hash = _hl.sha256(clean_prompt.encode()).hexdigest()
    cached_theme = repo.get_by_hash(query_hash)
    if cached_theme:
        from generator.slug import make_slug

        return GenerateResponse(
            theme_data=cached_theme["theme_data"],
            slug=make_slug(clean_prompt[:40]),
            cached=True,
            provider=cached_theme.get("provider") or "cache",
        )

    # 3. Tier 2 — similarity cache
    try:
        from cache.embeddings import find_similar

        candidates = repo.get_all_embeddings()
        similar_id = find_similar(clean_prompt, candidates, threshold=0.85)
        if similar_id is not None:
            similar = repo.get_by_id(similar_id)
            if similar:
                from generator.slug import make_slug

                return GenerateResponse(
                    theme_data=similar["theme_data"],
                    slug=make_slug(clean_prompt[:40]),
                    cached=True,
                    provider=similar.get("provider") or "cache",
                )
    except Exception:  # noqa: BLE001, S110
        pass  # embeddings not available — skip tier 2

    # 4. Rate limit check (only for actual LLM calls)
    from api.rate_limit import (
        BurstCooldown,
        RateLimitExceeded,
        check_rate_limit,
        increment_rate_limit,
    )

    try:
        check_rate_limit(ip_hash, repo)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "reset_at": exc.reset_at.isoformat(),
                "cooldown_seconds": 0,
            },
        ) from exc
    except BurstCooldown as exc:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "reset_at": datetime.now(tz=UTC).isoformat(),
                "cooldown_seconds": exc.cooldown_seconds,
            },
        ) from exc

    # 5a. Global daily spend cap
    _spend_cap = float(os.environ.get("DAILY_SPEND_CAP", "1.00"))
    if repo.get_daily_spend() >= _spend_cap:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "spend_cap_exceeded",
                "message": "Daily generation limit reached. Try again tomorrow.",
            },
        )

    # 5. LLM generation
    from generator.validator import validate_theme
    from providers.registry import generate_with_fallback

    try:
        user_prompt = build_user_prompt(clean_prompt)
        theme_raw, provider_name = generate_with_fallback(user_prompt, SYSTEM_PROMPT)
        validate_theme(theme_raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # 6. Cache result
    from generator.slug import make_slug

    slug = make_slug(clean_prompt[:40])
    try:
        from cache.embeddings import embed

        embedding = embed(clean_prompt)
    except Exception:  # noqa: BLE001, S110
        embedding = None

    repo.save_theme(
        query_hash=query_hash,
        theme_data=theme_raw,
        input_type="prompt",
        query_raw=clean_prompt,
        name=slug,
        embedding=embedding,
        source="ai",
        provider=provider_name,
    )

    # 7. Increment rate limit counter
    increment_rate_limit(ip_hash, repo)

    return GenerateResponse(
        theme_data=theme_raw,
        slug=slug,
        cached=False,
        provider=provider_name,
    )


@app.get("/v1/themes")
def list_themes(
    request: Request,
    sort: str = "newest",
    limit: int = 20,
    offset: int = 0,
):
    """Browse community themes."""
    from generator.slug import make_slug

    repo = request.app.state.repo
    limit = min(limit, 100)

    all_themes = repo.list_themes(limit=1000)

    if sort == "downloads":
        all_themes.sort(key=lambda t: t.get("download_count") or 0, reverse=True)

    total = len(all_themes)
    page = all_themes[offset : offset + limit]

    themes = [
        {
            "id": t["id"],
            "slug": make_slug(t["name"]) if t.get("name") else "",
            "name": t.get("name") or "",
            "download_count": t.get("download_count") or 0,
            "created_at": t.get("created_at") or "",
            "theme_data": t["theme_data"],
        }
        for t in page
    ]

    return {"themes": themes, "total": total, "offset": offset}


@app.get("/v1/themes/{slug}")
def get_theme_by_slug(slug: str, request: Request):
    """Get a single theme by slug."""
    from generator.slug import make_slug

    repo = request.app.state.repo
    all_themes = repo.list_themes(limit=1000)

    for t in all_themes:
        if t.get("name") and make_slug(t["name"]) == slug:
            return {
                "id": t["id"],
                "slug": slug,
                "name": t["name"],
                "theme_data": t["theme_data"],
                "source": t.get("source") or "ai",
                "provider": t.get("provider") or "",
                "created_at": t.get("created_at") or "",
                "download_count": t.get("download_count") or 0,
            }

    raise HTTPException(status_code=404, detail={"error": "not_found"})


@app.post("/v1/themes", status_code=201)
def publish_theme(req: PublishRequest, request: Request):
    """Publish a community theme to the gallery."""
    import hashlib as _hl

    from generator.slug import make_slug
    from generator.validator import validate_theme

    try:
        validate_theme(req.theme_data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    slug = make_slug(req.name)
    repo = request.app.state.repo

    # Check for existing slug
    all_themes = repo.list_themes(limit=1000)
    for t in all_themes:
        if t.get("name") and make_slug(t["name"]) == slug:
            raise HTTPException(status_code=409, detail={"error": "slug_exists", "slug": slug})

    query_hash = _hl.sha256(f"community:{slug}:{req.theme_data[:64]}".encode()).hexdigest()
    repo.save_theme(
        query_hash=query_hash,
        theme_data=req.theme_data,
        input_type="prompt",
        name=req.name,
        source="community",
        provider=None,
    )

    # Fetch the created_at
    saved = repo.get_by_hash(query_hash)
    created_at = saved["created_at"] if saved else ""

    return {"slug": slug, "name": req.name, "created_at": created_at}


@app.post("/v1/themes/{slug}/download")
def download_theme(slug: str, request: Request):
    """Increment download count for a theme."""
    repo = request.app.state.repo
    new_count = repo.increment_download_count(slug)
    if new_count == 0:
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    return {"download_count": new_count}


@app.get("/v1/neofetch/{slug}", response_class=PlainTextResponse)
def neofetch(slug: str, request: Request):
    """Return a text/plain ANSI color block for README embeds."""
    from generator.slug import make_slug

    repo = request.app.state.repo
    all_themes = repo.list_themes(limit=1000)

    theme = None
    for t in all_themes:
        if t.get("name") and make_slug(t["name"]) == slug:
            theme = t
            break

    if theme is None:
        return PlainTextResponse("Theme not found", status_code=404)

    colors = _parse_theme_colors(theme["theme_data"])
    name = theme.get("name") or slug

    lines = [name]
    for row_start in (0, 8):
        row = ""
        for i in range(row_start, row_start + 8):
            hex_color = colors.get(f"palette = {i}", "#888888").lstrip("#")
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            row += f"\x1b[48;2;{r};{g};{b}m  \x1b[0m"
        lines.append(row)

    return PlainTextResponse("\n".join(lines))
