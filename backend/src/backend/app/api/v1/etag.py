"""Strong/weak ETag derivation and If-None-Match handling (REQ-13, T-S5b-01).

Snapshots are immutable once persisted, so a content-derived checksum is a
strong ETag; snapshots without a checksum fall back to a weak
``W/"<snapshot_id>:<version>"`` tag.  ``should_not_modify`` answers whether a
request's ``If-None-Match`` header matches the candidate ETag.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def etag_for(snapshot: Mapping[str, Any] | Any) -> str:
    """Derive a strong or weak ETag from a snapshot-like object.

    Strong: ``"<checksum>"`` from statistics ``checksum``, ml
    ``checksum``/``input_fingerprint``, or bt ``fingerprint`` (content-derived,
    correct under immutability).  Weak: ``W/"<snapshot_id>:<version>"`` when no
    checksum-like field exists.
    """
    checksum = getattr(snapshot, "checksum", None) or (
        snapshot.get("checksum") if isinstance(snapshot, Mapping) else None
    )
    if checksum:
        return f'"{checksum}"'

    fingerprint = getattr(snapshot, "fingerprint", None) or (
        snapshot.get("fingerprint") if isinstance(snapshot, Mapping) else None
    )
    if fingerprint:
        return f'"{fingerprint}"'

    input_fingerprint = getattr(snapshot, "input_fingerprint", None) or (
        snapshot.get("input_fingerprint") if isinstance(snapshot, Mapping) else None
    )
    if input_fingerprint:
        return f'"{input_fingerprint}"'

    snapshot_id = getattr(snapshot, "id", None) or (
        snapshot.get("id") if isinstance(snapshot, Mapping) else None
    )
    version = getattr(snapshot, "version", None) or (
        snapshot.get("version") if isinstance(snapshot, Mapping) else None
    )
    return f'W/"{snapshot_id}:{version}"'


def should_not_modify(request_headers: Mapping[str, str], etag: str) -> bool:
    """Return True when ``If-None-Match`` matches *etag* (304 condition).

    Supports exact matches and the ``*`` wildcard; ignores weak-strong
    distinction for comparison purposes per RFC 7232.
    """
    header = request_headers.get("if-none-match")
    if not header:
        return False
    candidates = [part.strip() for part in header.split(",")]
    if "*" in candidates:
        return True
    normalized = etag.removeprefix("W/")
    return any(c.removeprefix("W/") == normalized for c in candidates)


__all__ = ["etag_for", "should_not_modify"]
