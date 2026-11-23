# AgriPredict AI - Market Data API Routes
"""
Government market price data with full traceability.
Statuses: LIVE, CACHED, HISTORICAL, DEMO, UNAVAILABLE, ERROR
"""

from datetime import datetime, date, timezone, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, Field
from sqlalchemy import func, and_, or_, desc
from sqlalchemy.orm import Session, joinedload

from ..db import get_db
from ..models import (
    MarketPrice, MarketPriceStatus, HistoricalPrice,
    MarketPriceFetchLog,
    Commodity, Mandi, State, District,
)
from ..services.market_api import fetch_market_data, fetch_all_market_data, get_api_config
from ..services.data_processor import normalize_market_records, update_market_history

router = APIRouter(prefix="/market-data", tags=["Market Data"])


# =============================================================================
# Pydantic Schemas
# =============================================================================

class MarketPriceResponse(BaseModel):
    id: int
    state_id: int
    district_id: int
    market_id: Optional[int] = None
    commodity_id: str
    variety: Optional[str] = None
    grade: str
    arrival_date: date
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    modal_price: float
    arrival_quantity: Optional[float] = None
    status: MarketPriceStatus
    source: str
    source_url: Optional[str] = None
    fetched_at: datetime
    quality_score: Optional[float] = None

    class Config:
        from_attributes = True


class MarketPriceDetailResponse(MarketPriceResponse):
    state_name: Optional[str] = None
    district_name: Optional[str] = None
    market_name: Optional[str] = None
    commodity_name: Optional[str] = None
    price_spread: Optional[float] = None
    price_spread_pct: Optional[float] = None

    class Config:
        from_attributes = True


class MarketPriceListResponse(BaseModel):
    records: List[MarketPriceResponse]
    total: int
    page: int
    page_size: int
    data_status: str  # Overall status of this response
    last_updated: datetime


class LatestPriceResponse(BaseModel):
    commodity_id: str
    commodity_name: str
    market_id: Optional[int] = None
    market_name: Optional[str] = None
    state: str
    district: str
    modal_price: float
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    arrival_date: date
    arrival_quantity: Optional[float] = None
    grade: str
    status: MarketPriceStatus
    source: str
    fetched_at: datetime
    days_old: int


class PriceTrendPoint(BaseModel):
    date: date
    modal_price: float
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    arrival_quantity: Optional[float] = None
    status: MarketPriceStatus


class PriceTrendResponse(BaseModel):
    commodity_id: str
    commodity_name: str
    market_id: Optional[int] = None
    market_name: Optional[str] = None
    state: str
    district: str
    grade: str
    variety: Optional[str] = None
    data_points: List[PriceTrendPoint]
    period_days: int
    data_status: str
    earliest_date: Optional[date] = None
    latest_date: Optional[date] = None


class MarketDataSyncRequest(BaseModel):
    state: Optional[str] = None
    district: Optional[str] = None
    commodity: Optional[str] = None
    arrival_date: Optional[date] = None
    limit: int = Field(default=100, ge=1, le=10000)
    max_pages: int = Field(default=10, ge=1, le=100)


class MarketDataSyncResponse(BaseModel):
    status: str
    data_source: str
    records_fetched: int
    records_added: int
    records_updated: int
    duplicates_skipped: int
    total_records: int
    date_range: str
    last_updated: datetime
    message: str


# =============================================================================
# Market Price Endpoints
# =============================================================================

