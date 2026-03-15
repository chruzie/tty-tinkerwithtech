"""tty-theme CLI entry point."""

from __future__ import annotations

import json
import re
from pathlib import Path

import typer

app = typer.Typer(
    name="tty-theme",
    help="Generate terminal colour themes from a prompt or image.",
    no_args_is_help=True,
)
config_app = typer.Typer(help="Configuration commands.")
app.add_typer(config_app, name="config")

# ── Install paths ──────────────────────────────────────────────────────────────

_GHOSTTY_THEMES = Path.home() / ".config" / "ghostty" / "themes"
_ITERM2_THEMES = Path.home() / "Library" / "Application Support" / "iTerm2" / "DynamicProfiles"


def _install_theme(name: str, content: str, target: str, force: bool = False) -> Path | None:
    """Write theme file to the target application's themes directory.

    Returns:
        Destination path on success, or None if dest exists and force=False.
    """
    if target == "ghostty":
        dest_dir = _GHOSTTY_THEMES
        ext = ""  # Ghostty themes have no extension
    elif target == "iterm2":
        dest_dir = _ITERM2_THEMES
        ext = ".itermcolors"
    else:
        raise ValueError(f"Unknown target: {target!r}")

    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = name.replace(" ", "-").lower()
    if not re.match(r"^[a-z0-9][a-z0-9_-]*$", safe_name):
        raise ValueError(
            f"Invalid theme name {name!r}. Names must start with a letter or digit "
            "and contain only letters, digits, hyphens, and underscores."
        )
    dest = dest_dir / f"{safe_name}{ext}"
    if dest.exists() and not force:
        typer.echo(
            f"Theme {safe_name!r} already exists at {dest}. Use --force to overwrite.",
            err=True,
        )
        return None
    dest.write_text(content)
    return dest


# ── generate command ──────────────────────────────────────────────────────────

@app.command()
def generate(
    prompt: str | None = typer.Option(None, "--prompt", "-p", help="Natural-language prompt."),
    image: Path | None = typer.Option(None, "--image", "-i", help="Image file or HTTPS URL."),
    target: str = typer.Option("ghostty", "--target", "-t", help="ghostty | iterm2"),
    install: bool = typer.Option(False, "--install", help="Install into target app."),
    name: str | None = typer.Option(None, "--name", "-n", help="Theme name (with --install)."),
    provider_name: str | None = typer.Option(None, "--provider", help="Force a specific provider."),
    refine: bool = typer.Option(False, "--refine", help="LLM refinement pass (image mode only)."),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing theme."),
) -> None:
    """Generate a terminal colour theme."""
    if not prompt and not image:
        typer.echo(
            "Error: at least one input is required.\n"
            "\n"
            "  tty-theme generate --prompt 'tokyo midnight'\n"
            "  tty-theme generate --image ./photo.jpg\n"
            "\n"
            "Run tty-theme generate --help for all options.",
            err=True,
        )
        raise typer.Exit(1)

    try:
        typer.echo("searching cache...", err=True)

        from providers.registry import resolve_provider

        try:
            provider = resolve_provider(preferred=provider_name)
        except RuntimeError:
            typer.echo(
                "No LLM provider available. Run tty-theme config setup to add an API key, "
                "or start Ollama with: ollama serve",
                err=True,
            )
            raise typer.Exit(1) from None

        typer.echo(f"  generating via {getattr(provider, 'name', 'unknown')}...", err=True)

        if prompt:
            from modes.prompt_mode import generate_from_prompt
            theme_str, _ = generate_from_prompt(prompt, provider=provider, target=target)
        else:
            from modes.image_mode import generate_from_image
            src = str(image) if image else ""
            theme_str, _ = generate_from_image(src, target=target, refine=refine, provider=provider)

    except (typer.Exit, SystemExit):
        raise
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from None

    typer.echo(theme_str)

    if install:
        if not name:
            typer.echo("Error: --name is required when using --install.", err=True)
            raise typer.Exit(1)
        dest = _install_theme(name, theme_str, target, force=force)
        if dest is None:
            raise typer.Exit(1)
        typer.echo(f"\nInstalled to: {dest}", err=True)
        if target == "ghostty":
            safe = name.replace(" ", "-").lower()
            typer.echo(
                f"To activate: add `theme = {safe}` to ~/.config/ghostty/config",
                err=True,
            )
        elif target == "iterm2":
            safe = name.replace(" ", "-").lower()
            typer.echo(
                f"To activate: open iTerm2 → Preferences → Profiles → Colors "
                f"→ Color Presets → {safe}",
                err=True,
            )


