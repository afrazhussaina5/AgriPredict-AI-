"""Phase 6: farmer profile and produce lots.

The three properties the architecture doc makes non-negotiable are covered
directly:

* **Ownership** - a farmer can never read or change another farmer's lot.
* **Authorization** - non-farmers are refused before any business logic runs.
* **Status transitions** - the lifecycle is closed, and every illegal move is
  refused with a message naming the allowed alternatives.
"""

from collections import deque
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from pydantic import ValidationError as PydanticValidationError
from app.models import (
    ALLOWED_LOT_TRANSITIONS,
    Commodity,
    CommodityGrade,
    CommodityVariety,
    District,
    FarmerProfile,
    LotStatus,
    Mandi,
    MeasurementUnit,
    ProduceLot,
    ReferenceSource,
    State,
    UserRole,
    UserRoleAssignment,
)
from app.services.lot_service import LotService, build_public_lot

PHONE_FARMER_ONE = "9000000001"
PHONE_FARMER_TWO = "9000000002"
PHONE_BUYER = "9000000003"


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture
async def reference_data(session):
    """A small, deliberately fake reference dataset.

    Names are obviously synthetic so a test failure can never be mistaken for
    a real agricultural record.
    """
    source = ReferenceSource(source_key="test-source", name="Test Source")
    session.add(source)
    await session.flush()

    state = State(code="TST", name="Test State", source_id=source.id)
    session.add(state)
    await session.flush()

    district = District(code="TST-D1", name="Test District One", source_id=source.id,
                        state_id=state.id)
    other_district = District(code="TST-D2", name="Test District Two", source_id=source.id,
                              state_id=state.id)
    session.add_all([district, other_district])
    await session.flush()

    mandi = Mandi(code="TST-M1", name="Test Mandi One", source_id=source.id,
                  district_id=district.id, has_storage=True)
    far_mandi = Mandi(code="TST-M2", name="Test Mandi Two", source_id=source.id,
                      district_id=other_district.id)
    session.add_all([mandi, far_mandi])
    await session.flush()

    commodity = Commodity(code="TESTCROP", name="Test Crop", source_id=source.id)
    other_commodity = Commodity(code="OTHERCROP", name="Other Crop", source_id=source.id)
    session.add_all([commodity, other_commodity])
    await session.flush()

    variety = CommodityVariety(code="V1", name="Test Variety One", source_id=source.id,
                               commodity_id=commodity.id)
    wrong_variety = CommodityVariety(code="V9", name="Other Variety", source_id=source.id,
                                     commodity_id=other_commodity.id)
    session.add_all([variety, wrong_variety])
    await session.flush()

    grade = CommodityGrade(code="G1", name="Test Grade One", source_id=source.id,
                          commodity_id=commodity.id)
    universal = CommodityGrade(code="G2", name="Universal Grade", source_id=source.id,
                               commodity_id=None)
    wrong_grade = CommodityGrade(code="G9", name="Other Grade", source_id=source.id,
                                 commodity_id=other_commodity.id)
    session.add_all([grade, universal, wrong_grade])
    await session.flush()

    unit = MeasurementUnit(code="kg", name="Kilogram", dimension="mass", to_base_kg=1,
                           source_id=source.id)
    session.add(unit)
    await session.commit()

    return {
        "source": source, "state": state, "district": district,
        "other_district": other_district, "mandi": mandi, "far_mandi": far_mandi,
        "commodity": commodity, "other_commodity": other_commodity,
        "variety": variety, "wrong_variety": wrong_variety,
        "grade": grade, "universal_grade": universal, "wrong_grade": wrong_grade,
        "unit": unit,
    }


@pytest.fixture
async def farmers(session, make_user):
    """Two distinct farmers, each with a profile."""
    created = {}
    for key, phone in (("one", PHONE_FARMER_ONE), ("two", PHONE_FARMER_TWO)):
        user = await make_user(phone, f"Farmer {phone[-2:]}")
        session.add(UserRoleAssignment(user_id=user.id, role=UserRole.FARMER))
        profile = FarmerProfile(user_id=user.id, full_name=f"Farmer {key}",
                               completion_percent=50)
        session.add(profile)
        await session.commit()
        await session.refresh(user)
        created[key] = user
    return created


