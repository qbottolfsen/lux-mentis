-- ============================================================
-- 01_census_national_create.sql
-- Creates ref.Census_US_65Plus for all US ZCTAs (~33,000 rows)
-- Source: US Census Bureau, American Community Survey
--         Table B01001 (Sex by Age), 5-year estimates, ZCTA level
-- Run after: HEALTHCARE_DATA database and ref schema already exist
--            (see Hawaii project sql/01 and sql/02 if starting fresh)
--
-- DESIGN NOTE:
--   Schema is identical to ref.Census_HI_65Plus so the analysis
--   scripts in 06_us_analysis.sql can apply the same flag logic
--   without modification. The only difference is scope: all ZCTAs,
--   not just Hawaii 967xx/968xx.
-- ============================================================

USE HEALTHCARE_DATA;
GO

IF OBJECT_ID('ref.Census_US_65Plus', 'U') IS NULL
BEGIN
    CREATE TABLE ref.Census_US_65Plus (
        ZIP                 VARCHAR(5)      NOT NULL,
        Population_Total    INT             NULL,
        Population_65Plus   INT             NULL,
        ACS_Year            VARCHAR(10)     NULL,
        CONSTRAINT PK_Census_US_65Plus PRIMARY KEY (ZIP)
    );
    PRINT 'ref.Census_US_65Plus created.';
END
ELSE
    PRINT 'ref.Census_US_65Plus already exists.';
GO

-- Next step: run python/get_census_us_65plus.py to pull all US ZCTAs
-- from the Census API (~33K rows, expect several minutes), then run
-- 02_census_national_load.sql to bulk load the output CSV.
--
-- NOTE ON CENSUS PULL SIZE:
--   The national ZCTA pull is significantly larger than Hawaii.
--   The Census API returns all ZCTAs in a single request; response
--   size is typically 10-15 MB. A Census API key is required.
--   The Python script handles suppressed values (-666666666 etc.)
--   the same way as the Hawaii version. No other changes needed.
