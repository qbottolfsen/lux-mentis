-- ============================================================
-- 03_us_ltpac_filter.sql
-- Filters NPI data to active LTPAC providers, all 50 states
-- Creates dbo.US_LTPAC_Providers
-- Run after: dbo.NPIData and ref.NUCC_Taxonomy are loaded
--            (Hawaii project scripts 03-08 if starting fresh)
--
-- DESIGN DIFFERENCES FROM HAWAII VERSION (11_hi_ltpac_filter.sql):
--   1. No state restriction — all 50 states + DC + territories
--   2. State column added explicitly so downstream tables have it
--      without re-deriving from address fields
--   3. Table name is US_LTPAC_Providers, not HI_LTPAC_Providers,
--      so both can coexist in HEALTHCARE_DATA without collision
--
-- KNOWN LIMITATION (same as Hawaii):
--   Filter matches TaxonomyCode_1 (primary taxonomy) only.
--   Providers whose LTPAC specialty is in a secondary slot are
--   not captured. See Hawaii project readme for full discussion.
-- ============================================================

USE HEALTHCARE_DATA;
GO

IF OBJECT_ID('dbo.US_LTPAC_Providers', 'U') IS NOT NULL
    DROP TABLE dbo.US_LTPAC_Providers;
GO

-- --------------------------------------------------------
-- Same 22 NUCC taxonomy codes as Hawaii project.
-- Verified against NUCC v25.1. Do not change without
-- also updating 04_us_ltpac_by_zip.sql category buckets.
-- --------------------------------------------------------

SELECT
    n.NPI,
    n.EntityTypeCode,
    n.ProviderLastName,
    n.ProviderFirstName,
    n.ProviderOrganizationName,
    n.PracticeLocationAddressLine1,
    n.PracticeLocationAddressLine2,
    n.PracticeLocationCity,
    n.PracticeLocationState                     AS State,
    LEFT(n.PracticeLocationPostalCode, 5)       AS PracticeZIP5,
    n.BusinessMailingAddressLine1,
    n.BusinessMailingCity,
    n.BusinessMailingState,
    LEFT(n.BusinessMailingPostalCode, 5)        AS MailingZIP5,
    n.TaxonomyCode_1,
    t.Classification,
    t.Specialization,
    t.DisplayName                               AS TaxonomyDisplayName,
    n.TaxonomyGroup_1,
    n.ParentOrganizationLBN,
    n.ParentOrganizationTIN,
    n.EnumerationDate,
    n.LastUpdateDate

INTO dbo.US_LTPAC_Providers

FROM dbo.NPIData n
LEFT JOIN ref.NUCC_Taxonomy t
    ON n.TaxonomyCode_1 = t.Code

WHERE n.NPIDeactivationReasonCode IS NULL
  AND n.TaxonomyCode_1 IN (
        '314000000X', '3140N1450X', '313M00000X',
        '310400000X', '3104A0630X', '3104A0625X',
        '311500000X', '311Z00000X', '311ZA0620X',
        '315D00000X', '315P00000X', '310500000X',
        '282E00000X', '283X00000X', '283XC2000X',
        '251E00000X', '251G00000X', '251J00000X',
        '225100000X', '225X00000X', '235Z00000X',
        '374U00000X'
  );
GO

-- --------------------------------------------------------
-- Validation
-- --------------------------------------------------------
SELECT COUNT(*)             AS TotalProviders    FROM dbo.US_LTPAC_Providers;
SELECT COUNT(DISTINCT NPI)  AS UniqueNPIs        FROM dbo.US_LTPAC_Providers;
SELECT COUNT(DISTINCT State) AS StateCount       FROM dbo.US_LTPAC_Providers;

-- Provider count by state (expect all 50 + DC + some territories)
SELECT
    State,
    COUNT(*) AS ProviderCount
FROM dbo.US_LTPAC_Providers
GROUP BY State
ORDER BY ProviderCount DESC;
GO
