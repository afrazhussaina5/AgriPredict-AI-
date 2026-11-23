# AgriPredict AI - Agmarknet API Routes
"""
Real-time mandi price data from Agmarknet Official Portal API.
"""

from datetime import datetime, date, timezone, timedelta
from typing import Optional, List
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import MarketPrice, MarketPriceStatus, Commodity, Mandi, State, District
from ..services.agmarknet_service import get_agmarknet_service, MandiPriceRecord

logger = logging.getLogger("agmarknet")

router = APIRouter(prefix="/agmarknet", tags=["Agmarknet"])


# =============================================================================
# Pydantic Schemas
# =============================================================================

class MandiPriceRecordResponse(BaseModel):
    state: str
    district: str
    market: str
    commodity: str
    variety: str
    grade: str
    arrival_date: date
    min_price: float
    max_price: float
    modal_price: float
    arrival_quantity: Optional[float] = None
    source: str
    source_url: str
    fetched_at: datetime


class AgmarknetFetchRequest(BaseModel):
    state: str = Field(default="Andhra Pradesh")
    district: Optional[str] = None
    commodity: Optional[str] = None
    date: Optional[date] = None


class AgmarknetFetchResponse(BaseModel):
    status: str
    records_fetched: int
    records: List[MandiPriceRecordResponse]
    message: str
    data_date: date
    fetched_at: datetime


class AgmarknetSyncRequest(BaseModel):
    state: str = Field(default="Andhra Pradesh")
    district: Optional[str] = None
    commodity: Optional[str] = None
    date: Optional[date] = None
    max_pages: int = Field(default=10, ge=1, le=50)


class AgmarknetSyncResponse(BaseModel):
    status: str
    records_fetched: int
    records_added: int
    duplicates_skipped: int
    total_records: int
    date_range: str
    message: str


class AgmarknetLatestRequest(BaseModel):
    state: str = Field(default="Andhra Pradesh")
    commodity: Optional[str] = None
    grade: str = Field(default="FAQ")
    limit: int = Field(default=20, ge=1, le=100)
    max_age_days: int = Field(default=7, ge=1, le=30)


# =============================================================================
# Agmarknet API Endpoints
# =============================================================================

router = APIRouter(prefix="/agmarknet", tags=["Agmarknet"])


@router.post("/prices/latest", response_model=List[dict])
async def get_latest_mandi_prices(
    request: AgmarknetLatestRequest,
    db: Session = Depends(get_db),
):
    """
    Get latest available mandi prices from database.
    Falls back to fetching from Agmarknet if data is stale.
    """
    from ..models import MarketPrice, MarketPriceStatus
    from sqlalchemy import func, desc, and_
    
    cutoff_date = date.today() - timedelta(days=request.max_age_days)
    
    query = db.query(MarketPrice).options(
        # joinedload removed for simplicity
    ).filter(
        MarketPrice.arrival_date >= cutoff_date,
        MarketPrice.grade == request.grade,
    )
    
    if request.commodity:
        query = query.filter(MarketPrice.commodity_id == request.commodity)
    
    # Get latest per commodity/market
    from sqlalchemy import func
    subquery = db.query(
        MarketPrice.commodity_id,
        MarketPrice.market_id,
        func.max(MarketPrice.arrival_date).label("max_date")
    ).filter(
        MarketPrice.arrival_date >= cutoff_date,
        MarketPrice.grade == request.grade,
    )
    
    if request.commodity:
        subquery = subquery.filter(MarketPrice.commodity_id == request.commodity)
    
    subquery = subquery.group_by(
        MarketPrice.commodity_id,
        MarketPrice.market_id
    ).subquery()
    
    latest_query = db.query(MarketPrice).join(
        subquery,
        and_(
            MarketPrice.commodity_id == subquery.c.commodity_id,
            MarketPrice.market_id == subquery.c.market_id,
            MarketPrice.arrival_date == subquery.c.max_date
        )
    ).order_by(desc(MarketPrice.arrival_date)).limit(request.limit)
    
    results = latest_query.all()
    
    return [
        {
            "commodity_id": r.commodity_id,
            "commodity_name": r.commodity.name if hasattr(r, 'commodity') and r.commodity else r.commodity_id,
            "market_id": r.market_id,
            "market_name": r.market.name if hasattr(r, 'market') and r.market else None,
            "state": r.state.name if hasattr(r, 'state') and r.state else "",
            "district": r.district.name if hasattr(r, 'district') and r.district else "",
            "modal_price": r.modal_price,
            "min_price": r.min_price,
            "max_price": r.max_price,
            "arrival_date": r.arrival_date.isoformat(),
            "arrival_quantity": r.arrival_quantity,
            "grade": r.grade,
            "status": r.status.value,
            "source": r.source,
            "fetched_at": r.fetched_at.isoformat(),
            "days_old": (date.today() - r.arrival_date).days,
        }
        for r in results
    ]


