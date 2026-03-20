"""Tests for X-Forwarded-For trusted-proxy logic in _ip_hash (US-005)."""

from __future__ import annotations

import hashlib
from unittest.mock import MagicMock, patch


def _make_request(xff: str | None = None, client_host: str = "10.0.0.1") -> MagicMock:
    """Build a minimal mock Request object."""
    req = MagicMock()
    req.client = MagicMock()
    req.client.host = client_host
    headers_mock = MagicMock()
    headers_mock.get = lambda key, default=None: (
        {"X-Forwarded-For": xff}.get(key, default) if xff is not None else default
    )
    req.headers = headers_mock
    return req


def _sha(ip: str) -> str:
    return hashlib.sha256(ip.encode()).hexdigest()[:16]


class TestIpHashNoProxy:
    """TRUSTED_PROXY_COUNT=0 (default) — XFF is ignored."""

    def test_ignores_xff_when_no_proxy(self):
        from api.middleware import _ip_hash

        req = _make_request(xff="1.2.3.4", client_host="10.0.0.99")
        with patch.dict("os.environ", {"TRUSTED_PROXY_COUNT": "0"}):
            result = _ip_hash(req)
        assert result == _sha("10.0.0.99")

    def test_uses_client_host_when_no_xff_and_no_proxy(self):
        from api.middleware import _ip_hash

        req = _make_request(xff=None, client_host="10.0.0.1")
        with patch.dict("os.environ", {"TRUSTED_PROXY_COUNT": "0"}):
            result = _ip_hash(req)
        assert result == _sha("10.0.0.1")

    def test_default_is_no_proxy(self):
        """When TRUSTED_PROXY_COUNT is not set, XFF is ignored."""
        import os

        from api.middleware import _ip_hash

        req = _make_request(xff="evil.client.ip", client_host="10.0.0.2")
        os.environ.pop("TRUSTED_PROXY_COUNT", None)
        with patch.dict("os.environ", {}, clear=False):
            os.environ.pop("TRUSTED_PROXY_COUNT", None)
            result = _ip_hash(req)
        assert result == _sha("10.0.0.2")


class TestIpHashOneProxy:
    """TRUSTED_PROXY_COUNT=1 — trust the last XFF entry (rightmost)."""

    def test_single_xff_entry(self):
        from api.middleware import _ip_hash

        req = _make_request(xff="203.0.113.5", client_host="10.0.0.1")
        with patch.dict("os.environ", {"TRUSTED_PROXY_COUNT": "1"}):
            result = _ip_hash(req)
        # With 1 proxy, idx = max(0, 1-1) = 0 → first (and only) entry
        assert result == _sha("203.0.113.5")

    def test_multiple_xff_entries_picks_nth_from_right(self):
        """Client → intermediate proxy → GFE → Cloud Run.
        XFF: client_ip, intermediate_ip
        With TRUSTED_PROXY_COUNT=1 we trust the rightmost hop → intermediate_ip.
        """
        from api.middleware import _ip_hash

        req = _make_request(xff="203.0.113.5, 198.51.100.1", client_host="10.0.0.1")
        with patch.dict("os.environ", {"TRUSTED_PROXY_COUNT": "1"}):
            result = _ip_hash(req)
        # parts = ["203.0.113.5", "198.51.100.1"], idx = max(0, 2-1) = 1 → "198.51.100.1"
        assert result == _sha("198.51.100.1")

    def test_no_xff_falls_back_to_client_host(self):
        from api.middleware import _ip_hash

        req = _make_request(xff=None, client_host="10.0.0.1")
        with patch.dict("os.environ", {"TRUSTED_PROXY_COUNT": "1"}):
            result = _ip_hash(req)
        assert result == _sha("10.0.0.1")

    def test_spoofed_xff_ignored_without_trusted_proxy(self):
        """With TRUSTED_PROXY_COUNT=0, a spoofed XFF header cannot bypass rate limit."""
        from api.middleware import _ip_hash

        spoofed = _make_request(xff="127.0.0.1", client_host="203.0.113.99")
        legit = _make_request(xff=None, client_host="203.0.113.99")
        with patch.dict("os.environ", {"TRUSTED_PROXY_COUNT": "0"}):
            assert _ip_hash(spoofed) == _ip_hash(legit)
