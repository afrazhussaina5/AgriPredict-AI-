# AgriPredict AI - Lot Models
"""
Produce lot creation, FPO aggregation, and sale lifecycle tracking.
"""

import enum
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    Date,
    ForeignKey,
    Index,
    UniqueConstraint,
    Text,
    Enum as SQLEnum,
    JSON,
)
from sqlalchemy.orm import relationship

from ..db import Base


class LotStatus(str, enum.Enum):
    """Lifecycle status of a produce lot."""
    DRAFT = "draft"                    # Being created, not yet published
    OPEN = "open"                      # Published, accepting buyer interest
    MATCHED = "matched"                # Buyer matched, negotiation in progress
    NEGOTIATING = "negotiating"        # Price/terms negotiation
    CONTRACTED = "contracted"          # Agreement signed
    READY_FOR_PICKUP = "ready_for_pickup"  # Produce ready, awaiting collection
    IN_TRANSIT = "in_transit"          # Produce collected, en route
    DELIVERED = "delivered"            # Delivered to buyer
    SETTLED = "settled"                # Payment received
    COMPLETED = "completed"            # Full lifecycle complete
    CANCELLED = "cancelled"            # Cancelled by seller
    EXPIRED = "expired"                # Availability window passed
    DISPUTED = "disputed"              # Quality/payment dispute


class SellerType(str, enum.Enum):
    """Type of seller."""
    INDIVIDUAL_FARMER = "individual_farmer"
    FPO = "fpo"
    COOPERATIVE = "cooperative"
    TRADER = "trader"