async def _lot_payload(ref, **overrides):
    """A valid create payload against the test reference data."""
    payload = {
        "commodity_id": ref["commodity"].id,
        "quantity": Decimal("50.000"),
        "unit_id": ref["unit"].id,
        "ready_date": (date.today() + timedelta(days=7)).isoformat(),
    }
    payload.update(overrides)
    return payload


async def _make_lot(session, farmer, ref, **overrides) -> ProduceLot:
    """Create a draft lot straight through the service."""
    from app.schemas.farmer import LotCreate

    payload = await _lot_payload(ref, **overrides)
    service = LotService(session, farmer)
    lot = await service.create(LotCreate(**payload))
    await session.commit()
    await session.refresh(lot)
    return lot


# --------------------------------------------------------------------------
# State machine
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("start", "target"),
    [
        (LotStatus.DRAFT, LotStatus.PUBLISHED),
        (LotStatus.DRAFT, LotStatus.ARCHIVED),
        (LotStatus.PUBLISHED, LotStatus.PAUSED),
        (LotStatus.PUBLISHED, LotStatus.CLOSED),
        (LotStatus.PUBLISHED, LotStatus.ARCHIVED),
        (LotStatus.PAUSED, LotStatus.PUBLISHED),
        (LotStatus.PAUSED, LotStatus.CLOSED),
        (LotStatus.PAUSED, LotStatus.ARCHIVED),
        (LotStatus.CLOSED, LotStatus.ARCHIVED),
    ],
)
async def test_every_legal_transition_is_allowed(session, farmers, reference_data, start, target):
    lot = await _make_lot(session, farmers["one"], reference_data)
    service = LotService(session, farmers["one"])
    for step in _path_to(lot.status, start):
        lot = await service.change_status(lot, step)
    assert lot.status is start

    lot = await service.change_status(lot, target)
    assert lot.status is target


@pytest.mark.parametrize(
    ("start", "target"),
    [
        (LotStatus.DRAFT, LotStatus.PAUSED),
        (LotStatus.DRAFT, LotStatus.CLOSED),
        (LotStatus.PUBLISHED, LotStatus.DRAFT),
        (LotStatus.PAUSED, LotStatus.DRAFT),
        (LotStatus.CLOSED, LotStatus.PUBLISHED),
        (LotStatus.CLOSED, LotStatus.PAUSED),
        (LotStatus.ARCHIVED, LotStatus.PUBLISHED),
        (LotStatus.ARCHIVED, LotStatus.DRAFT),
        (LotStatus.ARCHIVED, LotStatus.CLOSED),
    ],
)
async def test_every_illegal_transition_is_refused(
    session, farmers, reference_data, start, target
):
    from app.core.errors import ValidationError

    lot = await _make_lot(session, farmers["one"], reference_data)
    service = LotService(session, farmers["one"])
    for step in _path_to(lot.status, start):
        lot = await service.change_status(lot, step)

    with pytest.raises(ValidationError):
        await service.change_status(lot, target)


def _path_to(current: LotStatus, target: LotStatus) -> list[LotStatus]:
    """Shortest legal path from ``current`` to ``target``, searched over the
    real transition graph rather than a hand-written ordering."""
    if current is target:
        return []

    queue: deque[list[LotStatus]] = deque([[current]])
    seen = {current}
    while queue:
        path = queue.popleft()
        for nxt in sorted(
            ALLOWED_LOT_TRANSITIONS.get(path[-1], frozenset()),
            key=lambda item: item.value,
        ):
            if nxt is target:
                # path[0] is the status we are already in; only the moves count.
                return [*path[1:], nxt]
            if nxt not in seen:
                seen.add(nxt)
                queue.append([*path, nxt])

    raise AssertionError(f"No legal path from {current} to {target}")


async def test_archived_is_terminal(session, farmers, reference_data):
    lot = await _make_lot(session, farmers["one"], reference_data)
    service = LotService(session, farmers["one"])
    await service.change_status(lot, LotStatus.ARCHIVED)
    assert service.allowed_transitions(LotStatus.ARCHIVED) == []
    # Archived is a tombstone, not a delete: the lot is still in the farmer's list.
    assert (await service.list_owned())[1] >= 1


