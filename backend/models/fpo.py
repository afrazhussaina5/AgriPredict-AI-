# AgriPredict AI - FPO Models
"""
Farmer Producer Organization (FPO) models for collective aggregation.
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


class FPOStatus(str, enum.Enum):
    """FPO registration and operational status."""
    REGISTERING = "registering"
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DISSOLVED = "dissolved"
    DEMO = "demo"  # Prototype/demo FPO


class FPOType(str, enum.Enum):
    """Legal structure of FPO."""
    PRODUCER_COMPANY = "producer_company"      # Section 8 / Producer Company
    COOPERATIVE = "cooperative"                 # Cooperative Society
    FARMER_GROUP = "farmer_group"               # Informal Farmer Group
    TRUST = "trust"                             # Trust
    SOCIETY = "society"                         # Society Registration Act
    OTHER = "other"


# Association table for FPO <-> Commodity (commodities the FPO deals in)
fpo_commodities = Table(
    "fpo_commodities",
    Base.metadata,
    Column("fpo_id", Integer, ForeignKey("fpos.id", ondelete="CASCADE"), primary_key=True),
    Column("commodity_id", String(50), ForeignKey("commodities.id", ondelete="CASCADE"), primary_key=True),
    Column("is_primary", Boolean, default=False, nullable=False),
    Column("annual_volume_qtl", Float, nullable=True),
    Column("created_at", DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False),
)


# Association table for FPO <-> Mandi (mandis the FPO sells at)
fpo_mandis = Table(
    "fpo_mandis",
    Base.metadata,
    Column("fpo_id", Integer, ForeignKey("fpos.id", ondelete="CASCADE"), primary_key=True),
    Column("mandi_id", Integer, ForeignKey("mandis.id", ondelete="CASCADE"), primary_key=True),
    Column("is_preferred", Boolean, default=False, nullable=False),
    Column("created_at", DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False),
)


class FPO(Base):
    """
    Farmer Producer Organization.
    Enables collective aggregation and market access for member farmers.
    """
    __tablename__ = "fpos"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    fpo_id = Column(String(50), nullable=False, unique=True, index=True)  # "FPO-2026-001"
    
    # Identity
    name = Column(String(200), nullable=False, index=True)
    legal_name = Column(String(300), nullable=True)
    type = Column(SQLEnum(FPOType), nullable=False, default=FPOType.PRODUCER_COMPANY)
    
    # Registration
    registration_number = Column(String(100), nullable=True, unique=True, index=True)  # CIN / Registration No.
    registration_date = Column(Date, nullable=True)
    registration_authority = Column(String(200), nullable=True)  # "MCA", "Registrar of Cooperatives"
    pan = Column(String(10), nullable=True, unique=True)
    gstin = Column(String(15), nullable=True, unique=True, index=True)
    tan = Column(String(10), nullable=True)
    
    # Governance
    board_members = Column(JSON, nullable=True)  # [{"name": "", "designation": "", "contact": ""}]
    ceo_name = Column(String(100), nullable=True)
    ceo_contact = Column(String(20), nullable=True)
    ceo_email = Column(String(100), nullable=True)
    
    # Location
    registered_address = Column(Text, nullable=True)
    operational_address = Column(Text, nullable=True)
    state_id = Column(Integer, ForeignKey("states.id", ondelete="SET NULL"), nullable=True, index=True)
    district_id = Column(Integer, ForeignKey("districts.id", ondelete="SET NULL"), nullable=True, index=True)
    block_id = Column(Integer, ForeignKey("subdistricts.id", ondelete="SET NULL"), nullable=True)
    pincode = Column(String(6), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    # Operations
    status = Column(SQLEnum(FPOStatus), default=FPOStatus.REGISTERING, nullable=False, index=True)
    member_count = Column(Integer, default=0, nullable=False)
    total_land_hectares = Column(Float, default=0.0, nullable=False)
    share_capital = Column(Float, default=0.0, nullable=False)
    paid_up_capital = Column(Float, default=0.0, nullable=False)
    
    # Commodities & Markets
    commodities = relationship(
        "Commodity",
        secondary=fpo_commodities,
        back_populates="fpos",
    )
    mandis = relationship(
        "Mandi",
        secondary=fpo_mandis,
        back_populates="fpos",
    )
    
    # Infrastructure
    has_collection_centers = Column(Boolean, default=False, nullable=False)
    collection_centers = Column(JSON, nullable=True)  # [{"name": "", "location_id": "", "capacity_qtl": ""}]
    has_cold_storage = Column(Boolean, default=False, nullable=False)
    cold_storage_capacity_mt = Column(Float, nullable=True)
    has_processing_unit = Column(Boolean, default=False, nullable=False)
    processing_capacity = Column(JSON, nullable=True)  # [{"commodity": "", "capacity_qtl_per_day": ""}]
    has_transport = Column(Boolean, default=False, nullable=False)
    transport_details = Column(JSON, nullable=True)
    
    # Certifications
    certifications = Column(JSON, nullable=True)  # ["FPO Certification", "Organic", "Fairtrade", "ISO"]
    fpo_certification_number = Column(String(100), nullable=True)
    fpo_certification_date = Column(Date, nullable=True)
    fpo_certification_expiry = Column(Date, nullable=True)
    
    # Financial
    annual_turnover = Column(Float, nullable=True)
    profit_last_year = Column(Float, nullable=True)
    bank_account = Column(JSON, nullable=True)  # {"bank": "", "branch": "", "account": "", "ifsc": ""}
    
    # Contact
    phone = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    website = Column(String(200), nullable=True)
    
    # Demo flag
    is_demo = Column(Boolean, default=False, nullable=False, index=True)
    demo_disclaimer = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    created_by = Column(String(100), nullable=True)
    
    # Relationships
    state = relationship("State")
    district = relationship("District")
    block = relationship("Subdistrict")
    members = relationship("FPOMember", back_populates="fpo", cascade="all, delete-orphan")
    lots = relationship("Lot", back_populates="fpo")
    
    __table_args__ = (
        Index("ix_fpo_status_active", "status", "is_demo"),
        Index("ix_fpo_location", "state_id", "district_id"),
    )
    
    def __repr__(self):
        return f"<FPO(fpo_id='{self.fpo_id}', name='{self.name}', status={self.status.value}, members={self.member_count})>"
    
    @property
    def is_operational(self) -> bool:
        """Check if FPO is operational for aggregation."""
        return self.status == FPOStatus.ACTIVE and not self.is_demo


class FPOMember(Base):
    """
    Individual farmer members of an FPO.
    """
    __tablename__ = "fpo_members"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    fpo_id = Column(Integer, ForeignKey("fpos.id", ondelete="CASCADE"), nullable=False, index=True)
    farmer_id = Column(Integer, ForeignKey("farmers.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Member details
    member_id = Column(String(50), nullable=True, unique=True)  # Internal member ID
    name = Column(String(200), nullable=False)
    father_spouse_name = Column(String(200), nullable=True)
    phone = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    
    # Identity
    aadhaar_hash = Column(String(64), nullable=True)
    pan = Column(String(10), nullable=True)
    voter_id = Column(String(20), nullable=True)
    
    # Land
    village = Column(String(200), nullable=True)
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="SET NULL"), nullable=True)
    survey_numbers = Column(JSON, nullable=True)  # ["123/1", "124/2"]
    total_area_hectares = Column(Float, nullable=True)
    irrigated_area_hectares = Column(Float, nullable=True)
    ownership_type = Column(String(50), nullable=True)  # "owned", "leased", "forest_rights"
    
    # Shareholding
    shares_held = Column(Integer, default=0, nullable=False)
    share_value = Column(Float, default=0.0, nullable=False)
    date_of_joining = Column(Date, nullable=True)
    
    # Crops
    primary_crops = Column(JSON, nullable=True)  # [{"commodity_id": "", "area_hectares": "", "season": ""}]
    annual_production_qtl = Column(Float, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    membership_status = Column(String(20), default="active", nullable=False)  # active, inactive, expelled, resigned
    kyc_status = Column(String(20), default="pending", nullable=False)  # pending, verified, rejected
    
    # Bank
    bank_account = Column(JSON, nullable=True)  # {"bank": "", "account": "", "ifsc": ""}
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    fpo = relationship("FPO", back_populates="members")
    farmer = relationship("Farmer")
    location = relationship("Location")
    
    __table_args__ = (
        UniqueConstraint("fpo_id", "member_id", name="uq_fpo_member_id"),
        Index("ix_fpo_member_active", "fpo_id", "is_active"),
    )


class FPOAggregationPlan(Base):
    """
    Aggregation plan for collective selling.
    """
    __tablename__ = "fpo_aggregation_plans"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    fpo_id = Column(Integer, ForeignKey("fpos.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Plan details
    commodity_id = Column(String(50), ForeignKey("commodities.id", ondelete="RESTRICT"), nullable=False, index=True)
    season = Column(String(50), nullable=True)  # "Kharif 2026", "Rabi 2026-27"
    target_quantity_qtl = Column(Float, nullable=False)
    target_grade = Column(String(20), nullable=True)
    
    # Collection
    collection_start_date = Column(Date, nullable=True)
    collection_end_date = Column(Date, nullable=True)
    collection_centers = Column(JSON, nullable=True)  # List of center IDs/details
    
    # Quality
    quality_standards = Column(JSON, nullable=True)
    requires_sorting_grading = Column(Boolean, default=True, nullable=False)
    
    # Logistics
    transport_arranged = Column(Boolean, default=False, nullable=False)
    transport_details = Column(JSON, nullable=True)
    
    # Marketing
    target_markets = Column(JSON, nullable=True)  # [{"mandi_id": "", "expected_price": ""}]
    target_buyers = Column(JSON, nullable=True)   # [{"buyer_id": "", "contracted_qty": ""}]
    marketing_strategy = Column(Text, nullable=True)
    
    # Status
    status = Column(String(20), default="planned", nullable=False)  # planned, collecting, aggregated, marketed, completed
    actual_quantity_qtl = Column(Float, default=0.0, nullable=False)
    actual_revenue = Column(Float, default=0.0, nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    created_by = Column(String(100), nullable=True)
    
    # Relationships
    fpo = relationship("FPO")
    commodity = relationship("Commodity")
    
    __table_args__ = (
        Index("ix_fpo_agg_plan_status", "fpo_id", "status"),
    )


# Add back-references
from .mandi import Commodity, Mandi

Commodity.fpos = relationship(
    "FPO",
    secondary=fpo_commodities,
    back_populates="commodities",
)

Mandi.fpos = relationship(
    "FPO",
    secondary=fpo_mandis,
    back_populates="mandis",
)