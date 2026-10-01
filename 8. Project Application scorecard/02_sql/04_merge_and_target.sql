/* ============================================================================
   Script 04: Target Variable Creation (Good/Bad Flag)

   BUSINESS FRAMING
   -----------------
   A scorecard predicts the probability that a customer will become a "Bad"
   within some future window. Before we can model anything, we need to define,
   precisely and defensibly:

     1. WHAT COUNTS AS "BAD"?
        Industry standard: 90+ Days Past Due (90+ DPD) at any point during the
        performance window. This aligns with Basel/APRA default definitions
        (materiality + 90 days threshold) and is what MTB's Risk team would
        actually use.

     2. OBSERVATION WINDOW (a.k.a. "at time of application")
        The point at which we take a "snapshot" of the applicant's
        characteristics (bureau score, income, DTI, etc.) -- this is
        application_date. Everything we use as a MODEL FEATURE must be known
        AT or BEFORE this point. This is the #1 source of data leakage in
        scorecard projects: accidentally using information that wouldn't have
        been available yet at underwriting time.

     3. PERFORMANCE WINDOW -- 18 MONTHS (validated, not assumed)
        The forward-looking period during which we watch the loan to see if it
        goes 90+ DPD.

        IMPORTANT METHODOLOGY NOTE: a first-pass assumption of 12 months was
        tested using vintage/MOB curve analysis (see Script 05) BEFORE this
        target definition was finalized. That test showed a 12-month window
        still missed ~20% of eventual (24-month) bads -- the cumulative bad
        rate curve was still climbing steeply, not flattening, at MOB 12.
        Extending to 18 months brought that down to ~3-4% missed, which is
        within an acceptable maturity threshold. THIS IS THE CORRECT ORDER OF
        OPERATIONS FOR A REAL PROJECT: performance window is a measured,
        defensible choice validated against vintage curves -- not an
        assumption locked in before checking whether the data supports it.
        We are documenting the 12-month test explicitly here because a real
        model documentation / validation report would show this working, not
        hide it -- regulators and internal model validation teams expect to
        see that you tested your window assumption, not just asserted it.

     4. WHO IS "INDETERMINATE" / EXCLUDED?
        Applications with LESS than 18 months of performance history available
        (i.e., applied too recently relative to our SNAPSHOT_DATE of
        2025-09-30) cannot yet be labeled Good or Bad with confidence -- they
        haven't had the full window to season. These are EXCLUDED from the
        modeling dataset (not labeled "Good" by default -- that would bias
        the bad rate downward). This is a common real-world error: don't
        treat "hasn't defaulted YET" as the same as "Good."

   ============================================================================ */

USE MTB_ScorecardProject;
GO

/* ----------------------------------------------------------------------------
   STEP 1: For each application, find the WORST dpd_bucket reached within the
   first 18 months of the performance window, and how many months of
   performance history are actually observable given the snapshot date.
---------------------------------------------------------------------------- */
IF OBJECT_ID('dbo.vw_application_target', 'V') IS NOT NULL
    DROP VIEW dbo.vw_application_target;
GO

CREATE VIEW dbo.vw_application_target AS
WITH app_mob_available AS (
    SELECT
        application_id,
        application_date,
        DATEDIFF(MONTH, application_date, '2025-09-30') AS months_available
    FROM dbo.loan_applications
),
perf_within_window AS (
    -- worst dpd_bucket reached within the first 18 MOB only
    SELECT
        p.application_id,
        MAX(p.dpd_bucket) AS worst_dpd_bucket_18mob
    FROM dbo.loan_performance p
    WHERE p.mob <= 18
    GROUP BY p.application_id
)
SELECT
    a.application_id,
    a.application_date,
    a.months_available,
    p.worst_dpd_bucket_18mob,
    CASE
        WHEN a.months_available < 18 THEN 'Indeterminate - Insufficient Window'
        WHEN p.worst_dpd_bucket_18mob = 4 THEN 'Bad'
        WHEN p.worst_dpd_bucket_18mob IS NULL THEN 'Indeterminate - No Performance Data'
        ELSE 'Good'
    END AS good_bad_flag,
    CASE
        WHEN a.months_available >= 18 AND p.worst_dpd_bucket_18mob = 4 THEN 1
        WHEN a.months_available >= 18 AND p.worst_dpd_bucket_18mob < 4 THEN 0
        ELSE NULL  -- excluded from modeling
    END AS bad_flag
