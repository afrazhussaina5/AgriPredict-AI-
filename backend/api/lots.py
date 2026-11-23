# AgriPredict AI - Lot API Routes
"""
Produce lot creation, FPO aggregation, and sale lifecycle tracking.
"""

from datetime import datetime, date, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, desc
from sqlalchemy.orm import Session, joinedload

from ..db import get_db
from ..models import (
    Lot, LotMember, LotStatus, SellerType,
    BuyerInterest, LotTimelineEvent,
    Commodity, Mandi, Location, State, District,
    Farmer, FPO,
)

router = APIRouter(prefix="/lots", tags=["Produce Lots"])


# =============================================================================
# Pydantic Schemas
# =============================================================================

class LotMemberRequest(BaseModel):
    farmer_id: Optional[int] = None
    farmer_name: str
    farmer_contact: Optional[str] = None
    quantity: float = Field(..., gt=0)
    quality_grade: Optional[str] = None
    quality_specs: Optional[dict] = None
    expected_price: Optional[float] = None
    location_id: Optional[int] = None
    location_name: Optional[str] = None


class LotMemberResponse(BaseModel):
    id: int
    farmer_id: Optional[int] = None
    farmer_name: str
    farmer_contact: Optional[str] = None
    quantity: float
    quality_grade: Optional[str] = None
    quality_specs: Optional[dict] = None
    expected_price: Optional[float] = None
    location_id: Optional[int] = None
    location_name: Optional[str] = None
    is_confirmed: bool
    confirmed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LotCreateRequest(BaseModel):
    commodity_id: str
    commodity_name: Optional[str] = None
    quantity: float = Field(..., gt=0)
    unit: str = "Quintal (100 kg)"
    quality_grade: str = Field(default="A", pattern="^[ABC]$")
    variety: Optional[str] = None
    quality_specs: Optional[dict] = None
    certifications: Optional[List[str]] = None
    lab_test_report_id: Optional[str] = None
    lab_test_date: Optional[date] = None
    lab_test_results: Optional[dict] = None
    location_id: Optional[int] = None
    location_name: str
    state_id: Optional[int] = None
    district_id: Optional[int] = None
    pincode: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    expected_min_price: float = Field(..., gt=0)
    expected_max_price: Optional[float] = None
    reserve_price: Optional[float] = None
    pricing_basis: Optional[str] = None
    available_from: Optional[date] = None
    available_until: date
    harvest_date: Optional[date] = None
    has_storage: bool = False
    storage_type: Optional[str] = None
    storage_facility_name: Optional[str] = None
    storage_location_id: Optional[int] = None
    storage_cost_per_day_qtl: Optional[float] = None
    can_deliver: bool = False
    delivery_radius_km: Optional[float] = None
    preferred_mandi_id: Optional[int] = None
    transport_arrangement: Optional[str] = None
    seller_type: SellerType = SellerType.INDIVIDUAL_FARMER
    fpo_id: Optional[int] = None
    fpo_name: Optional[str] = None
    members: Optional[List[LotMemberRequest]] = None
    notes: Optional[str] = None


class LotUpdateRequest(BaseModel):
    quality_grade: Optional[str] = None
    quantity: Optional[float] = Field(None, gt=0)
    expected_min_price: Optional[float] = None
    expected_max_price: Optional[float] = None
    reserve_price: Optional[float] = None
    available_until: Optional[date] = None
    has_storage: Optional[bool] = None
    storage_type: Optional[str] = None
    storage_cost_per_day_qtl: Optional[float] = None
    can_deliver: Optional[bool] = None
    delivery_radius_km: Optional[float] = None
    preferred_mandi_id: Optional[int] = None
    notes: Optional[str] = None
    internal_notes: Optional[str] = None


