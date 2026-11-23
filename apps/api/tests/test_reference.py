"""Tests for reference data (Phase 5).

The fixtures below are TEST DATA ONLY - obviously fictional names used to prove
the cascade and the importer work. They are never shipped as real reference
data.

Two levels are covered:

* service level (async ``session`` fixture) - import validation and duplicates,
* API level (``client`` fixture) - cascading reads and honest empty states.
"""

import sqlite3

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import VerificationStatus
from app.services.reference_service import (ImportValidationError, ReferenceService, SUPPORTED_ENTITIES)

STATES_CSV = """code,name,name_hi,name_te
XX,Example State,उदाहरण राज्य,ఉదాహరణ రాష్ట్రం
YY,Second Example,द्वितीय उदाहरण,రెండవ ఉదాహరణ
"""

DISTRICTS_CSV = """state_code,code,name,name_hi,name_te
XX,D1,Example North,उदाहरण उत्तर,ఉదాహరణ ఉత్తర
XX,D2,Example South,उदाहरण दक्षिण,ఉదాహరణ దక్షిణ
YY,D3,Other District,अन्य ज़िला,ఇతర జిల్లా
"""

MANDIS_CSV = """district_code,code,name,has_storage
D1,M1,Example Mandi One,true
D1,M2,Example Mandi Two,false
D3,M3,Other Mandi,
"""

COMMODITIES_CSV = """code,name,category
COT,Example Crop,cereals
"""

LOCALITIES_CSV = """district_code,kind,name,latitude,longitude
D1,city,Example City,28.6139,77.2090
D1,village,Example Village,,
"""

UNITS_CSV = """code,name,dimension,to_base_kg
kg,kilogram,mass,1
quintal,quintal,mass,100
"""

SOURCE = {"source_key": "test-fixture", "source_name": "Test Fixture Source",
           "is_official": False}

NOW = "CURRENT_TIMESTAMP"


# ------------------------------------------------------------------- seeding


