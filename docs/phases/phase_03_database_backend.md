# Phase 3 — Database and Backend Foundation

| Field | Value |
|---|---|
| Status | **Implemented and verified locally — no Supabase database connected yet** |
| Date | 2026-10-03 |
| Depends on | Phase 0 (approved), Phase 1, Phase 2 |

> **Verified on this machine.** Git, Python 3.14.4, Node 24.19.0 and npm 11.17.0
> are installed. Backend and frontend suites, lint, type check and production
> build all pass. **No migration has been applied to Supabase** — no
> `POSTGRES_DSN` is configured.

---

## 1. What was built

| Area | File(s) |
|---|---|
| Async engine, session, `Base` | `apps/api/app/core/database.py` |
| Config + safe DB description | `apps/api/app/core/config.py` |
| Error types and handlers | `apps/api/app/core/errors.py` |
| Models: users, roles, farmer/buyer profiles | `apps/api/app/models/identity.py` |
| Models: OTP, audit log | `apps/api/app/models/verification.py` |
| Shared enums/mixins | `apps/api/app/models/base.py` |
| Repository layer | `apps/api/app/repositories/` |
| Schemas + phone normalisation/masking | `apps/api/app/schemas/user.py` |
| Alembic env + 2 revisions | `apps/api/alembic/` |
| Read-only DB verification | `apps/api/scripts/verify_database.py` |
| PowerShell migration wrapper | `scripts/migrate.ps1` |
| Tests | `apps/api/tests/test_models.py`, `test_database.py`, `test_schemas.py`, `test_errors.py` |

## 2. Design decisions (and why)

1. **Async SQLAlchemy 2.0 + asyncpg.** FastAPI is async; a synchronous driver
   would block the event loop under load. `asyncpg` is Supabase's supported
   async PostgreSQL driver.
2. **Alembic for schema only.** Migrations never create or drop a database.
   That is a Supabase console action, kept separate on purpose.
3. **`repr=False` on every secret-bearing setting.** `POSTGRES_DSN` and
   `SECRET_KEY` cannot appear in `repr(settings)`, logs or tracebacks.
4. **`ENVIRONMENT=test` forces in-memory SQLite.** Even if a real
   `POSTGRES_DSN` is present in `.env`, the test suite cannot reach it —
   asserted by `test_test_environment_never_uses_the_supabase_dsn`.
5. **Phone numbers are `+91` + 10 digits**, enforced by a unique constraint
   *and* two CHECK constraints. The API read model (`UserPublic`) has no
   `phone_e164` field at all — only a masked string.
6. **Privacy defaults are private in the schema**, not just in application code:
   `contact_phone_visible` and `show_exact_location_to_buyers` default to
   `False`.
7. **Admin cannot be granted through the ordinary repository.** `add_role`
   raises `PermissionError` for the admin role. The privileged grant path is
   built later with an audit entry (Phase 15).
8. **Audit log is append-only** and stores JSONB on PostgreSQL. The
   application has no update or delete path for it.
9. **Native enums off.** Roles/states are stored as `VARCHAR` + `CHECK` so the
   schema is portable and Alembic autogenerate stays predictable.

## 3. Table map (Phase 3 slice)

```
users ──< user_roles
  │
  ├──0..1 farmer_profiles      (individual farmer; no FPO required)
  └──0..1 buyer_profiles

otp_verifications  ──> users (CASCADE)
audit_logs         ──> users (SET NULL, so history survives account removal)
```

Marketplace, transport, storage, market-observation and forecast tables arrive
in their own phases; the reference-data tables in Phase 5.

## 4. Founder instructions (Windows PowerShell)

### 4.1 One-time: enter your database connection string

1. Open the **Supabase dashboard → your project → Project Settings → Database**.
2. Copy the **URI** connection string. It looks like
   `postgresql://postgres:YOUR-PASSWORD@db.xxxxx.supabase.co:5432/postgres`.
3. Insert `+asyncpg` after `postgresql`, giving
   `postgresql+asyncpg://postgres:YOUR-PASSWORD@db.xxxxx.supabase.co:5432/postgres`.
4. Open `apps\api\.env` (created by `.\scripts\setup.ps1`) and paste it after
   `POSTGRES_DSN=`.

**Do not paste that string into chat, a screenshot, or any document.** Typing it
directly into your local `.env` is the safe path.

### 4.2 Verify the target BEFORE migrating

```powershell
.\scripts\migrate.ps1 verify
```

This prints only the host, port, database name and server version. If it fails,
the password is wrong or the project is paused — nothing is changed.

### 4.3 Inspect, then migrate

```powershell
.\scripts\migrate.ps1 status   # read-only
.\scripts\migrate.ps1 up       # asks you to type 'apply'
```

### 4.4 Rollback

```powershell
.\scripts\migrate.ps1 down     # asks you to type 'revert'; take a backup first
```

### 4.5 Back up in Supabase first

Supabase dashboard → your project → **Database → Backups**. Free projects keep
a small window of automatic backups; confirm what your plan retains before you
rely on it.

## 5. Data-safety rules in force

- No migration runs without an explicit typed confirmation.
- The verification command is read-only.
- Tests cannot reach Supabase (enforced by code and by a test).
- No seeding of demo users, prices or listings — this phase creates empty
  tables only.
