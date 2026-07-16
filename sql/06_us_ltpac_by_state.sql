-- ============================================================
-- 06_us_ltpac_by_state.sql
-- State-level LTPAC provider access summary
-- Creates dbo.US_LTPAC_ByState — the "rank the states" table
-- Run after: 05_us_analysis.sql (MUST run 05 first — this script
--            reads from dbo.US_LTPAC_Analysis which 05 creates)
--
-- PURPOSE:
--   This is the table that drives the Power BI national choropleth
--   and state ranking visual. It aggregates ZIP-level analysis rows
--   to state level, computing population-weighted rates rather than
--   averaging per-ZIP ratios (which would overweight small ZIPs).
--
-- DESIGN NOTE — what goes here vs the ZIP-level analysis:
--   ProvidersPerThousandElderly here = SUM(providers) / SUM(pop65+) * 1000
--   This is not the same as AVG(ZIP-level ratio). The population-weighted
--   version is correct for state comparison. The ZIP-level table is for
--   within-state drill-down.
--
--   Military ZIPs are excluded from state totals (same logic as Hawaii
--   island summary). Small-denominator ZIPs are INCLUDED — their
--   absolute counts still contribute to the state total correctly even
--   when the ZIP-level ratio was unreliable.
-- ============================================================

USE HEALTHCARE_DATA;
GO

IF OBJECT_ID('dbo.US_LTPAC_ByState', 'U') IS NOT NULL
    DROP TABLE dbo.US_LTPAC_ByState;
GO

SELECT
    a.State,
    COUNT(DISTINCT a.ZIP)                   AS ZIPCount,
    SUM(a.TotalProviders)                   AS TotalProviders,
    SUM(a.FacilityCount)                    AS TotalFacilities,
    SUM(a.IndividualCount)                  AS TotalIndividuals,
    SUM(a.Population_Total)                 AS TotalPopulation,
    SUM(a.Population_65Plus)                AS TotalPop65Plus,

    -- Population-weighted access rate (correct for state comparison)
    ROUND(
        CAST(SUM(a.TotalProviders) AS FLOAT)
        / NULLIF(SUM(a.Population_65Plus), 0) * 1000
    , 2)                                    AS ProvidersPerThousandElderly,

    ROUND(
        CAST(SUM(a.FacilityCount) AS FLOAT)
        / NULLIF(SUM(a.Population_65Plus), 0) * 1000
    , 2)                                    AS FacilitiesPerThousandElderly,

    ROUND(
        CAST(SUM(a.Population_65Plus) AS FLOAT)
        / NULLIF(SUM(a.Population_Total), 0) * 100
    , 1)                                    AS Pct_65Plus,

    -- Count of flagged ZIPs for context
    SUM(a.SmallDenominatorFlag)             AS SmallDenominatorZIPCount,
    SUM(a.MilitaryInstallationFlag)         AS MilitaryZIPCount,

    MAX(a.NPI_ExtractDate)                  AS NPI_ExtractDate,
    MAX(a.ACS_Year)                         AS ACS_Year,
    GETDATE()                               AS AnalysisRunDate

INTO dbo.US_LTPAC_ByState

FROM dbo.US_LTPAC_Analysis a
WHERE a.MilitaryInstallationFlag = 0
  AND a.Population_65Plus IS NOT NULL
GROUP BY a.State;
GO

-- --------------------------------------------------------
-- Validation — the "rank the states" output
-- --------------------------------------------------------
SELECT COUNT(*) AS StateCount FROM dbo.US_LTPAC_ByState;

SELECT
    State,
    TotalProviders,
    TotalPop65Plus,
    ProvidersPerThousandElderly,
    RANK() OVER (ORDER BY ProvidersPerThousandElderly ASC) AS AccessRank
FROM dbo.US_LTPAC_ByState
ORDER BY ProvidersPerThousandElderly ASC;
GO
