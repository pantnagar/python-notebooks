"""
tests/test_pipeline_outputs.py

Automated sanity checks on the final pipeline output. These are the same
checks that were done manually, by hand, throughout development (and that
caught every real bug documented in CHANGELOG.md) -- codified here so they
run automatically on every future pipeline execution instead of relying on
someone remembering to eyeball the numbers again.

Run with: pytest tests/test_pipeline_outputs.py -v
    (or: python3 -m pytest tests/ -v  from the project root)

This is NOT a full unit test suite for the modeling code (that would mean
testing individual functions inside each notebook, which is a larger
refactor). This is a SMOKE TEST layer: given the actual output files the
pipeline produces, are the business-critical properties true? This is
exactly the layer of testing that would have caught the Stage 8
sign-convention bug and the Stage 10 approval-rate bug immediately, rather
than requiring a human to notice bad rate climbing through "Premium."
"""

import pandas as pd
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FINAL_OUTPUT = PROJECT_ROOT / "06_deliverables" / "final_scored_applications.csv"

EXPECTED_ROW_COUNT = 5578
EXPECTED_BAD_RATE_RANGE = (0.02, 0.06)  # sanity band, not an exact match
BAND_ORDER = ["Decline", "High Risk - Refer", "Standard", "Preferred", "Premium"]


@pytest.fixture(scope="module")
def final_df():
    if not FINAL_OUTPUT.exists():
        pytest.skip(f"{FINAL_OUTPUT} not found -- run src/run_pipeline.py first")
    return pd.read_csv(FINAL_OUTPUT)


def test_row_count(final_df):
    """The modeling population should be stable at 5,578 applications
    (18-month performance window, applications through 2024-09-30 only)."""
    assert len(final_df) == EXPECTED_ROW_COUNT, (
        f"Expected {EXPECTED_ROW_COUNT} rows, got {len(final_df)}. "
        "If this changed, check whether the performance window, snapshot "
        "date, or random seed changed upstream."
    )


def test_bad_rate_in_realistic_range(final_df):
    """Portfolio bad rate should sit in a realistic band for an unsecured
    personal loan book. This is the check that would have caught the
    original over-separated synthetic data calibration (Changelog v1.0)
    if it had existed at the time."""
    bad_rate = final_df["bad_flag"].mean()
    lo, hi = EXPECTED_BAD_RATE_RANGE
    assert lo <= bad_rate <= hi, (
        f"Bad rate {bad_rate:.4f} is outside the realistic range [{lo}, {hi}]. "
        "A rate below this range may indicate a hazard-calibration issue in "
        "the data generator; a rate above may indicate a target-definition bug."
    )


def test_score_direction(final_df):
    """CRITICAL: credit_score must correlate NEGATIVELY with bad_flag --
    higher score = safer applicant. This is the exact check that would have
    caught the Stage 8 sign-convention bug (Changelog v1.2) automatically,
    instead of requiring a human to notice risk bands were inverted."""
    corr = final_df["credit_score"].corr(final_df["bad_flag"])
    assert corr < 0, (
        f"credit_score correlates POSITIVELY with bad_flag (r={corr:.4f}). "
        "This means higher scores are being assigned to RISKIER applicants -- "
        "a sign-convention bug in the scorecard construction. See CHANGELOG v1.2."
    )


def test_risk_bands_present_and_complete(final_df):
    """All five expected risk bands should be present, with no unexpected
    extra categories (e.g. from a bad merge or a typo in a decision map)."""
    actual_bands = set(final_df["risk_band"].dropna().unique())
    assert actual_bands == set(BAND_ORDER), (
        f"Risk bands mismatch. Expected {set(BAND_ORDER)}, got {actual_bands}."
    )


def test_bad_rate_monotonic_across_bulk_of_bands(final_df):
    """Bad rate should decrease monotonically across the first 4 risk bands
    (Decline -> Preferred). The 5th band (Premium) is deliberately excluded
    from this strict check -- it's a known, documented, thin-population
    exception (see CHANGELOG and Stage 8/9 notebooks): ~250 applications,
    only a handful of bad outcomes, so its rate is expected to be noisy.
    A full write-up of why this exception is acceptable, rather than a bug,
    lives in 03_notebooks/06_validation.ipynb section 9.4."""
    band_rates = final_df.groupby("risk_band", observed=True)["bad_flag"].mean()
    band_rates = band_rates.reindex(BAND_ORDER)
    checked_bands = band_rates.iloc[:4]  # Decline through Preferred
    assert checked_bands.is_monotonic_decreasing, (
        f"Bad rate is not monotonically decreasing across the first 4 risk "
        f"bands:\n{checked_bands}\nThis is NOT the known Premium-band "
        "exception -- investigate as a genuine regression."
    )


def test_approval_rate_excludes_refers(final_df):
    """Regression test for the Stage 10 approval-rate bug (Changelog v1.3):
    'approved' must mean an explicit Approve decision, never 'not Declined'
    (which would wrongly include Refer-to-manual-underwriting applications)."""
    approved = final_df["decision"].str.startswith("Approve")
    referred = final_df["decision"] == "Refer to Manual Underwriting"
    declined = final_df["decision"] == "Decline"

    assert (approved | referred | declined).all(), "Unexpected decision category found."
    assert not (approved & referred).any(), "A row is flagged as both Approved and Referred."

    approval_rate = approved.mean()
    assert 0.55 <= approval_rate <= 0.75, (
        f"Automated approval rate {approval_rate:.2%} is outside a plausible "
        "range for this risk-band structure (bands are set at the 10/30/70/90 "
        "score percentiles, so ~70% of applications fall in an Approve band "
        "by construction). If this is close to 90%+, the approval_rate "
        "calculation may have regressed to counting Refer applications as "
        "approvals again (see CHANGELOG v1.3)."
    )


def test_no_duplicate_applications(final_df):
    """Each application should appear exactly once in the final output --
    a duplicate would indicate a bad join somewhere in Stage 10."""
    assert final_df["application_id"].is_unique, (
        "Duplicate application_id values found in final output."
    )


def test_no_null_scores_or_decisions(final_df):
    """Every scored application must have a complete score, band, and
    decision -- a null here would indicate a broken join or an application
    that fell outside every risk band's quantile range."""
    for col in ["predicted_pd", "credit_score", "risk_band", "decision"]:
        n_null = final_df[col].isna().sum()
        assert n_null == 0, f"{n_null} null values found in '{col}'."


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
