"""Tests for experiment error classes (EXP-008)."""

from backend.app.services.errors import (
    ComparisonError,
    ComparisonInsufficientRunsError,
    DuplicateExperimentError,
    ExperimentError,
    ExperimentNotFoundError,
    ExperimentRetiredError,
    ExportFormatInvalidError,
    ServiceError,
    SnapshotNotFoundError,
    SnapshotTypeMismatchError,
)


class TestExperimentError:
    """Test ExperimentError class."""

    def test_experiment_error_is_service_error(self):
        """ExperimentError must be a subclass of ServiceError."""
        assert issubclass(ExperimentError, ServiceError)

    def test_experiment_error_has_error_code(self):
        """ExperimentError has a default code attribute."""
        error = ExperimentError("test error")
        assert error.code == "EXPERIMENT_ERROR"

    def test_experiment_subclasses_have_correct_codes(self):
        """All experiment error subclasses have correct codes."""
        assert ExperimentNotFoundError.code == "EXPERIMENT_NOT_FOUND"
        assert ExperimentRetiredError.code == "EXPERIMENT_RETIRED"
        assert DuplicateExperimentError.code == "DUPLICATE_EXPERIMENT"
        assert SnapshotNotFoundError.code == "SNAPSHOT_NOT_FOUND"
        assert SnapshotTypeMismatchError.code == "SNAPSHOT_TYPE_MISMATCH"
        assert ExportFormatInvalidError.code == "EXPORT_FORMAT_INVALID"


class TestComparisonError:
    """Test ComparisonError class."""

    def test_comparison_error_is_service_error(self):
        """ComparisonError must be a subclass of ServiceError."""
        assert issubclass(ComparisonError, ServiceError)

    def test_comparison_error_has_error_code(self):
        """ComparisonError has a default code attribute."""
        error = ComparisonError("test error")
        assert error.code == "COMPARISON_ERROR"

    def test_comparison_insufficient_runs_has_correct_code(self):
        """ComparisonInsufficientRunsError has correct code."""
        assert ComparisonInsufficientRunsError.code == "COMPARISON_INSUFFICIENT_RUNS"
