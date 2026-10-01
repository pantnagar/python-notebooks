/* ============================================================================
   Meridian Trust Bank (MTB) - Personal Loan Application Credit Scorecard
   Script 01: Database & Table Creation

   Run this in SSMS connected to your SQL Server instance.

   GRAIN NOTES (read before you run this):
   - customer_details      : 1 row per customer
   - loan_applications     : 1 row per application  (1 customer -> many applications)
   - bureau_data            : 1 row per application  (bureau snapshot AT APPLICATION TIME,
                               NOT per customer -- this avoids leaking a customer's later
                               bureau history into an earlier application)
   - transactions           : many rows per customer (ongoing banking behavior)
   - loan_performance       : many rows per application (one row per Month-on-Book / MOB)
   ============================================================================ */

IF DB_ID('MTB_ScorecardProject') IS NULL
BEGIN
    CREATE DATABASE MTB_ScorecardProject;
END
GO

USE MTB_ScorecardProject;
GO

/* Drop tables if re-running this script during development */
IF OBJECT_ID('dbo.loan_performance', 'U') IS NOT NULL DROP TABLE dbo.loan_performance;
IF OBJECT_ID('dbo.transactions', 'U') IS NOT NULL DROP TABLE dbo.transactions;
IF OBJECT_ID('dbo.bureau_data', 'U') IS NOT NULL DROP TABLE dbo.bureau_data;
IF OBJECT_ID('dbo.loan_applications', 'U') IS NOT NULL DROP TABLE dbo.loan_applications;
IF OBJECT_ID('dbo.customer_details', 'U') IS NOT NULL DROP TABLE dbo.customer_details;
GO

/* ----------------------------------------------------------------------------
   1. CUSTOMER DETAILS
---------------------------------------------------------------------------- */
CREATE TABLE dbo.customer_details (
    customer_id                 VARCHAR(10)     NOT NULL,
    first_name                  VARCHAR(50),
    last_name                   VARCHAR(50),
    date_of_birth                DATE,
    age_at_2024                  INT,
    gender                       CHAR(1),
    state                        VARCHAR(5),
    postcode                     VARCHAR(10),
    employment_type              VARCHAR(20),
    employment_tenure_months     INT,
    annual_income                DECIMAL(12,2),
    residential_status           VARCHAR(20),
    dependents                   INT,
    customer_since               DATE,
    CONSTRAINT PK_customer_details PRIMARY KEY (customer_id)
);
GO

/* ----------------------------------------------------------------------------
   2. LOAN APPLICATIONS  (grain of the whole project)
---------------------------------------------------------------------------- */
CREATE TABLE dbo.loan_applications (
    application_id               VARCHAR(10)     NOT NULL,
    customer_id                  VARCHAR(10)     NOT NULL,
    application_date             DATE            NOT NULL,
    loan_purpose                 VARCHAR(30),
    loan_amount_requested        DECIMAL(12,2),
    term_months                  INT,
    interest_rate_offered        DECIMAL(5,2),
    channel                      VARCHAR(20),
    CONSTRAINT PK_loan_applications PRIMARY KEY (application_id),
    CONSTRAINT FK_loanapp_customer FOREIGN KEY (customer_id)
        REFERENCES dbo.customer_details(customer_id)
);
GO

/* ----------------------------------------------------------------------------
   3. BUREAU DATA (1:1 with application - snapshot at application time)
---------------------------------------------------------------------------- */
CREATE TABLE dbo.bureau_data (
    application_id                VARCHAR(10)     NOT NULL,
    bureau_credit_score           INT,
    enquiries_last_6m             INT,
    active_credit_accounts        INT,
    defaults_on_file              INT,
    months_since_last_delinquency INT NULL,   -- NULL = no prior delinquency on file
    total_existing_debt           DECIMAL(12,2),
    credit_utilization_pct        DECIMAL(5,1),
    credit_file_age_months        INT,
    CONSTRAINT PK_bureau_data PRIMARY KEY (application_id),
    CONSTRAINT FK_bureau_application FOREIGN KEY (application_id)
        REFERENCES dbo.loan_applications(application_id)
);
GO

/* ----------------------------------------------------------------------------
   4. TRANSACTIONS (many:1 with customer)
---------------------------------------------------------------------------- */
CREATE TABLE dbo.transactions (
    transaction_id                VARCHAR(15)     NOT NULL,
    customer_id                   VARCHAR(10)     NOT NULL,
    transaction_date              DATE,
    category                      VARCHAR(30),
    amount                        DECIMAL(12,2),
    CONSTRAINT PK_transactions PRIMARY KEY (transaction_id),
    CONSTRAINT FK_txn_customer FOREIGN KEY (customer_id)
        REFERENCES dbo.customer_details(customer_id)
);
GO

/* ----------------------------------------------------------------------------
   5. LOAN PERFORMANCE (many:1 with application - one row per MOB)
      This is the table that drives target creation (Stage 2) and
      vintage/MOB analysis (Stage 3).
---------------------------------------------------------------------------- */
CREATE TABLE dbo.loan_performance (
    application_id                VARCHAR(10)     NOT NULL,
    mob                            INT             NOT NULL,   -- Month on Book
    performance_date                DATE,
    dpd_bucket                      TINYINT,   -- 0=current,1=1-29,2=30-59,3=60-89,4=90+
    current_dpd                     INT,
    balance_outstanding             DECIMAL(12,2),
    CONSTRAINT PK_loan_performance PRIMARY KEY (application_id, mob),
    CONSTRAINT FK_perf_application FOREIGN KEY (application_id)
        REFERENCES dbo.loan_applications(application_id)
);
GO

/* ----------------------------------------------------------------------------
   Helpful indexes for the joins/aggregations we'll run in later scripts
---------------------------------------------------------------------------- */
CREATE INDEX IX_loanapp_customer ON dbo.loan_applications(customer_id);
CREATE INDEX IX_loanapp_date ON dbo.loan_applications(application_date);
CREATE INDEX IX_txn_customer_date ON dbo.transactions(customer_id, transaction_date);
CREATE INDEX IX_perf_app_mob ON dbo.loan_performance(application_id, mob);
GO

PRINT 'Schema created successfully.';
