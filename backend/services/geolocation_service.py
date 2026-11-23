# AgriPredict AI - Geolocation Service
"""
Real-time location detection using Browser Geolocation API + Nominatim (OpenStreetMap) reverse geocoding.
Provides state, district, subdistrict, pincode, and GPS coordinates.
"""

import os
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict
from functools import lru_cache

import requests
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

logger = logging.getLogger("geolocation_service")


@dataclass
class LocationInfo:
    """Complete location information from geocoding"""
    latitude: float
    longitude: float
    state: str
    district: str
    subdistrict: Optional[str] = None
    city: Optional[str] = None
    village: Optional[str] = None
    pincode: Optional[str] = None
    formatted_address: str = ""
    confidence: float = 0.0
    source: str = "nominatim"
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> dict:
        return asdict(self)


class GeolocationService:
    """
    Service for real-time location detection using:
    1. Browser Geolocation API (frontend)
    2. Nominatim (OpenStreetMap) reverse geocoding (backend)
    3. Caching for performance
    """
    
    def __init__(self):
        self.geolocator = Nominatim(
            user_agent="AgriPredictAI/2.0 (contact@agripredict.example)",
            timeout=10
        )
        self._cache = {}
        self._cache_ttl = 3600  # 1 hour cache
        
    def _cache_key(self, lat: float, lon: float) -> str:
        return f"{lat:.6f},{lon:.6f}"
    
    def _is_cache_valid(self, timestamp: str) -> bool:
        try:
            cached_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return (datetime.now(timezone.utc) - cached_time).total_seconds() < self._cache_ttl
        except:
            return False
    
    async def reverse_geocode(self, latitude: float, longitude: float) -> LocationInfo:
        """
        Reverse geocode latitude/longitude to full location info.
        Uses Nominatim (OpenStreetMap) with caching.
        """
        cache_key = self._cache_key(latitude, longitude)
        
        # Check cache
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            if self._is_cache_valid(timestamp):
                logger.debug(f"Cache hit for {latitude}, {longitude}")
                return cached_data
        
        try:
            # Run geocoding in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            location = await loop.run_in_executor(
                None,
                lambda: self.geolocator.reverse(
                    f"{latitude}, {longitude}",
                    exactly_one=True,
                    language="en",
                    addressdetails=True,
                    zoom=18
                )
            )
            
            if not location:
                raise ValueError("No location found")
            
            # Parse address components
            address = location.raw.get('address', {})
            
            # Extract components for India
            state = address.get('state', '')
            district = address.get('district', '') or address.get('county', '')
            subdistrict = address.get('subdistrict', '') or address.get('taluk', '') or address.get('tehsil', '')
            city = address.get('city', '') or address.get('town', '') or address.get('village', '')
            village = address.get('village', '') or address.get('hamlet', '')
            pincode = address.get('postcode', '')
            
            # Build formatted address
            formatted = location.address
            
            location_info = LocationInfo(
                latitude=location.latitude,
                longitude=location.longitude,
                state=state,
                district=district,
                subdistrict=subdistrict,
                city=city,
                village=village,
                pincode=pincode,
                formatted_address=formatted,
                confidence=1.0,
                source="nominatim"
            )
            
            # Cache the result
            self._cache[cache_key] = (location_info, datetime.now(timezone.utc).isoformat())
            
            return location_info
            
        except (GeocoderTimedOut, GeocoderUnavailable) as e:
            logger.warning(f"Nominatim timeout/unavailable: {e}")
            raise
        except Exception as e:
            logger.error(f"Reverse geocoding error: {e}")
            raise
    
    async def forward_geocode(self, query: str) -> List[LocationInfo]:
        """
        Forward geocode an address/query to coordinates.
        """
        try:
            loop = asyncio.get_event_loop()
            locations = await loop.run_in_executor(
                None,
                lambda: self.geolocator.geocode(
                    query,
                    exactly_one=False,
                    limit=5,
                    language="en",
                    addressdetails=True,
                    zoom=18
                )
            )
            
            results = []
            if locations:
                for loc in locations:
                    address = loc.raw.get('address', {})
                    results.append(LocationInfo(
                        latitude=loc.latitude,
                        longitude=loc.longitude,
                        state=address.get('state', ''),
                        district=address.get('district', '') or address.get('county', ''),
                        subdistrict=address.get('subdistrict', '') or address.get('taluk', ''),
                        city=address.get('city', '') or address.get('town', ''),
                        village=address.get('village', ''),
                        pincode=address.get('postcode', ''),
                        formatted_address=loc.address,
                        confidence=0.9,
                        source="nominatim"
                    ))
            
            return results
            
        except Exception as e:
            logger.error(f"Forward geocoding error: {e}")
            return []
    
    async def get_location_from_pincode(self, pincode: str) -> Optional[LocationInfo]:
        """
        Get location from 6-digit Indian pincode.
        """
        if not pincode or len(pincode) != 6 or not pincode.isdigit():
            return None
        
        query = f"{pincode}, India"
        results = await self.forward_geocode(query)
        return results[0] if results else None
    
    def clear_cache(self):
        """Clear the geocoding cache"""
        self._cache.clear()
        logger.info("Geocoding cache cleared")


