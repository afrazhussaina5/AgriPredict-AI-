# AgriPredict AI - Python FastAPI Backend Server
"""
FastAPI Server for AgriPredict AI
Smart Market Intelligence & Price Discovery Platform (SIH 26132)
Integrates real Government Mandi API client, dynamic commodity discovery,
historical dataset management, transparent prototype buyer scoring, and fallback mechanisms.
Now with PostgreSQL persistence, verified mandi master, real routing, and FPO workflows.
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Database
from .db import init_database, get_db_session as get_db_session_ctx
from .core.database import seed_core_data, create_sample_mandi
from .models import (
    State, District, Subdistrict, Location, LocationType,
    Mandi, MandiStatus, VerificationStatus, Commodity,
    MarketPrice, MarketPriceStatus,
    Buyer, BuyerVerificationStatus, BuyerCategory,
    Lot, LotMember, LotStatus, SellerType,
    FPO, FPOStatus, FPOType,
)

# Services
from .services.market_api import fetch_market_data, fetch_all_market_data, get_api_config
from .services.data_processor import (
    normalize_market_records,
    load_market_history,
    update_market_history,
    HISTORY_CSV_PATH
)

# API Routes
from .api import locations, mandis, market_data, buyers, lots, fpos, routing, sync, agmarknet

# Mock data for backward compatibility
from .mock_data import COMMODITIES_PY, MANDIS_PY, BUYERS_PY


# ============================================================================
# Lifespan Events
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    print("Starting AgriPredict AI Backend...")
    try:
        init_database()
        print("Database initialized.")
        
        # Seed core data
        with get_db_session_ctx() as db:
            seed_core_data(db)
        print("Core data seeded.")
    except Exception as e:
        print(f"Startup warning: {e}")
    
    yield
    
    # Shutdown
    print("Shutting down AgriPredict AI Backend...")


app = FastAPI(
    title="AgriPredict AI API",
    description="Backend service providing live Government Mandi price data integration, historical dataset management, dynamic commodity directory, verified mandi master, real routing, buyer matching, and FPO workflows (SIH 26132).",
    version="2.0.0",
    lifespan=lifespan,
)

# Enable CORS for local and cross-origin frontend calls
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")


# ============================================================================
# Database Dependency
# ============================================================================

def get_db():
    """Database session dependency for FastAPI."""
    db = get_db_session_ctx()
    try:
        with db as session:
            yield session
    finally:
        pass


# ============================================================================
# Include New API Routes
# ============================================================================

app.include_router(locations.router, prefix="/api")
app.include_router(mandis.router, prefix="/api")
app.include_router(market_data.router, prefix="/api")
app.include_router(buyers.router, prefix="/api")
app.include_router(lots.router, prefix="/api")
app.include_router(fpos.router, prefix="/api")
app.include_router(routing.router, prefix="/api")
app.include_router(sync.router, prefix="/api")
app.include_router(agmarknet.router, prefix="/api")


# ============================================================================
# Request Models (Legacy - kept for backward compatibility)
# ============================================================================

class AnalyzeRequest(BaseModel):
    commodityId: str = "onion"
    quantity: float = 50.0
    grade: str = "A"
    state: Optional[str] = "Andhra Pradesh"
    district: Optional[str] = "Kurnool"
    preferredMarket: Optional[str] = "Kurnool Agricultural Market Yard"
    location: Optional[str] = "Kurnool, Andhra Pradesh"
    hasStorage: bool = True


class SimulateRequest(BaseModel):
    commodityId: str = "onion"
    quantity: float = 50.0
    grade: str = "A"
    storageDays: int = 5
    transportRateMultiplier: float = 1.0
    storageRateMultiplier: float = 1.0


class UpdateHistoryRequest(BaseModel):
    state: Optional[str] = None
    district: Optional[str] = None
    commodity: Optional[str] = None
    arrival_date: Optional[str] = None
    limit: int = 100
    max_pages: int = 10


class LotMember(BaseModel):
    name: str = "Member"
    quantity: float = 0.0


class LotCreateRequest(BaseModel):
    commodityId: str = "onion"
    commodityName: Optional[str] = "Onion"
    quantity: float = 50.0
    unit: str = "Quintal (100 kg)"
    qualityGrade: str = "A"
    location: str = "Kurnool, Andhra Pradesh"
    expectedMinimumPrice: float = 3000.0
    availableUntil: Optional[str] = None
    sellerType: str = "Individual Farmer"  # "Individual Farmer" or "FPO / Producer Group"
    fpoName: Optional[str] = None
    fpoMembers: Optional[List[LotMember]] = None
    notes: Optional[str] = None


class LotInterestRequest(BaseModel):
    buyerId: str
    buyerName: Optional[str] = None
    contactName: Optional[str] = "Farmer / FPO Lead"
    contactPhone: Optional[str] = "+91 98765 43210"
    offeredPrice: Optional[float] = None
    message: Optional[str] = "Interested in supplying produce according to verified lot specifications."


# ============================================================================
# Core Health & Metadata Endpoints
# ============================================================================

@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    api_url, api_key = get_api_config()
    is_api_configured = bool(api_url and api_key)
    has_cached_history = os.path.exists(HISTORY_CSV_PATH)
    
    # Check database connectivity
    try:
        db.execute("SELECT 1")
        db_connected = True
    except Exception:
        db_connected = False
    
    # Count verified mandis
    verified_mandis = db.query(Mandi).filter(
        Mandi.verification_status == VerificationStatus.VERIFIED,
        Mandi.status == MandiStatus.ACTIVE,
    ).count()
    
    # Count verified buyers
    verified_buyers = db.query(Buyer).filter(
        Buyer.verification_status == BuyerVerificationStatus.VERIFIED,
        Buyer.is_active == True,
        Buyer.is_demo == False,
    ).count()
    
    return {
        "status": "healthy",
        "service": "AgriPredict AI Engine",
        "sihStatement": "26132 - Market Linkages & Price Discovery",
        "version": "2.0.0",
        "external_api_configured": is_api_configured,
        "historical_cache_available": has_cached_history,
        "database_connected": db_connected,
        "total_commodities": len(get_all_dynamic_commodities()),
        "verified_mandis": verified_mandis,
        "verified_buyers": verified_buyers,
        "last_checked": datetime.now(timezone.utc).isoformat()
    }


def get_all_dynamic_commodities() -> List[Dict[str, Any]]:
    """
    Dynamically discover commodities from:
    1. Database (Commodity table)
    2. Cached historical market CSV data (if present)
    3. Master agricultural catalog (COMMODITIES_PY)
    """
    discovered_dict = {c["id"]: dict(c) for c in COMMODITIES_PY}
    
    # Try database first
    try:
        with get_db_session_ctx() as db:
            db_commodities = db.query(Commodity).all()
            for c in db_commodities:
                discovered_dict[c.id] = {
                    "id": c.id,
                    "name": c.name,
                    "variety": c.variety,
                    "category": c.category,
                    "icon": c.icon,
                    "basePrice": c.base_price,
                    "predictedPrice": c.predicted_price,
                    "priceChangePct": 0.0,
                    "trend": "stable",
                    "unit": c.unit,
                    "defaultQty": c.default_qty,
                    "shelfLifeDays": c.shelf_life_days,
                    "storageCostPerDayPerQtl": c.storage_cost_per_day_qtl,
                    "baseTransportRatePerKmPerQtl": c.base_transport_rate_per_km_qtl,
                    "hasMLModel": c.has_ml_model,
                    "forecastType": "Actual ML Forecast" if c.has_ml_model else "Estimated Demo Forecast",
                    "gradeMultipliers": c.grade_multipliers,
                }
    except Exception:
        pass
    
    # Check local historical CSV
    try:
        cached_df = load_market_history(limit=500)
        if not cached_df.empty and "Commodity" in cached_df.columns:
            unique_crops = cached_df["Commodity"].dropna().unique()
            for crop_raw in unique_crops:
                crop_name = str(crop_raw).strip()
                crop_id = crop_name.lower().replace(" ", "_").replace("-", "_")
                if crop_id not in discovered_dict and len(crop_id) > 1:
                    crop_df = cached_df[cached_df["Commodity"] == crop_raw]
                    mean_price = round(float(crop_df["Modal_Price"].mean())) if not crop_df.empty else 2500
                    discovered_dict[crop_id] = {
                        "id": crop_id,
                        "name": f"{crop_name} (Mandi Harvest)",
                        "variety": "Standard Mandi Grade",
                        "category": "Agricultural Produce",
                        "icon": "🌾",
                        "basePrice": mean_price,
                        "predictedPrice": round(mean_price * 1.05),
                        "priceChangePct": 5.0,
                        "trend": "up",
                        "unit": "Quintal (100 kg)",
                        "defaultQty": 50,
                        "shelfLifeDays": 30,
                        "storageCostPerDayPerQtl": 3.0,
                        "baseTransportRatePerKmPerQtl": 1.8,
                        "hasMLModel": False,
                        "forecastType": "Estimated Demo Forecast",
                        "forecastStatus": "Live market data available; ML model in training",
                        "dataSource": "Cached Historical CSV",
                        "gradeMultipliers": {"A": 1.05, "B": 1.0, "C": 0.90},
                        "historical30d": [round(mean_price * 0.96), round(mean_price * 0.98), mean_price],
                        "predicted7d": [
                            {"day": "Day 1", "price": round(mean_price * 1.01), "lower": round(mean_price * 0.98), "upper": round(mean_price * 1.04)},
                            {"day": "Day 5 (Optimal)", "price": round(mean_price * 1.05), "lower": round(mean_price * 1.01), "upper": round(mean_price * 1.09)}
                        ],
                        "recommendation": {
                            "action": "SELL AT BEST APMC MANDI",
                            "type": "SELL_BEST_MARKET",
                            "headline": f"Direct Mandi Delivery for {crop_name}",
                            "optimalDays": 0,
                            "expectedGain": 5000,
                            "confidence": 85,
                            "explanation": f"Delivering {crop_name} to the highest-paying regional APMC mandi offers optimum net realization.",
                            "factors": []
                        }
                    }
    except Exception:
        pass
    
    return list(discovered_dict.values())


# ============================================================================
# Dynamic Commodity & Market Discovery Endpoints (Legacy)
# ============================================================================

@app.get("/api/commodities")
def get_commodities():
    """
    Returns the dynamic list of all supported commodities with category,
    price indicators, and ML forecasting capability status.
    """
    return get_all_dynamic_commodities()


@app.get("/api/mandis")
def get_mandis_legacy(db: Session = Depends(get_db)):
    """Legacy endpoint - returns mandis from database with verification status."""
    mandis = db.query(Mandi).options(
        # joinedload(Mandi.commodities),  # Avoid loading for list view
    ).order_by(Mandi.name).all()
    
    return [
        {
            "id": m.mandi_id,
            "name": m.name,
            "state": m.state.name if m.state else "",
            "district": m.district.name if m.district else "",
            "distanceKm": 0,  # Calculated dynamically per request
            "priceOffsetMultiplier": m.price_offset_multiplier,
            "transportCostPerKmQtl": m.transport_cost_per_km_qtl,
            "storageCostPerDayQtl": m.storage_cost_per_day_qtl,
            "arrivalStatus": m.arrival_capacity_qtl,
            "rating": m.rating,
            "isE_NAM": m.is_e_nam,
            "facilities": m.facilities,
            "bestFor": [c.id for c in m.commodities],
            "verificationStatus": m.verification_status.value,
            "isSelectable": m.is_selectable,
        }
        for m in mandis
    ]


@app.get("/api/buyers")
def get_buyers_legacy(commodity: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Legacy endpoint - returns buyers from database.
    """
    query = db.query(Buyer).filter(Buyer.is_active == True)
    
    if commodity:
        query = query.join(Buyer.commodities).filter(Commodity.id == commodity)
    
    buyers = query.all()
    
    buyers_list = []
    for b in buyers:
        buyers_list.append({
            "id": b.buyer_id,
            "name": b.legal_name,
            "category": b.category.value,
            "commodities": [c.id for c in b.commodities],
            "rating": b.rating,
            "dealsCompleted": b.deals_completed,
            "isPrototype": b.is_demo,
            "prototypeDisclaimer": b.demo_disclaimer or "Demo Buyer Profile — Hackathon Prototype. Data provided for algorithmic evaluation.",
            "reliability": "Verified" if b.verification_status == BuyerVerificationStatus.VERIFIED else "Unverified",
            "paymentTerms": b.payment_terms,
            "minQuantityQtl": 10,
            "baseOfferMultiplier": 1.05,
            "distanceKm": 0,  # Calculated dynamically
            "matchScore": 0,
            "verificationStatus": b.verification_status.value,
        })
    
    return buyers_list


