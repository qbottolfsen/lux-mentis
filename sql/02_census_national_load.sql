-- ============================================================
-- 02_census_national_load.sql
-- Loads national ZCTA population data into ref.Census_US_65Plus
-- Source: US Census Bureau ACS 5-Year (see python script for year)
-- File:   <your-data-path>\ACSDT5Y<year>.B01001_US_ZCTA_Pivoted.csv
-- Run after: 01_census_national_create.sql and Python pull complete
--
-- NOTE: ~33K rows vs 97 for Hawaii. Load time is still fast
--       (seconds, not minutes) since the CSV is modest in size.
--       Validate the row count carefully — a partial pull from the
--       Census API will load without error but produce fewer rows.
-- ============================================================

USE HEALTHCARE_DATA;
GO

TRUNCATE TABLE ref.Census_US_65Plus;
GO

BULK INSERT ref.Census_US_65Plus
FROM '<your-data-path>\ACSDT5Y<year>.B01001_US_ZCTA_Pivoted.csv'
WITH (
    FORMAT          = 'CSV',
    FIRSTROW        = 2,
    FIELDTERMINATOR = ',',
    ROWTERMINATOR   = '0x0A',
    CODEPAGE        = '65001'
);
GO

PRINT 'Census_US_65Plus loaded. -- VERIFY count below (expect ~33K rows, NOT 0).';
GO

-- --------------------------------------------------------
-- Validation
-- --------------------------------------------------------
SELECT COUNT(*) AS ZCTACount FROM ref.Census_US_65Plus;

-- State-prefix distribution (sanity check — all 50 states + territories)
SELECT LEFT(ZIP, 3) AS ZIPPrefix, COUNT(*) AS ZCTACount
FROM ref.Census_US_65Plus
GROUP BY LEFT(ZIP, 3)
ORDER BY ZIPPrefix;

-- Top 10 by elderly population
SELECT TOP 10
    ZIP,
    Population_Total,
    Population_65Plus,
    CAST(Population_65Plus AS FLOAT) / NULLIF(Population_Total, 0) * 100 AS Pct_65Plus,
    ACS_Year
FROM ref.Census_US_65Plus
ORDER BY Population_65Plus DESC;

-- ZCTAs with zero or missing population (expected for PO Box / military ZIPs)
SELECT COUNT(*) AS ZeroPopZCTAs
FROM ref.Census_US_65Plus
WHERE Population_Total = 0 OR Population_Total IS NULL;
GO
