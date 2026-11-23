# AgriPredict AI - Sync Log Models
"""
Synchronization logs for market data, mandi data, buyer data, etc.
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
)
from sqlalchemy.orm import relationship

from ..db import Base


class SyncStatus(str, enum.Enum):
    """Sync job status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SyncType(str, enum.Enum):
    """Type of synchronization job."""
    MARKET_PRICES = "market_prices"
    MANDI_MASTER = "mandi_master"
    COMMODITY_MASTER = "commodity_master"
    LOCATION_HIERARCHY = "location_hierarchy"
    BUYER_VERIFICATION = "buyer_verification"
    TRANSPORT_RATES = "transport_rates"
    STORAGE_RATES = "storage_rates"
    HISTORICAL_AGGREGATION = "historical_aggregation"
    GEOCODE_BATCH = "geocode_batch"
    ROUTE_CACHE_WARM = "route_cache_warm"


class SyncLog(Base):
    """
    Log of all synchronization jobs.
    """
    __tablename__ = "sync_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Job identification
    sync_type = Column(SQLEnum(SyncType), nullable=False, index=True)
    job_id = Column(String(100), nullable=True, unique=True, index=True)  # UUID for tracking
    triggered_by = Column(String(50), nullable=False)  # "scheduler", "manual", "api", "webhook"
    triggered_by_user = Column(String(100), nullable=True)
    
    # Parameters
    parameters = Column(JSON, nullable=True)  # Filters, date ranges, etc.
    filters = Column(JSON, nullable=True)
    
    # Source
    source_name = Column(String(100), nullable=True)  # "data.gov.in", "state_apmc", "manual_upload"
    source_url = Column(String(500), nullable=True)
    
    # Progress
    status = Column(SQLEnum(SyncStatus), default=SyncStatus.PENDING, nullable=False, index=True)
    total_items = Column(Integer, default=0)
    processed_items = Column(Integer, default=0)
    new_items = Column(Integer, default=0)
    updated_items = Column(Integer, default=0)
    skipped_items = Column(Integer, default=0)
    error_items = Column(Integer, default=0)
    
    # Current item being processed (for progress tracking)
    current_item = Column(String(200), nullable=True)
    current_item_index = Column(Integer, default=0)
    
    # Results summary
    result_summary = Column(JSON, nullable=True)
    errors = Column(JSON, nullable=True)  # List of error objects
    
    # Performance
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    api_calls_made = Column(Integer, default=0)
    api_errors = Column(Integer, default=0)
    avg_response_time_ms = Column(Float, nullable=True)
    
    # Error details
    error_message = Column(Text, nullable=True)
    error_code = Column(String(50), nullable=True)
    stack_trace = Column(Text, nullable=True)
    
    # Retry
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    parent_sync_id = Column(Integer, ForeignKey("sync_logs.id", ondelete="SET NULL"), nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    parent_sync = relationship("SyncLog", remote_side=[id], backref="retries")
    
    __table_args__ = (
        Index("ix_sync_log_type_status", "sync_type", "status"),
        Index("ix_sync_log_created", "created_at"),
        Index("ix_sync_log_job", "job_id"),
    )
    
    def __repr__(self):
        return f"<SyncLog(id={self.id}, type={self.sync_type.value}, status={self.status.value}, items={self.processed_items}/{self.total_items})>"
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_items == 0:
            return 0.0
        return (self.processed_items - self.error_items) / self.total_items


class SyncSchedule(Base):
    """
    Scheduled sync jobs configuration.
    """
    __tablename__ = "sync_schedules"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Identification
    name = Column(String(100), nullable=False, unique=True)
    sync_type = Column(SQLEnum(SyncType), nullable=False)
    
    # Schedule (cron expression)
    cron_expression = Column(String(100), nullable=False)  # e.g., "0 6 * * *" for daily 6 AM
    timezone = Column(String(50), default="Asia/Kolkata", nullable=False)
    
    # Parameters
    default_parameters = Column(JSON, nullable=True)
    default_filters = Column(JSON, nullable=True)
    
    # Control
    is_active = Column(Boolean, default=True, nullable=False)
    max_concurrent_runs = Column(Integer, default=1, nullable=False)
    timeout_seconds = Column(Integer, default=3600, nullable=False)  # 1 hour default
    
    # Retry policy
    max_retries = Column(Integer, default=3, nullable=False)
    retry_delay_seconds = Column(Integer, default=300, nullable=False)  # 5 minutes
    
    # Notifications
    notify_on_success = Column(Boolean, default=False, nullable=False)
    notify_on_failure = Column(Boolean, default=True, nullable=False)
    notification_emails = Column(JSON, nullable=True)
    notification_webhook = Column(String(500), nullable=True)
    
    # Metadata
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    last_run_status = Column(SQLEnum(SyncStatus), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    __table_args__ = (
        Index("ix_sync_schedule_next_run", "next_run_at", "is_active"),
    )


class DataQualityReport(Base):
    """
    Data quality metrics for monitoring.
    """
    __tablename__ = "data_quality_reports"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Scope
    report_date = Column(Date, nullable=False, index=True)
    scope_type = Column(String(20), nullable=False)  # "national", "state", "district", "market", "commodity"
    scope_id = Column(String(100), nullable=True)  # state_id, district_id, market_id, commodity_id
    
    # Market price quality
    total_records = Column(Integer, default=0)
    live_records = Column(Integer, default=0)
    cached_records = Column(Integer, default=0)
    historical_records = Column(Integer, default=0)
    demo_records = Column(Integer, default=0)
    unavailable_records = Column(Integer, default=0)
    error_records = Column(Integer, default=0)
    
    # Freshness
    avg_data_age_hours = Column(Float, nullable=True)
    max_data_age_hours = Column(Float, nullable=True)
    records_older_24h = Column(Integer, default=0)
    records_older_7d = Column(Integer, default=0)
    
    # Completeness
    commodities_covered = Column(Integer, default=0)
    markets_covered = Column(Integer, default=0)
    districts_covered = Column(Integer, default=0)
    states_covered = Column(Integer, default=0)
    expected_commodities = Column(Integer, default=0)
    expected_markets = Column(Integer, default=0)
    
    # Accuracy flags
    outlier_records = Column(Integer, default=0)
    duplicate_records = Column(Integer, default=0)
    missing_price_records = Column(Integer, default=0)
    missing_arrival_records = Column(Integer, default=0)
    
    # Source breakdown
    source_breakdown = Column(JSON, nullable=True)  # {"data.gov.in": 1000, "state_apmc": 500}
    
    # Metadata
    generated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    __table_args__ = (
        UniqueConstraint("report_date", "scope_type", "scope_id", name="uq_data_quality_report"),
        Index("ix_data_quality_date_scope", "report_date", "scope_type"),
    )