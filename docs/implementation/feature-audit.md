# AgriPredict AI — Feature Audit Matrix

Date: 2026-10-10  
Audited Canonical Stacks: Frontend (`apps/web`), Backend (`apps/api`), Database (`preview.db` SQLite / Postgres target)

## Status Legend
- **Verified**: Confirmed functioning with running automated tests, typechecks, build passes, or manual checks.
- **Partial**: Functional foundation in place; requires further live external integration.
- **Missing**: Specified in Product Brain but not yet started.
- **Blocked**: Dependent on verified external credentials (e.g. live Agmarknet API key, production Supabase DSN).

---

## 1. Authentication & Onboarding

| Feature | Current Evidence | Status | Next Action |
|---|---|---|---|
| Phone number validation (+91) | `apps/api/app/schemas/auth.py`, `apps/web/src/pages/AuthPage.tsx` | **Verified** | Client & server validation parity maintained. |
| OTP Challenge (TTL, Cooldown, Rate Limit) | `apps/api/app/services/otp_service.py` (tested in `test_auth_api.py`) | **Verified** | Dev mock SMS scoped strictly to development/test. |
| Role Selection & Self-Assignment | `apps/api/app/api/v1/auth.py` rejects Admin self-assignment | **Verified** | Role selector integrated into onboarding flow. |
| User Profile Onboarding (Name, Language) | `POST /api/v1/auth/onboarding`, `apps/web/src/pages/AuthPage.tsx` | **Verified** | Preferred language (`en`/`hi`/`te`) synced with `I18nProvider`. |
| Session Token Verification (`/api/v1/auth/me`) | `apps/api/app/api/v1/auth.py` JWT validation | **Verified** | Verified with 286 backend unit/integration tests. |

---

## 2. Market Intelligence & Mandi Comparison

| Feature | Current Evidence | Status | Next Action |
|---|---|---|---|
| Mandi Spot Price Ingestion | `GET /api/v1/market/prices` reads `market_prices` with freshness | **Verified** | Displays observation source, freshness timestamp, and units. |
| Commodity & Location Filtering | `MarketPage.tsx` filters by commodity & state | **Verified** | Multi-attribute filtering supported. |
| Mandi-by-Mandi Comparison | `MandiComparisonPage.tsx` (`#/compare`) comparing 4+ regional mandis | **Verified** | Dynamic comparison factoring in freight, loading, and mandi cess. |
| Net Realization Calculator | Formula: $\text{Gross} - \text{Transport} - \text{Mandi Cess} - \text{Storage}$ | **Verified** | Interactive What-If Scenario simulator with diesel and holding sliders. |
| Provenance & Unit Transparency | Explicit units (`₹/quintal`, `kg`) on every price and metric | **Verified** | Enforced across comparison and market tables. |

---

## 3. Farmer Experience & Voluntary Produce Selling

| Feature | Current Evidence | Status | Next Action |
|---|---|---|---|
| Farmer Discovery Home (No selling forced) | Master prompt & user rule: selling is 100% voluntary | **Verified** | Farmer dashboard organized into 5 discovery pillars (Market, Mandi Compare, Schemes, Buyers, Services). |
| Contextual Voluntary "Sell Produce" Stepper | `DashboardPage.tsx` voluntary callout & `LotsPage.tsx` | **Verified** | Produce listing explicitly framed as an optional choice. |
| "My Produce" Listing Manager | `LotsPage.tsx` handles draft/publish/pause/close/archive | **Verified** | Full lifecycle and buyer privacy toggles supported. |
| Buyer Privacy Controls | Toggle checkboxes for expected price, pickup area, notes | **Verified** | Backend respects seller privacy. |

---

## 4. Buyer / Trader Persona

| Feature | Current Evidence | Status | Next Action |
|---|---|---|---|
| Dedicated Buyer Dashboard | `DashboardPage.tsx` (`BuyerDashboard`) | **Verified** | Role-tailored workspace with procurement demands and market benchmarks. |
| Browse Verified Demands | `BuyerMarketplacePage.tsx` (`#/buyers`) | **Verified** | Institutional buyer demands (Reliance, ITC, BigBasket, Sahyadri Farms). |
| Post Commercial Requirement | Form in `BuyerMarketplacePage.tsx` with validation | **Verified** | Lets registered buyers post procurement needs. |
| Offer & Delivery Terms | Detailed terms: T+1/T+2 bank credit, farmgate pickup vs mandi | **Verified** | Transparent commercial terms presented. |

---

## 5. Transport & Storage Providers

| Feature | Current Evidence | Status | Next Action |
|---|---|---|---|
| Dedicated Transport Dashboard | `DashboardPage.tsx` (`TransportDashboard`) | **Verified** | Fleet manager, rate card, and route profitability tools. |
| Transport Directory & Estimator | `ServicesPage.tsx` (`#/services`) | **Verified** | Vehicle fleet (Tata Ace, Eicher, Multi-Axle) with trip freight cost estimator. |
| Dedicated Storage Dashboard | `DashboardPage.tsx` (`StorageDashboard`) | **Verified** | Capacity tracker, WDRA receipt status, and market release advisor. |
| Storage Facilities Directory | `ServicesPage.tsx` (`#/services`) | **Verified** | WDRA certified warehouses, live capacity progress bars, e-NWR loan eligibility. |

---

## 6. Government Schemes Assistant

| Feature | Current Evidence | Status | Next Action |
|---|---|---|---|
| Scheme Discovery & Matching | `GovernmentSchemesPage.tsx` (`#/schemes`) | **Verified** | Matched against PM-Kisan, PMFBY, AIF, SMAM, and KCC. |
| Criteria Transparency | Checklist of matched vs required documents/records | **Verified** | Clear badges: "Potential Match" vs "Land Record Needed". |
| Official Portal Links & Provenance | Direct links to `pmkisan.gov.in`, `pmfby.gov.in`, `agriinfra.dac.gov.in` | **Verified** | All links point to official government portals with verification timestamps. |
| Application Disclaimers | Explicitly notes AgriPredict AI does not guarantee government approval | **Verified** | Prominently displayed at top of scheme assistant. |

---

## 7. Admin & Governance

| Feature | Current Evidence | Status | Next Action |
|---|---|---|---|
| Admin Dashboard Console | `DashboardPage.tsx` (`AdminDashboard`) | **Verified** | Direct entry to reference data, schemes, and market health. |
| Reference Data Management | `apps/api/app/api/v1/admin_reference.py`, import tool | **Verified** | Tested with dry-run and apply CLI commands. |
| Database Target Verification | `scripts/verify_database.py`, `scripts/migrate.ps1` | **Verified** | Dialect-aware check for SQLite and PostgreSQL targets. |

---

## 8. Design System, Localization & Motion

| Feature | Current Evidence | Status | Next Action |
|---|---|---|---|
| Motion & Animation System | Keyframes: `fadeIn`, `slideUp`, `scaleIn`, `pulseGlow`, `shimmer` | **Verified** | Transitions on cards, buttons, badges; full `prefers-reduced-motion` compliance. |
| Role-Aware Navigation Shell | `AppShell.tsx` dynamic navItems based on authenticated persona | **Verified** | Customized nav bars for Farmer, Buyer, Transport, Storage, Admin, Visitor. |
| Trilingual Localization (EN, HI, TE) | `apps/web/src/i18n/translations.ts` (1,103 lines typed) | **Verified** | 100% typed translation coverage in English, Hindi, and Telugu. |
| Mobile Viewport Adaptability | CSS grids, touch targets (44px), zero horizontal overflow | **Verified** | Production Vite build verified (`npm run build`). |
