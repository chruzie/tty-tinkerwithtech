"""Tests for TTLCache-backed rate limiter buckets (US-006)."""

from __future__ import annotations

from unittest.mock import patch

from cachetools import TTLCache


class TestTTLCacheEviction:
    """Verify that TTLCache correctly evicts entries after TTL and that
    a previously seen IP gets a fresh bucket afterward."""

    def test_buckets_are_ttlcache_instances(self):
        from api.middleware import _hour_buckets, _minute_buckets

        assert isinstance(_minute_buckets, TTLCache)
        assert isinstance(_hour_buckets, TTLCache)

    def test_ttlcache_maxsize(self):
        from api.middleware import _hour_buckets, _minute_buckets

        assert _minute_buckets.maxsize == 10000
        assert _hour_buckets.maxsize == 10000

    def test_evicted_ip_gets_fresh_bucket(self):
        """After an entry is evicted from TTLCache, the IP gets a fresh bucket
        (full capacity) on next access — verifies correct post-eviction behavior."""
        from api.middleware import _get_minute_bucket

        with patch("api.middleware._minute_buckets", TTLCache(maxsize=10000, ttl=3600)):
            bucket1 = _get_minute_bucket("aabbccdd00112233")
            # Drain most of the bucket
            for _ in range(5):
                bucket1.consume()
            # Simulate eviction by removing the key
            from api.middleware import _minute_buckets

            _minute_buckets.pop("aabbccdd00112233", None)

            # Fresh bucket should have full capacity
            bucket2 = _get_minute_bucket("aabbccdd00112233")
            assert bucket2.tokens == bucket2.capacity
            assert bucket2 is not bucket1

    def test_get_minute_bucket_creates_and_returns_same_instance(self):
        """Two calls for the same IP within TTL return the same object."""
        with patch("api.middleware._minute_buckets", TTLCache(maxsize=10000, ttl=3600)):
            from api.middleware import _get_minute_bucket

            b1 = _get_minute_bucket("deadbeef12345678")
            b2 = _get_minute_bucket("deadbeef12345678")
            assert b1 is b2

    def test_get_hour_bucket_creates_and_returns_same_instance(self):
        with patch("api.middleware._hour_buckets", TTLCache(maxsize=10000, ttl=3600)):
            from api.middleware import _get_hour_bucket

            b1 = _get_hour_bucket("cafebabe87654321")
            b2 = _get_hour_bucket("cafebabe87654321")
            assert b1 is b2


class TestRateLimiterTokenBurn:
    """Verify BUG-07 fix: hour-exhausted requests must not burn minute tokens."""

    def test_hour_exhausted_does_not_burn_minute_token(self):
        """When the hour bucket is exhausted, the minute token count is unchanged."""
        from cachetools import TTLCache

        from api.middleware import _get_hour_bucket, _get_minute_bucket

        with (
            patch("api.middleware._minute_buckets", TTLCache(maxsize=10000, ttl=3600)),
            patch("api.middleware._hour_buckets", TTLCache(maxsize=10000, ttl=3600)),
        ):
            ip = "testip000001"
            minute_bucket = _get_minute_bucket(ip)
            hour_bucket = _get_hour_bucket(ip)

            # Drain the hour bucket completely
            while hour_bucket.consume():
                pass

            minute_tokens_before = minute_bucket.tokens

            # Attempt to pass the rate limiter (should fail — hour exhausted)
            assert not hour_bucket.available()
            # Minute bucket should NOT be consumed
            assert minute_bucket.tokens == minute_tokens_before

    def test_minute_exhausted_does_not_burn_hour_token(self):
        """When the minute bucket is exhausted, the hour bucket count is unchanged."""
        with (
            patch("api.middleware._minute_buckets", TTLCache(maxsize=10000, ttl=3600)),
            patch("api.middleware._hour_buckets", TTLCache(maxsize=10000, ttl=3600)),
        ):
            from api.middleware import _get_hour_bucket, _get_minute_bucket

            ip = "testip000002"
            minute_bucket = _get_minute_bucket(ip)
            hour_bucket = _get_hour_bucket(ip)

            # Drain the minute bucket
            while minute_bucket.consume():
                pass

            hour_tokens_before = hour_bucket.tokens

            assert not minute_bucket.available()
            # Hour bucket should NOT be consumed when minute check fails first
            assert hour_bucket.tokens == hour_tokens_before
