"""Buyer matching: the purchase requirements a buyer posts.

A requirement is a signed demand. It turns the matching engine from a vague
"who might want this" into "these producers sell exactly what I need".
"""

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import TimestampMixin, sa_enum, utcnow
from .identity import BuyerProfile
from .reference import Commodity, CommodityGrade


class Requirement(Base, TimestampMixin):
    """A buyer's published demand for a crop.

    ``grade_id`` is optional: a buyer who only cares about the crop accepts any
    grade. ``quantity_desired`` is the total a buyer will take per day before
    the requirement lapses; a zero value means "sell whatever you have".
    """

    __tablename__ = "requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    buyer_id: Mapped[int] = mapped_column(
        ForeignKey("buyer_profiles.user_id", ondelete="CASCADE"), nullable=False
    )
    commodity_id: Mapped[int] = mapped_column(
        ForeignKey("commodities.id", ondelete="CASCADE"), nullable=False
    )
    grade_id: Mapped[int | None] = mapped_column(
        ForeignKey("commodity_grades.id", ondelete="SET NULL"), nullable=True
    )
    quantity_desired: Mapped[str] = mapped_column(String(60), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=utcnow(), nullable=False
    )

    buyer: Mapped[BuyerProfile] = relationship(back_populates="requirements", uselist=False)
    commodity: Mapped[Commodity] = relationship(
        back_populates="requirements", uselist=False
    )
    grade: Mapped[CommodityGrade | None] = relationship(
        back_populates="requirements", uselist=False
    )
