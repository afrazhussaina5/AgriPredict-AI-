# AgriPredict AI - FPO API Routes
"""
Farmer Producer Organization management for collective aggregation.
"""

from datetime import datetime, date, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, desc
from sqlalchemy.orm import Session, joinedload

from ..db import get_db
from ..models import (
    FPO, FPOMember, FPOStatus, FPOType, FPOAggregationPlan,
    Commodity, Mandi, State, District, Subdistrict, Farmer, Lot,
)

router = APIRouter(prefix="/fpos", tags=["FPOs"])


# =============================================================================
# Pydantic Schemas
# =============================================================================

class FPOMemberRequest(BaseModel):
    farmer_id: Optional[int] = None
    member_id: Optional[str] = None
    name: str
    father_spouse_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    aadhaar_hash: Optional[str] = None
    pan: Optional[str] = None
    village: Optional[str] = None
    location_id: Optional[int] = None
    survey_numbers: Optional[List[str]] = None
    total_area_hectares: Optional[float] = None
    irrigated_area_hectares: Optional[float] = None
    ownership_type: Optional[str] = None
    shares_held: int = 0
    share_value: float = 0.0
    primary_crops: Optional[List[dict]] = None
    annual_production_qtl: Optional[float] = None
    bank_account: Optional[dict] = None


class FPOMemberResponse(BaseModel):
    id: int
    member_id: Optional[str] = None
    farmer_id: Optional[int] = None
    name: str
    father_spouse_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    village: Optional[str] = None
    location_id: Optional[int] = None
    total_area_hectares: Optional[float] = None
    irrigated_area_hectares: Optional[float] = None
    ownership_type: Optional[str] = None
    shares_held: int
    share_value: float
    date_of_joining: Optional[date] = None
    primary_crops: Optional[List[dict]] = None
    annual_production_qtl: Optional[float] = None
    is_active: bool
    membership_status: str
    kyc_status: str

    class Config:
        from_attributes = True


class FPOCommodityResponse(BaseModel):
    id: str
    name: str
    category: str
    is_primary: bool
    annual_volume_qtl: Optional[float] = None

    class Config:
        from_attributes = True


class FPOMandiResponse(BaseModel):
    id: int
    mandi_id: str
    name: str
    district: str
    is_preferred: bool

    class Config:
        from_attributes = True


class FPOBaseResponse(BaseModel):
    id: int
    fpo_id: str
    name: str
    legal_name: Optional[str] = None
    type: FPOType
    status: FPOStatus
    state_id: Optional[int] = None
    district_id: Optional[int] = None
    member_count: int
    is_demo: bool

    class Config:
        from_attributes = True


class FPODetailResponse(FPOBaseResponse):
    registration_number: Optional[str] = None
    registration_date: Optional[date] = None
    registration_authority: Optional[str] = None
    pan: Optional[str] = None
    gstin: Optional[str] = None
    tan: Optional[str] = None
    board_members: Optional[List[dict]] = None
    ceo_name: Optional[str] = None
    ceo_contact: Optional[str] = None
    ceo_email: Optional[str] = None
    registered_address: Optional[str] = None
    operational_address: Optional[str] = None
    pincode: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    total_land_hectares: float
    share_capital: float
    paid_up_capital: float
    has_collection_centers: bool
    collection_centers: Optional[List[dict]] = None
    has_cold_storage: bool
    cold_storage_capacity_mt: Optional[float] = None
    has_processing_unit: bool
    processing_capacity: Optional[List[dict]] = None
    has_transport: bool
    transport_details: Optional[dict] = None
    certifications: Optional[List[str]] = None
    fpo_certification_number: Optional[str] = None
    fpo_certification_date: Optional[date] = None
    fpo_certification_expiry: Optional[date] = None
    annual_turnover: Optional[float] = None
    profit_last_year: Optional[float] = None
    bank_account: Optional[dict] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    demo_disclaimer: Optional[str] = None
    commodities: List[FPOCommodityResponse] = []
    mandis: List[FPOMandiResponse] = []
    members: List[FPOMemberResponse] = []
    aggregation_plans: List[dict] = []

    class Config:
        from_attributes = True


class FPOCreateRequest(BaseModel):
    fpo_id: str = Field(..., min_length=3, max_length=50)
    name: str = Field(..., min_length=2, max_length=200)
    legal_name: Optional[str] = None
    type: FPOType = FPOType.PRODUCER_COMPANY
    registration_number: Optional[str] = None
    registration_date: Optional[date] = None
    registration_authority: Optional[str] = None
    pan: Optional[str] = None
    gstin: Optional[str] = None
    tan: Optional[str] = None
    board_members: Optional[List[dict]] = None
    ceo_name: Optional[str] = None
    ceo_contact: Optional[str] = None
    ceo_email: Optional[str] = None
    registered_address: Optional[str] = None
    operational_address: Optional[str] = None
    state_id: Optional[int] = None
    district_id: Optional[int] = None
    pincode: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    commodities: Optional[List[str]] = None
    mandis: Optional[List[int]] = None
    is_demo: bool = False
    demo_disclaimer: Optional[str] = None


class FPOAggregationPlanCreateRequest(BaseModel):
    commodity_id: str
    season: str
    target_quantity_qtl: float = Field(..., gt=0)
    target_grade: Optional[str] = None
    collection_start_date: Optional[date] = None
    collection_end_date: Optional[date] = None
    collection_centers: Optional[List[dict]] = None
    quality_standards: Optional[dict] = None
    requires_sorting_grading: bool = True
    transport_arranged: bool = False
    transport_details: Optional[dict] = None
    target_markets: Optional[List[dict]] = None
    target_buyers: Optional[List[dict]] = None
    marketing_strategy: Optional[str] = None


class FPOAggregationPlanResponse(BaseModel):
    id: int
    fpo_id: int
    commodity_id: str
    commodity_name: str
    season: str
    target_quantity_qtl: float
    target_grade: Optional[str] = None
    collection_start_date: Optional[date] = None
    collection_end_date: Optional[date] = None
    status: str
    actual_quantity_qtl: float
    actual_revenue: float
    created_at: datetime

    class Config:
        from_attributes = True


class FPOListResponse(BaseModel):
    fpos: List[FPOBaseResponse]
    total: int
    page: int
    page_size: int


# =============================================================================
# FPO Endpoints
# =============================================================================