# Global instance
_geolocation_service = None

def get_geolocation_service() -> GeolocationService:
    global _geolocation_service
    if _geolocation_service is None:
        _geolocation_service = GeolocationService()
    return _geolocation_service


# ============================================================================
# Frontend JavaScript Geolocation Helper (to be included in frontend)
# ============================================================================

FRONTEND_GEOLOCATION_JS = """
// AgriPredict AI - Browser Geolocation Helper
// Add this to your frontend to get user's real location

class AgriGeolocation {
    constructor() {
        this.watchId = null;
        this.locationCache = null;
    }

    /**
     * Get current position using Browser Geolocation API
     * Returns: { latitude, longitude, accuracy, timestamp }
     */
    async getCurrentPosition(options = {}) {
        const defaultOptions = {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 300000 // 5 minutes
        };
        
        return new Promise((resolve, reject) => {
            if (!navigator.geolocation) {
                reject(new Error('Geolocation is not supported by this browser'));
                return;
            }

            navigator.geolocation.getCurrentPosition(
                (position) => {
                    resolve({
                        latitude: position.coords.latitude,
                        longitude: position.coords.longitude,
                        accuracy: position.coords.accuracy,
                        altitude: position.coords.altitude,
                        heading: position.coords.heading,
                        speed: position.coords.speed,
                        timestamp: position.timestamp
                    });
                },
                (error) => {
                    const messages = {
                        1: 'Permission denied',
                        2: 'Position unavailable',
                        3: 'Timeout'
                    };
                    reject(new Error(messages[error.code] || 'Geolocation error'));
                },
                { ...defaultOptions, ...options }
            );
        });
    }

    /**
     * Watch position changes (for moving users)
     */
    watchPosition(callback, options = {}) {
        if (!navigator.geolocation) {
            throw new Error('Geolocation not supported');
        }
        
        this.watchId = navigator.geolocation.watchPosition(
            (position) => {
                callback({
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude,
                    accuracy: position.coords.accuracy,
                    timestamp: position.timestamp
                });
            },
            (error) => {
                console.warn('Geolocation watch error:', error.message);
            },
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000, ...options }
        );
        
        return this.watchId;
    }

    /**
     * Clear watch
     */
    clearWatch() {
        if (this.watchId !== null) {
            navigator.geolocation.clearWatch(this.watchId);
            this.watchId = null;
        }
    }

    /**
     * Get location from backend (reverse geocoding)
     * Calls backend API to convert lat/lon to full address
     */
    async getLocationDetails(latitude, longitude) {
        try {
            const response = await fetch(`/api/location/reverse`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ latitude, longitude })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('Reverse geocoding failed:', error);
            throw error;
        }
    }

    /**
     * Get location from pincode
     */
    async getLocationFromPincode(pincode) {
        try {
            const response = await fetch(`/api/location/pincode/${pincode}`);
            if (!response.ok) throw new Error('Invalid pincode');
            return await response.json();
        } catch (error) {
            console.error('Pincode lookup failed:', error);
            throw error;
        }
    }

    /**
     * Search locations by query
     */
    async searchLocations(query) {
        try {
            const response = await fetch(`/api/location/search`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query })
            });
            return await response.json();
        } catch (error) {
            console.error('Location search failed:', error);
            throw error;
        }
    }

    /**
     * Get full location hierarchy (state -> district -> subdistrict -> village)
     * Auto-detects user's location and returns full hierarchy
     */
    async getFullLocation() {
        // 1. Get GPS coordinates
        const position = await this.getCurrentPosition();
        
        // 2. Get detailed location from backend
        const location = await this.getLocationDetails(
            position.latitude,
            position.longitude
        );
        
        return {
            ...position,
            ...location
        };
    }
}

// Export for use in other modules
window.AgriGeolocation = AgriGeolocation;

// Auto-initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    window.agriGeo = new AgriGeolocation();
    console.log('AgriGeolocation initialized');
});
"""


# Global instance
_geolocation_service = None

def get_geolocation_service() -> GeolocationService:
    global _geolocation_service
    if _geolocation_service is None:
        _geolocation_service = GeolocationService()
    return _geolocation_service