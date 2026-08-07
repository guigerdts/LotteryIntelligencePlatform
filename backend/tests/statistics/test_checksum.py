"""Statistics checksum canonical/sort-stability tests (C2/STE-05, design §9).

The checksum must depend only on content, never on insertion order, key order,
or dict construction — ``sort_keys=True`` + compact separators guarantee it
(mirrors ``import_service._dataset_checksum``).
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.statistics.checksum import stat_checksum


def _payload() -> dict[str, object]:
    return {
        "lottery_id": 1,
        "metric_set": "core",
        "range": {"draws_from": 1, "draws_to": 112},
        "generator_version": "1.0.0",
        "engine_version": "0.1.0",
        "numbers": {1: 5, 2: 9, 3: 7},
        "positions": {"1:1": 4, "2:1": 7},
        "gaps": {1: {"count": 3, "min_gap": 1, "max_gap": 5, "avg_gap": "2.5"}},
        "averages": {"jackpot": {"mean": "1234.56", "non_null_count": 90}},
        "scalars": {"entropy": str(Decimal("2.000000"))},
    }


def test_checksum_is_stable_regardless_of_insertion_order() -> None:
    normal = _payload()
    # Same content, keys added in the opposite order — digest must not change.
    keys = list(normal)
    scrambled = {key: normal[key] for key in reversed(keys)}
    assert stat_checksum(normal) == stat_checksum(scrambled)


def test_checksum_depends_on_content() -> None:
    base = _payload()
    changed = dict(base)
    changed["range"] = {"draws_from": 2, "draws_to": 113}
    assert stat_checksum(base) != stat_checksum(changed)


def test_checksum_format_is_hex_fixed_length() -> None:
    digest = stat_checksum(_payload())
    assert len(digest) == 64
    int(digest, 16)  # raises if not canonical lowercase hex


def test_checksum_is_deterministic_across_calls() -> None:
    assert stat_checksum(_payload()) == stat_checksum(_payload())
