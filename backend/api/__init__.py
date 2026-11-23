# AgriPredict AI - API Routes Package
"""
All FastAPI route modules.
"""

from . import locations, mandis, market_data, buyers, lots, fpos, routing, sync, agmarknet

__all__ = [
    "locations",
    "mandis",
    "market_data",
    "buyers",
    "lots",
    "fpos",
    "routing",
    "sync",
    "agmarknet",
]