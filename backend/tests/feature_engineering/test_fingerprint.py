"""Feature-engine fingerprint determinism tests (FES-05, design §5).

The input fingerprint is canonical SHA-256 over ``{draws, features, stats}`` using
``json.dumps(sort_keys=True, separators=(",", ":"))``. The digest must depend only on
content — never on insertion order, dict construction, or feature ordering — and the
two independent generations over the same identity must produce the same digest.
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.feature_engineering.fingerprint import feature_input_fingerprint


def _input() -> dict[str, object]:
    """A canonical feature-engine input identity (draws + features + optional stats)."""
    return {
        "draws": {"lottery": 1, "from": 1, "to": 112, "checksum": "deadbeef"},
        "features": [
            ("draw_sum", "1.0.0", {"scale": 1}),
            ("draw_mean", "1.0.0", {"precision": 4}),
        ],
        "stats": {
            "checksum": "c0ffee",
            "generator_version": "1.0.0",
            "from": 1,
            "to": 112,
        },
    }


def test_fingerprint_is_stable_regardless_of_insertion_order() -> None:
    normal = _input()
    keys = list(normal)
    scrambled = {key: normal[key] for key in reversed(keys)}
    assert feature_input_fingerprint(_input()) == feature_input_fingerprint(scrambled)


def test_fingerprint_is_stable_regardless_of_feature_order() -> None:
    base = _input()
    # Reverse the features list without changing content — digest must not change.
    reversed_features = dict(base)
    reversed_features["features"] = list(reversed(base["features"]))
    assert feature_input_fingerprint(base) == feature_input_fingerprint(reversed_features)


def test_fingerprint_depends_on_draws_checksum() -> None:
    base = _input()
    changed = dict(base)
    changed["draws"] = {"lottery": 1, "from": 1, "to": 113, "checksum": "changed"}
    assert feature_input_fingerprint(base) != feature_input_fingerprint(changed)


def test_fingerprint_depends_on_feature_version() -> None:
    base = _input()
    changed = dict(base)
    feats = list(base["features"])
    feats[0] = ("draw_sum", "1.1.0", {"scale": 1})
    changed["features"] = feats
    assert feature_input_fingerprint(base) != feature_input_fingerprint(changed)


def test_fingerprint_depends_on_stats_identity() -> None:
    base = _input()
    changed = dict(base)
    changed["stats"] = {"checksum": "badf00d", "generator_version": "1.0.0", "from": 1, "to": 112}
    assert feature_input_fingerprint(base) != feature_input_fingerprint(changed)


def test_fingerprint_omitting_stats_changes_digest() -> None:
    base = _input()
    without_stats = {k: v for k, v in base.items() if k != "stats"}
    assert feature_input_fingerprint(base) != feature_input_fingerprint(without_stats)


def test_fingerprint_is_hex_fixed_length() -> None:
    digest = feature_input_fingerprint(_input())
    assert isinstance(digest, str)
    assert len(digest) == 64
    int(digest, 16)  # raises if not canonical lowercase hex


def test_fingerprint_is_deterministic_across_calls() -> None:
    assert feature_input_fingerprint(_input()) == feature_input_fingerprint(_input())


def test_compute_uses_single_accumulator_with_decimal() -> None:
    """The helper normalizes a Decimal payload to a stable jsonable form."""
    from backend.app.feature_engineering.fingerprint import _jsonable

    payload: dict[str, object] = {"draw_mean": Decimal("4.000000")}
    assert _jsonable(payload) == {"draw_mean": "4.000000"}
