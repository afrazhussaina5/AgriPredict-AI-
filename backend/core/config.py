# AgriPredict AI - Core Configuration
"""
Application settings and configuration management.
"""

import os
import json
from functools import lru_cache
from typing import List, Optional, Union

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    APP_NAME: str = "AgriPredict AI"
    APP_VERSION: str = "2.0.0"
    ENVIRONMENT: str = Field(default="development", description="development, staging, production")
    DEBUG: bool = Field(default=True)
    SECRET_KEY: str = Field(default="", description="Secret key for session signing")
    
    # Database
    DATABASE_URL: str = Field(default="", description="PostgreSQL connection string")
    
    # API
    API_PREFIX: str = "/api"
    CORS_ORIGINS_STR: str = Field(default="http://localhost:8000,http://127.0.0.1:8000", description="CORS allowed origins (comma-separated)")
    
    @property
    def CORS_ORIGINS(self) -> List[str]:
        """Parse CORS_ORIGINS from comma-separated string."""
        v = self.CORS_ORIGINS_STR
        if isinstance(v, str):
            if v.startswith("["):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"
    
    # Government Mandi API
    MARKET_API_URL: str = Field(default="", description="Data.gov.in / Agmarknet API endpoint")
    MARKET_API_KEY: str = Field(default="", description="API key for government mandi API")
    MARKET_API_TIMEOUT: int = Field(default=10, description="Request timeout in seconds")
    MARKET_API_MAX_PAGES: int = Field(default=20, description="Max pages for pagination")
    MARKET_API_LIMIT: int = Field(default=1000, description="Records per page")
    
    # Geocoding
    GEOCODING_PROVIDER: str = Field(default="nominatim", description="nominatim, google, mapbox, opencage")
    GEOCODING_API_KEY: str = Field(default="")
    NOMINATIM_USER_AGENT: str = Field(default="AgriPredictAI/1.0")
    GEOCODING_TIMEOUT: int = Field(default=10)
    GEOCODING_RATE_LIMIT: int = Field(default=1, description="Requests per second")
    
    # Routing
    ROUTING_PROVIDER: str = Field(default="osrm", description="osrm, ors, google, mapbox")
    ROUTING_API_KEY: str = Field(default="")
    OSRM_BASE_URL: str = Field(default="https://router.project-osrm.org")
    ORS_BASE_URL: str = Field(default="https://api.openrouteservice.org")
    ROUTING_TIMEOUT: int = Field(default=15)
    ROUTING_PROFILE: str = Field(default="truck", description="car, truck, tractor")
    
    # Cache
    REDIS_URL: str = Field(default="")
    CACHE_TTL_SECONDS: int = Field(default=3600, description="Default cache TTL")
    ROUTE_CACHE_TTL_DAYS: int = Field(default=7)
    GEOCODE_CACHE_TTL_DAYS: int = Field(default=30)
    
    # Sync
    MARKET_SYNC_CRON: str = Field(default="0 6 * * *", description="Cron expression for market data sync")
    MARKET_SYNC_LOOKBACK_DAYS: int = Field(default=7)
    SYNC_MAX_RETRIES: int = Field(default=3)
    SYNC_TIMEOUT_SECONDS: int = Field(default=3600)
    
    # External Services
    ORS_API_KEY: str = Field(default="")
    MAPBOX_API_KEY: str = Field(default="")
    GOOGLE_MAPS_API_KEY: str = Field(default="")
    
    # File Storage
    UPLOAD_DIR: str = Field(default="./uploads")
    MAX_UPLOAD_SIZE_MB: int = Field(default=10)
    
    # Pagination
    DEFAULT_PAGE_SIZE: int = Field(default=50)
    MAX_PAGE_SIZE: int = Field(default=1000)
    
    # Security
    RATE_LIMIT_REQUESTS: int = Field(default=100, description="Requests per minute")
    RATE_LIMIT_WINDOW: int = Field(default=60)
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO")
    LOG_FORMAT: str = Field(default="json")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Dependency for FastAPI
def get_settings_dep() -> Settings:
    return get_settings()