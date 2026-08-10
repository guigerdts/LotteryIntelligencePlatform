"""Tests for OE-08: Data Floor (<100 draws → INSUFFICIENT_DATA)."""

from __future__ import annotations

import pytest

from backend.app.opt.search_space import SearchParam, SearchSpace
from backend.app.services.errors import InsufficientDataError
from backend.app.services.opt_service import MIN_DRAWS, OptService


class TestOE08DataFloor:
    """OE-08: Data floor check tests."""

    def test_min_draws_constant(self) -> None:
        """MIN_DRAWS is 100."""
        assert MIN_DRAWS == 100

    def test_below_floor_raises(self) -> None:
        """<100 draws raises InsufficientDataError."""
        search_space = SearchSpace(
            params=(SearchParam(name="lr", param_type="continuous", low=1e-5, high=1e-1),)
        )
        service = OptService(
            session=None,
            objective_fn=lambda p: 0.5,
            search_space=search_space,
            lottery_id=1,
            optimizer="ga",
            draw_count=99,
        )
        with pytest.raises(InsufficientDataError, match="≥100 real draws"):
            service.train()

    def test_exactly_floor_allowed(self) -> None:
        """Exactly 100 draws is allowed (no InsufficientDataError)."""
        search_space = SearchSpace(
            params=(SearchParam(name="lr", param_type="continuous", low=1e-5, high=1e-1),)
        )
        service = OptService(
            session=None,
            objective_fn=lambda p: 0.5,
            search_space=search_space,
            lottery_id=1,
            optimizer="ga",
            draw_count=100,
        )
        # Should not raise InsufficientDataError (will fail for other reasons like no session)
        with pytest.raises(Exception) as exc_info:
            service.train()
        # The error should NOT be InsufficientDataError
        assert not isinstance(exc_info.value, InsufficientDataError)

    def test_above_floor_allowed(self) -> None:
        """150 draws is allowed (no InsufficientDataError)."""
        search_space = SearchSpace(
            params=(SearchParam(name="lr", param_type="continuous", low=1e-5, high=1e-1),)
        )
        service = OptService(
            session=None,
            objective_fn=lambda p: 0.5,
            search_space=search_space,
            lottery_id=1,
            optimizer="ga",
            draw_count=150,
        )
        # Should not raise InsufficientDataError
        with pytest.raises(Exception) as exc_info:
            service.train()
        assert not isinstance(exc_info.value, InsufficientDataError)

    def test_zero_draws_raises(self) -> None:
        """0 draws raises InsufficientDataError."""
        search_space = SearchSpace(
            params=(SearchParam(name="lr", param_type="continuous", low=1e-5, high=1e-1),)
        )
        service = OptService(
            session=None,
            objective_fn=lambda p: 0.5,
            search_space=search_space,
            lottery_id=1,
            optimizer="ga",
            draw_count=0,
        )
        with pytest.raises(InsufficientDataError):
            service.train()

    def test_error_message_includes_count(self) -> None:
        """Error message includes the actual draw count."""
        search_space = SearchSpace(
            params=(SearchParam(name="lr", param_type="continuous", low=1e-5, high=1e-1),)
        )
        service = OptService(
            session=None,
            objective_fn=lambda p: 0.5,
            search_space=search_space,
            lottery_id=1,
            optimizer="ga",
            draw_count=50,
        )
        with pytest.raises(InsufficientDataError, match="has 50"):
            service.train()

    def test_error_code_is_insufficient_data(self) -> None:
        """Error code is INSUFFICIENT_DATA."""
        err = InsufficientDataError("test")
        assert err.code == "INSUFFICIENT_DATA"


class TestInsufficientDataError:
    """InsufficientDataError class tests."""

    def test_inheritance(self) -> None:
        """InsufficientDataError inherits from ServiceError."""
        from backend.app.services.errors import ServiceError

        err = InsufficientDataError("test")
        assert isinstance(err, ServiceError)

    def test_code(self) -> None:
        """Error code is INSUFFICIENT_DATA."""
        err = InsufficientDataError("test")
        assert err.code == "INSUFFICIENT_DATA"

    def test_message(self) -> None:
        """Error message is preserved."""
        err = InsufficientDataError("not enough data")
        assert str(err) == "not enough data"