class LotBaseResponse(BaseModel):
    id: int
    lot_id: str
    commodity_id: str
    commodity_name: str
    variety: Optional[str] = None
    quality_grade: str
    quantity: float
    unit: str
    location_name: str
    state_id: Optional[int] = None
    district_id: Optional[int] = None
    expected_min_price: float
    expected_max_price: Optional[float] = None
    available_until: date
    status: LotStatus
    seller_type: SellerType
    fpo_id: Optional[int] = None
    is_aggregated: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LotDetailResponse(LotBaseResponse):
    quality_specs: Optional[dict] = None
    certifications: Optional[List[str]] = None
    lab_test_report_id: Optional[str] = None
    lab_test_date: Optional[date] = None
    lab_test_results: Optional[dict] = None
    location_id: Optional[int] = None
    pincode: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    reserve_price: Optional[float] = None
    pricing_basis: Optional[str] = None
    available_from: Optional[date] = None
    harvest_date: Optional[date] = None
    has_storage: bool
    storage_type: Optional[str] = None
    storage_facility_name: Optional[str] = None
    storage_location_id: Optional[int] = None
    storage_cost_per_day_qtl: Optional[float] = None
    can_deliver: bool
    delivery_radius_km: Optional[float] = None
    preferred_mandi_id: Optional[int] = None
    preferred_mandi_name: Optional[str] = None
    transport_arrangement: Optional[str] = None
    seller_name: Optional[str] = None
    seller_contact_phone: Optional[str] = None
    seller_contact_email: Optional[str] = None
    fpo_name: Optional[str] = None
    parent_lot_id: Optional[int] = None
    status_reason: Optional[str] = None
    members: List[LotMemberResponse] = []
    interests_count: int = 0
    days_until_expiry: Optional[int] = None
    total_value_range: tuple = (0, 0)

    class Config:
        from_attributes = True


class LotListResponse(BaseModel):
    lots: List[LotBaseResponse]
    total: int
    page: int
    page_size: int


class BuyerInterestCreateRequest(BaseModel):
    buyer_id: int
    offered_price: Optional[float] = None
    offered_quantity: Optional[float] = None
    payment_terms: Optional[str] = None
    collection_mode: Optional[str] = None
    proposed_pickup_date: Optional[date] = None
    validity_days: int = 7
    quality_conditions: Optional[str] = None
    requires_lab_test: bool = False
    message: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None


class BuyerInterestResponse(BaseModel):
    id: int
    lot_id: int
    buyer_id: int
    buyer_name: str
    offered_price: Optional[float] = None
    offered_quantity: Optional[float] = None
    total_offer_value: Optional[float] = None
    payment_terms: Optional[str] = None
    collection_mode: Optional[str] = None
    proposed_pickup_date: Optional[date] = None
    validity_days: int
    quality_conditions: Optional[str] = None
    requires_lab_test: bool
    status: str
    status_reason: Optional[str] = None
    message: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    sent_at: datetime
    viewed_at: Optional[datetime] = None
    responded_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TimelineEventResponse(BaseModel):
    id: int
    step: str
    completed: bool
    status: Optional[str] = None
    actor_type: Optional[str] = None
    actor_name: Optional[str] = None
    details: Optional[dict] = None
    previous_status: Optional[LotStatus] = None
    new_status: Optional[LotStatus] = None
    created_at: datetime
    estimated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# =============================================================================
# Lot Endpoints
# =============================================================================

