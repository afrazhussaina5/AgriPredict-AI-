# AgriPredict AI - Buyer API Routes
"""
Verified buyer onboarding, discovery, and matching.
Only VERIFIED buyers appear in verified listings.
"""

from datetime import datetime, timezone
from datetime import date as dt_date
from typing import Optional, List
import hashlib
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Path, UploadFile, File
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy import func, or_, and_, desc
from sqlalchemy.orm import Session, joinedload

from ..db import get_db
from ..models import (
    Buyer, BuyerVerificationStatus, BuyerCategory, BuyerDocument,
    BuyerCommodity, Commodity, State, District, Location,
    buyer_commodities, buyer_locations,
)

# Helper function to build BuyerDetailResponse manually
def build_buyer_detail_response(buyer, db):
    """Build BuyerDetailResponse manually with proper commodity and location details."""
    from ..models import BuyerCommodity, buyer_locations, buyer_commodities
    
    # Get commodity details from association table
    commodities = []
    buyer_comms = db.query(BuyerCommodity).options(
        joinedload(BuyerCommodity.commodity)
    ).filter(BuyerCommodity.buyer_id == buyer.id).all()
    
    for bc in buyer_comms:
        commodities.append(BuyerCommodityResponse(
            commodity_id=bc.commodity.id,
            commodity_name=bc.commodity.name,
            min_quantity_qtl=bc.min_quantity_qtl,
            max_quantity_qtl=bc.max_quantity_qtl,
            accepted_grades=bc.accepted_grades,
            base_offer_multiplier=bc.base_offer_multiplier,
            collection_mode=bc.collection_mode,
            max_distance_km=bc.max_distance_km,
        ))
    
    # Get serviceable locations from association table
    serviceable = []
    bls = db.query(buyer_locations).filter(buyer_locations.c.buyer_id == buyer.id).all()
    for bl in bls:
        state = db.query(State).filter(State.id == bl.state_id).first()
        district = db.query(District).filter(District.id == bl.district_id).first() if bl.district_id else None
        serviceable.append(BuyerLocationResponse(
            state_id=bl.state_id,
            state_name=state.name if state else "",
            district_id=bl.district_id,
            district_name=district.name if district else None,
            max_distance_km=bl.max_distance_km,
            preferred_collection=bl.preferred_collection,
        ))
    
    # Build response manually
    return BuyerDetailResponse(
        id=buyer.id,
        buyer_id=buyer.buyer_id,
        legal_name=buyer.legal_name,
        trade_name=buyer.trade_name,
        category=buyer.category,
        verification_status=buyer.verification_status,
        is_active=buyer.is_active,
        is_demo=buyer.is_demo,
        rating=buyer.rating,
        deals_completed=buyer.deals_completed,
        payment_terms=buyer.payment_terms,
        contact_person=buyer.contact_person,
        contact_phone=buyer.contact_phone,
        contact_email=buyer.contact_email,
        website=buyer.website,
        address=buyer.address,
        state_id=buyer.state_id,
        state_name=buyer.state.name if buyer.state else None,
        district_id=buyer.district_id,
        district_name=buyer.district.name if buyer.district else None,
        pincode=buyer.pincode,
        latitude=buyer.latitude,
        longitude=buyer.longitude,
        gstin=buyer.gstin,
        registration_number=buyer.registration_number,
        fssai_license=buyer.fssai_license,
        apmc_license=buyer.apmc_license,
        min_order_value=buyer.min_order_value,
        credit_period_days=buyer.credit_period_days,
        requires_quality_cert=buyer.requires_quality_cert,
        verification_source=buyer.verification_source,
        verified_at=buyer.verified_at,
        verification_expires_at=buyer.verification_expires_at,
        on_time_payment_rate=buyer.on_time_payment_rate,
        dispute_rate=buyer.dispute_rate,
        total_volume_qtl=buyer.total_volume_qtl,
        total_value_inr=buyer.total_value_inr,
        availability_notes=buyer.availability_notes,
        demo_disclaimer=buyer.demo_disclaimer,
        commodities=commodities,
        serviceable_locations=serviceable,
    )


