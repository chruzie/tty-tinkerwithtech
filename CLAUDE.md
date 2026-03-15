# tty-theme — Claude Code Context

## Workflow Instructions (follow every session)

1. **PRD-first:** Whenever the user requests a new feature, change, or design decision, **update `PRD.md` first** before touching any code or mockup. The PRD is the single source of truth. Add or modify the relevant section with full spec detail.

2. **After updating the PRD**, always ask:
   > "PRD updated. Do you want me to use Ralph to execute this phase now?"

   Wait for the user's answer before proceeding to implement.

3. **Mockup stays in sync:** After any PRD update, also reflect the change in `mockup.html` so it remains a live preview of the spec.

4. **Commit after every meaningful change** with a descriptive message referencing the PRD version/section.

---

## What This Project Is

`tty-theme` is an open source CLI tool (and planned web UI) that generates terminal color themes from two input modes:

1. **Prompt mode** — natural-language inspiration query (e.g. "cyberpunk neon rain")
2. **Image mode** — extract a harmonious palette from any image (local file or HTTPS URL)

Supports output for **Ghostty** (key=value text) and **iTerm2** (XML plist `.itermcolors`). Extensible to Alacritty, WezTerm, Kitty, etc. in v2.

GitHub: https://github.com/chruzie/tty-tinkerwithtech
PRD: `PRD.md` — authoritative design doc, read this first.
Mockup: `mockup.html` — open in browser, fully interactive, no build step.

---

## Architecture

### Generation Pipeline

```
User Input (prompt or image)
    │
    ├─[prompt]─▶ sanitize → normalize → cache lookup (exact) →
    │            similarity search (embeddings) → LLM generate → validate → cache
    │
    └─[image]──▶ validate (magic bytes, SSRF guard) → load → pHash →
                 cache lookup → k-means extract → palette map → (optional LLM refine) → validate → cache
                     │
                     ▼
              Normalized Palette (16 ANSI + 5 semantic hex colors)
                     │
              ┌──────┴──────┐
              ▼             ▼
         Ghostty        iTerm2
        serializer     serializer
        (key=value)    (XML plist)
```

### Provider Chain (cost-ordered, 429-aware auto-fallback)

One `OpenAICompatProvider` class handles all providers — they all speak `POST /v1/chat/completions`.

```
Local (no key needed):
  Ollama (11434) → LM Studio (1234) → llamafile (8080)

Free cloud (key required, 429 → auto-fallback to next):
  Groq → Gemini 2.0 Flash

Paid optional fallback:
  OpenAI gpt-4o-mini → Mistral small
```

Key function: `providers/registry.py::generate_with_fallback()` — catches HTTP 429 and transparently tries the next provider. Non-429 errors propagate immediately.

To force a provider: `tty-theme generate --prompt "..." --provider groq`

### Tiered Cache (prompt mode)

- **Tier 1** — Exact SHA256 hash match → return cached theme (free)
- **Tier 2** — Cosine similarity via MiniLM embeddings, threshold 0.85 → return closest match (free)
- **Tier 3** — LLM generation → cache result

Image mode uses **pHash** as cache key instead.

### Key Components

| Path | Responsibility |
|------|----------------|
| `cli/main.py` | Typer CLI entry point |
| `modes/prompt_mode.py` | Full prompt pipeline |
| `modes/image_mode.py` | Full image pipeline |
| `generator/llm.py` | Provider-agnostic LLM client |
| `generator/validator.py` | Schema + WCAG contrast validation |
| `generator/serializers/ghostty.py` | Ghostty key=value output |
| `generator/serializers/iterm2.py` | iTerm2 XML plist output |
| `generator/serializers/base.py` | `ThemeSerializer` abstract base |
| `image/loader.py` | Safe image loading (SSRF guard, magic bytes) |
| `image/extractor.py` | k-means color clustering |
| `image/phash.py` | Perceptual hash |
| `cache/db.py` | SQLite CRUD (repository pattern) |
| `cache/firestore_db.py` | Firestore repository (same interface, cloud/emulator) |
| `cache/embeddings.py` | MiniLM local embeddings + cosine similarity |
| `providers/openai_compat.py` | Single provider class + CATALOGUE for all LLMs |
| `providers/registry.py` | Health checks, provider resolution, 429 fallback |
| `api/main.py` | FastAPI app (Cloud Run target) |
| `api/middleware.py` | Rate limiting (token bucket) + audit log |
| `security/keystore.py` | OS keychain key management (`keyring` lib) |
| `security/secrets.py` | `get_secret()` — `.env` in dev, Secret Manager in prod |
| `security/ssrf_guard.py` | RFC1918 + loopback blocklist for remote URLs |
| `security/input_sanitizer.py` | Prompt sanitization, unicode normalization |
| `themes/index.json` | ~50 pre-seeded community themes (MIT/CC0) |

### Data Storage

**CLI mode:** SQLite, local at `~/.local/share/tty-theme/cache.db`
**API/web mode:** Firestore (via emulator locally, Cloud Firestore in prod)

Switch is env-var driven: if `FIRESTORE_PROJECT` is set → `FirestoreThemeRepository`; else → `ThemeRepository` (SQLite).

