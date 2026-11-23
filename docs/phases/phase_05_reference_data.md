# Phase 5 — Location and Reference Data

| Field | Value |
|---|---|
| Status | **Implemented and verified** (local SQLite + live browser check) |
| Date | 2026-10-03 |
| Depends on | Phase 0–4 |

**No official directory is bundled.** States, districts, mandis, localities,
commodities, varieties, grades and units all ship **empty**. Every row must come
from a named, recorded source before it is written. See §6.

---

## 1. What was built

| Area | File(s) |
|---|---|
| Tables + enums | `apps/api/app/models/reference.py` |
| Migration | `apps/api/alembic/versions/0003_reference_data.py` |
| Read/write schemas | `apps/api/app/schemas/reference.py` |
| CSV column specifications | `apps/api/app/services/reference_import_specs.py` |
| Import + read logic | `apps/api/app/services/reference_service.py` |
| Public read endpoints | `apps/api/app/api/v1/reference.py` |
| Admin import endpoint | `apps/api/app/api/v1/admin_reference.py` |
| Import CLI | `apps/api/scripts/import_reference.py` |
| Header-only CSV templates | `apps/api/reference_data/templates/*.csv` |
| Founder instructions | `apps/api/reference_data/README.md` |
| Cascade UI | `apps/web/src/pages/ReferencePage.tsx` |
| Typed client fetchers | `apps/web/src/api/client.ts` |
| `ref.*` strings (× 3 locales) | `apps/web/src/i18n/translations.ts` |

Ten tables: `reference_sources`, `reference_states`, `reference_districts`,
`reference_localities`, `reference_mandis`, `reference_commodities`,
`reference_commodity_varieties`, `reference_commodity_grades`,
`reference_units`, `reference_import_logs`.

## 2. Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/v1/reference/status` | none | Counts + sources + `is_populated` |
| GET | `/api/v1/reference/states` | none | All states |
| GET | `/api/v1/reference/states/{id}/districts` | none | Districts in a state |
| GET | `/api/v1/reference/districts/{id}/localities` | none | Villages / towns / cities |
| GET | `/api/v1/reference/mandis?district_id=` | none | Mandis, optionally filtered |
| GET | `/api/v1/reference/commodities` | none | Commodities |
| GET | `/api/v1/reference/commodities/{id}/varieties` | none | Varieties |
| GET | `/api/v1/reference/grades?commodity_id=` | none | Grades |
| GET | `/api/v1/reference/units` | none | Measurement units |
| POST | `/api/v1/admin/reference/import` | **admin** | Run an import |
| GET | `/api/v1/admin/reference/imports` | **admin** | Import history |

Read endpoints are public on purpose — place names are not private, and the
onboarding flow needs them before a farmer has finished signing up.

## 3. Honesty and provenance rules, and how each is enforced

| Rule | Enforcement |
|---|---|
| Nothing is imported anonymously | `--source-key` **and** `--source-name` required to write; the API refuses without them |
| "Government data" is never assumed | `is_official` is a flag the importer must pass explicitly; the tool never infers it |
| Dry run is the default | `--apply` is required; the API needs `dry_run=false` **and** `confirm=true` |
| Every run is recorded | `reference_import_logs` gets a row for applies **and** dry runs, including rejections |
| An empty DB says so | `/reference/status` returns `is_populated:false`; the UI shows "not loaded yet", never a broken empty dropdown |
| The farmer can see where data came from | every row carries `source_key`, `source_name`, `source_is_official`; the UI shows it under the selected mandi |
| Unknown parent → 404 | `session.get(...)` check before listing children |
| Bad ids are not silently coerced | non-numeric ids return **422** |
| Localised names are optional | `name_hi` / `name_te` nullable; the UI falls back to the official name instead of showing a blank |
| Only an admin can write | `require_admin`; self-assigning admin is impossible (Phase 4), so this is closed until Phase 15 |
| Imports are audited | `audit_logs` row per run |

## 4. Test results — EXECUTED

`cd apps\api; ..\..\.venv\Scripts\python.exe -m pytest`

| Suite | Tests | Result |
|---|---|---|
| `test_reference.py` | 39 | ✅ pass |
| `test_security.py` | 26 | ✅ pass |
| `test_schemas.py` | 21 | ✅ pass |
| `test_otp_service.py` | 18 | ✅ pass |
| `test_database.py` | 12 | ✅ pass |
| `test_config.py` | 11 | ✅ pass |
| `test_errors.py` | 10 | ✅ pass |
| `test_models.py` | 9 | ✅ pass |
| `test_health.py` | 7 | ✅ pass |
| `test_logging.py` | 6 | ✅ pass |
| `test_auth_api.py` | 31 | ✅ pass |
| **Backend total** | **190** | **190 passed, 0 failed** (26.24 s) |

| Check | Result |
|---|---|
| `ruff check .` | All checks passed |
| `mypy app` | No issues in 36 source files |
| Frontend `npm run lint` | 0 errors, 0 warnings |
| Frontend `npm run typecheck` | Clean |
| Frontend `npm run test` | 19 passed (3 files) |
| Frontend `npm run build` | Built — 285.27 kB / **85.30 kB gzip** |

## 5. Live verification (real CLI + real HTTP + real browser)

### 5.1 CLI, run against `apps/api/refdemo.db`

| Command | Observed |
|---|---|
| `--print-template --entity mandis` | `district_code,code,name,name_hi,name_te,has_storage` |
| `--apply` with no `--source-key` | **refused**, exit 2 — "Reference data is never imported anonymously." |
| districts dry run, parent state missing | `rows read 3 / inserted 2 / rejected 1` → `row 4: unknown state_code 'ZY'` |
| districts dry run | `DRY RUN (nothing written)` + **1 log row with `dry_run=1`** |
| states `--apply` | `inserted 1` |
| districts `--apply` | `inserted 3` |
| mandis `--apply` | `inserted 3` |
| districts `--apply` **again** | `inserted 0 / skipped 3` — idempotent |

### 5.2 HTTP

| Request | Observed |
|---|---|
| `GET /reference/status` | `is_populated:true`, states 2 / districts 3 / mandis 3, both sources listed |
| `GET /reference/states` | 2 rows with `name_hi` + `name_te` populated |
| `GET /reference/states/1/districts` | 2 districts |
| `GET /reference/mandis?district_id=1` | 2 mandis, `has_storage` true/false |
| `GET /reference/states/9999/districts` | **404** |
| `GET /reference/districts/9999/localities` | **404** |
| `GET /reference/districts/abc/mandis` | **422** |
| `POST /admin/reference/import` (no token) | **401** |

### 5.3 Browser (`/reference`)

| Step | Observed |
|---|---|
| Page load | honest counts, source list with `community` badges |
| Pick state → district → mandi | all three levels cascade; second level resets when the parent changes |
| Select a mandi | `Source: Demo Directory` shown beneath |
| Switch to **Hindi** | heading `स्थान और संदर्भ डेटा`, options `आयातित डेमो राज्य`, source line `स्रोत: Demo Directory` |
| Switch to **Telugu** | heading `ప్రదేశం మరియు రిఫరెన్స్ డేటా`, options `దిగుమతి డెమో రాష్ట్రం` |
| Selection across a locale switch | state/district/mandi ids **preserved** (1 / 1 / 1) |
| Console / network | **0 errors**; every fetch 200 |
| Layout at 1280×900 | no horizontal overflow (`scrollWidth === clientWidth`) |

Source names stay in English in all three locales — a source is a proper noun,
not a translatable string.

## 6. Loading real data — what you must do

The shipped templates are **header-only**. That is deliberate: inventing
district names would be fabricated data, so nothing is bundled.