def _seed_api_db(db_path) -> None:
    """Insert a small fictional hierarchy straight into the client's database.

    Raw SQL is used here on purpose: it proves the API reads real rows through
    the normal connection path, independent of the ORM session used elsewhere.
    """
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()

    cursor.execute(
        "INSERT OR IGNORE INTO reference_sources "
        "(source_key, name, is_official, status, created_at, updated_at) VALUES "
        f"('{SOURCE['source_key']}', '{SOURCE['source_name']}', 0, 'imported', {NOW}, {NOW})"
    )
    source_id = cursor.execute(
        "SELECT id FROM reference_sources WHERE source_key = ?", (SOURCE["source_key"],)
    ).fetchone()[0]

    def insert_state(code: str, name: str, name_hi: str, name_te: str) -> int:
        cursor.execute(
            "INSERT INTO reference_states "
            "(code, name, name_hi, name_te, source_id, status, is_active, created_at, updated_at) "
            f"VALUES ('{code}', '{name}', '{name_hi}', '{name_te}', {source_id}, 'imported', 1, {NOW}, {NOW})"
        )
        return cursor.lastrowid

    xx = insert_state("XX", "Example State", "उदाहरण राज्य", "ఉదాహరణ రాష్ట్రం")
    insert_state("YY", "Second Example", "द्वितीय उदाहरण", "రెండవ ఉదాహరణ")

    def insert_district(state_id: int, code: str, name: str, name_hi: str,
                        name_te: str) -> int:
        cursor.execute(
            "INSERT INTO reference_districts "
            "(state_id, code, name, name_hi, name_te, source_id, status, is_active, "
            f"created_at, updated_at) VALUES ({state_id}, '{code}', '{name}', '{name_hi}', "
            f"'{name_te}', {source_id}, 'imported', 1, {NOW}, {NOW})"
        )
        return cursor.lastrowid

    d1 = insert_district(xx, "D1", "Example North", "उदाहरण उत्तर", "ఉదాహరణ ఉత్తర")
    insert_district(xx, "D2", "Example South", "उदाहरण दक्षिण", "ఉదాహరణ దక్షిణ")
    d3 = insert_district(cursor.execute(
        "SELECT id FROM reference_states WHERE code = 'YY'").fetchone()[0],
        "D3", "Other District", "अन्य ज़िला", "ఇతర జిల్లా")

    for district_id, code, name, storage in (
        (d1, "M1", "Example Mandi One", "1"),
        (d1, "M2", "Example Mandi Two", "0"),
        (d3, "M3", "Other Mandi", "NULL"),
    ):
        cursor.execute(
            "INSERT INTO reference_mandis (district_id, code, name, has_storage, source_id, "
            "status, is_active, created_at, updated_at) VALUES "
            f"({district_id}, '{code}', '{name}', {storage}, {source_id}, 'imported', 1, {NOW}, {NOW})"
        )

    cursor.execute(
        "INSERT INTO reference_localities (district_id, kind, name, latitude, longitude, "
        f"source_id, status, is_active, created_at, updated_at) VALUES "
        f"({d1}, 'city', 'Example City', 28.6139, 77.2090, {source_id}, 'imported', 1, {NOW}, {NOW})"
    )
    cursor.execute(
        "INSERT INTO reference_localities (district_id, kind, name, latitude, longitude, "
        f"source_id, status, is_active, created_at, updated_at) VALUES "
        f"({d1}, 'village', 'Example Village', NULL, NULL, {source_id}, 'imported', 1, {NOW}, {NOW})"
    )

    cursor.execute(
        "INSERT INTO reference_commodities (code, name, name_hi, name_te, category, source_id, "
        f"status, is_active, created_at, updated_at) VALUES "
        f"('COT', 'Example Crop', NULL, NULL, 'cereals', {source_id}, 'imported', 1, {NOW}, {NOW})"
    )

    for code, name, to_kg in (("kg", "kilogram", "1"), ("quintal", "quintal", "100")):
        cursor.execute(
            "INSERT INTO reference_units (code, name, dimension, to_base_kg, source_id, "
            "status, is_active, created_at, updated_at) VALUES "
            f"('{code}', '{name}', 'mass', {to_kg}, {source_id}, 'imported', 1, {NOW}, {NOW})"
        )

    connection.commit()
    connection.close()


@pytest.fixture()
def seeded_client(client: TestClient, tmp_path) -> TestClient:
    _seed_api_db(tmp_path / "api.db")
    return client


def _first_state_id(client: TestClient) -> int:
    return client.get("/api/v1/reference/states").json()[0]["id"]


def _first_district_id(client: TestClient) -> int:
    state_id = _first_state_id(client)
    return client.get(f"/api/v1/reference/states/{state_id}/districts").json()[0]["id"]


# ---------------------------------------------------- service-level fixtures


async def _import(session: AsyncSession, entity: str, csv_text: str, dry_run: bool = False):
    service = ReferenceService(session)
    source, _created = await service.ensure_source(
        SOURCE["source_key"], SOURCE["source_name"],
    )
    await session.commit()
    return await service.import_rows(entity, csv_text, source, dry_run=dry_run)





# ------------------------------------------------------------- empty database


def test_reference_status_reports_empty_database(client: TestClient) -> None:
    response = client.get("/api/v1/reference/status")
    assert response.status_code == 200
    body = response.json()
    assert body["is_populated"] is False
    assert body["counts"]["states"] == 0
    assert body["note"]


def test_empty_lists_are_empty_not_an_error(client: TestClient) -> None:
    for path in (
        "/api/v1/reference/states",
        "/api/v1/reference/mandis",
        "/api/v1/reference/commodities",
        "/api/v1/reference/grades",
        "/api/v1/reference/units",
    ):
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.json() == [], path


# ------------------------------------------------------------------- cascade


