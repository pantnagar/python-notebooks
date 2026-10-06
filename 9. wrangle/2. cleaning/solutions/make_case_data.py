"""Builds the 'crime scene': a deliberately dirty + messy loan-application extract, with a hidden answer key."""
import numpy as np, pandas as pd, json
from pathlib import Path
rng = np.random.default_rng(7)
OUT, SOL = Path("data"), Path("solutions_private"); OUT.mkdir(exist_ok=True); SOL.mkdir(exist_ok=True)
N_CUST, N_APP = 1000, 1400

FIRST = ["Olivia","Liam","Chloe","Noah","Mia","Jack","Ava","Lucas","Ruby","Ethan","Zoe","Mason","Ella","Oscar","Isla","Leo","Grace","Henry","Lily","Archie"]
LAST = ["Nguyen","Smith","Patel","Brown","Wilson","Taylor","Singh","Kelly","Chen","Evans","Walker","Murray","Hughes","Lee","Khan","Young"]
STATES = {"NSW":"New South Wales","VIC":"Victoria","QLD":"Queensland","WA":"Western Australia","SA":"South Australia","TAS":"Tasmania","ACT":"Australian Capital Territory","NT":"Northern Territory"}
EMP = ["Full-time","Part-time","Casual","Self-employed","Retired","Unemployed"]

# ---------- TRUTH ----------
cust = pd.DataFrame({
    "customer_id": [f"CUS-{i+1:04d}" for i in range(N_CUST)],
    "customer_name": [f"{rng.choice(FIRST)} {rng.choice(LAST)}" for _ in range(N_CUST)],
    "state": rng.choice(list(STATES), N_CUST, p=[.32,.26,.20,.10,.06,.02,.02,.02]),
})
age0 = rng.integers(21, 70, N_CUST)
cust["dob"] = pd.Timestamp("2024-01-01") - pd.to_timedelta((age0*365.25 + rng.integers(0, 364, N_CUST)).astype(int), unit="D")

cid = np.concatenate([rng.permutation(N_CUST), rng.choice(N_CUST, N_APP - N_CUST)])
apps = pd.DataFrame({"app_id": [f"APP-{i+1:04d}" for i in range(N_APP)], "customer_id": [cust.customer_id[i] for i in cid]})
apps["application_date"] = pd.Timestamp("2023-01-01") + pd.to_timedelta(rng.integers(0, 911, N_APP), unit="D")
apps["product"] = rng.choice(["Credit Card","Personal Loan"], N_APP, p=[.6,.4])
card = apps["product"] == "Credit Card"
apps["requested_amount"] = np.where(card, rng.choice([2000,5000,8000,10000,15000,25000], N_APP),
                                    (rng.integers(10, 101, N_APP) * 500))
apps["approved_amount"] = (apps.requested_amount * rng.choice([1,1,1,.9,.8,.7,.5], N_APP) / 100).round() * 100
apps["term_months"] = np.where(card, np.nan, rng.choice([12,24,36,48,60], N_APP))
apps["employment_status"] = rng.choice(EMP, N_APP, p=[.5,.15,.1,.12,.08,.05])
apps["annual_income"] = np.clip(np.round(rng.lognormal(11.0, .45, N_APP), -2), 15000, 600000)
apps["bureau_score"] = np.clip(rng.normal(680, 90, N_APP), 300, 900).round().astype(int)

dpd = np.zeros((N_APP, 6), dtype=int)
p_def = 1/(1+np.exp(2.0 + 0.008*(apps.bureau_score.values-680)))
for i in range(N_APP):
    if rng.random() < p_def[i]:
        j = rng.integers(0, 4)
        for t in range(j, 6): dpd[i, t] = min(30*(t-j+1), 180)
    elif rng.random() < .25:
        j = rng.integers(0, 6); dpd[i, j] = 30
        if j < 5 and rng.random() < .4: dpd[i, j+1] = 60
for k in range(6): apps[f"dpd_m{k+1}"] = dpd[:, k]
apps["default_flag"] = (dpd.max(axis=1) >= 90).astype(int)
m = apps.merge(cust, on="customer_id")
def age_at(app_date, dob):
    return (app_date.dt.year - dob.dt.year) - (((app_date.dt.month < dob.dt.month) | ((app_date.dt.month == dob.dt.month) & (app_date.dt.day < dob.dt.day))).astype(int))
apps["age"] = age_at(apps.application_date, m.dob)
assert apps.age.min() >= 18

