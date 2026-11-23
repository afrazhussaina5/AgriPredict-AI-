# AgriPredict AI - Buyer Models
"""
Verified buyer onboarding and matching system.
Only genuinely verified buyers appear in VERIFIED BUYERS.
Demo buyers remain marked as DEMO.
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
    Table,
)
from sqlalchemy.orm import relationship

from ..db import Base


class BuyerVerificationStatus(str, enum.Enum):
    """Verification status of buyer."""
    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    SUSPENDED = "suspended"
    DEMO = "demo"  # Explicitly marked as demo/prototype


class BuyerCategory(str, enum.Enum):
    """Buyer category classification."""
    CORPORATE_RETAIL = "corporate_retail"       # BigBasket, Reliance, etc.
    AGRIBUSINESS = "agribusiness"               # ITC, ADM, Cargill, etc.
    EXPORTER = "exporter"                       # Spice exporters, etc.
    PROCESSOR = "processor"                     # Mills, crushing plants, etc.
    FPO_COOPERATIVE = "fpo_cooperative"         # Farmer Producer Organizations
    COMMISSION_AGENT = "commission_agent"       # Licensed APMC commission merchants
    WHOLESALE_TRADER = "wholesale_trader"       # Traditional wholesale traders
    GOVERNMENT = "government"                   # FCI, NAFED, state procurement
    OTHER = "other"


# Association table for Buyer <-> Commodity
buyer_commodities = Table(
    "buyer_commodities",
    Base.metadata,
    Column("buyer_id", Integer, ForeignKey("buyers.id", ondelete="CASCADE"), primary_key=True),
    Column("commodity_id", String(50), ForeignKey("commodities.id", ondelete="CASCADE"), primary_key=True),
    Column("min_quantity_qtl", Float, default=1.0, nullable=False),
    Column("max_quantity_qtl", Float, nullable=True),
    Column("accepted_grades", JSON, nullable=True),  # ["A", "B", "FAQ"]
    Column("quality_specs", JSON, nullable=True),    # {"moisture_max": 12, "foreign_matter_max": 1}
    Column("price_multiplier", Float, default=1.05, nullable=False),  # Offer vs mandi modal
    Column("is_primary", Boolean, default=False, nullable=False),
    Column("seasonal_months", JSON, nullable=True),
    Column("created_at", DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False),
)


# Association table for Buyer <-> Location (serviceable areas)
buyer_locations = Table(
    "buyer_locations",
    Base.metadata,
    Column("buyer_id", Integer, ForeignKey("buyers.id", ondelete="CASCADE"), primary_key=True),
    Column("state_id", Integer, ForeignKey("states.id", ondelete="CASCADE"), primary_key=True),
    Column("district_id", Integer, ForeignKey("districts.id", ondelete="CASCADE"), nullable=True),
    Column("max_distance_km", Float, default=100.0, nullable=False),
    Column("preferred_collection", String(50), nullable=True),  # "farm_gate", "mandi", "warehouse", "any"
    Column("created_at", DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False),
)


class Buyer(Base):
    """
    Verified Buyer Master.
    Only VERIFIED buyers appear in verified buyer listings.
    """
    __tablename__ = "buyers"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Identity
    buyer_id = Column(String(50), nullable=False, unique=True, index=True)  # "buyer-bb-01"
    legal_name = Column(String(200), nullable=False, index=True)  # "BigBasket Direct Farm Sourcing"
    trade_name = Column(String(200), nullable=True)  # "BigBasket"
    category = Column(SQLEnum(BuyerCategory), nullable=False, index=True)
    
    # Business registration
    registration_number = Column(String(100), nullable=True, unique=True)  # CIN, GSTIN, FPO registration
    gstin = Column(String(15), nullable=True, unique=True, index=True)  # GSTIN
    pan = Column(String(10), nullable=True, unique=True)
    fssai_license = Column(String(20), nullable=True)
    apmc_license = Column(String(50), nullable=True)  # For commission agents
    
    # Verification
    verification_status = Column(
        SQLEnum(BuyerVerificationStatus), 
        default=BuyerVerificationStatus.UNVERIFIED, 
        nullable=False, 
        index=True
    )
    verification_source = Column(String(200), nullable=True)  # "MCA", "GST Portal", "FSSAI", "APMC", "Field Visit", "Self-declared"
    verification_documents = Column(JSON, nullable=True)  # List of document references
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verified_by = Column(String(100), nullable=True)
    verification_expires_at = Column(DateTime(timezone=True), nullable=True)  # For periodic re-verification
    verification_notes = Column(Text, nullable=True)
    
    # Contact
    contact_person = Column(String(100), nullable=True)
    contact_phone = Column(String(20), nullable=True)
    contact_email = Column(String(100), nullable=True)
    website = Column(String(200), nullable=True)
    
    # Address (registered office)
    address = Column(Text, nullable=True)
    state_id = Column(Integer, ForeignKey("states.id", ondelete="SET NULL"), nullable=True, index=True)
    district_id = Column(Integer, ForeignKey("districts.id", ondelete="SET NULL"), nullable=True, index=True)
    pincode = Column(String(6), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    # Operational
    payment_terms = Column(String(200), nullable=True)  # "Direct Bank Transfer within 24 Hours"
    min_order_value = Column(Float, nullable=True)
    credit_period_days = Column(Integer, nullable=True)  # For corporate buyers
    requires_quality_cert = Column(Boolean, default=False, nullable=False)
    
    # Ratings & History
    rating = Column(Float, nullable=True)  # 1-5
    deals_completed = Column(Integer, default=0, nullable=False)
    total_volume_qtl = Column(Float, default=0.0, nullable=False)
    total_value_inr = Column(Float, default=0.0, nullable=False)
    on_time_payment_rate = Column(Float, nullable=True)  # 0-1
    dispute_rate = Column(Float, nullable=True)  # 0-1
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    is_accepting_orders = Column(Boolean, default=True, nullable=False)
    availability_notes = Column(Text, nullable=True)
    
    # Demo/Prototype flag
    is_demo = Column(Boolean, default=False, nullable=False, index=True)
    demo_disclaimer = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    created_by = Column(String(100), nullable=True)
    
    # Relationships
    state = relationship("State")
    district = relationship("District")
    commodities = relationship(
        "Commodity",
        secondary=buyer_commodities,
        back_populates="buyers",
    )
    serviceable_locations = relationship(
        "State",
        secondary=buyer_locations,
        back_populates="buyers",
    )
    documents = relationship("BuyerDocument", back_populates="buyer", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint("buyer_id", name="uq_buyer_buyer_id"),
        Index("ix_buyer_verification_active", "verification_status", "is_active"),
        Index("ix_buyer_category_active", "category", "is_active"),
        Index("ix_buyer_gstin", "gstin"),
    )
    
    def __repr__(self):
        return f"<Buyer(id={self.id}, buyer_id='{self.buyer_id}', name='{self.legal_name}', status={self.verification_status.value}, demo={self.is_demo})>"
    
    @property
    def is_verified_buyer(self) -> bool:
        """Check if buyer appears in verified listings."""
        return (
            self.verification_status == BuyerVerificationStatus.VERIFIED
            and self.is_active
            and not self.is_demo
        )
    
    @property
    def commodity_ids(self) -> List[str]:
        """Get list of commodity IDs this buyer procures."""
        return [c.id for c in self.commodities]


class BuyerCommodity(Base):
    """
    Detailed commodity procurement preferences for a buyer.
    """
    __tablename__ = "buyer_commodity_details"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    buyer_id = Column(Integer, ForeignKey("buyers.id", ondelete="CASCADE"), nullable=False, index=True)
    commodity_id = Column(String(50), ForeignKey("commodities.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Quantity preferences
    min_quantity_qtl = Column(Float, default=1.0, nullable=False)
    max_quantity_qtl = Column(Float, nullable=True)
    preferred_lot_size_qtl = Column(Float, nullable=True)
    
    # Quality requirements
    accepted_grades = Column(JSON, nullable=True)  # ["A", "B", "FAQ"]
    quality_specifications = Column(JSON, nullable=True)  # Detailed specs
    requires_lab_test = Column(Boolean, default=False, nullable=False)
    lab_test_parameters = Column(JSON, nullable=True)
    
    # Pricing
    base_offer_multiplier = Column(Float, default=1.05, nullable=False)  # vs mandi modal
    min_price_per_qtl = Column(Float, nullable=True)
    max_price_per_qtl = Column(Float, nullable=True)
    pricing_formula = Column(Text, nullable=True)  # e.g., "modal * 1.05 - transport"
    
    # Logistics
    collection_mode = Column(String(50), nullable=True)  # "farm_gate", "mandi", "buyer_warehouse"
    max_distance_km = Column(Float, nullable=True)
    provides_transport = Column(Boolean, default=False, nullable=False)
    provides_crates = Column(Boolean, default=False, nullable=False)
    
    # Seasonality
    active_months = Column(JSON, nullable=True)  # [1,2,3,10,11,12]
    peak_procurement_months = Column(JSON, nullable=True)
    
    # Contract
    contract_type = Column(String(50), nullable=True)  # "spot", "forward", "contract_farming"
    contract_duration_days = Column(Integer, nullable=True)
    
    # Metadata
    source = Column(String(100), nullable=True)
    last_updated = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    buyer = relationship("Buyer")
    commodity = relationship("Commodity")
    
    __table_args__ = (
        UniqueConstraint("buyer_id", "commodity_id", name="uq_buyer_commodity"),
    )


class BuyerDocument(Base):
    """Verification documents for buyers."""
    __tablename__ = "buyer_documents"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    buyer_id = Column(Integer, ForeignKey("buyers.id", ondelete="CASCADE"), nullable=False, index=True)
    
    document_type = Column(String(50), nullable=False)  # "incorporation", "gst", "fssai", "apmc_license", "pan", "address_proof", "bank_cancelled_cheque"
    document_number = Column(String(100), nullable=True)
    file_path = Column(String(500), nullable=True)  # Path to stored document
    file_hash = Column(String(64), nullable=True)  # SHA256 for integrity
    
    # Verification
    is_verified = Column(Boolean, default=False, nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verified_by = Column(String(100), nullable=True)
    expiry_date = Column(Date, nullable=True)
    
    # Metadata
    uploaded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    uploaded_by = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    
    # Relationships
    buyer = relationship("Buyer", back_populates="documents")
    
    __table_args__ = (
        Index("ix_buyer_doc_type", "buyer_id", "document_type"),
    )


# Add back-reference to Commodity
from .mandi import Commodity
Commodity.buyers = relationship(
    "Buyer",
    secondary=buyer_commodities,
    back_populates="commodities",
)

# Add back-reference to State for serviceable locations
from .location import State
State.buyers = relationship(
    "Buyer",
    secondary=buyer_locations,
    back_populates="serviceable_locations",
)