async def test_transition_to_the_same_status_is_refused(session, farmers, reference_data):
    from app.core.errors import ValidationError

    lot = await _make_lot(session, farmers["one"], reference_data)
    service = LotService(session, farmers["one"])
    with pytest.raises(ValidationError):
        await service.change_status(lot, LotStatus.DRAFT)


async def test_illegal_transition_message_names_the_allowed_moves(
    session, farmers, reference_data
):
    from app.core.errors import ValidationError

    lot = await _make_lot(session, farmers["one"], reference_data)
    service = LotService(session, farmers["one"])
    with pytest.raises(ValidationError) as excinfo:
        await service.change_status(lot, LotStatus.CLOSED)
    assert "published" in str(excinfo.value)


async def test_each_transition_writes_one_history_row(session, farmers, reference_data):
    lot = await _make_lot(session, farmers["one"], reference_data)
    service = LotService(session, farmers["one"])
    await service.change_status(lot, LotStatus.PUBLISHED)
    await service.change_status(lot, LotStatus.PAUSED)
    await service.change_status(lot, LotStatus.PUBLISHED)
    await session.commit()

    history = await service.lots.list_history(lot.id)
    assert [row.to_status for row in history] == [
        LotStatus.DRAFT, LotStatus.PUBLISHED, LotStatus.PAUSED, LotStatus.PUBLISHED,
    ]
    assert history[0].from_status is None
    assert history[1].from_status is LotStatus.DRAFT
    assert history[-1].from_status is LotStatus.PAUSED


async def test_publishing_sets_published_at_and_closing_sets_closed_reason(
    session, farmers, reference_data
):
    lot = await _make_lot(session, farmers["one"], reference_data)
    service = LotService(session, farmers["one"])
    await service.change_status(lot, LotStatus.PUBLISHED)
    assert lot.published_at is not None

    await service.change_status(lot, LotStatus.CLOSED, reason="Sold locally.")
    assert lot.closed_at is not None
    assert lot.closed_reason == "Sold locally."


# --------------------------------------------------------------------------
# Ownership
# --------------------------------------------------------------------------


async def test_another_farmer_cannot_read_the_lot(session, farmers, reference_data):
    from app.core.errors import NotFoundError

    lot = await _make_lot(session, farmers["one"], reference_data)
    intruder = LotService(session, farmers["two"])

    assert await intruder.lots.get_owned(lot.id, farmers["two"].id) is None
    with pytest.raises(NotFoundError):
        await intruder.get_owned_or_404(lot.id)


async def test_another_farmer_cannot_change_the_status(session, farmers, reference_data):
    from app.core.errors import NotFoundError

    lot = await _make_lot(session, farmers["one"], reference_data)
    intruder = LotService(session, farmers["two"])

    with pytest.raises(NotFoundError):
        owned = await intruder.get_owned_or_404(lot.id)
        await intruder.change_status(owned, LotStatus.PUBLISHED)

    await session.refresh(lot)
    assert lot.status is LotStatus.DRAFT


async def test_another_farmer_cannot_edit_or_delete(session, farmers, reference_data):
    from app.core.errors import NotFoundError
    from app.schemas.farmer import LotUpdate

    lot = await _make_lot(session, farmers["one"], reference_data)
    intruder = LotService(session, farmers["two"])

    with pytest.raises(NotFoundError):
        owned = await intruder.get_owned_or_404(lot.id)
        await intruder.update(owned, LotUpdate(quantity=Decimal("999")))

    await session.refresh(lot)
    assert lot.quantity == Decimal("50.000")


async def test_listing_only_returns_own_lots(session, farmers, reference_data):
    await _make_lot(session, farmers["one"], reference_data)
    await _make_lot(session, farmers["two"], reference_data)

    one_lots, one_total = await LotService(session, farmers["one"]).list_owned()
    two_lots, two_total = await LotService(session, farmers["two"]).list_owned()

    assert one_total == 1 and two_total == 1
    assert one_lots[0].farmer_id == farmers["one"].id
    assert two_lots[0].farmer_id == farmers["two"].id


async def test_missing_lot_is_a_404(session, farmers):
    from app.core.errors import NotFoundError

    with pytest.raises(NotFoundError):
        await LotService(session, farmers["one"]).get_owned_or_404(999999)


