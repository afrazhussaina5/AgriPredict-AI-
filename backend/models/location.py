# AgriPredict AI - Location Models
"""
Canonical location hierarchy:
State → District → Subdistrict/Mandal/Taluk → Location (Village/Town/City) → Pincode/GPS
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
)
from sqlalchemy.orm import relationship, declared_attr

from ..db import Base


class LocationType(str, enum.Enum):
    """Type of location in the hierarchy."""
    STATE = "state"
    DISTRICT = "district"
    SUBDISTRICT = "subdistrict"  # Mandal/Taluk/Tehsil
    VILLAGE = "village"
    TOWN = "town"
    CITY = "city"


class State(Base):
    """Indian State/Union Territory."""
    __tablename__ = "states"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    code = Column(String(10), nullable=False, unique=True, index=True)  # ISO 3166-2:IN code
    is_union_territory = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    districts = relationship("District", back_populates="state", cascade="all, delete-orphan", order_by="District.name")
    
    def __repr__(self):
        return f"<State(id={self.id}, name='{self.name}', code='{self.code}')>"


class District(Base):
    """District within a State."""
    __tablename__ = "districts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    state_id = Column(Integer, ForeignKey("states.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    code = Column(String(20), nullable=True, index=True)  # Census code
    headquarters = Column(String(100), nullable=True)  # District HQ town
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    state = relationship("State", back_populates="districts")
    subdistricts = relationship("Subdistrict", back_populates="district", cascade="all, delete-orphan", order_by="Subdistrict.name")
    locations = relationship("Location", back_populates="district", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint("state_id", "name", name="uq_district_state_name"),
        Index("ix_district_state_name", "state_id", "name"),
    )
    
    def __repr__(self):
        return f"<District(id={self.id}, name='{self.name}', state_id={self.state_id})>"


class Subdistrict(Base):
    """Subdistrict/Mandal/Taluk/Tehsil within a District."""
    __tablename__ = "subdistricts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    district_id = Column(Integer, ForeignKey("districts.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    code = Column(String(20), nullable=True, index=True)  # Census code
    type = Column(String(20), nullable=False, default="taluk")  # taluk, mandal, tehsil, block
    headquarters = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    district = relationship("District", back_populates="subdistricts")
    locations = relationship("Location", back_populates="subdistrict", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint("district_id", "name", name="uq_subdistrict_district_name"),
        Index("ix_subdistrict_district_name", "district_id", "name"),
    )
    
    def __repr__(self):
        return f"<Subdistrict(id={self.id}, name='{self.name}', district_id={self.district_id}, type='{self.type}')>"


class Location(Base):
    """
    Village/Town/City - the leaf level of the location hierarchy.
    Contains pincode and GPS coordinates.
    """
    __tablename__ = "locations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    subdistrict_id = Column(Integer, ForeignKey("subdistricts.id", ondelete="SET NULL"), nullable=True, index=True)
    district_id = Column(Integer, ForeignKey("districts.id", ondelete="CASCADE"), nullable=False, index=True)
    state_id = Column(Integer, ForeignKey("states.id", ondelete="CASCADE"), nullable=False, index=True)
    
    name = Column(String(150), nullable=False, index=True)
    type = Column(SQLEnum(LocationType), nullable=False, default=LocationType.VILLAGE, index=True)
    
    # Pincode (6-digit Indian PIN)
    pincode = Column(String(6), nullable=True, index=True)
    
    # GPS Coordinates (WGS84)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    # Source and verification
    source = Column(String(50), nullable=True)  # census, geocoded, manual, user
    source_url = Column(String(500), nullable=True)
    is_verified = Column(Boolean, default=False, nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verified_by = Column(String(100), nullable=True)
    
    # Population (optional, from census)
    population = Column(Integer, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    subdistrict = relationship("Subdistrict", back_populates="locations")
    district = relationship("District", back_populates="locations")
    state = relationship("State")
    
    __table_args__ = (
        UniqueConstraint("district_id", "name", "type", name="uq_location_district_name_type"),
        Index("ix_location_district_type", "district_id", "type"),
        Index("ix_location_pincode", "pincode"),
        Index("ix_location_coords", "latitude", "longitude"),
    )
    
    def __repr__(self):
        return f"<Location(id={self.id}, name='{self.name}', type={self.type.value}, pincode='{self.pincode}')>"
    
    @property
    def full_hierarchy(self) -> str:
        """Return full location hierarchy as string."""
        parts = [self.name]
        if self.subdistrict:
            parts.append(self.subdistrict.name)
        if self.district:
            parts.append(self.district.name)
        if self.state:
            parts.append(self.state.name)
        return ", ".join(reversed(parts))
    
    @property
    def has_coordinates(self) -> bool:
        """Check if location has valid GPS coordinates."""
        return self.latitude is not None and self.longitude is not None


class LocationSearchLog(Base):
    """Log of location searches/geocoding requests for analytics."""
    __tablename__ = "location_search_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    query = Column(String(500), nullable=False)
    resolved_location_id = Column(Integer, ForeignKey("locations.id", ondelete="SET NULL"), nullable=True)
    provider = Column(String(50), nullable=True)  # nominatim, google, manual
    status = Column(String(20), nullable=False)  # success, failed, partial
    response_time_ms = Column(Integer, nullable=True)
    ip_hash = Column(String(64), nullable=True)  # Hashed IP for privacy
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    resolved_location = relationship("Location")
    
    __table_args__ = (
        Index("ix_location_search_created", "created_at"),
        Index("ix_location_search_query", "query"),
    )