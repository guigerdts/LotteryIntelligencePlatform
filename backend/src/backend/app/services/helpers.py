"""Shared validation / error-mapping helpers reused across domain services (V6).

Both the draw and dataset services must resolve a ``lottery`` row from its id
and raise ``NotFoundError`` (RESOURCE_NOT_FOUND) when it is absent (a draw and a
dataset both carry a required ``lottery_id`` FK). Extracting the lookup here
keeps the invariant in exactly one place so there is no copy-pasted business
logic between the two services (design, scope item: no duplicated logic between
services).
"""

from __future__ import annotations

from backend.app.models import Lottery
from backend.app.repositories.lottery_repository import LotteryRepository
from backend.app.services.errors import NotFoundError


def get_lottery_or_raise(lotteries: LotteryRepository, lottery_id: int) -> Lottery:
    """Return the lottery row for ``lottery_id`` or raise ``NotFoundError``.

    Used by both draw and dataset services before any insert so a missing or
    referentially-bound lottery surfaces a clear ``RESOURCE_NOT_FOUND`` instead
    of a DB FK failure.
    """
    lottery = lotteries.get(lottery_id)
    if lottery is None:
        raise NotFoundError(f"lottery {lottery_id} does not exist")
    return lottery
