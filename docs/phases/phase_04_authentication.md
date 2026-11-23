# Phase 4 — Authentication, Onboarding, and RBAC

| Field | Value |
|---|---|
| Status | **Implemented and verified** (local SQLite + live browser check) |
| Date | 2026-10-03 |
| Depends on | Phase 0–3 |

**No real SMS was sent.** The development mock adapter is used, and the app
refuses to start in production with it. See §6 for the exact provider steps.

---

## 1. What was built

| Area | File(s) |
|---|---|
| OTP hashing, token issue/verify | `apps/api/app/core/security.py` |
| Auth dependencies, RBAC guards | `apps/api/app/core/dependencies.py` |
| SMS provider interface + mock | `apps/api/app/services/sms/` |
| OTP lifecycle service | `apps/api/app/services/otp_service.py` |
| Auth endpoints | `apps/api/app/api/v1/auth.py` |
| Auth schemas (incl. dev-code stripping) | `apps/api/app/schemas/auth.py` |
| Typed API client (in-memory token) | `apps/web/src/api/client.ts` |
| Auth session context | `apps/web/src/auth/AuthProvider.tsx`, `context.ts` |
| Sign-in / OTP / role / onboarding UI | `apps/web/src/pages/AuthPage.tsx` |
| EN / HI / TE strings (36 new keys × 3) | `apps/web/src/i18n/translations.ts` |

## 2. Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/v1/auth/otp/request` | none | Send a code (202) |
| POST | `/api/v1/auth/otp/verify` | none | Exchange code for a token |
| POST | `/api/v1/auth/logout` | token | Record sign-out |
| GET | `/api/v1/auth/me` | token | Current session |
| POST | `/api/v1/auth/roles` | token | Self-service role (admin refused) |
| POST | `/api/v1/auth/onboarding` | token | Set name + preferred language |

## 3. Security rules, and how each is enforced

| Rule | Enforcement |
|---|---|
| Indian `+91` numbers normalised | `normalize_phone_e164`; CHECK constraints on the column |
| OTP hashed, never stored in plaintext | HMAC-SHA256 keyed with `SECRET_KEY`, per-request salt |
| OTP expires | `OTP_TTL_MINUTES` (5) |
| Resend cooldown | `OTP_RESEND_COOLDOWN_SECONDS` (30), returns 429 |
| Hourly request cap | sliding window columns on the OTP record |
| Max failed attempts | `OTP_MAX_ATTEMPTS` (5), then the challenge is burned |
| Single use | `consumed_at` set; replay returns 401 |
| Production cannot use mock SMS | `validate_settings()` raises → **app refuses to start** |
| Production response never contains the OTP | `build_otp_request_response` drops `dev_code` unless `mock_sms_enabled` |
| Phone never returned in full | only `mask_phone()` output; no schema exposes `phone_e164` |
| Tokens short-lived and signed | HS256 JWT, 60 min, `exp` + `sub` + `typ` required |
| `alg: none` forgery rejected | algorithms pinned to HS256; tested |
| Token alone is not enough | the user must still exist and be `active` |
| Role revocation is immediate | roles re-read from the database, not from token claims |
| Admin cannot be self-assigned | 403 + audited denial; also blocked in `UserRepository.add_role` |
| Every auth action audited | `auth.otp_requested`, `auth.login_succeeded`, `auth.logout`, … |

## 4. Test results — EXECUTED

`cd apps\api; ..\..\.venv\Scripts\python.exe -m pytest`

| Suite | Tests | Result |
|---|---|---|
| `test_security.py` | 26 | ✅ pass |
| `test_otp_service.py` | 18 | ✅ pass |
| `test_auth_api.py` | 32 | ✅ pass |
| All other suites | 75 | ✅ pass |
| **Backend total** | **151** | **151 passed, 0 failed** |

| Check | Result |
|---|---|
| `ruff check .` | All checks passed |
| `mypy app` | No issues in 30 source files |
| Frontend `npm run lint` | 0 errors, 0 warnings |
| Frontend `npm run typecheck` | Clean |
| Frontend `npm run test` | 19 passed (3 files) |
| Frontend `npm run build` | Built — 83 kB gzip |

## 5. Live verification (real HTTP + real browser)

| Step | Observed |
|---|---|
| `POST /auth/otp/request` | `{"phone_masked":"+91 ******3210","dev_code":"743315",…}` |
| `POST /auth/otp/verify` | token issued, `phone_verified: true` |
| Replay the same code | **401** |
| `POST /auth/roles {"role":"admin"}` | **403** "Administrator access cannot be self-assigned." |
| `POST /auth/roles {"role":"farmer"}` | **201** |
| `POST /auth/onboarding` | `{"roles":["farmer"],"preferred_locale":"hi","onboarding_complete":true}` |
| `GET /auth/me` without token | **401** |
| Browser: phone → OTP → role → onboarding | completed in **Hindi**, landing on the dashboard |

## 6. Real SMS provider — what you must do to go live

1. Choose a provider (MSG91, Gupshup, Fast2SMS or Twilio). Compare price per
   SMS and confirm it delivers to Indian mobile numbers.
2. Create the account yourself and put the key in `apps\api\.env`:
   `SMS_PROVIDER=<name>` plus that provider's key variables.
3. Implement the adapter: create `apps/api/app/services/sms/<name>.py` with a
   class exposing `name` and `async send_otp(phone_e164, code)`, returning an
   `SmsResult`, then register it in `build_sms_provider`.
4. Until that class exists the factory raises "not implemented" — the platform
   fails closed rather than pretending to send an SMS.

**Cost:** roughly ₹0.20–₹0.50 per SMS in India. Nothing is spent until you
approve a provider.

## 7. Bugs found and fixed during this phase

Running the code (not reading it) found four real defects:

1. **Failed-attempt counts were rolled back.** The request raised an error, so
   `get_db` rolled the transaction back and erased the counter — an attacker
   could guess a 6-digit code forever. Fixed by writing the counter in its own
   committed transaction (`_record_failure`).
2. **The hourly rate limit did nothing.** Resends update the same row, so
   counting rows always returned 1. Replaced with a per-record sliding window
   (`window_started_at`, `window_request_count`).
3. **In-memory SQLite broke the API tests** ("no such table") because each
   connection gets its own empty database. Switched to a per-test SQLite file.
4. **Production settings tests failed** after the mock-SMS guard was added —
   correctly, because those fixtures still used `SMS_PROVIDER=mock`.

## 8. Known limitations and risks

1. **No real SMS provider is integrated** — this is the only blocker for live
   sign-in.
2. **No refresh tokens.** A session ends after 60 minutes and the farmer must
   request a new code. Acceptable for Phase 4; revisit before launch.
3. **The token lives in memory only.** A page reload signs the user out. This
   is deliberate (an XSS bug cannot steal a persisted token) but hurts UX.
4. **No per-IP rate limiting** on the OTP endpoints — the database limit is per
   phone number. A distributed attack across many numbers is not yet covered.
   Phase 16 should add IP limits at the reverse proxy.
5. **No CAPTCHA.** It will be needed before real SMS is switched on.
6. **Requests create a user row for unknown numbers**, which is a small amount
   of storage abuse; capped at 5/hour/number.
7. **Roles are read from the database on every request**, which is safe but
   costs one extra query per protected call.

## 9. Open decisions

| # | Decision | Recommendation |
|---|---|---|
| — | SMS provider | Compare 2–3 on delivered price and Indian coverage before committing. |
| — | Session length | Keep 60 minutes; add refresh tokens only if farmers report friction. |
| — | CAPTCHAs | Add on the OTP request endpoint before going live. |