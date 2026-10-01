# System Architecture & Data Flow
## Meridian Trust Bank — Personal Loan Application Credit Scorecard

This diagram shows the project at **infrastructure/systems level** — which
environments, tools, and storage layers data moves through — as distinct
from `06_deliverables/workflow_diagram.md`, which shows the **analytical
methodology** (Stage 1 through Stage 10). A platform or data engineering
team would draw this diagram; a risk analyst would draw the other one.

```mermaid
flowchart LR
    subgraph SRC["Source Systems (simulated)"]
        direction TB
        S1[Origination Platform<br/>loan_applications]
        S2[Bureau Feed<br/>bureau_data]
        S3[Core Banking<br/>customer_details,<br/>transactions]
        S4[Loan Servicing<br/>loan_performance]
    end

    subgraph STAGE["Staging / Warehouse"]
        direction TB
        DB[(SQL Server<br/>MTB_ScorecardProject)]
        V1[/vw_application_target/]
        V2[/vw_modeling_dataset/]
        V3[/vw_vintage_mob_curve/]
    end

    subgraph DEV["Model Development Environment"]
        direction TB
        NB[Jupyter Notebooks<br/>01-07]
        ART[(Model Artifacts<br/>JSON / PKL /<br/>frozen WOE bins)]
    end

    subgraph CONSUME["Consumption Layer"]
        direction TB
        XL[Excel<br/>Analyst Workbook]
        PBI[Power BI<br/>Portfolio Dashboard]
        OUT[final_scored_applications.csv<br/>Underwriting-ready output]
    end

    S1 --> DB
    S2 --> DB
    S3 --> DB
    S4 --> DB
    DB --> V1 --> V2
    DB --> V3
    V2 -->|CSV export| NB
    NB --> ART
    ART --> NB
    NB --> OUT
    OUT --> XL
    OUT --> PBI
    DB -.->|direct connection,<br/>vintage/MOB trend data| PBI

    style SRC fill:#E7E6E6,stroke:#666
    style STAGE fill:#DEEBF7,stroke:#1F4E78
    style DEV fill:#FCE4D6,stroke:#C00000
    style CONSUME fill:#E2EFDA,stroke:#548235
```

## Environment boundaries and why they matter

| Boundary | What crosses it | Why it's a real boundary, not just a folder |
|---|---|---|
| **Source Systems -> SQL Server** | Raw CSVs, loaded via `BULK INSERT` (Script 02) | In production this would be a scheduled ETL/ELT job (e.g. ADF, Fivetran, dbt), not a manual file copy -- the CSV-and-BULK-INSERT pattern here stands in for that, and is exactly the kind of thing you'd replace with a proper ingestion pipeline before going live |
| **SQL Server -> Model Development** | `vw_modeling_dataset`, exported to CSV | This is a genuine environment boundary in most banks: the SQL warehouse is typically a governed, access-controlled environment; the data science/model development environment (Jupyter, Python) usually runs elsewhere (a sandboxed VM, a notebook service) with its own access controls. Data physically leaves the database the moment it's exported to CSV -- worth being deliberate about what leaves and why |
| **Model Development -> Consumption Layer** | `final_scored_applications.csv`, frozen model artifacts | This is the model governance boundary -- once artifacts leave the dev environment, they're meant to be FROZEN (the WOE bins, coefficients, and scorecard points table shouldn't silently change without a formal model version bump). See `docs/model_governance_notes.md` |

## What's simulated vs what a real deployment would add

This project simulates the analytical pipeline end-to-end, but a real bank's
production deployment would add layers this project deliberately doesn't
build, since they're infrastructure/MLOps concerns rather than credit risk
methodology:

- **Automated scheduling** (Airflow/ADF/cron) instead of `src/run_pipeline.py`
  being run manually
- **A model registry** (e.g. MLflow) versioning each scorecard artifact,
  rather than a single `stage8_scorecard.json` file
- **A real-time or batch scoring API** sitting in front of the frozen
  scorecard, rather than a static `final_scored_applications.csv`
- **Access controls and data lineage tooling** (e.g. Unity Catalog, Purview)
  governing who can read `bureau_data` vs who can only read the final
  score, given the sensitivity of raw bureau attributes
- **Automated PSI/drift monitoring** running on a schedule against live
  scored applications, rather than the one-time Stage 9 calculation against
  a static test set

`src/run_pipeline.py` in this project is a deliberately simple stand-in for
what an Airflow DAG or ADF pipeline would do in production -- it
demonstrates the ORDERING and dependency logic (each stage's log entry
shows what a real scheduler log looks like) without the operational
complexity of an actual scheduler.
