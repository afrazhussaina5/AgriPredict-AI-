# AgriPredict AI - Routing Models
"""
Route caching for farmer-to-mandi distance and duration.
Real road routing via OSRM/ORS/Google Maps.
"""

import enum
from datetime import datetime, timezone
from typing import Optional

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
)
from sqlalchemy.orm import relationship

from ..db import Base


class RoutingProvider(str, enum.Enum):
    """Routing engine provider."""
    OSRM = "osrm"
    ORS = "ors"  # OpenRouteService
    GOOGLE = "google"
    MAPBOX = "mapbox"
    GRAPHHOPPER = "graphhopper"


class RouteProfile(str, enum.Enum):
    """Vehicle/profile for routing."""
    CAR = "car"
    TRUCK = "truck"
    TRACTOR = "tractor"
    SMALL_TRUCK = "small_truck"
    MULTI_AXLE_TRUCK = "multi_axle_truck"


class RouteCache(Base):
    """
    Cached route between farmer location and mandi.
    Stores road distance (km) and duration (minutes).
    """
    __tablename__ = "route_cache"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Origin (farmer location)
    origin_lat = Column(Float, nullable=False)
    origin_lng = Column(Float, nullable=False)
    origin_location_id = Column(Integer, ForeignKey("locations.id", ondelete="SET NULL"), nullable=True, index=True)
    origin_pincode = Column(String(6), nullable=True)
    
    # Destination (mandi)
    destination_lat = Column(Float, nullable=False)
    destination_lng = Column(Float, nullable=False)
    destination_mandi_id = Column(Integer, ForeignKey("mandis.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Route profile
    profile = Column(SQLEnum(RouteProfile), default=RouteProfile.TRUCK, nullable=False)
    provider = Column(SQLEnum(RoutingProvider), default=RoutingProvider.OSRM, nullable=False)
    
    # Results
    distance_km = Column(Float, nullable=False)  # Road distance
    duration_minutes = Column(Float, nullable=False)  # Travel time
    duration_traffic_minutes = Column(Float, nullable=True)  # With traffic if available
    
    # Route geometry (GeoJSON LineString)
    geometry = Column(JSON, nullable=True)
    
    # Alternative routes summary
    alternatives = Column(JSON, nullable=True)  # [{"distance_km": , "duration_minutes": , "geometry": }]
    
    # Metadata
    status = Column(String(20), default="success", nullable=False)  # success, partial, failed
    error_message = Column(Text, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    
    # Cache control
    expires_at = Column(DateTime(timezone=True), nullable=True)  # Recalculate after expiry
    is_stale = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    origin_location = relationship("Location", foreign_keys=[origin_location_id])
    destination_mandi = relationship("Mandi")
    
    __table_args__ = (
        # Unique route per origin/destination/profile/provider
        UniqueConstraint(
            "origin_lat", "origin_lng", "destination_lat", "destination_lng",
            "profile", "provider",
            name="uq_route_cache_unique"
        ),
        Index("ix_route_cache_origin_dest", "origin_location_id", "destination_mandi_id"),
        Index("ix_route_cache_coords", "origin_lat", "origin_lng", "destination_lat", "destination_lng"),
        Index("ix_route_cache_expires", "expires_at"),
    )
    
    def __repr__(self):
        return f"<RouteCache(origin=({self.origin_lat},{self.origin_lng}), dest=({self.destination_lat},{self.destination_lng}), dist={self.distance_km:.1f}km, dur={self.duration_minutes:.0f}min)>"


class GeocodeCache(Base):
    """
    Cached geocoding results for addresses/pincodes.
    """
    __tablename__ = "geocode_cache"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Input
    query = Column(String(500), nullable=False, index=True)
    query_normalized = Column(String(500), nullable=False, index=True)  # Lowercase, stripped
    query_type = Column(String(20), nullable=False)  # "address", "pincode", "place", "reverse"
    
    # Provider
    provider = Column(String(50), nullable=False)  # "nominatim", "google", "mapbox"
    
    # Results
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    formatted_address = Column(String(500), nullable=True)
    address_components = Column(JSON, nullable=True)  # Structured address parts
    place_type = Column(String(50), nullable=True)  # "village", "town", "city", "pincode"
    confidence = Column(Float, nullable=True)  # 0-1
    
    # Location hierarchy (if resolved)
    state_id = Column(Integer, ForeignKey("states.id", ondelete="SET NULL"), nullable=True)
    district_id = Column(Integer, ForeignKey("districts.id", ondelete="SET NULL"), nullable=True)
    subdistrict_id = Column(Integer, ForeignKey("subdistricts.id", ondelete="SET NULL"), nullable=True)
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="SET NULL"), nullable=True)
    pincode = Column(String(6), nullable=True)
    
    # Status
    status = Column(String(20), default="success", nullable=False)  # success, partial, failed, ambiguous
    error_message = Column(Text, nullable=True)
    results_count = Column(Integer, default=0)
    
    # Cache control
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    __table_args__ = (
        UniqueConstraint("query_normalized", "provider", name="uq_geocode_cache_query_provider"),
        Index("ix_geocode_cache_location", "state_id", "district_id"),
    )


class TransportRate(Base):
    """
    Transport rate configuration for cost estimation.
    """
    __tablename__ = "transport_rates"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Applicability
    state_id = Column(Integer, ForeignKey("states.id", ondelete="CASCADE"), nullable=True)
    district_id = Column(Integer, ForeignKey("districts.id", ondelete="CASCADE"), nullable=True)
    commodity_id = Column(String(50), ForeignKey("commodities.id", ondelete="CASCADE"), nullable=True)
    vehicle_type = Column(String(50), nullable=True)  # "truck_10t", "truck_16t", "tractor_trolley", "mini_truck"
    
    # Rate
    rate_per_km_per_qtl = Column(Float, nullable=False)  # ₹/km/quintal
    min_distance_km = Column(Float, default=0, nullable=False)
    max_distance_km = Column(Float, nullable=True)
    min_charge = Column(Float, nullable=True)  # Minimum charge per trip
    
    # Loading/Unloading
    loading_charge_per_qtl = Column(Float, default=0, nullable=False)
    unloading_charge_per_qtl = Column(Float, default=0, nullable=False)
    
    # Validity
    effective_from = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    effective_until = Column(DateTime(timezone=True), nullable=True)
    
    # Source
    source = Column(String(100), nullable=True)  # "state_government", "market_survey", "transporter_association"
    source_url = Column(String(500), nullable=True)
    verified = Column(Boolean, default=False, nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    state = relationship("State")
    district = relationship("District")
    commodity = relationship("Commodity")
    
    __table_args__ = (
        Index("ix_transport_rate_lookup", "state_id", "district_id", "commodity_id", "vehicle_type"),
    )


class StorageRate(Base):
    """
    Storage rate configuration (cold storage/godown).
    """
    __tablename__ = "storage_rates"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Applicability
    state_id = Column(Integer, ForeignKey("states.id", ondelete="CASCADE"), nullable=True)
    district_id = Column(Integer, ForeignKey("districts.id", ondelete="CASCADE"), nullable=True)
    commodity_id = Column(String(50), ForeignKey("commodities.id", ondelete="CASCADE"), nullable=True)
    storage_type = Column(String(50), nullable=False)  # "cold_storage", "godown", "warehouse", "cold_chamber"
    
    # Rate
    rate_per_day_per_qtl = Column(Float, nullable=False)  # ₹/day/quintal
    min_charge_per_day = Column(Float, nullable=True)
    min_quantity_qtl = Column(Float, default=1, nullable=False)
    
    # Capacity
    facility_name = Column(String(200), nullable=True)
    facility_id = Column(Integer, nullable=True)  # Reference to facility registry
    capacity_mt = Column(Float, nullable=True)
    available_capacity_mt = Column(Float, nullable=True)
    
    # Validity
    effective_from = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    effective_until = Column(DateTime(timezone=True), nullable=True)
    seasonal_multiplier = Column(JSON, nullable=True)  # {"peak": 1.5, "lean": 0.8}
    
    # Source
    source = Column(String(100), nullable=True)
    source_url = Column(String(500), nullable=True)
    verified = Column(Boolean, default=False, nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    state = relationship("State")
    district = relationship("District")
    commodity = relationship("Commodity")
    
    __table_args__ = (
        Index("ix_storage_rate_lookup", "state_id", "district_id", "commodity_id", "storage_type"),
    )