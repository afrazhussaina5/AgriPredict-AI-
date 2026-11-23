# Phase 1 — Project Foundation and Environment

| Field | Value |
|---|---|
| Status | **Source complete — automated checks NOT yet executed (blocked), founder run required** |
| Date | 2026-10-03 |
| Depends on | Phase 0 approval ✅ |
| Implements | Phase 1 of the master prompt (12 requirements) |

---

## 1. Phase goal and assumptions

**Goal:** a clean monorepo with a runnable FastAPI backend, a runnable
React + TypeScript + Vite frontend, dependency management, quality commands
(lint / format / type-check / tests), CI, and Windows PowerShell setup
instructions — **without** authentication, marketplace, or ML features.

**Assumptions applied**

| ID | Assumption | Consequence |
|---|---|---|
| A-D1 | Legacy `backend/` and `static/` stay untouched at the repository root | New code lives only under `apps/`, `scripts/`, `tests/`, `.github/` |
| A-D2 | The new backend reads `apps/api/.env` (not the legacy root `.env`) | Legacy Supabase credentials are never loaded by the new app |
| A-D3 | Bounded dependency ranges instead of exact pins | `requirements.txt` uses `>=x,<y`; rationale in that file's header |
| A-D4 | `format:check` is **not** run in CI yet | It would fail on files no formatter has processed; run `npm run format` locally first, then enable it |

**Risks identified:** the machine has no Git for Windows → no shell → no
commands could be executed by the agent (see §5).

---

## 2. What was created

### Repository layout

```
( repository root )
├── apps/
│   ├── api/                  # NEW — FastAPI backend
│   │   ├── app/
│   │   │   ├── main.py              # app factory, CORS allow-list, index route
│   │   │   ├── core/config.py       # Settings from env/.env, fail-closed production check
│   │   │   ├── core/logging.py      # logging + secret redaction filter
│   │   │   ├── api/v1/health.py     # GET /api/v1/health, GET /api/v1/ready
│   │   │   ├── api/v1/router.py     # versioned router
│   │   │   └── schemas/health.py    # Pydantic response models
│   │   ├── tests/                   # pytest: health, config, redaction, fail-closed start
│   │   ├── requirements.txt         # bounded runtime dependencies
│   │   ├── requirements-dev.txt     # bounded test/lint/type dependencies
│   │   ├── pyproject.toml           # pytest, ruff, mypy configuration
│   │   ├── .env.example             # clean template (no secrets)
│   │   └── README.md                # backend commands
│   └── web/                  # NEW — React + TypeScript + Vite
│       ├── src/App.tsx              # shell with loading/success/error API states
│       ├── src/main.tsx             # entry point
│       ├── src/appInfo.ts           # constants incl. en/hi/te locale codes
│       ├── src/appInfo.test.ts      # vitest unit test
│       ├── src/styles.css           # accessible responsive baseline (Phase 2 replaces)
│       ├── index.html, vite.config.ts (API proxy), tsconfig.json (strict)
│       ├── eslint.config.js, .prettierrc, .prettierignore
│       ├── package.json             # bounded versions + all quality scripts
│       └── .env.example             # PUBLIC values only — never secrets
├── scripts/                  # NEW — Windows PowerShell
│   ├── check-environment.ps1        # verifies git/python/node/npm with install hints
│   ├── setup.ps1                    # venv + pip install + npm install
│   ├── start-backend.ps1            # uvicorn on 127.0.0.1:8000
│   ├── start-frontend.ps1           # vite on localhost:5173
│   └── test.ps1                     # pytest + ruff + mypy + eslint + tsc + vitest + build
├── tests/README.md           # NEW — reserved for Phase 16 E2E tests
├── .github/workflows/ci.yml  # NEW — CI (no secrets, no DB, no external calls)
├── docs/README.md            # NEW — documentation index
├── docs/phases/phase_01_foundation.md   # this file
├── .gitignore                # UPDATED — added Node, venv and app .env entries
└── README.md                 # UPDATED — Phase 1 quick start added on top
```

### Untouched (preserved, per founder instruction)

`backend/`, `static/`, `index.html`, root `pyproject.toml`, root
`requirements.txt`, `.env`, `.env.example` (legacy — risk **R-01** stands),
`.pytest_cache/`.

---

## 3. Decisions explained in plain language

