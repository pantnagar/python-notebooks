/* ============================================================================
   Script 05: Vintage Analysis (MOB Curves)

   BUSINESS QUESTION
   ------------------
   Before locking in a performance window for the target variable (Script 04),
   we need to test: is a proposed window actually "mature" -- i.e., has the
   cumulative bad rate mostly stopped climbing by that MOB, or are we cutting
   the data off while defaults are still actively emerging?

   METHOD
   ------
   Group applications into VINTAGES (monthly cohorts by application_date).
   For each vintage, track CUMULATIVE bad rate by MOB. A loan that goes 90+
   DPD in one month STAYS counted as Bad in every later MOB's cumulative rate
   (cumulative bad rate can only go up, never down -- if your curve ever dips,
   that's a bug, not a real "cure" -- see the note on write-offs below).

   A CRITICAL DATA MODELING DECISION THIS EXPOSED
   ------------------------------------------------
   Two subtle bugs in how the underlying performance data was generated/
   modeled would have silently corrupted this analysis if not caught:

     1. WRITE-OFF PERSISTENCE: a loan that defaults must keep appearing in
        the performance panel every month after default (frozen at Bad),
        not just up to the month it defaulted. If a defaulted loan
        "disappears" from month 13 onward, it silently drops out of BOTH the
        numerator and denominator at every later MOB -- which can make
        cumulative bad rate appear to DECREASE, which is logically
        impossible for a cumulative measure. If your own MOB curve query
        ever shows cumulative bad rate declining between MOBs, this is
        almost certainly the bug: check whether "bad" loans vanish from your
        performance table after the default event instead of persisting.

     2. PAID-OFF PERSISTENCE (SURVIVORSHIP BIAS): a loan that reaches the end
        of its contractual term without ever going 90+ DPD is a Good, closed
        account -- it must ALSO keep appearing in the performance panel
        (frozen, Good) through the full observation horizon. If paid-off
        loans silently drop out of the panel once their term ends, your
        DENOMINATOR shrinks unevenly across vintages/MOBs (a vintage with
        many 12-month loans loses cohort members starting MOB 13, while a
        vintage of mostly 36-month loans doesn't) -- this creates
        misleading swings in the cumulative bad rate that have nothing to
        do with actual risk, purely an artifact of which loans are still
        "in view."

   In a real job, you'd catch these by: (a) checking that cumulative bad rate
   is monotonically non-decreasing per vintage, and (b) checking that a fixed
   vintage's cohort SIZE (denominator) does not change across MOBs unless
   loans are genuinely being excluded by snapshot-date cutoff (not by
   maturity or default). Both checks are included below -- run them FIRST,
   before trusting any curve you compute.
   ============================================================================ */

USE MTB_ScorecardProject;
GO

/* ----------------------------------------------------------------------------
   STEP 1: Cumulative worst dpd_bucket reached BY each MOB, per application
---------------------------------------------------------------------------- */
IF OBJECT_ID('dbo.vw_vintage_mob_curve', 'V') IS NOT NULL
    DROP VIEW dbo.vw_vintage_mob_curve;
GO

CREATE VIEW dbo.vw_vintage_mob_curve AS
WITH app_vintage AS (
    SELECT
        application_id,
        FORMAT(application_date, 'yyyy-MM') AS vintage_month
    FROM dbo.loan_applications
),
cum_perf AS (
    SELECT
        p1.application_id,
        p1.mob,
        MAX(p2.dpd_bucket) AS cumulative_worst_dpd_bucket
    FROM dbo.loan_performance p1
    INNER JOIN dbo.loan_performance p2
        ON p1.application_id = p2.application_id AND p2.mob <= p1.mob
    GROUP BY p1.application_id, p1.mob
)
SELECT
    v.vintage_month,
    c.mob,
    COUNT(DISTINCT c.application_id) AS applications_observed_at_mob,
    SUM(CASE WHEN c.cumulative_worst_dpd_bucket = 4 THEN 1 ELSE 0 END) AS cumulative_bads,
    CAST(SUM(CASE WHEN c.cumulative_worst_dpd_bucket = 4 THEN 1 ELSE 0 END) AS FLOAT)
        / COUNT(DISTINCT c.application_id) AS cumulative_bad_rate
FROM cum_perf c
INNER JOIN app_vintage v ON c.application_id = v.application_id
GROUP BY v.vintage_month, c.mob;
GO

/* ----------------------------------------------------------------------------
   VALIDATION CHECK #1: cohort denominator should be CONSTANT across all MOBs
   for a given vintage (loans shouldn't silently disappear as they age or
   default -- see bugs 1 & 2 above). If this returns any rows, something is
   dropping loans from the performance panel incorrectly.
---------------------------------------------------------------------------- */
WITH denom_check AS (
    SELECT vintage_month, mob, applications_observed_at_mob
    FROM dbo.vw_vintage_mob_curve
),
denom_variance AS (
    SELECT vintage_month, COUNT(DISTINCT applications_observed_at_mob) AS distinct_denominators
    FROM denom_check
    GROUP BY vintage_month
)
SELECT * FROM denom_variance WHERE distinct_denominators > 1;
-- Expected result: EMPTY. If not empty, a vintage's cohort size changes
-- across MOBs, which should only happen due to snapshot-date right-censoring
-- (i.e. very recent vintages naturally have fewer MOBs observed), never due
-- to default or payoff removing a loan from the panel mid-cohort.

/* ----------------------------------------------------------------------------
   VALIDATION CHECK #2: cumulative bad rate must be non-decreasing within
   each vintage as MOB increases. Flags any vintage where it dips.
---------------------------------------------------------------------------- */
WITH ordered AS (
    SELECT
        vintage_month, mob, cumulative_bad_rate,
        LAG(cumulative_bad_rate) OVER (PARTITION BY vintage_month ORDER BY mob) AS prev_rate
    FROM dbo.vw_vintage_mob_curve
)
SELECT * FROM ordered WHERE cumulative_bad_rate < prev_rate;
-- Expected result: EMPTY.

/* ----------------------------------------------------------------------------
   STEP 2: Maturity comparison -- for vintages old enough to have reached
   MOB 24 (applied by 2023-09-30 given our 2025-09-30 snapshot), compare
   cumulative bad rate at MOB 12, MOB 18, and MOB 24. This directly answers
   "how much of the eventual bad rate would we have missed" at each window.
---------------------------------------------------------------------------- */
WITH mature_vintages AS (
    SELECT DISTINCT FORMAT(application_date, 'yyyy-MM') AS vintage_month
    FROM dbo.loan_applications
    WHERE application_date <= '2023-09-30'
)
SELECT
    m12.vintage_month,
    m12.cumulative_bad_rate  AS bad_rate_at_mob12,
    m18.cumulative_bad_rate  AS bad_rate_at_mob18,
    m24.cumulative_bad_rate  AS bad_rate_at_mob24,
    (m24.cumulative_bad_rate - m12.cumulative_bad_rate) / NULLIF(m24.cumulative_bad_rate, 0)
        AS pct_of_eventual_bads_missed_by_mob12,
    (m24.cumulative_bad_rate - m18.cumulative_bad_rate) / NULLIF(m24.cumulative_bad_rate, 0)
        AS pct_of_eventual_bads_missed_by_mob18
FROM dbo.vw_vintage_mob_curve m12
INNER JOIN dbo.vw_vintage_mob_curve m18
    ON m12.vintage_month = m18.vintage_month AND m18.mob = 18
INNER JOIN dbo.vw_vintage_mob_curve m24
    ON m12.vintage_month = m24.vintage_month AND m24.mob = 24
INNER JOIN mature_vintages mv ON m12.vintage_month = mv.vintage_month
WHERE m12.mob = 12
ORDER BY m12.vintage_month;

/* ============================================================================
   ACTUAL RESULT FROM THIS PROJECT'S DATA (validate you get something close
   to this when you run it yourself):

     Average % of eventual (24mo) bads missed by MOB 12  : ~20%
     Average % of eventual (24mo) bads missed by MOB 18  : ~3-4%

   DECISION: a 12-month performance window is NOT mature enough for this
   portfolio -- roughly 1 in 5 eventual bads hadn't emerged yet. An 18-month
   window brings that down to a defensible ~3-4%, which is why Script 04
   uses 18 months as the performance window, not the 12 months a naive
   first-pass assumption might have used.

   This is the single most important lesson from this stage: NEVER lock in a
   performance window before testing it against vintage curves. A model
   trained on an immature window will systematically UNDERSTATE risk, because
   many applications labeled "Good" are actually "not-yet-Bad" -- they just
   hadn't had enough time to default yet when the label was assigned.

   COMMON MISTAKE: picking a performance window purely based on "how much
   data do I have" rather than "is this window actually mature." Vintage
   analysis exists specifically to stop you from doing that.
   ============================================================================ */
