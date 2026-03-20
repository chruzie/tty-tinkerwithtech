"""SSRF guard — blocks RFC1918, loopback, and link-local URLs."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse, urlunparse

import httpx

_BLOCKED_NETS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local
    ipaddress.ip_network("0.0.0.0/8"),  # this-host (RFC 1122)
    ipaddress.ip_network("100.64.0.0/10"),  # IANA Shared Address Space / CGNAT
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def check_url(url: str) -> None:
    """Validate a URL is safe to fetch (HTTPS, not RFC1918/loopback).

    Raises:
        ValueError: if the URL fails any safety check.
    """
    parsed = urlparse(url)

    if parsed.scheme != "https":
        raise ValueError(f"Only https:// URLs are allowed, got scheme {parsed.scheme!r}")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL has no hostname")

    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise ValueError(f"Cannot resolve hostname {hostname!r}: {exc}") from exc

    for info in infos:
        addr_str = info[4][0]
        try:
            addr = ipaddress.ip_address(addr_str)
        except ValueError:
            continue
        for net in _BLOCKED_NETS:
            if addr in net:
                raise ValueError(
                    f"URL resolves to blocked address {addr_str} (RFC1918/loopback/link-local)"
                )
        # Unwrap IPv4-mapped IPv6 addresses (e.g. ::ffff:127.0.0.1) and re-validate
        if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
            mapped = addr.ipv4_mapped
            for net in _BLOCKED_NETS:
                if mapped in net:
                    raise ValueError(
                        f"URL resolves to IPv4-mapped address {addr_str} "
                        f"embedding blocked IPv4 {mapped} (RFC1918/loopback/link-local)"
                    )


def safe_fetch(url: str, **kwargs) -> httpx.Response:
    """Fetch a URL with DNS rebinding protection.

    Resolves DNS once, validates the resolved IP against the blocklist,
    then connects directly to that IP (bypassing further DNS resolution)
    to eliminate the TOCTOU window between check_url and the HTTP request.

    Args:
        url: HTTPS URL to fetch.
        **kwargs: Additional keyword arguments forwarded to httpx.get().

    Raises:
        ValueError: if the URL fails any safety check.
    """
    # Step 1: initial validation (scheme, hostname format)
    check_url(url)

    parsed = urlparse(url)
    hostname = parsed.hostname
    assert hostname is not None  # already validated by check_url

    # Step 2: resolve DNS (same call as check_url, but we keep the result)
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise ValueError(f"Cannot resolve hostname {hostname!r}: {exc}") from exc

    # Step 3: re-validate each IP and pick the first safe one
    resolved_ip: str | None = None
    for info in infos:
        addr_str = info[4][0]
        try:
            addr = ipaddress.ip_address(addr_str)
        except ValueError:
            continue

        blocked = any(addr in net for net in _BLOCKED_NETS)
        if not blocked and isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
            blocked = any(addr.ipv4_mapped in net for net in _BLOCKED_NETS)
        if blocked:
            raise ValueError(
                f"URL resolves to blocked address {addr_str} (RFC1918/loopback/link-local)"
            )

        if resolved_ip is None:
            resolved_ip = addr_str

    if resolved_ip is None:
        raise ValueError(f"Could not resolve hostname {hostname!r} to any valid IP")

    # Step 4: build a URL with the resolved IP substituted for the hostname
    # so httpx does not perform its own DNS lookup (preventing DNS rebinding)
    addr_obj = ipaddress.ip_address(resolved_ip)
    ip_in_url = f"[{resolved_ip}]" if isinstance(addr_obj, ipaddress.IPv6Address) else resolved_ip
    port = parsed.port
    netloc = f"{ip_in_url}:{port}" if port else ip_in_url
    ip_url = urlunparse(
        (parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)
    )

    # Set Host header so the server receives the original hostname
    headers = dict(kwargs.pop("headers", {}))
    headers.setdefault("Host", hostname)

    return httpx.get(ip_url, headers=headers, **kwargs)