Embeddings stored as **JSON arrays** (`json.dumps(vector.tolist())`). API keys stored in **OS keychain** (never config files).

### Local Development Stack (Docker Compose)

```
docker compose up
```

| Service | Port | GCP Equivalent |
|---------|------|----------------|
| `api` | 8000 | Cloud Run |
| `firebase-emulator` (Firestore) | 8080 | Cloud Firestore |
| `firebase-emulator` (Auth) | 9099 | Firebase Auth |
| `firebase-emulator` (UI) | 4000 | — |
| `prometheus` | 9090 | Cloud Monitoring |

`FIRESTORE_EMULATOR_HOST=localhost:8080` auto-routes the Firestore SDK to the emulator — no code changes between local and prod.

### Secrets Pattern

`security/secrets.py::get_secret(name)`:
- `ENVIRONMENT=development` (or no `GCP_PROJECT`) → reads from `.env` via python-dotenv
- Production → reads from Google Cloud Secret Manager

Same call site everywhere; no `if dev / else prod` scattered through the codebase.

---

## Community Gallery

Users can publish themes to `tty-theme.dev`. Gallery features:
- Sort by **downloads** or **likes**
- Filter by terminal target (Ghostty / iTerm2)
- Shareable URLs: `tty-theme.dev/t/<slug>`
- CLI install: `tty-theme install <slug>`
- Auth via GitHub OAuth only (no email/password)

---

## CLI Reference

```bash
tty-theme config setup                          # first-run wizard (saves keys to OS keychain)
tty-theme config status                         # provider availability, cache stats, spend
tty-theme generate --prompt "tokyo midnight"    # prompt → Ghostty (default)
tty-theme generate --prompt "..." --target iterm2
tty-theme generate --prompt "..." --provider groq  # force specific provider
tty-theme generate --image ./photo.jpg --target ghostty
tty-theme generate --image ./photo.jpg --refine    # + LLM refinement pass
tty-theme generate --prompt "..." --install --name "my-theme"
tty-theme search "ocean"
tty-theme browse --sort downloads
tty-theme install cyberpunk-neon-rain --target ghostty
tty-theme publish "my-theme" --target ghostty --target iterm2
tty-theme share "my-theme"
tty-theme seed                                  # load community themes into local cache
```

---

## Development Commands

```bash
# Setup
cp .env.example .env
uv sync

# Full local stack (API + Firebase Emulator + Prometheus)
docker compose up

# CLI only (no Docker needed for local Ollama/basic use)
uv run tty-theme --help

# Tests
uv run pytest

# Lint + format
uv run ruff check .
uv run ruff format .

# Security scan
uv run pip-audit
uv run bandit -r . -c pyproject.toml

# Terraform (local validation only — never apply locally)
cd terraform
terraform init -backend=false
terraform validate
terraform plan -var-file=terraform.tfvars  # dry-run only

# Open mockup in browser
open mockup.html
```

---

## Terraform IaC

`terraform/` provisions the full GCP stack: IAM, Artifact Registry, Secret Manager, Firestore, Cloud Run, Cloud Monitoring. See `DEPLOY.md` for the production deploy workflow.

**Never run `terraform apply` locally.** All prod deployments go through Cloud Build CI (`cloudbuild.yaml`).

Secret *values* are never in Terraform state — only shells are declared. Values are set via `gcloud secrets versions add` (see `DEPLOY.md`).

---

## Security Rules (non-negotiable)

- **Embeddings use JSON serialization** — `json.dumps(vector.tolist())` / `json.loads()` only. Never use binary object serialization formats on external data.
- **No API keys in config files** — OS keychain (`keyring`) for CLI, Secret Manager for API. Never `.env` in prod.
- **No raw IP in logs** — store `SHA256(IP)[:16]` only
- **SSRF guard on all remote URLs** — block RFC1918, loopback, link-local before fetching
- **Magic-byte validation on images** — never trust file extensions
- **Structural output validation** — LLM output accepted only if it parses as valid hex color key=value pairs
- **`bandit` S-rules enforced** — `eval`, `exec`, and unsafe deserialization are banned via ruff/bandit config
- **No GCP project IDs, real credentials, or `.env` files committed** — `.gitignore` covers `.env`, `*.tfvars`, `*.tfstate`

---

## Key Design Decisions

- **Single provider class** — `OpenAICompatProvider` handles all LLMs; switching providers = changing CATALOGUE entry, not code
- **429 auto-fallback** — `generate_with_fallback()` in `providers/registry.py` tries next provider on throttle; user gets a theme even when one service is down
- **Repository pattern** — `ThemeRepository` (SQLite) and `FirestoreThemeRepository` share same interface; swapped via env var at runtime
- **Serializer pattern** in `generator/serializers/` — adding a new terminal target = one new file implementing `ThemeSerializer`
- **Local-first emulator parity** — `docker compose up` gives exact same stack as GCP; `FIRESTORE_EMULATOR_HOST` makes SDK auto-route
- **`security/secrets.py` abstraction** — same `get_secret(name)` call works in dev (`.env`) and prod (Secret Manager)
- **pHash for images** — near-identical images share a cached theme without any LLM call
- **JSON embeddings** — avoids unsafe deserialization vulnerabilities on any external data
