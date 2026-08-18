"""ETag / 304 integration tests (REQ-13, PFM-05, T-S5b-03).

Covers ETag derivation, ``If-None-Match`` → 304 empty body, version bump →
fresh ETag (never stale 304), and the golden rule: a 200 envelope with the
ETag header is byte-identical to the unconditional 200 (GF-1).
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from backend.app.api.v1.etag import etag_for, should_not_modify
from backend.app.models import StatSnapshot
from backend.app.services.draw_service import DrawService


class _Snap:
    """Snapshot-like object used by the derivation unit tests."""

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


# --- derivation (unit) -------------------------------------------------------


def test_etag_strong_from_checksum() -> None:
    snap = _Snap(id=7, version="3", checksum="abc123")
    assert etag_for(snap) == '"abc123"'


def test_etag_strong_from_fingerprint() -> None:
    snap = _Snap(id=7, version="3", fingerprint="xyz789")
    assert etag_for(snap) == '"xyz789"'


def test_etag_strong_from_input_fingerprint_mapping() -> None:
    snap = {"id": 7, "version": "3", "input_fingerprint": "inp42"}
    assert etag_for(snap) == '"inp42"'


def test_etag_weak_fallback() -> None:
    snap = _Snap(id=7, version="3")
    assert etag_for(snap) == 'W/"7:3"'


def test_should_not_modify_matching() -> None:
    assert should_not_modify({"if-none-match": '"abc123"'}, '"abc123"') is True
    assert should_not_modify({"if-none-match": 'W/"abc123"'}, '"abc123"') is True
    assert should_not_modify({"if-none-match": "*"}, '"abc123"') is True


def test_should_not_modify_non_matching() -> None:
    assert should_not_modify({}, '"abc123"') is False
    assert should_not_modify({"if-none-match": '"other"'}, '"abc123"') is False


# --- integration -------------------------------------------------------------

_STAT_READS = [
    "/api/v1/statistics/PBA/frequencies",
    "/api/v1/statistics/PBA/gaps",
    "/api/v1/statistics/PBA/averages",
    "/api/v1/statistics/PBA/scalars",
]


@pytest.mark.parametrize("path", _STAT_READS)
def test_read_returns_etag_and_304_on_match(client, generated, path) -> None:
    first = client.get(path)
    assert first.status_code == 200
    etag = first.headers["etag"]
    assert etag.startswith('"')

    cached = client.get(path, headers={"If-None-Match": etag})
    assert cached.status_code == 304
    assert cached.content == b""


def test_200_envelope_byte_identical_with_etag_header(client, generated) -> None:
    """Non-matching conditional 200 is byte-identical to the unconditional 200 (GF-1)."""
    path = "/api/v1/statistics/PBA/frequencies"
    plain = client.get(path)
    assert plain.status_code == 200
    conditional = client.get(path, headers={"If-None-Match": '"not-the-current"'})
    assert conditional.status_code == 200
    assert conditional.content == plain.content
    assert conditional.headers["etag"] == plain.headers["etag"]


def test_version_bump_yields_new_etag_no_stale_304(client, db, seeded_lottery, generated) -> None:
    path = "/api/v1/statistics/PBA/frequencies"
    old_etag = client.get(path).headers["etag"]

    DrawService(db).create_draw_bundle(
        lottery_id=seeded_lottery.id,
        draw_number=4,
        draw_date=date(2024, 1, 4),
        numbers=[5, 6, 7, 8],
        super_number=2,
        jackpot=2000,
        winners=4,
    )
    db.commit()
    resp = client.post("/api/v1/statistics/generate", json={"lottery_code": "PBA"})
    assert resp.status_code == 201

    new_etag = client.get(path).headers["etag"]
    assert new_etag != old_etag
    stale = client.get(path, headers={"If-None-Match": old_etag})
    assert stale.status_code == 200


def test_304_never_recomputes(client, db, generated) -> None:
    path = "/api/v1/statistics/PBA/frequencies"
    etag = client.get(path).headers["etag"]
    assert client.get(path, headers={"If-None-Match": etag}).status_code == 304
    active = (
        db.execute(
            select(StatSnapshot).where(StatSnapshot.status == "active", StatSnapshot.checksum != "")
        )
        .scalars()
        .all()
    )
    assert [s.version for s in active] == [generated["version"]]