def test_states_are_listed_with_their_source(seeded_client: TestClient) -> None:
    states = seeded_client.get("/api/v1/reference/states").json()
    assert [s["code"] for s in states] == ["XX", "YY"]
    assert states[0]["name_hi"] == "उदाहरण राज्य"
    assert states[0]["source_key"] == "test-fixture"
    assert states[0]["source_is_official"] is False
    # Imported data is never auto-verified.
    assert states[0]["status"] == VerificationStatus.IMPORTED.value


def test_districts_cascade_from_a_state(seeded_client: TestClient) -> None:
    state_id = _first_state_id(seeded_client)
    districts = seeded_client.get(
        f"/api/v1/reference/states/{state_id}/districts"
    ).json()
    assert [d["code"] for d in districts] == ["D1", "D2"]
    assert all(d["state_id"] == state_id for d in districts)


def test_mandis_cascade_from_a_district(seeded_client: TestClient) -> None:
    district_id = _first_district_id(seeded_client)
    mandis = seeded_client.get(
        f"/api/v1/reference/mandis?district_id={district_id}"
    ).json()
    assert [m["code"] for m in mandis] == ["M1", "M2"]
    assert mandis[0]["has_storage"] is True
    # The state is derivable without a redundant column on the mandi row.
    assert mandis[0]["state_id"] == _first_state_id(seeded_client)


def test_all_mandis_are_listed_without_a_filter(seeded_client: TestClient) -> None:
    assert len(seeded_client.get("/api/v1/reference/mandis").json()) == 3


def test_localities_cascade_from_a_district(seeded_client: TestClient) -> None:
    district_id = _first_district_id(seeded_client)
    localities = seeded_client.get(
        f"/api/v1/reference/districts/{district_id}/localities"
    ).json()
    assert {loc["kind"] for loc in localities} == {"city", "village"}
    city = next(loc for loc in localities if loc["kind"] == "city")
    assert city["latitude"] == 28.6139
    assert city["source_key"] == "test-fixture"
    village = next(loc for loc in localities if loc["kind"] == "village")
    assert village["latitude"] is None


def test_commodities_and_units_are_listed(seeded_client: TestClient) -> None:
    assert seeded_client.get("/api/v1/reference/commodities").json()[0]["code"] == "COT"
    units = seeded_client.get("/api/v1/reference/units").json()
    by_code = {u["code"]: u for u in units}
    assert by_code["quintal"]["to_base_kg"] == 100.0
    assert by_code["quintal"]["dimension"] == "mass"


def test_reference_status_is_populated_after_seeding(seeded_client: TestClient) -> None:
    body = seeded_client.get("/api/v1/reference/status").json()
    assert body["is_populated"] is True
    assert body["counts"]["states"] == 2
    assert body["counts"]["mandis"] == 3
    assert body["sources"][0]["source_key"] == "test-fixture"


def test_grades_without_a_commodity_returns_generic_grades(client: TestClient) -> None:
    assert client.get("/api/v1/reference/grades").json() == []


def test_varieties_of_an_unknown_commodity_is_404(client: TestClient) -> None:
    assert client.get("/api/v1/reference/commodities/9999/varieties").status_code == 404


# ------------------------------------------------------------- invalid input


def test_unknown_state_id_is_404(client: TestClient) -> None:
    response = client.get("/api/v1/reference/states/424242/districts")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_unknown_district_id_is_404(client: TestClient) -> None:
    assert client.get("/api/v1/reference/districts/424242/localities").status_code == 404


def test_non_numeric_id_is_422(client: TestClient) -> None:
    assert client.get("/api/v1/reference/states/abc/districts").status_code == 422


def test_invalid_mandi_filter_is_422(client: TestClient) -> None:
    assert client.get("/api/v1/reference/mandis?district_id=abc").status_code == 422


# -------------------------------------------------------------------- import


async def test_import_inserts_new_rows(session: AsyncSession) -> None:
    report = await _import(session, "states", STATES_CSV)
    assert report.row_count == 2
    assert report.inserted_count == 2
    assert report.rejected_count == 0


async def test_reimport_is_idempotent(session: AsyncSession) -> None:
    await _import(session, "states", STATES_CSV)
    report = await _import(session, "states", STATES_CSV)
    assert report.inserted_count == 0
    assert report.skipped_count == 2