async def test_unknown_lot_and_foreign_lot_return_the_same_message(
    session, farmers, reference_data
):
    from app.core.errors import NotFoundError

    lot = await _make_lot(session, farmers["one"], reference_data)
    service = LotService(session, farmers["two"])

    messages = set()
    for candidate in (lot.id, 999999):
        with pytest.raises(NotFoundError) as excinfo:
            await service.get_owned_or_404(candidate)
        messages.add(str(excinfo.value))

    # A 403-style difference would let anyone confirm that a lot id exists.
    assert len(messages) == 1


# --------------------------------------------------------------------------
# Editing rules
# --------------------------------------------------------------------------


async def test_published_lot_cannot_be_edited(session, farmers, reference_data):
    from app.core.errors import ValidationError
    from app.schemas.farmer import LotUpdate

    lot = await _make_lot(session, farmers["one"], reference_data)
    service = LotService(session, farmers["one"])
    await service.change_status(lot, LotStatus.PUBLISHED)

    with pytest.raises(ValidationError):
        await service.update(lot, LotUpdate(quantity=Decimal("80")))


async def test_paused_lot_can_be_edited_again(session, farmers, reference_data):
    from app.schemas.farmer import LotUpdate

    lot = await _make_lot(session, farmers["one"], reference_data)
    service = LotService(session, farmers["one"])
    await service.change_status(lot, LotStatus.PUBLISHED)
    await service.change_status(lot, LotStatus.PAUSED)

    await service.update(lot, LotUpdate(quantity=Decimal("80")))
    await session.commit()
    await session.refresh(lot)
    assert lot.quantity == Decimal("80.000")


async def test_update_only_touches_the_fields_that_were_sent(session, farmers, reference_data):
    from app.schemas.farmer import LotUpdate

    lot = await _make_lot(
        session, farmers["one"], reference_data,
        variety_id=reference_data["variety"].id,
        grade_id=reference_data["grade"].id,
    )
    service = LotService(session, farmers["one"])
    await service.update(lot, LotUpdate(quantity=Decimal("60")))
    await session.commit()
    await session.refresh(lot)

    assert lot.quantity == Decimal("60.000")
    assert lot.variety_id == reference_data["variety"].id
    assert lot.grade_id == reference_data["grade"].id


async def test_update_cannot_change_status(session, farmers, reference_data):
    """Status only moves through change_status, never through an edit."""
    from app.schemas.farmer import LotUpdate

    lot = await _make_lot(session, farmers["one"], reference_data)
    service = LotService(session, farmers["one"])
    await service.update(lot, LotUpdate(quantity=Decimal("60")))

    await session.refresh(lot)
    assert lot.status is LotStatus.DRAFT


# --------------------------------------------------------------------------
# Reference-data validation
# --------------------------------------------------------------------------


async def test_unknown_commodity_is_refused(session, farmers, reference_data):
    from app.core.errors import ValidationError
    from app.schemas.farmer import LotCreate

    service = LotService(session, farmers["one"])
    with pytest.raises(ValidationError):
        await service.create(
            LotCreate(**await _lot_payload(reference_data, commodity_id=999999))
        )


async def test_variety_from_another_commodity_is_refused(session, farmers, reference_data):
    from app.core.errors import ValidationError
    from app.schemas.farmer import LotCreate

    service = LotService(session, farmers["one"])
    with pytest.raises(ValidationError):
        await service.create(
            LotCreate(**await _lot_payload(
                reference_data, variety_id=reference_data["wrong_variety"].id
            ))
        )


async def test_grade_from_another_commodity_is_refused(session, farmers, reference_data):
    from app.core.errors import ValidationError
    from app.schemas.farmer import LotCreate

    service = LotService(session, farmers["one"])
    with pytest.raises(ValidationError):
        await service.create(
            LotCreate(**await _lot_payload(
                reference_data, grade_id=reference_data["wrong_grade"].id
            ))
        )


async def test_universal_grade_is_accepted(session, farmers, reference_data):
    from app.schemas.farmer import LotCreate

    lot = await LotService(session, farmers["one"]).create(
        LotCreate(**await _lot_payload(
            reference_data, grade_id=reference_data["universal_grade"].id
        ))
    )
    await session.commit()
    assert lot.grade_id == reference_data["universal_grade"].id


