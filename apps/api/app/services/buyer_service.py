"""Business rules for buyers, purchase requirements and lot matching.

Two things this module decides that the database cannot:

1. **Who counts as an active buyer.** A buyer must hold the ``buyer`` role, its
   profile must not be in draft/suspended state, and it must be accepting
   orders before it appears in a discover list.
2. **When a published lot matches a requirement.** Every field a farmer sold by
   a buyer had to agree on is drawn from the requirement. If even the crop and
   grade do not line up, the lot is a hard no; the response carries the exact
   criteria that passed and the criteria that did not, so a farmer can point at
   an explanation rather than see an opaque score.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.errors import NotFoundError
from ..models import (
    BuyerProfile,
    LotStatus,
    ProduceLot,
    UserRole,
)
from ..repositories import BuyerRepository, LotRepository

# A requirement that asks for a quantity the farmer cannot physically hold is a
# plan error, not a match. Hard cap the demand side so a single requester cannot
# anchor the entire discover feed with an absurd number.
MAX_REQUIRED_QTY = Decimal("100000000")
MIN_REQUIRED_QTY = Decimal("0.001")


class Requirement:
    """The thing a buyer asks a producer to match.

    Phase 7 pins the shape. A requirement is a signed demand the buyer has
    already posted, so it is created through the /requirements route rather
    than assembled ad hoc here.
    """

    def __init__(
        self,
        id: int,
        commodity_id: int,
        grade_id: int | None,
        min_required_value: Decimal,
    ) -> None:
        self.id = id
        self.commodity_id = commodity_id
        self.grade_id = grade_id
        self.min_required_value = min_required_value


class BuyerService:
    def __init__(self, session: AsyncSession, actor: User) -> None:
        self.session = session
        self.actor = actor
        self.repos = BuyerRepository(session)
        self.lots = LotRepository(session)

    # ------------------------------------------------------------------
    # Discovery reads
    # ------------------------------------------------------------------

    async def list_active_buyers(
        self,
        *,
        search: str | None = None,
        commodity_id: int | None = None,
        min_required_value: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> list[BuyerProfile]:
        profiles, _total = await self.repos.list_active(
            search=search,
            commodity_id=commodity_id,
            min_required_value=min_required_value,
            offset=offset,
            limit=limit,
        )
        return profiles

    async def get_owned_or_404(self, profile_id: int) -> BuyerProfile:
        profile = await self.repos.get_owned(profile_id, self.actor.id)
        if profile is None:
            raise NotFoundError(
                "That buyer profile does not exist or you do not own it."
            )
        return profile

    # ------------------------------------------------------------------
    # Matching (the Phase 7 payoff)
    # ------------------------------------------------------------------

    async def match_lots(self, requirement: Requirement) -> MatchedResult:
        """Return published producer lots that fit one of the buyer's
        requirements, with an explainable pass/fail per criterion.

        ``requirement`` is a signed requirement loaded by the route (it already
        belongs to the caller). The service is intentionally pure: it only
        iterates the lot table and marks each row.
        """
        rows = self.lots.list_for_farmer(
            farmer_id=self.actor.id,
            status=LotStatus.PUBLISHED,
            limit=200,
            offset=0,
        )
        lots, total = rows

        matches: list[MatchHit] = []
        for lot in lots:
            criteria = self._score_criteria(lot, requirement)
            if criteria.all_pass:
                matches.append(
                    MatchHit(
                        lot=lot,
                        criteria=criteria,
                        note="Every stated requirement matched.",
                    )
                )
            else:
                matches.append(
                    MatchHit(
                        lot=lot,
                        criteria=criteria,
                        note=(
                            "No match: "
                            + ", ".join(criteria.failed)
                            + ("." if criteria.failed else "The lot is hidden behind a privacy filter.")
                        ),
                    )
                )

        return MatchedResult(
            requirement_id=requirement.id,
            matched_count=len(matches),
            total_candidates=total,
            hits=matches,
        )

    def _score_criteria(self, lot: ProduceLot, requirement: Requirement) -> Score:
        failed: list[str] = []
        all_pass = True

        # Crop is the anchor: a lot must be the same commodity the buyer is
        # looking for. Grade falls back to "not graded" if either side is
        # ungraded - we never score ungraded against graded as a miss.
        if requirement.commodity_id is not None and lot.commodity_id not in _commodity_ids_of(requirement.commodity_id):
            all_pass = False
            failed.append("crop")

        if requirement.grade_id is not None and lot.grade_id != requirement.grade_id:
            all_pass = False
            failed.append("grade")

        if requirement.min_required_value is not None:
            qty = Decimal(lot.quantity) if lot.quantity else Decimal("0")
            if qty < requirement.min_required_value:
                all_pass = False
                failed.append("volume")

        return Score(
            all_pass=all_pass,
            failed=failed,
            matched={
                "crop": requirement.commodity_id == lot.commodity_id,
                "grade": requirement.grade_id is None or lot.grade_id == requirement.grade_id,
                "volume": requirement.min_required_value is None or (lot.quantity or Decimal("0")) >= requirement.min_required_value,
            },
        )

    # ------------------------------------------------------------------
    # Profile creation (the first thing a buyer does on the buyer screen)
    # ------------------------------------------------------------------

    async def create_profile(
        self,
        *,
        business_name: str,
        contact_person_name: str | None = None,
        business_type: str | None = None,
        gst_number: str | None = None,
        preferred_language: str = "en",
        state_id: int | None = None,
        district_id: int | None = None,
        address_line: str | None = None,
        contact_phone_visible: bool = False,
    ) -> BuyerProfile:
        profile = await self.repos.create(
            user_id=self.actor.id,
            business_name=business_name,
            contact_person_name=contact_person_name,
            business_type=business_type,
            gst_number=gst_number,
            preferred_language=preferred_language,
            state_id=state_id,
            district_id=district_id,
            address_line=address_line,
            contact_phone_visible=contact_phone_visible,
        )
        return profile


# ------------------------------------------------------------------ results
class MatchedResult:
    def __init__(
        self,
        requirement_id: int,
        matched_count: int,
        total_candidates: int,
        hits: list[MatchHit],
    ) -> None:
        self.requirement_id = requirement_id
        self.matched_count = matched_count
        self.total_candidates = total_candidates
        self.hits = hits


class MatchHit:
    def __init__(self, lot: ProduceLot, criteria: Score, note: str) -> None:
        self.lot = lot
        self.criteria = criteria
        self.note = note


class Score:
    def __init__(self, all_pass: bool, failed: list[str], matched: dict[str, bool]) -> None:
        self.all_pass = all_pass
        self.failed = failed
        self.matched = matched


def _commodity_ids_of(commodity_id: int) -> Iterable[int]:
    """A requirement may target one commodity or a small family of the same
    crop. This deliberately narrow helper keeps the matching rule readable
    instead of relegating it to a config enum."""
    return [commodity_id]