router = APIRouter(prefix="/buyers", tags=["Buyers"])


# =============================================================================
# Pydantic Schemas
# =============================================================================

class BuyerCommodityResponse(BaseModel):
    commodity_id: str
    commodity_name: str
    min_quantity_qtl: float
    max_quantity_qtl: Optional[float] = None
    accepted_grades: Optional[List[str]] = None
    base_offer_multiplier: float
    collection_mode: Optional[str] = None
    max_distance_km: Optional[float] = None

    class Config:
        from_attributes = True


class BuyerLocationResponse(BaseModel):
    state_id: int
    state_name: str
    district_id: Optional[int] = None
    district_name: Optional[str] = None
    max_distance_km: float
    preferred_collection: Optional[str] = None


class BuyerBaseResponse(BaseModel):
    id: int
    buyer_id: str
    legal_name: str
    trade_name: Optional[str] = None
    category: BuyerCategory
    verification_status: BuyerVerificationStatus
    is_active: bool
    is_demo: bool
    rating: Optional[float] = None
    deals_completed: int
    payment_terms: Optional[str] = None

    class Config:
        from_attributes = True


class BuyerDetailResponse(BuyerBaseResponse):
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    website: Optional[str] = None
    address: Optional[str] = None
    state_id: Optional[int] = None
    state_name: Optional[str] = None
    district_id: Optional[int] = None
    district_name: Optional[str] = None
    pincode: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    gstin: Optional[str] = None
    registration_number: Optional[str] = None
    fssai_license: Optional[str] = None
    apmc_license: Optional[str] = None
    min_order_value: Optional[float] = None
    credit_period_days: Optional[int] = None
    requires_quality_cert: bool
    verification_source: Optional[str] = None
    verified_at: Optional[datetime] = None
    verification_expires_at: Optional[datetime] = None
    on_time_payment_rate: Optional[float] = None
    dispute_rate: Optional[float] = None
    total_volume_qtl: float
    total_value_inr: float
    availability_notes: Optional[str] = None
    demo_disclaimer: Optional[str] = None
    commodities: List[BuyerCommodityResponse] = []
    serviceable_locations: List[BuyerLocationResponse] = []

    class Config:
        from_attributes = True


class BuyerListResponse(BaseModel):
    buyers: List[BuyerBaseResponse]
    total: int
    page: int
    page_size: int


class BuyerCreateRequest(BaseModel):
    buyer_id: str = Field(..., min_length=3, max_length=50)
    legal_name: str = Field(..., min_length=2, max_length=200)
    trade_name: Optional[str] = None
    category: BuyerCategory
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    website: Optional[str] = None
    address: Optional[str] = None
    state_id: Optional[int] = None
    district_id: Optional[int] = None
    pincode: Optional[str] = Field(None, pattern=r"^\d{6}$")
    gstin: Optional[str] = Field(None, pattern=r"^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}$")
    registration_number: Optional[str] = None
    pan: Optional[str] = Field(None, pattern=r"^[A-Z]{5}\d{4}[A-Z]{1}$")
    fssai_license: Optional[str] = None
    apmc_license: Optional[str] = None
    payment_terms: Optional[str] = None
    min_order_value: Optional[float] = None
    credit_period_days: Optional[int] = None
    requires_quality_cert: bool = False
    commodities: List[dict] = []  # [{"commodity_id": "", "min_quantity_qtl": 10, ...}]
    serviceable_locations: List[dict] = []  # [{"state_id": 1, "district_id": 2, "max_distance_km": 50}]
    is_demo: bool = False
    demo_disclaimer: Optional[str] = None


class BuyerVerificationRequest(BaseModel):
    verification_status: BuyerVerificationStatus
    verification_source: Optional[str] = None
    verification_notes: Optional[str] = None
    verified_by: Optional[str] = None


class BuyerMatchRequest(BaseModel):
    commodity_id: str
    quantity_qtl: float = Field(..., gt=0)
    grade: str = Field(default="A", pattern="^[ABC]$")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    max_distance_km: float = Field(default=200, ge=1, le=500)
    min_match_score: int = Field(default=50, ge=0, le=100)
    verified_only: bool = True


