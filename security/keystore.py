"""API key management via OS keychain (keyring library)."""

from __future__ import annotations

import keyring

_SERVICE = "tty-theme"


def get_key(provider: str) -> str | None:
    """Return the stored API key for *provider*, or None if not set."""
    return keyring.get_password(_SERVICE, provider)


def set_key(provider: str, key: str) -> None:
    """Persist *key* for *provider* in the OS keychain."""
    keyring.set_password(_SERVICE, provider, key)


def delete_key(provider: str) -> None:
    """Remove the stored key for *provider* (noop if not present)."""
    try:
        keyring.delete_password(_SERVICE, provider)
    except keyring.errors.PasswordDeleteError:
        pass
