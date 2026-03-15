.PHONY: install dev api ui test lint generate neofetch

install:  ## Install all dependencies with uv
	uv sync

dev:      ## Start API (:8000) + UI (:3000) — run in split terminals
	@echo "Run 'make api' in one terminal and 'make ui' in another"
	@echo "Or: tmux new-session \; split-window -h \; send-keys 'make api' Enter \; select-pane -t 0 \; send-keys 'make ui' Enter"

api:      ## Start FastAPI backend on :8000 with hot-reload
	uv run uvicorn api.main:app --reload --port 8000

ui:       ## Serve web UI on :3000 (no build step)
	@echo "Web UI → http://localhost:3000"
	@echo "API    → http://localhost:8000"
	cd web && python3 -m http.server 3000

test:     ## Run test suite
	uv run pytest -v

lint:     ## Ruff lint + format check + bandit security scan
	uv run ruff check .
	uv run ruff format --check .
	uv run bandit -r . -c pyproject.toml

generate: ## Quick CLI generation — usage: make generate PROMPT="tokyo midnight"
	uv run tty-theme generate --prompt "$(PROMPT)"

neofetch: ## Show neofetch info for a theme — usage: make neofetch THEME=cyberpunk-neon-rain
	uv run tty-theme neofetch --theme "$(THEME)"

audit:    ## Dependency CVE scan
	uv run pip-audit
