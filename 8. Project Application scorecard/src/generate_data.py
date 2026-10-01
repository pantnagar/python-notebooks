"""
Meridian Trust Bank (MTB) - Personal Loan Scorecard
Synthetic Data Generator

Design principles:
- customer_id and application_id are DIFFERENT grains (1 customer : many applications)
- Bureau data is snapshotted AT APPLICATION TIME (no leakage from future bureau pulls)
- Default risk is DRIVEN by real underlying factors (income, DTI, bureau delinquencies,
  employment tenure, existing defaults) so WOE/IV/logistic regression later actually
  finds real signal -- not noise.
- Applications span 2023-01 to 2024-12 so we have enough MOB history for vintage analysis
  as of a snapshot date of 2025-09-30 (giving the earliest vintage ~20 months on book).
"""

import numpy as np
import pandas as pd
from faker import Faker
import random

np.random.seed(42)
random.seed(42)
fake = Faker('en_AU')
Faker.seed(42)

N_CUSTOMERS = 6000
N_APPLICATIONS = 9000  # some customers apply more than once
SNAPSHOT_DATE = pd.Timestamp('2025-09-30')

# ---------------------------------------------------------------------------
# 1. CUSTOMER DETAILS
# ---------------------------------------------------------------------------
au_states = ['NSW', 'VIC', 'QLD', 'WA', 'SA', 'TAS', 'ACT', 'NT']
au_state_weights = [0.32, 0.26, 0.20, 0.11, 0.07, 0.02, 0.015, 0.005]

employment_types = ['Full-Time', 'Part-Time', 'Self-Employed', 'Casual', 'Unemployed']
employment_weights = [0.60, 0.14, 0.13, 0.10, 0.03]

residential_status = ['Owner', 'Mortgage', 'Renting', 'Living with Family']
residential_weights = [0.18, 0.32, 0.40, 0.10]

customers = []
for i in range(1, N_CUSTOMERS + 1):
    customer_id = f"CUST{i:06d}"
    # Enforce 18-75 AS OF our reference date (2024-01-01), not Faker's internal
    # "today" -- date_of_birth's minimum_age/maximum_age are relative to the
    # system clock at generation time, which caused a real bug here: ages
    # under 18 slipped through when checked against our project's reference date.
    dob = fake.date_of_birth(minimum_age=19, maximum_age=76)
    age = (pd.Timestamp('2024-01-01') - pd.Timestamp(dob)).days // 365
    while age < 18 or age > 75:
        dob = fake.date_of_birth(minimum_age=19, maximum_age=76)
        age = (pd.Timestamp('2024-01-01') - pd.Timestamp(dob)).days // 365
    state = np.random.choice(au_states, p=au_state_weights)
    employment = np.random.choice(employment_types, p=employment_weights)
    residential = np.random.choice(residential_status, p=residential_weights)

    # income correlated loosely with employment type & age
    base_income = {
        'Full-Time': 78000, 'Part-Time': 42000, 'Self-Employed': 68000,
        'Casual': 38000, 'Unemployed': 18000
    }[employment]
    income = max(15000, np.random.normal(base_income, base_income * 0.30))

    # employment tenure (months) - unemployed gets 0
    if employment == 'Unemployed':
        emp_tenure_months = 0
    else:
        emp_tenure_months = int(np.clip(np.random.exponential(36), 1, 480))

    customers.append({
        'customer_id': customer_id,
        'first_name': fake.first_name(),
        'last_name': fake.last_name(),
        'date_of_birth': dob,
        'age_at_2024': age,
        'gender': np.random.choice(['M', 'F'], p=[0.51, 0.49]),
        'state': state,
        'postcode': fake.postcode(),
        'employment_type': employment,
        'employment_tenure_months': emp_tenure_months,
        'annual_income': round(income, 2),
        'residential_status': residential,
        'dependents': np.random.choice([0, 1, 2, 3, 4], p=[0.35, 0.25, 0.22, 0.13, 0.05]),
        'customer_since': fake.date_between(start_date='-10y', end_date='-1y'),
    })

customer_df = pd.DataFrame(customers)

# ---------------------------------------------------------------------------
# 2. LOAN APPLICATIONS (grain of the whole project)
# ---------------------------------------------------------------------------
loan_purposes = ['Debt Consolidation', 'Car Purchase', 'Home Renovation',
                  'Wedding', 'Travel', 'Medical', 'Other']
loan_purpose_weights = [0.30, 0.22, 0.18, 0.08, 0.10, 0.06, 0.06]

# customer_ids with replacement so some customers apply multiple times (max 4 apps)
app_customer_pool = []
for cust in customer_df['customer_id']:
    n_apps = np.random.choice([1, 2, 3, 4], p=[0.72, 0.20, 0.06, 0.02])
    app_customer_pool.extend([cust] * n_apps)

random.shuffle(app_customer_pool)
app_customer_pool = app_customer_pool[:N_APPLICATIONS]
# top up if short
while len(app_customer_pool) < N_APPLICATIONS:
    app_customer_pool.append(np.random.choice(customer_df['customer_id']))

application_dates = pd.date_range('2023-01-01', '2024-12-31', freq='D')

applications = []
cust_lookup = customer_df.set_index('customer_id').to_dict('index')

for idx, cust_id in enumerate(app_customer_pool, start=1):
    application_id = f"APP{idx:06d}"
    app_date = np.random.choice(application_dates)
    app_date = pd.Timestamp(app_date)

    cust = cust_lookup[cust_id]
    loan_amount = round(np.random.uniform(2000, 50000) / 500) * 500
    term_months = int(np.random.choice([12, 24, 36, 48, 60], p=[0.10, 0.25, 0.30, 0.20, 0.15]))

    # interest rate: risk-based pricing proxy (not used as a model feature - just realism)
    interest_rate = round(np.random.uniform(7.5, 22.5), 2)

    applications.append({
        'application_id': application_id,
        'customer_id': cust_id,
        'application_date': app_date.date(),
        'loan_purpose': np.random.choice(loan_purposes, p=loan_purpose_weights),
        'loan_amount_requested': loan_amount,
        'term_months': term_months,
        'interest_rate_offered': interest_rate,
        'channel': np.random.choice(['Branch', 'Online', 'Broker'], p=[0.25, 0.50, 0.25]),
    })

app_df = pd.DataFrame(applications)

# ---------------------------------------------------------------------------
# 3. BUREAU DATA (snapshotted AT APPLICATION TIME - one row per application)
# ---------------------------------------------------------------------------
bureau_rows = []
app_lookup = app_df.set_index('application_id').to_dict('index')

for _, row in app_df.iterrows():
    app_id = row['application_id']
    cust_id = row['customer_id']
    cust = cust_lookup[cust_id]

    # Build a latent "true risk" factor per application (not stored) that drives
    # both bureau attributes AND the eventual default outcome -- this is what
    # creates REAL correlations for WOE/IV to discover later.
    risk_latent = np.random.normal(0, 1)

    # income and employment reduce latent risk; low tenure/income raise it
    income_z = (cust['annual_income'] - 55000) / 25000
    tenure_z = (cust['employment_tenure_months'] - 40) / 40
    risk_latent -= 0.35 * income_z
    risk_latent -= 0.25 * tenure_z
    if cust['employment_type'] == 'Unemployed':
        risk_latent += 1.2
    if cust['employment_type'] == 'Casual':
        risk_latent += 0.4
    if cust['residential_status'] == 'Renting':
        risk_latent += 0.15
    if cust['residential_status'] == 'Owner':
        risk_latent -= 0.2

    # store latent risk temporarily for use in performance simulation
    bureau_credit_score = int(np.clip(np.random.normal(700 - 60 * risk_latent, 55), 300, 900))

    n_enquiries_6m = int(np.clip(np.random.poisson(1.2 + max(0, risk_latent) * 1.5), 0, 15))
    n_active_accounts = int(np.clip(np.random.poisson(3 + max(0, -risk_latent)), 0, 20))
    n_defaults_on_file = int(np.clip(np.random.poisson(max(0, risk_latent - 0.5) * 0.8), 0, 6))
    total_existing_debt = round(max(0, np.random.normal(15000 + risk_latent * 8000, 9000)), 2)
    credit_utilization_pct = round(np.clip(np.random.normal(45 + risk_latent * 15, 20), 0, 100), 1)
    months_since_last_delinquency = (
        None if n_defaults_on_file == 0
        else int(np.clip(np.random.exponential(24), 1, 120))
    )
    file_age_months = int(np.clip(np.random.normal(96, 48), 3, 360))

    bureau_rows.append({
        'application_id': app_id,
        'bureau_credit_score': bureau_credit_score,
        'enquiries_last_6m': n_enquiries_6m,
        'active_credit_accounts': n_active_accounts,
        'defaults_on_file': n_defaults_on_file,
        'months_since_last_delinquency': months_since_last_delinquency,
        'total_existing_debt': total_existing_debt,
        'credit_utilization_pct': credit_utilization_pct,
        'credit_file_age_months': file_age_months,
        '_risk_latent': risk_latent,  # kept for performance simulation, dropped before CSV export
    })

bureau_df = pd.DataFrame(bureau_rows)

# ---------------------------------------------------------------------------
# 4. TRANSACTIONS (ongoing banking behavior - many rows per customer)
# ---------------------------------------------------------------------------
txn_categories = ['Salary Credit', 'Rent/Mortgage Debit', 'Retail Spend',
                   'Utility Bill', 'Loan Repayment', 'ATM Withdrawal', 'Other Debit']

transactions = []
txn_id = 1
for _, cust in customer_df.iterrows():
    cust_id = cust['customer_id']
    n_months = np.random.randint(6, 24)
    start = pd.Timestamp('2023-01-01') + pd.DateOffset(months=np.random.randint(0, 6))
    for m in range(n_months):
        month_date = start + pd.DateOffset(months=m)
        n_txns = np.random.randint(3, 9)
        for _ in range(n_txns):
            category = np.random.choice(txn_categories)
            if category == 'Salary Credit':
                amount = round(cust['annual_income'] / 12 * np.random.uniform(0.9, 1.0), 2)
            elif category == 'Rent/Mortgage Debit':
                amount = -round(np.random.uniform(800, 2800), 2)
            else:
                amount = -round(np.random.uniform(20, 600), 2)
            transactions.append({
                'transaction_id': f"TXN{txn_id:08d}",
                'customer_id': cust_id,
                'transaction_date': (month_date + pd.DateOffset(days=np.random.randint(0, 27))).date(),
                'category': category,
                'amount': amount,
            })
            txn_id += 1

txn_df = pd.DataFrame(transactions)

# ---------------------------------------------------------------------------
# 5. LOAN PERFORMANCE (monthly panel - one row per application per MOB)
#    This is what Stage 2 (target creation) and Stage 3 (vintage analysis) use.
# ---------------------------------------------------------------------------
perf_rows = []

