"""AgriPredict AI ORM models.

Importing this package registers every table on ``Base.metadata``, which is what
Alembic autogenerate and the test fixtures rely on.
"""

from ..core.database import Base
from .base import (
    LocaleCode,
    OtpPurpose,
    OtpStatus,
    ProfileStatus,
    TimestampMixin,
    UserRole,
    UserStatus,
    utcnow,
)
from .identity import BuyerProfile, FarmerProfile, User, UserRoleAssignment
from .lots import (
    ALLOWED_LOT_TRANSITIONS,
    EDITABLE_LOT_STATUSES,
    LotStatus,
    ProduceLot,
    ProduceLotStatusHistory,
)
# Reference tables ship from the phase-3 module; it exposes every table this
# package needs. The phase-6 market tables below are defined in this package's
# .reference module and reuse the same Base.
from .reference import (
    Commodity,
    CommodityGrade,
    CommodityVariety,
    District,
    Locality,
    LocalityKind,
    Mandi,
    MeasurementUnit,
    ReferenceImportLog,
    ReferenceSource,
    State,
    UnitDimension,
    VerificationStatus,
)
from .reference import MarketPrice, MarketPriceCache
from .verification import AuditLog, OtpVerification

__all__ = [
    "ALLOWED_LOT_TRANSITIONS",
    "AuditLog",
    "Base",
    "BuyerProfile",
    "Commodity",
    "CommodityGrade",
    "CommodityVariety",
    "District",
    "EDITABLE_LOT_STATUSES",
    "FarmerProfile",
    "LocaleCode",
    "Locality",
    "LocalityKind",
    "LotStatus",
    "Mandi",
    "MeasurementUnit",
    "OtpPurpose",
    "OtpStatus",
    "OtpVerification",
    "ProduceLot",
    "ProduceLotStatusHistory",
    "ProfileStatus",
    "ReferenceImportLog",
    "ReferenceSource",
    "State",
    "TimestampMixin",
    "UnitDimension",
    "User",
    "UserRole",
    "UserRoleAssignment",
    "UserStatus",
    "VerificationStatus",
    "utcnow",
]
