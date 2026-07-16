-- ============================================================
-- 05_us_analysis.sql
-- Final national analysis: LTPAC provider access by ZIP
-- Creates dbo.US_LTPAC_Analysis
-- Run after: 04_us_ltpac_by_zip.sql and 02_census_national_load.sql
-- Run BEFORE: 06_us_ltpac_by_state.sql (which depends on this table)
--
-- DESIGN:
--   Mirrors 13_hi_analysis.sql from the Hawaii project exactly,
--   with three changes:
--     1. Joins to ref.Census_US_65Plus instead of ref.Census_HI_65Plus
--     2. State column carried through from dbo.US_LTPAC_ByZIP
--     3. Island CASE removed; State passthrough replaces it
--   All flag logic, ZIPLabel precedence, and vintage fields are
--   identical. This is intentional — the Hawaii scripts are the
--   template and the national version should not diverge from them
--   without good reason.
--
-- SCHEMA DESIGN PRINCIPLES (same as Hawaii, repeated for reference):
--   1. Every ZIP stays in output. Flags are context, not filters.
--   2. Absolute counts travel alongside rates.
--   3. Vintage fields on every row.
--   4. Military ZIPs flagged separately from small-denominator ZIPs.
--
-- KNOWN LIMITATION (same as Hawaii):
--   Providers attributed to billing ZIP understates regional access.
--   At national scale this applies to VA, Indian Health Service,
--   and other federally-serving facilities, not just Hawaii VA cases.
-- ============================================================

USE HEALTHCARE_DATA;
GO

-- Populate Hawaii military ZIPs if not already done.
-- Add all other states here before running. The ref table schema
-- (State column, same PK) supports all 50 states without changes.
-- TODO: populate ref.MilitaryInstallation_ZIPs for all states
--       before running this script at national scale.
-- ============================================================

DECLARE @SmallPopThreshold INT = 100;

IF OBJECT_ID('dbo.US_LTPAC_Analysis', 'U') IS NOT NULL
    DROP TABLE dbo.US_LTPAC_Analysis;

SELECT
    z.ZIP,
    z.State,
    c.Population_Total,
    c.Population_65Plus,
    z.TotalProviders,
    z.FacilityCount,
    z.IndividualCount,
    z.SNF_Count,
    z.AssistedLiving_Count,
    z.HomeHealth_Hospice_Count,
    z.Hospital_LTC_Rehab_Count,
    z.Therapy_Count,
    z.MultiLocationIndicator,

    CASE
        WHEN c.Population_65Plus > 0
        THEN ROUND(CAST(z.TotalProviders AS FLOAT) / c.Population_65Plus * 1000, 2)
        ELSE NULL
    END AS ProvidersPerThousandElderly,

    CASE
        WHEN c.Population_65Plus > 0
        THEN ROUND(CAST(z.FacilityCount AS FLOAT) / c.Population_65Plus * 1000, 2)
        ELSE NULL
    END AS FacilitiesPerThousandElderly,

    CASE
        WHEN c.Population_Total > 0
        THEN ROUND(CAST(c.Population_65Plus AS FLOAT) / c.Population_Total * 100, 1)
        ELSE NULL
    END AS Pct_65Plus,

    CASE WHEN c.Population_65Plus IS NULL
              OR c.Population_65Plus < @SmallPopThreshold
         THEN 1 ELSE 0
    END AS SmallDenominatorFlag,

    CASE WHEN mil.ZIP IS NOT NULL THEN 1 ELSE 0
    END AS MilitaryInstallationFlag,

    -- ZIPLabel precedence: military > no Census match > small pop > clean
    CASE
        WHEN mil.ZIP IS NOT NULL         THEN z.ZIP + ' **'
        WHEN c.Population_65Plus IS NULL THEN z.ZIP + ' ***'
        WHEN c.Population_65Plus < @SmallPopThreshold
                                         THEN z.ZIP + ' *'
        ELSE z.ZIP
    END AS ZIPLabel,

    c.ACS_Year,
    CAST('<npi-extract-date>' AS DATE)  AS NPI_ExtractDate,  -- update to match your file date
    GETDATE()                           AS AnalysisRunDate

INTO dbo.US_LTPAC_Analysis

FROM dbo.US_LTPAC_ByZIP z
LEFT JOIN ref.Census_US_65Plus c
    ON z.ZIP = c.ZIP
LEFT JOIN ref.MilitaryInstallation_ZIPs mil
    ON z.ZIP = mil.ZIP;
GO

PRINT 'US_LTPAC_Analysis table created.';
GO

-- --------------------------------------------------------
-- Validation
-- --------------------------------------------------------
SELECT COUNT(*)                     AS TotalZIPs    FROM dbo.US_LTPAC_Analysis;
SELECT COUNT(DISTINCT State)        AS States       FROM dbo.US_LTPAC_Analysis;
SELECT SUM(SmallDenominatorFlag)    AS SmallDenomZIPs FROM dbo.US_LTPAC_Analysis;
SELECT SUM(MilitaryInstallationFlag) AS MilZIPs     FROM dbo.US_LTPAC_Analysis;

-- ZIPs with no Census match (expect some — rural/PO Box ZIPs)
SELECT COUNT(*) AS NoCensusMatch
FROM dbo.US_LTPAC_Analysis
WHERE Population_65Plus IS NULL;
GO
