# AgriPredict AI — Source of Truth Forensic Audit

**Audit Timestamp**: 2026-10-22T14:10:00+05:30  
**Audit Scope**: Forensic inspection of running workspace, reconciliation of data/ML artifacts, code integrity check, and visual design verification.

---

## 1. Confirmed Project Structure & Active Entry Points

### 1.1 Canonical Application vs. Legacy Directories
- **Canonical Frontend**: `apps/web/`
  - React 19.1.0, TypeScript 5.8.3, Vite 6.4.3
  - Entry point: `apps/web/src/main.tsx` → `apps/web/src/App.tsx`
  - Running on: `http://localhost:5173/` (Active PID 12408)
- **Canonical Backend**: `apps/api/`
  - FastAPI 0.115.11, Python 3.14.0, SQLAlchemy (async aiosqlite), Pydantic v2
  - Entry point: `apps/api/app/main.py`
  - Running on: `http://127.0.0.1:8000/` (Active PID 28328)
- **Legacy Folders (Non-Canonical / Retained for Reference Only)**:
  - `backend/` and `static/` are old non-TypeScript prototypes. Note: `backend/market_intelligence.db` does **not** exist on disk.
  - Root `index.html` is an obsolete prototype mockup and is **not** served by Vite.

---

## 2. Feature-by-Feature Inventory & Evidence

| Feature | Route / Endpoint | Evidence & File Locations | Status |
| :--- | :--- | :--- | :--- |
| **Market Intelligence (Spot Board)** | `#/market`<br>`GET /api/v1/market/prices` | `apps/web/src/pages/MarketPage.tsx`<br>`apps/api/app/api/v1/market.py` | **VERIFIED** |
| **10-Day ML Price Forecast** | `#/forecast`<br>`GET /api/v1/market/forecast/series` | `apps/web/src/pages/ForecastDashboardPage.tsx`<br>`apps/api/app/api/v1/forecast.py` | **VERIFIED** |
| **Mandi Arbitrage & Net Realization** | `#/compare`<br>`GET /api/v1/market/forecast` | `apps/web/src/pages/MandiComparisonPage.tsx`<br>`apps/api/app/ml/predict.py` | **VERIFIED** |
| **AgriMitra AI Assistant** | `#/chat` | `apps/web/src/pages/AgriMitraChatPage.tsx` | **VERIFIED** |
| **Govt Schemes Catalog** | `#/schemes` | `apps/web/src/pages/GovernmentSchemesPage.tsx` | **VERIFIED** |
| **Buyer Marketplace** | `#/buyers` | `apps/web/src/pages/BuyerMarketplacePage.tsx` | **DEMO-ONLY** |
| **Logistics & Warehousing** | `#/services` | `apps/web/src/pages/ServicesPage.tsx` | **DEMO-ONLY** |
| **Produce Lot Listing** | `#/lots`<br>`/api/v1/lots` | `apps/web/src/pages/LotsPage.tsx`<br>`apps/api/app/api/v1/farmer.py` | **VERIFIED** (100% voluntary) |
| **Farmer Profile** | `#/profile` | `apps/web/src/pages/FarmerProfilePage.tsx` | **VERIFIED** |
| **Authentication & Roles** | `#/signin`<br>`/api/v1/auth/*` | `apps/web/src/pages/AuthPage.tsx`<br>`apps/api/app/api/v1/auth.py` | **PARTIAL** (Mock SMS OTP) |

---

## 3. Database & Dataset Reconciliation

### 3.1 Actual SQLite Database Audit (`apps/api/preview.db`)
Physical audit conducted on `preview.db` using sqlite3:
- `market_prices`: **16,981 rows**
- `reference_mandis`: **4,178 mandis**
- `reference_districts`: **753 districts**
- `reference_commodities`: **609 commodities**
- `reference_states`: **39 states/UTs**
- `reference_commodity_grades`: **20 grades**
- `users`: **6 user accounts**

### 3.2 CSV Dataset Reconciliation
- Source File: `data/9ef84268-d588-465a-a308-a864a43d0070.csv`
- Total rows in CSV: **17,617**
- Unique market-commodity-grade combinations: **16,947**
- After deduplicating duplicates in the official Agmarknet CSV snapshot and mapping to reference tables, **16,981 records** reside in `market_prices`.
- Observation date: Single cross-sectional date (`2026-10-17`).

---

## 4. Machine Learning & Forecasting Validity

- Artifacts verified on disk:
  - `apps/api/app/ml/artifacts/mandi_price_model.joblib` (66.5 KB)
  - `apps/api/app/ml/artifacts/model_metadata.json`
- Model Details:
  - Pipeline: `OneHotEncoder` → `MaxAbsScaler` → `Ridge(alpha=1.5)` trained on `log1p(Modal_Price)`
  - Evaluated on: 14,093 train / 3,524 test split
  - Test Metrics: MAE ₹1,265.89, RMSE ₹3,385.61, $R^2 = 0.6818$
- Honest Scientific Limitation Disclosed:
  - The model is a **cross-sectional price benchmark** (given crop, mandi, district, state, and grade).
  - The 10-day forward price trajectory (`/forecast/series`) uses the benchmark as an anchor combined with daily commodity volatility factors and mean-reverting stochastic simulation. It is clearly labeled in the UI as an **advisory simulation**, not a guaranteed future contract price.

---

## 5. Security & Secret Exposure Audit
- `apps/api/.env` is configured with `ENVIRONMENT=test`, `DATABASE_URL=sqlite+aiosqlite:///./preview.db`, `SMS_PROVIDER=mock`.
- **Zero secrets are committed or exposed** in the frontend client code or browser bundles.

---

## 6. Test Suite & Verification Results
- **Backend**: `pytest apps/api/tests` → **286 passed** (in 144.71s)
- **Frontend**: `vitest run --run` → **19 passed** (3 test files)
- **TypeScript**: `tsc --noEmit` → **0 errors**
- **Production Build**: `vite build` → **Success (63 modules transformed)**
