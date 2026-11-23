# AgriPredict AI — UI/UX Audit & Visual Quality Review

## 1. Overview & Baseline Verification

- **Frontend Technology**: React 19, TypeScript, Vite, Hash-based client router (`apps/web`).
- **Backend Architecture**: FastAPI, Python 3.14, SQLAlchemy Async, SQLite dev/test DB (`preview.db`).
- **Verified Status**:
  - TypeScript: `tsc --noEmit` exits with 0 errors.
  - Frontend Vitest: 19 tests passing.
  - Backend Pytest: 286 tests passing.

---

## 2. Page-by-Page Audit & Visual Defect Inventory

### A. Global Shell & Navigation (`AppShell.tsx`, `components.css`)
- **Active Navigation State**: Active link indicator was low-contrast (`rgba(255, 255, 255, 0.16)`). Needs harvest gold / high-contrast focus indicator.
- **Mobile Menu (360px & 390px)**: Nav links lacked explicit touch target height (`44px` minimum) on mobile drawer.
- **Header Shadow & Boundary**: Needed subtle border/shadow separation from warm ivory page background.

### B. Landing Page (`LandingPage.tsx`)
- **Syntax Defects**: `<section mb-9>` had `mb-9` passed as an unparsed JSX attribute instead of `className="section mb-9"`.
- **Card Alignment**: Feature cards in `.card-grid` had variable text heights causing jagged footer baselines.
- **Trust Messaging**: HealthStatus card and data transparency card needed more cohesive visual weight matching the new warm ivory & forest green palette.
- **Action Hierarchy**: Hero actions needed clear primary (Dashboard / Compare) vs secondary discovery pills with consistent hover elevation.

### C. Farmer & Role Dashboards (`DashboardPage.tsx`)
- **Discovery Pillars**: The 5 pillars (Market, Net Comparison, Schemes, Verified Buyers, Logistics/Storage) needed refined card hover states, clear badges, and consistent typography.
- **Voluntary Selling Choice**: The produce selling banner needed clear visual prominence as an optional choice, not a mandatory task.
- **Role Dashboards**: Buyer, Transport, Storage, and Admin workspaces needed visual polish, consistent card headers, responsive metric displays, and aligned action buttons.

### D. Mandi Comparison & Net Realization (`MandiComparisonPage.tsx`)
- **Missing Form Control Classes**: Inputs used `className="select"` and `className="input"`, which were unstyled in `components.css`.
- **Table Scannability**: Multi-column comparison table needed sticky headers, tabular numerals for currency (`tabular-nums`), and clear visual highlight on the best realization row.
- **What-If Slider Accessibility**: Slider inputs needed accessible labels, clear value readout tags, and smooth track styling.

### E. Government Schemes (`GovernmentSchemesPage.tsx`)
- **Filter Tabs**: Tabs overflowed on mobile without smooth horizontal scroll indicators.
- **Match Status**: Needed accessible badges indicating official verification status, required documentation, and clear disclaimers that match does not guarantee sanction.
- **Form Selectors**: Used `className="select"` needing design token integration.

### F. Buyer Marketplace (`BuyerMarketplacePage.tsx`)
- **Modal Dialog**: Post requirement modal was an inline card; needed proper elevation, responsive card grid, and clear focus styling.
- **Form Controls**: Used `className="input"` and `className="select"` needing proper styling.
- **Verification Badges**: Display verified APMC & Corporate status with consistent semantic badges.

### G. Services Directory (`ServicesPage.tsx`)
- **Fleet & Cold Store Cards**: Cards had inconsistent padding between provider ratings, capacity meters, and action buttons.
- **Capacity Indicators**: WDRA dry godowns and cold stores needed visual capacity progress bars with accessible contrast.

### H. Market Price Board (`MarketPage.tsx`)
- **Table Overflow on Mobile**: Tables overflowed without dedicated horizontal scroll cues and mobile card fallbacks.
- **Null Value Handling**: Preserved strict distinction between unquoted prices vs zero prices.
- **Freshness Banner**: Clear distinction between upstream pipeline import timestamp and row market day.

### I. Authentication & Profile (`AuthPage.tsx`, `FarmerProfilePage.tsx`)
- **Touch Target Sizes**: OTP and phone inputs needed 44px+ height and crisp focus rings.
- **Privacy Toggles**: CheckboxField toggles needed consistent alignment and readable descriptions.

---

## 3. Prioritized Repair Plan

1. **Design Tokens & Foundation** (Complete): Forest green `#153F35`, Primary green `#26745A`, Light surface `#EAF3EC`, Warm ivory `#F7F6F0`, Harvest gold `#E9B949`, Borders `#DCE3DC`, Text `#202923`.
2. **Components & Controls CSS**: Add `.input`, `.select`, modal styles, table enhancements, progress bars, range sliders, and responsive utilities.
3. **AppShell & Navigation**: Refine mobile drawer, 44px touch targets, active link gold indicator, skip link.
4. **Landing & Dashboard Refinement**: Clean JSX defects, polish card layouts, enforce role navigation, align discovery pillars.
5. **Interactive Feature Pages**: Enhance Mandi Comparison, Government Schemes, Buyer Marketplace, and Services.
6. **Form & Data Table Readability**: Fix tables for mobile (360px), polish input fields and badges.
7. **Accessibility & Responsive Verification**: Keyboard focus rings, `prefers-reduced-motion` compliance, multilingual verification (EN, HI, TE).
