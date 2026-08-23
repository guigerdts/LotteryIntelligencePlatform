"""Tests for generator identity helpers — GEN-008/009 (T-GEN-018a, D6).

Covers the deterministic seed (GEN-009) and snapshot fingerprint (GEN-008)
used by the generator pipeline, extracted into ``generators/identity.py``
following the repo precedent of ``probability/determinism.py`` +
``probability/fingerprint.py`` (GEN-015 reuse surface).

D6: pre-change golden vectors are locked at the EXPLICIT ``1.0.0`` version so
the stream-consumption change cannot alias them; regenerated ``2.0.0`` goldens
lock the new identity, and an aliasing guard asserts the version bump actually
moved every derived value.

Design refs: Determinism Design, Pipeline steps 9-10, NFR-GEN-01.
"""

from __future__ import annotations

import hashlib

import pytest

from backend.app.generators.identity import generation_seed, snapshot_fingerprint
from backend.app.generators.version import GENERATOR_VERSION
from backend.app.probability.determinism import derive_seed
from backend.app.probability.fingerprint import _canonical_json

# Pre-change golden vectors computed with the F5 primitives for the canonical
# inputs (lottery_id=7, selection_id=3, count=10, selection_fingerprint="abc123",
# version="1.0.0"). Locked at the EXPLICIT pre-change version so the D6 bump
# cannot silently rewrite history: new fingerprints MUST NOT alias these.
PRE_CHANGE_VERSION = "1.0.0"
GOLDEN_SELECTION_FINGERPRINT = "abc123"
GOLDEN_LOTTERY_ID = 7
GOLDEN_SELECTION_ID = 3
GOLDEN_COUNT = 10
GOLDEN_INPUT_FINGERPRINT = "a7b7e0c02d515212ae9ac621887d46e1ce504ebb07786760b0f624c76682ff5a"
PRE_CHANGE_SEED = 297872213468358109463619875798332175481
PRE_CHANGE_SNAPSHOT_FINGERPRINT = "ddd2dbe5c6c8002067c2191e118caf1902c9c2e9b9ee2616136119bda3feb42c"

# Regenerated v2.0.0 golden vectors (D6) — locked atomically with the bump.
GOLDEN_SEED_V2 = 275000497823893291003335902595522194545
GOLDEN_SNAPSHOT_FINGERPRINT_V2 = "3a767d0a41419b566bc718e64821d59a698321355b4d0da533b0435b22b48373"


