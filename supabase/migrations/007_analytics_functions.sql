-- ============================================================
-- PS-CRM Migration 007 — Analytics Functions & Schema Additions
-- Adds:
--   • contractor_id column to complaint_departments
--   • get_wards_geojson      — ward boundaries as GeoJSON FeatureCollection
--   • get_hotspots_with_coords — hotspots with lat/lng extracted from geometry
--   • compute_sla_compliance — SLA compliance per department
--   • complaint_volume_series — complaint volume time series
--   • ward_complaint_density  — complaint count per ward (public heatmap)
--   • get_complaints_with_coords_last_90_days — for Predictive Agent DBSCAN
-- ============================================================

-- ── Add contractor_id to complaint_departments ────────────────────────
-- (Backend references contractor_id for work order assignment and scorecard)
ALTER TABLE complaint_departments
  ADD COLUMN IF NOT EXISTS contractor_id UUID REFERENCES contractors(id);

CREATE INDEX IF NOT EXISTS idx_cd_contractor_id
  ON complaint_departments(contractor_id);

-- Add detected_at to hotspots if missing
ALTER TABLE hotspots
  ADD COLUMN IF NOT EXISTS detected_at TIMESTAMPTZ DEFAULT NOW();

-- ── get_wards_geojson ─────────────────────────────────────────────────
-- Returns ward boundaries as a GeoJSON FeatureCollection string.
-- Used by GET /wards and cached for 24h in the router.
CREATE OR REPLACE FUNCTION get_wards_geojson()
RETURNS TEXT AS $$
  SELECT json_build_object(
    'type', 'FeatureCollection',
    'features', COALESCE(json_agg(
      json_build_object(
        'type', 'Feature',
        'geometry', ST_AsGeoJSON(boundary)::json,
        'properties', json_build_object(
          'id',          id,
          'name',        name,
          'ward_number', ward_number
        )
      )
    ), '[]'::json)
  )::text
  FROM wards;
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- ── get_hotspots_with_coords ──────────────────────────────────────────
-- Returns hotspot rows with lat/lng extracted from the PostGIS center column.
CREATE OR REPLACE FUNCTION get_hotspots_with_coords(p_is_resolved BOOLEAN DEFAULT FALSE)
RETURNS TABLE (
  id              UUID,
  lat             DOUBLE PRECISION,
  lng             DOUBLE PRECISION,
  radius_meters   INTEGER,
  category        VARCHAR,
  complaint_count INTEGER,
  severity        SMALLINT,
  ward_name       TEXT,
  detected_at     TIMESTAMPTZ,
  is_resolved     BOOLEAN
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    h.id,
    ST_Y(h.center::geometry)             AS lat,
    ST_X(h.center::geometry)             AS lng,
    h.radius_meters,
    h.category,
    h.complaint_count,
    h.severity,
    w.name::TEXT                         AS ward_name,
    h.detected_at,
    NOT h.is_active                      AS is_resolved
  FROM hotspots h
  LEFT JOIN wards w ON w.id = h.ward_id
  WHERE h.is_active = (NOT p_is_resolved)
  ORDER BY h.severity DESC;
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;

-- ── compute_sla_compliance ────────────────────────────────────────────
-- Returns SLA compliance grouped by department for a date range.
-- Called by GET /analytics/sla-compliance
CREATE OR REPLACE FUNCTION compute_sla_compliance(
  from_date TEXT DEFAULT NULL,
  to_date   TEXT DEFAULT NULL
)
RETURNS TABLE (
  department_name       TEXT,
  total_complaints      BIGINT,
  resolved_within_sla   BIGINT,
  sla_breached          BIGINT,
  compliance_pct        NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    d.name::TEXT                                                AS department_name,
    COUNT(c.id)                                                 AS total_complaints,
    COUNT(c.id) FILTER (
      WHERE c.status IN ('CLOSED', 'CLOSED_UNVERIFIED')
        AND c.updated_at <= c.sla_deadline
    )                                                           AS resolved_within_sla,
    COUNT(c.id) FILTER (
      WHERE c.sla_deadline IS NOT NULL
        AND c.updated_at > c.sla_deadline
        AND c.status NOT IN ('NEW', 'CLASSIFIED')
    )                                                           AS sla_breached,
    ROUND(
      100.0 * COUNT(c.id) FILTER (
        WHERE c.status IN ('CLOSED', 'CLOSED_UNVERIFIED')
          AND c.updated_at <= c.sla_deadline
      ) / NULLIF(COUNT(c.id), 0),
      1
    )                                                            AS compliance_pct
  FROM complaints c
  JOIN complaint_departments cd ON cd.complaint_id = c.id
  JOIN departments d             ON d.id = cd.department_id
  WHERE
    (from_date IS NULL OR c.created_at >= from_date::TIMESTAMPTZ)
    AND (to_date IS NULL OR c.created_at <= (to_date::TIMESTAMPTZ + INTERVAL '1 day'))
  GROUP BY d.id, d.name
  ORDER BY compliance_pct ASC NULLS LAST;
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;

-- ── complaint_volume_series ───────────────────────────────────────────
-- Returns complaint count grouped by time period (day/week/month).
-- Optional filters: category and ward_id.
CREATE OR REPLACE FUNCTION complaint_volume_series(
  group_by        TEXT    DEFAULT 'day',
  filter_category TEXT    DEFAULT NULL,
  filter_ward_id  UUID    DEFAULT NULL
)
RETURNS TABLE (
  period     TEXT,
  count      BIGINT,
  category   TEXT,
  ward_name  TEXT
) AS $$
DECLARE
  trunc_unit TEXT;
BEGIN
  trunc_unit := CASE group_by
    WHEN 'week'  THEN 'week'
    WHEN 'month' THEN 'month'
    ELSE 'day'
  END;

  RETURN QUERY
  EXECUTE format(
    $sql$
    SELECT
      TO_CHAR(DATE_TRUNC($1, c.created_at), 'YYYY-MM-DD') AS period,
      COUNT(*)                                              AS count,
      c.category::TEXT,
      w.name::TEXT                                          AS ward_name
    FROM complaints c
    LEFT JOIN wards w ON w.id = c.ward_id
    WHERE
      ($2 IS NULL OR c.category = $2)
      AND ($3 IS NULL OR c.ward_id = $3)
    GROUP BY DATE_TRUNC($1, c.created_at), c.category, w.name
    ORDER BY DATE_TRUNC($1, c.created_at) DESC
    $sql$
  ) USING trunc_unit, filter_category, filter_ward_id;
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;

-- ── ward_complaint_density ────────────────────────────────────────────
-- Returns complaint count per ward — public endpoint, no PII.
CREATE OR REPLACE FUNCTION ward_complaint_density(
  filter_category TEXT DEFAULT NULL
)
RETURNS TABLE (
  ward_id    UUID,
  ward_name  TEXT,
  count      BIGINT
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    w.id                    AS ward_id,
    w.name::TEXT            AS ward_name,
    COUNT(c.id)             AS count
  FROM wards w
  LEFT JOIN complaints c ON c.ward_id = w.id
    AND c.status NOT IN ('CLOSED', 'CLOSED_UNVERIFIED')
    AND (filter_category IS NULL OR c.category = filter_category)
  GROUP BY w.id, w.name
  ORDER BY count DESC;
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;

-- ── get_complaints_with_coords_last_90_days ───────────────────────────
-- Returns lat/lng + metadata for all complaints in last 90 days.
-- Used by the nightly Predictive Agent DBSCAN clustering.
CREATE OR REPLACE FUNCTION get_complaints_with_coords_last_90_days()
RETURNS TABLE (
  id          UUID,
  category    VARCHAR,
  urgency     SMALLINT,
  lat         DOUBLE PRECISION,
  lng         DOUBLE PRECISION,
  ward_id     UUID,
  created_at  TIMESTAMPTZ
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    c.id,
    c.category,
    c.urgency,
    ST_Y(c.location::geometry) AS lat,
    ST_X(c.location::geometry) AS lng,
    c.ward_id,
    c.created_at
  FROM complaints c
  WHERE
    c.created_at >= NOW() - INTERVAL '90 days'
    AND c.location IS NOT NULL
  ORDER BY c.created_at DESC;
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;