class BuyerMatchResult(BaseModel):
    buyer: BuyerDetailResponse
    match_score: int
    score_breakdown: dict
    offer_price_per_qtl: float
    estimated_transport_cost: float
    estimated_net_return: float
    distance_km: float
    match_reasons: List[str]


# =============================================================================
# Buyer Endpoints
# =============================================================================

@router.get("", response_model=BuyerListResponse)
async def list_buyers(
    category: Optional[BuyerCategory] = Query(None),
    verification_status: Optional[BuyerVerificationStatus] = Query(None),
    commodity_id: Optional[str] = Query(None),
    state_id: Optional[int] = Query(None),
    district_id: Optional[int] = Query(None),
    is_active: Optional[bool] = Query(True),
    include_demo: bool = Query(False),
    verified_only: bool = Query(False),
    search: Optional[str] = Query(None),
    min_rating: Optional[float] = Query(None, ge=0, le=5),
    min_deals: Optional[int] = Query(None, ge=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    List buyers with filters.
    By default shows only active, non-demo buyers.
    If verified_only=True, only VERIFIED buyers are returned.
    """
    query = db.query(Buyer).options(
        joinedload(Buyer.commodities),
        joinedload(Buyer.state),
        joinedload(Buyer.district),
    )
    
    if category:
        query = query.filter(Buyer.category == category)
    if verification_status:
        query = query.filter(Buyer.verification_status == verification_status)
    elif verified_only:
        query = query.filter(Buyer.verification_status == BuyerVerificationStatus.VERIFIED)
    if is_active is not None:
        query = query.filter(Buyer.is_active == is_active)
    if not include_demo:
        query = query.filter(Buyer.is_demo == False)
    if search:
        query = query.filter(
            or_(
                Buyer.legal_name.ilike(f"%{search}%"),
                Buyer.trade_name.ilike(f"%{search}%"),
                Buyer.buyer_id.ilike(f"%{search}%"),
            )
        )
    if min_rating:
        query = query.filter(Buyer.rating >= min_rating)
    if min_deals:
        query = query.filter(Buyer.deals_completed >= min_deals)
    if commodity_id:
        query = query.join(Buyer.commodities).filter(Commodity.id == commodity_id)
    if state_id:
        query = query.filter(Buyer.state_id == state_id)
    if district_id:
        query = query.filter(Buyer.district_id == district_id)
    
    total = query.count()
    buyers = query.order_by(
        Buyer.verification_status.desc(),  # VERIFIED first
        Buyer.rating.desc().nullslast(),
        Buyer.deals_completed.desc(),
    ).offset((page - 1) * page_size).limit(page_size).all()
    
    return BuyerListResponse(
        buyers=buyers,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/verified", response_model=List[BuyerBaseResponse])
async def list_verified_buyers(
    commodity_id: Optional[str] = Query(None),
    state_id: Optional[int] = Query(None),
    max_distance_km: Optional[float] = Query(None),
    latitude: Optional[float] = Query(None, ge=-90, le=90),
    longitude: Optional[float] = Query(None, ge=-180, le=180),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Get verified buyers (for farmer-facing matching).
    Only returns VERIFIED, active, non-demo buyers.
    """
    query = db.query(Buyer).filter(
        Buyer.verification_status == BuyerVerificationStatus.VERIFIED,
        Buyer.is_active == True,
        Buyer.is_demo == False,
        Buyer.is_accepting_orders == True,
    ).options(
        joinedload(Buyer.commodities),
        joinedload(Buyer.state),
        joinedload(Buyer.district),
    )
    
    if commodity_id:
        query = query.join(Buyer.commodities).filter(Commodity.id == commodity_id)
    if state_id:
        query = query.filter(Buyer.state_id == state_id)
    
    buyers = query.order_by(
        Buyer.rating.desc().nullslast(),
        Buyer.on_time_payment_rate.desc().nullslast(),
        Buyer.deals_completed.desc(),
    ).limit(limit).all()
    
    # Filter by distance if coordinates provided
    if latitude is not None and longitude is not None and max_distance_km:
        from math import radians, sin, cos, sqrt, atan2
        
        filtered = []
        for b in buyers:
            if b.latitude and b.longitude:
                R = 6371
                lat1, lon1 = radians(latitude), radians(longitude)
                lat2, lon2 = radians(b.latitude), radians(b.longitude)
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
                dist = 2 * R * atan2(sqrt(a), sqrt(1-a))
                if dist <= max_distance_km:
                    filtered.append(b)
            elif max_distance_km > 500:  # No coords, include if very large radius
                filtered.append(b)
        buyers = filtered
    
    return buyers


@router.get("/{buyer_id}", response_model=BuyerDetailResponse)
async def get_buyer(
    buyer_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    """Get detailed buyer information."""
    from ..models import buyer_commodities, buyer_locations
    
    buyer = db.query(Buyer).options(
        joinedload(Buyer.state),
        joinedload(Buyer.district),
    ).filter(Buyer.id == buyer_id).first()
    
    if not buyer:
        raise HTTPException(status_code=404, detail="Buyer not found")
    
    # Get commodity details from association table
    commodities = []
    buyer_comms = db.query(BuyerCommodity).options(
        joinedload(BuyerCommodity.commodity)
    ).filter(BuyerCommodity.buyer_id == buyer.id).all()
    
    for bc in buyer_comms:
        commodities.append(BuyerCommodityResponse(
            commodity_id=bc.commodity.id,
            commodity_name=bc.commodity.name,
            min_quantity_qtl=bc.min_quantity_qtl,
            max_quantity_qtl=bc.max_quantity_qtl,
            accepted_grades=bc.accepted_grades,
            base_offer_multiplier=bc.base_offer_multiplier,
            collection_mode=bc.collection_mode,
            max_distance_km=bc.max_distance_km,
        ))
    
    # Get serviceable locations from association table
    serviceable = []
    bls = db.query(buyer_locations).filter(buyer_locations.c.buyer_id == buyer.id).all()
    for bl in bls:
        state = db.query(State).filter(State.id == bl.state_id).first()
        district = db.query(District).filter(District.id == bl.district_id).first() if bl.district_id else None
        serviceable.append(BuyerLocationResponse(
            state_id=bl.state_id,
            state_name=state.name if state else "",
            district_id=bl.district_id,
            district_name=district.name if district else None,
            max_distance_km=bl.max_distance_km,
            preferred_collection=bl.preferred_collection,
        ))
    
    # Build response manually
    response = BuyerDetailResponse(
        id=buyer.id,
        buyer_id=buyer.buyer_id,
        legal_name=buyer.legal_name,
        trade_name=buyer.trade_name,
        category=buyer.category,
        verification_status=buyer.verification_status,
        is_active=buyer.is_active,
        is_demo=buyer.is_demo,
        rating=buyer.rating,
        deals_completed=buyer.deals_completed,
        payment_terms=buyer.payment_terms,
        contact_person=buyer.contact_person,
        contact_phone=buyer.contact_phone,
        contact_email=buyer.contact_email,
        website=buyer.website,
        address=buyer.address,
        state_id=buyer.state_id,
        state_name=buyer.state.name if buyer.state else None,
        district_id=buyer.district_id,
        district_name=buyer.district.name if buyer.district else None,
        pincode=buyer.pincode,
        latitude=buyer.latitude,
        longitude=buyer.longitude,
        gstin=buyer.gstin,
        registration_number=buyer.registration_number,
        fssai_license=buyer.fssai_license,
        apmc_license=buyer.apmc_license,
        min_order_value=buyer.min_order_value,
        credit_period_days=buyer.credit_period_days,
        requires_quality_cert=buyer.requires_quality_cert,
        verification_source=buyer.verification_source,
        verified_at=buyer.verified_at,
        verification_expires_at=buyer.verification_expires_at,
        on_time_payment_rate=buyer.on_time_payment_rate,
        dispute_rate=buyer.dispute_rate,
        total_volume_qtl=buyer.total_volume_qtl,
        total_value_inr=buyer.total_value_inr,
        availability_notes=buyer.availability_notes,
        demo_disclaimer=buyer.demo_disclaimer,
        commodities=commodities,
        serviceable_locations=serviceable,
    )
    return response


@router.get("/by-code/{buyer_code}", response_model=BuyerDetailResponse)
async def get_buyer_by_code(
    buyer_code: str = Path(..., description="Buyer ID code (e.g., buyer-bb-01)"),
    db: Session = Depends(get_db),
):
    """Get buyer by unique code."""
    from ..models import buyer_commodities, buyer_locations
    
    buyer = db.query(Buyer).options(
        joinedload(Buyer.state),
        joinedload(Buyer.district),
    ).filter(Buyer.buyer_id == buyer_code).first()
    
    if not buyer:
        raise HTTPException(status_code=404, detail="Buyer not found")
    
    # Get commodity details from association table
    commodities = []
    buyer_comms = db.query(BuyerCommodity).options(
        joinedload(BuyerCommodity.commodity)
    ).filter(BuyerCommodity.buyer_id == buyer.id).all()
    
    for bc in buyer_comms:
        commodities.append(BuyerCommodityResponse(
            commodity_id=bc.commodity.id,
            commodity_name=bc.commodity.name,
            min_quantity_qtl=bc.min_quantity_qtl,
            max_quantity_qtl=bc.max_quantity_qtl,
            accepted_grades=bc.accepted_grades,
            base_offer_multiplier=bc.base_offer_multiplier,
            collection_mode=bc.collection_mode,
            max_distance_km=bc.max_distance_km,
        ))
    
    # Get serviceable locations from association table
    serviceable = []
    bls = db.query(buyer_locations).filter(buyer_locations.c.buyer_id == buyer.id).all()
    for bl in bls:
        state = db.query(State).filter(State.id == bl.state_id).first()
        district = db.query(District).filter(District.id == bl.district_id).first() if bl.district_id else None
        serviceable.append(BuyerLocationResponse(
            state_id=bl.state_id,
            state_name=state.name if state else "",
            district_id=bl.district_id,
            district_name=district.name if district else None,
            max_distance_km=bl.max_distance_km,
            preferred_collection=bl.preferred_collection,
        ))
    
    # Build response manually
    response = BuyerDetailResponse(
        id=buyer.id,
        buyer_id=buyer.buyer_id,
        legal_name=buyer.legal_name,
        trade_name=buyer.trade_name,
        category=buyer.category,
        verification_status=buyer.verification_status,
        is_active=buyer.is_active,
        is_demo=buyer.is_demo,
        rating=buyer.rating,
        deals_completed=buyer.deals_completed,
        payment_terms=buyer.payment_terms,
        contact_person=buyer.contact_person,
        contact_phone=buyer.contact_phone,
        contact_email=buyer.contact_email,
        website=buyer.website,
        address=buyer.address,
        state_id=buyer.state_id,
        state_name=buyer.state.name if buyer.state else None,
        district_id=buyer.district_id,
        district_name=buyer.district.name if buyer.district else None,
        pincode=buyer.pincode,
        latitude=buyer.latitude,
        longitude=buyer.longitude,
        gstin=buyer.gstin,
        registration_number=buyer.registration_number,
        fssai_license=buyer.fssai_license,
        apmc_license=buyer.apmc_license,
        min_order_value=buyer.min_order_value,
        credit_period_days=buyer.credit_period_days,
        requires_quality_cert=buyer.requires_quality_cert,
        verification_source=buyer.verification_source,
        verified_at=buyer.verified_at,
        verification_expires_at=buyer.verification_expires_at,
        on_time_payment_rate=buyer.on_time_payment_rate,
        dispute_rate=buyer.dispute_rate,
        total_volume_qtl=buyer.total_volume_qtl,
        total_value_inr=buyer.total_value_inr,
        availability_notes=buyer.availability_notes,
        demo_disclaimer=buyer.demo_disclaimer,
        commodities=commodities,
        serviceable_locations=serviceable,
    )
    return response


@router.post("", response_model=BuyerDetailResponse, status_code=201)
async def create_buyer(
    request: BuyerCreateRequest,
    db: Session = Depends(get_db),
):
    """Register a new buyer (goes to UNVERIFIED status by default)."""
    # Check for duplicate buyer_id
    existing = db.query(Buyer).filter(Buyer.buyer_id == request.buyer_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Buyer ID already exists")
    
    # Check for duplicate GSTIN
    if request.gstin:
        existing_gstin = db.query(Buyer).filter(Buyer.gstin == request.gstin).first()
        if existing_gstin:
            raise HTTPException(status_code=409, detail="GSTIN already registered")
    
    # Create buyer
    buyer = Buyer(
        buyer_id=request.buyer_id,
        legal_name=request.legal_name,
        trade_name=request.trade_name,
        category=request.category,
        contact_person=request.contact_person,
        contact_phone=request.contact_phone,
        contact_email=request.contact_email,
        website=request.website,
        address=request.address,
        state_id=request.state_id,
        district_id=request.district_id,
        pincode=request.pincode,
        gstin=request.gstin,
        registration_number=request.registration_number,
        pan=request.pan,
        fssai_license=request.fssai_license,
        apmc_license=request.apmc_license,
        payment_terms=request.payment_terms,
        min_order_value=request.min_order_value,
        credit_period_days=request.credit_period_days,
        requires_quality_cert=request.requires_quality_cert,
        is_demo=request.is_demo,
        demo_disclaimer=request.demo_disclaimer,
        verification_status=BuyerVerificationStatus.UNVERIFIED,
    )
    
    db.add(buyer)
    db.flush()
    
    # Add commodities
    for comm_data in request.commodities:
        comm_id = comm_data.get("commodity_id")
        if comm_id:
            commodity = db.query(Commodity).filter(Commodity.id == comm_id).first()
            if commodity:
                buyer.commodities.append(commodity)
    
    # Add serviceable locations
    for loc_data in request.serviceable_locations:
        from ..models import buyer_locations
        state_id = loc_data.get("state_id")
        if state_id:
            stmt = buyer_locations.insert().values(
                buyer_id=buyer.id,
                state_id=state_id,
                district_id=loc_data.get("district_id"),
                max_distance_km=loc_data.get("max_distance_km", 100),
                preferred_collection=loc_data.get("preferred_collection"),
            )
            db.execute(stmt)
    
    db.commit()
    db.refresh(buyer)
    
    return BuyerDetailResponse.from_orm(buyer)


@router.patch("/{buyer_id}/verify", response_model=BuyerDetailResponse)
async def verify_buyer(
    buyer_id: int = Path(..., gt=0),
    request: BuyerVerificationRequest = ...,
    db: Session = Depends(get_db),
):
    """Update buyer verification status (admin)."""
    buyer = db.query(Buyer).filter(Buyer.id == buyer_id).first()
    if not buyer:
        raise HTTPException(status_code=404, detail="Buyer not found")
    
    buyer.verification_status = request.verification_status
    if request.verification_source:
        buyer.verification_source = request.verification_source
    if request.verification_notes:
        buyer.verification_notes = request.verification_notes
    if request.verified_by:
        buyer.verified_by = request.verified_by
    buyer.verified_at = datetime.now(timezone.utc)
    buyer.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(buyer)
    
    return BuyerDetailResponse.from_orm(buyer)


@router.post("/{buyer_id}/documents")
async def upload_buyer_document(
    buyer_id: int = Path(..., gt=0),
    document_type: str = Query(..., description="Type: incorporation, gst, fssai, apmc_license, pan, address_proof, bank_cancelled_cheque"),
    file: UploadFile = File(...),
    document_number: Optional[str] = Query(None),
    expiry_date: Optional[dt_date] = Query(None),
    db: Session = Depends(get_db),
):
    """Upload verification document for buyer."""
    buyer = db.query(Buyer).filter(Buyer.id == buyer_id).first()
    if not buyer:
        raise HTTPException(status_code=404, detail="Buyer not found")
    
    # Read file content
    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()
    
    # Save file (in production, use proper storage like S3)
    upload_dir = Path("./uploads/buyers") / str(buyer_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{document_type}_{file.filename}"
    
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Create document record
    doc = BuyerDocument(
        buyer_id=buyer_id,
        document_type=document_type,
        document_number=document_number,
        file_path=str(file_path),
        file_hash=file_hash,
        expiry_date=expiry_date,
    )
    
    db.add(doc)
    db.commit()
    
    return {"status": "success", "document_id": doc.id, "file_hash": file_hash}


@router.post("/match", response_model=List[BuyerMatchResult])
async def match_buyers(
    request: BuyerMatchRequest,
    db: Session = Depends(get_db),
):
    """
    Match verified buyers against farmer's produce.
    Returns ranked buyers with transparent score breakdown.
    """
    # Get verified buyers for this commodity
    query = db.query(Buyer).filter(
        Buyer.verification_status == BuyerVerificationStatus.VERIFIED,
        Buyer.is_active == True,
        Buyer.is_demo == False,
        Buyer.is_accepting_orders == True,
    ).join(Buyer.commodities).filter(Commodity.id == request.commodity_id)
    
    buyers = query.all()
    
    if not buyers:
        return []
    
    commodity = db.query(Commodity).filter(Commodity.id == request.commodity_id).first()
    if not commodity:
        raise HTTPException(status_code=404, detail="Commodity not found")
    
    # Get current market price for reference
    from ..models import MarketPrice, MarketPriceStatus
    latest_price = db.query(MarketPrice).filter(
        MarketPrice.commodity_id == request.commodity_id,
        MarketPrice.grade == request.grade,
        MarketPrice.status.in_([MarketPriceStatus.LIVE, MarketPriceStatus.CACHED, MarketPriceStatus.HISTORICAL]),
    ).order_by(desc(MarketPrice.arrival_date)).first()
    
    modal_price = latest_price.modal_price if latest_price else 3000.0
    
    results = []
    from math import radians, sin, cos, sqrt, atan2
    
    for buyer in buyers:
        # Calculate distance
        distance_km = None
        if buyer.latitude and buyer.longitude and request.latitude and request.longitude:
            R = 6371
            lat1, lon1 = radians(request.latitude), radians(request.longitude)
            lat2, lon2 = radians(buyer.latitude), radians(buyer.longitude)
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            distance_km = round(2 * R * atan2(sqrt(a), sqrt(1-a)), 1)
        
        # Skip if distance exceeds buyer's max or request max
        buyer_max_dist = None
        from ..models import buyer_locations
        bl = db.query(buyer_locations.c.max_distance_km).filter(
            buyer_locations.c.buyer_id == buyer.id
        ).first()
        if bl:
            buyer_max_dist = bl[0]
        
        if distance_km and buyer_max_dist and distance_km > buyer_max_dist:
            continue
        if distance_km and distance_km > request.max_distance_km:
            continue
        if not distance_km and request.max_distance_km < 500:
            continue  # Skip if no coords and tight radius
        
        # Get commodity details for this buyer
        buyer_comm = db.query(BuyerCommodity).filter(
            BuyerCommodity.buyer_id == buyer.id,
            BuyerCommodity.commodity_id == request.commodity_id,
        ).first()
        
        if not buyer_comm:
            continue
        
        # Check quantity compatibility
        if request.quantity_qtl < buyer_comm.min_quantity_qtl:
            qty_score = max(10, int((request.quantity_qtl / buyer_comm.min_quantity_qtl) * 25))
            qty_reason = f"Below minimum ({buyer_comm.min_quantity_qtl} Qtl)"
        elif buyer_comm.max_quantity_qtl and request.quantity_qtl > buyer_comm.max_quantity_qtl:
            qty_score = 20
            qty_reason = f"Exceeds max, split possible"
        else:
            qty_score = 25
            qty_reason = "Quantity fits"
        
        # Check grade
        accepted = buyer_comm.accepted_grades or ["A", "B", "FAQ"]
        if request.grade in accepted:
            if request.grade == "A":
                grade_score = 20
                grade_reason = "Grade A premium"
            elif request.grade == "B":
                grade_score = 17
                grade_reason = "Grade B standard"
            else:
                grade_score = 14
                grade_reason = "Grade C FAQ"
        else:
            grade_score = 5
            grade_reason = f"Grade {request.grade} not preferred"
        
        # Distance score
        if distance_km:
            if distance_km <= 25:
                dist_score = 25
                dist_reason = "Hyper-local"
            elif distance_km <= 75:
                dist_score = 20
                dist_reason = "Regional"
            elif distance_km <= 200:
                dist_score = 15
                dist_reason = "Inter-district"
            else:
                dist_score = 10
                dist_reason = "Long distance"
        else:
            dist_score = 15
            dist_reason = "Distance unknown"
        
        # Price score
        offer_multiplier = buyer_comm.base_offer_multiplier or 1.05
        offer_price = round(modal_price * offer_multiplier)
        price_ratio = offer_price / modal_price if modal_price > 0 else 1.0
        price_score = min(30, int(25 * price_ratio))
        
        # Total score
        total_score = min(100, price_score + dist_score + qty_score + grade_score)
        
        if total_score < request.min_match_score:
            continue
        
        # Calculate economics
        transport_rate = commodity.base_transport_rate_per_km_qtl or 1.8
        transport_cost = round(distance_km * transport_rate * request.quantity_qtl) if distance_km else 0
        gross = offer_price * request.quantity_qtl
        net = gross - transport_cost
        
        # Build match reasons
        reasons = []
        if price_ratio > 1.05:
            reasons.append(f"Premium offer: {round((price_ratio-1)*100)}% above mandi")
        if distance_km and distance_km <= 25:
            reasons.append(f"Very close: {distance_km} km")
        if buyer.on_time_payment_rate and buyer.on_time_payment_rate > 0.9:
            reasons.append("Excellent payment history")
        if buyer.category == BuyerCategory.FPO_COOPERATIVE:
            reasons.append("Farmer collective - zero middleman")
        
        results.append(BuyerMatchResult(
            buyer=build_buyer_detail_response(buyer, db),
            match_score=total_score,
            score_breakdown={
                "price_score": price_score,
                "distance_score": dist_score,
                "quantity_score": qty_score,
                "grade_score": grade_score,
                "total": total_score,
                "max": 100,
            },
            offer_price_per_qtl=offer_price,
            estimated_transport_cost=transport_cost,
            estimated_net_return=net,
            distance_km=distance_km or 0,
            match_reasons=reasons,
        ))
    
    # Sort by match score descending
    results.sort(key=lambda x: x.match_score, reverse=True)
    
    return results


# =============================================================================
# Statistics
# =============================================================================

@router.get("/stats/summary")
async def get_buyer_stats(db: Session = Depends(get_db)):
    """Get buyer statistics."""
    total = db.query(Buyer).count()
    verified = db.query(Buyer).filter(Buyer.verification_status == BuyerVerificationStatus.VERIFIED).count()
    active = db.query(Buyer).filter(Buyer.is_active == True).count()
    demo = db.query(Buyer).filter(Buyer.is_demo == True).count()
    
    by_category = db.query(
        Buyer.category,
        func.count(Buyer.id)
    ).group_by(Buyer.category).all()
    
    by_verification = db.query(
        Buyer.verification_status,
        func.count(Buyer.id)
    ).group_by(Buyer.verification_status).all()
    
    return {
        "total": total,
        "verified": verified,
        "active": active,
        "demo": demo,
        "by_category": {str(cat): count for cat, count in by_category},
        "by_verification": {str(v): count for v, count in by_verification},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health")
async def buyers_health(db: Session = Depends(get_db)):
    """Health check for buyer services."""
    verified_active = db.query(Buyer).filter(
        Buyer.verification_status == BuyerVerificationStatus.VERIFIED,
        Buyer.is_active == True,
        Buyer.is_demo == False,
    ).count()
    
    return {
        "status": "healthy",
        "verified_active_buyers": verified_active,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }