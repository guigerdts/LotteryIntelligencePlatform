"""Tests for the Generator Pydantic schemas (GEN-010).

Spec refs: GEN-002 (count default), GEN-003 (selection override), GEN-007
(lifecycle statuses).
Design refs: API Endpoints section.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.schemas.gen import (
    CombinationList,
    CombinationRow,
    GenerateRequest,
    GenerationResult,
    SnapshotList,
    SnapshotResult,
    SnapshotUpdateRequest,
)


class TestGenerateRequest:
    """GenerateRequest schema validation."""

    def test_minimal(self) -> None:
        req = GenerateRequest(lottery_id=1)
        assert req.lottery_id == 1
        assert req.count is None
        assert req.seed is None
        assert req.selection_id is None

    def test_with_optional_fields(self) -> None:
        req = GenerateRequest(lottery_id=1, count=20, seed=42, selection_id=7)
        assert req.count == 20
        assert req.seed == 42
        assert req.selection_id == 7

    def test_rejects_zero_lottery_id(self) -> None:
        with pytest.raises(ValidationError):
            GenerateRequest(lottery_id=0)

    def test_rejects_zero_selection_id(self) -> None:
        with pytest.raises(ValidationError):
            GenerateRequest(lottery_id=1, selection_id=0)

    def test_count_range_left_to_service(self) -> None:
        """count=0 parses at schema level; GenService raises GEN_COUNT_INVALID (GEN-002)."""
        req = GenerateRequest(lottery_id=1, count=0)
        assert req.count == 0

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            GenerateRequest(lottery_id=1, unknown_field="x")


class TestSnapshotUpdateRequest:
    """SnapshotUpdateRequest schema validation."""

    def test_valid_statuses(self) -> None:
        for status in ("active", "retired", "failed"):
            req = SnapshotUpdateRequest(lottery_id=1, snapshot_id=2, status=status)
            assert req.status == status

    def test_rejects_invalid_status(self) -> None:
        with pytest.raises(ValidationError):
            SnapshotUpdateRequest(lottery_id=1, snapshot_id=2, status="bogus")

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            SnapshotUpdateRequest(lottery_id=1, snapshot_id=2, status="retired", x=1)


class TestResponseSchemas:
    """Response schema construction."""

    def test_generation_result(self) -> None:
        result = GenerationResult(
            snapshot_id=1,
            lottery_id=1,
            selection_id=1,
            version="1",
            status="active",
            fingerprint="fp123",
            seed=42,
            count=10,
            combinations=[
                CombinationRow(
                    position=0, numbers=[1, 15, 22, 33, 41, 49], super_number=7, score=0.035
                )
            ],
        )
        assert result.count == 10
        assert result.combinations[0].super_number == 7
        assert result.combinations[0].score == 0.035

    def test_combination_row_with_score(self) -> None:
        row = CombinationRow(position=0, numbers=[1, 2, 3, 4, 5, 6], super_number=None, score=0.85)
        assert row.score == 0.85

    def test_combination_list(self) -> None:
        data = CombinationList(snapshot_id=1, lottery_id=1, combinations=[])
        assert data.snapshot_id == 1

    def test_combination_row_tolerates_null_for_legacy_reads(self) -> None:
        """Read-path row stays tolerant: legacy NULL-SB rows deserialize (D6/R2)."""
        row = CombinationRow(position=0, numbers=[1, 2, 3, 4, 5, 6], super_number=None)
        assert row.super_number is None


class TestGenerationResultStrictRows:
    """R3 — the generate response echoes NON-null super_number/score (D10/R3)."""

    @staticmethod
    def _result_kwargs() -> dict:
        return dict(
            snapshot_id=1,
            lottery_id=1,
            selection_id=1,
            version="1",
            status="active",
            fingerprint="fp123",
            seed=42,
            count=10,
        )

    def test_accepts_fully_scored_row(self) -> None:
        result = GenerationResult(
            combinations=[
                CombinationRow(
                    position=0, numbers=[1, 15, 22, 33, 41, 49], super_number=7, score=0.035
                )
            ],
            **self._result_kwargs(),
        )
        assert result.combinations[0].super_number == 7
        assert result.combinations[0].score == 0.035

    def test_rejects_null_score_in_generate_echo(self) -> None:
        with pytest.raises(ValidationError):
            GenerationResult(
                combinations=[
                    {"position": 0, "numbers": [1, 2, 3], "super_number": 7, "score": None}
                ],
                **self._result_kwargs(),
            )

    def test_rejects_null_super_number_in_generate_echo(self) -> None:
        with pytest.raises(ValidationError):
            GenerationResult(
                combinations=[
                    {"position": 0, "numbers": [1, 2, 3], "super_number": None, "score": 0.5}
                ],
                **self._result_kwargs(),
            )

    def test_rejects_missing_super_number_in_generate_echo(self) -> None:
        with pytest.raises(ValidationError):
            GenerationResult(
                combinations=[{"position": 0, "numbers": [1, 2, 3]}],
                **self._result_kwargs(),
            )

    def test_snapshot_result_created_at_optional(self) -> None:
        snap = SnapshotResult(
            snapshot_id=1,
            lottery_id=1,
            selection_id=1,
            version="1",
            status="active",
            fingerprint="fp",
        )
        assert snap.created_at is None

    def test_snapshot_list(self) -> None:
        data = SnapshotList(
            lottery_id=1,
            snapshots=[
                SnapshotResult(
                    snapshot_id=1,
                    lottery_id=1,
                    selection_id=1,
                    version="1",
                    status="active",
                    fingerprint="fp",
                )
            ],
        )
        assert len(data.snapshots) == 1
