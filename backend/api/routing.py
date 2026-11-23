# AgriPredict AI - Routing API Routes
"""
Real road routing API using OSRM (OpenStreetMap Routing Machine).
Provides accurate road distance and travel time for truck routing.
"""

from datetime import datetime, timezone
from typing import Optional, List, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..services.osrm_service import get_osrm_service, RouteResult, haversine_distance
from ..models import Commodity

router = APIRouter(prefix="/routing", tags=["Routing"])


# =============================================================================
# Pydantic Schemas
# =============================================================================

class RouteRequest(BaseModel):
    origin_latitude: float = Field(..., ge=-90, le=90)
    origin_longitude: float = Field(..., ge=-180, le=180)
    destination_latitude: float = Field(..., ge=-90, le=90)
    destination_longitude: float = Field(..., ge=-180, le=180)
    profile: str = Field(default="truck", pattern="^(car|truck|tractor)$")
    alternatives: bool = False
    steps: bool = True


class RouteTableRequest(BaseModel):
    origins: List[Tuple[float, float]] = Field(..., min_items=1, max_items=100)
    destinations: List[Tuple[float, float]] = Field(..., min_items=1, max_items=100)
    profile: str = Field(default="truck", pattern="^(car|truck|tractor)$")


class RouteResponse(BaseModel):
    distance_km: float
    duration_minutes: float
    duration_traffic_minutes: Optional[float] = None
    geometry: Optional[dict] = None
    steps: Optional[List[dict]] = None
    profile: str
    source: str
    timestamp: str


class RouteTableResponse(BaseModel):
    durations: List[List[float]]  # seconds
    distances: List[List[float]]  # meters
    sources: List[dict]
    destinations: List[dict]


class NearestRoadRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    number: int = Field(default=1, ge=1, le=5)


class NearestRoadResponse(BaseModel):
    latitude: float
    longitude: float
    name: Optional[str] = None
    distance_meters: float


class HaversineRequest(BaseModel):
    origin_latitude: float = Field(..., ge=-90, le=90)
    origin_longitude: float = Field(..., ge=-180, le=180)
    destination_latitude: float = Field(..., ge=-90, le=90)
    destination_longitude: float = Field(..., ge=-180, le=180)


class HaversineResponse(BaseModel):
    haversine_distance_km: float
    estimated_road_distance_km: float
    estimated_duration_minutes: int


# =============================================================================
# Routing API Endpoints
# =============================================================================

router = APIRouter(prefix="/routing", tags=["Routing"])


@router.post("/route", response_model=RouteResponse)
async def get_route(
    request: RouteRequest,
    db: Session = Depends(get_db),
):
    """
    Get road route between two points using OSRM.
    Returns accurate road distance, duration, and optional geometry/steps.
    """
    osrm = get_osrm_service()
    
    try:
        result = await osrm.get_route(
            origin_lat=request.origin_latitude,
            origin_lon=request.origin_longitude,
            dest_lat=request.destination_latitude,
            dest_lon=request.destination_longitude,
            profile=request.profile,
            alternatives=request.alternatives,
            steps=request.steps,
        )
        return RouteResponse(**result.to_dict())
    except Exception as e:
        logger.error(f"Route calculation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Route calculation failed: {str(e)}")


@router.post("/table", response_model=RouteTableResponse)
async def get_distance_table(
    request: RouteTableRequest,
    db: Session = Depends(get_db),
):
    """
    Get distance/duration matrix for multiple origins and destinations.
    Useful for finding nearest mandis from multiple locations.
    """
    osrm = get_osrm_service()
    
    try:
        result = await osrm.get_route_table(
            origins=request.origins,
            destinations=request.destinations,
            profile=request.profile,
        )
        return RouteTableResponse(**result)
    except Exception as e:
        logger.error(f"Distance table calculation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Distance table calculation failed: {str(e)}")


