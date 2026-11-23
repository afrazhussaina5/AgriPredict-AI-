# AgriPredict AI - Market Data Models
"""
Market price data from government sources with full traceability.
Statuses: LIVE, CACHED, HISTORICAL, DEMO, UNAVAILABLE, ERROR
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
    Date,
    ForeignKey,
    Index,
    UniqueConstraint,
    Text,
    Enum as SQLEnum,
    JSON,
    func,
)
from sqlalchemy.orm import relationship

from ..db import Base


class MarketPriceStatus(str, enum.Enum):
    """Data source status for market prices."""
    LIVE = "live"                    # Fresh from government API
    CACHED = "cached"                # From local cache (recent)
    HISTORICAL = "historical"        # From historical database
    DEMO = "demo"                    # Demo/estimated data
    UNAVAILABLE = "unavailable"      # No data available
    ERROR = "error"                  # Fetch failed


class MarketPrice(Base):
    """
    Daily market price records from government mandi feeds.
    Each record represents one commodity at one market on one day.
    """
    __tablename__ = "market_prices"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Location hierarchy
    state_id = Column(Integer, ForeignKey("states.id", ondelete="RESTRICT"), nullable=False, index=True)
    district_id = Column(Integer, ForeignKey("districts.id", ondelete="RESTRICT"), nullable=False, index=True)
    market_id = Column(Integer, ForeignKey("mandis.id", ondelete="RESTRICT"), nullable=True, index=True)
    
    # Commodity
    commodity_id = Column(String(50), ForeignKey("commodities.id", ondelete="RESTRICT"), nullable=False, index=True)
    variety = Column(String(100), nullable=True)
    grade = Column(String(20), nullable=False, default="FAQ", index=True)  # FAQ, A, B, C, etc.
    
    # Date
    arrival_date = Column(Date, nullable=False, index=True)
    
    # Prices (in ₹ per quintal)
    min_price = Column(Float, nullable=True)
    max_price = Column(Float, nullable=True)
    modal_price = Column(Float, nullable=False, index=True)  # Most traded price
    
    # Volume
    arrival_quantity = Column(Float, nullable=True)  # In quintals
    arrival_unit = Column(String(20), default="Quintal", nullable=False)
    
    # Data provenance - CRITICAL for trust
    status = Column(SQLEnum(MarketPriceStatus), default=MarketPriceStatus.UNAVAILABLE, nullable=False, index=True)
    source = Column(String(100), nullable=False)  # "data.gov.in", "agmarknet", "state_apmc", "e-nam"
    source_url = Column(String(500), nullable=True)  # Direct URL to source record
    source_record_id = Column(String(100), nullable=True)  # ID from source system
    
    # Timestamps
    fetched_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Quality flags
    is_outlier = Column(Boolean, default=False, nullable=False)  # Statistically flagged
    quality_score = Column(Float, nullable=True)  # 0-1 confidence in this record
    notes = Column(Text, nullable=True)
    
    # Relationships
    state = relationship("State")
    district = relationship("District")
    market = relationship("Mandi")
    commodity = relationship("Commodity")
    
    __table_args__ = (
        # One record per commodity/grade/variety per market per day
        UniqueConstraint(
            "state_id", "district_id", "market_id", "commodity_id", 
            "variety", "grade", "arrival_date", 
            name="uq_market_price_unique_record"
        ),
        Index("ix_market_price_commodity_date", "commodity_id", "arrival_date"),
        Index("ix_market_price_market_date", "market_id", "arrival_date"),
        Index("ix_market_price_status_date", "status", "arrival_date"),
        Index("ix_market_price_fetched", "fetched_at"),
    )
    
    def __repr__(self):
        return f"<MarketPrice(id={self.id}, commodity={self.commodity_id}, market={self.market_id}, date={self.arrival_date}, modal={self.modal_price}, status={self.status.value})>"
    
    @property
    def price_spread(self) -> Optional[float]:
        """Price spread (max - min) if both available."""
        if self.min_price is not None and self.max_price is not None:
            return self.max_price - self.min_price
        return None
    
    @property
    def price_spread_pct(self) -> Optional[float]:
        """Price spread as percentage of modal price."""
        if self.modal_price and self.modal_price > 0 and self.price_spread:
            return (self.price_spread / self.modal_price) * 100
        return None


class HistoricalPrice(Base):
    """
    Aggregated historical price analytics for trend analysis.
    Pre-computed for performance.
    """
    __tablename__ = "historical_prices"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Grouping keys
    commodity_id = Column(String(50), ForeignKey("commodities.id", ondelete="RESTRICT"), nullable=False, index=True)
    state_id = Column(Integer, ForeignKey("states.id", ondelete="RESTRICT"), nullable=True, index=True)
    district_id = Column(Integer, ForeignKey("districts.id", ondelete="RESTRICT"), nullable=True, index=True)
    market_id = Column(Integer, ForeignKey("mandis.id", ondelete="RESTRICT"), nullable=True, index=True)
    variety = Column(String(100), nullable=True)
    grade = Column(String(20), nullable=True)
    
    # Time period
    period_start = Column(Date, nullable=False, index=True)
    period_end = Column(Date, nullable=False, index=True)
    period_type = Column(String(20), nullable=False)  # "daily", "weekly", "monthly", "seasonal", "annual"
    
    # Aggregated statistics
    avg_modal_price = Column(Float, nullable=False)
    min_modal_price = Column(Float, nullable=False)
    max_modal_price = Column(Float, nullable=False)
    median_modal_price = Column(Float, nullable=True)
    std_dev_price = Column(Float, nullable=True)
    
    total_arrivals = Column(Float, nullable=True)
    avg_daily_arrivals = Column(Float, nullable=True)
    num_records = Column(Integer, nullable=False)
    
    # Trend indicators
    price_trend = Column(String(20), nullable=True)  # "rising", "falling", "stable", "volatile"
    trend_strength = Column(Float, nullable=True)  # 0-1
    volatility_index = Column(Float, nullable=True)
    
    # Metadata
    computed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    data_completeness = Column(Float, nullable=True)  # 0-1, fraction of days with data
    
    __table_args__ = (
        UniqueConstraint(
            "commodity_id", "state_id", "district_id", "market_id", 
            "variety", "grade", "period_start", "period_type",
            name="uq_historical_price_period"
        ),
        Index("ix_historical_commodity_period", "commodity_id", "period_type", "period_start"),
    )


class MarketPriceFetchLog(Base):
    """Log of market data fetch attempts for monitoring."""
    __tablename__ = "market_price_fetch_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Request parameters
    state_id = Column(Integer, ForeignKey("states.id", ondelete="SET NULL"), nullable=True)
    district_id = Column(Integer, ForeignKey("districts.id", ondelete="SET NULL"), nullable=True)
    commodity_id = Column(String(50), ForeignKey("commodities.id", ondelete="SET NULL"), nullable=True)
    arrival_date = Column(Date, nullable=True)
    limit = Column(Integer, nullable=True)
    offset = Column(Integer, nullable=True)
    
    # Response
    status = Column(String(20), nullable=False)  # success, error, unconfigured, partial
    records_fetched = Column(Integer, default=0)
    records_new = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)
    records_skipped = Column(Integer, default=0)
    total_available = Column(Integer, nullable=True)
    
    # Error info
    error_message = Column(Text, nullable=True)
    error_code = Column(String(50), nullable=True)
    
    # Performance
    response_time_ms = Column(Integer, nullable=True)
    api_latency_ms = Column(Integer, nullable=True)
    
    # Metadata
    source = Column(String(100), nullable=True)  # "live_api", "cached_data", "mock_fallback"
    requested_by = Column(String(100), nullable=True)  # "scheduler", "user", "api"
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    __table_args__ = (
        Index("ix_fetch_log_created", "created_at"),
        Index("ix_fetch_log_status", "status"),
    )