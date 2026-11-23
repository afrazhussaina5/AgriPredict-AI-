# AgriPredict AI - OSRM Routing Service
"""
Real road distance and duration calculation using OSRM (OpenStreetMap Routing Machine).
Provides accurate road distance and travel time for truck routing between farmer location and mandis.
"""

import os
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict
from functools import lru_cache

import requests

logger = logging.getLogger("osrm_service")


@dataclass
class RouteResult:
    """Route calculation result"""
    distance_km: float
    duration_minutes: float
    duration_traffic_minutes: Optional[float] = None
    geometry: Optional[Dict[str, Any]] = None
    steps: Optional[List[Dict[str, Any]]] = None
    source: str = "osrm"
    profile: str = "truck"
    timestamp: str = ""
    cached: bool = False
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class StorageCostResponse:
    """Storage cost calculation result"""
    rate_per_day_per_qtl: float
    storage_cost: float
    total_cost: float
    rate_source: str
    min_charge: Optional[float] = None
    facility_name: Optional[str] = None
    
    def to_dict(self) -> dict:
        return asdict(self)


class OSRMService:
    """
    Service for real road routing using OSRM (OpenStreetMap Routing Machine).
    Uses public OSRM instance or can be configured for self-hosted instance.
    """
    
    # Public OSRM instances (with usage limits)
    PUBLIC_OSRM_INSTANCES = [
        "https://router.project-osrm.org",
        "https://routing.openstreetmap.de",
    ]
    
    # Profile options
    PROFILES = {
        "car": "driving",
        "truck": "driving",  # OSRM uses 'driving' for trucks too
        "tractor": "driving",
    }
    
    def __init__(self, base_url: str = None, profile: str = "truck"):
        """
        Initialize OSRM service.
        
        Args:
            base_url: OSRM server URL (uses public instances if not provided)
            profile: Routing profile (car, truck, tractor)
        """
        self.base_url = base_url or self.PUBLIC_OSRM_INSTANCES[0]
        self.profile = self.PROFILES.get(profile, "driving")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "AgriPredictAI/2.0",
            "Accept": "application/json",
        })
        
        # Cache for routes
        self._cache = {}
        self._cache_ttl = 86400  # 24 hours
    
    def _cache_key(self, lat1: float, lon1: float, lat2: float, lon2: float, profile: str) -> str:
        return f"{lat1:.6f},{lon1:.6f}->{lat2:.6f},{lon2:.6f}:{profile}"
    
    def _is_cache_valid(self, timestamp: str) -> bool:
        try:
            cached_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return (datetime.now(timezone.utc) - cached_time).total_seconds() < 86400
        except:
            return False
    
    async def get_route(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        profile: str = None,
        alternatives: bool = False,
        steps: bool = True,
        geometries: str = "geojson",
    ) -> RouteResult:
        """
        Get route between two points using OSRM.
        
        Args:
            origin_lat, origin_lon: Starting coordinates
            dest_lat, dest_lon: Destination coordinates
            profile: Routing profile (car, truck, tractor)
            alternatives: Return alternative routes
            steps: Include turn-by-turn instructions
            geometries: Geometry format (geojson, polyline, polyline6)
        
        Returns:
            RouteResult with distance, duration, and geometry
        """
        profile = profile or self.profile
        profile = self.PROFILES.get(profile, "driving")
        
        # Check cache
        cache_key = self._cache_key(
            origin_lat, origin_lon, dest_lat, dest_lon, profile
        )
        
        if cache_key in self._cache:
            cached_result, timestamp = self._cache[cache_key]
            if (datetime.now(timezone.utc) - datetime.fromisoformat(timestamp)).total_seconds() < 86400:
                logger.debug(f"Route cache hit: {cache_key}")
                cached_result.cached = True
                return cached_result
        
        # Build OSRM URL
        url = f"{self.base_url}/route/v1/{profile}/{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
        
        params = {
            "alternatives": "true" if alternatives else "false",
            "steps": "true" if steps else "false",
            "geometries": geometries,
            "overview": "full",
            "annotations": "duration,distance",
        }
        
        try:
            logger.debug(f"Requesting OSRM route: {url}")
            
            loop = asyncio.get_event_loop()
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: requests.get(url, params=params, timeout=30)
            )
            
            if response.status_code != 200:
                raise Exception(f"OSRM API error: {response.status_code} - {response.text}")
            
            data = response.json()
            
            if data.get("code") != "Ok":
                raise Exception(f"OSRM error: {data.get('message', 'Unknown error')}")
            
            routes = data.get("routes", [])
            if not routes:
                raise Exception("No route found")
            
            # Use first (best) route
            route = routes[0]
            
            result = RouteResult(
                distance_km=round(route["distance"] / 1000, 2),
                duration_minutes=round(route["duration"] / 60, 1),
                geometry=route.get("geometry"),
                steps=route.get("legs", [{}])[0].get("steps", []) if route.get("legs") else [],
                profile=profile,
                source="osrm",
                cached=False
            )
            
            # Cache the result
            self._cache[self._cache_key(
                origin_lat, origin_lon, dest_lat, dest_lon, profile
            )] = (result, datetime.now(timezone.utc).isoformat())
            
            return result
            
        except requests.exceptions.Timeout:
            logger.error("OSRM request timeout")
            raise Exception("Routing service timeout")
        except requests.exceptions.RequestException as e:
            logger.error(f"OSRM request failed: {e}")
            raise Exception(f"Routing service unavailable: {e}")
        except Exception as e:
            logger.error(f"Route calculation error: {e}")
            raise
    
    async def get_route_table(
        self,
        origins: List[Tuple[float, float]],
        destinations: List[Tuple[float, float]],
        profile: str = None,
    ) -> Dict[str, Any]:
        """
        Get distance/duration matrix for multiple origins/destinations.
        Uses OSRM table endpoint.
        """
        profile = profile or self.profile
        profile = self.PROFILES.get(profile, "driving")
        
        # Format coordinates
        coords = ";".join([f"{lon},{lat}" for lat, lon in origins + destinations])
        sources = ";".join(str(i) for i in range(len(origins)))
        destinations_idx = ";".join(str(i) for i in range(len(origins), len(origins) + len(destinations)))
        
        url = f"{self.base_url}/table/v1/{profile}/{coords}"
        
        params = {
            "sources": sources,
            "destinations": destinations_idx,
            "annotations": "duration,distance",
        }
        
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(url, params=params, timeout=30)
            )
            
            if response.status_code != 200:
                raise Exception(f"OSRM table API error: {response.status_code}")
            
            data = response.json()
            
            if data.get("code") != "Ok":
                raise Exception(f"OSRM table error: {data.get('message')}")
            
            return {
                "durations": data.get("durations", []),
                "distances": data.get("distances", []),
                "sources": data.get("sources", []),
                "destinations": data.get("destinations", []),
            }
            
        except Exception as e:
            logger.error(f"OSRM table API error: {e}")
            raise
    
    async def nearest_road(
        self,
        latitude: float,
        longitude: float,
        number: int = 1
    ) -> Dict[str, Any]:
        """
        Snap a coordinate to the nearest road.
        """
        url = f"{self.base_url}/nearest/v1/driving/{longitude},{latitude}"
        
        params = {"number": number}
        
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(url, params=params, timeout=10)
            )
            
            if response.status_code != 200:
                raise Exception(f"OSRM nearest error: {response.status_code}")
            
            data = response.json()
            
            if data.get("code") != "Ok":
                raise Exception(f"OSRM nearest error: {data.get('message')}")
            
            waypoints = data.get("waypoints", [])
            if waypoints:
                wp = waypoints[0]
                return {
                    "latitude": wp["location"][1],
                    "longitude": wp["location"][0],
                    "name": wp.get("name"),
                    "distance_meters": wp.get("distance"),
                }
            return {}
            
        except Exception as e:
            logger.error(f"OSRM nearest error: {e}")
            raise
    
    def clear_cache(self):
        """Clear route cache"""
        self._cache.clear()
        logger.info("OSRM route cache cleared")
    
    async def get_storage_cost(
        self,
        commodity_id: str,
        quantity_qtl: float,
        storage_type: str = "cold_storage",
        days: int = 1,
    ) -> "StorageCostResponse":
        """
        Get storage cost from database or use defaults.
        """
        from ..models import StorageRate, Commodity
        from ..db import get_db_session
        
        try:
            with get_db_session() as db:
                commodity = db.query(Commodity).filter(Commodity.id == commodity_id).first()
                
                # Try to get specific rate
                rate = db.query(StorageRate).filter(
                    StorageRate.commodity_id == commodity_id,
                    StorageRate.storage_type == storage_type,
                ).first()
                
                if not rate:
                    # Try state-level rate
                    rate = db.query(StorageRate).filter(
                        StorageRate.commodity_id == commodity_id,
                        StorageRate.storage_type == storage_type,
                    ).first()
                
                if not rate:
                    # Use commodity default
                    if commodity:
                        if storage_type == "cold_storage":
                            rate_per_day = commodity.storage_cost_per_day_qtl or 4.0
                        else:
                            rate_per_day = (commodity.storage_cost_per_day_qtl or 4.0) * 0.6
                    else:
                        rate_per_day = 4.0 if storage_type == "cold_storage" else 2.4
                    min_charge = 50.0
                    rate_source = "default"
                    facility_name = None
                else:
                    rate_per_day = rate.rate_per_day_per_qtl
                    min_charge = rate.min_charge_per_day
                    rate_source = "configured"
                    facility_name = rate.facility_name
                
                storage_cost = round(rate_per_day * quantity_qtl * days, 2)
                
                # Apply minimum charge
                if min_charge and storage_cost < min_charge * days:
                    storage_cost = round(min_charge * days, 2)
                
                return StorageCostResponse(
                    rate_per_day_per_qtl=rate_per_day,
                    storage_cost=storage_cost,
                    min_charge=min_charge,
                    total_cost=storage_cost,
                    rate_source=rate_source,
                    facility_name=facility_name,
                )
        except Exception as e:
            logger.error(f"Storage cost calculation failed: {e}")
            # Fallback to default
            return StorageCostResponse(
                rate_per_day_per_qtl=4.0,
                storage_cost=round(4.0 * quantity_qtl * days, 2),
                min_charge=50.0,
                total_cost=round(4.0 * quantity_qtl * days, 2),
                rate_source="default_fallback",
                facility_name=None,
            )
    
    def clear_cache(self):
        """Clear route cache"""
        self._cache.clear()
        logger.info("OSRM route cache cleared")