@router.get("", response_model=MarketPriceListResponse)
async def get_market_prices(
    state_id: Optional[int] = Query(None),
    district_id: Optional[int] = Query(None),
    market_id: Optional[int] = Query(None),
    commodity_id: Optional[str] = Query(None),
    variety: Optional[str] = Query(None),
    grade: Optional[str] = Query(None),
    arrival_date: Optional[date] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    status: Optional[MarketPriceStatus] = Query(None),
    source: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """
    Get market price records with filters.
    Returns records with explicit data source status.
    """
    query = db.query(MarketPrice).options(
        joinedload(MarketPrice.state),
        joinedload(MarketPrice.district),
        joinedload(MarketPrice.market),
        joinedload(MarketPrice.commodity),
    )
    
    if state_id:
        query = query.filter(MarketPrice.state_id == state_id)
    if district_id:
        query = query.filter(MarketPrice.district_id == district_id)
    if market_id:
        query = query.filter(MarketPrice.market_id == market_id)
    if commodity_id:
        query = query.filter(MarketPrice.commodity_id == commodity_id)
    if variety:
        query = query.filter(MarketPrice.variety.ilike(f"%{variety}%"))
    if grade:
        query = query.filter(MarketPrice.grade == grade)
    if arrival_date:
        query = query.filter(MarketPrice.arrival_date == arrival_date)
    if date_from:
        query = query.filter(MarketPrice.arrival_date >= date_from)
    if date_to:
        query = query.filter(MarketPrice.arrival_date <= date_to)
    if status:
        query = query.filter(MarketPrice.status == status)
    if source:
        query = query.filter(MarketPrice.source.ilike(f"%{source}%"))
    
    # Default sort: newest arrival date first
    query = query.order_by(desc(MarketPrice.arrival_date), desc(MarketPrice.fetched_at))
    
    total = query.count()
    records = query.offset((page - 1) * page_size).limit(page_size).all()
    
    # Determine overall data status
    if records:
        statuses = [r.status for r in records]
        if all(s == MarketPriceStatus.LIVE for s in statuses):
            data_status = "LIVE"
        elif any(s == MarketPriceStatus.LIVE for s in statuses):
            data_status = "MIXED_LIVE"
        elif all(s == MarketPriceStatus.CACHED for s in statuses):
            data_status = "CACHED"
        elif all(s == MarketPriceStatus.HISTORICAL for s in statuses):
            data_status = "HISTORICAL"
        elif all(s == MarketPriceStatus.DEMO for s in statuses):
            data_status = "DEMO"
        else:
            data_status = "MIXED"
    else:
        data_status = "UNAVAILABLE"
    
    return MarketPriceListResponse(
        records=records,
        total=total,
        page=page,
        page_size=page_size,
        data_status=data_status,
        last_updated=datetime.now(timezone.utc),
    )


@router.get("/latest", response_model=List[LatestPriceResponse])
async def get_latest_prices(
    commodity_id: Optional[str] = Query(None),
    state_id: Optional[int] = Query(None),
    district_id: Optional[int] = Query(None),
    grade: str = Query("FAQ"),
    limit: int = Query(20, ge=1, le=100),
    max_age_days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db),
):
    """
    Get latest available price for each commodity/market combination.
    Returns the most recent record within max_age_days.
    """
    cutoff_date = date.today() - timedelta(days=max_age_days)
    
    query = db.query(MarketPrice).options(
        joinedload(MarketPrice.state),
        joinedload(MarketPrice.district),
        joinedload(MarketPrice.market),
        joinedload(MarketPrice.commodity),
    ).filter(
        MarketPrice.arrival_date >= cutoff_date,
        MarketPrice.grade == grade,
    )
    
    if commodity_id:
        query = query.filter(MarketPrice.commodity_id == commodity_id)
    if state_id:
        query = query.filter(MarketPrice.state_id == state_id)
    if district_id:
        query = query.filter(MarketPrice.district_id == district_id)
    
    # Get latest per commodity/market
    subquery = query.with_entities(
        MarketPrice.commodity_id,
        MarketPrice.market_id,
        func.max(MarketPrice.arrival_date).label("max_date")
    ).group_by(
        MarketPrice.commodity_id,
        MarketPrice.market_id
    ).subquery()
    
    latest_query = query.join(
        subquery,
        and_(
            MarketPrice.commodity_id == subquery.c.commodity_id,
            MarketPrice.market_id == subquery.c.market_id,
            MarketPrice.arrival_date == subquery.c.max_date
        )
    ).order_by(desc(MarketPrice.arrival_date)).limit(limit)
    
    results = latest_query.all()
    
    return [
        LatestPriceResponse(
            commodity_id=r.commodity_id,
            commodity_name=r.commodity.name if r.commodity else r.commodity_id,
            market_id=r.market_id,
            market_name=r.market.name if r.market else None,
            state=r.state.name if r.state else "",
            district=r.district.name if r.district else "",
            modal_price=r.modal_price,
            min_price=r.min_price,
            max_price=r.max_price,
            arrival_date=r.arrival_date,
            arrival_quantity=r.arrival_quantity,
            grade=r.grade,
            status=r.status,
            source=r.source,
            fetched_at=r.fetched_at,
            days_old=(date.today() - r.arrival_date).days,
        )
        for r in results
    ]


@router.get("/trend", response_model=PriceTrendResponse)
async def get_price_trend(
    commodity_id: str = Query(..., description="Commodity ID"),
    state_id: Optional[int] = Query(None),
    district_id: Optional[int] = Query(None),
    market_id: Optional[int] = Query(None),
    variety: Optional[str] = Query(None),
    grade: str = Query("FAQ"),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """
    Get price trend for a commodity over specified period.
    Returns time series with data source status for each point.
    """
    cutoff_date = date.today() - timedelta(days=days)
    
    query = db.query(MarketPrice).options(
        joinedload(MarketPrice.state),
        joinedload(MarketPrice.district),
        joinedload(MarketPrice.market),
        joinedload(MarketPrice.commodity),
    ).filter(
        MarketPrice.commodity_id == commodity_id,
        MarketPrice.arrival_date >= cutoff_date,
        MarketPrice.grade == grade,
    )
    
    if variety:
        query = query.filter(MarketPrice.variety == variety)
    if state_id:
        query = query.filter(MarketPrice.state_id == state_id)
    if district_id:
        query = query.filter(MarketPrice.district_id == district_id)
    if market_id:
        query = query.filter(MarketPrice.market_id == market_id)
    
    records = query.order_by(MarketPrice.arrival_date).all()
    
    if not records:
        raise HTTPException(status_code=404, detail="No price data found for the given criteria")
    
    # Determine market/location info from first record
    first = records[0]
    
    data_points = [
        PriceTrendPoint(
            date=r.arrival_date,
            modal_price=r.modal_price,
            min_price=r.min_price,
            max_price=r.max_price,
            arrival_quantity=r.arrival_quantity,
            status=r.status,
        )
        for r in records
    ]
    
    # Overall data status
    statuses = [r.status for r in records]
    if all(s == MarketPriceStatus.LIVE for s in statuses):
        data_status = "LIVE"
    elif any(s == MarketPriceStatus.LIVE for s in statuses):
        data_status = "MIXED_LIVE"
    elif all(s == MarketPriceStatus.CACHED for s in statuses):
        data_status = "CACHED"
    elif all(s == MarketPriceStatus.HISTORICAL for s in statuses):
        data_status = "HISTORICAL"
    elif all(s == MarketPriceStatus.DEMO for s in statuses):
        data_status = "DEMO"
    else:
        data_status = "MIXED"
    
    return PriceTrendResponse(
        commodity_id=commodity_id,
        commodity_name=first.commodity.name if first.commodity else commodity_id,
        market_id=first.market_id,
        market_name=first.market.name if first.market else None,
        state=first.state.name if first.state else "",
        district=first.district.name if first.district else "",
        grade=grade,
        variety=variety,
        data_points=data_points,
        period_days=days,
        data_status=data_status,
        earliest_date=records[0].arrival_date if records else None,
        latest_date=records[-1].arrival_date if records else None,
    )


@router.get("/historical/aggregated", response_model=List[dict])
async def get_historical_aggregates(
    commodity_id: str = Query(...),
    state_id: Optional[int] = Query(None),
    district_id: Optional[int] = Query(None),
    market_id: Optional[int] = Query(None),
    variety: Optional[str] = Query(None),
    grade: Optional[str] = Query(None),
    period_type: str = Query("monthly", pattern="^(daily|weekly|monthly|seasonal|annual)$"),
    limit: int = Query(24, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Get pre-computed historical price aggregates for analytics.
    """
    query = db.query(HistoricalPrice).filter(
        HistoricalPrice.commodity_id == commodity_id,
        HistoricalPrice.period_type == period_type,
    )
    
    if state_id:
        query = query.filter(HistoricalPrice.state_id == state_id)
    if district_id:
        query = query.filter(HistoricalPrice.district_id == district_id)
    if market_id:
        query = query.filter(HistoricalPrice.market_id == market_id)
    if variety:
        query = query.filter(HistoricalPrice.variety == variety)
    if grade:
        query = query.filter(HistoricalPrice.grade == grade)
    
    records = query.order_by(desc(HistoricalPrice.period_start)).limit(limit).all()
    
    return [
        {
            "period_start": r.period_start,
            "period_end": r.period_end,
            "period_type": r.period_type,
            "avg_modal_price": r.avg_modal_price,
            "min_modal_price": r.min_modal_price,
            "max_modal_price": r.max_modal_price,
            "median_modal_price": r.median_modal_price,
            "std_dev_price": r.std_dev_price,
            "total_arrivals": r.total_arrivals,
            "avg_daily_arrivals": r.avg_daily_arrivals,
            "num_records": r.num_records,
            "price_trend": r.price_trend,
            "trend_strength": r.trend_strength,
            "volatility_index": r.volatility_index,
            "data_completeness": r.data_completeness,
        }
        for r in records
    ]


# =============================================================================
# Live Government API Endpoints
# =============================================================================

@router.get("/live", response_model=MarketPriceListResponse)
async def get_live_market_data(
    state: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    commodity: Optional[str] = Query(None),
    arrival_date: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Fetch live market data from government API.
    Falls back to cached/historical data if API unavailable.
    """
    # Try live API first
    live_res = fetch_market_data(
        state=state,
        district=district,
        commodity=commodity,
        arrival_date=arrival_date,
        limit=limit,
        offset=offset,
    )
    
    if live_res["status"] == "success" and live_res["records"]:
        df_clean = normalize_market_records(live_res["records"])
        records_list = df_clean.to_dict(orient="records")
        
        return MarketPriceListResponse(
            records=records_list,
            total_records=len(records_list),
            total_available=live_res.get("total", len(records_list)),
            offset=offset,
            limit=limit,
            last_updated=live_res.get("last_updated", datetime.now(timezone.utc).isoformat()),
            data_source="live_api",
            message="Live market data successfully fetched from external Government API."
        )
    
    # Fallback to cached data
    from ..services.data_processor import load_market_history
    cached_df = load_market_history(
        state=state,
        district=district,
        commodity=commodity,
        arrival_date=arrival_date,
        limit=limit,
    )
    
    if not cached_df.empty:
        cached_records = cached_df.to_dict(orient="records")
        return MarketPriceListResponse(
            records=cached_records,
            total_records=len(cached_records),
            total_available=len(cached_records),
            offset=offset,
            limit=limit,
            last_updated=datetime.now(timezone.utc).isoformat(),
            data_source="cached_data",
            message="Returned from local persistent market history dataset."
        )
    
    # Final fallback - return empty with UNAVAILABLE status
    return MarketPriceListResponse(
        records=[],
        total=0,
        page=1,
        page_size=limit,
        data_status="UNAVAILABLE",
        last_updated=datetime.now(timezone.utc),
    )


@router.post("/sync", response_model=MarketDataSyncResponse)
async def sync_market_data(
    request: MarketDataSyncRequest = None,
    db: Session = Depends(get_db),
):
    """
    Trigger synchronization of market data from government API.
    Fetches all pages and updates local historical database.
    """
    if request is None:
        request = MarketDataSyncRequest()
    
    api_url, api_key = get_api_config()
    if not api_url or not api_key:
        return MarketDataSyncResponse(
            status="unconfigured",
            data_source="unconfigured",
            records_fetched=0,
            records_added=0,
            records_updated=0,
            duplicates_skipped=0,
            total_records=0,
            date_range="N/A",
            last_updated=datetime.now(timezone.utc).isoformat(),
            message="Government Mandi API URL or Key is not configured in .env."
        )
    
    # Fetch all pages
    fetch_result = fetch_all_market_data(
        state=request.state,
        district=request.district,
        commodity=request.commodity,
        arrival_date=request.arrival_date.isoformat() if request.arrival_date else None,
        limit=request.limit,
        max_pages=request.max_pages,
    )
    
    if fetch_result["status"] != "success" or not fetch_result["records"]:
        return MarketDataSyncResponse(
            status="error",
            data_source="live_api",
            records_fetched=0,
            records_added=0,
            records_updated=0,
            duplicates_skipped=0,
            total_records=0,
            date_range="N/A",
            last_updated=datetime.now(timezone.utc).isoformat(),
            message=fetch_result.get("message", "Failed to fetch records from Government Mandi API.")
        )
    
    # Update local history
    update_res = update_market_history(fetch_result["records"])
    update_res["data_source"] = "live_api"
    
    return MarketDataSyncResponse(**update_res)


@router.get("/sync/status", response_model=List[dict])
async def get_sync_status(
    sync_type: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get recent sync job statuses."""
    query = db.query(MarketPriceFetchLog)
    
    if sync_type:
        query = query.filter(MarketPriceFetchLog.source == sync_type)
    
    logs = query.order_by(desc(MarketPriceFetchLog.created_at)).limit(limit).all()
    
    return [
        {
            "id": log.id,
            "status": log.status,
            "records_fetched": log.records_fetched,
            "records_new": log.records_new,
            "records_updated": log.records_updated,
            "records_skipped": log.records_skipped,
            "total_available": log.total_available,
            "error_message": log.error_message,
            "response_time_ms": log.response_time_ms,
            "source": log.source,
            "requested_by": log.requested_by,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]


# =============================================================================
# Data Quality Endpoints
# =============================================================================

@router.get("/quality/report")
async def get_data_quality_report(
    scope_type: str = Query("national", pattern="^(national|state|district|market|commodity)$"),
    scope_id: Optional[str] = Query(None),
    report_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    """Get data quality metrics."""
    from ..models import DataQualityReport
    
    target_date = report_date or date.today()
    
    query = db.query(DataQualityReport).filter(
        DataQualityReport.report_date == target_date,
        DataQualityReport.scope_type == scope_type,
    )
    
    if scope_id:
        query = query.filter(DataQualityReport.scope_id == scope_id)
    
    report = query.first()
    
    if not report:
        # Generate on-the-fly if not pre-computed
        return await generate_quality_report(scope_type, scope_id, target_date, db)
    
    return {
        "report_date": report.report_date.isoformat(),
        "scope_type": report.scope_type,
        "scope_id": report.scope_id,
        "total_records": report.total_records,
        "live_records": report.live_records,
        "cached_records": report.cached_records,
        "historical_records": report.historical_records,
        "demo_records": report.demo_records,
        "unavailable_records": report.unavailable_records,
        "error_records": report.error_records,
        "avg_data_age_hours": report.avg_data_age_hours,
        "max_data_age_hours": report.max_data_age_hours,
        "commodities_covered": report.commodities_covered,
        "markets_covered": report.markets_covered,
        "districts_covered": report.districts_covered,
        "states_covered": report.states_covered,
        "outlier_records": report.outlier_records,
        "duplicate_records": report.duplicate_records,
        "source_breakdown": report.source_breakdown,
        "generated_at": report.generated_at.isoformat(),
    }


async def generate_quality_report(scope_type: str, scope_id: Optional[str], target_date: date, db: Session) -> dict:
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
        return {"error": "No data for scope", "scope_type": scope_type, "scope_id": scope_id}
    
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
    
    return {
        "report_date": target_date.isoformat(),
        "scope_type": scope_type,
        "scope_id": scope_id,
        "total_records": len(records),
        "status_breakdown": status_counts,
        "source_breakdown": source_counts,
        "avg_data_age_hours": round(avg_age, 1),
        "max_data_age_hours": round(max_age, 1),
        "commodities_covered": len(set(r.commodity_id for r in records)),
        "markets_covered": len(set(r.market_id for r in records if r.market_id)),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": "Generated on-demand, not persisted",
    }


@router.get("/health")
async def market_data_health(db: Session = Depends(get_db)):
    """Health check for market data services."""
    total = db.query(MarketPrice).count()
    live = db.query(MarketPrice).filter(MarketPrice.status == MarketPriceStatus.LIVE).count()
    cached = db.query(MarketPrice).filter(MarketPrice.status == MarketPriceStatus.CACHED).count()
    historical = db.query(MarketPrice).filter(MarketPrice.status == MarketPriceStatus.HISTORICAL).count()
    unavailable = db.query(MarketPrice).filter(MarketPrice.status == MarketPriceStatus.UNAVAILABLE).count()
    
    latest_fetch = db.query(MarketPriceFetchLog).order_by(desc(MarketPriceFetchLog.created_at)).first()
    
    return {
        "status": "healthy",
        "total_records": total,
        "live_records": live,
        "cached_records": cached,
        "historical_records": historical,
        "unavailable_records": unavailable,
        "latest_sync": latest_fetch.created_at.isoformat() if latest_fetch else None,
        "latest_sync_status": latest_fetch.status if latest_fetch else None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }