-- ============================================================
-- 04_us_ltpac_by_zip.sql
-- Aggregates US LTPAC provider counts by ZIP code
-- Creates dbo.US_LTPAC_ByZIP
-- Run after: 03_us_ltpac_filter.sql
--
-- DESIGN DIFFERENCES FROM HAWAII VERSION (12_hi_ltpac_by_zip.sql):
--   1. State column carried through for downstream joins and filters
--   2. No ZIP-prefix filter (Hawaii restricted to 967%/968%)
--   3. NULL/empty ZIP handling still applies — PO Box and military
--      ZIPs with no practice location are excluded at this step
-- ============================================================

USE HEALTHCARE_DATA;
GO

IF OBJECT_ID('dbo.US_LTPAC_ByZIP', 'U') IS NOT NULL
    DROP TABLE dbo.US_LTPAC_ByZIP;
GO

SELECT
    PracticeZIP5                        AS ZIP,
    State,
    COUNT(DISTINCT NPI)                 AS TotalProviders,
    SUM(CASE WHEN EntityTypeCode = '2' THEN 1 ELSE 0 END) AS FacilityCount,
    SUM(CASE WHEN EntityTypeCode = '1' THEN 1 ELSE 0 END) AS IndividualCount,
    SUM(CASE WHEN TaxonomyCode_1 IN ('314000000X','3140N1450X','313M00000X')
             THEN 1 ELSE 0 END)         AS SNF_Count,
    SUM(CASE WHEN TaxonomyCode_1 IN ('310400000X','3104A0630X','3104A0625X','311500000X')
             THEN 1 ELSE 0 END)         AS AssistedLiving_Count,
    SUM(CASE WHEN TaxonomyCode_1 IN ('251E00000X','251G00000X','374U00000X')
             THEN 1 ELSE 0 END)         AS HomeHealth_Hospice_Count,
    SUM(CASE WHEN TaxonomyCode_1 IN ('282E00000X','283X00000X','283XC2000X')
             THEN 1 ELSE 0 END)         AS Hospital_LTC_Rehab_Count,
    SUM(CASE WHEN TaxonomyCode_1 IN ('225100000X','225X00000X','235Z00000X')
             THEN 1 ELSE 0 END)         AS Therapy_Count,
    SUM(CASE WHEN MailingZIP5 <> PracticeZIP5
              AND MailingZIP5 IS NOT NULL
              AND MailingZIP5 <> ''
             THEN 1 ELSE 0 END)         AS MultiLocationIndicator

INTO dbo.US_LTPAC_ByZIP

FROM dbo.US_LTPAC_Providers
WHERE PracticeZIP5 IS NOT NULL
  AND PracticeZIP5 <> ''
GROUP BY PracticeZIP5, State;
GO

-- --------------------------------------------------------
-- Validation
-- --------------------------------------------------------
SELECT COUNT(*) AS ZIPCount         FROM dbo.US_LTPAC_ByZIP;
SELECT COUNT(DISTINCT State) AS States FROM dbo.US_LTPAC_ByZIP;

SELECT
    State,
    COUNT(ZIP) AS ZIPCount,
    SUM(TotalProviders) AS TotalProviders
FROM dbo.US_LTPAC_ByZIP
GROUP BY State
ORDER BY TotalProviders DESC;
GO