@router.post("/nearest", response_model=NearestRoadResponse)
async def nearest_road(
    request: NearestRoadRequest,
    db: Session = Depends(get_db),
):
    """
    Snap coordinates to nearest road.
    Useful for correcting GPS coordinates to actual road network.
    """
    osrm = get_osrm_service()
    
    try:
        result = await osrm.nearest_road(
            latitude=request.latitude,
            longitude=request.longitude,
            number=request.number,
        )
        return NearestRoadResponse(**result)
    except Exception as e:
        logger.error(f"Nearest road lookup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Nearest road lookup failed: {str(e)}")


@router.post("/haversine", response_model=HaversineResponse)
async def haversine_distance_calc(
    request: HaversineRequest,
    db: Session = Depends(get_db),
):
    """
    Calculate straight-line (Haversine) distance between two points.
    Useful as fallback when OSRM is unavailable.
    """
    from backend.services.osrm_service import haversine_distance, estimate_road_distance, estimate_travel_time
    
    distance = haversine_distance(
        request.origin_latitude,
        request.origin_longitude,
        request.destination_latitude,
        request.destination_longitude,
    )
    
    road_distance = round(distance * 1.3, 1)  # 1.3x factor for roads
    duration = int((distance * 1.3 / 40) * 60)  # 40 km/h average
    
    return HaversineResponse(
        haversine_distance_km=distance,
        estimated_road_distance_km=round(distance * 1.3, 1),
        estimated_duration_minutes=int((distance * 1.3 / 40) * 60),
    )