@router.post("/prices/fetch", response_model=AgmarknetFetchResponse)
async def fetch_live_prices(
    request: AgmarknetFetchRequest = None,
    db: Session = Depends(get_db),
):
    """
    Fetch live mandi prices from Agmarknet Official Portal.
    """
    if request is None:
        request = AgmarknetFetchRequest()
    
    agmarknet = get_agmarknet_service()
    
    try:
        records = await agmarknet.fetch_latest_prices(
            state=request.state,
            district=request.district,
            commodity=request.commodity,
            arrival_date=request.date,
        )
        
        if not records:
            return AgmarknetFetchResponse(
                status="no_data",
                records_fetched=0,
                records=[],
                message=f"No data found for {request.state} on {request.date or date.today()}",
                data_date=request.date or date.today(),
                fetched_at=datetime.now(timezone.utc),
            )
        
        # Convert to response format
        record_responses = [MandiPriceRecordResponse(**r.to_dict()) for r in records]
        
        return AgmarknetFetchResponse(
            status="success",
            records_fetched=len(records),
            records=record_responses,
            message=f"Successfully fetched {len(records)} records from Agmarknet",
            data_date=records[0].arrival_date if records else date.today(),
            fetched_at=datetime.now(timezone.utc),
        )
        
    except Exception as e:
        logger.error(f"Agmarknet fetch failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch from Agmarknet: {str(e)}")


