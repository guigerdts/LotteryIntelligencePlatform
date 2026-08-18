"""In-process thread-safe LRU response cache (PFM-05, T-S5a-01).

Bounds the 2.4 GB box by caching read-only snapshot responses in-process
(D3): no Redis, no external store.  Keys are plain tuples; payloads are
read-only after ``set``; eviction happens on insert past ``maxsize``.
"""

from __future__ import annotations

from collections import OrderedDict
from threading import RLock
from typing import TypeVar

K = TypeVar("K")
V = TypeVar("V")


class ThreadSafeLRU[K, V]:
    """Bounded LRU cache safe for concurrent reads (PFM-05).

    ``get``/``set`` are atomic under one ``RLock``; a ``get`` hit refreshes
    recency; ``set`` evicts the least-recently-used entry when full.
    """

    def __init__(self, maxsize: int = 256) -> None:
        if maxsize < 1:
            raise ValueError("maxsize must be >= 1")
        self._maxsize = maxsize
        self._data: OrderedDict[K, V] = OrderedDict()
        self._lock = RLock()

    def get(self, key: K) -> V | None:
        """Return the cached value or None; a hit refreshes recency."""
        with self._lock:
            if key not in self._data:
                return None
            self._data.move_to_end(key)
            return self._data[key]

    def set(self, key: K, value: V) -> None:
        """Insert ``key -> value``; evict the LRU entry past maxsize."""
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = value
            while len(self._data) > self._maxsize:
                self._data.popitem(last=False)

    def clear(self) -> None:
        """Drop every cached entry (test isolation / cache reset)."""
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)


_REGISTRY: list[ThreadSafeLRU] = []


def register_cache(cache: ThreadSafeLRU) -> None:
    """Track a service-level cache so ``clear_all_caches`` can reset it."""
    _REGISTRY.append(cache)


def clear_all_caches() -> None:
    """Clear every registered response cache (test isolation)."""
    for cache in _REGISTRY:
        cache.clear()


__all__ = ["ThreadSafeLRU", "clear_all_caches", "register_cache"]
