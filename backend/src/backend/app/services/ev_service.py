"""Expected-value analysis for generated combinations (EV-15).

Lever A from the number-generation-remix design: surface the *payout-if-win*
expectation of a ticket so the UI can be honest about odds. The app models a
single jackpot tier (Draw.jackpot) with parimutuel split by winners, so the only
data-driven lever is the current jackpot magnitude relative to ticket cost and
historical mean winners. Without per-combination sales data (lever B is
out-of-scope), every combination has the same expected value; `combination_ev`
still accepts an `expected_winners` so popularity-differentiated ranking can be
added later without an API change.
"""

from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from backend.app.repositories.lottery_repository import LotteryRepository
from backend.app.repositories.stat_payload_repository import StatPayloadRepository
from backend.app.services.errors import NotFoundError


class EVService:
    """Compute expected value of a ticket / combination for a lottery."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._lotteries = LotteryRepository(session)
        self._payloads = StatPayloadRepository(session)

    def _resolve_lottery(self, *, lottery_code: str | None, lottery_id: int | None):
        """Resolve the lottery from ``code`` or ``id``; 404-style when absent."""
        lottery = None
        if lottery_code is not None:
            lottery = self._lotteries.get_by_code(lottery_code)
        elif lottery_id is not None:
            lottery = self._lotteries.get(lottery_id)
        if lottery is None:
            raise NotFoundError("lottery does not exist")
        return lottery

    def combinations_count(
        self, *, lottery_code: str | None = None, lottery_id: int | None = None
    ) -> int:
        """Number of possible combinations C(universe, numbers_to_select)."""
        lottery = self._resolve_lottery(lottery_code=lottery_code, lottery_id=lottery_id)
        universe = lottery.max_number - lottery.min_number + 1
        return math.comb(universe, lottery.numbers_to_select)

    def _latest_jackpot_and_avg_winners(self, lottery_id: int) -> tuple[Decimal, Decimal]:
        jackpots: list[Decimal] = []
        winners: list[Decimal] = []
        for _draw_number, _numbers, jackpot, winner in self._payloads.iter_draws(lottery_id):
            if jackpot is not None:
                jackpots.append(Decimal(str(jackpot)))
            if winner is not None:
                winners.append(Decimal(str(winner)))
        latest = jackpots[-1] if jackpots else Decimal(0)
        avg = (sum(winners) / Decimal(len(winners))) if winners else Decimal(1)
        return latest, avg

    @staticmethod
    def combination_ev(
        combo,
        jackpot: Decimal | float | str,
        ticket_cost: Decimal | float | str,
        combinations: int,
        expected_winners: Decimal | float | str = 1,
    ) -> Decimal:
        """Expected value of playing one combination.

        ``EV = (jackpot / expected_winners) / combinations - ticket_cost``.
        The ``combo`` argument is accepted for API symmetry (per-combination
        winner estimates can differentiate EV later) but is not yet used.
        """
        jackpot_d = Decimal(str(jackpot))
        cost = Decimal(str(ticket_cost))
        combos = Decimal(combinations)
        winners = Decimal(str(expected_winners)) if expected_winners else Decimal(1)
        expected_share = jackpot_d / winners
        ev = expected_share / combos - cost
        return ev.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    def estimate_ticket_ev(
        self,
        ticket_cost: Decimal | float | str,
        *,
        lottery_code: str | None = None,
        lottery_id: int | None = None,
    ) -> Decimal:
        """EV of a single ticket using the latest jackpot and historical mean winners."""
        lottery = self._resolve_lottery(lottery_code=lottery_code, lottery_id=lottery_id)
        jackpot, avg_winners = self._latest_jackpot_and_avg_winners(lottery.id)
        combos = self.combinations_count(lottery_id=lottery.id)
        return self.combination_ev(None, jackpot, ticket_cost, combos, avg_winners)

    def is_high_ev_window(
        self,
        ticket_cost: Decimal | float | str,
        *,
        lottery_code: str | None = None,
        lottery_id: int | None = None,
    ) -> bool:
        """True when a ticket's EV is positive (rare; only on large rollovers)."""
        ev = self.estimate_ticket_ev(ticket_cost, lottery_code=lottery_code, lottery_id=lottery_id)
        return ev > 0
