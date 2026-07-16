-- ============================================================
-- 07_mil_installations_load.sql
-- Populates ref.MilitaryInstallation_ZIPs for all US states
-- Run BEFORE: 05_us_analysis.sql
--
-- AUTHORITATIVE SOURCE:
--   Homeland Infrastructure Foundation-Level Data (HIFLD)
--   Dataset: "Military Installations, Ranges, and Training Areas"
--   URL: https://hifld-geoplatform.opendata.arcgis.com/
--        search for "Military Installations"
--   Format: downloadable CSV/GeoJSON, public, no account required
--   Fields include: COMPONENT, SITE_NAME, ADDRESS, CITY, STATE, ZIP
--   Updated periodically by DoD. Note the vintage when you load.
--
-- WHY UNIFORM MATTERS:
--   A partial military-installation list (some states flagged,
--   others not) biases the state ranking silently. States with
--   large military footprints (VA, CA, TX, FL, NC) that aren't
--   flagged will overstate civilian access density. This is the
--   same "flag, don't drop" ethic applied to the source data
--   itself: be uniform or be explicitly documented, never partial.
--
--   If you cannot complete the national load before running the
--   analysis, document the gap in the README Known Limitations
--   section rather than running with incomplete coverage.
--
-- LOAD APPROACH:
--   1. Download the HIFLD CSV
--   2. Filter to rows where ZIP is 5 digits and not null
--   3. Deduplicate on ZIP (one row per ZIP — the ref table PK is ZIP)
--      Some installations span multiple ZIPs; some ZIPs have
--      multiple installations. For this analysis, what matters is
--      whether the ZIP is a military ZIP, not which installation.
--      Keep the first/dominant installation name per ZIP for context.
--   4. INSERT below, or write a Python/PowerShell loader if the
--      HIFLD CSV is large enough to make manual INSERT impractical
--
-- EXISTING ROWS (from Hawaii project, already inserted):
--   96853  Joint Base Pearl Harbor-Hickam  HI
--   96857  Schofield Barracks              HI
--   96859  Tripler Army Medical Center     HI
--   96860  Naval Station Pearl Harbor      HI
-- ============================================================

USE HEALTHCARE_DATA;
GO

-- --------------------------------------------------------
-- INSERT template — one row per unique military ZIP
-- DataSource should record the HIFLD vintage (download date
-- or dataset publication date) for reproducibility.
-- --------------------------------------------------------

-- INSERT INTO ref.MilitaryInstallation_ZIPs
--     (ZIP, InstallationName, BranchOfService, State, DataSource)
-- VALUES
--     ('<zip>', '<installation name>', '<branch>', '<state>',
--      'HIFLD Military Installations <download-date>'),
--     ...

-- --------------------------------------------------------
-- After completing the load, verify coverage
-- --------------------------------------------------------
SELECT State, COUNT(*) AS ZIPCount
FROM ref.MilitaryInstallation_ZIPs
GROUP BY State
ORDER BY ZIPCount DESC;

-- States with large military presence to confirm are covered:
-- VA (Norfolk/Quantico/Pentagon area), CA, TX, FL, NC, GA, WA
SELECT State, ZIPCount = COUNT(*)
FROM ref.MilitaryInstallation_ZIPs
WHERE State IN ('VA','CA','TX','FL','NC','GA','WA','HI')
GROUP BY State
ORDER BY State;
GO
