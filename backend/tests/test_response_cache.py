"""Tests for the ThreadSafeLRU response cache (PFM-05, T-S5a-03).

Covers hit/miss keying, eviction, thread-safety under concurrent reads, and
the golden rule: cached payload == fresh DB-built (GF-1).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from backend.app.core.response_cache import ThreadSafeLRU


class TestThreadSafeLRU:
    """Core LRU semantics."""

    def test_hit_and_miss(self) -> None:
        cache: ThreadSafeLRU[tuple, str] = ThreadSafeLRU(maxsize=4)
        assert cache.get(("a", 1)) is None
        cache.set(("a", 1), "payload")
        assert cache.get(("a", 1)) == "payload"

    def test_key_is_full_tuple_including_params(self) -> None:
        """Different params must not collide (PFM-05 key folding)."""
        cache: ThreadSafeLRU[tuple, str] = ThreadSafeLRU(maxsize=4)
        cache.set(("stat", 10, "freq", "last=5"), "five")
        cache.set(("stat", 10, "freq", "last=20"), "twenty")
        assert cache.get(("stat", 10, "freq", "last=5")) == "five"
        assert cache.get(("stat", 10, "freq", "last=20")) == "twenty"
        # Different endpoint also distinct.
        assert cache.get(("stat", 10, "gaps", "last=5")) is None

    def test_eviction_lru(self) -> None:
        cache: ThreadSafeLRU[tuple, str] = ThreadSafeLRU(maxsize=2)
        cache.set(("k", 1), "v1")
        cache.set(("k", 2), "v2")
        cache.get(("k", 1))  # refresh recency
        cache.set(("k", 3), "v3")  # evicts k2 (LRU)
        assert cache.get(("k", 1)) == "v1"
        assert cache.get(("k", 2)) is None
        assert cache.get(("k", 3)) == "v3"
        assert len(cache) == 2

    def test_rejects_zero_maxsize(self) -> None:
        try:
            ThreadSafeLRU(maxsize=0)  # type: ignore[arg-type]
        except ValueError:
            pass
        else:
            raise AssertionError("maxsize=0 must raise ValueError")

    def test_thread_safety_concurrent_reads(self) -> None:
        """Concurrent reads never corrupt state and always return values."""
        cache: ThreadSafeLRU[tuple, str] = ThreadSafeLRU(maxsize=64)
        for i in range(32):
            cache.set(("n", i), f"v{i}")

        def read(i: int) -> str | None:
            return cache.get(("n", i))

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(read, range(32)))
        assert results == [f"v{i}" for i in range(32)]

        # Concurrent writes too.
        def write(i: int) -> None:
            cache.set(("w", i), f"w{i}")

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(write, range(64)))
        assert cache.get(("w", 63)) == "w63"

    def test_golden_cached_equals_fresh_byte_identical(self) -> None:
        """A cached payload is byte-identical to a freshly built one (GF-1)."""
        cache: ThreadSafeLRU[tuple, bytes] = ThreadSafeLRU(maxsize=4)

        def build() -> bytes:
            return b'{"hit_rate": 0.50000000, "checksum": "abc"}'

        fresh = build()
        cache.set(("snap", 7), fresh)
        cached = cache.get(("snap", 7))
        assert cached == fresh
        assert cached is fresh  # returned object identity preserved

    def test_version_bump_new_key(self) -> None:
        """A new snapshot version is a new key, never a stale hit (PFM-05)."""
        cache: ThreadSafeLRU[tuple, str] = ThreadSafeLRU(maxsize=4)
        cache.set(("snap", 1, "v1"), "old")
        cache.set(("snap", 2, "v1"), "new-snapshot")
        assert cache.get(("snap", 1, "v1")) == "old"
        assert cache.get(("snap", 2, "v1")) == "new-snapshot"