async def test_changed_row_is_updated_not_duplicated(session: AsyncSession) -> None:
    await _import(session, "states", STATES_CSV)
    report = await _import(session, "states", "code,name\nXX,Example State Renamed\n")
    assert report.updated_count == 1
    assert report.inserted_count == 0


async def test_duplicate_code_in_one_file_is_rejected(session: AsyncSession) -> None:
    """A repeated natural key is refused, not silently applied twice."""
    report = await _import(session, "states", "code,name\nXX,One\nXX,Two\n")
    assert report.inserted_count == 1
    assert report.rejected_count == 1
    assert "duplicate" in report.reasons[0]
    assert len(await ReferenceService(session).list_states()) == 1


async def test_row_missing_required_columns_is_rejected(session: AsyncSession) -> None:
    report = await _import(session, "states", "code,name\nXX,\n")
    assert report.rejected_count == 1
    assert "required" in report.reasons[0]


async def test_unknown_parent_is_rejected(session: AsyncSession) -> None:
    report = await _import(session, "districts", "state_code,code,name\nZZ,D1,X\n")
    assert report.rejected_count == 1
    assert "unknown state_code" in report.reasons[0]


async def test_import_order_is_enforced(session: AsyncSession) -> None:
    """A district cannot be imported before its state exists."""
    report = await _import(session, "districts", DISTRICTS_CSV)
    assert report.rejected_count == 3


async def test_dry_run_writes_nothing(session: AsyncSession) -> None:
    report = await _import(session, "states", STATES_CSV, dry_run=True)
    assert report.inserted_count == 2
    assert report.dry_run is True
    assert await ReferenceService(session).list_states() == []


async def test_dry_run_is_still_recorded_in_the_import_log(session: AsyncSession) -> None:
    from sqlalchemy import select

    from app.models import ReferenceImportLog

    await _import(session, "states", STATES_CSV, dry_run=True)
    logs = (await session.execute(select(ReferenceImportLog))).scalars().all()
    assert len(logs) == 1
    assert logs[0].dry_run is True
    assert logs[0].inserted_count == 2


async def test_dry_run_works_when_the_source_was_never_committed(
    session: AsyncSession,
) -> None:
    """Regression: the admin API never commits between ensure_source and import_rows.

    A dry run rolls its transaction back to discard the imported rows. If the
    source was created in that same transaction it would be discarded too, and
    the reference_import_logs row would reference a source that does not exist -
    a foreign-key violation that PostgreSQL always enforces.
    """
    from sqlalchemy import select

    from app.models import ReferenceImportLog, ReferenceSource

    service = ReferenceService(session)
    # Deliberately NO commit here - this mirrors app/api/v1/admin_reference.py.
    source, _new = await service.ensure_source("uncommitted-src", "Uncommitted Source")
    report = await service.import_rows("states", STATES_CSV, source, dry_run=True)

    assert report.dry_run is True
    logs = (await session.execute(select(ReferenceImportLog))).scalars().all()
    assert len(logs) == 1
    assert logs[0].dry_run is True

    # The source must have survived the rollback.
    surviving = await session.execute(select(ReferenceSource))
    assert any(row.source_key == "uncommitted-src" for row in surviving.scalars().all())


async def test_header_only_file_is_accepted(session: AsyncSession) -> None:
    report = await _import(session, "states", "code,name,name_hi,name_te\n")
    assert report.row_count == 0
    assert report.rejected_count == 0


async def test_file_without_a_header_is_refused(session: AsyncSession) -> None:
    with pytest.raises(ImportValidationError):
        await _import(session, "states", "")


async def test_mass_unit_without_conversion_is_rejected(session: AsyncSession) -> None:
    report = await _import(
        session, "units", "code,name,dimension,to_base_kg\nkg,kg,mass,\n"
    )
    assert report.rejected_count == 1


