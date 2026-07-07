import asyncio

import pytest

from app.url_safety import (
    UrlValidationError,
    is_private_or_reserved_ip,
    validate_url_syntax,
)


def test_rejects_missing_scheme():
    with pytest.raises(UrlValidationError):
        validate_url_syntax("example.com")


def test_rejects_non_http_scheme():
    with pytest.raises(UrlValidationError):
        validate_url_syntax("file:///etc/passwd")


def test_rejects_embedded_credentials():
    with pytest.raises(UrlValidationError):
        validate_url_syntax("http://user:pass@example.com")


def test_rejects_localhost_literal():
    with pytest.raises(UrlValidationError):
        validate_url_syntax("http://localhost:8000/")


def test_rejects_dot_local_suffix():
    with pytest.raises(UrlValidationError):
        validate_url_syntax("http://printer.local/")


def test_rejects_loopback_ip_literal():
    with pytest.raises(UrlValidationError):
        validate_url_syntax("http://127.0.0.1/")


def test_rejects_metadata_ip_literal():
    with pytest.raises(UrlValidationError):
        validate_url_syntax("http://169.254.169.254/latest/meta-data/")


def test_accepts_well_formed_public_url():
    assert validate_url_syntax("https://example.com/page") == "https://example.com/page"


@pytest.mark.parametrize(
    "ip,expected",
    [
        ("127.0.0.1", True),
        ("10.0.0.1", True),
        ("172.16.0.1", True),
        ("192.168.1.1", True),
        ("169.254.169.254", True),
        ("100.64.0.1", True),  # CGNAT
        ("224.0.0.1", True),  # multicast
        ("0.0.0.0", True),
        ("::1", True),
        ("fe80::1", True),  # IPv6 link-local
        ("::ffff:127.0.0.1", True),  # IPv4-mapped IPv6 loopback
        ("8.8.8.8", False),
        ("93.184.216.34", False),
    ],
)
def test_is_private_or_reserved_ip(ip, expected):
    assert is_private_or_reserved_ip(ip) is expected


def test_resolve_and_validate_blocks_localhost_domain():
    from app.url_safety import resolve_and_validate

    async def run():
        with pytest.raises(UrlValidationError):
            await resolve_and_validate("localhost")

    asyncio.run(run())
