#!/usr/bin/env python3
"""
run_pipeline.py
Meridian Trust Bank -- Personal Loan Application Credit Scorecard

Orchestrates the full Stage 4-10 Python/Jupyter pipeline end-to-end and
writes a timestamped run log to /logs/. This is the same pattern a real
scheduled batch job (Airflow, cron, ADF, etc.) would follow: execute each
step in dependency order, capture pass/fail and timing per step, halt on
first failure rather than continuing with a broken upstream artifact, and
leave an audit trail behind.

Usage:
    python3 src/run_pipeline.py

Exit code 0 = full pipeline succeeded. Non-zero = a step failed; check the
log file for which one and why.
"""

import subprocess
import sys
import time
import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NOTEBOOKS_DIR = PROJECT_ROOT / "03_notebooks"
LOGS_DIR = PROJECT_ROOT / "logs"

# Pipeline steps in dependency order. Each depends on the previous step's
# output artifacts (see docs/data_lineage.md for the full dependency map).
PIPELINE_STEPS = [
    ("01_eda_cleaning.ipynb", "Data Cleaning & EDA"),
    ("02_woe_binning.ipynb", "WOE & Binning"),
    ("03_information_value.ipynb", "Information Value"),
    ("04_logistic_regression.ipynb", "Logistic Regression"),
    ("05_scorecard_build.ipynb", "Credit Scorecard Build"),
    ("06_validation.ipynb", "Model Validation & Performance"),
    ("07_business_output.ipynb", "Business Output"),
]


def run_step(notebook_name: str, step_label: str, log_lines: list) -> tuple[bool, float]:
    """Execute one notebook in-place via nbconvert. Returns (success, elapsed_seconds)."""
    notebook_path = NOTEBOOKS_DIR / notebook_name
    start = time.time()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    log_lines.append(f"[{timestamp}] START  {step_label} ({notebook_name})")

    result = subprocess.run(
        [
            "jupyter", "nbconvert", "--to", "notebook", "--execute",
            "--inplace", str(notebook_path),
            "--ExecutePreprocessor.timeout=600",
        ],
        cwd=str(NOTEBOOKS_DIR),
        capture_output=True,
        text=True,
    )

    elapsed = time.time() - start
    timestamp_end = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if result.returncode == 0:
        log_lines.append(f"[{timestamp_end}] SUCCESS {step_label} ({elapsed:.1f}s)")
        return True, elapsed
    else:
        log_lines.append(f"[{timestamp_end}] FAILED  {step_label} ({elapsed:.1f}s)")
        # Capture the last part of stderr -- usually where the actual Python
        # traceback lives -- so the log is actually useful for debugging,
        # not just a pass/fail flag.
        stderr_tail = result.stderr.strip().split("\n")[-15:]
        log_lines.append("  --- stderr tail ---")
        for line in stderr_tail:
            log_lines.append(f"  {line}")
        log_lines.append("  --- end stderr ---")
        return False, elapsed


def main():
    run_start = datetime.datetime.now()
    run_id = run_start.strftime("%Y%m%d_%H%M%S")
    log_file = LOGS_DIR / f"pipeline_run_{run_id}.log"

    log_lines = []
    log_lines.append("=" * 78)
    log_lines.append("MTB Personal Loan Scorecard -- Pipeline Run Log")
    log_lines.append(f"Run ID:     {run_id}")
    log_lines.append(f"Started:    {run_start.strftime('%Y-%m-%d %H:%M:%S')}")
    log_lines.append(f"Project:    {PROJECT_ROOT}")
    log_lines.append("=" * 78)
    log_lines.append("")

    results = []
    for notebook_name, step_label in PIPELINE_STEPS:
        success, elapsed = run_step(notebook_name, step_label, log_lines)
        results.append((step_label, success, elapsed))
        if not success:
            log_lines.append("")
            log_lines.append(f"PIPELINE HALTED at '{step_label}' -- downstream steps skipped.")
            break
        log_lines.append("")

    run_end = datetime.datetime.now()
    total_elapsed = (run_end - run_start).total_seconds()

    log_lines.append("=" * 78)
    log_lines.append("RUN SUMMARY")
    log_lines.append("=" * 78)
    for step_label, success, elapsed in results:
        status = "PASS" if success else "FAIL"
        log_lines.append(f"  [{status}] {step_label:<32s} {elapsed:>6.1f}s")

    overall_success = all(r[1] for r in results) and len(results) == len(PIPELINE_STEPS)
    log_lines.append("")
    log_lines.append(f"Total steps run:    {len(results)} / {len(PIPELINE_STEPS)}")
    log_lines.append(f"Total elapsed:      {total_elapsed:.1f}s")
    log_lines.append(f"Overall result:     {'SUCCESS' if overall_success else 'FAILURE'}")
    log_lines.append(f"Finished:           {run_end.strftime('%Y-%m-%d %H:%M:%S')}")
    log_lines.append("=" * 78)

    LOGS_DIR.mkdir(exist_ok=True)
    log_file.write_text("\n".join(log_lines) + "\n")

    # Also print to stdout so this behaves like a normal CLI tool when run
    # interactively, not just when scheduled.
    print("\n".join(log_lines))
    print(f"\nFull log written to: {log_file}")

    sys.exit(0 if overall_success else 1)


if __name__ == "__main__":
    main()