@router.post("", response_model=LotDetailResponse, status_code=201)
async def create_lot(
    request: LotCreateRequest,
    db: Session = Depends(get_db),
):
    """Create a new produce lot."""
    # Validate commodity
    commodity = db.query(Commodity).filter(Commodity.id == request.commodity_id).first()
    if not commodity:
        raise HTTPException(status_code=404, detail="Commodity not found")
    
    # Validate location
    if request.location_id:
        location = db.query(Location).filter(Location.id == request.location_id).first()
        if not location:
            raise HTTPException(status_code=404, detail="Location not found")
        request.latitude = location.latitude
        request.longitude = location.longitude
        request.pincode = location.pincode
        if not request.state_id:
            request.state_id = location.state_id
        if not request.district_id:
            request.district_id = location.district_id
    
    # Validate FPO if provided
    if request.seller_type in [SellerType.FPO, SellerType.COOPERATIVE] and request.fpo_id:
        fpo = db.query(FPO).filter(FPO.id == request.fpo_id).first()
        if not fpo:
            raise HTTPException(status_code=404, detail="FPO not found")
        request.fpo_name = fpo.name
    
    # Validate preferred mandi
    preferred_mandi_name = None
    if request.preferred_mandi_id:
        mandi = db.query(Mandi).filter(Mandi.id == request.preferred_mandi_id).first()
        if not mandi:
            raise HTTPException(status_code=404, detail="Preferred mandi not found")
        preferred_mandi_name = mandi.name
    
    # Generate lot ID
    from sqlalchemy import text
    result = db.execute(text("SELECT COALESCE(MAX(CAST(SUBSTRING(lot_id FROM 'AGRI-2026-(\\d+)') AS INTEGER)), 1000) FROM lots"))
    next_num = (result.scalar() or 1000) + 1
    lot_id = f"AGRI-2026-{next_num}"
    
    # Create lot
    lot = Lot(
        lot_id=lot_id,
        commodity_id=request.commodity_id,
        commodity_name=request.commodity_name or commodity.name,
        variety=request.variety or commodity.variety,
        quality_grade=request.quality_grade,
        quantity=request.quantity,
        unit=request.unit,
        quality_specs=request.quality_specs,
        certifications=request.certifications,
        lab_test_report_id=request.lab_test_report_id,
        lab_test_date=request.lab_test_date,
        lab_test_results=request.lab_test_results,
        location_id=request.location_id,
        location_name=request.location_name,
        state_id=request.state_id,
        district_id=request.district_id,
        pincode=request.pincode,
        latitude=request.latitude,
        longitude=request.longitude,
        expected_min_price=request.expected_min_price,
        expected_max_price=request.expected_max_price,
        reserve_price=request.reserve_price,
        pricing_basis=request.pricing_basis,
        available_from=request.available_from,
        available_until=request.available_until,
        harvest_date=request.harvest_date,
        has_storage=request.has_storage,
        storage_type=request.storage_type,
        storage_facility_name=request.storage_facility_name,
        storage_location_id=request.storage_location_id,
        storage_cost_per_day_qtl=request.storage_cost_per_day_qtl,
        can_deliver=request.can_deliver,
        delivery_radius_km=request.delivery_radius_km,
        preferred_mandi_id=request.preferred_mandi_id,
        transport_arrangement=request.transport_arrangement,
        seller_type=request.seller_type,
        fpo_id=request.fpo_id,
        fpo_name=request.fpo_name,
        notes=request.notes,
        status=LotStatus.DRAFT,
    )
    
    db.add(lot)
    db.flush()
    
    # Add members if FPO aggregation
    if request.members and request.seller_type in [SellerType.FPO, SellerType.COOPERATIVE]:
        for member_data in request.members:
            member = LotMember(
                lot_id=lot.id,
                farmer_id=member_data.farmer_id,
                farmer_name=member_data.farmer_name,
                farmer_contact=member_data.farmer_contact,
                quantity=member_data.quantity,
                quality_grade=member_data.quality_grade,
                quality_specs=member_data.quality_specs,
                expected_price=member_data.expected_price,
                location_id=member_data.location_id,
                location_name=member_data.location_name,
            )
            db.add(member)
        
        # Update aggregated flag
        lot.is_aggregated = True
    
    # Add initial timeline event
    timeline = LotTimelineEvent(
        lot_id=lot.id,
        step="LOT_CREATED",
        completed=True,
        actor_type="farmer" if request.seller_type == SellerType.INDIVIDUAL_FARMER else "fpo",
        actor_name=lot.seller_name or "Farmer",
        new_status=LotStatus.DRAFT,
        details={"lot_id": lot_id, "commodity": request.commodity_id},
    )
    db.add(timeline)
    
    db.commit()
    db.refresh(lot)
    
    return LotDetailResponse.from_orm(lot)