@router.get("/health")
async def routing_health():
    """Health check for routing service"""
    return {
        "status": "healthy",
        "service": "routing",
        "provider": "osrm",
        "profiles": ["car", "truck", "tractor"],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# =============================================================================
# Net Return Calculation Endpoint
# =============================================================================

class NetReturnRequest(BaseModel):
    commodity_id: str = Field(..., description="Commodity ID (e.g., onion, tomato)")
    quantity_qtl: float = Field(..., gt=0, description="Quantity in quintals")
    grade: str = Field(default="A", pattern="^[ABC]$")
    market_price: float = Field(..., gt=0, description="Market modal price per quintal")
    origin_latitude: float = Field(..., ge=-90, le=90)
    origin_longitude: float = Field(..., ge=-180, le=180)
    destination_latitude: float = Field(..., ge=-90, le=90)
    destination_longitude: float = Field(..., ge=-180, le=180)
    storage_days: int = Field(default=0, ge=0, le=365)
    storage_type: str = Field(default="cold_storage", pattern="^(cold_storage|godown|warehouse)$")
    vehicle_type: str = Field(default="truck_10t")


class NetReturnResponse(BaseModel):
    commodity_id: str
    commodity_name: str
    quantity_qtl: float
    grade: str
    grade_multiplier: float
    market_price_per_qtl: float
    adjusted_price_per_qtl: float
    gross_revenue: float
    transport: dict
    storage: dict
    total_deductions: float
    net_return: float
    net_return_per_qtl: float
    calculated_at: str


@router.post("/net-return", response_model=NetReturnResponse)
async def calculate_net_return(
    request: NetReturnRequest,
    db: Session = Depends(get_db),
):
    """
    Calculate complete net return: Gross Revenue - Transport - Storage.
    Every cost component has explicit source/status.
    """
    from ..models import Commodity, MarketPrice, MarketPriceStatus
    
    commodity = db.query(Commodity).filter(Commodity.id == request.commodity_id).first()
    if not commodity:
        raise HTTPException(status_code=404, detail="Commodity not found")
    
    # Grade-adjusted price
    grade_multiplier = commodity.grade_multipliers.get(request.grade, 1.0) if commodity.grade_multipliers else 1.0
    adjusted_price = round(request.market_price * grade_multiplier, 2)
    
    # Gross revenue
    gross_revenue = round(adjusted_price * request.quantity_qtl, 2)
    
    # Transport cost
    osrm = get_osrm_service()
    route = await osrm.get_route(
        origin_lat=request.origin_latitude,
        origin_lon=request.origin_longitude,
        dest_lat=request.destination_latitude,
        dest_lon=request.destination_longitude,
        profile="truck",
    )
    
    transport_rate = commodity.base_transport_rate_per_km_qtl or 1.8
    
    transport_cost = round(route.distance_km * transport_rate * request.quantity_qtl, 2)
    loading_charge = round(2.0 * request.quantity_qtl, 2)
    unloading_charge = round(2.0 * request.quantity_qtl, 2)
    total_transport = transport_cost + loading_charge + unloading_charge
    
    # Storage cost
    storage_cost = 0
    storage_details = None
    if request.storage_days > 0:
        storage = await osrm.get_storage_cost(
            commodity_id=request.commodity_id,
            quantity_qtl=request.quantity_qtl,
            storage_type=request.storage_type,
            days=request.storage_days,
        )
        storage_cost = storage.total_cost
        storage_details = {
            "days": request.storage_days,
            "storage_type": request.storage_type,
            "rate_per_day_per_qtl": storage.rate_per_day_per_qtl,
            "total_storage_cost": storage_cost,
            "rate_source": storage.rate_source,
            "facility_name": storage.facility_name,
        }
    
    # Net return
    total_deductions = total_transport + storage_cost
    net_return = round(gross_revenue - total_deductions, 2)
    
    return NetReturnResponse(
        commodity_id=request.commodity_id,
        commodity_name=commodity.name if commodity else request.commodity_id,
        quantity_qtl=request.quantity_qtl,
        grade=request.grade,
        grade_multiplier=grade_multiplier,
        market_price_per_qtl=request.market_price,
        adjusted_price_per_qtl=adjusted_price,
        gross_revenue=gross_revenue,
        transport={
            "distance_km": route.distance_km,
            "duration_minutes": route.duration_minutes,
            "rate_per_km_per_qtl": transport_rate,
            "transport_cost": transport_cost,
            "loading_charge": loading_charge,
            "unloading_charge": unloading_charge,
            "total_transport_cost": total_transport,
            "rate_source": "configured",
            "distance_source": "cached" if route.cached else "estimated",
        },
        storage=storage_details,
        total_deductions=total_deductions,
        net_return=net_return,
        net_return_per_qtl=round(net_return / request.quantity_qtl, 2) if request.quantity_qtl > 0 else 0,
        calculated_at=datetime.now(timezone.utc).isoformat(),
    )


# GET versions for simple browser testing
@router.get("/route")
async def get_route_get(
    origin_lat: float = Query(..., ge=-90, le=90),
    origin_lon: float = Query(..., ge=-180, le=180),
    dest_lat: float = Query(..., ge=-90, le=90),
    dest_lon: float = Query(..., ge=-180, le=180),
    profile: str = Query("truck", pattern="^(car|truck|tractor)$"),
    db: Session = Depends(get_db),
):
    """GET version of route calculation"""
    from backend.services.osrm_service import get_osrm_service
    
    try:
        osrm = get_osrm_service()
        result = await osrm.get_route(
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            dest_lat=dest_lat,
            dest_lon=dest_lon,
            profile=profile,
        )
        return RouteResponse(**result.to_dict())
    except Exception as e:
        logger.error(f"Route calculation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Route calculation failed: {str(e)}")


@router.get("/haversine")
async def haversine_get(
    origin_lat: float = Query(..., ge=-90, le=90),
    origin_lon: float = Query(..., ge=-180, le=180),
    dest_lat: float = Query(..., ge=-90, le=90),
    dest_lon: float = Query(..., ge=-180, le=180),
    db: Session = Depends(get_db),
):
    """GET version of Haversine calculation"""
    from backend.services.osrm_service import haversine_distance
    
    distance = haversine_distance(origin_lat, origin_lon, dest_lat, dest_lon)
    road_distance = round(distance * 1.3, 1)
    duration = int((distance * 1.3 / 40) * 60)
    
    return {
        "haversine_distance_km": distance,
        "estimated_road_distance_km": road_distance,
        "estimated_duration_minutes": duration,
    }