@router.post("/prices/sync", response_model=AgmarknetSyncResponse)
async def sync_mandi_prices(
    request: AgmarknetSyncRequest = None,
    db: Session = Depends(get_db),
):
    """
    Sync mandi prices from Agmarknet to local database.
    Fetches all pages and updates local historical database.
    """
    if request is None:
        request = AgmarknetSyncRequest()
    
    agmarknet = get_agmarknet_service()
    
    try:
        all_records = []
        current_date = request.date or (date.today() - timedelta(days=1))
        
        # Fetch for multiple dates (lookback period)
        for i in range(request.max_pages):
            fetch_date = current_date - timedelta(days=i)
            records = await get_agmarknet_service().fetch_latest_prices(
                state=request.state,
                district=request.district,
                commodity=request.commodity,
                arrival_date=fetch_date,
            )
            
            if records:
                all_records.extend(records)
                # If we got data, we can stop (latest available)
                if i == 0:
                    break
        
        if not all_records:
            return AgmarknetSyncResponse(
                status="no_data",
                records_fetched=0,
                records_added=0,
                duplicates_skipped=0,
                total_records=0,
                date_range="N/A",
                message=f"No data found for {request.state} in the last {request.max_pages} days",
            )
        
        # Store in database using existing data processor
        from ..services.data_processor import normalize_market_records, update_market_history
        
        # Convert records to raw format for processor
        raw_records = [r.to_dict() for r in all_records]
        
        # Convert dict keys to match expected format
        raw_records_formatted = []
        for r in raw_records:
            raw_records_formatted.append({
                "State": r["state"],
                "District": r["district"],
                "Market": r["market"],
                "Commodity": r["commodity"],
                "Variety": r["variety"],
                "Grade": r["grade"],
                "Arrival_Date": r["arrival_date"],
                "Min_Price": r["min_price"],
                "Max_Price": r["max_price"],
                "Modal_Price": r["modal_price"],
            })
        
        # Update history
        update_result = update_market_history(raw_records_formatted)
        
        return AgmarknetSyncResponse(
            status=update_result.get("status", "success"),
            records_fetched=len(all_records),
            records_added=update_result.get("records_added", 0),
            duplicates_skipped=update_result.get("duplicates_skipped", 0),
            total_records=update_result.get("total_records", 0),
            date_range=update_result.get("date_range", "N/A"),
            message=update_result.get("message", "Sync completed"),
        )
        
    except Exception as e:
        logger.error(f"Agmarknet sync failed: {e}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.get("/markets", response_model=List[dict])
async def get_markets(
    state: str = Query("Andhra Pradesh"),
    district: Optional[str] = None,
    commodity: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Get list of markets/mandis from Agmarknet for a state.
    """
    agmarknet = get_agmarknet_service()
    
    try:
        # Get markets from database
        from ..models import Mandi, MandiStatus, VerificationStatus, Commodity
        
        query = db.query(Mandi).filter(
            Mandi.verification_status == "verified",
            Mandi.status == "active",
        )
        
        if district:
            query = query.filter(Mandi.district_id == district)
        else:
            # Filter by state
            from ..models import State
            state_obj = db.query(State).filter(State.name == state).first()
            if state_obj:
                query = query.filter(Mandi.state_id == state_obj.id)
        
        if commodity:
            query = query.join(Mandi.commodities).filter(Commodity.id == commodity)
        
        mandis = query.order_by(Mandi.name).all()
        
        return [
            {
                "id": m.id,
                "mandi_id": m.mandi_id,
                "name": m.name,
                "apmc_name": m.apmc_name,
                "state": m.state.name if m.state else "",
                "district": m.district.name if m.district else "",
                "latitude": m.latitude,
                "longitude": m.longitude,
                "pincode": m.pincode,
                "is_e_nam": m.is_e_nam,
                "facilities": m.facilities,
                "price_offset_multiplier": m.price_offset_multiplier,
                "transport_cost_per_km_qtl": m.transport_cost_per_km_qtl,
                "storage_cost_per_day_qtl": m.storage_cost_per_day_qtl,
            }
            for m in mandis
        ]
        
    except Exception as e:
        logger.error(f"Failed to get markets: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get markets: {str(e)}")


@router.get("/commodities", response_model=List[dict])
async def get_commodities(
    state: str = Query("Andhra Pradesh"),
    db: Session = Depends(get_db),
):
    """
    Get list of commodities available in a state from Agmarknet.
    """
    # For now, return commodities from our database that are active
    from ..models import Commodity
    
    commodities = db.query(Commodity).order_by(Commodity.name).all()
    
    return [
        {
            "id": c.id,
            "name": c.name,
            "variety": c.variety,
            "category": c.category,
            "icon": c.icon,
            "unit": c.unit,
            "has_ml_model": c.has_ml_model,
            "base_transport_rate_per_km_qtl": c.base_transport_rate_per_km_qtl,
            "storage_cost_per_day_qtl": c.storage_cost_per_day_qtl,
        }
        for c in commodities
    ]


@router.get("/health")
async def agmarknet_health(db: Session = Depends(get_db)):
    """Health check for Agmarknet service"""
    # Test database connectivity
    try:
        from ..models import MarketPrice
        count = db.query(MarketPrice).count()
        
        # Test Agmarknet connectivity
        agmarknet = get_agmarknet_service()
        
        return {
            "status": "healthy",
            "service": "agmarknet",
            "database_records": count,
            "agmarknet_available": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Agmarknet health check failed: {e}")
        return {
            "status": "degraded",
            "service": "agmarknet",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }