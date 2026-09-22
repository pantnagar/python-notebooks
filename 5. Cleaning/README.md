# Meridian National Bank (MNB) — Synthetic Credit Card Risk Portfolio

Synthetic data for learning purposes only. No real customer data.

## Tables

| File | Format | Grain | Rows (approx) | Notes |
|---|---|---|---|---|
| customers.csv | CSV | 1 row per customer | ~2,540 | Contains duplicates, near-duplicates, missing values, invalid IDs, inconsistent categories |
| accounts.csv | CSV | 1 row per credit card account | ~3,690 | FK -> customers.customer_id; contains orphan FKs, duplicate account_ids |
| monthly_performance.csv | CSV | 1 row per account per month (Oct 2024 - Sep 2025) | ~44,000 | FK -> accounts.account_id; large table, some duplicate grain violations |
| payments.txt | Pipe-delimited TXT | 1 row per payment event | ~29,700 | FK -> accounts.account_id; some orphan FKs, some negative amounts |
| bureau_data.json | Nested JSON | 1 record per customer (subset) | ~2,325 | Schema drift on a few records, nested public_records/collections_accounts |
| applications.xlsx | Excel (3 sheets) | 1 row per application | ~606 | Sheets: Applications, Decision_Codes, Branch_Reference |
| branch_lookup.txt | Pipe-delimited TXT | 1 row per branch | 12 | Reference/lookup table |
| customers_dup_source.csv | CSV | 1 row per customer (partial, second source) | ~885 | "Second system" extract for merge/integrity practice — conflicting values vs customers.csv |
| mnb_portfolio.db | SQLite | Relational | — | Contains customers, accounts, monthly_performance, payments, branches as tables |

## Important

These datasets contain **intentional, realistic data-quality problems** (missing values,
duplicates, invalid values, inconsistent formatting, referential integrity issues).
This is by design — the exercises in the workbook and notebook ask you to find and
handle these problems yourself. Do not assume the data is clean.
