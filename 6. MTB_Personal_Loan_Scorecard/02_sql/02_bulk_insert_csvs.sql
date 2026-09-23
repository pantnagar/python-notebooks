/* ============================================================================
   Script 02: Load CSVs into SQL Server using BULK INSERT

   BEFORE RUNNING:
   1. Copy the 01_data/raw_csv/ folder to a local path SQL Server can read,
      e.g. C:\MTB_Project\raw_csv\   (SQL Server's service account needs file
      system read access to this path -- if you get a permissions error,
      right-click the folder -> Properties -> Security -> give the SQL Server
      service account (or Everyone, for local dev) Read permission).
   2. Update @csv_path below to match your local path.

   WHY BULK INSERT (not the GUI Import Wizard): this is what you'd actually
   write in a production ETL/staging script, it's scriptable and repeatable,
   and it forces you to think about data types and error handling explicitly.
   ============================================================================ */

USE MTB_ScorecardProject;
GO

DECLARE @csv_path VARCHAR(200) = 'C:\MTB_Project\raw_csv\';

-- NOTE: BULK INSERT can't take a variable for the file path directly in T-SQL,
-- so below each statement has the path hardcoded. Update the path in EACH
-- statement to match where you saved the CSVs.

/* 1. customer_details */
BULK INSERT dbo.customer_details
FROM 'C:\MTB_Project\raw_csv\customer_details.csv'
WITH (
    FIRSTROW = 2,               -- skip header row
    FIELDTERMINATOR = ',',
    ROWTERMINATOR = '0x0a',     -- handles Unix-style line endings from Python
    TABLOCK,
    CODEPAGE = '65001'          -- UTF-8, handles names with special characters
);
GO

/* 2. loan_applications */
BULK INSERT dbo.loan_applications
FROM 'C:\MTB_Project\raw_csv\loan_applications.csv'
WITH (
    FIRSTROW = 2,
    FIELDTERMINATOR = ',',
    ROWTERMINATOR = '0x0a',
    TABLOCK,
    CODEPAGE = '65001'
);
GO

/* 3. bureau_data
   NOTE: months_since_last_delinquency has blank values (NULL) in the CSV for
   applicants with no prior delinquency -- BULK INSERT handles empty fields as
   NULL by default, but confirm this after loading (see checkpoint query below).
*/
BULK INSERT dbo.bureau_data
FROM 'C:\MTB_Project\raw_csv\bureau_data.csv'
WITH (
    FIRSTROW = 2,
    FIELDTERMINATOR = ',',
    ROWTERMINATOR = '0x0a',
    TABLOCK,
    CODEPAGE = '65001'
);
GO

/* 4. transactions (largest file, ~480K rows - may take a minute) */
BULK INSERT dbo.transactions
FROM 'C:\MTB_Project\raw_csv\transactions.csv'
WITH (
    FIRSTROW = 2,
    FIELDTERMINATOR = ',',
    ROWTERMINATOR = '0x0a',
    TABLOCK,
    CODEPAGE = '65001'
);
GO

/* 5. loan_performance (~169K rows) */
BULK INSERT dbo.loan_performance
FROM 'C:\MTB_Project\raw_csv\loan_performance.csv'
WITH (
    FIRSTROW = 2,
    FIELDTERMINATOR = ',',
    ROWTERMINATOR = '0x0a',
    TABLOCK,
    CODEPAGE = '65001'
);
GO

/* ----------------------------------------------------------------------------
   CHECKPOINT: row count validation
   Run this and compare against the expected counts printed by the Python
   generator (or in 00_README.md). If any of these don't match, STOP --
   do not proceed to Stage 2 with a partial load.
---------------------------------------------------------------------------- */
SELECT 'customer_details' AS table_name, COUNT(*) AS row_count FROM dbo.customer_details
UNION ALL
SELECT 'loan_applications', COUNT(*) FROM dbo.loan_applications
UNION ALL
SELECT 'bureau_data', COUNT(*) FROM dbo.bureau_data
UNION ALL
SELECT 'transactions', COUNT(*) FROM dbo.transactions
UNION ALL
SELECT 'loan_performance', COUNT(*) FROM dbo.loan_performance;

/* Expected (from data generator run):
   customer_details   : 6,000
   loan_applications  : 9,000
   bureau_data        : 9,000
   transactions       : ~479,000  (varies slightly by random seed)
   loan_performance   : ~169,000  (varies -- depends on who defaults early and stops generating)
*/
