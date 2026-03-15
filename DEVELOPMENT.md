# tty-theme — Local Development Guide

Everything runs locally. No real GCP account required.

---

## Prerequisites

| Tool | Purpose | Install |
|------|---------|---------|
| Docker Desktop | Runs API + Firebase Emulator Suite | https://docker.com |
| Node 18+ / npm | Runs `firebase` CLI for emulator | `brew install node` |
| `firebase-tools` | Firebase Emulator Suite | `npm install -g firebase-tools` |
| Python 3.11+ / uv | CLI and tests | https://astral.sh/uv |

---

## Quick Start (5 minutes)

```bash
# 1. Clone and enter the project
git clone https://github.com/chruzie/tty-tinkerwithtech
cd ghostty-theme

# 2. Create your .env
cp .env.example .env
# Optionally add a GEMINI_API_KEY, GROQ_API_KEY, etc. to .env.
# Local providers (Ollama, LM Studio) need no keys.

# 3. Start the full local stack
docker compose up

# 4. Verify everything is running
curl http://localhost:8000/health          # API → {"status": "ok"}
open http://localhost:4000                 # Firebase Emulator UI
```

---

## Local Service Map

| Service | URL | What it does |
|---------|-----|-------------|
| FastAPI | http://localhost:8000 | tty-theme REST API |
| Firebase Emulator UI | http://localhost:4000 | Inspect Firestore, Auth |
| Firestore Emulator | localhost:8080 | Database (auto-used by SDK) |
| Auth Emulator | localhost:9099 | GitHub-free OAuth for local dev |
| Hosting Emulator | http://localhost:5000 | Web UI (after `npm run build`) |
| Prometheus (opt.) | http://localhost:9090 | Local metrics dashboard |

---

## Running with Optional Monitoring

```bash
docker compose --profile monitoring up
# Then open http://localhost:9090
```

---

## CLI Development (no Docker needed)

```bash
# Install all deps
uv sync --extra dev

# Run CLI directly
uv run tty-theme --help
uv run tty-theme seed                              # load community themes
uv run tty-theme generate --prompt "tokyo night"  # needs a local/cloud provider
uv run tty-theme config status                     # check providers + cache
```

---

## Web UI Development

```bash
cd web
npm install
npm run dev          # Vite dev server → http://localhost:5173 (hot reload)
# or
npm run build        # Build web/dist
firebase emulators:start --only hosting   # serve at http://localhost:5000
```

---

## Firebase Auth — Local Testing

The Auth Emulator **bypasses real GitHub OAuth**. Create test users in the UI:

1. Open http://localhost:4000/auth
2. Click "Add user"
3. Fill in a display name and email
4. Use that account to test authenticated endpoints

---

## Seeding Test Data in Firestore

In the Emulator UI (http://localhost:4000):
- Firestore tab → start a collection named `themes`
- Or: run `uv run tty-theme seed` to populate via the CLI

Data persists in the `firebase-data` Docker volume between restarts.
To reset: `docker compose down -v`

---

## Running Tests

```bash
uv sync --extra dev --extra api
uv run pytest -q                           # all tests
uv run pytest tests/test_api.py -v        # API tests only
FIRESTORE_EMULATOR_HOST=localhost:8080 \
  uv run pytest tests/test_firestore.py   # Firestore emulator tests
```

---

## Environment Variables Reference

See `.env.example` for the full list. Key variables:

| Variable | Default | Notes |
|----------|---------|-------|
| `ENVIRONMENT` | `development` | `development` uses SQLite + .env; anything else uses Firestore + Secret Manager |
| `FIRESTORE_EMULATOR_HOST` | `localhost:8080` | Auto-routed by Firestore SDK |
| `FIREBASE_AUTH_EMULATOR_HOST` | `localhost:9099` | Auto-routed by firebase-admin SDK |
| `DAILY_SPEND_CAP` | `10.0` | USD cap per day before API returns 503 |

---

## 1:1 Parity with Production

The local stack is designed to be identical to production:

| Local | Production |
|-------|-----------|
| SQLite (when `ENVIRONMENT=development`) | Firestore (when `FIRESTORE_PROJECT` set) |
| `.env` file | Google Cloud Secret Manager |
| `docker compose up api` | Cloud Run (auto-scaled) |
| `firebase emulators:start` | Firebase Hosting + Auth |
| Prometheus Docker Compose profile | Google Cloud Monitoring |

To switch to production mode locally (for testing the Firestore adapter):
```bash
ENVIRONMENT=staging FIRESTORE_PROJECT=tty-theme-local \
  FIRESTORE_EMULATOR_HOST=localhost:8080 \
  uv run uvicorn api.main:app --reload
```

See **DEPLOY.md** for the actual GCP production deploy commands.