FROM app_mob_available a
LEFT JOIN perf_within_window p ON a.application_id = p.application_id;
GO

/* ----------------------------------------------------------------------------
   CHECKPOINT: target distribution
   Expected (validated against the actual dataset):
     Modeling population : ~5,578 applications
     Bad rate             : ~3.48%
     Indeterminate        : applications from ~2024-04 onward (< 18mo history
                             as of the 2025-09-30 snapshot)
---------------------------------------------------------------------------- */
SELECT good_bad_flag, COUNT(*) AS n, CAST(COUNT(*) AS FLOAT) / SUM(COUNT(*)) OVER() AS pct
FROM dbo.vw_application_target
GROUP BY good_bad_flag
ORDER BY n DESC;

SELECT
    SUM(bad_flag) AS total_bads,
    COUNT(bad_flag) AS total_modeling_population,
    CAST(SUM(bad_flag) AS FLOAT) / COUNT(bad_flag) AS bad_rate
FROM dbo.vw_application_target;

/* ----------------------------------------------------------------------------
   STEP 2: Build the full modeling dataset by joining application, customer,
   and bureau attributes -- for the MODELING POPULATION ONLY (bad_flag NOT NULL)
---------------------------------------------------------------------------- */
IF OBJECT_ID('dbo.vw_modeling_dataset', 'V') IS NOT NULL
    DROP VIEW dbo.vw_modeling_dataset;
GO

CREATE VIEW dbo.vw_modeling_dataset AS
SELECT
    la.application_id,
    la.customer_id,
    la.application_date,
    la.loan_purpose,
    la.loan_amount_requested,
    la.term_months,
    la.channel,
    cd.age_at_2024,
    cd.gender,
    cd.state,
    cd.employment_type,
    cd.employment_tenure_months,
    cd.annual_income,
    cd.residential_status,
    cd.dependents,
    bd.bureau_credit_score,
    bd.enquiries_last_6m,
    bd.active_credit_accounts,
    bd.defaults_on_file,
    bd.months_since_last_delinquency,
    bd.total_existing_debt,
    bd.credit_utilization_pct,
    bd.credit_file_age_months,
    t.bad_flag,
    t.good_bad_flag
FROM dbo.loan_applications la
INNER JOIN dbo.customer_details cd ON la.customer_id = cd.customer_id
INNER JOIN dbo.bureau_data bd ON la.application_id = bd.application_id
INNER JOIN dbo.vw_application_target t ON la.application_id = t.application_id
WHERE t.bad_flag IS NOT NULL;   -- exclude indeterminates from the modeling set
GO

SELECT COUNT(*) AS modeling_population_rows FROM dbo.vw_modeling_dataset;
SELECT AVG(CAST(bad_flag AS FLOAT)) AS overall_bad_rate FROM dbo.vw_modeling_dataset;

/* ============================================================================
   CHECKPOINT QUESTIONS (answer before moving to Script 05):

   1. Why do we compute bad_flag using dpd_bucket WITHIN THE FIRST 18 MOB only,
      rather than the worst dpd_bucket EVER reached (including beyond MOB 18)?
      What would go wrong if we used "worst ever" instead?

   2. A customer with 3 applications appears 3 times in vw_modeling_dataset --
      once per application, correctly. Could this customer have one
      application flagged Good and another flagged Bad? Is that a data error,
      or realistic? What does it imply for row independence in Stage 7's
      logistic regression?

   3. We excluded "Indeterminate" applications entirely rather than labeling
      them Good. A common mistake is to instead label anything that "hasn't
      defaulted yet" as Good. What would that do to our bad rate, and why is
      it wrong?

   4. This script assumes an 18-month window as settled fact. But we only
      arrived at "18 months" by testing 12 months first and finding it
      inadequate via vintage analysis (Script 05). In your own project work,
      would you build vintage analysis BEFORE or AFTER writing target
      definition SQL? Notice that in a real analysis you'd actually iterate
      between the two -- propose a window, vintage-test it, revise, retest.
   ============================================================================ */
