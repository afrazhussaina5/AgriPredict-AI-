# AgriPredict AI - Mandi Models
"""
Canonical Verified Mandi Master.
Only VERIFIED mandis are selectable by farmers.
No universal fallback mandis (like Kurnool as default).
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


class MandiStatus(str, enum.Enum):
    """Operational status of the mandi."""
    ACTIVE = "active"
    SEASONAL = "seasonal"
    CLOSED = "closed"
    UNDER_MAINTENANCE = "under_maintenance"
    UNKNOWN = "unknown"


class VerificationStatus(str, enum.Enum):
    """Verification status of mandi data."""
    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    EXPIRED = "expired"  # Verification expired, needs re-verification


# Association table for Mandi <-> Commodity many-to-many
mandi_commodities = Table(
    "mandi_commodities",
    Base.metadata,
    Column("mandi_id", Integer, ForeignKey("mandis.id", ondelete="CASCADE"), primary_key=True),
    Column("commodity_id", String(50), ForeignKey("commodities.id", ondelete="CASCADE"), primary_key=True),
    Column("is_primary", Boolean, default=False, nullable=False),  # Primary commodity for this mandi
    Column("seasonal_months", JSON, nullable=True),  # e.g., [1,2,3,10,11,12] for seasonal
    Column("created_at", DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False),
)


class Mandi(Base):
    """
    Verified Mandi Master.
    Each mandi must be verified from authoritative source before being selectable.
    """
    __tablename__ = "mandis"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Unique identifiers
    mandi_id = Column(String(50), nullable=False, unique=True, index=True)  # e.g., "mandi-kurnool"
    e_nam_id = Column(String(50), nullable=True, unique=True, index=True)  # e-NAM registration ID
    
    # Names
    name = Column(String(200), nullable=False, index=True)  # "Kurnool Agricultural Market Yard"
    apmc_name = Column(String(200), nullable=True, index=True)  # "Kurnool APMC"
    local_name = Column(String(200), nullable=True)  # Local language name
    
    # Location hierarchy
    state_id = Column(Integer, ForeignKey("states.id", ondelete="RESTRICT"), nullable=False, index=True)
    district_id = Column(Integer, ForeignKey("districts.id", ondelete="RESTRICT"), nullable=False, index=True)
    subdistrict_id = Column(Integer, ForeignKey("subdistricts.id", ondelete="SET NULL"), nullable=True, index=True)
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Address details
    address = Column(Text, nullable=True)
    pincode = Column(String(6), nullable=True, index=True)
    
    # GPS Coordinates (WGS84) - MANDATORY for verified mandis
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    
    # Operational details
    status = Column(SQLEnum(MandiStatus), default=MandiStatus.UNKNOWN, nullable=False, index=True)
    is_e_nam = Column(Boolean, default=False, nullable=False, index=True)
    market_type = Column(String(50), nullable=True)  # "Wholesale", "Retail", "Terminal", "Processing"
    
    # Contact
    phone = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    website = Column(String(200), nullable=True)
    
    # Facilities (JSON array)
    facilities = Column(JSON, nullable=True)  # ["Cold Storage", "Electronic Weighbridge", "Grading Lab", ...]
    
    # Verification
    verification_status = Column(
        SQLEnum(VerificationStatus), 
        default=VerificationStatus.UNVERIFIED, 
        nullable=False, 
        index=True
    )
    official_source = Column(String(200), nullable=True)  # "Data.gov.in", "State APMC Portal", "e-NAM", "Field Survey"
    source_url = Column(String(500), nullable=True)  # URL to official listing
    last_verified_at = Column(DateTime(timezone=True), nullable=True)
    verified_by = Column(String(100), nullable=True)
    verification_notes = Column(Text, nullable=True)
    
    # Market operations
    operating_hours = Column(String(100), nullable=True)  # "6:00 AM - 6:00 PM"
    market_days = Column(String(50), nullable=True)  # "Mon-Sat", "Daily", "Weekly Wed"
    arrival_capacity_qtl = Column(Integer, nullable=True)  # Daily arrival capacity in quintals
    
    # Pricing metadata (for fallback/estimation when live data unavailable)
    price_offset_multiplier = Column(Float, default=1.0, nullable=False)
    transport_cost_per_km_qtl = Column(Float, default=1.8, nullable=False)
    storage_cost_per_day_qtl = Column(Float, default=4.0, nullable=False)
    
    # Metadata
    rating = Column(Float, nullable=True)  # 1-5 rating
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    state = relationship("State")
    district = relationship("District")
    subdistrict = relationship("Subdistrict")
    location = relationship("Location")
    commodities = relationship(
        "Commodity",
        secondary=mandi_commodities,
        back_populates="mandis",
    )
    
    __table_args__ = (
        UniqueConstraint("mandi_id", name="uq_mandi_mandi_id"),
        UniqueConstraint("e_nam_id", name="uq_mandi_e_nam_id"),
        Index("ix_mandi_state_district", "state_id", "district_id"),
        Index("ix_mandi_verification", "verification_status", "status"),
        Index("ix_mandi_coords", "latitude", "longitude"),
        Index("ix_mandi_e_nam", "is_e_nam"),
    )
    
    def __repr__(self):
        return f"<Mandi(id={self.id}, mandi_id='{self.mandi_id}', name='{self.name}', verified={self.verification_status.value})>"
    
    @property
    def is_selectable(self) -> bool:
        """Check if mandi can be selected by farmers."""
        return (
            self.verification_status == VerificationStatus.VERIFIED 
            and self.status == MandiStatus.ACTIVE
            and self.latitude is not None 
            and self.longitude is not None
        )
    
    @property
    def commodity_ids(self) -> List[str]:
        """Get list of commodity IDs supported by this mandi."""
        return [c.id for c in self.commodities]


class MandiCommodity(Base):
    """
    Detailed commodity support for a mandi with seasonal info.
    """
    __tablename__ = "mandi_commodity_details"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    mandi_id = Column(Integer, ForeignKey("mandis.id", ondelete="CASCADE"), nullable=False, index=True)
    commodity_id = Column(String(50), ForeignKey("commodities.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Seasonal availability
    is_available_year_round = Column(Boolean, default=False, nullable=False)
    peak_months = Column(JSON, nullable=True)  # [1,2,3] for Jan-Mar peak
    lean_months = Column(JSON, nullable=True)
    
    # Price behavior
    typical_price_offset = Column(Float, default=1.0, nullable=False)  # Multiplier vs state average
    min_arrival_qtl = Column(Integer, nullable=True)
    max_arrival_qtl = Column(Integer, nullable=True)
    
    # Quality grades typically accepted
    accepted_grades = Column(JSON, nullable=True)  # ["A", "B", "FAQ"]
    
    # Source
    source = Column(String(100), nullable=True)
    source_url = Column(String(500), nullable=True)
    last_updated = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    mandi = relationship("Mandi")
    commodity = relationship("Commodity")
    
    __table_args__ = (
        UniqueConstraint("mandi_id", "commodity_id", name="uq_mandi_commodity"),
        Index("ix_mandi_commodity_peak", "peak_months"),
    )


class Commodity(Base):
    """
    Master commodity catalog.
    Synced with frontend commodity definitions.
    """
    __tablename__ = "commodities"
    
    id = Column(String(50), primary_key=True)  # e.g., "onion", "wheat", "cotton"
    name = Column(String(100), nullable=False, index=True)  # "Onion (प्याज / ఉల్లిపాయ)"
    variety = Column(String(100), nullable=True)
    category = Column(String(50), nullable=False, index=True)  # "Vegetables", "Cereals & Grains", etc.
    icon = Column(String(10), nullable=True)
    unit = Column(String(50), default="Quintal (100 kg)", nullable=False)
    
    # Default parameters for estimation
    default_qty = Column(Integer, default=50, nullable=False)
    shelf_life_days = Column(Integer, default=30, nullable=False)
    storage_cost_per_day_qtl = Column(Float, default=3.0, nullable=False)
    base_transport_rate_per_km_qtl = Column(Float, default=1.8, nullable=False)
    base_price = Column(Float, default=0, nullable=False)  # Base price per quintal
    predicted_price = Column(Float, default=0, nullable=False)  # Predicted price per quintal
    
    # Grade multipliers
    grade_multipliers = Column(JSON, nullable=False)  # {"A": 1.05, "B": 1.0, "C": 0.9}
    
    # ML Model info
    has_ml_model = Column(Boolean, default=False, nullable=False)
    model_version = Column(String(20), nullable=True)
    model_accuracy = Column(Float, nullable=True)
    
    # Metadata
    arrival_trend = Column(String(100), nullable=True)
    demand_index = Column(String(100), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    mandis = relationship(
        "Mandi",
        secondary=mandi_commodities,
        back_populates="commodities",
    )
    
    def __repr__(self):
        return f"<Commodity(id='{self.id}', name='{self.name}', category='{self.category}')>"