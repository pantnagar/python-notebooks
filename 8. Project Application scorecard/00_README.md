# Meridian Trust Bank (MTB) — Personal Loan Application Credit Scorecard

An end-to-end, industry-style credit risk scorecard project simulating the work
of a Credit Risk Analyst at a third-party analytics vendor servicing an
Australian retail bank ("Meridian Trust Bank").

**Pipeline:** SQL Server (SSMS) → Python/Jupyter (Pandas) → Excel → Power BI

---

## Project scope

Build a Personal Loan Application scorecard from raw data through to a
business-usable output: application ID → predicted PD → credit score → risk
band → decision, validated with standard credit risk performance metrics and
presented via a Power BI portfolio dashboard.

## Folder structure

```
MTB_Personal_Loan_Scorecard/
├── 00_README.md                    <- you are here
├── 01_data/
│   ├── raw_csv/                    <- synthetic source CSVs + modeling/scored datasets
│   ├── data_dictionary.xlsx        <- full column-level documentation
│   └── *.json / *.pkl              <- frozen bin specs, IV lookups, model artifacts
├── 02_sql/
│   ├── 01_create_tables.sql        <- DDL, PKs, FKs, indexes
│   ├── 02_bulk_insert_csvs.sql     <- load CSVs into SQL Server
│   ├── 03_data_quality_checks.sql  <- referential integrity, nulls, ranges
│   ├── 04_merge_and_target.sql     <- Good/Bad target definition + modeling view
│   └── 05_vintage_analysis.sql     <- MOB curves, performance window validation
├── 03_notebooks/
│   ├── 01_eda_cleaning.ipynb
│   ├── 02_woe_binning.ipynb
│   ├── 03_information_value.ipynb
│   ├── 04_logistic_regression.ipynb
│   ├── 05_scorecard_build.ipynb
│   ├── 06_validation.ipynb
│   └── 07_business_output.ipynb
├── 04_excel/
│   ├── scorecard_summary.xlsx      <- Overview, Portfolio Summary (live formulas),
│   │                                   Scorecard Table, Model Performance, Scored Applications
│   └── scorecard_table_export.csv
├── 05_powerbi/
│   └── powerbi_data_model_guide.md <- star schema, DAX measures, dashboard pages
└── 06_deliverables/
    ├── final_scored_applications.csv
    ├── final_scorecard.json
    ├── model_performance_report.md
    └── workflow_diagram.md
```

## Data model

Five tables, deliberately at **different grains** — this is the first real
design decision in the project, not a simplification:

| Table | Grain | Why this grain |
|---|---|---|
| `customer_details` | 1 row per customer | Stable customer attributes |
| `loan_applications` | 1 row per application | **Primary grain of the whole project.** One customer can have many applications. |
| `bureau_data` | 1 row per application | Bureau data is a **snapshot at application time** — not a live customer attribute. Keying this on customer_id instead would leak a customer's *future* bureau history into an *earlier* application. |
| `transactions` | many rows per customer | Ongoing banking behavior, independent of any one loan |
| `loan_performance` | 1 row per application per MOB | The monthly performance panel — this table is what makes target creation (Stage 2) and vintage analysis (Stage 3) possible at all |

## Key methodology decisions (and how we arrived at them)

### Target definition: Good/Bad based on 90+ DPD

Standard Basel/APRA-aligned definition. A loan is **Bad** if it reaches 90+
days past due (`dpd_bucket = 4`) within the performance window. Anything else
is **Good**, provided it has been observed for the full window. Applications
too recent to have completed the window are **Indeterminate** and excluded
from modeling — never labeled Good by default (a very common real-world
mistake that silently understates the bad rate).

### Performance window: 18 months — a MEASURED decision, not an assumption

This is the most important methodological lesson in the project, and we're
documenting it explicitly because it's exactly the kind of validation a real
model documentation package would show:

