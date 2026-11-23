# AgriPredict AI - Geolocation API Routes
"""
Real-time location detection API using Browser Geolocation + Nominatim reverse geocoding.
"""

from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..services.geolocation_service import get_geolocation_service, LocationInfo

router = APIRouter(prefix="/locations", tags=["Locations"])


# =============================================================================
# Pydantic Schemas
# =============================================================================

class ReverseGeocodeRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90, description="Latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude")


class ForwardGeocodeRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=200, description="Address or place query")


class PincodeRequest(BaseModel):
    pincode: str = Field(..., pattern=r"^\d{6}$", description="6-digit Indian pincode")


class LocationSearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=200, description="Search query")


class LocationResponse(BaseModel):
    latitude: float
    longitude: float
    state: str
    district: str
    subdistrict: Optional[str] = None
    city: Optional[str] = None
    village: Optional[str] = None
    pincode: Optional[str] = None
    formatted_address: str
    confidence: float
    source: str
    timestamp: str


class LocationSearchResponse(BaseModel):
    query: str
    results: List[LocationInfo]
    total: int


# =============================================================================
# Location API Endpoints
# =============================================================================

@router.post("/reverse", response_model=LocationResponse)
async def reverse_geocode(
    request: ReverseGeocodeRequest,
    db: Session = Depends(get_db),
):
    """
    Reverse geocode latitude/longitude to full location details.
    Uses Nominatim (OpenStreetMap) reverse geocoding with caching.
    """
    service = get_geolocation_service()
    
    try:
        location = await service.reverse_geocode(request.latitude, request.longitude)
        return LocationResponse(**location.to_dict())
    except Exception as e:
        logger.error(f"Reverse geocoding failed: {e}")
        raise HTTPException(status_code=500, detail=f"Reverse geocoding failed: {str(e)}")


@router.post("/forward", response_model=List[LocationInfo])
async def forward_geocode(
    request: ForwardGeocodeRequest,
    db: Session = Depends(get_db),
):
    """
    Forward geocode an address/query to coordinates.
    Returns up to 5 matching locations.
    """
    service = get_geolocation_service()
    
    try:
        results = await service.forward_geocode(request.query)
        return [LocationInfo(**r.to_dict()) for r in results]
    except Exception as e:
        logger.error(f"Forward geocoding failed: {e}")
        raise HTTPException(status_code=500, detail=f"Forward geocoding failed: {str(e)}")


@router.get("/pincode/{pincode}", response_model=LocationResponse)
async def get_location_from_pincode(
    pincode: str = Path(..., pattern=r"^\d{6}$"),
    db: Session = Depends(get_db),
):
    """
    Get location details from 6-digit Indian pincode.
    """
    service = get_geolocation_service()
    
    try:
        location = await service.get_location_from_pincode(pincode)
        if not location:
            raise HTTPException(status_code=404, detail="Location not found for pincode")
        return LocationResponse(**location.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pincode lookup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Pincode lookup failed: {str(e)}")


@router.post("/search", response_model=LocationSearchResponse)
async def search_locations(
    request: LocationSearchRequest,
    db: Session = Depends(get_db),
):
    """
    Search locations by query string.
    Returns up to 5 matching locations with full hierarchy.
    """
    service = get_geolocation_service()
    
    try:
        results = await service.forward_geocode(request.query)
        return LocationSearchResponse(
            query=request.query,
            results=[LocationInfo(**r.to_dict()) for r in results],
            total=len(results)
        )
    except Exception as e:
        logger.error(f"Location search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Location search failed: {str(e)}")


@router.post("/full", response_model=LocationInfo)
async def get_full_location(
    request: Optional[ReverseGeocodeRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Get complete location hierarchy for current user position.
    If latitude/longitude not provided, uses browser geolocation via frontend.
    """
    if request:
        latitude = request.latitude
        longitude = request.longitude
    else:
        # Frontend should call this with coordinates from browser geolocation
        raise HTTPException(status_code=400, detail="Latitude/longitude required")
    
    service = get_geolocation_service()
    
    try:
        location = await service.reverse_geocode(latitude, longitude)
        return LocationInfo(**location.to_dict())
    except Exception as e:
        logger.error(f"Full location lookup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Location lookup failed: {str(e)}")


@router.get("/health")
async def geolocation_health():
    """Health check for geolocation service"""
    return {
        "status": "healthy",
        "service": "geolocation",
        "provider": "nominatim",
        "cache_size": len(get_geolocation_service()._cache),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# Alias for backward compatibility
@router.get("/reverse")
async def reverse_geocode_get(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    db: Session = Depends(get_db),
):
    """GET version of reverse geocode for simple browser requests"""
    service = get_geolocation_service()
    
    try:
        location = await service.reverse_geocode(latitude, longitude)
        return LocationResponse(**location.to_dict())
    except Exception as e:
        logger.error(f"Reverse geocoding failed: {e}")
        raise HTTPException(status_code=500, detail=f"Reverse geocoding failed: {str(e)}")


@router.get("/forward")
async def forward_geocode_get(
    q: str = Query(..., min_length=2, description="Search query"),
    db: Session = Depends(get_db),
):
    """GET version of forward geocode"""
    service = get_geolocation_service()
    
    try:
        results = await service.forward_geocode(q)
        return {"query": q, "results": [r.to_dict() for r in results], "total": len(results)}
    except Exception as e:
        logger.error(f"Forward geocoding failed: {e}")
        raise HTTPException(status_code=500, detail=f"Forward geocoding failed: {str(e)}")


@router.get("/pincode/{pincode}")
async def get_pincode_get(
    pincode: str = Path(..., pattern=r"^\d{6}$"),
    db: Session = Depends(get_db),
):
    """GET version of pincode lookup"""
    service = get_geolocation_service()
    
    try:
        location = await service.get_location_from_pincode(pincode)
        if not location:
            raise HTTPException(status_code=404, detail="Location not found for pincode")
        return LocationResponse(**location.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pincode lookup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Pincode lookup failed: {str(e)}")


@router.get("/search")
async def search_locations_get(
    q: str = Query(..., min_length=2, description="Search query"),
    db: Session = Depends(get_db),
):
    """GET version of location search"""
    service = get_geolocation_service()
    
    try:
        results = await service.forward_geocode(q)
        return {"query": q, "results": [r.to_dict() for r in results], "total": len(results)}
    except Exception as e:
        logger.error(f"Location search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Location search failed: {str(e)}")