"""Tests for phone normalisation, masking and profile schemas."""

import pytest
from pydantic import ValidationError

from app.models import UserRole
from app.schemas.user import (
    BuyerProfileBase,
    FarmerProfileBase,
    PhoneValidationSample,
    UserPublic,
    mask_phone,
    normalize_phone_e164,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("9876543210", "+919876543210"),
        ("+919876543210", "+919876543210"),
        ("919876543210", "+919876543210"),
        ("09876543210", "+919876543210"),
        ("+91 98765 43210", "+919876543210"),
        ("98765-43210", "+919876543210"),
    ],
)
def test_valid_phone_numbers_normalize(raw: str, expected: str) -> None:
    assert normalize_phone_e164(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["1234567890", "98765", "abcdefghij", "", "  ", "+91987654321", "98765432101"],
)
def test_invalid_phone_numbers_are_rejected(raw: str) -> None:
    with pytest.raises(ValueError):
        normalize_phone_e164(raw)


def test_phone_schema_normalizes_through_pydantic() -> None:
    assert PhoneValidationSample(phone="98765 43210").phone == "+919876543210"


def test_phone_schema_rejects_bad_input() -> None:
    with pytest.raises(ValidationError):
        PhoneValidationSample(phone="not-a-number")


def test_masking_never_reveals_the_full_number() -> None:
    masked = mask_phone("+919876543210")
    assert masked == "+91 ******3210"
    assert "9876543210" not in masked
    assert mask_phone(None) is None


def test_user_public_schema_has_no_raw_phone_field() -> None:
    """The read model must be structurally incapable of leaking a phone number."""
    assert "phone_e164" not in UserPublic.model_fields
    assert "phone_masked" in UserPublic.model_fields


def test_farmer_profile_requires_a_name() -> None:
    with pytest.raises(ValidationError):
        FarmerProfileBase(full_name="A")


def test_privacy_flags_default_to_private() -> None:
    profile = FarmerProfileBase(full_name="Ravi Kumar")
    assert profile.show_exact_location_to_buyers is False
    assert profile.contact_phone_visible is False


def test_buyer_profile_requires_a_business_name() -> None:
    with pytest.raises(ValidationError):
        BuyerProfileBase(business_name="")


def test_roles_enum_covers_all_five_platform_roles() -> None:
    assert {role.value for role in UserRole} == {
        "farmer",
        "buyer",
        "transport_provider",
        "storage_provider",
        "admin",
    }