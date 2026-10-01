# Power BI Data Model & Dashboard Guide
## Meridian Trust Bank — Personal Loan Application Credit Scorecard

This guide walks through building a Power BI dashboard on top of this
project's outputs. It assumes Power BI Desktop and a connection either to
`final_scored_applications.csv` (simplest) or directly to the
`MTB_ScorecardProject` SQL Server database (more realistic, and preferred if
you have SSMS/SQL Server running from Stage 1).

---

## 1. Data sources to connect

| Source | Use |
|---|---|
| `06_deliverables/final_scored_applications.csv` | Primary fact table — one row per scored application |
| SQL Server `dbo.loan_performance` (via Script 01-04) | For a vintage/MOB trend visual, if you want to go beyond the static scorecard output |
| `01_data/data_dictionary.xlsx` | Reference only — not loaded into the model, just for building tooltips/documentation |

**Recommended approach:** connect Power BI directly to SQL Server
(`Get Data → SQL Server`, pointing at `MTB_ScorecardProject`) for the
`loan_performance` vintage data, and import `final_scored_applications.csv`
for the scored application fact table. This mirrors a realistic production
setup: SQL Server holds the transactional/performance history, while the
final model OUTPUT — which lives outside the source system, since it comes
from Python modeling, not raw operational data — is loaded as its own table.

## 2. Data model (star schema)

Build a simple star schema:

```
                    ┌─────────────────────┐
                    │   Dim_RiskBand       │
                    │  (Decline/Refer/     │
                    │   Standard/Preferred/│
                    │   Premium, sort order)│
                    └──────────┬───────────┘
                               │
┌──────────────┐      ┌────────▼─────────────┐      ┌──────────────────┐
│  Dim_Date     │◄─────┤  Fact_ScoredApps      ├─────►│  Dim_LoanPurpose │
│ (application_ │      │  (from final_scored_  │      │                  │
│  date calendar)│      │  applications.csv)    │      └──────────────────┘
└──────────────┘      └────────┬──────────────┘
                               │
                      ┌────────▼─────────────┐
                      │  Fact_LoanPerformance │
                      │  (from SQL, for MOB/  │
                      │   vintage visuals)     │
                      └───────────────────────┘
```

**Why a star schema, not one flat table:** Power BI's DAX engine is
optimized for star schemas — filters propagate cleanly from dimension
tables to fact tables, and it keeps the model from becoming an
unmaintainable wide table as you add more visuals. For a project this size,
a fully normalized model is overkill, but at minimum separate out
`Dim_Date` (for time intelligence functions) and `Dim_RiskBand` (to control
sort order — risk bands need to display Decline→Premium, not alphabetically).

### Building Dim_Date
`Modeling → New Table`:
```
Dim_Date = CALENDAR(DATE(2023,1,1), DATE(2024,12,31))
```
Then add calculated columns for `Year`, `Month`, `YearMonth` (for vintage
grouping) using standard DAX date functions.

### Building Dim_RiskBand (for correct sort order)
`Enter Data`, manually create:
| RiskBand | SortOrder |
|---|---|
| Decline | 1 |
| High Risk - Refer | 2 |
| Standard | 3 |
| Preferred | 4 |
| Premium | 5 |

Relate `Fact_ScoredApps[risk_band]` → `Dim_RiskBand[RiskBand]` (many-to-one).
Then set `Dim_RiskBand[RiskBand]` to sort by `SortOrder` (column tool: "Sort
by Column").

## 3. Key DAX measures to create

```dax
Total Applications = COUNTROWS(Fact_ScoredApps)

Total Bads = SUM(Fact_ScoredApps[bad_flag])

Bad Rate = DIVIDE([Total Bads], [Total Applications])

Avg Predicted PD = AVERAGE(Fact_ScoredApps[predicted_pd])

Avg Credit Score = AVERAGE(Fact_ScoredApps[credit_score])

Approval Rate =
VAR ApprovedCount =
    CALCULATE(
        [Total Applications],
        Fact_ScoredApps[decision] IN {
            "Approve - Standard Terms",
            "Approve - Preferred Pricing",
            "Approve - Premium Pricing"
        }
    )
RETURN DIVIDE(ApprovedCount, [Total Applications])

Decline Rate =
DIVIDE(
    CALCULATE([Total Applications], Fact_ScoredApps[decision] = "Decline"),
    [Total Applications]
)

-- Calibration gap: predicted vs actual, useful as a dashboard health check
Calibration Gap = [Avg Predicted PD] - [Bad Rate]
```

**Why `Approval Rate` needs an explicit list of decision values, not just
"not Decline":** this mirrors the real bug caught and fixed in Stage 10's
notebook — "Refer to Manual Underwriting" is neither an approval nor a
decline, and a careless `!= "Decline"` filter would overstate the automated
approval rate. Encode the correct business logic explicitly in the measure,
the same way the notebook does.

## 4. Recommended dashboard pages

### Page 1 — Portfolio Overview
- KPI cards: Total Applications, Bad Rate, Approval Rate, Avg Credit Score
- Bar chart: Applications by Risk Band (sorted Decline→Premium via
  `Dim_RiskBand`)
- Bar chart: Bad Rate by Risk Band (same sort) — this is the single most
  important visual in the whole dashboard; it's the direct visual proof the
  scorecard rank-orders risk
- Donut/bar: Decision mix (Approve tiers / Refer / Decline)

### Page 2 — Score Distribution & Model Health
- Histogram: `credit_score` distribution (use a calculated column binning
  score into 20-point buckets, since Power BI doesn't histogram numeric
  columns natively without binning)
- Scatter or line: Calibration check — Avg Predicted PD vs Observed Bad
  Rate, by score decile (create a `Score Decile` calculated column using
  `RANKX` or Power Query bucketing)
- Card: Model Performance metrics (AUC, Gini, KS) — these are static values
  from Stage 9, not live DAX measures (they're properties of the model
  itself, not something that recalculates as new applications flow in) — add
  them as a small static table or card visuals with the Stage 9 values typed
  in directly, clearly labeled "as of model development."

### Page 3 — Vintage & Portfolio Trends
- Line chart: cumulative bad rate by MOB, one line per vintage month (this
  needs `Fact_LoanPerformance` from SQL Server — reproduces Stage 3's
  vintage analysis as a live, explorable visual instead of a static SQL
  output)
- Line chart: Application volume by month (`application_date` from
  `Dim_Date`), to spot origination volume trends
- Bar: Bad rate by `loan_purpose`, `channel`, `employment_type` — lets a
  portfolio manager slice by segment beyond just risk band

### Page 4 — Underwriter / Decision Drill-through
- Table visual: application-level detail (application_id, key attributes,
  PD, score, band, decision) — filterable, for a specific applicant lookup
- Set up drill-through from Page 1's risk band bar chart to this page, so a
  user can click "Decline" on the overview and see the actual declined
  applications

## 5. Slicers to add (top of every page)
- `application_date` (date range)
- `Dim_RiskBand[RiskBand]`
- `loan_purpose`
- `channel`
- `state`

## 6. A note on what NOT to build live in Power BI

The model performance metrics (AUC, Gini, KS, PSI) from Stage 9 are
properties of the FITTED MODEL at a point in time — they were computed once,
in Python, against a specific train/test split. Do not try to recreate ROC
curve or AUC calculations natively in DAX; it's the wrong tool for that job
(no native ROC/AUC function, and reimplementing one in DAX would be fragile
and hard to verify against the Python source of truth). Bring these in as
static reference values with a clear "as of [model development date]" label,
and refresh them only when the model itself is redeveloped (see Stage 9's
PSI/stability discussion for when that might be triggered) — not on every
data refresh.

## 7. Refresh cadence (for a real production setup)

- `Fact_ScoredApps`: refreshed whenever new applications are scored (daily
  or per-batch, depending on MTB's underwriting cadence)
- `Fact_LoanPerformance`: refreshed monthly (as new MOB performance data
  becomes available)
- Model performance metrics: refreshed only on model redevelopment (not tied
  to the regular data refresh schedule)