class Lot(Base):
    """
    Produce Lot - core entity for market access.
    Created by farmer/FPO, matched with buyers, tracked through sale lifecycle.
    """
    __tablename__ = "lots"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    lot_id = Column(String(50), nullable=False, unique=True, index=True)  # "AGRI-2026-1001"
    
    # Seller
    seller_type = Column(SQLEnum(SellerType), nullable=False, default=SellerType.INDIVIDUAL_FARMER, index=True)
    farmer_id = Column(Integer, ForeignKey("farmers.id", ondelete="SET NULL"), nullable=True, index=True)
    fpo_id = Column(Integer, ForeignKey("fpos.id", ondelete="SET NULL"), nullable=True, index=True)
    seller_name = Column(String(200), nullable=False)  # Denormalized for display
    seller_contact_phone = Column(String(20), nullable=True)
    seller_contact_email = Column(String(100), nullable=True)
    
    # Produce details
    commodity_id = Column(String(50), ForeignKey("commodities.id", ondelete="RESTRICT"), nullable=False, index=True)
    commodity_name = Column(String(100), nullable=False)  # Denormalized
    variety = Column(String(100), nullable=True)
    quality_grade = Column(String(20), nullable=False, default="A", index=True)
    quantity = Column(Float, nullable=False)  # In quintals
    unit = Column(String(50), default="Quintal (100 kg)", nullable=False)
    
    # Quality specifications (detailed)
    quality_specs = Column(JSON, nullable=True)  # {"moisture": 12, "foreign_matter": 1, "size": "medium"}
    certifications = Column(JSON, nullable=True)  # ["organic", "fairtrade", "globalgap"]
    lab_test_report_id = Column(String(100), nullable=True)
    lab_test_date = Column(Date, nullable=True)
    lab_test_results = Column(JSON, nullable=True)
    
    # Location
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="SET NULL"), nullable=True, index=True)
    location_name = Column(String(300), nullable=False)  # Denormalized full address
    state_id = Column(Integer, ForeignKey("states.id", ondelete="SET NULL"), nullable=True, index=True)
    district_id = Column(Integer, ForeignKey("districts.id", ondelete="SET NULL"), nullable=True, index=True)
    pincode = Column(String(6), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    # Pricing
    expected_min_price = Column(Float, nullable=False)  # Per quintal
    expected_max_price = Column(Float, nullable=True)   # Per quintal
    reserve_price = Column(Float, nullable=True)        # Per quintal (confidential)
    pricing_basis = Column(String(50), nullable=True)   # "mandi_modal", "cost_plus", "market_survey"
    
    # Availability
    available_from = Column(Date, nullable=True)
    available_until = Column(Date, nullable=False, index=True)
    harvest_date = Column(Date, nullable=True)
    
    # Storage
    has_storage = Column(Boolean, default=False, nullable=False)
    storage_type = Column(String(50), nullable=True)  # "cold_storage", "godown", "on_farm", "none"
    storage_facility_name = Column(String(200), nullable=True)
    storage_location_id = Column(Integer, ForeignKey("locations.id", ondelete="SET NULL"), nullable=True)
    storage_cost_per_day_qtl = Column(Float, nullable=True)
    
    # Logistics
    can_deliver = Column(Boolean, default=False, nullable=False)
    delivery_radius_km = Column(Float, nullable=True)
    preferred_mandi_id = Column(Integer, ForeignKey("mandis.id", ondelete="SET NULL"), nullable=True)
    transport_arrangement = Column(String(50), nullable=True)  # "seller", "buyer", "shared", "fpo"
    
    # FPO Aggregation
    is_aggregated = Column(Boolean, default=False, nullable=False)
    parent_lot_id = Column(Integer, ForeignKey("lots.id", ondelete="SET NULL"), nullable=True)
    member_lots = relationship("Lot", backref="parent_lot", remote_side=[id])
    
    # Status & Lifecycle
    status = Column(SQLEnum(LotStatus), default=LotStatus.DRAFT, nullable=False, index=True)
    status_reason = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=True)
    matched_at = Column(DateTime(timezone=True), nullable=True)
    contracted_at = Column(DateTime(timezone=True), nullable=True)
    picked_up_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    settled_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Notes
    notes = Column(Text, nullable=True)
    internal_notes = Column(Text, nullable=True)  # For FPO/admin use
    
    # Relationships
    commodity = relationship("Commodity")
    location = relationship("Location", foreign_keys=[location_id])
    state = relationship("State")
    district = relationship("District")
    storage_location = relationship("Location", foreign_keys=[storage_location_id])
    preferred_mandi = relationship("Mandi")
    farmer = relationship("Farmer", back_populates="lots")
    fpo = relationship("FPO", back_populates="lots")
    members = relationship("LotMember", back_populates="lot", cascade="all, delete-orphan")
    interests = relationship("BuyerInterest", back_populates="lot", cascade="all, delete-orphan")
    timeline_events = relationship("LotTimelineEvent", back_populates="lot", cascade="all, delete-orphan", order_by="LotTimelineEvent.created_at")
    
    __table_args__ = (
        Index("ix_lot_status_dates", "status", "available_until"),
        Index("ix_lot_commodity_location", "commodity_id", "state_id", "district_id"),
        Index("ix_lot_seller", "seller_type", "farmer_id", "fpo_id"),
    )
    
    def __repr__(self):
        return f"<Lot(lot_id='{self.lot_id}', commodity='{self.commodity_id}', qty={self.quantity}, status={self.status.value})>"
    
    @property
    def is_active(self) -> bool:
        """Check if lot is actively accepting interest."""
        return self.status in [LotStatus.OPEN, LotStatus.MATCHED, LotStatus.NEGOTIATING]
    
    @property
    def days_until_expiry(self) -> Optional[int]:
        """Days until lot expires."""
        if self.available_until:
            delta = self.available_until - datetime.now(timezone.utc).date()
            return max(0, delta.days)
        return None
    
    @property
    def total_value_range(self) -> tuple:
        """Min and max expected total value."""
        min_val = self.expected_min_price * self.quantity
        max_val = self.expected_max_price * self.quantity if self.expected_max_price else min_val
        return (min_val, max_val)


class LotMember(Base):
    """
    Individual farmer contributions to an FPO-aggregated lot.
    """
    __tablename__ = "lot_members"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    lot_id = Column(Integer, ForeignKey("lots.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Farmer details
    farmer_id = Column(Integer, ForeignKey("farmers.id", ondelete="SET NULL"), nullable=True, index=True)
    farmer_name = Column(String(200), nullable=False)
    farmer_contact = Column(String(20), nullable=True)
    
    # Contribution
    quantity = Column(Float, nullable=False)  # In quintals
    quality_grade = Column(String(20), nullable=True)
    quality_specs = Column(JSON, nullable=True)
    
    # Pricing (if different from lot level)
    expected_price = Column(Float, nullable=True)
    
    # Location
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="SET NULL"), nullable=True)
    location_name = Column(String(300), nullable=True)
    
    # Status
    is_confirmed = Column(Boolean, default=False, nullable=False)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    lot = relationship("Lot", back_populates="members")
    farmer = relationship("Farmer")
    location = relationship("Location")
    
    __table_args__ = (
        Index("ix_lot_member_lot_confirmed", "lot_id", "is_confirmed"),
    )


