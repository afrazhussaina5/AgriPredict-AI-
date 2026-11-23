# AgriPredict AI — Backend (`apps/api`)

Python + FastAPI service. Phase 1 foundation, Phase 3 database layer,
Phase 4 authentication, Phase 5 reference data.

## Commands (run from the repository root in PowerShell)

```powershell
# One-time setup (creates .venv and installs dependencies)
.\scripts\setup.ps1

# Start the API dev server
.\scripts\start-backend.ps1
# equivalent to:
#   cd apps\api
#   ..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Run tests
Set-Location apps\api
..\..\.venv\Scripts\python.exe -m pytest

# Lint / format check / type check
..\..\.venv\Scripts\python.exe -m ruff check .
..\..\.venv\Scripts\python.exe -m ruff format --check .
..\..\.venv\Scripts\python.exe -m mypy app
```

> If you run commands from inside `apps\api`, the venv path is `..\..\.venv\...`.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | API name, version, environment (no secrets) |
| GET | `/api/v1/health` | Liveness probe |
| GET | `/api/v1/ready` | Readiness probe incl. database check (Phase 3) |
| POST | `/api/v1/auth/otp/request` | Send a phone verification code (Phase 4) |
| POST | `/api/v1/auth/otp/verify` | Exchange a code for an access token |
| POST | `/api/v1/auth/logout` | Record a sign-out |
| GET | `/api/v1/auth/me` | Current session |
| POST | `/api/v1/auth/roles` | Self-service role (admin is refused) |
| POST | `/api/v1/auth/onboarding` | Set display name and preferred language |
| GET | `/api/v1/reference/status` | Reference data counts, sources, `is_populated` (Phase 5) |
| GET | `/api/v1/reference/states` | All states |
| GET | `/api/v1/reference/states/{id}/districts` | Districts in a state |
| GET | `/api/v1/reference/districts/{id}/localities` | Villages / towns / cities in a district |
| GET | `/api/v1/reference/mandis?district_id=` | Mandis, optionally filtered by district |
| GET | `/api/v1/reference/commodities` | Commodities |
| GET | `/api/v1/reference/commodities/{id}/varieties` | Varieties of a commodity |
| GET | `/api/v1/reference/grades?commodity_id=` | Grades, optionally filtered |
| GET | `/api/v1/reference/units` | Measurement units |
| POST | `/api/v1/admin/reference/import` | Run an import (**admin**, dry run by default) |
| GET | `/api/v1/admin/reference/imports` | Import history (**admin**) |
| GET | `/docs` | Interactive OpenAPI documentation |

Reference read endpoints are public on purpose: place names are not private,
and onboarding needs them before a farmer has finished signing up.

## Reference data (Phase 5)

The ten `reference_*` tables ship **empty**. Nothing is bundled because
invented place names would be fabricated data.

```powershell
# Print the exact CSV header for a list
..\..\.venv\Scripts\python.exe -m scripts.import_reference --entity mandis --print-template

# Dry run - the default. Writes no rows, but still records the run.
..\..\.venv\Scripts\python.exe -m scripts.import_reference --entity mandis --file mandis.csv

# Apply - refuses to write without a named source.
..\..\.venv\Scripts\python.exe -m scripts.import_reference --entity mandis --file mandis.csv `
  --source-key my-directory-2026 --source-name "State statistical handbook" `
  --url https://... --publisher "..." --apply
```

Rules enforced by the tool:

- **No source, no write.** `--source-key` and `--source-name` are mandatory for `--apply`.
- **`--official` is never inferred** — the importer asserts it.
- **Order matters:** `states → districts → mandis`, `commodities → varieties → grades`.
- A child whose parent is missing is **rejected with a reason**, never silently dropped.
- Re-running the same file **skips** existing codes instead of duplicating them.
- Every run (apply or dry run) is written to `reference_import_logs` and audited.

Column-by-column rules: [`reference_data/README.md`](reference_data/README.md).
Phase report: [`docs/phases/phase_05_reference_data.md`](../../docs/phases/phase_05_reference_data.md).

> The Windows console (cp1252) cannot print Devanagari or Telugu. The import
> report only prints counts and reasons, so it is unaffected; set
> `PYTHONIOENCODING=utf-8` if you extend it to echo place names.

## Database (Phase 3)

```powershell
# 1. Read-only check of the configured database - prints no credentials
.\scripts\migrate.ps1 verify

# 2. See which migrations are applied (changes nothing)
.\scripts\migrate.ps1 status

# 3. Apply pending migrations (asks you to type 'apply')
.\scripts\migrate.ps1 up

# 4. Revert the last migration (asks you to type 'revert' - back up first)
.\scripts\migrate.ps1 down
```

Direct Alembic equivalents (from `apps\api`, with `.env` present):

```powershell
..\..\.venv\Scripts\python.exe -m alembic current
..\..\.venv\Scripts\python.exe -m alembic upgrade head
..\..\.venv\Scripts\python.exe -m scripts.verify_database
```

**Rules:** migrations never create or drop a database; a missing `POSTGRES_DSN`
makes the command stop before connecting; no URL is ever printed.

## Configuration

Settings load from environment variables and `apps/api/.env`
(copy from [`.env.example`](.env.example)).

- Development needs **no credentials** — the API starts without a database.
- `POSTGRES_DSN` is **required** for `staging` and `production`.
- `SECRET_KEY` is **required** for `production` and must be at least 32 chars.
- `SMS_PROVIDER=mock` is **development only**; the app refuses to start with it
  in `production`.
- `POSTGRES_DSN`, `SECRET_KEY` and `TEST_DATABASE_URL` are excluded from
  `repr()` so they cannot be logged by accident.
- `ENVIRONMENT=test` forces an isolated SQLite database, so the test suite can
  never reach Supabase.

## Structure

```
apps/api/
├── app/
│   ├── main.py            # App factory, CORS, routers, lifespan
│   ├── core/
│   │   ├── config.py      # Settings (env + .env), validation, safe DB description
│   │   ├── database.py    # Async engine, session, Base, readiness probe
│   │   ├── dependencies.py# Auth dependency + role guards (Phase 4)
│   │   ├── errors.py      # App errors + uniform JSON error responses
│   │   ├── logging.py     # Logging setup with secret redaction
│   │   └── security.py    # OTP hashing + JWT issue/verify (Phase 4)
│   ├── api/v1/            # Versioned routes (/api/v1/...)
│   ├── models/            # SQLAlchemy ORM models
│   │   └── reference.py   # States, districts, mandis, commodities... (Phase 5)
│   ├── repositories/      # Data access (all SQL lives here)
│   ├── schemas/           # Pydantic request/response models
│   └── services/          # Business logic
│       ├── otp_service.py # OTP lifecycle (Phase 4)
│       ├── reference_service.py       # Import + read logic (Phase 5)
│       ├── reference_import_specs.py  # CSV column specs (Phase 5)
│       └── sms/           # SMS provider adapters (mock is dev-only)
├── alembic/               # Migration environment and revisions
├── reference_data/        # Header-only CSV templates + how to prepare a dataset
├── scripts/               # Developer helpers (verify_database, import_reference)
├── tests/                 # pytest suite
├── requirements.txt       # bounded runtime dependencies
├── requirements-dev.txt   # bounded test/lint/type dependencies
└── pyproject.toml         # tool configuration (pytest, ruff, mypy)
```

Layering rule: **routers → services → repositories → models**.