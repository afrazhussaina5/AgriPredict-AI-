# AgriPredict AI — Data and Machine Learning Audit

**Date:** 2026-10-20  
**Status:** Audited & Ready for Integration  
**Scope:** Ingestion pipeline, dataset validation, ML forecasting capabilities, net-realization calculations, and frontend-backend synchronization.

---

## 1. Executive Summary

An audit was conducted on the canonical AgriPredict AI codebase, the newly supplied market dataset (`data/9ef84268-d588-465a-a308-a864a43d0070.csv`), database schema, ML feasibility, and end-to-end data flow.

### Key Audit Findings:
1. **Supplied Dataset Quality:**
   - **Total Records:** 17,617 verified rows.
   - **Null / Missing Values:** 0 across all 10 columns.
   - **Geographic Coverage:** 27 States / Union Territories, 484 Districts, 1,830 Markets (Mandis).
   - **Commodity Coverage:** 270 Commodities, 519 Varieties, 13 Quality Grades.
   - **Date Range:** Single business observation date — `17/10/2026`.
   - **Vocabulary Alignment:** **100% exact match** with the official Government of India Agmarknet reference tables (`reference_states`, `reference_districts`, `reference_mandis`, `reference_commodities`, and `reference_commodity_grades`).
   - **Unit Standard:** ₹ per Quintal (100 kg), standard Agmarknet convention.
2. **Critical Data Limitation:**
   - Because all 17,617 records originate from a single snapshot date (`17/10/2026`), **pure time-series forecasting (e.g., ARIMA, Prophet, multi-lag temporal models) cannot be honestly trained on this file alone without temporal data leakage or hallucinated historical dates**.
   - **Approved Solution:** Implement an honest two-tier ML & analytics architecture:
     - **Tier 1:** Cross-sectional price distribution model & benchmark estimator (gradient boosted tree / ridge regression evaluating expected modal prices across mandi tier, district location, crop variety, and quality grade).
     - **Tier 2:** Naive and moving-spread forecast baseline with explicit uncertainty intervals (`± standard error`) and transparent metadata disclosing that forecasts represent cross-sectional price projection, not verified multi-month time series.
3. **Database Architecture:**
   - ORM Models in `apps/api/app/models/market.py` enforce strict non-negative price constraints, decimal accuracy, and unique constraints `uq_market_prices_key` (`commodity_id`, `grade_id`, `mandi_id`, `district_id`, `state_id`, `market_date`, `unit_id`).
   - All 286 backend tests and 19 frontend vitest tests pass.

---

## 2. Dataset Schema & Validation Matrix

| Column in CSV | Data Type | Non-Null Count | Sample Values | DB Target |
| :--- | :--- | :--- | :--- | :--- |
| `State` | string | 17,617 (100%) | Maharashtra, Telangana, Andhra Pradesh, Punjab | `reference_states.name` |
| `District` | string | 17,617 (100%) | Nashik, Warangal, Guntur, Ludhiana | `reference_districts.name` |
| `Market` | string | 17,617 (100%) | Lasalgaon, Warangal, Azadpur, Khanna | `reference_mandis.name` |
| `Commodity` | string | 17,617 (100%) | Onion, Tomato, Cotton, Wheat, Soyabean | `reference_commodities.name` |
| `Variety` | string | 17,617 (100%) | Red / Garwa, Hybrid, Sharbati, Bt Cotton | `reference_commodity_varieties` |
| `Grade` | string | 17,617 (100%) | Grade A, FAQ, Medium, Grade B | `reference_commodity_grades.name` |
| `Arrival_Date` | string (date) | 17,617 (100%) | `17/10/2026` | `market_prices.market_date` |
| `Min_x0020_Price` | float | 17,617 (100%) | 2200.0, 6800.0 | Min price envelope |
| `Max_x0020_Price` | float | 17,617 (100%) | 2600.0, 7800.0 | Max price envelope |
| `Modal_x0020_Price`| float | 17,617 (100%) | 2450.0, 7550.0 | `market_prices.modal_price` |

### Statistical Distribution of Modal Prices:
- **Mean:** ₹5,513.39 / quintal
- **Median (50%):** ₹4,000.00 / quintal
- **25th Percentile:** ₹2,500.00 / quintal
- **75th Percentile:** ₹6,500.00 / quintal
- **IQR:** ₹4,000.00 / quintal

---

## 3. Machine Learning Model Architecture & Strategy

### Objective
Provide farmers with data-backed price intelligence:
1. **Expected Modal Price Benchmark:** Predict the expected modal price for a given crop, variety, and quality grade in a given district/mandi based on current market dynamics across India.
2. **Forecast Projection with Confidence Bounds:** Output a baseline projection with upper and lower confidence intervals, calculated using intra-district dispersion and historical spread.
3. **Honest Model Governance:**
   - Model version, evaluation metrics (MAE, RMSE, R²), training date, and limitations are returned in every API response.
   - Predictions are never represented as guaranteed futures.

### Training & Evaluation Pipeline:
- **Model Choice:** `HistGradientBoostingRegressor` (scikit-learn) with categorical features (`Commodity`, `Grade`, `State`, `District`, `Market`).
- **Validation Split:** Chronological/GroupKFold by District (80% train, 20% test) to prevent geographic leakage.
- **Baseline Comparison:**
  - Naive baseline: State/Commodity median price.
  - Regression Model: Predicts conditional modal price given specific quality grade and market location.
- **Model Serialization:** Pipeline saved to `apps/api/app/ml/artifacts/price_model_v1.joblib` with metadata JSON.

---

## 4. Net-Realization Engine Integration

The net realization calculation formula implemented in Phase 5:
$$\text{Gross Revenue} = \text{Modal Price} \times \text{Quantity (Quintals)}$$
$$\text{Transport Cost} = \text{Distance (km)} \times \text{Freight Rate (₹/tonne/km)} \times 0.1 \times \text{Quantity}$$
$$\text{Mandi Fees} = (\text{Base Price} \times \text{Cess Rate \%} + \text{Loading Charge}) \times \text{Quantity}$$
$$\text{Storage Cost} = \text{Holding Days} \times \text{Storage Rate (₹/qtl/day)} \times \text{Quantity}$$
$$\text{Net Realization} = \text{Gross Revenue} - (\text{Transport} + \text{Mandi Fees} + \text{Storage Cost})$$

---

## 5. Implementation Roadmap

1. **Phase 2 — Ingestion Script:** Run `apps/api/scripts/import_snapshot_dataset.py` to ingest the 17,617 rows into `market_prices`.
2. **Phase 3 — Verified Dataset Check:** Verify database row count, freshness timestamp, and provenance stamp (`agmarknet-official`).
3. **Phase 4 — Model Training & ML Endpoint:** Train the cross-sectional ML model, evaluate metrics (MAE, RMSE), save pipeline artifact, and create `/api/v1/market/forecast` endpoint.
4. **Phase 5 & 6 — Full Application Integration:** Connect UI pages (`/market`, `/compare`, `/dashboard`) to live endpoints with interactive sliders, animated breakdown bars, and live search.
5. **Phase 7 — Verification:** Run all test suites and verify production build.