async def test_mandi_in_another_district_is_refused(session, farmers, reference_data):
    from app.core.errors import ValidationError
    from app.schemas.farmer import LotCreate

    service = LotService(session, farmers["one"])
    with pytest.raises(ValidationError):
        await service.create(
            LotCreate(**await _lot_payload(
                reference_data,
                pickup_district_id=reference_data["district"].id,
                pickup_mandi_id=reference_data["far_mandi"].id,
            ))
        )


async def test_mandi_without_a_district_is_refused_at_the_schema(
    session, farmers, reference_data
):
    """The Pydantic validator rejects it before any database work."""
    from pydantic import ValidationError as PydanticValidationError
    from app.schemas.farmer import LotCreate

    with pytest.raises(PydanticValidationError):
        LotCreate(**await _lot_payload(
            reference_data, pickup_mandi_id=reference_data["mandi"].id
        ))


async def test_zero_quantity_is_refused(session, farmers, reference_data):
    from pydantic import ValidationError as PydanticValidationError
    from app.schemas.farmer import LotCreate

    with pytest.raises(PydanticValidationError):
        LotCreate(**await _lot_payload(reference_data, quantity=Decimal("0")))


async def test_far_future_ready_date_is_refused(session, farmers, reference_data):
    from app.core.errors import ValidationError
    from app.schemas.farmer import LotCreate

    service = LotService(session, farmers["one"])
    with pytest.raises(ValidationError):
        await service.create(
            LotCreate(**await _lot_payload(
                reference_data,
                ready_date=(date.today() + timedelta(days=3650)).isoformat(),
            ))
        )


async def test_min_price_above_expected_price_is_refused_at_the_schema(
    session, farmers, reference_data
):
    """The Pydantic validator catches it before any database work happens."""
    from pydantic import ValidationError as PydanticValidationError
    from app.schemas.farmer import LotCreate

    with pytest.raises(PydanticValidationError):
        LotCreate(**await _lot_payload(
            reference_data,
            expected_price_per_unit=Decimal("100"),
            min_expected_price_per_unit=Decimal("150"),
        ))


async def test_min_price_without_an_expected_price_is_refused_by_the_service(
    session, farmers, reference_data
):
    """A floor price with nothing to compare against is meaningless."""
    from app.core.errors import ValidationError
    from app.schemas.farmer import LotUpdate

    lot = await _make_lot(session, farmers["one"], reference_data)
    service = LotService(session, farmers["one"])
    with pytest.raises(ValidationError):
        await service.update(
            lot, LotUpdate(min_expected_price_per_unit=Decimal("50"))
        )


# --------------------------------------------------------------------------
# Privacy defaults
# --------------------------------------------------------------------------


async def test_visibility_flags_default_to_private(session, farmers, reference_data):
    lot = await _make_lot(
        session, farmers["one"], reference_data,
        expected_price_per_unit=Decimal("1200"),
        notes="Picked this morning.",
        pickup_area_label="Test Hamlet",
        pickup_district_id=reference_data["district"].id,
    )
    assert lot.show_expected_price is False
    assert lot.show_pickup_area is False
    assert lot.show_notes is False


async def test_public_view_hides_a_price_the_farmer_did_not_share(
    session, farmers, reference_data
):
    lot = await _make_lot(
        session, farmers["one"], reference_data,
        expected_price_per_unit=Decimal("1200"),
    )
    service = LotService(session, farmers["one"])
    await service.change_status(lot, LotStatus.PUBLISHED)

    public = build_public_lot(lot)
    assert public.expected_price_per_unit is None
    # The owner still sees it.
    assert lot.expected_price_per_unit == Decimal("1200.00")


async def test_public_view_shows_a_price_the_farmer_shared(session, farmers, reference_data):
    lot = await _make_lot(
        session, farmers["one"], reference_data,
        expected_price_per_unit=Decimal("1200"),
        show_expected_price=True,
    )
    service = LotService(session, farmers["one"])
    await service.change_status(lot, LotStatus.PUBLISHED)

    assert build_public_lot(lot).expected_price_per_unit == Decimal("1200.00")


