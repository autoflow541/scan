import time

from app.rate_limit import RateLimiter, TokenBucket


def test_token_bucket_allows_up_to_capacity():
    bucket = TokenBucket(capacity=3, refill_per_sec=0)  # no refill -- isolate burst behavior
    assert bucket.allow() is True
    assert bucket.allow() is True
    assert bucket.allow() is True
    assert bucket.allow() is False


def test_token_bucket_refills_over_time():
    bucket = TokenBucket(capacity=1, refill_per_sec=1.0)  # 1 token/sec
    assert bucket.allow() is True
    assert bucket.allow() is False  # exhausted, no time has passed
    bucket.last_check -= 1.0  # simulate 1 second elapsed without a real sleep
    assert bucket.allow() is True


def test_token_bucket_refill_caps_at_capacity():
    bucket = TokenBucket(capacity=2, refill_per_sec=1.0)
    bucket.tokens = 0
    bucket.last_check -= 1000  # a huge elapsed gap shouldn't overflow past capacity
    assert bucket.allow() is True
    assert bucket.allow() is True
    assert bucket.allow() is False  # capped at 2, not unbounded


def test_rate_limiter_gives_each_ip_its_own_bucket():
    limiter = RateLimiter(capacity=1, refill_per_sec=0)
    assert limiter.check("1.1.1.1") is True
    assert limiter.check("1.1.1.1") is False  # this IP is now exhausted
    assert limiter.check("2.2.2.2") is True  # a different IP is unaffected


def test_rate_limiter_burst_then_blocks():
    limiter = RateLimiter(capacity=5, refill_per_sec=0)
    results = [limiter.check("9.9.9.9") for _ in range(6)]
    assert results == [True, True, True, True, True, False]


def test_sweep_drops_stale_buckets_but_keeps_recent_ones():
    limiter = RateLimiter(capacity=1, refill_per_sec=0)
    limiter.check("stale-ip")
    # Backdate this IP's last-touched time past the sweep threshold, and force
    # the tracked-IP count over the sweep trigger without creating 5000 real
    # entries.
    from app import rate_limit as rl_module

    limiter._touched["stale-ip"] = time.monotonic() - rl_module._STALE_AFTER_SECONDS - 1
    original_max = rl_module._MAX_TRACKED_IPS
    rl_module._MAX_TRACKED_IPS = 0  # force _maybe_sweep to always run its check
    try:
        limiter.check("fresh-ip")
    finally:
        rl_module._MAX_TRACKED_IPS = original_max

    assert "stale-ip" not in limiter._buckets
    assert "fresh-ip" in limiter._buckets
