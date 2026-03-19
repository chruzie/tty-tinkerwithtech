"""Unified secret access — .env in development, Secret Manager in production.

Usage:
    from security.secrets import get_secret
    key = get_secret("GEMINI_API_KEY")

The call site is identical in both environments. The only difference is
the backend:
  - ENVIRONMENT=development (or no GCP_PROJECT set): reads from os.environ
    (populated from .env via python-dotenv at app startup).
  - Production: reads from Google Cloud Secret Manager.
"""

from __future__ import annotations

import os
import re

_SECRET_NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")


def _is_development() -> bool:
    return os.environ.get("ENVIRONMENT", "development") == "development" or not os.environ.get(
        "GCP_PROJECT"
    )


def get_secret(name: str) -> str:
    """Return the value of secret *name*.

    Raises:
        ValueError: if name does not match r'^[A-Z_][A-Z0-9_]*$'.
        KeyError: if the secret is not found.
        RuntimeError: if Secret Manager call fails.
    """
    if not _SECRET_NAME_RE.match(name):
        raise ValueError(f"Invalid secret name: {name}")

    if _is_development():
        val = os.environ.get(name)
        if val:
            return val
        raise KeyError(
            f"Secret {name!r} not found in environment. "
            f"Add it to your .env file (see .env.example)."
        )

    # Production: Google Cloud Secret Manager
    project = os.environ["GCP_PROJECT"]
    try:
        from google.cloud import secretmanager  # type: ignore[import]

        client = secretmanager.SecretManagerServiceClient()
        secret_name = f"projects/{project}/secrets/{name}/versions/latest"
        response = client.access_secret_version(request={"name": secret_name})
        return response.payload.data.decode("utf-8")
    except Exception as exc:
        raise RuntimeError(f"Failed to access secret {name!r} from Secret Manager: {exc}") from exc


def load_dotenv_if_dev() -> None:
    """Load .env into os.environ when running in development mode.

    Call once at application startup (api/main.py or cli/main.py).
    Silently no-ops if .env does not exist or python-dotenv is not installed.
    """
    if not _is_development():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(override=False)
    except ImportError:
        pass