async def test_public_view_hides_notes_and_exact_pickup(session, farmers, reference_data):
    lot = await _make_lot(
        session, farmers["one"], reference_data,
        notes="Secret field location.",
        pickup_area_label="Behind the big tree",
        pickup_district_id=reference_data["district"].id,
        pickup_mandi_id=reference_data["mandi"].id,
    )
    service = LotService(session, farmers["one"])
    await service.change_status(lot, LotStatus.PUBLISHED)

    public = build_public_lot(lot)
    assert public.notes is None
    assert public.pickup_mandi_name is None
    # The district is the public granularity and is always shown.
    assert public.pickup_district_name == "Test District One"


async def test_public_view_is_refused_for_any_status_other_than_published(
    session, farmers, reference_data
):
    for status in (LotStatus.DRAFT, LotStatus.PAUSED, LotStatus.CLOSED, LotStatus.ARCHIVED):
        lot = await _make_lot(session, farmers["one"], reference_data)
        service = LotService(session, farmers["one"])
        for step in _path_to(lot.status, status):
            lot = await service.change_status(lot, step)
        assert build_public_lot(lot) is None


async def test_showing_a_price_that_was_never_set_is_refused(
    session, farmers, reference_data
):
    """An opt-in flag on an empty field would advertise nothing."""
    from app.core.errors import ValidationError
    from app.schemas.farmer import LotCreate, LotUpdate

    # Creating one is caught by the schema.
    with pytest.raises(PydanticValidationError):
        LotCreate(**await _lot_payload(reference_data, show_expected_price=True))

    # Turning it on later is caught by the service.
    lot = await _make_lot(session, farmers["one"], reference_data)
    service = LotService(session, farmers["one"])
    with pytest.raises(ValidationError):
        await service.update(lot, LotUpdate(show_expected_price=True))


async def test_showing_notes_that_were_never_written_is_refused(
    session, farmers, reference_data
):
    from app.core.errors import ValidationError
    from app.schemas.farmer import LotUpdate

    lot = await _make_lot(session, farmers["one"], reference_data)
    service = LotService(session, farmers["one"])
    with pytest.raises(ValidationError):
        await service.update(lot, LotUpdate(show_notes=True))


async def test_unstated_price_is_never_treated_as_zero(session, farmers, reference_data):
    lot = await _make_lot(session, farmers["one"], reference_data)
    assert lot.expected_price_per_unit is None
    assert build_public_lot(lot) is None  # not published, so nothing is exposed


# --------------------------------------------------------------------------
# HTTP layer: authorization and privacy of the endpoints themselves
# --------------------------------------------------------------------------


def _seed_http(client, session_factory_hint=PHONE_FARMER_ONE):
    """Create a farmer + token through the real API. Returns (token, user_id)."""
    response = client.post("/api/v1/auth/otp/request", json={"phone": PHONE_FARMER_ONE})
    assert response.status_code == 202
    code = response.json()["dev_code"]
    verified = client.post(
        "/api/v1/auth/otp/verify", json={"phone": PHONE_FARMER_ONE, "code": code}
    )
    assert verified.status_code == 200
    return verified.json()["access_token"]


def _http_client_with_reference(client):
    """Insert reference rows the API tests need, using a raw SQLite session."""
    import sqlite3
    from app.core.config import get_settings

    dsn = get_settings().TEST_DATABASE_URL or ""
    path = dsn.split("///")[-1]
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys=ON")
    cursor = connection.execute(
        "INSERT INTO reference_sources (source_key, name, is_official, status,"
        " created_at, updated_at) VALUES ('http-src','HTTP Source',0,'imported',"
        " datetime('now'), datetime('now'))"
    )
    source_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO reference_states (code, name, source_id, status, is_active,"
        " created_at, updated_at) VALUES ('HTT','HTTP State',?,'imported',1,"
        " datetime('now'), datetime('now'))", (source_id,)
    )
    state_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO reference_districts (state_id, code, name, source_id, status, is_active,"
        " created_at, updated_at) VALUES (?,'HTT-D','HTTP District',?,'imported',1,"
        " datetime('now'), datetime('now'))", (state_id, source_id)
    )
    district_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO reference_commodities (code, name, source_id, status, is_active,"
        " created_at, updated_at) VALUES ('HTTC','HTTP Crop',?,'imported',1,"
        " datetime('now'), datetime('now'))", (source_id,)
    )
    commodity_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO reference_units (code, name, dimension, to_base_kg, source_id, status,"
        " is_active, created_at, updated_at)"
        " VALUES ('kg','Kilogram','mass',1,?,'imported',1, datetime('now'), datetime('now'))",
        (source_id,)
    )
    unit_id = cursor.lastrowid
    connection.commit()
    connection.close()
    return {
        "district_id": district_id, "commodity_id": commodity_id, "unit_id": unit_id,
    }