# ============================================================================
# Distance Calculation Fallback (Haversine)
# ============================================================================

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate Haversine distance between two points (straight-line distance).
    Used as fallback when OSRM is unavailable.
    """
    from math import radians, sin, cos, sqrt, atan2
    
    R = 6371  # Earth radius in km
    
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return round(R * c, 2)


def estimate_road_distance(haversine_km: float, terrain_factor: float = 1.3) -> float:
    """
    Estimate road distance from straight-line distance.
    Default factor 1.3 accounts for road curves, detours.
    """
    return round(haversine_km * terrain_factor, 1)


def estimate_travel_time(distance_km: float, avg_speed_kmh: float = 40) -> int:
    """
    Estimate travel time in minutes.
    Default 40 km/h for trucks on Indian roads.
    """
    return round((distance_km / avg_speed_kmh) * 60)


# Global instance
_osrm_service = None

def get_osrm_service(base_url: str = None, profile: str = "truck") -> OSRMService:
    global _osrm_service
    if _osrm_service is None:
        _osrm_service = OSRMService(base_url, profile)
    return _osrm_service


# ============================================================================
# Frontend JavaScript Routing Helper
# ============================================================================

FRONTEND_ROUTING_JS = """
// AgriPredict AI - OSRM Routing Helper (Frontend)
// Calculate real road distances and durations between locations

