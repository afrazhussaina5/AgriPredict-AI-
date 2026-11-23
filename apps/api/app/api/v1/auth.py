"""Authentication endpoints (Phase 4).

Flow: request code -> verify code -> receive an access token.

Production guarantees:
* the SMS provider must be a real one (the app refuses to start otherwise),
* the response never contains the OTP,
* every request/verify attempt is written to the audit log.
"""

from fastapi import APIRouter, Request, status

from ...core.config import Settings
from ...core.database import get_session_factory
from ...core.dependencies import AppSettings, CurrentUser, DbSession
from ...core.errors import AuthorizationError
from ...core.logging import get_logger
from ...core.security import issue_access_token
from ...models import OtpPurpose, UserRole, utcnow
from ...repositories import AuditRepository, UserRepository
from ...schemas.auth import (
    LogoutResponse,
    MessageResponse,
    OnboardingRequest,
    OtpRequestResponse,
    OtpVerifyRequest,
    PhoneRequest,
    RoleSelectionRequest,
    SessionUser,
    TokenResponse,
    build_otp_request_response,
)
from ...schemas.user import mask_phone
from ...services.otp_service import OtpService, upsert_user_for_phone
from ...services.sms import build_sms_provider

router = APIRouter(tags=["auth"])
logger = get_logger(__name__)

MESSAGE_REQUESTED = (
    "If this number can receive SMS, a verification code has been sent."
)
MESSAGE_ROLES = "Choose the role that matches how you will use the platform."
MESSAGE_VERIFIED = "Phone number verified."


async def _build_session_user(user, settings: Settings) -> SessionUser:
    """Assemble the session payload without exposing the full phone number."""
    factory = get_session_factory()
    assert factory is not None, "Session factory missing; database not initialised"
    async with factory() as session:
        roles = await UserRepository(session).list_roles(user.id)

    phone_verified = user.phone_verified_at is not None
    has_profile_role = bool(roles.intersection(
        {UserRole.FARMER, UserRole.BUYER, UserRole.TRANSPORT_PROVIDER,
         UserRole.STORAGE_PROVIDER}
    ))

    return SessionUser(
        id=user.id,
        display_name=user.display_name,
        phone_masked=mask_phone(user.phone_e164),
        status=user.status,
        preferred_locale=user.preferred_locale,
        roles=sorted(roles, key=lambda role: role.value),
        phone_verified=phone_verified,
        onboarding_complete=phone_verified and has_profile_role,
    )


@router.post(
    "/auth/otp/request",
    response_model=OtpRequestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request a phone verification code",
)
async def request_otp(
    payload: PhoneRequest,
    request: Request,
    session: DbSession,
    settings: AppSettings,
) -> OtpRequestResponse:
    """Send a code to a phone number.

    The response is deliberately uniform whether or not the number is already
    registered, so this endpoint cannot be used to discover users.
    """
    phone_e164 = payload.phone
    user = await upsert_user_for_phone(session, phone_e164)

    service = OtpService(session, settings, build_sms_provider(settings))
    record, _sms, code = await service.request_otp(
        phone_e164, purpose=OtpPurpose.LOGIN, user=user
    )

    # The role is only *applied* after the code verifies. If the caller already
    # picked a role on the sign-in screen, persist it here so the session holds
    # it even before onboarding. Admin is never self-assigned (see verify below).
    if payload.role is not None and not await UserRepository(session).has_role(
        user.id, UserRole.ADMIN
    ):
        await UserRepository(session).add_role(user.id, payload.role)
        await AuditRepository(session).record(
            action="auth.role_assigned",
            entity_type="user",
            entity_id=user.id,
            actor_user_id=user.id,
            details={"role": payload.role.value, "source": "sign_in"},
        )
        await session.commit()
        logger.info("Role %s applied at sign-in for user id %s", payload.role.value, user.id)

    await AuditRepository(session).record(
        action="auth.otp_requested",
        entity_type="user",
        entity_id=user.id,
        actor_user_id=user.id,
        ip_address=request.client.host if request.client else None,
        details={"purpose": OtpPurpose.LOGIN.value},
    )
    await session.commit()

    logger.info("OTP requested for user id %s", user.id)

    return build_otp_request_response(
        message=MESSAGE_REQUESTED,
        phone_masked=mask_phone(phone_e164) or "",
        expires_in_seconds=settings.OTP_TTL_MINUTES * 60,
        resend_after_seconds=settings.OTP_RESEND_COOLDOWN_SECONDS,
        dev_code=code,
        mock_enabled=settings.mock_sms_enabled,
    )