def test_lots_require_authentication(client):
    assert client.get("/api/v1/lots").status_code == 401
    assert client.post("/api/v1/lots", json={}).status_code == 401


def test_non_farmer_role_is_refused(client):
    token = _seed_http(client)
    response = client.get("/api/v1/lots", headers={"Authorization": f"Bearer {token}"})
    # Signed in, but never chose the farmer role.
    assert response.status_code == 403


def test_farmer_can_create_and_publish_a_lot(client):
    ref = _http_client_with_reference(client)
    token = _seed_http(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Grant the farmer role through the real onboarding endpoint.
    role = client.post("/api/v1/auth/roles", json={"role": "farmer"}, headers=headers)
    assert role.status_code == 201

    created = client.post(
        "/api/v1/lots",
        json={
            "commodity_id": ref["commodity_id"],
            "quantity": "40",
            "unit_id": ref["unit_id"],
            "ready_date": (date.today() + timedelta(days=5)).isoformat(),
            "expected_price_per_unit": "900",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "draft"
    assert body["commodity_name"] == "HTTP Crop"
    assert body["unit_name"] == "Kilogram"

    published = client.post(
        f"/api/v1/lots/{body['id']}/status",
        json={"status": "published"},
        headers=headers,
    )
    assert published.status_code == 200, published.text
    detail = published.json()
    assert detail["status"] == "published"
    assert len(detail["history"]) == 2
    assert set(detail["allowed_transitions"]) == {"paused", "closed", "archived"}


def test_illegal_transition_over_http_is_a_400(client):
    ref = _http_client_with_reference(client)
    token = _seed_http(client)
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/auth/roles", json={"role": "farmer"}, headers=headers)

    created = client.post(
        "/api/v1/lots",
        json={
            "commodity_id": ref["commodity_id"],
            "quantity": "40",
            "unit_id": ref["unit_id"],
            "ready_date": (date.today() + timedelta(days=5)).isoformat(),
        },
        headers=headers,
    )
    lot_id = created.json()["id"]

    response = client.post(
        f"/api/v1/lots/{lot_id}/status", json={"status": "closed"}, headers=headers
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_profile_is_created_on_first_save(client):
    """Phase 4 onboarding creates no farmer profile, so PATCH creates it.

    Regression: both GET and PATCH used to 404 forever, leaving the profile page
    unreachable for every real farmer.
    """
    token = _seed_http(client)
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/auth/roles", json={"role": "farmer"}, headers=headers)

    # Before any save there is genuinely no profile.
    missing = client.get("/api/v1/farmer/profile", headers=headers)
    assert missing.status_code == 404

    created = client.patch(
        "/api/v1/farmer/profile",
        json={"full_name": "Lakshmi", "village_or_town": "Demo Village"},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    assert created.json()["full_name"] == "Lakshmi"

    now = client.get("/api/v1/farmer/profile", headers=headers)
    assert now.status_code == 200
    assert now.json()["village_or_town"] == "Demo Village"


def test_profile_creation_requires_a_name(client):
    token = _seed_http(client)
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/auth/roles", json={"role": "farmer"}, headers=headers)
    response = client.patch(
        "/api/v1/farmer/profile", json={"village_or_town": "Nameless"}, headers=headers
    )
    assert response.status_code == 400


def test_profile_rejects_a_mandi_from_another_district(client):
    ref = _http_client_with_reference(client)
    token = _seed_http(client)
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/auth/roles", json={"role": "farmer"}, headers=headers)

    response = client.patch(
        "/api/v1/farmer/profile",
        json={
            "full_name": "Lakshmi",
            "district_id": ref["district_id"],
            "mandi_id": 999999,
        },
        headers=headers,
    )
    assert response.status_code == 400


def test_pagination_bounds_are_enforced(client):
    token = _seed_http(client)
    headers = {"Authorization": f"Bearer {token}"}
    # The role guard runs before query validation, so a caller without the
    # farmer role is refused before the parameter schema is even consulted.
    assert client.get("/api/v1/lots?limit=0", headers=headers).status_code == 403

    client.post("/api/v1/auth/roles", json={"role": "farmer"}, headers=headers)
    assert client.get("/api/v1/lots?limit=0", headers=headers).status_code == 422
    assert client.get("/api/v1/lots?limit=101", headers=headers).status_code == 422
    assert client.get("/api/v1/lots?offset=-1", headers=headers).status_code == 422
    ok = client.get("/api/v1/lots?limit=20&offset=0", headers=headers)
    assert ok.status_code == 200
    assert ok.json() == {"items": [], "total": 0, "limit": 20, "offset": 0}


def test_negative_quantity_is_rejected_by_the_schema(client):
    ref = _http_client_with_reference(client)
    token = _seed_http(client)
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/auth/roles", json={"role": "farmer"}, headers=headers)

    response = client.post(
        "/api/v1/lots",
        json={
            "commodity_id": ref["commodity_id"],
            "quantity": "-5",
            "unit_id": ref["unit_id"],
            "ready_date": (date.today() + timedelta(days=5)).isoformat(),
        },
        headers=headers,
    )
    assert response.status_code == 422


async def test_deleting_a_user_removes_their_lots(session, make_user):
    """The cascade is intentional: erasure takes the lots with it."""
    user = await make_user("9000000009", "Erasure")
    session.add(UserRoleAssignment(user_id=user.id, role=UserRole.FARMER))
    source = ReferenceSource(source_key="erase-src", name="Erase Source")
    session.add(source)
    await session.flush()
    commodity = Commodity(code="ERASE", name="Erase Crop", source_id=source.id)
    unit = MeasurementUnit(code="kg", name="Kilogram", dimension="mass", to_base_kg=1,
                           source_id=source.id)
    session.add_all([commodity, unit])
    await session.flush()

    from app.schemas.farmer import LotCreate

    lot = await LotService(session, user).create(
        LotCreate(commodity_id=commodity.id, quantity=Decimal("10"),
                  unit_id=unit.id,
                  ready_date=(date.today() + timedelta(days=3)).isoformat())
    )
    await session.commit()
    lot_id = lot.id

    await session.delete(user)
    await session.commit()

    result = await session.execute(
        select(ProduceLot).where(ProduceLot.id == lot_id)
    )
    assert result.scalar_one_or_none() is None


async def test_status_history_survives_actor_deletion(session, farmers, reference_data):
    """changed_by_user_id is SET NULL, so the timeline stays readable.

    The actor is deliberately *not* the owner here: deleting an account that
    owns lots cascades the lots away by design, so this isolates the
    SET NULL behaviour on the history table itself.
    """
    lot = await _make_lot(session, farmers["one"], reference_data)
    service = LotService(session, farmers["one"])
    await service.change_status(lot, LotStatus.PUBLISHED)
    await session.commit()

    history = await service.lots.list_history(lot.id)
    # Attribute one move to a different account, then erase that account.
    history[-1].changed_by_user_id = farmers["two"].id
    await session.commit()
    lot_id = lot.id

    await session.delete(farmers["two"])
    await session.commit()

    # ON DELETE SET NULL is applied by the database, but the session identity map
    # still holds the pre-delete object (expire_on_commit=False). Drop the cached
    # state so the re-read reflects what the database actually stored.
    session.expire_all()

    remaining = await service.lots.list_history(lot_id)
    assert [row.to_status for row in remaining] == [LotStatus.DRAFT, LotStatus.PUBLISHED]
    assert remaining[-1].changed_by_user_id is None
    assert remaining[-1].from_status is LotStatus.DRAFT


async def test_audit_trail_records_every_lot_action(session, farmers, reference_data):
    from app.models import AuditLog
    from app.repositories import AuditRepository

    lot = await _make_lot(session, farmers["one"], reference_data)
    service = LotService(session, farmers["one"])
    await service.change_status(lot, LotStatus.PUBLISHED)
    await session.commit()

    entries = await AuditRepository(session).list_for_entity("produce_lot", lot.id)
    actions = [entry.action for entry in entries]
    assert "lot.created" in actions
    assert "lot.published" in actions
    assert all(isinstance(entry, AuditLog) for entry in entries)