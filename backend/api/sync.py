# AgriPredict AI - Sync API Routes
"""
Synchronization job management and monitoring.
"""

from datetime import datetime, date, timezone, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, Field
from sqlalchemy import func, desc, and_
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    SyncLog, SyncSchedule, DataQualityReport,
    SyncStatus, SyncType,
    MarketPrice, MarketPriceStatus,
)

router = APIRouter(prefix="/sync", tags=["Synchronization"])


# =============================================================================
# Pydantic Schemas
# =============================================================================

class SyncLogResponse(BaseModel):
    id: int
    sync_type: SyncType
    job_id: Optional[str] = None
    triggered_by: str
    triggered_by_user: Optional[str] = None
    status: SyncStatus
    total_items: int
    processed_items: int
    new_items: int
    updated_items: int
    skipped_items: int
    error_items: int
    current_item: Optional[str] = None
    result_summary: Optional[dict] = None
    errors: Optional[List[dict]] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    api_calls_made: int
    api_errors: int
    error_message: Optional[str] = None
    retry_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SyncScheduleResponse(BaseModel):
    id: int
    name: str
    sync_type: SyncType
    cron_expression: str
    timezone: str
    is_active: bool
    max_concurrent_runs: int
    timeout_seconds: int
    max_retries: int
    last_run_at: Optional[datetime] = None
    last_run_status: Optional[SyncStatus] = None
    next_run_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SyncScheduleCreateRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    sync_type: SyncType
    cron_expression: str = Field(..., min_length=5, max_length=100)
    timezone: str = "Asia/Kolkata"
    default_parameters: Optional[dict] = None
    default_filters: Optional[dict] = None
    max_concurrent_runs: int = 1
    timeout_seconds: int = 3600
    max_retries: int = 3
    retry_delay_seconds: int = 300
    notify_on_success: bool = False
    notify_on_failure: bool = True
    notification_emails: Optional[List[str]] = None
    notification_webhook: Optional[str] = None


class TriggerSyncRequest(BaseModel):
    sync_type: SyncType
    parameters: Optional[dict] = None
    filters: Optional[dict] = None
    triggered_by: str = "manual"


class DataQualityResponse(BaseModel):
    report_date: date
    scope_type: str
    scope_id: Optional[str] = None
    total_records: int
    live_records: int
    cached_records: int
    historical_records: int
    demo_records: int
    unavailable_records: int
    error_records: int
    avg_data_age_hours: Optional[float] = None
    max_data_age_hours: Optional[float] = None
    commodities_covered: int
    markets_covered: int
    districts_covered: int
    states_covered: int
    outlier_records: int
    duplicate_records: int
    source_breakdown: Optional[dict] = None
    generated_at: datetime


# =============================================================================
# Sync Log Endpoints
# =============================================================================