@router.get("", response_model=FPOListResponse)
async def list_fpos(
    status: Optional[FPOStatus] = Query(None),
    type: Optional[FPOType] = Query(None),
    state_id: Optional[int] = Query(None),
    district_id: Optional[int] = Query(None),
    commodity_id: Optional[str] = Query(None),
    is_demo: Optional[bool] = Query(False),
    include_demo: bool = Query(False),
    search: Optional[str] = Query(None),
    min_members: Optional[int] = Query(None, ge=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List FPOs with filters."""
    query = db.query(FPO).options(
        joinedload(FPO.state),
        joinedload(FPO.district),
    )
    
    if status:
        query = query.filter(FPO.status == status)
    if type:
        query = query.filter(FPO.type == type)
    if state_id:
        query = query.filter(FPO.state_id == state_id)
    if district_id:
        query = query.filter(FPO.district_id == district_id)
    if is_demo is not None:
        query = query.filter(FPO.is_demo == is_demo)
    if not include_demo:
        query = query.filter(FPO.is_demo == False)
    if search:
        query = query.filter(
            or_(
                FPO.name.ilike(f"%{search}%"),
                FPO.legal_name.ilike(f"%{search}%"),
                FPO.fpo_id.ilike(f"%{search}%"),
            )
        )
    if min_members:
        query = query.filter(FPO.member_count >= min_members)
    if commodity_id:
        query = query.join(FPO.commodities).filter(Commodity.id == commodity_id)
    
    total = query.count()
    fpos = query.order_by(
        FPO.status.desc(),
        FPO.member_count.desc(),
    ).offset((page - 1) * page_size).limit(page_size).all()
    
    return FPOListResponse(
        fpos=fpos,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/active", response_model=List[FPOBaseResponse])
async def list_active_fpos(
    state_id: Optional[int] = Query(None),
    district_id: Optional[int] = Query(None),
    commodity_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get active, non-demo FPOs for farmer-facing selection."""
    query = db.query(FPO).filter(
        FPO.status == FPOStatus.ACTIVE,
        FPO.is_demo == False,
    )
    
    if state_id:
        query = query.filter(FPO.state_id == state_id)
    if district_id:
        query = query.filter(FPO.district_id == district_id)
    if commodity_id:
        query = query.join(FPO.commodities).filter(Commodity.id == commodity_id)
    
    fpos = query.order_by(FPO.member_count.desc()).limit(limit).all()
    return fpos


@router.get("/{fpo_id}", response_model=FPODetailResponse)
async def get_fpo(
    fpo_id: int = Path(..., gt=0),
    include_members: bool = Query(False),
    include_plans: bool = Query(False),
    db: Session = Depends(get_db),
):
    """Get detailed FPO information."""
    query = db.query(FPO).options(
        joinedload(FPO.commodities),
        joinedload(FPO.mandis),
        joinedload(FPO.state),
        joinedload(FPO.district),
    )
    
    if include_members:
        query = query.options(joinedload(FPO.members))
    if include_plans:
        query = query.options(joinedload(FPO.aggregation_plans))
    
    fpo = query.filter(FPO.id == fpo_id).first()
    
    if not fpo:
        raise HTTPException(status_code=404, detail="FPO not found")
    
    # Build mandis response
    mandis_resp = []
    for m in fpo.mandis:
        mandis_resp.append(FPOMandiResponse(
            id=m.id,
            mandi_id=m.mandi_id,
            name=m.name,
            district=m.district.name if m.district else "",
            is_preferred=False,  # Would need fpo_mandis association
        ))
    
    response = FPODetailResponse.from_orm(fpo)
    response.mandis = mandis_resp
    return response


@router.get("/by-code/{fpo_code}", response_model=FPODetailResponse)
async def get_fpo_by_code(
    fpo_code: str = Path(..., description="FPO ID code (e.g., FPO-2026-001)"),
    db: Session = Depends(get_db),
):
    """Get FPO by unique code."""
    fpo = db.query(FPO).options(
        joinedload(FPO.commodities),
        joinedload(FPO.mandis),
        joinedload(FPO.state),
        joinedload(FPO.district),
    ).filter(FPO.fpo_id == fpo_code).first()
    
    if not fpo:
        raise HTTPException(status_code=404, detail="FPO not found")
    
    return FPODetailResponse.from_orm(fpo)


@router.post("", response_model=FPODetailResponse, status_code=201)
async def create_fpo(
    request: FPOCreateRequest,
    db: Session = Depends(get_db),
):
    """Register a new FPO."""
    # Check for duplicate fpo_id
    existing = db.query(FPO).filter(FPO.fpo_id == request.fpo_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="FPO ID already exists")
    
    # Check for duplicate registration number
    if request.registration_number:
        existing_reg = db.query(FPO).filter(FPO.registration_number == request.registration_number).first()
        if existing_reg:
            raise HTTPException(status_code=409, detail="Registration number already exists")
    
    # Check for duplicate GSTIN
    if request.gstin:
        existing_gstin = db.query(FPO).filter(FPO.gstin == request.gstin).first()
        if existing_gstin:
            raise HTTPException(status_code=409, detail="GSTIN already registered")
    
    fpo = FPO(
        fpo_id=request.fpo_id,
        name=request.name,
        legal_name=request.legal_name,
        type=request.type,
        registration_number=request.registration_number,
        registration_date=request.registration_date,
        registration_authority=request.registration_authority,
        pan=request.pan,
        gstin=request.gstin,
        tan=request.tan,
        board_members=request.board_members,
        ceo_name=request.ceo_name,
        ceo_contact=request.ceo_contact,
        ceo_email=request.ceo_email,
        registered_address=request.registered_address,
        operational_address=request.operational_address,
        state_id=request.state_id,
        district_id=request.district_id,
        pincode=request.pincode,
        latitude=request.latitude,
        longitude=request.longitude,
        status=FPOStatus.REGISTERING,
        is_demo=request.is_demo,
        demo_disclaimer=request.demo_disclaimer,
    )
    
    db.add(fpo)
    db.flush()
    
    # Add commodities
    if request.commodities:
        for comm_id in request.commodities:
            commodity = db.query(Commodity).filter(Commodity.id == comm_id).first()
            if commodity:
                fpo.commodities.append(commodity)
    
    # Add mandis
    if request.mandis:
        for mandi_id in request.mandis:
            mandi = db.query(Mandi).filter(Mandi.id == mandi_id).first()
            if mandi:
                fpo.mandis.append(mandi)
    
    db.commit()
    db.refresh(fpo)
    
    return FPODetailResponse.from_orm(fpo)


@router.patch("/{fpo_id}/status")
async def update_fpo_status(
    fpo_id: int = Path(..., gt=0),
    status: FPOStatus = Query(...),
    reason: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Update FPO operational status (admin)."""
    fpo = db.query(FPO).filter(FPO.id == fpo_id).first()
    if not fpo:
        raise HTTPException(status_code=404, detail="FPO not found")
    
    old_status = fpo.status
    fpo.status = status
    fpo.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    
    return {
        "status": "success",
        "fpo_id": fpo.fpo_id,
        "previous_status": old_status.value,
        "new_status": status.value,
    }


# =============================================================================
# FPO Member Endpoints
# =============================================================================

@router.get("/{fpo_id}/members", response_model=List[FPOMemberResponse])
async def list_fpo_members(
    fpo_id: int = Path(..., gt=0),
    is_active: Optional[bool] = Query(True),
    kyc_status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Get FPO members."""
    fpo = db.query(FPO).filter(FPO.id == fpo_id).first()
    if not fpo:
        raise HTTPException(status_code=404, detail="FPO not found")
    
    query = db.query(FPOMember).filter(FPOMember.fpo_id == fpo_id)
    
    if is_active is not None:
        query = query.filter(FPOMember.is_active == is_active)
    if kyc_status:
        query = query.filter(FPOMember.kyc_status == kyc_status)
    
    members = query.order_by(FPOMember.name).all()
    return members


@router.post("/{fpo_id}/members", response_model=FPOMemberResponse, status_code=201)
async def add_fpo_member(
    fpo_id: int = Path(..., gt=0),
    request: FPOMemberRequest = ...,
    db: Session = Depends(get_db),
):
    """Add a member to FPO."""
    fpo = db.query(FPO).filter(FPO.id == fpo_id).first()
    if not fpo:
        raise HTTPException(status_code=404, detail="FPO not found")
    
    # Check for duplicate member_id
    if request.member_id:
        existing = db.query(FPOMember).filter(
            FPOMember.fpo_id == fpo_id,
            FPOMember.member_id == request.member_id,
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Member ID already exists in this FPO")
    
    member = FPOMember(
        fpo_id=fpo_id,
        farmer_id=request.farmer_id,
        member_id=request.member_id,
        name=request.name,
        father_spouse_name=request.father_spouse_name,
        phone=request.phone,
        email=request.email,
        aadhaar_hash=request.aadhaar_hash,
        pan=request.pan,
        village=request.village,
        location_id=request.location_id,
        survey_numbers=request.survey_numbers,
        total_area_hectares=request.total_area_hectares,
        irrigated_area_hectares=request.irrigated_area_hectares,
        ownership_type=request.ownership_type,
        shares_held=request.shares_held,
        share_value=request.share_value,
        primary_crops=request.primary_crops,
        annual_production_qtl=request.annual_production_qtl,
        bank_account=request.bank_account,
        date_of_joining=date.today(),
    )
    
    db.add(member)
    
    # Update FPO member count
    fpo.member_count = db.query(FPOMember).filter(
        FPOMember.fpo_id == fpo_id,
        FPOMember.is_active == True,
    ).count() + 1
    
    db.commit()
    db.refresh(member)
    
    return member


@router.patch("/{fpo_id}/members/{member_id}")
async def update_fpo_member(
    fpo_id: int = Path(..., gt=0),
    member_id: int = Path(..., gt=0),
    is_active: Optional[bool] = Query(None),
    membership_status: Optional[str] = Query(None),
    kyc_status: Optional[str] = Query(None),
    shares_held: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Update FPO member details."""
    member = db.query(FPOMember).filter(
        FPOMember.id == member_id,
        FPOMember.fpo_id == fpo_id,
    ).first()
    
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    
    if is_active is not None:
        member.is_active = is_active
    if membership_status:
        member.membership_status = membership_status
    if kyc_status:
        member.kyc_status = kyc_status
    if shares_held is not None:
        member.shares_held = shares_held
    
    member.updated_at = datetime.now(timezone.utc)
    
    # Update FPO member count
    fpo = db.query(FPO).filter(FPO.id == fpo_id).first()
    fpo.member_count = db.query(FPOMember).filter(
        FPOMember.fpo_id == fpo_id,
        FPOMember.is_active == True,
    ).count()
    
    db.commit()
    
    return {"status": "success", "member_id": member.member_id}


# =============================================================================
# Aggregation Plan Endpoints
# =============================================================================

@router.get("/{fpo_id}/aggregation-plans", response_model=List[FPOAggregationPlanResponse])
async def list_aggregation_plans(
    fpo_id: int = Path(..., gt=0),
    status: Optional[str] = Query(None),
    commodity_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Get FPO aggregation plans."""
    fpo = db.query(FPO).filter(FPO.id == fpo_id).first()
    if not fpo:
        raise HTTPException(status_code=404, detail="FPO not found")
    
    query = db.query(FPOAggregationPlan).filter(FPOAggregationPlan.fpo_id == fpo_id)
    
    if status:
        query = query.filter(FPOAggregationPlan.status == status)
    if commodity_id:
        query = query.filter(FPOAggregationPlan.commodity_id == commodity_id)
    
    plans = query.order_by(desc(FPOAggregationPlan.created_at)).all()
    
    # Add commodity names
    result = []
    for p in plans:
        commodity = db.query(Commodity).filter(Commodity.id == p.commodity_id).first()
        result.append(FPOAggregationPlanResponse(
            id=p.id,
            fpo_id=p.fpo_id,
            commodity_id=p.commodity_id,
            commodity_name=commodity.name if commodity else p.commodity_id,
            season=p.season,
            target_quantity_qtl=p.target_quantity_qtl,
            target_grade=p.target_grade,
            collection_start_date=p.collection_start_date,
            collection_end_date=p.collection_end_date,
            status=p.status,
            actual_quantity_qtl=p.actual_quantity_qtl,
            actual_revenue=p.actual_revenue,
            created_at=p.created_at,
        ))
    
    return result


@router.post("/{fpo_id}/aggregation-plans", response_model=FPOAggregationPlanResponse, status_code=201)
async def create_aggregation_plan(
    fpo_id: int = Path(..., gt=0),
    request: FPOAggregationPlanCreateRequest = ...,
    db: Session = Depends(get_db),
):
    """Create a new aggregation plan for collective selling."""
    fpo = db.query(FPO).filter(FPO.id == fpo_id).first()
    if not fpo:
        raise HTTPException(status_code=404, detail="FPO not found")
    
    commodity = db.query(Commodity).filter(Commodity.id == request.commodity_id).first()
    if not commodity:
        raise HTTPException(status_code=404, detail="Commodity not found")
    
    plan = FPOAggregationPlan(
        fpo_id=fpo_id,
        commodity_id=request.commodity_id,
        season=request.season,
        target_quantity_qtl=request.target_quantity_qtl,
        target_grade=request.target_grade,
        collection_start_date=request.collection_start_date,
        collection_end_date=request.collection_end_date,
        collection_centers=request.collection_centers,
        quality_standards=request.quality_standards,
        requires_sorting_grading=request.requires_sorting_grading,
        transport_arranged=request.transport_arranged,
        transport_details=request.transport_details,
        target_markets=request.target_markets,
        target_buyers=request.target_buyers,
        marketing_strategy=request.marketing_strategy,
        status="planned",
    )
    
    db.add(plan)
    db.commit()
    db.refresh(plan)
    
    return FPOAggregationPlanResponse(
        id=plan.id,
        fpo_id=plan.fpo_id,
        commodity_id=plan.commodity_id,
        commodity_name=commodity.name,
        season=plan.season,
        target_quantity_qtl=plan.target_quantity_qtl,
        target_grade=plan.target_grade,
        collection_start_date=plan.collection_start_date,
        collection_end_date=plan.collection_end_date,
        status=plan.status,
        actual_quantity_qtl=plan.actual_quantity_qtl,
        actual_revenue=plan.actual_revenue,
        created_at=plan.created_at,
    )


@router.patch("/{fpo_id}/aggregation-plans/{plan_id}/progress")
async def update_aggregation_progress(
    fpo_id: int = Path(..., gt=0),
    plan_id: int = Path(..., gt=0),
    actual_quantity_qtl: float = Query(..., ge=0),
    actual_revenue: float = Query(..., ge=0),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Update aggregation plan progress."""
    plan = db.query(FPOAggregationPlan).filter(
        FPOAggregationPlan.id == plan_id,
        FPOAggregationPlan.fpo_id == fpo_id,
    ).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    plan.actual_quantity_qtl = actual_quantity_qtl
    plan.actual_revenue = actual_revenue
    if status:
        plan.status = status
    plan.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    
    return {
        "status": "success",
        "plan_id": plan.id,
        "progress_pct": round((actual_quantity_qtl / plan.target_quantity_qtl * 100), 1) if plan.target_quantity_qtl > 0 else 0,
    }


# =============================================================================
# Statistics
# =============================================================================

@router.get("/stats/summary")
async def get_fpo_stats(
    state_id: Optional[int] = Query(None),
    district_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Get FPO statistics."""
    query = db.query(FPO)
    
    if state_id:
        query = query.filter(FPO.state_id == state_id)
    if district_id:
        query = query.filter(FPO.district_id == district_id)
    
    total = query.count()
    active = query.filter(FPO.status == FPOStatus.ACTIVE).count()
    demo = query.filter(FPO.is_demo == True).count()
    
    total_members = db.query(func.sum(FPO.member_count)).filter(
        FPO.state_id == state_id if state_id else True,
        FPO.district_id == district_id if district_id else True,
    ).scalar() or 0
    
    by_type = db.query(FPO.type, func.count(FPO.id)).group_by(FPO.type).all()
    by_status = db.query(FPO.status, func.count(FPO.id)).group_by(FPO.status).all()
    
    return {
        "total": total,
        "active": active,
        "demo": demo,
        "total_members": total_members,
        "by_type": {str(t): c for t, c in by_type},
        "by_status": {str(s): c for s, c in by_status},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health")
async def fpos_health(db: Session = Depends(get_db)):
    """Health check for FPO services."""
    active = db.query(FPO).filter(
        FPO.status == FPOStatus.ACTIVE,
        FPO.is_demo == False,
    ).count()
    
    return {
        "status": "healthy",
        "active_fpos": active,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }