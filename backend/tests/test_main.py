from starlette.requests import Request

from app.main import _client_ip


def _make_request(headers=None, client_host="203.0.113.7"):
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
    }
    if client_host is not None:
        scope["client"] = (client_host, 12345)
    return Request(scope)


def test_uses_x_forwarded_for_when_present():
    req = _make_request(headers={"X-Forwarded-For": "198.51.100.9"}, client_host="127.0.0.1")
    assert _client_ip(req) == "198.51.100.9"


def test_takes_rightmost_ip_from_forwarded_chain():
    """The rightmost entry is the one Caddy itself appended from the real
    TCP connection -- the trustworthy one when there's a single proxy hop."""
    req = _make_request(headers={"X-Forwarded-For": "10.0.0.1, 198.51.100.9"}, client_host="127.0.0.1")
    assert _client_ip(req) == "198.51.100.9"


def test_client_supplied_leading_ip_is_not_trusted():
    """Guards against the exact bypass a naive "take the first entry" fix
    would introduce: a client can send their own X-Forwarded-For directly.
    Caddy appends its own observed IP rather than replacing it, so the
    attacker-controlled entry must NOT be the one that wins -- otherwise
    rotating a fake leading value on every request gives an unlimited
    supply of fresh rate-limit buckets."""
    spoofed = _make_request(
        headers={"X-Forwarded-For": "1.2.3.4"},  # attacker-supplied, forwarded on by Caddy
        client_host="127.0.0.1",
    )
    # Simulate what Caddy actually does: append its own observed peer address
    # rather than trust the client's claim.
    real_caddy_view = _make_request(
        headers={"X-Forwarded-For": "1.2.3.4, 198.51.100.9"},
        client_host="127.0.0.1",
    )
    assert _client_ip(real_caddy_view) == "198.51.100.9"
    assert _client_ip(real_caddy_view) != "1.2.3.4"


def test_falls_back_to_direct_connection_without_proxy_header():
    req = _make_request(headers={}, client_host="203.0.113.7")
    assert _client_ip(req) == "203.0.113.7"


def test_falls_back_to_unknown_with_no_client_at_all():
    req = _make_request(headers={}, client_host=None)
    assert _client_ip(req) == "unknown"


def test_different_forwarded_ips_produce_different_keys():
    """The bug this guards against: without reading X-Forwarded-For, every
    request behind Caddy looks like it came from 127.0.0.1, so two different
    real visitors would collapse onto the same rate-limit bucket."""
    req_a = _make_request(headers={"X-Forwarded-For": "198.51.100.1"}, client_host="127.0.0.1")
    req_b = _make_request(headers={"X-Forwarded-For": "198.51.100.2"}, client_host="127.0.0.1")
    assert _client_ip(req_a) != _client_ip(req_b)