@router.get("/logs", response_model=List[SyncLogResponse])
async def list_sync_logs(
    sync_type: Optional[SyncType] = Query(None),
    status: Optional[SyncStatus] = Query(None),
    triggered_by: Optional[str] = Query(None),
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List sync job logs."""
    query = db.query(SyncLog)
    
    if sync_type:
        query = query.filter(SyncLog.sync_type == sync_type)
    if status:
        query = query.filter(SyncLog.status == status)
    if triggered_by:
        query = query.filter(SyncLog.triggered_by == triggered_by)
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    query = query.filter(SyncLog.created_at >= cutoff)
    
    logs = query.order_by(desc(SyncLog.created_at)).limit(limit).all()
    return logs


@router.get("/logs/{log_id}", response_model=SyncLogResponse)
async def get_sync_log(
    log_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    """Get detailed sync log."""
    log = db.query(SyncLog).filter(SyncLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Sync log not found")
    return log


@router.post("/trigger", response_model=SyncLogResponse)
async def trigger_sync(
    request: TriggerSyncRequest,
    db: Session = Depends(get_db),
):
    """Manually trigger a sync job."""
    import uuid
    
    job_id = str(uuid.uuid4())
    
    # Create sync log entry
    log = SyncLog(
        sync_type=request.sync_type,
        job_id=job_id,
        triggered_by=request.triggered_by,
        triggered_by_user=request.triggered_by,
        parameters=request.parameters,
        filters=request.filters,
        status=SyncStatus.PENDING,
        start_time=datetime.now(timezone.utc),
    )
    
    db.add(log)
    db.commit()
    db.refresh(log)
    
    # TODO: Actually execute the sync job in background
    # For now, return the pending log
    return log


# =============================================================================
# Sync Schedule Endpoints
# =============================================================================

@router.get("/schedules", response_model=List[SyncScheduleResponse])
async def list_sync_schedules(
    is_active: Optional[bool] = Query(True),
    db: Session = Depends(get_db),
):
    """List configured sync schedules."""
    query = db.query(SyncSchedule)
    
    if is_active is not None:
        query = query.filter(SyncSchedule.is_active == is_active)
    
    schedules = query.order_by(SyncSchedule.name).all()
    return schedules


@router.get("/schedules/{schedule_id}", response_model=SyncScheduleResponse)
async def get_sync_schedule(
    schedule_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    """Get sync schedule details."""
    schedule = db.query(SyncSchedule).filter(SyncSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule


@router.post("/schedules", response_model=SyncScheduleResponse, status_code=201)
async def create_sync_schedule(
    request: SyncScheduleCreateRequest,
    db: Session = Depends(get_db),
):
    """Create a new sync schedule."""
    # Check for duplicate name
    existing = db.query(SyncSchedule).filter(SyncSchedule.name == request.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Schedule name already exists")
    
    schedule = SyncSchedule(
        name=request.name,
        sync_type=request.sync_type,
        cron_expression=request.cron_expression,
        timezone=request.timezone,
        default_parameters=request.default_parameters,
        default_filters=request.default_filters,
        max_concurrent_runs=request.max_concurrent_runs,
        timeout_seconds=request.timeout_seconds,
        max_retries=request.max_retries,
        retry_delay_seconds=request.retry_delay_seconds,
        notify_on_success=request.notify_on_success,
        notify_on_failure=request.notify_on_failure,
        notification_emails=request.notification_emails,
        notification_webhook=request.notification_webhook,
        is_active=True,
    )
    
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    
    return schedule


@router.patch("/schedules/{schedule_id}")
async def update_sync_schedule(
    schedule_id: int = Path(..., gt=0),
    is_active: Optional[bool] = Query(None),
    cron_expression: Optional[str] = Query(None),
    max_retries: Optional[int] = Query(None),
    notify_on_failure: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
):
    """Update sync schedule."""
    schedule = db.query(SyncSchedule).filter(SyncSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    if is_active is not None:
        schedule.is_active = is_active
    if cron_expression:
        schedule.cron_expression = cron_expression
    if max_retries is not None:
        schedule.max_retries = max_retries
    if notify_on_failure is not None:
        schedule.notify_on_failure = notify_on_failure
    
    schedule.updated_at = datetime.now(timezone.utc)
    db.commit()
    
    return {"status": "success", "schedule_id": schedule.id}


# =============================================================================
# Data Quality Endpoints
# =============================================================================

@router.get("/quality/report", response_model=DataQualityResponse)
async def get_data_quality_report(
    scope_type: str = Query("national", pattern="^(national|state|district|market|commodity)$"),
    scope_id: Optional[str] = Query(None),
    report_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    """Get data quality report."""
    target_date = report_date or date.today()
    
    report = db.query(DataQualityReport).filter(
        DataQualityReport.report_date == target_date,
        DataQualityReport.scope_type == scope_type,
        DataQualityReport.scope_id == scope_id,
    ).first()
    
    if not report:
        # Generate on-the-fly
        return await generate_quality_report(scope_type, scope_id, target_date, db)
    
    return DataQualityResponse.from_orm(report)


@router.get("/quality/reports", response_model=List[DataQualityResponse])
async def list_quality_reports(
    scope_type: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List recent quality reports."""
    query = db.query(DataQualityReport)
    
    if scope_type:
        query = query.filter(DataQualityReport.scope_type == scope_type)
    
    cutoff = date.today() - timedelta(days=days)
    query = query.filter(DataQualityReport.report_date >= cutoff)
    
    reports = query.order_by(desc(DataQualityReport.report_date)).limit(limit).all()
    return reports


async def generate_quality_report(scope_type: str, scope_id: Optional[str], target_date: date, db: Session) -> DataQualityResponse:
    """Generate quality report on demand."""
    query = db.query(MarketPrice).filter(
        MarketPrice.arrival_date <= target_date,
        MarketPrice.arrival_date >= target_date - timedelta(days=30),
    )
    
    if scope_type == "state" and scope_id:
        query = query.filter(MarketPrice.state_id == int(scope_id))
    elif scope_type == "district" and scope_id:
        query = query.filter(MarketPrice.district_id == int(scope_id))
    elif scope_type == "market" and scope_id:
        query = query.filter(MarketPrice.market_id == int(scope_id))
    elif scope_type == "commodity" and scope_id:
        query = query.filter(MarketPrice.commodity_id == scope_id)
    
    records = query.all()
    
    if not records:
        return DataQualityResponse(
            report_date=target_date,
            scope_type=scope_type,
            scope_id=scope_id,
            total_records=0,
            live_records=0,
            cached_records=0,
            historical_records=0,
            demo_records=0,
            unavailable_records=0,
            error_records=0,
            commodities_covered=0,
            markets_covered=0,
            districts_covered=0,
            states_covered=0,
            generated_at=datetime.now(timezone.utc),
        )
    
    # Count by status
    status_counts = {}
    for r in records:
        status_counts[r.status.value] = status_counts.get(r.status.value, 0) + 1
    
    # Source breakdown
    source_counts = {}
    for r in records:
        source_counts[r.source] = source_counts.get(r.source, 0) + 1
    
    # Data age
    now = datetime.now(timezone.utc)
    ages = [(now - r.fetched_at).total_seconds() / 3600 for r in records]
    avg_age = sum(ages) / len(ages) if ages else 0
    max_age = max(ages) if ages else 0
    
    # Unique counts
    commodities = set(r.commodity_id for r in records)
    markets = set(r.market_id for r in records if r.market_id)
    districts = set(r.district_id for r in records if r.district_id)
    states = set(r.state_id for r in records if r.state_id)
    
    return DataQualityResponse(
        report_date=target_date,
        scope_type=scope_type,
        scope_id=scope_id,
        total_records=len(records),
        live_records=status_counts.get("live", 0),
        cached_records=status_counts.get("cached", 0),
        historical_records=status_counts.get("historical", 0),
        demo_records=status_counts.get("demo", 0),
        unavailable_records=status_counts.get("unavailable", 0),
        error_records=status_counts.get("error", 0),
        avg_data_age_hours=round(avg_age, 1),
        max_data_age_hours=round(max_age, 1),
        commodities_covered=len(commodities),
        markets_covered=len(markets),
        districts_covered=len(districts),
        states_covered=len(states),
        outlier_records=sum(1 for r in records if r.is_outlier),
        duplicate_records=0,  # Would need more complex query
        source_breakdown=source_counts,
        generated_at=datetime.now(timezone.utc),
    )


# =============================================================================
# Statistics & Monitoring
# =============================================================================

@router.get("/stats/overview")
async def get_sync_overview(db: Session = Depends(get_db)):
    """Get sync system overview."""
    # Recent sync stats
    recent_logs = db.query(SyncLog).filter(
        SyncLog.created_at >= datetime.now(timezone.utc) - timedelta(days=7)
    ).all()
    
    total_jobs = len(recent_logs)
    successful = len([l for l in recent_logs if l.status == SyncStatus.SUCCESS])
    failed = len([l for l in recent_logs if l.status == SyncStatus.FAILED])
    partial = len([l for l in recent_logs if l.status == SyncStatus.PARTIAL])
    
    # By sync type
    by_type = {}
    for log in recent_logs:
        t = log.sync_type.value
        if t not in by_type:
            by_type[t] = {"total": 0, "success": 0, "failed": 0}
        by_type[t]["total"] += 1
        if log.status == SyncStatus.SUCCESS:
            by_type[t]["success"] += 1
        elif log.status == SyncStatus.FAILED:
            by_type[t]["failed"] += 1
    
    # Active schedules
    active_schedules = db.query(SyncSchedule).filter(SyncSchedule.is_active == True).count()
    
    # Latest sync per type
    latest_per_type = {}
    for sync_type in SyncType:
        latest = db.query(SyncLog).filter(
            SyncLog.sync_type == sync_type
        ).order_by(desc(SyncLog.created_at)).first()
        if latest:
            latest_per_type[sync_type.value] = {
                "status": latest.status.value,
                "created_at": latest.created_at.isoformat(),
                "records_processed": latest.processed_items,
            }
    
    return {
        "last_7_days": {
            "total_jobs": total_jobs,
            "successful": successful,
            "failed": failed,
            "partial": partial,
            "success_rate": round(successful / total_jobs * 100, 1) if total_jobs > 0 else 0,
        },
        "by_type": by_type,
        "active_schedules": active_schedules,
        "latest_per_type": latest_per_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/market-data/stats")
async def get_market_data_sync_stats(db: Session = Depends(get_db)):
    """Get market data synchronization statistics."""
    # Overall counts
    total = db.query(MarketPrice).count()
    live = db.query(MarketPrice).filter(MarketPrice.status == MarketPriceStatus.LIVE).count()
    cached = db.query(MarketPrice).filter(MarketPrice.status == MarketPriceStatus.CACHED).count()
    historical = db.query(MarketPrice).filter(MarketPrice.status == MarketPriceStatus.HISTORICAL).count()
    demo = db.query(MarketPrice).filter(MarketPrice.status == MarketPriceStatus.DEMO).count()
    unavailable = db.query(MarketPrice).filter(MarketPrice.status == MarketPriceStatus.UNAVAILABLE).count()
    error = db.query(MarketPrice).filter(MarketPrice.status == MarketPriceStatus.ERROR).count()
    
    # Recent freshness
    now = datetime.now(timezone.utc)
    last_24h = db.query(MarketPrice).filter(MarketPrice.fetched_at >= now - timedelta(hours=24)).count()
    last_7d = db.query(MarketPrice).filter(MarketPrice.fetched_at >= now - timedelta(days=7)).count()
    
    # By source
    sources = db.query(MarketPrice.source, func.count(MarketPrice.id)).group_by(MarketPrice.source).all()
    
    # By commodity
    commodities = db.query(
        MarketPrice.commodity_id,
        func.count(MarketPrice.id)
    ).group_by(MarketPrice.commodity_id).order_by(desc(func.count(MarketPrice.id))).limit(10).all()
    
    # Latest sync
    latest_sync = db.query(SyncLog).filter(
        SyncLog.sync_type == SyncType.MARKET_PRICES
    ).order_by(desc(SyncLog.created_at)).first()
    
    return {
        "total_records": total,
        "by_status": {
            "live": live,
            "cached": cached,
            "historical": historical,
            "demo": demo,
            "unavailable": unavailable,
            "error": error,
        },
        "freshness": {
            "last_24h": last_24h,
            "last_7d": last_7d,
        },
        "by_source": {s: c for s, c in sources},
        "top_commodities": [{c: cnt} for c, cnt in commodities],
        "latest_sync": {
            "status": latest_sync.status.value if latest_sync else None,
            "created_at": latest_sync.created_at.isoformat() if latest_sync else None,
            "records_fetched": latest_sync.records_fetched if latest_sync else None,
            "records_added": latest_sync.records_new if latest_sync else None,
        } if latest_sync else None,
        "timestamp": now.isoformat(),
    }


@router.get("/health")
async def sync_health(db: Session = Depends(get_db)):
    """Health check for sync services."""
    pending_jobs = db.query(SyncLog).filter(SyncLog.status.in_([SyncStatus.PENDING, SyncStatus.RUNNING])).count()
    active_schedules = db.query(SyncSchedule).filter(SyncSchedule.is_active == True).count()
    
    return {
        "status": "healthy",
        "pending_jobs": pending_jobs,
        "active_schedules": active_schedules,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }