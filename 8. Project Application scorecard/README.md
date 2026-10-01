# MTB Personal Loan Application Credit Scorecard

[![Pipeline](https://img.shields.io/badge/pipeline-passing-brightgreen)]()
[![Tests](https://img.shields.io/badge/tests-8%2F8%20passing-brightgreen)]()
[![Stage](https://img.shields.io/badge/stages-10%2F10%20complete-blue)]()

An end-to-end credit risk scorecard build for a fictional Australian retail
bank (**Meridian Trust Bank**), simulating the work of a Credit Risk Analyst
at a third-party analytics vendor. Full pipeline: **SQL Server -> Python
(Pandas/statsmodels) -> Excel -> Power BI**.

This file is the engineering/operational entry point (setup, structure, how
to run things). For the analytical methodology — what each of the 10 stages
does and why — see [`00_README.md`](00_README.md).

---

## Quick start

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. (Optional) Regenerate synthetic source data
python3 src/generate_data.py

# 3. Load into SQL Server (see 02_sql/ scripts, run in order 01 -> 05)
#    Requires a local/remote SQL Server instance + SSMS or sqlcmd

# 4. Run the full Python modeling pipeline (Stages 4-10)
python3 src/run_pipeline.py

# 5. Run automated smoke tests against the output
python3 -m pytest tests/ -v
```

A successful `run_pipeline.py` run writes a timestamped log to `logs/` and
exits 0. `pytest` should report 8/8 passing against a correctly-run
pipeline — see `tests/test_pipeline_outputs.py` for what's checked and why
each check exists (most map directly to a real bug documented in
`CHANGELOG.md`).

## Project structure

```
MTB_Personal_Loan_Scorecard/
├── README.md                    <- you are here (setup & structure)
├── 00_README.md                  <- methodology (what/why for each stage)
├── CHANGELOG.md                   <- full development history, bugs found & fixed
├── requirements.txt
│
├── config/
│   └── project_config.yaml       <- central reference for every tunable constant
│
├── src/
│   ├── generate_data.py          <- synthetic data generator
│   └── run_pipeline.py           <- orchestrates Stages 4-10, writes logs/
│
├── tests/
│   └── test_pipeline_outputs.py  <- automated smoke tests (8 checks)
│
├── logs/
│   └── pipeline_run_*.log        <- timestamped execution logs (auto-generated)
│
├── 01_data/
│   ├── raw_csv/                   <- synthetic source data + intermediate exports
│   ├── data_dictionary.xlsx
│   └── *.json / *.pkl             <- frozen bin specs, IV lookup, model artifacts
│
├── 02_sql/                        <- Scripts 01-05: schema through vintage analysis
├── 03_notebooks/                  <- Notebooks 01-07: EDA through business output
├── 04_excel/                      <- Analyst-facing workbook (live formulas)
├── 05_powerbi/                    <- Power BI data model & dashboard guide
├── 06_deliverables/                <- Final scored output, performance report,
│                                      workflow diagram, scorecard export
└── docs/
    └── architecture.md            <- system/infrastructure-level data flow
```

**Why two README files, not one:** `README.md` (this file) is what a new
engineer or analyst opens first to get the project running — setup,
structure, commands. `00_README.md` is the methodology write-up — the
credit risk reasoning behind every stage. Real bank model-development repos
almost always separate these, because the audiences and the update cadence
differ: this file changes when tooling changes; `00_README.md` changes when
the modeling approach changes.

## Requirements

- Python 3.10+
- SQL Server (2019+) or Azure SQL, with SSMS or `sqlcmd` for the `02_sql/`
  scripts (not required to run the Python pipeline standalone — Stage 4
  onward reads from CSV exports, not a live database connection)
- Power BI Desktop (optional — only needed to build the dashboard described
  in `05_powerbi/powerbi_data_model_guide.md`)

See `requirements.txt` for the full Python dependency list.

## Where to look for specific things

| I want to... | Go to |
|---|---|
| Understand the credit risk methodology stage-by-stage | `00_README.md` |
| **Get a plain-English explanation + step-by-step run guide (PDF)** | `06_deliverables/Project_Explainer_and_Run_Guide.pdf` |
| See what bugs were found and how they were fixed | `CHANGELOG.md` |
| Run the whole pipeline myself | `src/run_pipeline.py`, this file's Quick Start |
| Check whether the current output is trustworthy | `python3 -m pytest tests/ -v` |
| See the actual credit risk analysis, cell by cell | `03_notebooks/` |
| Get the final scored dataset | `06_deliverables/final_scored_applications.csv` |
| Understand the systems/infrastructure this simulates | `docs/architecture.md` |
| See a specific pipeline run's timing/success record | `logs/pipeline_run_*.log` |
| Present results to a non-technical stakeholder | `04_excel/scorecard_summary.xlsx` |
| Build the Power BI dashboard | `05_powerbi/powerbi_data_model_guide.md` |

## Known limitations

See `06_deliverables/model_performance_report.md` Section 6 for the full,
honest list (modest bad-event count, single train/test split, thin
top-band populations). This is a deliberately realistic, not-overstated
scorecard — Gini/KS both sit at the low end of the "acceptable" band, and
the project's own `CHANGELOG.md` documents multiple real bugs (including
two separate wrong "approval rate" figures during development) precisely
so the final numbers can be trusted rather than taken on faith.