class AgriRouting {
    constructor(baseUrl = 'https://router.project-osrm.org') {
        this.baseUrl = baseUrl;
        this.cache = new Map();
    }

    /**
     * Get route between two points using OSRM
     * @param {Object} origin - { latitude, longitude }
     * @param {Object} destination - { latitude, longitude }
     * @param {String} profile - 'driving' (car), 'truck', 'tractor'
     * @returns {Promise<Object>} { distance_km, duration_minutes, geometry, steps }
     */
    async getRoute(origin, destination, profile = 'truck') {
        const cacheKey = `${origin.latitude},${origin.longitude}->${destination.latitude},${destination.longitude}:${profile}`;
        
        // Check cache
        if (this.cache.has(cacheKey)) {
            return this.cache.get(cacheKey);
        }
        
        const profileMap = { 'car': 'driving', 'truck': 'driving', 'tractor': 'driving' };
        const osrmProfile = profileMap[profile] || 'driving';
        
        const url = `${this.baseUrl}/route/v1/${osrmProfile}/${origin.longitude},${origin.latitude};${destination.longitude},${destination.latitude}`;
        
        const params = new URLSearchParams({
            alternatives: 'false',
            steps: 'true',
            geometries: 'geojson',
            overview: 'full',
            annotations: 'duration,distance'
        });
        
        try {
            const response = await fetch(`${url}?${params}`);
            
            if (!response.ok) {
                throw new Error(`OSRM API error: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.code !== 'Ok') {
                throw new Error(`OSRM error: ${data.message}`);
            }
            
            const route = data.routes[0];
            
            const result = {
                distance_km: Math.round(route.distance / 1000 * 100) / 100,
                duration_minutes: Math.round(route.duration / 60 * 10) / 10,
                geometry: route.geometry,
                steps: route.legs?.[0]?.steps || [],
                profile: 'truck',
                source: 'osrm'
            };
            
            // Cache result
            this.cache.set(`${origin.latitude},${origin.longitude}->${destination.latitude},${destination.longitude}:truck`, result);
            
            return result;
            
        } catch (error) {
            console.error('OSRM routing error:', error);
            // Fallback to Haversine estimation
            return this.estimateRouteFallback(origin, destination);
        }
    }
    
    /**
     * Fallback: Estimate route using Haversine distance
     */
    estimateRouteFallback(origin, destination) {
        const distance = this.haversineDistance(
            origin.latitude, origin.longitude,
            destination.latitude, destination.longitude
        );
        
        const roadDistance = distance * 1.3; // 1.3x factor for road curves
        const duration = (roadDistance / 40) * 60; // 40 km/h average
        
        return {
            distance_km: Math.round(roadDistance * 100) / 100,
            duration_minutes: Math.round(duration * 10) / 10,
            geometry: null,
            steps: [],
            profile: 'truck',
            source: 'haversine_estimate'
        };
    }
    
    /**
     * Haversine distance (straight-line)
     */
    haversineDistance(lat1, lon1, lat2, lon2) {
        const R = 6371; // Earth radius in km
        const toRad = (deg) => deg * Math.PI / 180;
        
        const lat1 = toRad(lat1), lon1 = toRad(lon1);
        const lat2 = toRad(lat2), lon2 = toRad(lon2);
        
        const dlat = lat2 - lat1;
        const dlon = lon2 - lon1;
        
        const a = Math.sin(dlat/2)**2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dlon/2)**2;
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        
        return R * c;
    }
    
    /**
     * Get distance matrix for multiple origins/destinations
     */
    async getDistanceMatrix(origins, destinations) {
        // origins/destinations: [{latitude, longitude}, ...]
        const coords = [...origins, ...destinations].map(p => `${p.longitude},${p.latitude}`).join(';');
        const sources = Array.from({length: origins.length}, (_, i) => i).join(';');
        const destinationsIdx = Array.from({length: destinations.length}, (_, i) => i + origins.length).join(';');
        
        const url = `${this.baseUrl}/table/v1/driving/${coords}`;
        const params = new URLSearchParams({
            sources: sources,
            destinations: destinationsIdx,
            annotations: 'duration,distance'
        });
        
        const response = await fetch(`${url}?${params}`);
        const data = await response.json();
        
        if (data.code !== 'Ok') {
            throw new Error(`OSRM table error: ${data.message}`);
        }
        
        return {
            durations: data.durations, // seconds
            distances: data.distances  // meters
        };
    }
    
    clearCache() {
        this.cache.clear();
    }
}

// Export for use
window.AgriRouting = AgriRouting;

// Auto-initialize
document.addEventListener('DOMContentLoaded', () => {
    window.agriRouting = new AgriRouting();
    console.log('AgriRouting initialized');
});
"""


# Global instance
_osrm_service = None

def get_osrm_service(base_url: str = None, profile: str = "truck") -> OSRMService:
    global _osrm_service
    if _osrm_service is None:
        _osrm_service = OSRMService(base_url, profile)
    return _osrm_service