# ============================================================================
# Live Government Mandi API Endpoints (Legacy - kept for compatibility)
# ============================================================================

@app.get("/api/live-market-data")
def get_live_market_data(
    state: Optional[str] = Query(None, description="Filter by State name"),
    district: Optional[str] = Query(None, description="Filter by District name"),
    commodity: Optional[str] = Query(None, description="Filter by Commodity"),
    arrival_date: Optional[str] = Query(None, description="Filter by Arrival Date"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to fetch"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    current_time = datetime.now(timezone.utc).isoformat()

    # 1. Live Government API
    live_res = fetch_market_data(
        state=state,
        district=district,
        commodity=commodity,
        arrival_date=arrival_date,
        limit=limit,
        offset=offset
    )

    if live_res["status"] == "success" and live_res["records"]:
        df_clean = normalize_market_records(live_res["records"])
        records_list = df_clean.to_dict(orient="records")
        return {
            "status": "success",
            "data_source": "live_api",
            "total_records": len(records_list),
            "total_available": live_res.get("total", len(records_list)),
            "offset": offset,
            "limit": limit,
            "last_updated": live_res.get("last_updated", current_time),
            "records": records_list,
            "message": "Live market data successfully fetched from external Government API."
        }

    # 2. Cached Historical CSV
    cached_df = load_market_history(
        state=state,
        district=district,
        commodity=commodity,
        arrival_date=arrival_date,
        limit=limit
    )

    if not cached_df.empty:
        cached_records = cached_df.to_dict(orient="records")
        return {
            "status": "success",
            "data_source": "cached_data",
            "total_records": len(cached_records),
            "total_available": len(cached_records),
            "offset": offset,
            "limit": limit,
            "last_updated": current_time,
            "records": cached_records,
            "message": "Returned from local persistent market history dataset."
        }

    # 3. Structured Fallback
    mock_records = []
    target_crop = commodity.lower() if commodity else "all"
    all_commodities = get_all_dynamic_commodities()

    for com in all_commodities:
        if target_crop != "all" and target_crop not in com["name"].lower() and target_crop not in com["id"]:
            continue
        for mandi in MANDIS_PY:
            if state and state.lower() not in mandi["state"].lower():
                continue
            if district and district.lower() not in mandi["district"].lower():
                continue

            spot_rate = round(com["basePrice"] * mandi["priceOffsetMultiplier"])
            mock_records.append({
                "State": mandi["state"],
                "District": mandi["district"],
                "Market": mandi["name"],
                "Commodity": com["name"].split()[0],
                "Variety": com["variety"],
                "Grade": "FAQ",
                "Arrival_Date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "Min_Price": round(spot_rate * 0.95),
                "Max_Price": round(spot_rate * 1.05),
                "Modal_Price": spot_rate
            })

    return {
        "status": "success",
        "data_source": "mock_fallback",
        "total_records": len(mock_records),
        "total_available": len(mock_records),
        "offset": offset,
        "limit": limit,
        "last_updated": current_time,
        "records": mock_records,
        "message": "Fallback prototype dataset (External API not configured or offline)."
    }


@app.post("/api/update-market-history")
def update_market_history_endpoint(payload: Optional[UpdateHistoryRequest] = None):
    p = payload or UpdateHistoryRequest()
    api_url, api_key = get_api_config()
    current_time = datetime.now(timezone.utc).isoformat()

    if not api_url or not api_key:
        return {
            "status": "unconfigured",
            "data_source": "unconfigured",
            "records_fetched": 0,
            "records_added": 0,
            "duplicates_skipped": 0,
            "total_records": len(load_market_history()),
            "date_range": "N/A",
            "last_updated": current_time,
            "message": "Government Mandi API URL or Key is not configured in .env."
        }

    fetch_result = fetch_all_market_data(
        state=p.state,
        district=p.district,
        commodity=p.commodity,
        arrival_date=p.arrival_date,
        limit=p.limit,
        max_pages=p.max_pages
    )

    if fetch_result["status"] != "success" or not fetch_result["records"]:
        return {
            "status": "error",
            "data_source": "live_api",
            "records_fetched": 0,
            "records_added": 0,
            "duplicates_skipped": 0,
            "total_records": len(load_market_history()),
            "date_range": "N/A",
            "last_updated": current_time,
            "message": fetch_result.get("message", "Failed to fetch records from Government Mandi API.")
        }

    update_res = update_market_history(fetch_result["records"])
    update_res["data_source"] = "live_api"
    return update_res


# ============================================================================
# Produce Analysis & Market Intelligence Engine (Legacy - kept for compatibility)
# ============================================================================

@app.post("/api/analyze")
def analyze_produce(payload: AnalyzeRequest):
    """
    Legacy market intelligence engine using mock data.
    For new database-backed analysis, use /api/routing/net-return and /api/buyers/match
    """
    all_commodities = get_all_dynamic_commodities()
    commodity = next(
        (c for c in all_commodities if c["id"] == payload.commodityId or payload.commodityId in c["id"] or c["id"] in payload.commodityId),
        all_commodities[0]
    )

    grade_multiplier = commodity["gradeMultipliers"].get(payload.grade, 1.0)
    qty = max(1.0, payload.quantity)
    loc = (payload.location or f"{payload.district or ''}, {payload.state or ''}").lower()

    current_price = round(commodity["basePrice"] * grade_multiplier)
    predicted_price = round(commodity["predictedPrice"] * grade_multiplier)
    price_diff = predicted_price - current_price
    price_change_pct = round((price_diff / current_price) * 100, 1) if current_price > 0 else 0.0
    price_trend = "up" if price_diff > 20 else ("down" if price_diff < -20 else "stable")

    # Multi-Mandi Logistics Analysis (using static distances)
    mandi_analysis = []
    for mandi in MANDIS_PY:
        effective_dist = mandi["distanceKm"]
        if "nashik" in loc or "lasalgaon" in loc:
            effective_dist = 12 if "nashik" in mandi["id"] else (mandi["distanceKm"] + 350)
        elif "guntur" in loc or "vijayawada" in loc:
            effective_dist = 15 if "guntur" in mandi["id"] else (mandi["distanceKm"] + 120)
        elif "warangal" in loc or "karimnagar" in loc:
            effective_dist = 14 if "warangal" in mandi["id"] else (mandi["distanceKm"] + 80)
        elif "hyderabad" in loc or "secunderabad" in loc:
            effective_dist = 10 if "hyderabad" in mandi["id"] else (mandi["distanceKm"] + 50)
        elif "kurnool" in loc or "andhra" in loc:
            if "kurnool" in mandi["id"]:
                effective_dist = 18
            elif "hyderabad" in mandi["id"]:
                effective_dist = 65
            elif "local" in mandi["id"]:
                effective_dist = 8
            elif "guntur" in mandi["id"]:
                effective_dist = 290
            elif "warangal" in mandi["id"]:
                effective_dist = 320
            else:
                effective_dist = mandi["distanceKm"] + 550

        mandi_spot = round(current_price * mandi["priceOffsetMultiplier"])
        mandi_pred = round(predicted_price * mandi["priceOffsetMultiplier"])
        
        transport_per_qtl = round(effective_dist * mandi["transportCostPerKmQtl"])
        transport_cost = round(transport_per_qtl * qty)

        optimal_days = commodity.get("recommendation", {}).get("optimalDays", 5)
        storage_rate = mandi["storageCostPerDayQtl"] if payload.hasStorage else (mandi["storageCostPerDayQtl"] + 3.0)
        storage_cost = round(optimal_days * storage_rate * qty) if optimal_days > 0 else 0
        storage_per_qtl = round(optimal_days * storage_rate) if optimal_days > 0 else 0

        gross_today = mandi_spot * qty
        net_today = gross_today - transport_cost

        gross_future = mandi_pred * qty
        net_future = gross_future - transport_cost - storage_cost

        mandi_analysis.append({
            **mandi,
            "distanceKm": effective_dist,
            "spotPricePerQtl": mandi_spot,
            "predPricePerQtl": mandi_pred,
            "transportCostTotal": transport_cost,
            "transportCostPerQtl": transport_per_qtl,
            "storageCostTotal": storage_cost,
            "storageCostPerQtl": storage_per_qtl,
            "grossToday": gross_today,
            "netReturnToday": net_today,
            "grossFuture": gross_future,
            "netReturnFuture": net_future
        })

    is_perishable = commodity.get("shelfLifeDays", 30) <= 10
    top_future = sorted(mandi_analysis, key=lambda m: m["netReturnFuture"], reverse=True)[0]
    top_today = sorted(mandi_analysis, key=lambda m: m["netReturnToday"], reverse=True)[0]
    local_mandi = sorted(mandi_analysis, key=lambda m: m["distanceKm"])[0]

    # Dynamic Selling Recommendation Verdict
    opt_days_rec = commodity.get("recommendation", {}).get("optimalDays", 5)

    if is_perishable and not payload.hasStorage:
        dec_type = "SELL_NOW"
        dec_action = "SELL IMMEDIATELY (TODAY)"
        opt_days = 0
        conf = 96
        headline = f"High perishability risk: Sell {commodity['name'].split()[0]} today"
        expl = f"Without cold storage, holding {commodity['name'].split()[0]} risks spoilage. Selling today locks in ₹{current_price}/Qtl."
    elif price_trend == "down":
        dec_type = "SELL_NOW"
        dec_action = "SELL IMMEDIATELY (TODAY)"
        opt_days = 0
        conf = 93
        headline = f"Arrival surge: Prices expected to drop by {abs(price_change_pct)}%"
        expl = f"Heavy supplies entering wholesale mandis. Selling today at ₹{current_price}/Qtl secures optimal net return."
    elif opt_days_rec > 0 and price_trend == "up" and (top_future["netReturnFuture"] > top_today["netReturnToday"] + 500):
        dec_type = "WAIT"
        dec_action = f"WAIT FOR {opt_days_rec} DAYS"
        opt_days = opt_days_rec
        conf = 94
        headline = f"Prices surging (+{price_change_pct}%): Holding produce yields high net profit"
        gain = top_future["netReturnFuture"] - top_today["netReturnToday"]
        expl = f"Expected price hike (+₹{price_diff}/Qtl) far exceeds storage rent. Waiting {opt_days} days yields approximately ₹{gain:,.0f} additional net profit."
    else:
        dec_type = "SELL_BEST_MARKET"
        dec_action = "SELL AT BEST APMC MANDI (TODAY)"
        opt_days = 0
        conf = 90
        headline = f"Stable price: Deliver to {top_today['name']}"
        expl = f"Delivering today to {top_today['name']} gives highest net return without extended storage deductions."

    is_wait = dec_type == "WAIT"
    mandi_analysis.sort(key=lambda m: m["netReturnFuture"] if is_wait else m["netReturnToday"], reverse=True)
    best_mandi = mandi_analysis[0]
    estimated_net = best_mandi["netReturnFuture"] if is_wait else best_mandi["netReturnToday"]
    additional_profit = max(0, estimated_net - local_mandi["netReturnToday"])

    # Transparent Prototype Buyer Matching & Scoring
    buyer_matches = []
    for b in BUYERS_PY:
        # Check commodity match
        is_matched_crop = any(commodity["id"] in c or c in commodity["id"] for c in b["commodities"])
        
        offer_rate = round(current_price * b["baseOfferMultiplier"])
        b_dist = b["distanceKm"]
        b_transport = round(b_dist * 1.8 * qty)
        b_gross = offer_rate * qty
        b_net = b_gross - b_transport

        # Calculate Prototype Match Score (out of 100)
        # Factor 1: Price Score (Max 40 pts)
        price_ratio = offer_rate / current_price if current_price > 0 else 1.0
        price_score = min(40, round(35 * price_ratio))

        # Factor 2: Distance Score (Max 25 pts)
        distance_score = max(10, round(25 - (b_dist * 0.25)))

        # Factor 3: Quantity Match Score (Max 20 pts)
        quantity_score = 20 if qty >= b["minQuantityQtl"] else round((qty / b["minQuantityQtl"]) * 20)

        # Factor 4: Quality Grade Alignment (Max 15 pts)
        grade_score = 15 if payload.grade == "A" else (13 if payload.grade == "B" else 10)

        total_match = min(99, price_score + distance_score + quantity_score + (5 if is_matched_crop else -15))

        buyer_matches.append({
            **b,
            "offerPricePerQtl": offer_rate,
            "grossContractValue": b_gross,
            "transportCostTotal": b_transport,
            "netReturn": b_net,
            "matchScore": total_match,
            "scoreBreakdown": {
                "priceScore": price_score,
                "distanceScore": distance_score,
                "quantityScore": quantity_score,
                "gradeScore": grade_score,
                "total": total_match,
                "max": 100
            },
            "isPrototype": True,
            "prototypeDisclaimer": "Prototype Buyer Matching Data for demonstration and evaluation only. Not a live exchange contract."
        })

    buyer_matches.sort(key=lambda b: b["matchScore"], reverse=True)

    has_ml = bool(commodity.get("hasMLModel", False))
    forecast_label = "Actual ML Forecast" if has_ml else "Estimated Demo Forecast"

    return {
        "status": "success",
        "data_source": commodity.get("dataSource", "mock_fallback"),
        "forecast_source": "actual_ml_model" if has_ml else "estimated_demo_forecast",
        "forecast_notice": forecast_label,
        "commodityInfo": commodity,
        "input": payload.model_dump(),
        "pricing": {
            "currentPrice": current_price,
            "predictedPrice": predicted_price,
            "priceChangePct": price_change_pct,
            "priceTrend": price_trend,
            "isPositive": price_diff >= 0,
            "priceDiff": price_diff,
            "optimalDays": opt_days,
            "bestMarketName": best_mandi["name"],
            "bestMarketDistance": best_mandi["distanceKm"],
            "bestMarketPricePerQtl": best_mandi["predPricePerQtl"] if is_wait else best_mandi["spotPricePerQtl"],
            "transportCostTotal": best_mandi["transportCostTotal"],
            "transportCostPerQtl": best_mandi["transportCostPerQtl"],
            "storageCostTotal": best_mandi["storageCostTotal"] if is_wait else 0,
            "storageCostPerQtl": best_mandi["storageCostPerQtl"] if is_wait else 0,
            "grossReturn": best_mandi["grossFuture"] if is_wait else best_mandi["grossToday"],
            "estimatedNetReturn": estimated_net,
            "additionalProfit": additional_profit,
            "historical30d": commodity.get("historical30d", []),
            "predicted7d": commodity.get("predicted7d", [])
        },
        "recommendation": {
            "action": dec_action,
            "type": dec_type,
            "headline": headline,
            "explanation": expl,
            "optimalDays": opt_days,
            "expectedGain": additional_profit,
            "confidence": conf,
            "factors": commodity.get("recommendation", {}).get("factors", [])
        },
        "mandis": mandi_analysis,
        "buyers": buyer_matches
    }


# ============================================================================
# Static Files & SPA Route Servicing
# ============================================================================

if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
@app.get("/analyze")
@app.get("/analysis")
@app.get("/dashboard")
@app.get("/recommendation")
@app.get("/buyers")
def serve_spa_pages():
    """Serve the single page application HTML shell for all frontend routes."""
    index_path = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>AgriPredict AI Backend Running</h1>")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)