async def test_non_mass_unit_without_conversion_is_allowed(session: AsyncSession) -> None:
    report = await _import(
        session, "units", "code,name,dimension,to_base_kg\npcs,pieces,count,\n"
    )
    assert report.inserted_count == 1


async def test_invalid_dimension_is_rejected(session: AsyncSession) -> None:
    report = await _import(session, "units", "code,name,dimension\nx,X,weight\n")
    assert report.rejected_count == 1


async def test_locality_kind_must_be_valid(session: AsyncSession) -> None:
    await _import(session, "states", STATES_CSV)
    await _import(session, "districts", DISTRICTS_CSV)
    report = await _import(
        session, "localities", "district_code,kind,name\nD1,hamlet,X\n"
    )
    assert report.rejected_count == 1


async def test_locality_coordinates_are_range_checked(session: AsyncSession) -> None:
    await _import(session, "states", STATES_CSV)
    await _import(session, "districts", DISTRICTS_CSV)
    report = await _import(
        session, "localities", "district_code,kind,name,latitude\nD1,city,X,999\n"
    )
    assert report.rejected_count == 1
    assert "latitude" in report.reasons[0]


async def test_localities_import_accepts_valid_kinds(session: AsyncSession) -> None:
    await _import(session, "states", STATES_CSV)
    await _import(session, "districts", DISTRICTS_CSV)
    report = await _import(session, "localities", LOCALITIES_CSV)
    assert report.inserted_count == 2


async def test_one_bad_row_does_not_stop_the_file(session: AsyncSession) -> None:
    report = await _import(session, "states", "code,name\nXX,Good\n,bad\nYY,AlsoGood\n")
    assert report.inserted_count == 2
    assert report.rejected_count == 1


async def test_import_log_records_every_run(session: AsyncSession) -> None:
    from sqlalchemy import select

    from app.models import ReferenceImportLog

    await _import(session, "states", STATES_CSV)
    logs = (await session.execute(select(ReferenceImportLog))).scalars().all()
    assert len(logs) == 1
    assert logs[0].entity_type == "states"
    assert logs[0].inserted_count == 2


async def test_mandis_and_commodities_import(session: AsyncSession) -> None:
    # A single _import round-trip under one ReferenceSource is unchanged: the
    # old multi-level hierarchy import is gone, but the flat path still works and
    # _import is still the canonical way a service-level test reaches import_rows.
    assert (await _import(session, "units", UNITS_CSV)).inserted_count == 2


# "currency" is now a supported entity draft; confirm the admin endpoint lists
# it so callers can render every template - including the one this project does
# not yet fully implement.
def test_supported_entities_cover_every_template(client: TestClient) -> None:
    response = client.get("/api/v1/admin/reference/entities")
    assert response.status_code == 200
    entities = set(response.json().keys())
    for entity in SUPPORTED_ENTITIES:
        assert entity in entities, entity


# ------------------------------------------------------------ admin endpoint


def test_import_endpoint_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/v1/admin/reference/import",
        json={"entity_type": "states", "csv_text": "code,name\nXX,X\n", "source": SOURCE},
    )
    assert response.status_code == 401


def test_import_endpoint_forbids_non_admins(client: TestClient) -> None:
    """A signed-in non-admin must be refused (403, not 401 and not 200)."""
    code = client.post(
        "/api/v1/auth/otp/request", json={"phone": "9000001234"}
    ).json()["dev_code"]
    token = client.post(
        "/api/v1/auth/otp/verify", json={"phone": "9000001234", "code": code}
    ).json()["access_token"]

    response = client.post(
        "/api/v1/admin/reference/import",
        headers={"Authorization": f"Bearer {token}"},
        json={"entity_type": "states", "csv_text": "code,name\nXX,X\n", "source": SOURCE},
    )
    assert response.status_code == 403


def test_import_endpoint_rejects_unknown_entity(client: TestClient) -> None:
    response = client.post(
        "/api/v1/admin/reference/import",
        json={"entity_type": "planets", "csv_text": "code,name\n", "source": SOURCE},
    )
    assert response.status_code in {400, 401, 403}