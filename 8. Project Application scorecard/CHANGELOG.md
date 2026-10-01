# Changelog
## Meridian Trust Bank — Personal Loan Application Credit Scorecard

All notable changes to this project are documented here, in the order they
actually happened during development. This follows the spirit of
[Keep a Changelog](https://keepachangelog.com/) — reverse-chronological,
grouped by type, one entry per real change — adapted for a model
development project rather than a software release.

Version numbers here mark meaningful project milestones, not calendar time.

---

## [v1.4] — Test/train decision-mapping gap & automated smoke tests

### Added
- `tests/test_pipeline_outputs.py` — 8 automated smoke tests covering row
  count, bad rate range, score direction, risk band completeness,
  monotonicity, approval-rate logic, duplicate detection, and null checks.
  These codify the exact manual checks that caught every bug listed below
  and in earlier versions.

### Fixed
- **Null decisions on the entire test set.** Stage 8's `decision_map`
  application (`risk_band` -> `decision`) was only applied to `train_woe`,
  never to `test_woe` — so every one of the 1,674 test-set applications in
  the final Stage 10 output had `decision = NaN`. This was never caught
  by hand because every manual summary printed throughout Stage 8
  development only inspected `train_woe`. Caught immediately by
  `test_no_null_scores_or_decisions` on the first real test run. Fixed by
  applying the mapping to both `train_woe` and `test_woe` explicitly, with
  an inline assertion guarding against recurrence.

### Corrected (documentation, not code)
- **The "46.1% automated approval rate" figure reported in v1.3 and in
  `00_README.md` was itself computed on the bugged, null-decision data**
  (pandas silently excludes NaN from `.mean()` denominators is NOT what
  happened here — rather, `str.startswith('Approve')` on a NaN returns
  False, so null-decision test rows were counted as "not approved,"
  deflating the reported rate). The CORRECT automated approval rate, after
  the null-decision fix above, is **65.97%** (Approve: 65.97%, Refer:
  23.99%, Decline: 10.04%) — which is the expected outcome given the risk
  bands are deliberately set at the 10th/30th/70th/90th score percentiles
  (i.e. ~70% of the population falls in an Approve-eligible band by
  construction). `00_README.md` and `06_deliverables/model_performance_report.md`
  updated to reflect the correct figure.

### Notes
- This is the second bug in this project caught only by checking a
  SPECIFIC SUBSET (the test set) that a human reviewer's summary
  statistics happened not to cover, rather than by a calculation being
  obviously wrong. It's the strongest argument in this project's history
  for why `tests/test_pipeline_outputs.py` exists: manual spot-checks are
  only as good as which subsets a person thinks to check.

---

## [v1.3] — Stage 10 completion & full pipeline hardening

### Added
- `src/run_pipeline.py` — orchestration script executing Stages 4-10 in
  dependency order with timing and pass/fail logging
- Excel analyst workbook (`04_excel/scorecard_summary.xlsx`) with live
  formulas (Portfolio Summary sheet recalculates from raw data, not
  hardcoded values)
- Power BI data model guide (star schema, DAX measures, dashboard spec)
- Final business output: `06_deliverables/final_scored_applications.csv`

### Fixed
- **Business logic error**: `approval_rate` was defined as `decision !=
  'Decline'`, which incorrectly counted "Refer to Manual Underwriting"
  applications as approvals (reported 92.8% approval). Corrected to count
  only explicit `Approve - *` decision categories. (Note: the specific
  "corrected" figure reported at this point in development, 46.1%, was
  itself still wrong due to an unrelated bug not yet discovered — see
  v1.4 below for the actual correct figure, 65.97%.)
- **Data lineage break**: `application_id` was dropped when WOE-transformed
  train/test dataframes were constructed in the logistic regression
  notebook (only the pandas index carried it, not an actual column). This
  broke the Stage 10 business-output merge two notebooks downstream.
  Fixed at the source — `application_id` is now an explicit column on
  `train_woe`/`test_woe` from the point they're created, and propagates
  through every downstream notebook and export.

---

## [v1.2] — Scorecard construction bug (Stage 8)

### Fixed
- **Critical: scorecard sign convention error.** The standard
  Offset + Factor x logit formula was applied directly to a model whose
  fitted `logit` was log-odds of Bad (since the model was fit with
  `bad_flag=1` as target), not log-odds of Good as the textbook formula
  assumes. This produced a scorecard that gave the HIGHEST points to the
  RISKIEST applicants — confirmed by the resulting risk bands showing bad
  rate INCREASING from "Decline" (0.10%) through "Premium" (9.7%), exactly
  backwards. Root-caused and fixed by introducing an explicit sign
  correction (`SIGN = -1`) applied consistently across base points,
  per-bin points, and the scoring function, plus a hard validation check
  (`credit_score` must correlate negatively with `bad_flag`) that halts
  notebook execution if the direction is ever wrong again.
- Fixed a `.values` read-only array bug in risk-band quantile edge
  computation (`band_edges = ....values.copy()`).

### Notes
- This bug was NOT caught by the points-vs-logit consistency check in the
  same notebook, because that check only confirms the points-based and
  logit-based scores agree with EACH OTHER, not that either one points the
  correct business direction. Internal consistency and correctness are
  different properties — both are checked separately from this version
  onward.

---

## [v1.1] — Model selection & multicollinearity fixes (Stage 7)

### Fixed
- **Incomplete multicollinearity handling.** The first version of the
  collinearity check only tested one anticipated variable pair
  (`total_existing_debt` vs `credit_utilization_pct`). It missed a much
  stronger pair — `defaults_on_file` and `months_since_last_delinquency`
  (r=0.89, mechanically linked since the latter is only defined when the
  former is nonzero) — which produced a wrong-signed coefficient in the
  full model. Replaced with a general scan across all candidate pairs
  above a 0.6 correlation threshold, resolving via comparison of
  standalone Information Value (Stage 6).
- **Naive variable selection.** Dropping every variable with p > 0.05 in a
  single pass (rather than one at a time) landed on a 2-variable model
  that discarded `employment_type` despite its real business rationale
  and reasonable standalone IV. Replaced with proper backward stepwise
  elimination (drop worst p-value, refit, repeat), which retained a more
  defensible 4-variable model.

### Changed
- Final model features: `bureau_credit_score`, `defaults_on_file`,
  `total_existing_debt`, `employment_type` (previously would have been
  just `bureau_credit_score` + `defaults_on_file` under the naive
  one-shot approach).

---

## [v1.0] — Synthetic data recalibration (Stage 6)

### Fixed
- **Critical: over-separated synthetic data.** Initial calibration made
  `bureau_credit_score` an almost-perfect proxy for true default risk
  (single-variable Information Value > 3.0 — real single-variable
  scorecard IVs rarely exceed ~0.5-0.8). Root cause: the observable bureau
  attributes and the underlying default hazard function were both
  deterministic functions of the identical latent risk variable in the
  data generator. Fixed by introducing an independent noise component to
  the hazard function's risk driver, decoupling "what the bureau can
  observe" from "true unobserved risk," then recalibrating the hazard
  magnitude via Monte Carlo simulation to land bureau score IV at a
  realistic ~0.27 and portfolio bad rate at ~3.5-3.6%.
- Re-ran WOE/binning (Stage 5) and IV (Stage 6) against the recalibrated
  data; re-fixed 3 of 5 newly-non-monotonic variables
  (`bureau_credit_score`, `employment_tenure_months`, `annual_income`) via
  targeted bin merges; left 4 genuinely weak/flat variables undistorted
  rather than force-fit.

---

## [v0.3] — Vintage analysis data integrity fixes (Stage 1-3)

### Fixed
- **Cumulative bad rate computed as decreasing between months** (a logical
  impossibility for a cumulative measure). Root cause: the performance
  panel generator stopped emitting rows for a loan the moment it
  defaulted, causing defaulted loans to silently vanish from both the
  numerator and denominator of later-MOB cumulative bad rate
  calculations. Fixed by having defaulted loans persist in the panel,
  frozen at Bad, through the full observation horizon.
- **Survivorship bias in vintage cohort denominators.** Loans that paid
  off at their contractual term also disappeared from the performance
  panel, shrinking cohort denominators unevenly across vintages (a
  vintage with many short-term loans lost members earlier than one with
  mostly long-term loans). Fixed by persisting paid-off loans too, frozen
  at Good/closed, through the full observation horizon.
- Added two permanent validation checks to `02_sql/05_vintage_analysis.sql`
  (cohort denominator constant per vintage; cumulative bad rate
  non-decreasing per vintage) so these bug classes are caught
  automatically on any future data regeneration.

### Changed
- **Performance window revised from 12 to 18 months**, based on the
  (corrected) vintage analysis: a 12-month window missed ~20-26% of
  eventual (24-month) bads; an 18-month window reduced that to ~4-6%,
  within a defensible maturity threshold. This is a methodology decision,
  not a bug fix — documented in `02_sql/04_merge_and_target.sql`.

---

## [v0.2] — Data quality fix (Stage 1)

### Fixed
- **Age generation bug.** `Faker.date_of_birth(minimum_age=18, ...)`
  guarantees age 18+ relative to the system clock at generation time, not
  relative to the project's own reference date (2024-01-01). ~289
  synthetic customers came out younger than 18 (as low as 15) when
  re-checked against the project reference date. Fixed by validating age
  explicitly against the project's reference date rather than trusting
  the library's internal "today."

---

## [v0.1] — Initial project scaffold

### Added
- Relational schema across 5 source tables (`customer_details`,
  `loan_applications`, `bureau_data`, `transactions`, `loan_performance`)
  with deliberately different grains — see `00_README.md` for the design
  rationale (application-level bureau snapshots to prevent temporal
  leakage; 1-customer-to-many-applications relationship).
- Synthetic data generator (`generate_data.py`) producing realistic,
  correlated risk signal rather than random noise.
- SQL Server DDL, bulk-insert, and data-quality-check scripts.