# ── config commands ────────────────────────────────────────────────────────────

@config_app.command("setup")
def config_setup() -> None:
    """Interactive first-run wizard to configure API keys."""
    from security.keystore import set_key

    typer.echo("tty-theme config wizard")
    typer.echo("─" * 40)
    typer.echo("Press Enter to skip any provider.\n")

    providers = [
        ("gemini", "Google Gemini API key"),
        ("groq", "Groq API key (free tier)"),
        ("anthropic", "Anthropic API key"),
        ("openai", "OpenAI API key"),
        ("mistral", "Mistral API key"),
    ]

    for key_name, label in providers:
        val = typer.prompt(f"{label}", default="", hide_input=True, show_default=False)
        if val.strip():
            set_key(key_name, val.strip())
            typer.echo(f"  ✓ {key_name} saved to keychain")

    typer.echo("\nSetup complete. Run 'tty-theme generate --prompt ...' to get started.")


@config_app.command("status")
def config_status() -> None:
    """Show provider availability, cache stats, and spend."""
    from cache.db import ThemeRepository

    repo = ThemeRepository()
    repo.init_db()

    typer.echo("Provider availability:")
    from providers.registry import _build_chain

    for p in _build_chain():
        status = "✓ running" if p.health_check() else "✗ offline"
        typer.echo(f"  {p.name:12} {status}")

    typer.echo(f"\nCache: {repo.db_path}")
    themes = repo.list_themes(limit=5)
    typer.echo(f"  Cached themes: {len(repo.list_themes(limit=10000))}")
    if themes:
        typer.echo("  Recent themes:")
        for t in themes:
            typer.echo(f"    {t['created_at'][:16]}  {t.get('query_raw', '(image)')[:40]}")

    spend = repo.get_daily_spend()
    typer.echo(f"\nToday's spend: ${spend:.4f}")


# ── seed command ───────────────────────────────────────────────────────────────

@app.command()
def seed() -> None:
    """Load pre-seeded community themes into the local cache."""
    from cache.db import ThemeRepository

    index_path = Path(__file__).parent.parent / "themes" / "index.json"
    if not index_path.exists():
        typer.echo("themes/index.json not found.", err=True)
        raise typer.Exit(1)

    themes = json.loads(index_path.read_text())
    repo = ThemeRepository()
    repo.init_db()

    count = 0
    import hashlib

    for theme in themes:
        q_hash = hashlib.sha256(theme["name"].encode()).hexdigest()
        if not repo.get_by_hash(q_hash):
            repo.save_theme(
                query_hash=q_hash,
                theme_data=theme["ghostty_data"],
                input_type="prompt",
                query_raw=theme["name"],
                name=theme["name"],
                source="community",
            )
            count += 1

    typer.echo(f"Seeded {count} theme(s) into cache.")


# ── search command ─────────────────────────────────────────────────────────────

@app.command()
def search(
    query: str = typer.Argument(..., help="Search term."),
    limit: int = typer.Option(10, "--limit", "-l"),
) -> None:
    """Search cached themes by name."""
    from cache.db import ThemeRepository

    repo = ThemeRepository()
    repo.init_db()

    all_themes = repo.list_themes(limit=10000)
    matches = [t for t in all_themes if query.lower() in (t.get("query_raw") or "").lower()][:limit]

    if not matches:
        typer.echo("No matches found.")
        return

    for t in matches:
        typer.echo(f"{t['id']:4}  {t['created_at'][:16]}  {t.get('query_raw', '')[:50]}")


if __name__ == "__main__":
    app()
