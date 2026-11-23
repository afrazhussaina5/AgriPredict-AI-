# Phase 2 — Design System, Responsive Layout, and Localization

| Field | Value |
|---|---|
| Status | **Source complete — automated checks NOT yet executed (blocked), founder run required** |
| Date | 2026-10-03 |
| Depends on | Phase 1 source (tests still pending), founder review |
| Blocking issue | Same as Phase 1: Git for Windows missing → no shell → no lint/typecheck/build can run here |

---

## 1. Phase goal and assumptions

**Goal:** the visual and linguistic foundation — design tokens, reusable
accessible components, app shell with responsive navigation, a language
selector for English/Hindi/Telugu with persistence, loading/empty/error/success
patterns, an initial public landing page and role-aware dashboard shells —
**with zero fabricated prices, forecasts, statistics or listings.**

**Assumptions**

| ID | Assumption | Why it is safe |
|---|---|---|
| A-D5 | Build a small in-house i18n layer instead of adding `i18next`/`react-i18next` | No dependency can be installed or verified on this machine; a typed ~100-line layer is fully type-checked by `tsc` and unit-tested by `vitest` |
| A-D6 | Hash-based routing (`#/`, `#/dashboard/...`) for now | Works on any static host with no server config; a routing library can replace it in Phase 4 when auth adds real navigation |
| A-D7 | `localStorage` key `agripredict.locale` for the language preference | Survives reloads, holds no personal data, degrades gracefully if storage is blocked |
| A-D8 | Dark-mode values derive from `prefers-color-scheme` using the same tokens | No user setting needed yet; adds comfort at near-zero risk |

---

## 2. What was created

```
apps/web/src/
├── design/
│   ├── tokens.css          # colors, spacing, type, radius, shadow, focus ring, dark mode
│   └── components.css      # buttons, cards, badges, alerts, fields, states, tables, menu
├── i18n/
│   ├── translations.ts     # en + hi + te, typed key parity, {placeholder} formatting
│   ├── I18nProvider.tsx    # context, persistence, document.lang, useTranslation()
│   └── i18n.test.ts        # key parity, no empty strings, placeholder parity, formatting
├── components/
│   ├── ui.tsx              # Button, Card, Badge, Alert, Spinner (no text of their own)
│   ├── states.tsx          # LoadingState, EmptyState, ErrorState, SuccessState
│   ├── fields.tsx          # TextField, SelectField with label/hint/error aria wiring
│   ├── LanguageSwitcher.tsx# EN / हिन्दी / తెలుగు selector
│   ├── HealthStatus.tsx    # real GET /api/v1/health with loading/success/error
│   └── AppShell.tsx        # skip link, header, nav, mobile menu, main, footer
├── pages/
│   ├── LandingPage.tsx     # hero, four-decision cards, five role cards, honesty notice
│   ├── DashboardPage.tsx   # role picker + role shells (clearly marked placeholders)
│   └── NotFoundPage.tsx    # translated 404
├── roles.ts                # dashboard role keys
├── router.ts               # minimal hash router (anchor-safe)
├── App.tsx                 # provider → shell → route
├── main.tsx                # imports tokens.css, components.css, styles.css
└── styles.css              # base document styles (rewritten; Phase 1 CSS absorbed)
```

**Changed:** `appInfo.ts` (phase label), `README.md`, `docs/README.md`.
**Deleted:** nothing.

---

## 3. Key decisions in plain language

| Decision | Why |
|---|---|
| **Typed translation parity** | `hi` and `te` are declared as `Record<TranslationKey, string>` against the English key set — a missing Hindi or Telugu string is a **compile error**, not a surprise on screen. |
| **Components carry no text** | Buttons/cards/alerts receive translated strings from callers, so no UI component can ever smuggle an untranslated word into the interface. |
| **Real health status, no fake numbers** | The only dynamic data on screen is the genuine backend health check. There are deliberately **no** prices, forecasts, buyer counts or user statistics anywhere. |
| **Placeholders are labelled** | Every dashboard shell shows a warning banner ("Coming in a later phase") plus an honest empty state — nobody can mistake a shell for a working feature. |
| **Mobile menu is accessible** | `aria-expanded`, `aria-controls`, keyboard-operable toggle, visible focus rings, skip link to `#main-content`, `aria-current="page"` on the active nav item. |
| **Anchor-safe routing** | The skip link (`#main-content`) and in-page anchors (`#how`) do **not** confuse the router — it only treats `#/...` hashes as routes. |

---

## 4. Commands (unchanged from Phase 1)

```powershell
.\scripts\setup.ps1      # once
.\scripts\test.ps1       # eslint + tsc + vitest + build (and backend checks)
.\scripts\start-frontend.ps1   # http://localhost:5173
```

---

## 5. Test results — ACTUAL

**Not executed.** The shell tool still reports Git for Windows missing, so no
command can run from this side. The Phase 2 checks that exist and are ready to
run: `npm run lint`, `npm run typecheck`, `npm run test` (7 new i18n/formatting
tests + the 3 existing appInfo tests), `npm run build`.

**No pass rate is claimed.**

---

## 6. Known limitations

1. No browser verification yet (no Node.js execution available here).
2. `eslint` may emit a *warning* (not an error) for `I18nProvider.tsx` because it
   exports both a component and a hook — warnings do not fail `npm run lint`.
3. Translations are my best-effort Hindi/Telugu; a native review is planned
   (assumption A-16 in the architecture doc).
4. Dashboard shells are navigation placeholders only — no data, by design.
5. No charts, tables of data, or search UI yet — those arrive with real data.

---

## 7. Requirement checklist (Phase 2 prompt)

| # | Requirement | Status |
|---|---|---|
| 1 | Shared design tokens and reusable components | ✅ source (`design/`, `components/`) |
| 2 | App shell, header, nav, footer, responsive menu | ✅ source (`AppShell.tsx`) |
| 3 | Language selector EN/HI/TE | ✅ source (`LanguageSwitcher.tsx`) |
| 4 | Translation resources + reliable localization approach | ✅ source (`translations.ts`, `I18nProvider.tsx`) |
| 5 | All visible text from translations | ✅ source review — every rendered string goes through `t()` |
| 6 | Language persists safely client-side | ✅ source (`localStorage`, try/catch guarded) |
| 7 | Accessible labels, keyboard nav, focus states, semantic HTML | ✅ source (skip link, aria wiring, `:focus-visible`) |
| 8 | Loading / empty / error / success patterns | ✅ source (`states.tsx` + real health states) |
| 9 | Landing page + role-aware dashboard shells, marked placeholders | ✅ source (`LandingPage`, `DashboardPage`) |
| 10 | No fake prices/forecasts/statistics/listings | ✅ source review (nothing fabricated anywhere) |
| — | Run lint / typecheck / build | ⛔ **BLOCKED** (Git missing) |

---

## 8. Next step for the founder

Same as Phase 1: install Git (and Node/Python if missing), run
`.\scripts\setup.ps1`, then `.\scripts\test.ps1`, and paste the output here.
I will fix every reported failure before we do the formal Phase 2 review.