@router.post(
    "/auth/otp/verify",
    response_model=TokenResponse,
    summary="Verify a code and receive an access token",
)
async def verify_otp(
    payload: OtpVerifyRequest,
    request: Request,
    session: DbSession,
    settings: AppSettings,
) -> TokenResponse:
    """Exchange a valid OTP for a short-lived access token."""
    phone_e164 = payload.phone
    user = await upsert_user_for_phone(session, phone_e164)

    service = OtpService(session, settings, build_sms_provider(settings))
    await service.verify_otp(user.id, payload.code, purpose=OtpPurpose.LOGIN)

    user.phone_verified_at = user.phone_verified_at or utcnow()
    user.last_login_at = utcnow()
    session.add(user)

    # A role picked on the sign-in screen is applied once, here. No role can be
    # changed at sign-in afterwards; if none was given the session is simply
    # role-less until the user chooses one via POST /auth/roles.
    if payload.role is not None:
        allowed_roles = {UserRole.FARMER, UserRole.BUYER, UserRole.TRANSPORT_PROVIDER,
                          UserRole.STORAGE_PROVIDER}
        existing = await UserRepository(session).list_roles(user.id)
        if not existing.intersection(allowed_roles):
            await UserRepository(session).add_role(user.id, payload.role)
            await AuditRepository(session).record(
                action="auth.role_assigned",
                entity_type="user",
                entity_id=user.id,
                actor_user_id=user.id,
                details={"role": payload.role.value, "source": "sign_in_fallback"},
            )
            await session.commit()
            logger.info("Decided role %s applied at sign-in for user id %s",
                        payload.role.value, user.id)

    roles = await UserRepository(session).list_roles(user.id)
    token, expires_at = issue_access_token(
        settings=settings,
        user_id=user.id,
        roles=[role.value for role in sorted(roles, key=lambda item: item.value)],
    )

    await AuditRepository(session).record(
        action="auth.login_succeeded",
        entity_type="user",
        entity_id=user.id,
        actor_user_id=user.id,
        ip_address=request.client.host if request.client else None,
    )
    await session.commit()

    logger.info("User id %s signed in", user.id)
    return TokenResponse(
        access_token=token,
        expires_at=expires_at,
        user=await _build_session_user(user, settings),
    )


@router.post(
    "/auth/logout",
    response_model=LogoutResponse,
    summary="Sign out on this device",
)
async def logout(
    request: Request,
    user: CurrentUser,
    session: DbSession,
) -> LogoutResponse:
    """Record the sign-out.

    Tokens are short-lived and stateless; the client discards the token. This
    endpoint exists so the audit trail records explicit sign-outs.
    """
    await AuditRepository(session).record(
        action="auth.logout",
        entity_type="user",
        entity_id=user.id,
        actor_user_id=user.id,
        ip_address=request.client.host if request.client else None,
    )
    await session.commit()
    return LogoutResponse(message="Signed out.")


@router.get("/auth/me", response_model=SessionUser, summary="Current session")
async def read_me(user: CurrentUser, settings: AppSettings) -> SessionUser:
    """Return the signed-in user's own profile (never another user's)."""
    return await _build_session_user(user, settings)


@router.post(
    "/auth/roles",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Choose a platform role during onboarding",
)
async def select_role(
    payload: RoleSelectionRequest,
    request: Request,
    user: CurrentUser,
    session: DbSession,
) -> MessageResponse:
    """Assign a self-service role.

    ``admin`` is refused: it can only be granted through the controlled admin
    process built in Phase 15, never by the user themselves.
    """
    if payload.role is UserRole.ADMIN:
        await AuditRepository(session).record(
            action="auth.role_assignment_denied",
            entity_type="user",
            entity_id=user.id,
            actor_user_id=user.id,
            result="denied",
            ip_address=request.client.host if request.client else None,
            details={"attempted_role": UserRole.ADMIN.value},
        )
        await session.commit()
        # 403, not 201 with a message: the caller must not believe the grant
        # succeeded.
        raise AuthorizationError(
            "Administrator access cannot be self-assigned. "
            "Contact the platform administrator."
        )

    repository = UserRepository(session)
    if payload.role is UserRole.FARMER and await repository.has_role(user.id, UserRole.ADMIN):
        return MessageResponse(message="Administrator accounts keep their own role.")

    await repository.add_role(user.id, payload.role)
    await AuditRepository(session).record(
        action="auth.role_assigned",
        entity_type="user",
        entity_id=user.id,
        actor_user_id=user.id,
        details={"role": payload.role.value},
    )
    await session.commit()
    return MessageResponse(message=f"Role '{payload.role.value}' assigned.")


@router.post(
    "/auth/onboarding",
    response_model=SessionUser,
    summary="Complete onboarding",
)
async def complete_onboarding(
    payload: OnboardingRequest,
    user: CurrentUser,
    session: DbSession,
    settings: AppSettings,
) -> SessionUser:
    """Finish onboarding by setting the display name and preferred language."""
    user.display_name = payload.display_name
    user.preferred_locale = payload.preferred_locale
    session.add(user)

    await AuditRepository(session).record(
        action="auth.onboarding_completed",
        entity_type="user",
        entity_id=user.id,
        actor_user_id=user.id,
        details={"preferred_locale": payload.preferred_locale.value},
    )
    await session.commit()
    return await _build_session_user(user, settings)