- The app starts and serves health checks with no database configured at all.

## 6. Test results — EXECUTED

Command: `cd apps/api; ..\..\.venv\Scripts\python.exe -m pytest`

| Suite | Tests | Result |
|---|---|---|
| `test_health.py` | 7 | ✅ pass |
| `test_config.py` | 12 | ✅ pass |
| `test_logging.py` | 6 | ✅ pass |
| `test_models.py` | 9 | ✅ pass |
| `test_database.py` | 12 | ✅ pass |
| `test_schemas.py` | 17 | ✅ pass |
| `test_errors.py` | 11 | ✅ pass |
| **Backend total** | **76** | **76 passed, 0 failed** |

Other checks (all pass):

| Check | Command | Result |
|---|---|---|
| Lint | `ruff check .` | All checks passed |
| Types | `mypy app` | No issues in 21 source files |
| Migration graph | `alembic heads` | `0002_verification_audit (head)` — single head, no branch |
| Frontend lint | `npm run lint` | 0 errors, 0 warnings |
| Frontend types | `npm run typecheck` | Clean |
| Frontend tests | `npm run test` | 11 passed (2 files) |
| Frontend build | `npm run build` | Built in 2.3s — 257 kB JS / 78 kB gzip |

Live verification against the running servers:

| Request | Result |
|---|---|
| `GET /api/v1/health` | `{"status":"ok",...,"version":"1.0.0"}` |
| `GET /api/v1/ready` | `not_ready` — database check correctly reports `Database is not configured.` (no DSN set) |
| `GET /api/v1/nope` | `{"error":{"code":"not_found","message":"Not Found"}}` |
| Frontend browser check | Landing page shows **"Connected — version 1.0.0, environment development"** |
| Language switch | Switching to తెలుగు translated the whole UI and persisted to `localStorage`; `document.lang` became `te` |
| Responsive nav | Below 720px the menu collapses behind a toggle; at 1280px the full nav and language selector appear |

### Defects found by actually running the code

These could not be found by reading the source:

1. **`sqlalchemy` was missing `greenlet`** — every test failed at collection.
   Fixed by using `sqlalchemy[asyncio]`.
2. **Bearer tokens leaked into logs.** The key/value redaction ran *before* the
   Bearer pattern, so it consumed the word "Bearer" and left the token itself.
   This was a real security defect. Fixed by reordering.
3. **`phone_e164` length was wrong.** `+91` plus a 10-digit number is **13**
   characters, not 12, so every user insert failed its own CHECK constraint.
   Fixed in the model, the schema and both migrations.
4. **Ambiguous foreign key** on `users <-> user_roles` (`user_id` and
   `granted_by_id` both point at `users.id`). Fixed with an explicit join.
5. **Admin guard was bypassable.** `if role is UserRole.ADMIN` fails for the
   plain string `"admin"`. Now uses equality, and both forms are tested.
6. Async test fixtures were declared synchronous (`session.commit()` was never
   awaited). Fixed.

## 7. Audit pass (two rounds)

**Round 1 — source review** (done before a shell was available). Defects found
and fixed: production settings tests missing a `POSTGRES_DSN`; a stray
`TEST_DATABASE_URL` in `.env` being able to point tests at a real database;
session-scoped async engine on a different event loop; a sync fixture depending
on an async one; an unused parameter; stale docstrings; `setup.ps1` not creating
the `.env` files the docs promised; missing `aria-current` on sub-routes;
timestamps typed as `str`.

**Round 2 — actually executing the code** caught six more that reading could
not have found, including the Bearer-token leak and the wrong phone-length
constraint. Both rounds mattered; the second was decisive.

## 8. Known limitations and risks

1. **No migration has been applied to a real database.** Everything was verified
   against SQLite. `POSTGRES_DSN` is still empty, and `/ready` honestly reports
   `not_ready` because of it.
2. **The migrations have never executed.** `alembic heads` proves the revision
   graph is valid, but the `upgrade()` bodies are unrun. Run
   `alembic upgrade head` against Supabase before trusting the schema, and
   follow with `alembic check` to detect drift against the models.
3. **`FarmerProfile.state_id` / `district_id` are plain integers with no foreign
   key yet.** Phase 5 adds the reference-data tables and the constraints; the
   columns are intentionally FK-free until then so Phase 5 can define them once.
4. **No authentication yet**, so no endpoint reads these tables. That is
   intentional: Phase 4 adds auth before any data is exposed.
5. **SQLite is not PostgreSQL.** Tests cover constraints and logic, not
   PostgreSQL-specific behaviour (`JSONB`, timezone-aware defaults).
6. **`audit_logs.details` uses JSONB**; on SQLite it degrades to JSON.
7. Python here is 3.14.4 while `pyproject.toml` targets 3.11 for linting. That
   is intentional (broader compatibility) but is not the same as being tested
   on 3.11 or 3.12.

## 9. Open decisions for the founder

| # | Decision | Recommendation |
|---|---|---|
| D6 | Fresh Supabase project vs the legacy one | **Fresh project.** The legacy prototype's project should be retired once this one is verified. |
| D1 | Legacy `backend/` and `static/` folders | Keep them untouched; they are the only working reference for porting later. |
| — | Run migrations against Supabase now? | Wait until you have confirmed the connection string and taken a backup. |