class BuyerInterest(Base):
    """
    Buyer interest/expression of interest in a lot.
    """
    __tablename__ = "buyer_interests"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    lot_id = Column(Integer, ForeignKey("lots.id", ondelete="CASCADE"), nullable=False, index=True)
    buyer_id = Column(Integer, ForeignKey("buyers.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Offer details
    offered_price = Column(Float, nullable=True)  # Per quintal
    offered_quantity = Column(Float, nullable=True)  # Qtl (may be partial)
    total_offer_value = Column(Float, nullable=True)
    
    # Terms
    payment_terms = Column(String(200), nullable=True)
    collection_mode = Column(String(50), nullable=True)  # "farm_gate", "mandi", "warehouse"
    proposed_pickup_date = Column(Date, nullable=True)
    validity_days = Column(Integer, default=7, nullable=False)
    
    # Quality conditions
    quality_conditions = Column(Text, nullable=True)
    requires_lab_test = Column(Boolean, default=False, nullable=False)
    
    # Status
    status = Column(String(50), default="INTEREST_SENT", nullable=False, index=True)  # INTEREST_SENT, VIEWED, NEGOTIATING, ACCEPTED, REJECTED, WITHDRAWN, EXPIRED
    status_reason = Column(Text, nullable=True)
    
    # Communication
    message = Column(Text, nullable=True)
    contact_person = Column(String(100), nullable=True)
    contact_phone = Column(String(20), nullable=True)
    
    # Timestamps
    sent_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    viewed_at = Column(DateTime(timezone=True), nullable=True)
    responded_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    lot = relationship("Lot", back_populates="interests")
    buyer = relationship("Buyer")
    
    __table_args__ = (
        UniqueConstraint("lot_id", "buyer_id", name="uq_lot_buyer_interest"),
        Index("ix_buyer_interest_status", "lot_id", "status"),
    )


class LotTimelineEvent(Base):
    """
    Immutable timeline of lot lifecycle events for transparency.
    """
    __tablename__ = "lot_timeline_events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    lot_id = Column(Integer, ForeignKey("lots.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Event
    step = Column(String(50), nullable=False)  # "LOT_CREATED", "PUBLISHED", "BUYER_MATCHED", "INTEREST_RECEIVED", "NEGOTIATION_STARTED", "CONTRACTED", "PICKED_UP", "DELIVERED", "SETTLED", "COMPLETED", "CANCELLED"
    completed = Column(Boolean, default=False, nullable=False)
    status = Column(String(100), nullable=True)  # Additional status detail
    
    # Actor
    actor_type = Column(String(20), nullable=True)  # "farmer", "fpo", "buyer", "system", "admin"
    actor_id = Column(String(100), nullable=True)
    actor_name = Column(String(200), nullable=True)
    
    # Details
    details = Column(JSON, nullable=True)
    previous_status = Column(SQLEnum(LotStatus), nullable=True)
    new_status = Column(SQLEnum(LotStatus), nullable=True)
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    estimated_at = Column(DateTime(timezone=True), nullable=True)  # For future steps
    
    # Relationships
    lot = relationship("Lot", back_populates="timeline_events")
    
    __table_args__ = (
        Index("ix_lot_timeline_lot_created", "lot_id", "created_at"),
    )


# Farmer model (minimal, referenced by lots)
class Farmer(Base):
    """Farmer profile for lot ownership."""
    __tablename__ = "farmers"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    farmer_id = Column(String(50), nullable=False, unique=True, index=True)  # "FAR-2026-001"
    
    # Identity
    name = Column(String(200), nullable=False)
    phone = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    aadhaar_hash = Column(String(64), nullable=True)  # Hashed for privacy
    pan = Column(String(10), nullable=True)
    
    # Location
    village = Column(String(200), nullable=True)
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="SET NULL"), nullable=True)
    state_id = Column(Integer, ForeignKey("states.id", ondelete="SET NULL"), nullable=True)
    district_id = Column(Integer, ForeignKey("districts.id", ondelete="SET NULL"), nullable=True)
    pincode = Column(String(6), nullable=True)
    
    # Land details
    land_holding_hectares = Column(Float, nullable=True)
    land_ownership_type = Column(String(50), nullable=True)  # "owned", "leased", "sharecropping"
    
    # Verification
    is_verified = Column(Boolean, default=False, nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    kyc_status = Column(String(20), default="pending", nullable=False)  # pending, verified, rejected
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    location = relationship("Location")
    state = relationship("State")
    district = relationship("District")
    lots = relationship("Lot", back_populates="farmer")
    
    __table_args__ = (
        Index("ix_farmer_location", "state_id", "district_id"),
    )