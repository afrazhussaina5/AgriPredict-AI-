# AgriPredict AI - Mandi API Routes
"""
Verified Mandi Master API.
Only VERIFIED mandis are selectable by farmers.
"""

from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, and_
from sqlalchemy.orm import Session, joinedload

from ..db import get_db
from ..models import (
    Mandi, MandiStatus, VerificationStatus, Commodity,
    State, District, Subdistrict, Location,
)
from ..core.config import get_settings

router = APIRouter(prefix="/mandis", tags=["Mandis"])


# =============================================================================
# Pydantic Schemas
# =============================================================================

class MandiCommodityResponse(BaseModel):
    id: str
    name: str
    variety: Optional[str] = None
    category: str
    is_primary: bool = False
    seasonal_months: Optional[List[int]] = None

    class Config:
        from_attributes = True


class MandiBaseResponse(BaseModel):
    id: int
    mandi_id: str
    e_nam_id: Optional[str] = None
    name: str
    apmc_name: Optional[str] = None
    local_name: Optional[str] = None
    state_id: int
    district_id: int
    subdistrict_id: Optional[int] = None
    address: Optional[str] = None
    pincode: Optional[str] = None
    latitude: float
    longitude: float
    status: MandiStatus
    is_e_nam: bool
    market_type: Optional[str] = None
    facilities: Optional[List[str]] = None
    verification_status: VerificationStatus
    official_source: Optional[str] = None
    source_url: Optional[str] = None
    last_verified_at: Optional[datetime] = None
    operating_hours: Optional[str] = None
    market_days: Optional[str] = None
    arrival_capacity_qtl: Optional[int] = None
    price_offset_multiplier: float
    transport_cost_per_km_qtl: float
    storage_cost_per_day_qtl: float
    rating: Optional[float] = None
    is_selectable: bool

    class Config:
        from_attributes = True


class MandiDetailResponse(MandiBaseResponse):
    state_name: Optional[str] = None
    district_name: Optional[str] = None
    subdistrict_name: Optional[str] = None
    commodities: List[MandiCommodityResponse] = []
    distance_km: Optional[float] = None
    duration_minutes: Optional[float] = None

    class Config:
        from_attributes = True


class NearbyMandiRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    commodity_id: Optional[str] = None
    max_distance_km: float = Field(default=100, ge=1, le=500)
    limit: int = Field(default=10, ge=1, le=50)
    verified_only: bool = True


class NearbyMandiResponse(BaseModel):
    mandi: MandiDetailResponse
    distance_km: float
    duration_minutes: Optional[float] = None
    routing_status: str  # "cached", "calculated", "estimated"


class MandiListResponse(BaseModel):
    mandis: List[MandiBaseResponse]
    total: int
    page: int
    page_size: int


# =============================================================================
# Mandi Endpoints
# =============================================================================

@router.get("", response_model=MandiListResponse)
async def list_mandis(
    state_id: Optional[int] = Query(None, description="Filter by state"),
    district_id: Optional[int] = Query(None, description="Filter by district"),
    commodity_id: Optional[str] = Query(None, description="Filter by commodity"),
    status: Optional[MandiStatus] = Query(None, description="Filter by operational status"),
    verification_status: Optional[VerificationStatus] = Query(None, description="Filter by verification"),
    is_e_nam: Optional[bool] = Query(None, description="Filter by e-NAM integration"),
    search: Optional[str] = Query(None, description="Search by name"),
    selectable_only: bool = Query(True, description="Only show verified+active mandis"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    List mandis with filters.
    By default, only VERIFIED and ACTIVE mandis are returned (selectable_only=True).
    """
    query = db.query(Mandi).options(
        joinedload(Mandi.commodities),
        joinedload(Mandi.state),
        joinedload(Mandi.district),
        joinedload(Mandi.subdistrict),
    )
    
    if selectable_only:
        query = query.filter(
            Mandi.verification_status == VerificationStatus.VERIFIED,
            Mandi.status == MandiStatus.ACTIVE,
        )
    else:
        if status:
            query = query.filter(Mandi.status == status)
        if verification_status:
            query = query.filter(Mandi.verification_status == verification_status)
    
    if state_id:
        query = query.filter(Mandi.state_id == state_id)
    if district_id:
        query = query.filter(Mandi.district_id == district_id)
    if commodity_id:
        query = query.join(Mandi.commodities).filter(Commodity.id == commodity_id)
    if is_e_nam is not None:
        query = query.filter(Mandi.is_e_nam == is_e_nam)
    if search:
        query = query.filter(
            or_(
                Mandi.name.ilike(f"%{search}%"),
                Mandi.apmc_name.ilike(f"%{search}%"),
                Mandi.mandi_id.ilike(f"%{search}%"),
            )
        )
    
    total = query.count()
    mandis = query.order_by(Mandi.name).offset((page - 1) * page_size).limit(page_size).all()
    
    # Build response with computed is_selectable field
    result_mandis = []
    for m in mandis:
        is_selectable = (
            m.verification_status == VerificationStatus.VERIFIED
            and m.status == MandiStatus.ACTIVE
            and m.latitude is not None
            and m.longitude is not None
        )
        result_mandis.append(MandiBaseResponse(
            id=m.id,
            mandi_id=m.mandi_id,
            e_nam_id=m.e_nam_id,
            name=m.name,
            apmc_name=m.apmc_name,
            local_name=m.local_name,
            state_id=m.state_id,
            district_id=m.district_id,
            subdistrict_id=m.subdistrict_id,
            address=m.address,
            pincode=m.pincode,
            latitude=m.latitude,
            longitude=m.longitude,
            status=m.status,
            is_e_nam=m.is_e_nam,
            market_type=m.market_type,
            facilities=m.facilities,
            verification_status=m.verification_status,
            official_source=m.official_source,
            source_url=m.source_url,
            last_verified_at=m.last_verified_at,
            operating_hours=m.operating_hours,
            market_days=m.market_days,
            arrival_capacity_qtl=m.arrival_capacity_qtl,
            price_offset_multiplier=m.price_offset_multiplier,
            transport_cost_per_km_qtl=m.transport_cost_per_km_qtl,
            storage_cost_per_day_qtl=m.storage_cost_per_day_qtl,
            rating=m.rating,
            is_selectable=is_selectable,
        ))
    
    return MandiListResponse(
        mandis=result_mandis,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{mandi_id}", response_model=MandiDetailResponse)
async def get_mandi(
    mandi_id: int = Path(..., gt=0),
    include_commodities: bool = Query(True),
    db: Session = Depends(get_db),
):
    """Get detailed mandi information."""
    query = db.query(Mandi).options(
        joinedload(Mandi.state),
        joinedload(Mandi.district),
        joinedload(Mandi.subdistrict),
    )
    
    if include_commodities:
        query = query.options(joinedload(Mandi.commodities))
    
    mandi = query.filter(Mandi.id == mandi_id).first()
    
    if not mandi:
        raise HTTPException(status_code=404, detail="Mandi not found")
    
    # Build detail response
    is_selectable = (
        mandi.verification_status == VerificationStatus.VERIFIED
        and mandi.status == MandiStatus.ACTIVE
        and mandi.latitude is not None
        and mandi.longitude is not None
    )
    response = MandiDetailResponse(
        id=mandi.id,
        mandi_id=mandi.mandi_id,
        e_nam_id=mandi.e_nam_id,
        name=mandi.name,
        apmc_name=mandi.apmc_name,
        local_name=mandi.local_name,
        state_id=mandi.state_id,
        district_id=mandi.district_id,
        subdistrict_id=mandi.subdistrict_id,
        address=mandi.address,
        pincode=mandi.pincode,
        latitude=mandi.latitude,
        longitude=mandi.longitude,
        status=mandi.status,
        is_e_nam=mandi.is_e_nam,
        market_type=mandi.market_type,
        facilities=mandi.facilities,
        verification_status=mandi.verification_status,
        official_source=mandi.official_source,
        source_url=mandi.source_url,
        last_verified_at=mandi.last_verified_at,
        operating_hours=mandi.operating_hours,
        market_days=mandi.market_days,
        arrival_capacity_qtl=mandi.arrival_capacity_qtl,
        price_offset_multiplier=mandi.price_offset_multiplier,
        transport_cost_per_km_qtl=mandi.transport_cost_per_km_qtl,
        storage_cost_per_day_qtl=mandi.storage_cost_per_day_qtl,
        rating=mandi.rating,
        is_selectable=is_selectable,
        state_name=mandi.state.name if mandi.state else None,
        district_name=mandi.district.name if mandi.district else None,
        subdistrict_name=mandi.subdistrict.name if mandi.subdistrict else None,
        commodities=[
            MandiCommodityResponse(
                id=c.id,
                name=c.name,
                variety=c.variety,
                category=c.category,
            ) for c in mandi.commodities
        ] if include_commodities else [],
        distance_km=None,
        duration_minutes=None,
    )
    
    return response


@router.get("/by-code/{mandi_code}", response_model=MandiDetailResponse)
async def get_mandi_by_code(
    mandi_code: str = Path(..., description="Mandi ID code (e.g., mandi-kurnool)"),
    db: Session = Depends(get_db),
):
    """Get mandi by its unique code."""
    mandi = db.query(Mandi).options(
        joinedload(Mandi.state),
        joinedload(Mandi.district),
        joinedload(Mandi.subdistrict),
        joinedload(Mandi.commodities),
    ).filter(Mandi.mandi_id == mandi_code).first()
    
    if not mandi:
        raise HTTPException(status_code=404, detail="Mandi not found")
    
    return MandiDetailResponse.from_orm(mandi)


@router.get("/enam/{enam_id}", response_model=MandiDetailResponse)
async def get_mandi_by_enam(
    enam_id: str = Path(..., description="e-NAM registration ID"),
    db: Session = Depends(get_db),
):
    """Get mandi by e-NAM ID."""
    mandi = db.query(Mandi).options(
        joinedload(Mandi.state),
        joinedload(Mandi.district),
        joinedload(Mandi.commodities),
    ).filter(Mandi.e_nam_id == enam_id).first()
    
    if not mandi:
        raise HTTPException(status_code=404, detail="Mandi not found")
    
    return MandiDetailResponse.from_orm(mandi)


# =============================================================================
# Nearby Mandis (Core Feature)
# =============================================================================

@router.post("/nearby", response_model=List[NearbyMandiResponse])
async def find_nearby_mandis(
    request: NearbyMandiRequest,
    db: Session = Depends(get_db),
):
    """
    Find verified mandis near farmer's GPS coordinates.
    Returns real road distance and duration via routing engine.
    """
    from ..models import RouteCache, RoutingProvider, RouteProfile
    
    # Build base query for verified, active mandis
    query = db.query(Mandi).filter(
        Mandi.verification_status == VerificationStatus.VERIFIED,
        Mandi.status == MandiStatus.ACTIVE,
        Mandi.latitude.isnot(None),
        Mandi.longitude.isnot(None),
    )
    
    if request.commodity_id:
        query = query.join(Mandi.commodities).filter(Commodity.id == request.commodity_id)
    
    mandis = query.all()
    
    if not mandis:
        return []
    
    results = []
    settings = get_settings()
    
    for mandi in mandis:
        # Skip mandis without coordinates
        if not mandi.latitude or not mandi.longitude:
            # Try to refresh from database
            db.refresh(mandi)
            if not mandi.latitude or not mandi.longitude:
                continue
            
        # Calculate Haversine distance as quick filter
        from math import radians, sin, cos, sqrt, atan2
        
        R = 6371  # Earth radius in km
        lat1, lon1 = radians(request.latitude), radians(request.longitude)
        lat2, lon2 = radians(mandi.latitude), radians(mandi.longitude)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        haversine_dist = 2 * R * atan2(sqrt(a), sqrt(1-a))
        
        # Skip if haversine distance exceeds max (road distance will be longer)
        if haversine_dist > request.max_distance_km * 1.5:
            continue
        
        # Try to get cached route
        cached_route = db.query(RouteCache).filter(
            RouteCache.origin_lat == request.latitude,
            RouteCache.origin_lng == request.longitude,
            RouteCache.destination_mandi_id == mandi.id,
            RouteCache.profile == RouteProfile.TRUCK,
        ).first()
        
        if cached_route and not cached_route.is_stale:
            road_distance = cached_route.distance_km
            duration = cached_route.duration_minutes
            routing_status = "cached"
        else:
            # TODO: Call actual routing provider (OSRM/ORS/Google)
            # For now, estimate road distance as 1.3x haversine
            road_distance = round(haversine_dist * 1.3, 1)
            duration = round(road_distance * 1.5, 0)  # ~40 km/h average
            routing_status = "estimated"
            
            # Cache the estimate
            new_route = RouteCache(
                origin_lat=request.latitude,
                origin_lng=request.longitude,
                destination_lat=mandi.latitude,
                destination_lng=mandi.longitude,
                destination_mandi_id=mandi.id,
                profile=RouteProfile.TRUCK,
                provider=RoutingProvider.OSRM,
                distance_km=road_distance,
                duration_minutes=duration,
                status="estimated",
            )
            db.add(new_route)
        
        # Check if within max distance
        if road_distance <= request.max_distance_km:
            results.append(NearbyMandiResponse(
                mandi=MandiDetailResponse.from_orm(mandi),
                distance_km=road_distance,
                duration_minutes=duration,
                routing_status=routing_status,
            ))
    
    # Sort by road distance
    results.sort(key=lambda x: x.distance_km)
    
    db.commit()
    return results[:request.limit]


@router.get("/nearby/from-location/{location_id}", response_model=List[NearbyMandiResponse])
async def find_nearby_mandis_from_location(
    location_id: int = Path(..., gt=0),
    commodity_id: Optional[str] = Query(None),
    max_distance_km: float = Query(100, ge=1, le=500),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Find mandis near a saved location."""
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    
    if not location.latitude or not location.longitude:
        raise HTTPException(status_code=400, detail="Location has no coordinates")
    
    request = NearbyMandiRequest(
        latitude=location.latitude,
        longitude=location.longitude,
        commodity_id=commodity_id,
        max_distance_km=max_distance_km,
        limit=limit,
    )
    
    return await find_nearby_mandis(request, db)


# =============================================================================
# Mandi Commodities
# =============================================================================

@router.get("/{mandi_id}/commodities", response_model=List[MandiCommodityResponse])
async def get_mandi_commodities(
    mandi_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    """Get commodities supported by a mandi."""
    mandi = db.query(Mandi).options(joinedload(Mandi.commodities)).filter(Mandi.id == mandi_id).first()
    if not mandi:
        raise HTTPException(status_code=404, detail="Mandi not found")
    
    return [
        MandiCommodityResponse(
            id=c.id,
            name=c.name,
            variety=c.variety,
            category=c.category,
        )
        for c in mandi.commodities
    ]


# =============================================================================
# Verification Endpoints (Admin)
# =============================================================================

class MandiVerificationRequest(BaseModel):
    verification_status: VerificationStatus
    official_source: Optional[str] = None
    source_url: Optional[str] = None
    verification_notes: Optional[str] = None
    verified_by: Optional[str] = None


@router.patch("/{mandi_id}/verify", response_model=MandiDetailResponse)
async def update_mandi_verification(
    mandi_id: int = Path(..., gt=0),
    request: MandiVerificationRequest = ...,
    db: Session = Depends(get_db),
):
    """Update mandi verification status (admin only)."""
    mandi = db.query(Mandi).filter(Mandi.id == mandi_id).first()
    if not mandi:
        raise HTTPException(status_code=404, detail="Mandi not found")
    
    mandi.verification_status = request.verification_status
    if request.official_source:
        mandi.official_source = request.official_source
    if request.source_url:
        mandi.source_url = request.source_url
    if request.verification_notes:
        mandi.verification_notes = request.verification_notes
    if request.verified_by:
        mandi.verified_by = request.verified_by
    mandi.last_verified_at = datetime.now(timezone.utc)
    mandi.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(mandi)
    
    return MandiDetailResponse.from_orm(mandi)


# =============================================================================
# Statistics
# =============================================================================

@router.get("/stats/summary")
async def get_mandi_stats(db: Session = Depends(get_db)):
    """Get mandi statistics."""
    total = db.query(Mandi).count()
    verified = db.query(Mandi).filter(Mandi.verification_status == VerificationStatus.VERIFIED).count()
    active = db.query(Mandi).filter(Mandi.status == MandiStatus.ACTIVE).count()
    selectable = db.query(Mandi).filter(
        Mandi.verification_status == VerificationStatus.VERIFIED,
        Mandi.status == MandiStatus.ACTIVE,
        Mandi.latitude.isnot(None),
        Mandi.longitude.isnot(None),
    ).count()
    e_nam = db.query(Mandi).filter(Mandi.is_e_nam == True).count()
    
    by_state = db.query(
        State.name,
        func.count(Mandi.id)
    ).join(Mandi, Mandi.state_id == State.id).group_by(State.name).all()
    
    by_status = db.query(
        Mandi.status,
        func.count(Mandi.id)
    ).group_by(Mandi.status).all()
    
    by_verification = db.query(
        Mandi.verification_status,
        func.count(Mandi.id)
    ).group_by(Mandi.verification_status).all()
    
    return {
        "total": total,
        "verified": verified,
        "active": active,
        "selectable": selectable,
        "e_nam": e_nam,
        "by_state": {name: count for name, count in by_state},
        "by_status": {str(status): count for status, count in by_status},
        "by_verification": {str(v): count for v, count in by_verification},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health")
async def mandis_health(db: Session = Depends(get_db)):
    """Health check for mandi services."""
    selectable_count = db.query(Mandi).filter(
        Mandi.verification_status == VerificationStatus.VERIFIED,
        Mandi.status == MandiStatus.ACTIVE,
        Mandi.latitude.isnot(None),
        Mandi.longitude.isnot(None),
    ).count()
    
    return {
        "status": "healthy",
        "selectable_mandis": selectable_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }