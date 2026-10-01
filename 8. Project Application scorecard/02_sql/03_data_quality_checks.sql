/* ============================================================================
   Script 03: Data Quality Checks

   This is the step most beginners skip and most real analysts don't.
   Before ANY modeling, you validate:
     a) Referential integrity (do FKs actually resolve?)
     b) Uniqueness of grain (is the PK actually unique / no duplicate rows?)
     c) Null/missing patterns (expected vs unexpected nulls)
     d) Range/sanity checks (impossible values -- negative income, DPD > 999, etc.)
     e) Duplicate records
   ============================================================================ */

USE MTB_ScorecardProject;
GO

-- ============================================================================
-- A. REFERENTIAL INTEGRITY
-- ============================================================================

-- A1. Any applications pointing to a customer_id that doesn't exist?
--     (Should be 0 -- FK constraint would have blocked the load if not, but
--      confirm explicitly; this is the query you'd run on a system WITHOUT
--      enforced FKs, which is common in real staging/lake environments.)
SELECT COUNT(*) AS orphaned_applications
FROM dbo.loan_applications la
LEFT JOIN dbo.customer_details cd ON la.customer_id = cd.customer_id
WHERE cd.customer_id IS NULL;

-- A2. Any bureau_data rows without a matching application?
SELECT COUNT(*) AS orphaned_bureau_rows
FROM dbo.bureau_data bd
LEFT JOIN dbo.loan_applications la ON bd.application_id = la.application_id
WHERE la.application_id IS NULL;

-- A3. Every application should have EXACTLY ONE bureau row (1:1 relationship).
--     Flag any application with 0 or 2+ bureau rows.
SELECT la.application_id, COUNT(bd.application_id) AS bureau_row_count
FROM dbo.loan_applications la
LEFT JOIN dbo.bureau_data bd ON la.application_id = bd.application_id
GROUP BY la.application_id
HAVING COUNT(bd.application_id) <> 1;

-- ============================================================================
-- B. UNIQUENESS OF GRAIN
-- ============================================================================

-- B1. customer_details: customer_id should be unique (PK already enforces this,
--     but this is the pattern you'd use on a table without a PK constraint)
SELECT customer_id, COUNT(*) AS n
FROM dbo.customer_details
GROUP BY customer_id
HAVING COUNT(*) > 1;

-- B2. loan_performance: grain is (application_id, mob) -- confirm no duplicates
SELECT application_id, mob, COUNT(*) AS n
FROM dbo.loan_performance
GROUP BY application_id, mob
HAVING COUNT(*) > 1;

-- ============================================================================
-- C. NULL / MISSING VALUE PATTERNS
-- ============================================================================

-- C1. Null counts across bureau_data (months_since_last_delinquency is EXPECTED
--     to be null when defaults_on_file = 0 -- confirm that's the only pattern)
SELECT
    SUM(CASE WHEN bureau_credit_score IS NULL THEN 1 ELSE 0 END) AS null_score,
    SUM(CASE WHEN enquiries_last_6m IS NULL THEN 1 ELSE 0 END) AS null_enquiries,
    SUM(CASE WHEN defaults_on_file IS NULL THEN 1 ELSE 0 END) AS null_defaults,
    SUM(CASE WHEN months_since_last_delinquency IS NULL THEN 1 ELSE 0 END) AS null_months_since_delinq,
    SUM(CASE WHEN total_existing_debt IS NULL THEN 1 ELSE 0 END) AS null_debt
FROM dbo.bureau_data;

-- C2. Confirm months_since_last_delinquency is null ONLY when defaults_on_file = 0
--     (if this returns rows, we have an inconsistent/broken data generation assumption)
SELECT COUNT(*) AS inconsistent_rows
FROM dbo.bureau_data
WHERE (defaults_on_file = 0 AND months_since_last_delinquency IS NOT NULL)
   OR (defaults_on_file > 0 AND months_since_last_delinquency IS NULL);

-- C3. Null income or employment on customer_details?
SELECT
    SUM(CASE WHEN annual_income IS NULL THEN 1 ELSE 0 END) AS null_income,
    SUM(CASE WHEN employment_type IS NULL THEN 1 ELSE 0 END) AS null_employment
FROM dbo.customer_details;

-- ============================================================================
-- D. RANGE / SANITY CHECKS
--    (This is where you'd catch real-world garbage: negative ages, DPD of 9999,
--     income of $0, dates in the future, etc.)
-- ============================================================================

-- D1. Age sanity (should be 18-100 for a lending population)
SELECT MIN(age_at_2024) AS min_age, MAX(age_at_2024) AS max_age
FROM dbo.customer_details;

-- D2. Income sanity (should be > 0, and check for implausible outliers)
SELECT MIN(annual_income) AS min_income, MAX(annual_income) AS max_income,
       AVG(annual_income) AS avg_income
FROM dbo.customer_details;

-- D3. Bureau credit score should be in a sane range (we generated 300-900 AU-style)
SELECT MIN(bureau_credit_score) AS min_score, MAX(bureau_credit_score) AS max_score
FROM dbo.bureau_data;

-- D4. Application dates should all fall within our known generation window
SELECT MIN(application_date) AS earliest_app, MAX(application_date) AS latest_app
FROM dbo.loan_applications;

-- D5. DPD bucket should only be 0-4
SELECT DISTINCT dpd_bucket FROM dbo.loan_performance ORDER BY dpd_bucket;

-- D6. current_dpd should be non-negative and consistent with dpd_bucket
SELECT dpd_bucket, MIN(current_dpd) AS min_dpd, MAX(current_dpd) AS max_dpd
FROM dbo.loan_performance
GROUP BY dpd_bucket
ORDER BY dpd_bucket;

-- D7. loan_amount_requested should be positive and within a believable personal
--     loan range (we generated $2,000-$50,000)
SELECT MIN(loan_amount_requested) AS min_amt, MAX(loan_amount_requested) AS max_amt
FROM dbo.loan_applications;

-- ============================================================================
-- E. CUSTOMER -> APPLICATION CARDINALITY CHECK
--    Confirms our 1:many design actually produced multi-application customers
--    (this is a good checkpoint question -- see notes in 00_README.md)
-- ============================================================================
SELECT applications_per_customer, COUNT(*) AS n_customers
FROM (
    SELECT customer_id, COUNT(*) AS applications_per_customer
    FROM dbo.loan_applications
    GROUP BY customer_id
) t
GROUP BY applications_per_customer
ORDER BY applications_per_customer;

/* ============================================================================
   CHECKPOINT QUESTIONS (answer before moving to Script 04):

   1. Did any of the referential integrity checks (Section A) return non-zero
      rows? If so, what would that mean about how the FK constraints were
      enforced (or not) during the BULK INSERT?

   2. Section C2 checks a business RULE, not just a null count. Why is checking
      "is null only where it should be null" a more useful QA step than just
      counting nulls?

   3. Look at Section E's output. What does the distribution of
      applications-per-customer tell you about how you'll need to think about
      independence between rows when you get to modeling in Stage 7? (Hint:
      logistic regression assumes each row is an independent observation --
      is that strictly true here?)
   ============================================================================ */
