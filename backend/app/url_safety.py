"""SSRF-safe URL validation for user-submitted scan targets.

The scanner fetches and renders arbitrary URLs supplied by the public, so this
module is the primary defense against the tool being used to probe internal
network addresses (localhost, cloud metadata endpoints, RFC1918 ranges, etc.).

Three layers:
  1. Cheap string/scheme/host checks before any network I/O (validate_url_syntax).
  2. DNS-resolution-time re-check (resolve_and_validate) -- a hostname that looks
     public in isolation can still resolve to a private IP.
  3. The caller (scanner.py) pins the resolved IP for the actual navigation via a
     Chromium --host-resolver-rules flag, so a second DNS lookup made by the
     browser itself (DNS rebinding) can't land somewhere different from what we
     validated here.
"""
from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

ALLOWED_SCHEMES = {"http", "https"}

# Hostname suffixes/literals that are always rejected regardless of what they
# resolve to (or even if they don't resolve at all, e.g. *.local via mDNS).
_BLOCKED_HOST_LITERALS = {"localhost", "metadata.google.internal"}
_BLOCKED_HOST_SUFFIXES = (".localhost", ".local", ".internal")

# 100.64.0.0/10 -- Carrier-Grade NAT (RFC 6598), not covered by ipaddress.is_private.
_CGNAT = ipaddress.ip_network("100.64.0.0/10")


class UrlValidationError(Exception):
    """Raised when a user-submitted URL is malformed or targets a disallowed host."""


def validate_url_syntax(raw: str) -> str:
    """Parse and normalize a user-submitted URL string.

    Rejects: missing/non-http(s) scheme, embedded credentials (user:pass@),
    missing host, obviously-blocked hostname literals/suffixes. Does not do any
    network I/O. Returns the normalized URL string.
    """
    raw = (raw or "").strip()
    if not raw:
        raise UrlValidationError("URL is required.")
    # urlparse is lenient about missing schemes -- require one explicitly so
    # "http://internal-host" isn't the only path in and "//internal-host" or a
    # bare "internal-host" can't sneak through with an implicit scheme.
    if "://" not in raw:
        raise UrlValidationError("URL must start with http:// or https://.")

    parsed = urlparse(raw)
    scheme = parsed.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise UrlValidationError(f"Unsupported scheme {scheme!r}. Use http or https.")
    if parsed.username or parsed.password:
        raise UrlValidationError("URLs with embedded credentials are not allowed.")
    hostname = parsed.hostname
    if not hostname:
        raise UrlValidationError("URL must include a host.")

    host_lower = hostname.lower()
    if host_lower in _BLOCKED_HOST_LITERALS:
        raise UrlValidationError(f"Host {hostname!r} is not allowed.")
    if host_lower.endswith(_BLOCKED_HOST_SUFFIXES):
        raise UrlValidationError(f"Host {hostname!r} is not allowed.")

    # If the host is itself a literal IP, validate it right away -- no DNS
    # lookup will happen for it later, so this is the only checkpoint.
    literal_ip = _parse_ip_literal(hostname)
    if literal_ip is not None and is_private_or_reserved_ip(str(literal_ip)):
        raise UrlValidationError(f"Host {hostname!r} resolves to a private or reserved address.")

    return parsed.geturl()


def _parse_ip_literal(hostname: str) -> ipaddress._BaseAddress | None:
    """Return an ip_address if hostname is a literal IPv4/IPv6, else None."""
    try:
        return ipaddress.ip_address(hostname)
    except ValueError:
        return None


def is_private_or_reserved_ip(ip: str) -> bool:
    """True if `ip` is a loopback/private/link-local/reserved/multicast address,
    including ranges the stdlib doesn't flag under is_private (CGNAT), and
    IPv4-mapped IPv6 addresses unwrapped to their embedded IPv4 form first.
    """
    addr = ipaddress.ip_address(ip)
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    if isinstance(addr, ipaddress.IPv4Address) and addr in _CGNAT:
        return True
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


async def resolve_and_validate(hostname: str) -> list[str]:
    """Resolve `hostname` (A + AAAA) and reject it outright if ANY resolved
    address is private/reserved -- blocking the whole hostname on a single bad
    record prevents a multi-A-record bypass where only some addresses are public.
    """
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UrlValidationError(f"Could not resolve host {hostname!r}: {exc}") from exc

    ips = sorted({info[4][0] for info in infos})
    if not ips:
        raise UrlValidationError(f"Host {hostname!r} did not resolve to any address.")
    for ip in ips:
        if is_private_or_reserved_ip(ip):
            raise UrlValidationError(
                f"Host {hostname!r} resolves to a private or reserved address ({ip})."
            )
    return ips


async def safe_resolve_target(raw_url: str) -> tuple[str, str]:
    """Top-level entry point. Validates syntax, resolves DNS, and rejects
    anything pointing at a private/reserved address. Returns (normalized_url,
    pinned_ip) -- the caller should pin navigation to pinned_ip to close the
    DNS-rebinding window between this check and the actual page load.
    """
    url = validate_url_syntax(raw_url)
    hostname = urlparse(url).hostname
    literal_ip = _parse_ip_literal(hostname)
    if literal_ip is not None:
        # Already validated in validate_url_syntax; no DNS lookup needed/possible.
        return url, str(literal_ip)
    ips = await resolve_and_validate(hostname)
    return url, ips[0]


async def revalidate_landed_host(landed_url: str) -> None:
    """Defense against redirects: re-run the full syntax + DNS validation
    against the URL the page actually landed on. A redirect to a *different*
    hostname than the one we pinned would cause Chromium to issue a fresh,
    unpinned DNS lookup for that new host -- our --host-resolver-rules mapping
    only covers the original hostname. This is post-hoc detection (the page
    has already loaded by the time we check), but it still lets us refuse to
    return results and flag the scan as unsafe rather than silently reporting
    on content fetched from an internal address.
    """
    await safe_resolve_target(landed_url)
