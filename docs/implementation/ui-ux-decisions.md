# AgriPredict AI — UI/UX Design Decisions & Motion System

Date: 2026-10-10  
Author: Product Design & Frontend Architecture Team

---

## 1. Core Design Philosophy: Purposeful, Credible, Calming

AgriPredict AI is an agricultural decision-support platform designed for real-world farmers, buyers, logistics providers, and administrators. The interface must communicate authority, trust, clarity, and warmth without generic SaaS dashboard clutter, gimmicky neon accents, or unverified claims.

### Key Visual Tenets
1. **Calm Agricultural Palette**:
   - Primary: Deep forest green (`--color-primary`, `--color-primary-dark`) conveying crop vitality and stability.
   - Backgrounds: Warm neutral off-white (`--color-bg-canvas`) avoiding sterile clinical white.
   - Surfaces: Crisp white cards (`--color-bg-surface`) with subtle 1px border lines (`--color-border-subtle`).
   - Alerts & Accents: Restrained amber for freshness/cooldown warnings; crimson red exclusively for errors and destructive actions.
2. **Data Truthfulness & Unit Clarity**:
   - Every price number has an explicit unit attached (e.g. `₹2,450 / quintal`).
   - Every date or observation displays provenance (`Agmarknet APMC`, `Observed on 2026-10-08`).
   - Tabular numerals (`font-variant-numeric: tabular-nums`) are enforced on all monetary and quantity figures to guarantee column alignment.
3. **No Forced Farmer Selling**:
   - An individual farmer's primary goal is frequently checking market prices, comparing nearby mandis, or discovering government subsidies.
   - "Sell Produce" is an **optional contextual CTA**, not a mandatory onboarding obstacle or the dominant dashboard hero.

---

## 2. Information Architecture & Role Navigation

### Role Shell Rules
- **One Platform, Distinct Views**: The authenticated role dictates the primary navigation in [`AppShell.tsx`](file:///d:/Projects/AgriPredict-AI%20anti/apps/web/src/components/AppShell.tsx).
- **Public Visitor**: Home, Market Intelligence, Government Schemes, How it Works, Sign In.
- **Farmer**:
  - Primary Nav: Home (Dashboard), Market Intelligence, Mandi Comparison, Government Schemes, Buyers, Services.
  - Secondary Nav: My Produce (`/lots`), Messages, Profile.
  - Contextual CTA: "Sell Produce" (single-lot guided stepper).
- **Buyer / Trader**:
  - Primary Nav: Overview, Browse Produce, My Requirements, Offers, Orders, Messages, Profile.
- **Transport Provider**:
  - Primary Nav: Overview, Requests, Vehicles & Fleet, Quotes, Bookings, Availability.
- **Storage Provider**:
  - Primary Nav: Overview, Facilities, Inquiries, Quotes, Bookings, Capacity Tracker.
- **Admin**:
  - Primary Nav: Overview, Users & Roles, Provider Verification, Market Ingestion Health, Reference Data, Schemes, Audit Logs.

---

## 3. Motion & Animation System

Animations must guide visual focus, provide clear haptic-style feedback, and communicate system state changes without inducing cognitive fatigue or delaying user actions.

### Motion Principles
1. **Restraint Over Spectacle**: Never animate simply for decoration. Motion must communicate state (loading, expanding, transition, success).
2. **Speed & Easing**:
   - Micro-interactions (button press, hover): `150ms ease-out`.
   - Card reveals, dropdowns, dialogs: `220ms cubic-bezier(0.16, 1, 0.3, 1)` (quick entry, gentle settle).
   - Step transitions: `250ms ease-in-out` with subtle horizontal drift (6px).
3. **Strict Accessibility (`prefers-reduced-motion: reduce`)**:
   - When the user's OS requests reduced motion, all positional translations, scale changes, and continuous shimmers are disabled, falling back to simple opacity fades or instant transitions.

### Motion Tokens
```css
--transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
--transition-normal: 220ms cubic-bezier(0.16, 1, 0.3, 1);
--transition-slow: 320ms cubic-bezier(0.16, 1, 0.3, 1);

--anim-fade-in: fadeIn 220ms cubic-bezier(0.16, 1, 0.3, 1) both;
--anim-slide-up: slideUp 240ms cubic-bezier(0.16, 1, 0.3, 1) both;
--anim-scale-in: scaleIn 180ms cubic-bezier(0.16, 1, 0.3, 1) both;
```

---

## 4. CTA Hierarchy & Action Rules

| Tier | Visual Treatment | When to Use | Example |
|---|---|---|---|
| **Primary CTA** | Solid forest green, elevated on hover, prominent focus ring | The single most impactful action on the screen | "Calculate Net Return", "Send Verification Code", "Publish Produce" |
| **Secondary CTA** | Outlined border with soft hover background | Supporting, reversible, or discovery actions | "Compare Mandis", "Save Draft", "View Details" |
| **Quiet / Ghost** | No border, text-only with underline or background hover | Low-priority utility actions | "Cancel", "Back to Market", "Close" |
| **Destructive** | Crimson red outline/solid, requires confirmation dialog | Irreversible actions | "Archive Listing", "Reject Offer" |

---

## 5. Responsive Behavior & Mobile-First Standards

- **Target Viewports**: 360px (entry Android smartphones), 390px (modern iPhones), 768px (tablets), 1280px+ (desktop).
- **Touch Targets**: Minimum 44×44 CSS pixels for all buttons, inputs, toggles, and nav pills.
- **Zero Horizontal Scroll**: Tables automatically transform into stacked key-value cards on viewports `< 640px`.
- **Keyboard Navigation**: All interactive elements have high-contrast `:focus-visible` rings (`outline: 2px solid var(--color-primary-focus)`).