class TestGenerationSeed:
    """``generation_seed`` — deterministic run seed (GEN-009)."""

    def test_deterministic_same_inputs_same_seed(self) -> None:
        seed_a = generation_seed(
            GOLDEN_SELECTION_FINGERPRINT, GOLDEN_LOTTERY_ID, GOLDEN_COUNT, GENERATOR_VERSION
        )
        seed_b = generation_seed(
            GOLDEN_SELECTION_FINGERPRINT, GOLDEN_LOTTERY_ID, GOLDEN_COUNT, GENERATOR_VERSION
        )
        assert seed_a == seed_b

    def test_returns_positive_int(self) -> None:
        seed = generation_seed(
            GOLDEN_SELECTION_FINGERPRINT, GOLDEN_LOTTERY_ID, GOLDEN_COUNT, GENERATOR_VERSION
        )
        assert isinstance(seed, int)
        assert seed > 0

    def test_locked_pre_change_golden_vector(self) -> None:
        """Pre-change seed stays locked at its historical version (D6)."""
        seed = generation_seed(
            GOLDEN_SELECTION_FINGERPRINT, GOLDEN_LOTTERY_ID, GOLDEN_COUNT, PRE_CHANGE_VERSION
        )
        assert seed == PRE_CHANGE_SEED

    def test_locked_v2_golden_vector(self) -> None:
        """Regenerated golden under the bumped identity (D6)."""
        assert GENERATOR_VERSION == "2.0.0"
        seed = generation_seed(
            GOLDEN_SELECTION_FINGERPRINT, GOLDEN_LOTTERY_ID, GOLDEN_COUNT, GENERATOR_VERSION
        )
        assert seed == GOLDEN_SEED_V2

    @pytest.mark.parametrize(
        ("selection_fingerprint", "lottery_id", "count", "version"),
        [
            ("other-fp", GOLDEN_LOTTERY_ID, GOLDEN_COUNT, GENERATOR_VERSION),
            (GOLDEN_SELECTION_FINGERPRINT, 8, GOLDEN_COUNT, GENERATOR_VERSION),
            (GOLDEN_SELECTION_FINGERPRINT, GOLDEN_LOTTERY_ID, 20, GENERATOR_VERSION),
            (GOLDEN_SELECTION_FINGERPRINT, GOLDEN_LOTTERY_ID, GOLDEN_COUNT, "1.0.1"),
        ],
    )
    def test_any_input_change_changes_seed(
        self, selection_fingerprint: str, lottery_id: int, count: int, version: str
    ) -> None:
        seed = generation_seed(
            GOLDEN_SELECTION_FINGERPRINT, GOLDEN_LOTTERY_ID, GOLDEN_COUNT, GENERATOR_VERSION
        )
        changed = generation_seed(selection_fingerprint, lottery_id, count, version)
        assert changed != seed

    def test_cross_lottery_no_seed_collision(self) -> None:
        seeds = {
            generation_seed("fp", lottery_id, 10, GENERATOR_VERSION) for lottery_id in range(1, 21)
        }
        assert len(seeds) == 20

    def test_delegates_to_f5_derive_seed(self) -> None:
        # GEN-015: generators/ reuses F5 derive_seed — the seed MUST equal the
        # F5 primitive applied to the canonical input fingerprint.
        input_fp = hashlib.sha256(
            _canonical_json(
                {
                    "selection_fingerprint": GOLDEN_SELECTION_FINGERPRINT,
                    "lottery_id": GOLDEN_LOTTERY_ID,
                    "count": GOLDEN_COUNT,
                    "GENERATOR_VERSION": PRE_CHANGE_VERSION,
                }
            ).encode("utf-8")
        ).hexdigest()
        assert input_fp == GOLDEN_INPUT_FINGERPRINT
        expected = derive_seed(
            input_fp,
            model_params={"lottery_id": GOLDEN_LOTTERY_ID, "count": GOLDEN_COUNT},
            n_simulations=GOLDEN_COUNT,
        )
        assert (
            generation_seed(
                GOLDEN_SELECTION_FINGERPRINT, GOLDEN_LOTTERY_ID, GOLDEN_COUNT, PRE_CHANGE_VERSION
            )
            == expected
        )


