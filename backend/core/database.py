# AgriPredict AI - Database Initialization
"""
Database initialization, seeding, and migration utilities.
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import init_database, get_engine, get_db_session
from ..models import (
    State, District, Subdistrict, Location, LocationType,
    Mandi, MandiStatus, VerificationStatus, Commodity,
    MarketPrice, MarketPriceStatus,
    Buyer, BuyerVerificationStatus, BuyerCategory,
    FPO, FPOStatus, FPOType,
    TransportRate, StorageRate,
    SyncSchedule, SyncType,
)

logger = logging.getLogger(__name__)


def init_db() -> None:
    """Initialize database tables."""
    logger.info("Initializing database tables...")
    init_database()
    logger.info("Database tables created.")


def seed_core_data(session: Session) -> None:
    """Seed essential reference data."""
    logger.info("Seeding core reference data...")
    
    # Seed States (if empty)
    if session.query(State).count() == 0:
        logger.info("Seeding Indian states...")
        seed_states(session)
    
    # Seed Commodities (if empty)
    if session.query(Commodity).count() == 0:
        logger.info("Seeding commodity master...")
        seed_commodities(session)
    
    # Seed Transport Rates (if empty)
    if session.query(TransportRate).count() == 0:
        logger.info("Seeding default transport rates...")
        seed_transport_rates(session)
    
    # Seed Storage Rates (if empty)
    if session.query(StorageRate).count() == 0:
        logger.info("Seeding default storage rates...")
        seed_storage_rates(session)
    
    # Seed Sync Schedules (if empty)
    if session.query(SyncSchedule).count() == 0:
        logger.info("Seeding sync schedules...")
        seed_sync_schedules(session)
    
    session.commit()
    logger.info("Core data seeding completed.")


def seed_states(session: Session) -> None:
    """Seed Indian states and union territories."""
    states_data = [
        {"name": "Andhra Pradesh", "code": "AP", "is_union_territory": False},
        {"name": "Arunachal Pradesh", "code": "AR", "is_union_territory": False},
        {"name": "Assam", "code": "AS", "is_union_territory": False},
        {"name": "Bihar", "code": "BR", "is_union_territory": False},
        {"name": "Chhattisgarh", "code": "CG", "is_union_territory": False},
        {"name": "Goa", "code": "GA", "is_union_territory": False},
        {"name": "Gujarat", "code": "GJ", "is_union_territory": False},
        {"name": "Haryana", "code": "HR", "is_union_territory": False},
        {"name": "Himachal Pradesh", "code": "HP", "is_union_territory": False},
        {"name": "Jharkhand", "code": "JH", "is_union_territory": False},
        {"name": "Karnataka", "code": "KA", "is_union_territory": False},
        {"name": "Kerala", "code": "KL", "is_union_territory": False},
        {"name": "Madhya Pradesh", "code": "MP", "is_union_territory": False},
        {"name": "Maharashtra", "code": "MH", "is_union_territory": False},
        {"name": "Manipur", "code": "MN", "is_union_territory": False},
        {"name": "Meghalaya", "code": "ML", "is_union_territory": False},
        {"name": "Mizoram", "code": "MZ", "is_union_territory": False},
        {"name": "Nagaland", "code": "NL", "is_union_territory": False},
        {"name": "Odisha", "code": "OD", "is_union_territory": False},
        {"name": "Punjab", "code": "PB", "is_union_territory": False},
        {"name": "Rajasthan", "code": "RJ", "is_union_territory": False},
        {"name": "Sikkim", "code": "SK", "is_union_territory": False},
        {"name": "Tamil Nadu", "code": "TN", "is_union_territory": False},
        {"name": "Telangana", "code": "TS", "is_union_territory": False},
        {"name": "Tripura", "code": "TR", "is_union_territory": False},
        {"name": "Uttar Pradesh", "code": "UP", "is_union_territory": False},
        {"name": "Uttarakhand", "code": "UK", "is_union_territory": False},
        {"name": "West Bengal", "code": "WB", "is_union_territory": False},
        {"name": "Andaman and Nicobar Islands", "code": "AN", "is_union_territory": True},
        {"name": "Chandigarh", "code": "CH", "is_union_territory": True},
        {"name": "Dadra and Nagar Haveli and Daman and Diu", "code": "DN", "is_union_territory": True},
        {"name": "Delhi", "code": "DL", "is_union_territory": True},
        {"name": "Jammu and Kashmir", "code": "JK", "is_union_territory": True},
        {"name": "Ladakh", "code": "LA", "is_union_territory": True},
        {"name": "Lakshadweep", "code": "LD", "is_union_territory": True},
        {"name": "Puducherry", "code": "PY", "is_union_territory": True},
    ]
    
    for state_data in states_data:
        state = State(**state_data)
        session.add(state)
    
    session.flush()


def seed_commodities(session: Session) -> None:
    """Seed commodity master from the canonical list."""
    commodities_data = [
        # Vegetables
        {
            "id": "onion", "name": "Onion (प्याज / ఉల్లిపాయ)", "variety": "Nashik Red / Bellary",
            "category": "Vegetables", "icon": "🧅",
            "default_qty": 50, "shelf_life_days": 45,
            "storage_cost_per_day_qtl": 4.0, "base_transport_rate_per_km_qtl": 1.8,
            "grade_multipliers": {"A": 1.05, "B": 1.0, "C": 0.88},
            "has_ml_model": True, "arrival_trend": "Decreasing (-18%)",
            "demand_index": "Very High (Festive & Export Inflow)",
        },
        {
            "id": "tomato", "name": "Tomato (टमाटर / టమాటా)", "variety": "Hybrid Desi / Shivam",
            "category": "Vegetables", "icon": "🍅",
            "default_qty": 40, "shelf_life_days": 6,
            "storage_cost_per_day_qtl": 6.0, "base_transport_rate_per_km_qtl": 2.0,
            "grade_multipliers": {"A": 1.08, "B": 1.0, "C": 0.82},
            "has_ml_model": True, "arrival_trend": "Surging (+35% fresh harvest arrival)",
            "demand_index": "Moderate",
        },
        {
            "id": "potato", "name": "Potato (आलू / బంగాళాదుంప)", "variety": "Jyoti / Kufri Pukhraj",
            "category": "Vegetables", "icon": "🥔",
            "default_qty": 80, "shelf_life_days": 90,
            "storage_cost_per_day_qtl": 2.5, "base_transport_rate_per_km_qtl": 1.5,
            "grade_multipliers": {"A": 1.05, "B": 1.0, "C": 0.85},
            "has_ml_model": True, "arrival_trend": "Declining in central hubs",
            "demand_index": "High",
        },
        {
            "id": "garlic", "name": "Garlic (लहसुन / వెల్లుల్లి)", "variety": "Desi White / Ooty",
            "category": "Vegetables", "icon": "🧄",
            "default_qty": 20, "shelf_life_days": 90,
            "storage_cost_per_day_qtl": 5.0, "base_transport_rate_per_km_qtl": 2.2,
            "grade_multipliers": {"A": 1.10, "B": 1.0, "C": 0.85},
            "has_ml_model": False, "arrival_trend": "Low Supplies",
            "demand_index": "Very High",
        },
        {
            "id": "ginger", "name": "Ginger (अदरक / అల్లం)", "variety": "Fresh Green / Mahim",
            "category": "Vegetables", "icon": "🫚",
            "default_qty": 30, "shelf_life_days": 30,
            "storage_cost_per_day_qtl": 4.5, "base_transport_rate_per_km_qtl": 2.0,
            "grade_multipliers": {"A": 1.06, "B": 1.0, "C": 0.88},
            "has_ml_model": False, "arrival_trend": "Moderate",
            "demand_index": "High",
        },
        # Cereals & Grains
        {
            "id": "wheat", "name": "Wheat (गेहूं / గోధుమ)", "variety": "Sharbati / Mill Quality",
            "category": "Cereals & Grains", "icon": "🌾",
            "default_qty": 60, "shelf_life_days": 365,
            "storage_cost_per_day_qtl": 2.0, "base_transport_rate_per_km_qtl": 1.6,
            "grade_multipliers": {"A": 1.07, "B": 1.0, "C": 0.92},
            "has_ml_model": True, "arrival_trend": "Steady",
            "demand_index": "Strong (FCI & Private Flour Mills)",
        },
        {
            "id": "paddy", "name": "Paddy / Rice (धान / వరి)", "variety": "BPT 5204 (Sona Masoori)",
            "category": "Cereals & Grains", "icon": "🌾",
            "default_qty": 75, "shelf_life_days": 300,
            "storage_cost_per_day_qtl": 1.8, "base_transport_rate_per_km_qtl": 1.7,
            "grade_multipliers": {"A": 1.06, "B": 1.0, "C": 0.91},
            "has_ml_model": True, "arrival_trend": "Steady",
            "demand_index": "High (Millers & Exporters)",
        },
        {
            "id": "maize", "name": "Maize / Corn (मक्का / మొక్కజొన్న)", "variety": "Yellow Hybrid (Feed Quality)",
            "category": "Cereals & Grains", "icon": "🌽",
            "default_qty": 80, "shelf_life_days": 180,
            "storage_cost_per_day_qtl": 2.0, "base_transport_rate_per_km_qtl": 1.7,
            "grade_multipliers": {"A": 1.05, "B": 1.0, "C": 0.90},
            "has_ml_model": False, "arrival_trend": "Tightening",
            "demand_index": "Very High (Poultry & Starch)",
        },
        # Pulses
        {
            "id": "arhar_tur", "name": "Red Gram / Tur (अरहर / కందులు)", "variety": "Maruti (ICP-8863)",
            "category": "Pulses", "icon": "🥣",
            "default_qty": 35, "shelf_life_days": 240,
            "storage_cost_per_day_qtl": 3.0, "base_transport_rate_per_km_qtl": 2.0,
            "grade_multipliers": {"A": 1.06, "B": 1.0, "C": 0.90},
            "has_ml_model": False, "arrival_trend": "Scarce Mandi Arrivals",
            "demand_index": "Extremely High (Dal Mills)",
        },
        {
            "id": "chana_gram", "name": "Bengal Gram / Chana (चना / శనగలు)", "variety": "Desi Chana / Digvijay",
            "category": "Pulses", "icon": "🍲",
            "default_qty": 40, "shelf_life_days": 300,
            "storage_cost_per_day_qtl": 2.5, "base_transport_rate_per_km_qtl": 1.8,
            "grade_multipliers": {"A": 1.05, "B": 1.0, "C": 0.90},
            "has_ml_model": False, "arrival_trend": "Moderate",
            "demand_index": "High",
        },
        {
            "id": "moong", "name": "Green Gram / Moong (मूंग / పెసలు)", "variety": "Shiny Green / Pusa Vishal",
            "category": "Pulses", "icon": "🫛",
            "default_qty": 30, "shelf_life_days": 200,
            "storage_cost_per_day_qtl": 2.8, "base_transport_rate_per_km_qtl": 1.9,
            "grade_multipliers": {"A": 1.06, "B": 1.0, "C": 0.91},
            "has_ml_model": False, "arrival_trend": "Normal",
            "demand_index": "Steady High",
        },
        # Oilseeds
        {
            "id": "soybean", "name": "Soybean (सोयाबीन / సోయాబీన్)", "variety": "Yellow Bold (JS-335)",
            "category": "Oilseeds", "icon": "🌱",
            "default_qty": 45, "shelf_life_days": 120,
            "storage_cost_per_day_qtl": 2.8, "base_transport_rate_per_km_qtl": 1.9,
            "grade_multipliers": {"A": 1.05, "B": 1.0, "C": 0.89},
            "has_ml_model": True, "arrival_trend": "Declining",
            "demand_index": "Very High (Crushing Plants)",
        },
        {
            "id": "mustard", "name": "Mustard / Rapeseed (सरसों / ఆవాలు)", "variety": "Black Bold / Pioneer 45S46",
            "category": "Oilseeds", "icon": "🌼",
            "default_qty": 50, "shelf_life_days": 180,
            "storage_cost_per_day_qtl": 2.5, "base_transport_rate_per_km_qtl": 1.8,
            "grade_multipliers": {"A": 1.06, "B": 1.0, "C": 0.90},
            "has_ml_model": False, "arrival_trend": "Tightening",
            "demand_index": "High (Oil Expellers)",
        },
        {
            "id": "groundnut", "name": "Groundnut / Peanut (मूंगफली / వేరుశెనగ)", "variety": "Bold Kernels / Kadiri-6",
            "category": "Oilseeds", "icon": "🥜",
            "default_qty": 40, "shelf_life_days": 150,
            "storage_cost_per_day_qtl": 3.0, "base_transport_rate_per_km_qtl": 1.9,
            "grade_multipliers": {"A": 1.07, "B": 1.0, "C": 0.89},
            "has_ml_model": False, "arrival_trend": "Steady",
            "demand_index": "High (HPS Peanut Exports & Oil)",
        },
        # Cash Crops
        {
            "id": "cotton", "name": "Cotton (कपास / పత్తి)", "variety": "Long Staple (Bunny/Bt-II)",
            "category": "Cash Crops", "icon": "☁️",
            "default_qty": 30, "shelf_life_days": 180,
            "storage_cost_per_day_qtl": 3.0, "base_transport_rate_per_km_qtl": 2.2,
            "grade_multipliers": {"A": 1.06, "B": 1.0, "C": 0.90},
            "has_ml_model": True, "arrival_trend": "Stable (-8%)",
            "demand_index": "Extremely High (Textile Mills Ex-Factory)",
        },
        {
            "id": "sugarcane", "name": "Sugarcane (गन्ना / చెరకు)", "variety": "Co 0238 / Early Maturing",
            "category": "Cash Crops", "icon": "🎋",
            "default_qty": 200, "shelf_life_days": 4,
            "storage_cost_per_day_qtl": 1.0, "base_transport_rate_per_km_qtl": 1.2,
            "grade_multipliers": {"A": 1.04, "B": 1.0, "C": 0.92},
            "has_ml_model": False, "arrival_trend": "Peak Crushing",
            "demand_index": "High (Sugar Mills FRP)",
        },
        # Spices
        {
            "id": "chilli", "name": "Red Chilli (लाल मिर्च / ఎర్ర మిరపకాయలు)", "variety": "Teja / Guntur Sannam",
            "category": "Spices", "icon": "🌶️",
            "default_qty": 25, "shelf_life_days": 180,
            "storage_cost_per_day_qtl": 8.0, "base_transport_rate_per_km_qtl": 3.0,
            "grade_multipliers": {"A": 1.08, "B": 1.0, "C": 0.88},
            "has_ml_model": True, "arrival_trend": "Tightening Inflow",
            "demand_index": "Extremely High (Oleoresin & Export)",
        },
        {
            "id": "turmeric", "name": "Turmeric (हल्दी / పసుపు)", "variety": "Salem / Nizamabad Finger",
            "category": "Spices", "icon": "🟡",
            "default_qty": 25, "shelf_life_days": 365,
            "storage_cost_per_day_qtl": 6.0, "base_transport_rate_per_km_qtl": 2.5,
            "grade_multipliers": {"A": 1.09, "B": 1.0, "C": 0.86},
            "has_ml_model": False, "arrival_trend": "Low Supplies",
            "demand_index": "Very High (Pharma & Curcumin Extraction)",
        },
        {
            "id": "cumin_jeera", "name": "Cumin / Jeera (जीरा / జీలకర్ర)", "variety": "Unjha Machine Cleaned",
            "category": "Spices", "icon": "✨",
            "default_qty": 15, "shelf_life_days": 365,
            "storage_cost_per_day_qtl": 10.0, "base_transport_rate_per_km_qtl": 3.5,
            "grade_multipliers": {"A": 1.08, "B": 1.0, "C": 0.88},
            "has_ml_model": False, "arrival_trend": "Tight",
            "demand_index": "Extremely High (Global Benchmark)",
        },
        # Fruits
        {
            "id": "banana", "name": "Banana (केला / అరటి)", "variety": "Grand Naine (G9 Premium)",
            "category": "Fruits", "icon": "🍌",
            "default_qty": 60, "shelf_life_days": 8,
            "storage_cost_per_day_qtl": 5.0, "base_transport_rate_per_km_qtl": 2.2,
            "grade_multipliers": {"A": 1.08, "B": 1.0, "C": 0.85},
            "has_ml_model": False, "arrival_trend": "Moderate",
            "demand_index": "High (Metro Supermarkets)",
        },
        {
            "id": "apple", "name": "Apple (सेब / ఆపిల్)", "variety": "Royal Delicious / Shimla",
            "category": "Fruits", "icon": "🍎",
            "default_qty": 30, "shelf_life_days": 60,
            "storage_cost_per_day_qtl": 7.0, "base_transport_rate_per_km_qtl": 2.8,
            "grade_multipliers": {"A": 1.10, "B": 1.0, "C": 0.85},
            "has_ml_model": False, "arrival_trend": "Declining Fresh Harvest",
            "demand_index": "Very High (CA Storage Driven)",
        },
    ]
    
    for comm_data in commodities_data:
        commodity = Commodity(**comm_data)
        session.add(commodity)
    
    session.flush()


def seed_transport_rates(session: Session) -> None:
    """Seed default transport rates (fallback values)."""
    # Default national rate
    default_rate = TransportRate(
        state_id=None,
        district_id=None,
        commodity_id=None,
        vehicle_type="truck_10t",
        rate_per_km_per_qtl=1.8,
        min_distance_km=10,
        min_charge=150.0,
        loading_charge_per_qtl=2.0,
        unloading_charge_per_qtl=2.0,
        source="default_fallback",
        verified=False,
    )
    session.add(default_rate)
    
    # Commodity-specific adjustments
    commodity_adjustments = {
        "onion": 1.75,
        "potato": 1.5,
        "tomato": 2.0,
        "wheat": 1.6,
        "paddy": 1.7,
        "cotton": 2.2,
        "chilli": 3.0,
        "turmeric": 2.5,
        "banana": 2.2,
        "apple": 2.8,
    }
    
    for comm_id, rate in commodity_adjustments.items():
        comm_rate = TransportRate(
            state_id=None,
            district_id=None,
            commodity_id=comm_id,
            vehicle_type="truck_10t",
            rate_per_km_per_qtl=rate,
            min_distance_km=10,
            min_charge=150.0,
            loading_charge_per_qtl=2.0,
            unloading_charge_per_qtl=2.0,
            source="commodity_default",
            verified=False,
        )
        session.add(comm_rate)
    
    session.flush()


def seed_storage_rates(session: Session) -> None:
    """Seed default storage rates (fallback values)."""
    # Default cold storage rate
    default_cold = StorageRate(
        state_id=None,
        district_id=None,
        commodity_id=None,
        storage_type="cold_storage",
        rate_per_day_per_qtl=4.0,
        min_charge_per_day=50.0,
        min_quantity_qtl=10,
        source="default_fallback",
        verified=False,
    )
    session.add(default_cold)
    
    # Default godown rate
    default_godown = StorageRate(
        state_id=None,
        district_id=None,
        commodity_id=None,
        storage_type="godown",
        rate_per_day_per_qtl=2.5,
        min_charge_per_day=30.0,
        min_quantity_qtl=5,
        source="default_fallback",
        verified=False,
    )
    session.add(default_godown)
    
    # Commodity-specific cold storage
    commodity_cold_rates = {
        "onion": 4.0,
        "tomato": 6.0,
        "potato": 2.5,
        "garlic": 5.0,
        "ginger": 4.5,
        "chilli": 8.0,
        "turmeric": 6.0,
        "cumin_jeera": 10.0,
        "banana": 5.0,
        "apple": 7.0,
    }
    
    for comm_id, rate in commodity_cold_rates.items():
        comm_rate = StorageRate(
            state_id=None,
            district_id=None,
            commodity_id=comm_id,
            storage_type="cold_storage",
            rate_per_day_per_qtl=rate,
            min_charge_per_day=50.0,
            min_quantity_qtl=10,
            source="commodity_default",
            verified=False,
        )
        session.add(comm_rate)
    
    session.flush()


def seed_sync_schedules(session: Session) -> None:
    """Seed default sync schedules."""
    schedules = [
        {
            "name": "daily_market_prices",
            "sync_type": SyncType.MARKET_PRICES,
            "cron_expression": "0 6 * * *",  # Daily at 6 AM
            "default_parameters": {"lookback_days": 7},
            "notify_on_failure": True,
        },
        {
            "name": "weekly_mandi_master",
            "sync_type": SyncType.MANDI_MASTER,
            "cron_expression": "0 2 * * 0",  # Weekly Sunday 2 AM
            "notify_on_failure": True,
        },
        {
            "name": "monthly_commodity_master",
            "sync_type": SyncType.COMMODITY_MASTER,
            "cron_expression": "0 1 1 * *",  # Monthly 1st at 1 AM
            "notify_on_failure": False,
        },
        {
            "name": "daily_historical_aggregation",
            "sync_type": SyncType.HISTORICAL_AGGREGATION,
            "cron_expression": "0 3 * * *",  # Daily at 3 AM
            "notify_on_failure": False,
        },
    ]
    
    for sched_data in schedules:
        schedule = SyncSchedule(**sched_data)
        session.add(schedule)
    
    session.flush()


def create_sample_mandi(session: Session) -> None:
    """Create a sample verified mandi for testing."""
    # Get Andhra Pradesh state
    ap_state = session.query(State).filter(State.code == "AP").first()
    if not ap_state:
        return
    
    # Get Kurnool district
    kurnool_district = session.query(District).filter(
        District.state_id == ap_state.id,
        District.name == "Kurnool"
    ).first()
    
    if not kurnool_district:
        # Create Kurnool district
        kurnool_district = District(
            state_id=ap_state.id,
            name="Kurnool",
            code="KNL"
        )
        session.add(kurnool_district)
        session.flush()
    
    # Create mandi
    mandi = Mandi(
        mandi_id="mandi-kurnool",
        name="Kurnool Agricultural Market Yard",
        apmc_name="Kurnool APMC",
        state_id=ap_state.id,
        district_id=kurnool_district.id,
        address="NH-44, Kurnool, Andhra Pradesh 518001",
        pincode="518001",
        latitude=15.8281,
        longitude=78.0373,
        status=MandiStatus.ACTIVE,
        is_e_nam=True,
        market_type="Wholesale",
        phone="08518-270400",
        facilities=["Electronic Weighbridge", "Cold Storage (2000 MT)", "Instant Bank Transfer", "Grading Lab"],
        verification_status=VerificationStatus.VERIFIED,
        official_source="e-NAM Portal",
        source_url="https://enam.gov.in/web/mandi-details/kurnool",
        last_verified_at=datetime.now(timezone.utc),
        verified_by="system_seed",
        operating_hours="6:00 AM - 6:00 PM",
        market_days="Mon-Sat",
        arrival_capacity_qtl=5000,
        price_offset_multiplier=1.045,
        transport_cost_per_km_qtl=1.75,
        storage_cost_per_day_qtl=4.0,
        rating=4.8,
    )
    session.add(mandi)
    session.flush()
    
    # Link commodities
    commodities = session.query(Commodity).filter(
        Commodity.id.in_(["onion", "cotton", "tomato", "chilli", "groundnut"])
    ).all()
    mandi.commodities.extend(commodities)
    
    logger.info(f"Created sample mandi: {mandi.name}")


def run_migrations() -> None:
    """Run database migrations (placeholder for Alembic)."""
    logger.info("Running migrations...")
    # In production, use Alembic for migrations
    # For now, just ensure tables exist
    init_db()
    
    with get_db_session() as session:
        seed_core_data(session)
        create_sample_mandi(session)
    
    logger.info("Migrations completed.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_migrations()