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


def test_takes_leftmost_ip_from_forwarded_chain():
    req = _make_request(headers={"X-Forwarded-For": "198.51.100.9, 10.0.0.1, 127.0.0.1"}, client_host="127.0.0.1")
    assert _client_ip(req) == "198.51.100.9"


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
