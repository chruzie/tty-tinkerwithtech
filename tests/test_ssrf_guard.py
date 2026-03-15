"""Tests for SSRF guard including edge-case address ranges and IPv4-mapped IPv6."""

from __future__ import annotations

import socket
from unittest.mock import MagicMock, patch

import pytest

from security.ssrf_guard import check_url, safe_fetch


def _mock_getaddrinfo(ip: str):
    """Return a minimal getaddrinfo result for a single IP."""
    return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip, 0))]


def _mock_getaddrinfo_v6(ip: str):
    """Return a minimal getaddrinfo result for an IPv6 address."""
    return [(socket.AF_INET6, socket.SOCK_STREAM, 0, "", (ip, 0, 0, 0))]


class TestExistingBlocks:
    def test_blocks_private_10(self):
        with patch("socket.getaddrinfo", return_value=_mock_getaddrinfo("10.0.0.1")):
            with pytest.raises(ValueError, match="blocked address"):
                check_url("https://internal.example.com/")

    def test_blocks_loopback(self):
        with patch("socket.getaddrinfo", return_value=_mock_getaddrinfo("127.0.0.1")):
            with pytest.raises(ValueError, match="blocked address"):
                check_url("https://localhost/")

    def test_blocks_link_local(self):
        with patch("socket.getaddrinfo", return_value=_mock_getaddrinfo("169.254.1.1")):
            with pytest.raises(ValueError, match="blocked address"):
                check_url("https://link-local.example.com/")

    def test_allows_public_ip(self):
        with patch("socket.getaddrinfo", return_value=_mock_getaddrinfo("93.184.216.34")):
            check_url("https://example.com/")  # should not raise


class TestNewBlockRanges:
    def test_blocks_zero_network(self):
        """0.0.0.0/8 (this-host) must be blocked."""
        with patch("socket.getaddrinfo", return_value=_mock_getaddrinfo("0.0.0.1")):
            with pytest.raises(ValueError, match="blocked address"):
                check_url("https://0.0.0.1/")

    def test_blocks_0_0_0_0(self):
        with patch("socket.getaddrinfo", return_value=_mock_getaddrinfo("0.0.0.0")):  # noqa: S104
            with pytest.raises(ValueError, match="blocked address"):
                check_url("https://0.0.0.0/")

    def test_blocks_cgnat(self):
        """100.64.0.0/10 (IANA Shared Address Space / CGNAT) must be blocked."""
        with patch("socket.getaddrinfo", return_value=_mock_getaddrinfo("100.64.1.1")):
            with pytest.raises(ValueError, match="blocked address"):
                check_url("https://100.64.1.1/")

    def test_blocks_cgnat_edge(self):
        with patch("socket.getaddrinfo", return_value=_mock_getaddrinfo("100.127.255.255")):
            with pytest.raises(ValueError, match="blocked address"):
                check_url("https://cgnat.example.com/")


class TestIPv4MappedIPv6:
    def test_blocks_ipv4_mapped_loopback(self):
        """::ffff:127.0.0.1 must be treated as 127.0.0.1 and blocked."""
        with patch("socket.getaddrinfo", return_value=_mock_getaddrinfo_v6("::ffff:127.0.0.1")):
            with pytest.raises(ValueError, match="IPv4-mapped"):
                check_url("https://[::ffff:127.0.0.1]/")

    def test_blocks_ipv4_mapped_private(self):
        """::ffff:192.168.1.1 must be treated as private and blocked."""
        with patch("socket.getaddrinfo", return_value=_mock_getaddrinfo_v6("::ffff:192.168.1.1")):
            with pytest.raises(ValueError, match="IPv4-mapped"):
                check_url("https://example.com/")

    def test_allows_ipv4_mapped_public(self):
        """::ffff:93.184.216.34 is a public IP and should be allowed."""
        with patch("socket.getaddrinfo", return_value=_mock_getaddrinfo_v6("::ffff:93.184.216.34")):
            check_url("https://example.com/")  # should not raise


class TestSchemeValidation:
    def test_rejects_http(self):
        with pytest.raises(ValueError, match="Only https"):
            check_url("http://example.com/")

    def test_rejects_ftp(self):
        with pytest.raises(ValueError, match="Only https"):
            check_url("ftp://example.com/")


class TestSafeFetch:
    """safe_fetch must reject blocked IPs and not allow a second DNS lookup."""

    def test_rejects_loopback_dns(self):
        """safe_fetch raises ValueError when DNS resolves to 127.0.0.1 (DNS rebinding scenario)."""
        loopback = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 0))]
        with patch("socket.getaddrinfo", return_value=loopback):
            with pytest.raises(ValueError, match="blocked address"):
                safe_fetch("https://example.com/")

    def test_rejects_private_dns(self):
        """safe_fetch raises ValueError when DNS resolves to an RFC1918 address."""
        private = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("192.168.1.100", 0))]
        with patch("socket.getaddrinfo", return_value=private):
            with pytest.raises(ValueError, match="blocked address"):
                safe_fetch("https://example.com/")

    def test_calls_httpx_with_resolved_ip(self):
        """safe_fetch calls httpx.get with the IP-substituted URL, not the original hostname."""
        public = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]
        mock_response = MagicMock()

        with patch("socket.getaddrinfo", return_value=public):
            with patch("security.ssrf_guard.httpx") as mock_httpx:
                mock_httpx.get.return_value = mock_response
                result = safe_fetch("https://example.com/path")

        mock_httpx.get.assert_called_once()
        call_url = mock_httpx.get.call_args[0][0]
        # The URL passed to httpx must contain the IP, not the hostname
        assert "93.184.216.34" in call_url
        assert "example.com" not in call_url
        # Host header must be set to the original hostname
        call_headers = mock_httpx.get.call_args[1]["headers"]
        assert call_headers.get("Host") == "example.com"
        assert result is mock_response
