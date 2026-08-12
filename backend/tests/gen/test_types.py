"""Tests for generator types, version, and error taxonomy.

Spec refs: GEN-001 (pipeline types), GEN-009 (seed/version), GEN-013 (errors).
Design refs: Module Structure, Error Taxonomy, Determinism Design.
"""

from __future__ import annotations

import pytest

from backend.app.generators.types import Allocation, Combination, GenerationConfig
from backend.app.generators.version import GENERATOR_VERSION
from backend.app.services.errors import GenServiceError, ServiceError


class TestGenerationConfig:
    """GenerationConfig frozen dataclass — pipeline input parameters."""

    def test_creation_with_all_fields(self) -> None:
        cfg = GenerationConfig(lottery_id=1, count=10, seed=42, selection_id=5)
        assert cfg.lottery_id == 1
        assert cfg.count == 10
        assert cfg.seed == 42
        assert cfg.selection_id == 5

    def test_creation_without_optional_seed(self) -> None:
        cfg = GenerationConfig(lottery_id=1, count=10, seed=None, selection_id=5)
        assert cfg.seed is None

    def test_immutability(self) -> None:
        cfg = GenerationConfig(lottery_id=1, count=10, seed=42, selection_id=5)
        with pytest.raises(AttributeError):
            cfg.count = 20  # type: ignore[misc]

    def test_equality(self) -> None:
        a = GenerationConfig(1, 10, 42, 5)
        b = GenerationConfig(1, 10, 42, 5)
        assert a == b

    def test_inequality_different_count(self) -> None:
        a = GenerationConfig(1, 10, 42, 5)
        b = GenerationConfig(1, 20, 42, 5)
        assert a != b


class TestCombination:
    """Combination frozen dataclass — one generated lottery combination."""

    def test_creation_with_all_fields(self) -> None:
        combo = Combination(position=0, numbers=[1, 15, 22, 33, 41, 49], super_number=7)
        assert combo.position == 0
        assert combo.numbers == [1, 15, 22, 33, 41, 49]
        assert combo.super_number == 7

    def test_creation_without_super_number(self) -> None:
        combo = Combination(position=1, numbers=[3, 8, 17, 25, 30, 44], super_number=None)
        assert combo.super_number is None

    def test_immutability(self) -> None:
        combo = Combination(position=0, numbers=[1, 15, 22, 33, 41, 49], super_number=7)
        with pytest.raises(AttributeError):
            combo.position = 1  # type: ignore[misc]

    def test_inequality_different_position(self) -> None:
        a = Combination(0, [1, 2, 3, 4, 5, 6], None)
        b = Combination(1, [1, 2, 3, 4, 5, 6], None)
        assert a != b


class TestAllocation:
    """Allocation frozen dataclass — per-entry count allocation."""

    def test_creation(self) -> None:
        alloc = Allocation(entry_index=0, count=63)
        assert alloc.entry_index == 0
        assert alloc.count == 63

    def test_immutability(self) -> None:
        alloc = Allocation(entry_index=0, count=63)
        with pytest.raises(AttributeError):
            alloc.count = 70  # type: ignore[misc]

    def test_equality(self) -> None:
        a = Allocation(0, 63)
        b = Allocation(0, 63)
        assert a == b

    def test_inequality_different_count(self) -> None:
        a = Allocation(0, 63)
        b = Allocation(0, 27)
        assert a != b


class TestGeneratorVersion:
    """GENERATOR_VERSION constant — GEN-009 determinism."""

    def test_version_is_1_0_0(self) -> None:
        assert GENERATOR_VERSION == "1.0.0"

    def test_version_is_string(self) -> None:
        assert isinstance(GENERATOR_VERSION, str)


class TestGenServiceError:
    """GenServiceError taxonomy — GEN-013, error codes and HTTP mapping."""

    def test_mro_includes_service_error(self) -> None:
        assert issubclass(GenServiceError, ServiceError)

    def test_instantiation(self) -> None:
        err = GenServiceError(GenServiceError.GEN_NO_SELECTION, "no active selection")
        assert err.code == "GEN_NO_SELECTION"
        assert str(err) == "no active selection"

    def test_gen_no_selection_is_404(self) -> None:
        from backend.app.api.errors import status_for_code

        assert status_for_code(GenServiceError.GEN_NO_SELECTION) == 404

    def test_gen_no_distribution_is_404(self) -> None:
        from backend.app.api.errors import status_for_code

        assert status_for_code(GenServiceError.GEN_NO_DISTRIBUTION) == 404

    def test_gen_lottery_not_found_is_404(self) -> None:
        from backend.app.api.errors import status_for_code

        assert status_for_code(GenServiceError.GEN_LOTTERY_NOT_FOUND) == 404

    def test_gen_count_invalid_is_422(self) -> None:
        from backend.app.api.errors import status_for_code

        assert status_for_code(GenServiceError.GEN_COUNT_INVALID) == 422

    def test_gen_snapshot_not_found_is_404(self) -> None:
        from backend.app.api.errors import status_for_code

        assert status_for_code(GenServiceError.GEN_SNAPSHOT_NOT_FOUND) == 404

    def test_gen_duplicate_snapshot_is_409(self) -> None:
        from backend.app.api.errors import status_for_code

        assert status_for_code(GenServiceError.GEN_DUPLICATE_SNAPSHOT) == 409

    def test_gen_space_exhausted_is_422(self) -> None:
        from backend.app.api.errors import status_for_code

        assert status_for_code(GenServiceError.GEN_SPACE_EXHAUSTED) == 422