| Decision | Why |
|---|---|
| **Bounded versions** (`fastapi>=0.115,<1.0`) | Exact pins go stale and miss security fixes; no bounds risks a surprise breaking release. Bounds are the safe middle. A lockfile tool (uv/poetry) can be adopted later if exact reproducibility is wanted. |
| **`apps/` monorepo** | Frontend, backend, docs, scripts and tests are clearly separated; legacy code stays beside them without collisions. |
| **CORS allow-list, never `*`** | The legacy prototype used `allow_origins=["*"]`; that would be a production security hole, so the new app defaults to the local frontend origins only. |
| **Fail-closed startup** | If `ENVIRONMENT=production` and no `SECRET_KEY`, the API refuses to start instead of running unsafely. |
| **Log redaction** | Every log line is filtered so `SECRET_KEY=...`, `api_key: ...`, `Bearer ...` and OTP-shaped values print as `[REDACTED]`. |
| **Health + readiness split** | `/health` says "the process is alive"; `/ready` says "it can take traffic" (config checks now, database check in Phase 3). |
| **npm install, not npm ci, in CI** | `npm ci` requires `package-lock.json`, which is generated on your first local `npm install` and then committed. |
| **Versioned API** | All routes live under `/api/v1` so future breaking changes don't break old clients. |

---

## 4. Exact commands (Windows PowerShell)

```powershell
# 0) One-time: install missing tools (if check-environment says so)
winget install --id Git.Git --exact --source winget
winget install --id Python.Python.3.12 --exact --source winget
winget install --id OpenJS.NodeJS.LTS --exact --source winget
# then CLOSE and REOPEN this window

# 1) Verify the machine
.\scripts\check-environment.ps1

# 2) One-time setup (creates .venv, installs backend + frontend dependencies)
.\scripts\setup.ps1

# 3) Run everything (tests, lint, type checks, build)
.\scripts\test.ps1

# 4) Daily development — two separate windows
# Window A
.\scripts\start-backend.ps1        # http://127.0.0.1:8000  (docs at /docs)
# Window B
.\scripts\start-frontend.ps1       # http://localhost:5173
```

If scripts are blocked by execution policy, run once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

> ⚠️ Always run tests via `\scripts\test.ps1` or from **inside `apps\api`**.
> Running bare `pytest` at the repository root would also collect the **legacy
> prototype's** tests under `backend/`, which are reference-only and may fail.

No credentials are needed for Phase 1. **Never paste `.env` contents, keys or
connection strings into chat.**

---

## 5. Test results — ACTUAL, not assumed

**Nothing was executed by the agent.** The shell tool on this machine requires
Git for Windows (`bash.exe`), which is not installed:

```
Bash is required but was not found on this Windows system.
Install Git for Windows: https://git-scm.com/download/win
  winget install --id Git.Git --exact --source winget
```

Therefore:

| Check | Command | Result |
|---|---|---|
| Backend tests | `pytest` (in `apps/api`) | ⛔ **NOT RUN — blocked** |
| Backend lint | `ruff check .` | ⛔ **NOT RUN — blocked** |
| Backend types | `mypy app` | ⛔ **NOT RUN — blocked** |
| Frontend lint | `npm run lint` | ⛔ **NOT RUN — blocked** |
| Frontend types | `npm run typecheck` | ⛔ **NOT RUN — blocked** |
| Frontend tests | `npm run test` | ⛔ **NOT RUN — blocked** |
| Frontend build | `npm run build` | ⛔ **NOT RUN — blocked** |
| PowerShell scripts | `.\scripts\test.ps1` | ⛔ **NOT RUN — blocked** |

**No pass rate is claimed.** Once Git (and Node/Python if missing) are
installed, run `.\scripts\test.ps1` and share its output — every failure it
reports will be fixed in the next iteration before Phase 2 starts.

---

## 6. Known limitations

1. **No verification yet** of installability, lint cleanliness, or build —
   reported honestly above.
2. `package-lock.json` does not exist yet; CI uses `npm install` until the
   first local install is committed.
3. Backend `ruff` import-sort rule (`I`) is disabled until ruff can be run.
4. Prettier formatting is not enforced in CI yet (reason in §1, A-D4).
5. The frontend shell fetches only real health data; no market data, prices,
   forecasts, buyers or statistics are shown (none exist yet — by design).
6. No database, auth, or marketplace code — that is Phase 3/4 scope.
7. Root `.env.example` still contains legacy credentials (founder decision,
   risk R-01). The new app does not read it.

---

## 7. Changed / created / updated files

**Created:** everything under `apps/`, `scripts/`, `tests/`,
`.github/workflows/`, `docs/README.md`, `docs/phases/phase_01_foundation.md`.

**Updated:** `.gitignore` (added sections only), `README.md` (quick start
added on top; legacy content preserved).

**Deleted:** nothing.

---

## 8. Next step for the founder

1. Install the missing tools (§4 step 0).
2. Run `.\scripts\test.ps1`.
3. Paste the **output** (it contains no secrets) back here.
4. I fix every reported failure, then we review Phase 1 for approval.
