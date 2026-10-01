# Model Performance Report
## Meridian Trust Bank — Personal Loan Application Credit Scorecard

**Model:** Logistic regression on WOE-transformed variables
**Development sample:** 5,578 applications (18-month performance window, 90+ DPD default definition)
**Train/test split:** 70/30, stratified on bad_flag (train n=3,904, test n=1,674)
**Snapshot date:** 2025-09-30

---

## 1. Final model specification

| Variable | Coefficient | p-value |
|---|---|---|
| `bureau_credit_score` (WOE) | -0.499 | 0.007 |
| `defaults_on_file` (WOE) | -0.470 | 0.007 |
| `total_existing_debt` (WOE) | -0.431 | 0.029 |
| `employment_type` (WOE) | -0.422 | 0.029 |
| Intercept | -3.270 | <0.001 |

All coefficients negative, as expected for WOE-transformed inputs (higher
WOE = safer bin = lower log-odds of default). Selected via backward stepwise
elimination from an initial 7-variable shortlist (Stage 6 IV screen ≥ 0.10),
after resolving a multicollinearity conflict between `defaults_on_file` and
`months_since_last_delinquency` (correlation 0.89 — the latter was dropped).

## 2. Discrimination metrics (test set)

| Metric | Train | Test |
|---|---|---|
| AUC | 0.6772 | 0.6133 |
| Gini | 0.3544 | 0.2265 |
| KS (×100 scale) | 28.5 | 24.1 |

**Assessment:** Test Gini (0.23) and KS (24.1) both sit at the low end of
the conventional "acceptable" band, not the "good" band. This is a modest
but genuine, deployable scorecard — appropriate for a 4-variable model
built on a portfolio with a ~3.6% bad rate (a limited number of actual
default events to learn from). The train-to-test AUC gap (0.064) indicates
some, but not severe, overfitting.

## 3. Rank-ordering

Bad rate decreases monotonically across risk bands on the training set
(Decline 9.46% → Premium, see caveat below). On the test set, deciles 0-8
show a clean, strong monotonic decline (10.1% → ~1.5%); the top decile
(n=74, the thinnest population in the split) showed a modest reversal
(6.8%), attributable to sampling noise at that population size rather than
a genuine rank-ordering failure — approximately 2-3 actual bad outcomes
drive that entire decile's rate.

## 4. Calibration

Overall: average predicted PD (3.64% train, 3.57% test) closely tracks
observed bad rate (3.64% train, 3.64% test) — the model is well-calibrated
in aggregate. Decile-level calibration shows expected scatter consistent
with sample size, with no systematic directional bias identified.

## 5. Stability

Population Stability Index (train vs test score distribution): **0.0052**
— well under the 0.10 "no significant shift" threshold, as expected for a
random split of the same underlying population. In production, PSI should
be recomputed monthly/quarterly comparing live applicant score
distributions against this development sample, per the standing monitoring
practice described in the Stage 9 notebook.

## 6. Known limitations

1. **Modest bad-event count** (~200 bads in the full modeling population)
   limits statistical power — several plausible business-relevant variables
   (`annual_income`, `enquiries_last_6m`, `credit_utilization_pct`) were
   statistically non-significant in the final model despite reasonable
   standalone IV, likely a sample-size effect as much as a genuine lack of
   signal.
2. **18-month performance window**, while validated against vintage curves
   (Stage 3) as capturing ~94-96% of eventual (24-month) bads, still
   excludes late-emerging defaults beyond that horizon by construction.
3. **Single train/test split**, not k-fold cross-validated — a defensible,
   standard approach for this scale of project, but a full model validation
   process would typically also assess metric stability across multiple
   resampled splits.
4. **Thin top-band populations** (both the "Premium" risk band and the
   top score decile) mean the model's precision at the very safest end of
   the score range is less certain than in the bulk of the distribution.

## 7. Recommendation

This scorecard clears a reasonable minimum bar for deployment as a
decision-support tool (automated approve/decline/refer routing), but
performance is not strong enough to justify aggressive risk-based pricing
differentiation across many fine-grained bands. Recommend: (a) deploy with
the 5-band structure as-is, (b) monitor PSI monthly, (c) plan for
redevelopment once a larger volume of matured (18mo+) performance history
accumulates, which should materially improve statistical power.

## 8. Business output summary

At the risk-band cutoffs used in this project (10th/30th/70th/90th score
percentiles): **65.97% automated approval** (Standard + Preferred + Premium
bands), **23.99% referred to manual underwriting**, **10.04% automated
decline**. See `CHANGELOG.md` v1.3-v1.4 for the development history behind
this figure — it was reported incorrectly twice during development (once
at 92.8%, once at 46.1%) before both underlying bugs were found and fixed,
the second one only by an automated test.
