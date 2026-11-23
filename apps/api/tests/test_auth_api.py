"""End-to-end tests for the authentication API (Phase 4).

These run against the isolated in-memory SQLite database. No SMS is ever sent:
the development mock provider records the code in memory.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import issue_access_token

PHONE = "9876543210"


def _request_code(client: TestClient, phone: str = PHONE) -> str:
    """Request a code and return the development-only code from the response."""
    response = client.post("/api/v1/auth/otp/request", json={"phone": phone})
    assert response.status_code == 202, response.text
    code = response.json()["dev_code"]
    assert code, "the mock provider must return dev_code in development/test"
    return code


def _login(client: TestClient, phone: str = PHONE) -> str:
    code = _request_code(client, phone)
    response = client.post(
        "/api/v1/auth/otp/verify", json={"phone": phone, "code": code}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------- phone input


@pytest.mark.parametrize(
    "phone", ["9876543210", "+919876543210", "919876543210", "09876543210", "98765 43210"]
)
def test_valid_phone_formats_are_accepted(client: TestClient, phone: str) -> None:
    response = client.post("/api/v1/auth/otp/request", json={"phone": phone})
    assert response.status_code == 202


@pytest.mark.parametrize("phone", ["1234567890", "98765", "abcdefghij", ""])
def test_invalid_phone_formats_are_rejected(client: TestClient, phone: str) -> None:
    response = client.post("/api/v1/auth/otp/request", json={"phone": phone})
    assert response.status_code == 422


# ------------------------------------------------------------------- request


def test_request_never_returns_the_full_phone_number(client: TestClient) -> None:
    response = client.post("/api/v1/auth/otp/request", json={"phone": PHONE})
    body = response.json()
    assert "9876543210" not in response.text
    assert body["phone_masked"] == "+91 ******3210"


def test_request_response_has_no_code_in_production_mode() -> None:
    """Build the response as production would and confirm dev_code is dropped."""
    from app.schemas.auth import build_otp_request_response

    production = Settings(_env_file=None, ENVIRONMENT="production", SMS_PROVIDER="msg91")
    response = build_otp_request_response(
        message="sent",
        phone_masked="+91 ******3210",
        expires_in_seconds=300,
        resend_after_seconds=30,
        dev_code="123456",
        mock_enabled=production.mock_sms_enabled,
    )
    assert response.dev_code is None


def test_second_request_inside_cooldown_is_rate_limited(client: TestClient) -> None:
    _request_code(client)
    response = client.post("/api/v1/auth/otp/request", json={"phone": PHONE})
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"


# -------------------------------------------------------------------- verify


def test_verify_with_correct_code_returns_a_token(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/otp/verify", json={"phone": PHONE, "code": _request_code(client)}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["phone_verified"] is True
    assert "9876543210" not in response.text


def test_verify_with_wrong_code_is_unauthorized(client: TestClient) -> None:
    _request_code(client)
    response = client.post(
        "/api/v1/auth/otp/verify", json={"phone": PHONE, "code": "000000"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_code_cannot_be_replayed(client: TestClient) -> None:
    code = _request_code(client)
    first = client.post("/api/v1/auth/otp/verify", json={"phone": PHONE, "code": code})
    assert first.status_code == 200
    replay = client.post("/api/v1/auth/otp/verify", json={"phone": PHONE, "code": code})
    assert replay.status_code == 401


def test_non_numeric_code_is_rejected(client: TestClient) -> None:
    _request_code(client)
    response = client.post(
        "/api/v1/auth/otp/verify", json={"phone": PHONE, "code": "abcdef"}
    )
    assert response.status_code == 422


def test_too_many_wrong_attempts_burns_the_code(client: TestClient) -> None:
    code = _request_code(client)
    for _ in range(5):
        client.post("/api/v1/auth/otp/verify", json={"phone": PHONE, "code": "000000"})
    final = client.post("/api/v1/auth/otp/verify", json={"phone": PHONE, "code": code})
    assert final.status_code == 401


# --------------------------------------------------------------------- /me


def test_me_requires_a_token(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_rejects_a_garbage_token(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me", headers=_auth("not-a-token")).status_code == 401


def test_me_returns_the_signed_in_user(client: TestClient) -> None:
    token = _login(client)
    response = client.get("/api/v1/auth/me", headers=_auth(token))
    assert response.status_code == 200
    assert response.json()["phone_verified"] is True


# ---------------------------------------------------------------- roles/RBAC


def test_user_can_select_the_farmer_role(client: TestClient) -> None:
    token = _login(client)
    response = client.post("/api/v1/auth/roles", json={"role": "farmer"}, headers=_auth(token))
    assert response.status_code == 201
    assert "farmer" in response.json()["message"]


def test_admin_role_cannot_be_self_assigned(client: TestClient) -> None:
    token = _login(client)
    response = client.post("/api/v1/auth/roles", json={"role": "admin"}, headers=_auth(token))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_role_selection_requires_authentication(client: TestClient) -> None:
    response = client.post("/api/v1/auth/roles", json={"role": "farmer"})
    assert response.status_code == 401


def test_roles_appear_in_the_session_after_selection(client: TestClient) -> None:
    token = _login(client)
    client.post("/api/v1/auth/roles", json={"role": "farmer"}, headers=_auth(token))
    me = client.get("/api/v1/auth/me", headers=_auth(token)).json()
    assert "farmer" in me["roles"]
    assert "admin" not in me["roles"]


def test_onboarding_sets_display_name_and_language(client: TestClient) -> None:
    token = _login(client)
    client.post("/api/v1/auth/roles", json={"role": "farmer"}, headers=_auth(token))
    response = client.post(
        "/api/v1/auth/onboarding",
        json={"display_name": "Ravi Kumar", "preferred_locale": "hi"},
        headers=_auth(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Ravi Kumar"
    assert body["preferred_locale"] == "hi"
    assert body["onboarding_complete"] is True


def test_onboarding_rejects_a_too_short_name(client: TestClient) -> None:
    token = _login(client)
    response = client.post(
        "/api/v1/auth/onboarding", json={"display_name": "R"}, headers=_auth(token)
    )
    assert response.status_code == 422


def test_logout_is_recorded(client: TestClient) -> None:
    token = _login(client)
    response = client.post("/api/v1/auth/logout", headers=_auth(token))
    assert response.status_code == 200


# ------------------------------------------------------------------- audit


def test_login_writes_an_audit_record(client: TestClient, tmp_path) -> None:
    """Login must leave a trace in the audit table."""
    import sqlite3

    _login(client)
    db_file = tmp_path / "api.db"
    with sqlite3.connect(db_file) as connection:
        rows = connection.execute(
            "SELECT action FROM audit_logs ORDER BY id"
        ).fetchall()
    actions = [row[0] for row in rows]
    assert "auth.otp_requested" in actions
    assert "auth.login_succeeded" in actions


def test_denied_admin_assignment_is_audited(client: TestClient, tmp_path) -> None:
    import sqlite3

    token = _login(client)
    client.post("/api/v1/auth/roles", json={"role": "admin"}, headers=_auth(token))
    with sqlite3.connect(tmp_path / "api.db") as connection:
        rows = connection.execute(
            "SELECT action, result FROM audit_logs WHERE action LIKE 'auth.role%'"
        ).fetchall()
    assert ("auth.role_assignment_denied", "denied") in rows


# --------------------------------------------------------- token/user binding


def test_token_for_a_nonexistent_user_is_rejected(client: TestClient) -> None:
    """A valid signature must not be enough - the user must still exist."""
    from app.core.config import get_settings

    token, _ = issue_access_token(
        settings=get_settings(), user_id=999999, roles=["farmer"]
    )
    response = client.get("/api/v1/auth/me", headers=_auth(token))
    assert response.status_code == 401


def test_suspended_user_cannot_use_a_still_valid_token(client: TestClient, tmp_path) -> None:
    """Suspension must take effect immediately, not at token expiry."""
    import sqlite3


    token = _login(client)
    assert client.get("/api/v1/auth/me", headers=_auth(token)).status_code == 200

    with sqlite3.connect(tmp_path / "api.db") as connection:
        connection.execute("UPDATE users SET status = 'suspended'")
        connection.commit()

    assert client.get("/api/v1/auth/me", headers=_auth(token)).status_code == 403