class TestSnapshotFingerprint:
    """``snapshot_fingerprint`` — SHA-256 snapshot identity (GEN-008)."""

    def test_deterministic_same_inputs_same_fingerprint(self) -> None:
        fp_a = snapshot_fingerprint(
            GOLDEN_LOTTERY_ID, GOLDEN_SELECTION_ID, GOLDEN_COUNT, PRE_CHANGE_SEED, GENERATOR_VERSION
        )
        fp_b = snapshot_fingerprint(
            GOLDEN_LOTTERY_ID, GOLDEN_SELECTION_ID, GOLDEN_COUNT, PRE_CHANGE_SEED, GENERATOR_VERSION
        )
        assert fp_a == fp_b

    def test_is_sha256_hexdigest(self) -> None:
        fp = snapshot_fingerprint(
            GOLDEN_LOTTERY_ID, GOLDEN_SELECTION_ID, GOLDEN_COUNT, PRE_CHANGE_SEED, GENERATOR_VERSION
        )
        assert len(fp) == 64
        int(fp, 16)  # valid hex

    def test_locked_pre_change_golden_vector(self) -> None:
        """Pre-change fingerprint stays locked at its historical version (D6)."""
        fp = snapshot_fingerprint(
            GOLDEN_LOTTERY_ID,
            GOLDEN_SELECTION_ID,
            GOLDEN_COUNT,
            PRE_CHANGE_SEED,
            PRE_CHANGE_VERSION,
        )
        assert fp == PRE_CHANGE_SNAPSHOT_FINGERPRINT

    def test_locked_v2_golden_vector(self) -> None:
        """Regenerated fingerprint under the bumped identity (D6)."""
        assert GENERATOR_VERSION == "2.0.0"
        seed_v2 = generation_seed(
            GOLDEN_SELECTION_FINGERPRINT, GOLDEN_LOTTERY_ID, GOLDEN_COUNT, GENERATOR_VERSION
        )
        fp = snapshot_fingerprint(
            GOLDEN_LOTTERY_ID, GOLDEN_SELECTION_ID, GOLDEN_COUNT, seed_v2, GENERATOR_VERSION
        )
        assert fp == GOLDEN_SNAPSHOT_FINGERPRINT_V2

    @pytest.mark.parametrize(
        ("lottery_id", "selection_id", "count", "seed", "version"),
        [
            (8, GOLDEN_SELECTION_ID, GOLDEN_COUNT, PRE_CHANGE_SEED, GENERATOR_VERSION),
            (GOLDEN_LOTTERY_ID, 4, GOLDEN_COUNT, PRE_CHANGE_SEED, GENERATOR_VERSION),
            (GOLDEN_LOTTERY_ID, GOLDEN_SELECTION_ID, 20, PRE_CHANGE_SEED, GENERATOR_VERSION),
            (
                GOLDEN_LOTTERY_ID,
                GOLDEN_SELECTION_ID,
                GOLDEN_COUNT,
                PRE_CHANGE_SEED + 1,
                GENERATOR_VERSION,
            ),
            (GOLDEN_LOTTERY_ID, GOLDEN_SELECTION_ID, GOLDEN_COUNT, PRE_CHANGE_SEED, "1.0.1"),
        ],
    )
    def test_any_input_change_changes_fingerprint(
        self, lottery_id: int, selection_id: int, count: int, seed: int, version: str
    ) -> None:
        fp = snapshot_fingerprint(
            GOLDEN_LOTTERY_ID, GOLDEN_SELECTION_ID, GOLDEN_COUNT, PRE_CHANGE_SEED, GENERATOR_VERSION
        )
        changed = snapshot_fingerprint(lottery_id, selection_id, count, seed, version)
        assert changed != fp

    def test_cross_lottery_no_fingerprint_collision(self) -> None:
        fps = {
            snapshot_fingerprint(lottery_id, 3, 10, PRE_CHANGE_SEED, GENERATOR_VERSION)
            for lottery_id in range(1, 21)
        }
        assert len(fps) == 20

    def test_matches_canonical_sha256_formula(self) -> None:
        # GEN-008: SHA-256(_canonical_json({lottery_id, selection_id, count,
        # seed, VERSION})) — verify against the formula directly.
        payload = _canonical_json(
            {
                "lottery_id": GOLDEN_LOTTERY_ID,
                "selection_id": GOLDEN_SELECTION_ID,
                "count": GOLDEN_COUNT,
                "seed": PRE_CHANGE_SEED,
                "VERSION": PRE_CHANGE_VERSION,
            }
        )
        expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        assert (
            snapshot_fingerprint(
                GOLDEN_LOTTERY_ID,
                GOLDEN_SELECTION_ID,
                GOLDEN_COUNT,
                PRE_CHANGE_SEED,
                PRE_CHANGE_VERSION,
            )
            == expected
        )


class TestVersionBumpAliasingGuard:
    """D6/R2 — v2 outputs MUST NOT alias any pre-change fixture fingerprint."""

    def test_v2_fingerprint_differs_from_pre_change(self) -> None:
        """Same canonical inputs → bump moves the fingerprint away from legacy."""
        assert GENERATOR_VERSION == "2.0.0"
        seed_v2 = generation_seed(
            GOLDEN_SELECTION_FINGERPRINT, GOLDEN_LOTTERY_ID, GOLDEN_COUNT, GENERATOR_VERSION
        )
        fp_v2 = snapshot_fingerprint(
            GOLDEN_LOTTERY_ID, GOLDEN_SELECTION_ID, GOLDEN_COUNT, seed_v2, GENERATOR_VERSION
        )
        assert fp_v2 != PRE_CHANGE_SNAPSHOT_FINGERPRINT

    def test_v2_seed_differs_from_pre_change(self) -> None:
        seed_v2 = generation_seed(
            GOLDEN_SELECTION_FINGERPRINT, GOLDEN_LOTTERY_ID, GOLDEN_COUNT, GENERATOR_VERSION
        )
        assert seed_v2 != PRE_CHANGE_SEED

    def test_new_generation_fingerprints_avoid_legacy_fixture_set(self) -> None:
        """No fresh fingerprint equals any preserved pre-change fixture vector."""
        pre_change_fixtures = {PRE_CHANGE_SNAPSHOT_FINGERPRINT}
        for lottery_id in range(1, 11):
            seed = generation_seed("fp", lottery_id, 10, GENERATOR_VERSION)
            fp = snapshot_fingerprint(lottery_id, 3, 10, seed, GENERATOR_VERSION)
            assert fp not in pre_change_fixtures
