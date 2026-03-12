-- ============================================================
-- PS-CRM Migration 008 — Add generated lat/lng columns to complaints
-- Extracted from the PostGIS GEOMETRY(Point, 4326) location column.
-- Allows the admin complaint list API to return lat/lng without
-- requiring PostGIS function calls in the Python backend.
-- ============================================================

ALTER TABLE complaints
  ADD COLUMN IF NOT EXISTS lat DOUBLE PRECISION GENERATED ALWAYS AS (ST_Y(location::geometry)) STORED,
  ADD COLUMN IF NOT EXISTS lng DOUBLE PRECISION GENERATED ALWAYS AS (ST_X(location::geometry)) STORED;

COMMENT ON COLUMN complaints.lat IS 'Latitude extracted from PostGIS location column (auto-generated)';
COMMENT ON COLUMN complaints.lng IS 'Longitude extracted from PostGIS location column (auto-generated)';
