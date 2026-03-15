# tty-theme — Claude Code Context

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

### Provider Chain (cost-ordered, first available wins)

```
Ollama (local) → LM Studio (local) → llamafile (local) →
Gemini Flash → Groq (free tier) → Claude Haiku → GPT-4o-mini → Mistral
```

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
| `serializers/ghostty.py` | Ghostty key=value output |
| `serializers/iterm2.py` | iTerm2 XML plist output |
| `serializers/base.py` | `ThemeSerializer` abstract base |
| `image/loader.py` | Safe image loading (SSRF guard, magic bytes) |
| `image/extractor.py` | k-means color clustering |
| `image/phash.py` | Perceptual hash |
| `cache/db.py` | SQLite CRUD (repository pattern, swappable to Postgres) |
| `cache/embeddings.py` | MiniLM local embeddings + cosine similarity |
| `providers/` | One file per LLM provider adapter |
| `security/keystore.py` | OS keychain key management (`keyring` lib) |
| `security/ssrf_guard.py` | RFC1918 + loopback blocklist for remote URLs |
| `security/input_sanitizer.py` | Prompt sanitization, unicode normalization |
| `themes/index.json` | ~50 pre-seeded community themes (MIT/CC0) |

### Data Storage

**CLI mode:** SQLite, local at `~/.local/share/tty-theme/cache.db`
**API/web mode:** PostgreSQL + pgvector (similarity), Redis (cache + rate limits)

Embeddings stored as **JSON arrays** (`json.dumps(vector.tolist())`). API keys stored in **OS keychain** (never config files).

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
tty-theme config setup                          # first-run wizard
tty-theme generate --prompt "tokyo midnight"    # prompt → Ghostty (default)
tty-theme generate --prompt "..." --target iterm2
tty-theme generate --image ./photo.jpg --target ghostty
tty-theme generate --image ./photo.jpg --refine # + LLM refinement pass
tty-theme generate --prompt "..." --install --name "my-theme"
tty-theme search "ocean"
tty-theme browse --sort downloads
tty-theme install cyberpunk-neon-rain --target ghostty
tty-theme publish "my-theme" --target ghostty --target iterm2
tty-theme share "my-theme"
tty-theme config status                         # spend, provider, cache stats
```

---

## Development Commands

```bash
# Install deps
uv sync

# Run CLI
uv run tty-theme --help

# Tests
uv run pytest

# Lint + format
uv run ruff check .
uv run ruff format .

# Security scan
uv run pip-audit
uv run bandit -r . -c pyproject.toml

# Open mockup in browser
open mockup.html
```

---

## Security Rules (non-negotiable)

- **Embeddings use JSON serialization** — `json.dumps(vector.tolist())` / `json.loads()` only. Never use binary object serialization formats on external data.
- **No API keys in config files** — OS keychain (`keyring`) or env vars only
- **No raw IP in logs** — store `SHA256(IP)` only
- **SSRF guard on all remote URLs** — block RFC1918, loopback, link-local before fetching
- **Magic-byte validation on images** — never trust file extensions
- **Structural output validation** — LLM output accepted only if it parses as valid hex color key=value pairs
- **`bandit` S-rules enforced** — `eval`, `exec`, and unsafe deserialization are banned via ruff/bandit config

---

## Key Design Decisions

- **Repository pattern** in `cache/db.py` — SQLite for CLI, swapped to Postgres for hosted API without changing callers
- **Serializer pattern** in `serializers/` — adding a new terminal target = one new file implementing `ThemeSerializer`
- **Provider chain** — resolves local-first, cloud as fallback; user never pays if Ollama is running
- **pHash for images** — near-identical images share a cached theme without any LLM call
- **JSON embeddings** — avoids unsafe deserialization vulnerabilities on any external data