# ---------- RAW (all text) ----------
raw = pd.DataFrame({"app_id": apps.app_id, "customer_id": apps.customer_id})
raw["applicant_info"] = [f"{n} | {d:%Y-%m-%d}" for n, d in zip(m.customer_name, m.dob)]
fmt_choice = rng.choice(["iso","dmy","dmon"], N_APP, p=[.7,.2,.1])
raw["application_date"] = [d.strftime({"iso":"%Y-%m-%d","dmy":"%d/%m/%Y","dmon":"%d %b %Y"}[f]) for d, f in zip(apps.application_date, fmt_choice)]
raw["age"] = apps.age.astype(str)
sv = []
for s in m.state:
    r = rng.random(); sv.append(s if r < .55 else s.lower() if r < .70 else STATES[s] if r < .90 else STATES[s].upper())
raw["state"] = sv
pmap = {"Credit Card": ["Credit Card","credit card","CC","CREDIT CARD"], "Personal Loan": ["Personal Loan","personal loan","P. Loan","PL"]}
raw["product"] = [rng.choice(pmap[p], p=[.7,.12,.10,.08]) for p in apps["product"]]
ev = []
for e in apps.employment_status:
    r = rng.random(); ev.append(e if r < .85 else e.lower() if r < .92 else e.upper() if r < .96 else f"  {e} ")
raw["employment_status"] = ev
raw["annual_income"] = apps.annual_income.astype(int).astype(str)
raw["requested_amount"] = apps.requested_amount.astype(int).astype(str)
raw["approved_amount"] = apps.approved_amount.astype(int).astype(str)
tv = []
for t in apps.term_months:
    if np.isnan(t): tv.append("")
    else:
        t = int(t); r = rng.random()
        tv.append(f"{t} months" if r < .6 else f"{t} mths" if r < .85 or t % 12 else f"{t//12} yrs")
raw["term"] = tv
raw["bureau_score"] = apps.bureau_score.astype(str)
for k in range(6): raw[f"dpd_m{k+1}"] = apps[f"dpd_m{k+1}"].astype(str)
dv = []
for d in apps.default_flag:
    dv.append(str(d) if rng.random() > .08 else ("Y" if d else "N"))
raw["default_flag"] = dv

# ---------- INJECT DEFECTS (disjoint row pools) ----------
key, used = {}, set()
def pool(n, name):
    avail = [i for i in rng.permutation(N_APP) if i not in used][:n]
    used.update(avail); key[name] = len(avail); return np.array(avail)
# income
idx = pool(56, "income_blank");      raw.loc[idx, "annual_income"] = ""
idx = pool(14, "income_na");         raw.loc[idx, "annual_income"] = "N/A"
idx = pool(14, "income_unknown");    raw.loc[idx, "annual_income"] = "unknown"
idx = pool(14, "income_zero");       raw.loc[idx, "annual_income"] = "0"
idx = pool(14, "income_minus1");     raw.loc[idx, "annual_income"] = "-1"
idx = pool(28, "income_k_string");   raw.loc[idx, "annual_income"] = [f"{int(apps.annual_income[i]/1000)}k" for i in idx]
idx = pool(42, "income_dollar_str"); raw.loc[idx, "annual_income"] = [f"${int(apps.annual_income[i]):,}" for i in idx]
idx = pool(30, "income_in_thousands"); raw.loc[idx, "annual_income"] = [f"{apps.annual_income[i]/1000:.1f}" for i in idx]
# bureau score
idx = pool(42, "score_na");       raw.loc[idx, "bureau_score"] = "N/A"
idx = pool(20, "score_9999");     raw.loc[idx, "bureau_score"] = "9999"
idx = pool(15, "score_zero");     raw.loc[idx, "bureau_score"] = "0"
idx = pool(8,  "score_out_of_range"); raw.loc[idx, "bureau_score"] = rng.choice(["1000","1200","150","250"], len(idx))
# dates
idx = pool(12, "date_impossible")
bad = []
for i in idx:
    y = int(rng.choice([2023, 2024, 2025])); f = rng.choice(["iso","dmy"])
    mo, d = rng.choice([(2,30),(2,31),(4,31),(6,31),(9,31),(11,31)])
    bad.append(f"{y}-{mo:02d}-{d:02d}" if f == "iso" else f"{d:02d}/{mo:02d}/{y}")
raw.loc[idx, "application_date"] = bad
idx = pool(8, "date_out_of_range"); raw.loc[idx, "application_date"] = ["2087-03-15","2099-12-01","1923-07-01","2031-05-20","2087-11-09","1999-01-01","2050-08-08","1901-02-03"]
# age / approved / default accuracy defects
idx = pool(30, "age_mismatch")
raw.loc[idx, "age"] = [str(int(apps.age[i]) + int(rng.choice([-1,1])*rng.integers(3, 16))) for i in idx]
idx = pool(35, "approved_gt_requested")
raw.loc[idx, "approved_amount"] = [str(int(round(apps.requested_amount[i]*rng.uniform(1.3, 2.0), -2))) for i in idx]
idx = pool(25, "default_conflict")
for i in idx:
    cur = 1 if apps.default_flag[i] else 0; new = 1 - cur
    old = raw.at[i, "default_flag"]
    raw.at[i, "default_flag"] = ("Y" if new else "N") if old in ("Y","N") else str(new)
# employment
idx = pool(25, "employment_garbled")
GARBLE = str.maketrans({"l":"1","i":"1","o":"0"})
raw.loc[idx, "employment_status"] = [apps.employment_status[i].translate(GARBLE) for i in idx]
idx = pool(18, "employment_blank");   raw.loc[idx, "employment_status"] = ""
idx = pool(14, "employment_unknown"); raw.loc[idx, "employment_status"] = "unknown"
idx = pool(10, "employment_na");      raw.loc[idx, "employment_status"] = "N/A"

# ---------- DUPLICATES (from rows that carry no injected defect) ----------
clean_rows = [i for i in range(N_APP) if i not in used]
src = rng.choice(clean_rows, 65, replace=False)
exact = raw.loc[src[:40]].copy()
near = raw.loc[src[40:]].copy()
near["app_id"] = [rng.choice([f" {a}", f"{a} ", a.lower()]) for a in near.app_id]
near["product"] = near["product"].str.upper()
key["exact_duplicates"], key["near_duplicates_extra"] = 40, 25
raw_all = pd.concat([raw, exact, near], ignore_index=True).sample(frac=1, random_state=3).reset_index(drop=True)

# ---------- WRITE ----------
raw_all.to_csv(OUT/"loan_applications_raw.csv", index=False)
raw_all.to_excel(OUT/"loan_applications_raw.xlsx", index=False, sheet_name="applications")
dd = pd.DataFrame([
 ["app_id","Unique application ID, format APP-####","text","unique; matches ^APP-\\d{4}$"],
 ["customer_id","Customer ID, format CUS-####. A customer can have several applications","text","matches ^CUS-\\d{4}$"],
 ["applicant_info","Applicant name and date of birth","text","name | YYYY-MM-DD"],
 ["application_date","Date the application was lodged","date","between 2023-01-01 and 2025-06-30"],
 ["age","Applicant age in whole years on the application date","integer","18-100; must agree with dob and application_date"],
 ["state","Applicant's Australian state/territory","category","one of NSW, VIC, QLD, WA, SA, TAS, ACT, NT"],
 ["product","Product applied for","category","Credit Card | Personal Loan"],
 ["employment_status","Employment status at application","category","Full-time, Part-time, Casual, Self-employed, Retired, Unemployed (or Unknown if not provided)"],
 ["annual_income","Gross annual income, AUD, per year","number","> 0 (blank/0/-1 are NOT valid values: they mean 'not provided')"],
 ["requested_amount","Limit or loan amount requested, AUD","number","> 0"],
 ["approved_amount","Limit or loan amount approved, AUD","number","> 0 and <= requested_amount"],
 ["term","Loan term. Not applicable to credit cards","text","loans only; stored as months in clean data (term_months)"],
 ["bureau_score","Credit bureau score at application","integer","300-900"],
 ["dpd_m1 ... dpd_m6","Days past due in months-on-book 1 to 6","integer","0 or more"],
 ["default_flag","Default indicator","0/1","1 if ANY dpd_m1..dpd_m6 >= 90, else 0"],
], columns=["column","description","type","rule"])
dd.to_csv(OUT/"data_dictionary.csv", index=False)

apps.to_csv(SOL/"truth_applications.csv", index=False); cust.to_csv(SOL/"truth_customers.csv", index=False)
key.update({"raw_rows": len(raw_all), "clean_apps": N_APP, "clean_customers": N_CUST, "clean_perf_rows": N_APP*6,
            "income_missing_any": key["income_blank"]+key["income_na"]+key["income_unknown"]+key["income_zero"]+key["income_minus1"],
            "income_placeholder_nonpositive": key["income_zero"]+key["income_minus1"],
            "score_invalid_numeric": key["score_9999"]+key["score_zero"]+key["score_out_of_range"],
            "score_missing_total": key["score_na"]+key["score_9999"]+key["score_zero"]+key["score_out_of_range"],
            "bad_dates": key["date_impossible"]+key["date_out_of_range"]})
json.dump(key, open(SOL/"answer_key.json","w"), indent=1)
print(json.dumps(key, indent=1)); print(raw_all.shape)
