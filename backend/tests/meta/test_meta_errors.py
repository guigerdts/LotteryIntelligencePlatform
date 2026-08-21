"""Tests for meta error taxonomy (META-016).

Spec refs: META-016 (error taxonomy).
Design refs: Error System section.
"""

from __future__ import annotations

from backend.app.services.errors import MetaServiceError, ServiceError


class TestMetaServiceErrorHierarchy:
    """MetaServiceError must subclass ServiceError."""

    def test_base_class(self) -> None:
        assert issubclass(MetaServiceError, ServiceError)

    def test_mro_includes_service_error(self) -> None:
        assert ServiceError in MetaServiceError.__mro__


class TestMetaServiceErrorCodes:
    """Each error code must have the correct HTTP status mapping."""

    def test_ranking_not_found(self) -> None:
        assert MetaServiceError.META_RANKING_NOT_FOUND == "META_RANKING_NOT_FOUND"

    def test_selection_not_found(self) -> None:
        assert MetaServiceError.META_SELECTION_NOT_FOUND == "META_SELECTION_NOT_FOUND"

    def test_no_engine_data(self) -> None:
        assert MetaServiceError.META_NO_ENGINE_DATA == "META_NO_ENGINE_DATA"

    def test_weights_invalid(self) -> None:
        assert MetaServiceError.META_WEIGHTS_INVALID == "META_WEIGHTS_INVALID"

    def test_top_k_invalid(self) -> None:
        assert MetaServiceError.META_TOP_K_INVALID == "META_TOP_K_INVALID"

    def test_duplicate_ranking(self) -> None:
        assert MetaServiceError.META_DUPLICATE_RANKING == "META_DUPLICATE_RANKING"

    def test_instantiation(self) -> None:
        err = MetaServiceError(MetaServiceError.META_RANKING_NOT_FOUND, "not found")
        assert err.code == "META_RANKING_NOT_FOUND"
        assert str(err) == "not found"


class TestMetaServiceErrorHttpStatusMapping:
    """MetaServiceError codes must map to correct HTTP statuses in _CODE_TO_STATUS."""

    def test_ranking_not_found_404(self) -> None:
        from backend.app.api.errors import _CODE_TO_STATUS

        assert _CODE_TO_STATUS["META_RANKING_NOT_FOUND"] == 404

    def test_selection_not_found_404(self) -> None:
        from backend.app.api.errors import _CODE_TO_STATUS

        assert _CODE_TO_STATUS["META_SELECTION_NOT_FOUND"] == 404

    def test_no_engine_data_404(self) -> None:
        from backend.app.api.errors import _CODE_TO_STATUS

        assert _CODE_TO_STATUS["META_NO_ENGINE_DATA"] == 404

    def test_weights_invalid_422(self) -> None:
        from backend.app.api.errors import _CODE_TO_STATUS

        assert _CODE_TO_STATUS["META_WEIGHTS_INVALID"] == 422

    def test_top_k_invalid_422(self) -> None:
        from backend.app.api.errors import _CODE_TO_STATUS

        assert _CODE_TO_STATUS["META_TOP_K_INVALID"] == 422

    def test_duplicate_ranking_409(self) -> None:
        from backend.app.api.errors import _CODE_TO_STATUS

        assert _CODE_TO_STATUS["META_DUPLICATE_RANKING"] == 409