1. We first proposed a **12-month** window as a reasonable first pass.
2. Vintage/MOB curve analysis (Script 05) tested that assumption directly:
   for vintages mature enough to observe out to 24 months, how much of the
   *eventual* (24-month) bad rate had already shown up by month 12?
3. **Answer: only about 80%.** Roughly 1 in 5 eventual bads had not yet
   occurred by MOB 12 — the cumulative bad rate curve was still climbing
   steeply, not flattening.
4. We extended the window to **18 months** and re-tested: at MOB 18, only
   ~3–4% of eventual bads were still missing — a defensible maturity level.
5. **Result:** target variable uses an 18-month performance window
   (~5,578 applications in the modeling population, ~3.48% bad rate).

**Never lock in a performance window before testing it against vintage
curves.** A model trained on an immature window systematically understates
risk, because "Good" really means "not yet observed long enough to know."

### Bugs we actually hit while building this (kept here deliberately)

Real synthetic-data and real production pipelines both have this class of
bug, and catching them is part of the skill this project is meant to build:

1. **Age generation bug:** `Faker.date_of_birth(minimum_age=18, ...)`
   guarantees age 18+ *at the moment the code runs*, not as of our project's
   reference date. A handful of synthetic customers came out as young as 15
   when re-checked against `2024-01-01`. Fixed by validating age against the
   project's own reference date, not the library's internal clock.
   **Lesson:** any "age" or "tenure" field computed by a third-party function
   has an implicit reference point — check what it actually is.

2. **Write-off persistence bug:** the first version of the performance-panel
   generator stopped emitting rows for a loan the moment it defaulted. This
   silently removed defaulted loans from *both* the numerator and
   denominator of cumulative bad-rate calculations at every MOB after the
   default — which produced a *cumulative* bad rate that occasionally
   **decreased** between months, a logical impossibility. Fixed by having
   defaulted loans persist in the performance panel, frozen at Bad, through
   the full observation horizon.