@router.get("", response_model=LotListResponse)
async def list_lots(
    status: Optional[LotStatus] = Query(None),
    commodity_id: Optional[str] = Query(None),
    seller_type: Optional[SellerType] = Query(None),
    fpo_id: Optional[int] = Query(None),
    farmer_id: Optional[int] = Query(None),
    state_id: Optional[int] = Query(None),
    district_id: Optional[int] = Query(None),
    is_aggregated: Optional[bool] = Query(None),
    available_before: Optional[date] = Query(None),
    available_after: Optional[date] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List produce lots with filters."""
    query = db.query(Lot).options(
        joinedload(Lot.commodity),
        joinedload(Lot.preferred_mandi),
        joinedload(Lot.fpo),
    )
    
    if status:
        query = query.filter(Lot.status == status)
    if commodity_id:
        query = query.filter(Lot.commodity_id == commodity_id)
    if seller_type:
        query = query.filter(Lot.seller_type == seller_type)
    if fpo_id:
        query = query.filter(Lot.fpo_id == fpo_id)
    if farmer_id:
        query = query.filter(Lot.farmer_id == farmer_id)
    if state_id:
        query = query.filter(Lot.state_id == state_id)
    if district_id:
        query = query.filter(Lot.district_id == district_id)
    if is_aggregated is not None:
        query = query.filter(Lot.is_aggregated == is_aggregated)
    if available_before:
        query = query.filter(Lot.available_until <= available_before)
    if available_after:
        query = query.filter(Lot.available_until >= available_after)
    if search:
        query = query.filter(
            or_(
                Lot.lot_id.ilike(f"%{search}%"),
                Lot.commodity_name.ilike(f"%{search}%"),
                Lot.location_name.ilike(f"%{search}%"),
            )
        )
    
    total = query.count()
    lots = query.order_by(desc(Lot.created_at)).offset((page - 1) * page_size).limit(page_size).all()
    
    return LotListResponse(
        lots=lots,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{lot_id}", response_model=LotDetailResponse)
async def get_lot(
    lot_id: int = Path(..., gt=0),
    include_members: bool = Query(True),
    include_interests: bool = Query(False),
    db: Session = Depends(get_db),
):
    """Get detailed lot information."""
    query = db.query(Lot).options(
        joinedload(Lot.commodity),
        joinedload(Lot.preferred_mandi),
        joinedload(Lot.fpo),
        joinedload(Lot.location),
        joinedload(Lot.state),
        joinedload(Lot.district),
    )
    
    if include_members:
        query = query.options(joinedload(Lot.members))
    if include_interests:
        query = query.options(joinedload(Lot.interests).joinedload(BuyerInterest.buyer))
    
    lot = query.filter(Lot.id == lot_id).first()
    
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")
    
    response = LotDetailResponse.from_orm(lot)
    response.preferred_mandi_name = lot.preferred_mandi.name if lot.preferred_mandi else None
    response.days_until_expiry = lot.days_until_expiry
    response.total_value_range = lot.total_value_range
    response.interests_count = len(lot.interests) if lot.interests else 0
    
    return response


@router.get("/by-code/{lot_code}", response_model=LotDetailResponse)
async def get_lot_by_code(
    lot_code: str = Path(..., description="Lot ID code (e.g., AGRI-2026-1001)"),
    db: Session = Depends(get_db),
):
    """Get lot by unique code."""
    lot = db.query(Lot).options(
        joinedload(Lot.commodity),
        joinedload(Lot.preferred_mandi),
        joinedload(Lot.fpo),
        joinedload(Lot.members),
    ).filter(Lot.lot_id == lot_code).first()
    
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")
    
    return LotDetailResponse.from_orm(lot)


@router.patch("/{lot_id}", response_model=LotDetailResponse)
async def update_lot(
    lot_id: int = Path(..., gt=0),
    request: LotUpdateRequest = ...,
    db: Session = Depends(get_db),
):
    """Update lot details (only if DRAFT or OPEN)."""
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")
    
    if lot.status not in [LotStatus.DRAFT, LotStatus.OPEN]:
        raise HTTPException(status_code=400, detail=f"Cannot update lot in {lot.status.value} status")
    
    # Track status change
    old_status = lot.status
    
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(lot, field, value)
    
    lot.updated_at = datetime.now(timezone.utc)
    
    # Add timeline event if status changed
    if 'status' in update_data and update_data['status'] != old_status:
        timeline = LotTimelineEvent(
            lot_id=lot.id,
            step=f"STATUS_CHANGED_{update_data['status'].upper()}",
            completed=True,
            actor_type="farmer",
            actor_name=lot.seller_name or "Farmer",
            previous_status=old_status,
            new_status=update_data['status'],
            details={"reason": request.internal_notes},
        )
        db.add(timeline)
    
    db.commit()
    db.refresh(lot)
    
    return LotDetailResponse.from_orm(lot)


@router.post("/{lot_id}/publish", response_model=LotDetailResponse)
async def publish_lot(
    lot_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    """Publish a draft lot to OPEN status for buyer matching."""
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")
    
    if lot.status != LotStatus.DRAFT:
        raise HTTPException(status_code=400, detail=f"Only DRAFT lots can be published. Current: {lot.status.value}")
    
    lot.status = LotStatus.OPEN
    lot.published_at = datetime.now(timezone.utc)
    lot.updated_at = datetime.now(timezone.utc)
    
    timeline = LotTimelineEvent(
        lot_id=lot.id,
        step="PUBLISHED",
        completed=True,
        actor_type="farmer",
        actor_name=lot.seller_name or "Farmer",
        previous_status=LotStatus.DRAFT,
        new_status=LotStatus.OPEN,
        details={"published_at": lot.published_at.isoformat()},
    )
    db.add(timeline)
    
    db.commit()
    db.refresh(lot)
    
    return LotDetailResponse.from_orm(lot)


@router.post("/{lot_id}/cancel", response_model=LotDetailResponse)
async def cancel_lot(
    lot_id: int = Path(..., gt=0),
    reason: str = Query(..., min_length=5),
    db: Session = Depends(get_db),
):
    """Cancel a lot."""
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")
    
    if lot.status in [LotStatus.COMPLETED, LotStatus.SETTLED, LotStatus.CANCELLED]:
        raise HTTPException(status_code=400, detail=f"Cannot cancel lot in {lot.status.value} status")
    
    old_status = lot.status
    lot.status = LotStatus.CANCELLED
    lot.cancelled_at = datetime.now(timezone.utc)
    lot.status_reason = reason
    lot.updated_at = datetime.now(timezone.utc)
    
    timeline = LotTimelineEvent(
        lot_id=lot.id,
        step="CANCELLED",
        completed=True,
        actor_type="farmer",
        actor_name=lot.seller_name or "Farmer",
        previous_status=old_status,
        new_status=LotStatus.CANCELLED,
        details={"reason": reason},
    )
    db.add(timeline)
    
    db.commit()
    db.refresh(lot)
    
    return LotDetailResponse.from_orm(lot)


# =============================================================================
# Buyer Interest Endpoints
# =============================================================================

@router.post("/{lot_id}/interests", response_model=BuyerInterestResponse, status_code=201)
async def create_buyer_interest(
    lot_id: int = Path(..., gt=0),
    request: BuyerInterestCreateRequest = ...,
    db: Session = Depends(get_db),
):
    """Buyer expresses interest in a lot."""
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")
    
    if lot.status not in [LotStatus.OPEN, LotStatus.MATCHED]:
        raise HTTPException(status_code=400, detail=f"Lot not accepting interests. Status: {lot.status.value}")
    
    buyer = db.query(Buyer).filter(Buyer.id == request.buyer_id).first()
    if not buyer:
        raise HTTPException(status_code=404, detail="Buyer not found")
    
    if not buyer.is_verified_buyer:
        raise HTTPException(status_code=400, detail="Only verified buyers can express interest")
    
    # Check for existing interest
    existing = db.query(BuyerInterest).filter(
        BuyerInterest.lot_id == lot_id,
        BuyerInterest.buyer_id == request.buyer_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Interest already submitted for this lot")
    
    # Calculate total offer value
    offer_qty = request.offered_quantity or lot.quantity
    offer_price = request.offered_price or lot.expected_min_price
    total_value = offer_price * offer_qty
    
    interest = BuyerInterest(
        lot_id=lot_id,
        buyer_id=request.buyer_id,
        offered_price=offer_price,
        offered_quantity=offer_qty,
        total_offer_value=total_value,
        payment_terms=request.payment_terms,
        collection_mode=request.collection_mode,
        proposed_pickup_date=request.proposed_pickup_date,
        validity_days=request.validity_days,
        quality_conditions=request.quality_conditions,
        requires_lab_test=request.requires_lab_test,
        message=request.message,
        contact_person=request.contact_person,
        contact_phone=request.contact_phone,
        status="INTEREST_SENT",
        sent_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=request.validity_days),
    )
    
    db.add(interest)
    
    # Update lot status if first interest
    if lot.status == LotStatus.OPEN:
        lot.status = LotStatus.MATCHED
        lot.matched_at = datetime.now(timezone.utc)
        
        timeline = LotTimelineEvent(
            lot_id=lot.id,
            step="BUYER_MATCHED",
            completed=True,
            actor_type="buyer",
            actor_id=str(request.buyer_id),
            actor_name=buyer.legal_name,
            previous_status=LotStatus.OPEN,
            new_status=LotStatus.MATCHED,
            details={"buyer_id": request.buyer_id, "buyer_name": buyer.legal_name},
        )
        db.add(timeline)
    
    db.commit()
    db.refresh(interest)
    
    # Add buyer name to response
    response = BuyerInterestResponse.from_orm(interest)
    response.buyer_name = buyer.legal_name
    return response


@router.get("/{lot_id}/interests", response_model=List[BuyerInterestResponse])
async def get_lot_interests(
    lot_id: int = Path(..., gt=0),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Get all buyer interests for a lot."""
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")
    
    query = db.query(BuyerInterest).options(
        joinedload(BuyerInterest.buyer),
    ).filter(BuyerInterest.lot_id == lot_id)
    
    if status:
        query = query.filter(BuyerInterest.status == status)
    
    interests = query.order_by(desc(BuyerInterest.sent_at)).all()
    
    return [
        BuyerInterestResponse(
            **i.__dict__,
            buyer_name=i.buyer.legal_name if i.buyer else "Unknown",
        )
        for i in interests
    ]


@router.patch("/{lot_id}/interests/{interest_id}/respond")
async def respond_to_interest(
    lot_id: int = Path(..., gt=0),
    interest_id: int = Path(..., gt=0),
    action: str = Query(..., pattern="^(accept|reject|negotiate)$"),
    counter_price: Optional[float] = Query(None),
    counter_terms: Optional[str] = Query(None),
    reason: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Farmer responds to buyer interest."""
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")
    
    interest = db.query(BuyerInterest).filter(
        BuyerInterest.id == interest_id,
        BuyerInterest.lot_id == lot_id,
    ).first()
    if not interest:
        raise HTTPException(status_code=404, detail="Interest not found")
    
    if action == "accept":
        interest.status = "ACCEPTED"
        interest.responded_at = datetime.now(timezone.utc)
        lot.status = LotStatus.CONTRACTED
        lot.contracted_at = datetime.now(timezone.utc)
        
        timeline = LotTimelineEvent(
            lot_id=lot.id,
            step="CONTRACTED",
            completed=True,
            actor_type="farmer",
            actor_name=lot.seller_name or "Farmer",
            previous_status=lot.status,
            new_status=LotStatus.CONTRACTED,
            details={"buyer_id": interest.buyer_id, "price": interest.offered_price},
        )
        db.add(timeline)
    
    elif action == "reject":
        interest.status = "REJECTED"
        interest.responded_at = datetime.now(timezone.utc)
        interest.status_reason = reason
    
    elif action == "negotiate":
        interest.status = "NEGOTIATING"
        lot.status = LotStatus.NEGOTIATING
        if counter_price:
            interest.offered_price = counter_price
            interest.total_offer_value = counter_price * (interest.offered_quantity or lot.quantity)
        if counter_terms:
            interest.payment_terms = counter_terms
        interest.responded_at = datetime.now(timezone.utc)
        
        timeline = LotTimelineEvent(
            lot_id=lot.id,
            step="NEGOTIATION_STARTED",
            completed=True,
            actor_type="farmer",
            actor_name=lot.seller_name or "Farmer",
            previous_status=LotStatus.MATCHED,
            new_status=LotStatus.NEGOTIATING,
            details={"buyer_id": interest.buyer_id, "counter_price": counter_price},
        )
        db.add(timeline)
    
    db.commit()
    db.refresh(interest)
    db.refresh(lot)
    
    return {
        "status": "success",
        "interest_status": interest.status,
        "lot_status": lot.status.value,
    }


# =============================================================================
# Timeline Endpoints
# =============================================================================

@router.get("/{lot_id}/timeline", response_model=List[TimelineEventResponse])
async def get_lot_timeline(
    lot_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    """Get complete lifecycle timeline for a lot."""
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")
    
    events = db.query(LotTimelineEvent).filter(
        LotTimelineEvent.lot_id == lot_id
    ).order_by(LotTimelineEvent.created_at).all()
    
    return events


# =============================================================================
# Statistics
# =============================================================================

@router.get("/stats/summary")
async def get_lot_stats(
    state_id: Optional[int] = Query(None),
    district_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Get lot statistics."""
    query = db.query(Lot)
    
    if state_id:
        query = query.filter(Lot.state_id == state_id)
    if district_id:
        query = query.filter(Lot.district_id == district_id)
    
    total = query.count()
    by_status = db.query(Lot.status, func.count(Lot.id)).filter(
        Lot.state_id == state_id if state_id else True,
        Lot.district_id == district_id if district_id else True,
    ).group_by(Lot.status).all()
    
    by_seller_type = db.query(Lot.seller_type, func.count(Lot.id)).group_by(Lot.seller_type).all()
    
    # Active lots
    active = query.filter(Lot.status.in_([LotStatus.OPEN, LotStatus.MATCHED, LotStatus.NEGOTIATING])).count()
    
    # Expiring soon
    expiring_soon = query.filter(
        Lot.available_until <= date.today() + timedelta(days=7),
        Lot.status.in_([LotStatus.OPEN, LotStatus.MATCHED, LotStatus.NEGOTIATING]),
    ).count()
    
    return {
        "total": total,
        "active": active,
        "expiring_soon": expiring_soon,
        "by_status": {str(s): c for s, c in by_status},
        "by_seller_type": {str(s): c for s, c in by_seller_type},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health")
async def lots_health(db: Session = Depends(get_db)):
    """Health check for lot services."""
    active = db.query(Lot).filter(
        Lot.status.in_([LotStatus.OPEN, LotStatus.MATCHED, LotStatus.NEGOTIATING]),
    ).count()
    
    return {
        "status": "healthy",
        "active_lots": active,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }