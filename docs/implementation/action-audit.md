# AgriPredict AI — Action & Interactive Control Audit

Date: 2026-10-10  
Audited Stack: `apps/web` React Interactive Controls (Canonical Application)

## Interactive Action Inventory

| Screen | Control Label | Target Role | Purpose / Destination | API / State Mutation | Loading / Animation State | Success Result | Error Handling | Verification Test |
|---|---|---|---|---|---|---|---|---|
| Landing | "Sign In / Register" | Public | Direct user to phone-based auth | Navigate to `#/signin` | Instant | Renders `AuthPage` | Fallback 404 | Router navigation |
| Landing | "Compare Mandis" | Public | Open net realization calculator | Navigate to `#/compare` | Instant | Opens Mandi comparison view | None | Router test |
| Landing | "Explore Market Prices" | Public | Jump to market intelligence board | Navigate to `#/market` | Instant | Opens `MarketPage` | None | Router test |
| Landing | "Government Schemes" | Public | Browse agricultural schemes | Navigate to `#/schemes` | Instant | Opens `GovernmentSchemesPage` | None | Router test |
| Landing | "Buyers" | Public | Browse verified buyer demands | Navigate to `#/buyers` | Instant | Opens `BuyerMarketplacePage` | None | Router test |
| Landing | "Services" | Public | Explore transport & storage | Navigate to `#/services` | Instant | Opens `ServicesPage` | None | Router test |
| AuthPage | "Send verification code" | Visitor | Initiates OTP request to phone | `POST /api/v1/auth/otp/request` | Spinner + button disabled | Enters OTP step, starts 30s cooldown | Inline alert with cooldown / invalid format | `test_auth_api.py::test_otp_request` |
| AuthPage | "Verify & Continue" | Visitor | Submits entered OTP code | `POST /api/v1/auth/otp/verify` | Spinner on button | Issues JWT, navigates to onboarding or dashboard | "Invalid or expired code" alert | `test_auth_api.py::test_otp_verify` |
| AuthPage | "Complete Setup" | Visitor | Saves display name & language | `POST /api/v1/auth/onboarding` | Disables form inputs | Redirects to role dashboard | Validation errors inline | `test_auth_api.py::test_onboarding` |
| Farmer Dashboard | Pillar 1: "Check Mandi Prices" | Farmer | View full mandi commodity board | Navigate to `#/market` | Card micro-elevation | Opens `MarketPage` | None | Router test |
| Farmer Dashboard | Pillar 2: "Calculate Net Return" | Farmer | Compare mandis & freight deductions | Navigate to `#/compare` | Card micro-elevation | Opens `MandiComparisonPage` | None | Router test |
| Farmer Dashboard | Pillar 3: "Find Matched Schemes" | Farmer | Discover relevant welfare schemes | Navigate to `#/schemes` | Card micro-elevation | Opens `GovernmentSchemesPage` | None | Router test |
| Farmer Dashboard | Pillar 4: "View Buyer Demands" | Farmer | View active procurement requirements | Navigate to `#/buyers` | Card micro-elevation | Opens `BuyerMarketplacePage` | None | Router test |
| Farmer Dashboard | Pillar 5: "Explore Services" | Farmer | Browse mini-trucks & cold stores | Navigate to `#/services` | Card micro-elevation | Opens `ServicesPage` | None | Router test |
| Farmer Dashboard | "+ Sell Produce (Optional)" | Farmer | Voluntary contextual harvest listing | Navigate to `#/lots` | Instant button click | Opens produce listing view | None | Router test |
| Mandi Compare | Crop Selector (`select`) | All | Changes commodity dataset | Local state `selectedCrop` | Instant re-calc | Updates mandi rows and benchmark prices | None | Component state test |
| Mandi Compare | Harvest Quantity (`input`) | All | Updates total volume in quintals | Local state `quantityQtl` | Tabular numeral update | Recalculates gross revenue, freight & net | Clamped min 1 | Math calculation verified |
| Mandi Compare | Transport Rate Slider (`range`) | All | Simulates diesel & freight shifts | Local state `freightRatePerTonneKm` | Smooth slider drag | Real-time recalculation of transport deductions | None | Scenario test verified |
| Mandi Compare | Storage Duration Slider (`range`) | All | Simulates holding period storage cost | Local state `holdingDays` | Smooth slider drag | Real-time recalculation of net return | None | Scenario test verified |
| Govt Schemes | Category Filter Tabs | All | Filters schemes by benefit type | Local state `activeFilter` | Animated fade transition | Filters scheme cards | None | Component filter test |
| Govt Schemes | Landholding Selector | Farmer | Matches land size criteria | Local state `landCategory` | Instant match update | Toggles "Potential Match" badge | None | Criteria engine test |
| Govt Schemes | Land Ownership Selector | Farmer | Matches titleholder vs tenant rules | Local state `isOwner` | Instant match update | Updates ownership checklist badge | None | Criteria engine test |
| Govt Schemes | "Apply on Official Portal" | All | Directs to authentic government site | External link (`target="_blank"`) | Browser tab open | Opens official portal (`pmkisan.gov.in`) | None | Link verification |
| Buyers Page | Commodity Filter | All | Filters active purchase demands | Local state `selectedCrop` | Instant list filter | Displays matching buyers | None | Component filter test |
| Buyers Page | "Express Interest / Connect" | Farmer | Requests direct contact with buyer | Local state `inquiredId` | Button morphs to badge | Displays success confirmation | None | Component state test |
| Buyers Page | "+ Post Requirement" | Buyer | Reveals buyer procurement form | Local state `showPostModal` | Animated modal scale-in | Opens validated form | Form validation | Buyer workflow test |
| Services Page | Tab Switcher | All | Toggles Transport vs Storage | Local state `activeTab` | Animated tab switch | Renders vehicle fleet or warehouse list | None | Component state test |
| Services Page | Trip Distance Slider | All | Estimates freight trip costs | Local state `testDistanceKm` | Live numeral recalculation | Updates trip cost estimate (₹) | None | Math calculation verified |
| Services Page | "Request Quote & Book" | All | Books commercial freight driver | Local state `bookedTransportId` | Button morphs to badge | Displays booking confirmation | None | Provider state test |
| Services Page | "Inquire Space / Reserve" | All | Inquires warehouse capacity | Local state `inquiredStorageId` | Button morphs to badge | Displays space inquiry confirmation | None | Provider state test |
| LotsPage | "+ Add a lot" | Farmer | Opens create draft lot form | Local state `creating = true` | Instant | Reveals form with validation | Form error alerts | `test_lots.py::test_create_lot` |
| LotsPage | "Publish" | Farmer | Changes status to published | `POST /api/v1/farmer/lots/{id}/status` | Row spinner | Status badge updates to green "Published" | Error toast | `test_lots.py::test_status_transition` |
| Navigation Shell | "Sign Out" | All Auth | Terminates session | Clears tokens & session state | Instant | Redirects to `#/` | None | `test_auth_api.py::test_logout` |
| Navigation Shell | Language Switcher | All | Changes locale (`en`/`hi`/`te`) | `I18nContext.setLocale` | Instant re-render | Translates all strings into chosen language | None | `i18n.test.ts` |