3. **Survivorship bias in paid-off loans:** similarly, loans that reached
   the end of their contractual term (paid off, never defaulted) were also
   disappearing from the performance panel — shrinking the cohort
   denominator unevenly across vintages (a vintage with many 12-month loans
   lost members starting MOB 13; a vintage of mostly 36-month loans didn't).
   Fixed by persisting paid-off loans too, frozen at Good/closed.

**Both of these bugs were caught using the exact validation checks now built
into `05_vintage_analysis.sql`**: (a) cumulative bad rate must be
monotonically non-decreasing per vintage, and (b) a vintage's cohort
denominator must stay constant across MOBs (barring snapshot-date
right-censoring). Run those checks first, before trusting any vintage curve
you build — in this project or any other.

## Snapshot date

All "as of" calculations (months available, indeterminate flagging, etc.) use
a fixed snapshot date of **2025-09-30**. Applications span 2023-01-01 through
2024-12-31, giving the earliest vintages ~32 months of observable history and
the most recent applications ~9 months (hence why late-2024 applications are
Indeterminate under an 18-month window).

## How to run Stage 1

1. Copy `01_data/raw_csv/*.csv` to a local path SQL Server can read.
2. Run `02_sql/01_create_tables.sql` in SSMS to create the database and schema.
3. Update the file paths in `02_sql/02_bulk_insert_csvs.sql` to match where
   you saved the CSVs, then run it.
4. Run `02_sql/03_data_quality_checks.sql` and confirm all checks pass
   (expected results are documented inline).
5. Run `02_sql/04_merge_and_target.sql` to build the target variable and
   modeling dataset view.
6. Run `02_sql/05_vintage_analysis.sql` to reproduce the performance-window
   validation described above.

## Stage roadmap (this project)

| # | Stage | Status |
|---|---|---|
| 1 | Data Gathering & Integration | ✅ Complete |
| 2 | Target Variable Creation | ✅ Complete |
| 3 | Vintage Analysis | ✅ Complete |
| 4 | Data Cleaning & EDA | ✅ Complete |
| 5 | WOE & Binning | ✅ Complete |
| 6 | Information Value | ✅ Complete |
| 7 | Logistic Regression | ✅ Complete |
| 8 | Credit Scorecard | ✅ Complete |
| 9 | Model Validation & Performance | ✅ Complete |
| 10 | Business Output (Excel + Power BI) | ✅ Complete |

## Final model summary

- **4-variable logistic regression** on WOE-transformed inputs:
  `bureau_credit_score`, `defaults_on_file`, `total_existing_debt`,
  `employment_type` (selected via backward stepwise elimination from a
  7-variable IV shortlist, after resolving a multicollinearity conflict
  between `defaults_on_file` and `months_since_last_delinquency`)
- **Test set performance:** AUC 0.613, Gini 0.227, KS 24.1 — modest but
  genuine and honestly reported (see `06_deliverables/model_performance_report.md`)
- **5 risk bands** (Decline / High Risk-Refer / Standard / Preferred /
  Premium) with monotonically decreasing bad rate, validated on both train
  and test
- **Final output:** 5,578 scored applications in
  `06_deliverables/final_scored_applications.csv`

## Real bugs caught and fixed in Stages 5-10 (documented, not hidden)

Continuing the same honesty standard as Stages 1-3:

1. **Over-separated synthetic data (Stage 6):** the first calibration of
   the data generator made `bureau_credit_score` an almost perfect proxy for
   true default risk (IV > 3.0 — real scorecards rarely exceed ~0.5-0.8 for
   any single variable). Root cause: the observable bureau score and the
   hazard function were both deterministic functions of the identical
   latent risk variable. Fixed by decoupling them with independent noise
   and recalibrating via Monte Carlo simulation, landing bureau score IV at
   a realistic ~0.27.
2. **Hard-coded, incomplete collinearity check (Stage 7):** the first
   version of the multicollinearity handling only checked for one
   anticipated variable pair. It missed a much stronger pair
   (`defaults_on_file` / `months_since_last_delinquency`, r=0.89, linked by
   construction since the latter is only defined when the former is
   nonzero), which produced a wrong-signed coefficient. Fixed by
   generalizing the check to scan all pairs above a correlation threshold.
3. **Naive one-shot p-value cutting (Stage 7):** dropping every
   non-significant variable in a single pass landed on a different (worse)
   model than proper backward stepwise elimination, which drops one
   variable at a time and refits. Replaced with stepwise elimination,
   which kept `employment_type` — a variable with real business
   rationale that the naive approach would have discarded.
4. **Scorecard sign-convention bug (Stage 8):** the textbook
   Offset+Factor×logit formula was applied directly to a model whose
   `logit` was log-odds of BAD, not log-odds of GOOD as the formula
   assumes — this silently produced a scorecard giving the HIGHEST scores
   to the RISKIEST applicants. Caught only because Stage 8 explicitly
   checks that bad rate decreases monotonically across risk bands, not
   merely that the points arithmetic is internally consistent. Fixed with
   an explicit sign correction and a hard validation check
   (`credit_score` must correlate negatively with `bad_flag`) that halts
   execution if violated.
5. **Misleading "approval rate" metric (Stage 10):** an early business
   summary defined "approved" as "not Declined," which incorrectly counted
   "Refer to Manual Underwriting" applications as approvals (92.8%
   reported). Fixed to count only explicit "Approve - ..." decision
   categories — correct figure is 65.97% (see also the related test/train
   decision-mapping gap bug in `CHANGELOG.md` v1.4, which affected the
   figure again after this fix and was caught by the automated test suite
   in `tests/test_pipeline_outputs.py`).

**The pattern across all five:** each bug produced output that looked
plausible and ran without error — the danger was never a crash, it was a
confident, wrong number. Every one was caught by a deliberate, concrete
correctness check (a direction check, a monotonicity check, a business
sense-check) rather than by code simply failing to execute.