for _, app in app_df.iterrows():
    app_id = app['application_id']
    app_date = pd.Timestamp(app['application_date'])
    term = app['term_months']
    # IMPORTANT CALIBRATION NOTE: the true default hazard is driven by a
    # PARTIALLY-OBSERVED version of risk_latent, not risk_latent directly.
    # In the first calibration pass, bureau attributes (score, utilization,
    # enquiries, etc.) AND the hazard function were both deterministic
    # functions of the exact same risk_latent value -- which made
    # bureau_credit_score an almost perfect proxy for true risk (IV values
    # came out at 1-3+, when real single-variable scorecard IVs are almost
    # never above ~0.5-0.8). Real bureau data is a NOISY signal of true
    # risk, not a perfect one -- the bureau can't see a customer's actual
    # financial stress, job security, or spending discipline, only proxies
    # for it. We fix this by adding independent noise to the hazard's risk
    # driver, so bureau attributes remain informative but genuinely
    # imperfect predictors, as they are in real underwriting.
    observed_risk = bureau_df.loc[bureau_df['application_id'] == app_id, '_risk_latent'].values[0]
    hazard_noise = np.random.normal(0, 1)  # unobserved risk component
    bureau_risk = 0.35 * observed_risk + 0.65 * hazard_noise

    # months on book available up to snapshot date -- NOTE: we no longer cap
    # this at `term`. A loan that pays off at its contractual term should
    # still appear (frozen, Good, closed) in the performance panel for every
    # MOB through months_available, exactly like a defaulted loan stays
    # frozen at Bad. Capping at term was the original bug that caused
    # cumulative vintage bad-rate denominators to shrink over time.
    months_available = (SNAPSHOT_DATE.year - app_date.year) * 12 + (SNAPSHOT_DATE.month - app_date.month)
    mob_max = months_available
    if mob_max < 1:
        continue  # too new, no performance history yet (excluded from modeling universe)

    # Convert latent risk to a monthly hazard of rolling to worse delinquency.
    # Real unsecured personal loan portfolios "front-load" risk: marginal
    # borrowers who were going to struggle tend to show distress within the
    # first 12-18 months, then the hazard tapers off (survivors have proven
    # themselves, and/or self-select into stable repayment behavior). We
    # model that with a hazard that DECAYS with MOB, rather than the
    # constant hazard used in the first pass -- which produced a vintage
    # curve still climbing steeply at MOB 30 with no clear maturity point.
    # decay_factor: hazard at MOB m = base_hazard * decay_factor^m
    # CALIBRATION NOTE: base_coef=0.14 was chosen via a standalone Monte
    # Carlo simulation of this exact hazard/decay logic (matching observed
    # 18mo bad rate ~3.2% and single-variable IV for bureau_credit_score
    # ~0.45, which lands in the "Strong" band -- a realistic value for the
    # single best predictor in a real scorecard, not the 1-3+ "suspiciously
    # strong" values the earlier fully-deterministic risk coupling produced.
    base_hazard = 0.14 * np.exp(0.75 * bureau_risk)
    decay_factor = 0.93   # hazard roughly halves every ~10 months
    dpd_bucket = 0  # 0=current, 1=1-29, 2=30-59, 3=60-89, 4=90+ (default)
    dpd_map = {0: 0, 1: 15, 2: 45, 3: 75, 4: 95}

    defaulted_mob = None
    write_off_balance = None
    paid_off_mob = None
    for mob in range(1, mob_max + 1):
        if defaulted_mob is not None:
            # Already defaulted (charged off) in a prior MOB -- keep appearing,
            # frozen at Bad, so cumulative vintage bad-rate denominators stay
            # correct at every later MOB (see note below on why this matters).
            current_dpd = dpd_map[4]
            balance = write_off_balance
        elif mob > term:
            # Loan has PAID OFF (reached its contractual term without ever
            # going 90+ DPD). It stops accruing balance/DPD activity, but we
            # STILL emit a frozen "Good, closed" row every month through
            # mob_max. This matters for vintage analysis: if we let paid-off
            # loans silently vanish from the performance panel, the cohort
            # denominator at later MOBs shrinks to only "still-open" loans --
            # which biases the cumulative bad rate (survivorship bias: closed
            # Good loans get invisibly dropped while defaulted loans, if not
            # persisted, would also vanish). Both must persist identically.
            current_dpd = 0
            balance = 0.0
            if paid_off_mob is None:
                paid_off_mob = mob
        else:
            # chance to roll forward one bucket, or cure (roll back) if mild delinquency
            current_hazard = base_hazard * (decay_factor ** mob)
            roll = np.random.random()
            if dpd_bucket < 4:
                if roll < current_hazard:
                    dpd_bucket += 1
                elif dpd_bucket > 0 and roll > 0.75:
                    dpd_bucket = max(0, dpd_bucket - 1)  # cure
            current_dpd = dpd_map[dpd_bucket]
            balance = round(max(0, app['loan_amount_requested'] * (1 - mob / term) *
                                 np.random.uniform(0.95, 1.05)), 2)

        perf_rows.append({
            'application_id': app_id,
            'mob': mob,
            'performance_date': (app_date + pd.DateOffset(months=mob)).date(),
            'dpd_bucket': dpd_bucket if defaulted_mob is None else 4,
            'current_dpd': current_dpd,
            'balance_outstanding': balance,
        })

        if dpd_bucket == 4 and defaulted_mob is None:
            defaulted_mob = mob
            write_off_balance = balance
            # NOTE: loop continues (no break) -- see comment above.

perf_df = pd.DataFrame(perf_rows)

# drop internal latent risk column before export
bureau_export = bureau_df.drop(columns=['_risk_latent'])

# ---------------------------------------------------------------------------
# EXPORT
# ---------------------------------------------------------------------------
out = '/home/claude/MTB_Personal_Loan_Scorecard/01_data/raw_csv'
customer_df.to_csv(f'{out}/customer_details.csv', index=False)
app_df.to_csv(f'{out}/loan_applications.csv', index=False)
bureau_export.to_csv(f'{out}/bureau_data.csv', index=False)
txn_df.to_csv(f'{out}/transactions.csv', index=False)
perf_df.to_csv(f'{out}/loan_performance.csv', index=False)

print("customer_details:", customer_df.shape)
print("loan_applications:", app_df.shape)
print("bureau_data:", bureau_export.shape)
print("transactions:", txn_df.shape)
print("loan_performance:", perf_df.shape)
print("\nApplications with at least 1 month performance history:", perf_df['application_id'].nunique())
print("Overall ever-90+DPD rate among apps with history:",
      round(perf_df.groupby('application_id')['dpd_bucket'].max().eq(4).mean() * 100, 2), "%")