1. Pick a real source and record it. Candidates: your state agriculture
   department's mandi list, the national agricultural marketing portal, or a
   district handbook. Note the URL, publisher and licence.
2. Fill a template. Required columns are listed in
   `apps/api/reference_data/README.md`; run `--print-template --entity <name>`
   to print the exact header.
3. **Import order matters:** `states → districts → mandis` and
   `commodities → varieties → grades`. A child whose parent has not been
   imported is rejected with a reason, not silently dropped.
4. Dry run first, read the rejection reasons, then `--apply`.

```
cd apps\api
..\..\.venv\Scripts\python.exe -m scripts.import_reference --entity districts --file my_districts.csv
..\..\.venv\Scripts\python.exe -m scripts.import_reference --entity districts --file my_districts.csv --source-key my-directory-2026 --source-name "State statistical handbook" --url https://… --apply
```

Once an admin account exists (Phase 15), the same import is available over HTTP
at `POST /api/v1/admin/reference/import`.

## 7. Bugs found and fixed during this phase

Running the code (not reading it) found two real defects:

1. **Dry runs were writing rows.** The import used a SQLAlchemy savepoint per
   row and rolled back rejected ones. Under `pysqlite`/`aiosqlite`,
   `RELEASE SAVEPOINT` is a COMMIT, not a no-op — so the release committed the
   earlier inserts and the rollback did nothing. A "dry run" had silently
   written to the database. Fixed by using one explicit outer transaction,
   validating rows in Python, and rejecting duplicates against an in-memory
   `seen` set instead of relying on savepoints.
2. **Async lazy-load after rollback.** After a rollback, SQLAlchemy expires ORM
   objects, so reading `source_id` off a rolled-back instance raised. The id is
   now captured *before* the rollback.

A third defect was found during review, not by running: `mandis` is served from
`/reference/mandis?district_id=` while the other two levels use nested paths.
This is inconsistent and surprised me during verification — the API docs in §2
are now the source of truth, but it should probably be unified in Phase 6.

## 8. Known limitations and risks

1. **No verified Supabase connection.** Nothing has been run against
   PostgreSQL. The JSONB and timezone behaviour of these tables is untested
   there. Migrations 0001–0003 have only ever run on SQLite.
2. **The admin import endpoint is unreachable** until an admin account exists
   (Phase 15). By design — there is no back door.
3. **The API URL shape is inconsistent** — two nested paths and two query
   parameters. Harmless now, annoying later.
4. **`has_storage` is imported but never shown** in the UI. Farmers will care
   about cold storage, so this should surface in the mandi summary.
5. **No geocoding.** Localities can carry `latitude`/`longitude` but nothing
   computes them, and nothing maps a GPS fix to a district yet. Phase 6+.
6. **CSV only.** No way to import from a spreadsheet, and no bulk update or
   deactivation workflow — correcting a typo means editing the CSV and
   re-running, which skips (does not update) the row. `updated_count` is
   currently always 0.
7. **The Windows console cannot print Devanagari or Telugu** (cp1252). The CLI
   itself is unaffected because reports only print counts and reasons, but any
   future command that echoes a place name needs `PYTHONIOENCODING=utf-8`.
8. **No pagination.** `/reference/mandis` returns every mandi. Fine for one
   district, wrong for a national list.
9. **The demo database used for verification has been deleted**, as have the
   demo CSVs. Nothing in the repo claims data that is not there.

## 9. Open decisions

| # | Decision | Recommendation |
|---|---|---|
| — | Which official directory to load first | Start with one state end-to-end rather than a national list; it proves the pipeline cheaply. |
| — | Fix or rename the state/district codes | Adopt the source's own codes permanently, or Phase 6 migrations will have to remap them. |
| — | Unify the endpoint shapes | Change `mandis`/`grades` to nested paths before any client other than ours depends on them. |
| — | Who may import | Keep it admin-only; do not add an in-app uploader for farmers. |