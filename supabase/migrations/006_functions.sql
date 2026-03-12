-- ============================================================
-- PS-CRM PostgreSQL Functions Migration 006
-- Called from FastAPI backend via supabase.rpc()
-- ============================================================

-- ============================================================
-- Find assets near a GPS point (within radius)
-- Used by GeoSpatial logic in complaint intake
-- ============================================================
CREATE OR REPLACE FUNCTION find_nearby_assets(
  lat          DOUBLE PRECISION,
  lng          DOUBLE PRECISION,
  radius_m     INTEGER DEFAULT 50,
  p_asset_type VARCHAR DEFAULT NULL
)
RETURNS TABLE (
  id            UUID,
  asset_type    VARCHAR,
  ward_id       UUID,
  department_id UUID,
  external_ref  VARCHAR,
  metadata      JSONB,
  distance_meters DOUBLE PRECISION
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    a.id,
    a.asset_type,
    a.ward_id,
    a.department_id,
    a.external_ref,
    a.metadata,
    ST_Distance(
      a.location::geography,
      ST_SetSRID(ST_Point(lng, lat), 4326)::geography
    ) AS distance_meters
  FROM assets a
  WHERE
    ST_DWithin(
      a.location::geography,
      ST_SetSRID(ST_Point(lng, lat), 4326)::geography,
      radius_m
    )
    AND (p_asset_type IS NULL OR a.asset_type = p_asset_type)
  ORDER BY distance_meters ASC
  LIMIT 10;
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;

-- ============================================================
-- Find which ward contains a GPS point
-- ============================================================
CREATE OR REPLACE FUNCTION find_ward_for_point(
  lat DOUBLE PRECISION,
  lng DOUBLE PRECISION
)
RETURNS UUID AS $$
  SELECT id
  FROM wards
  WHERE ST_Contains(
    boundary,
    ST_SetSRID(ST_Point(lng, lat), 4326)
  )
  LIMIT 1;
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- ============================================================
-- Get complaints within bounding box (for public map heatmap)
-- Returns only non-closed complaints, no PII
-- ============================================================
CREATE OR REPLACE FUNCTION get_complaints_in_bounds(
  min_lat DOUBLE PRECISION,
  min_lng DOUBLE PRECISION,
  max_lat DOUBLE PRECISION,
  max_lng DOUBLE PRECISION
)
RETURNS TABLE (
  id          UUID,
  grievance_id VARCHAR,
  category    VARCHAR,
  urgency     SMALLINT,
  status      VARCHAR,
  lat         DOUBLE PRECISION,
  lng         DOUBLE PRECISION,
  ward_id     UUID
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    c.id,
    c.grievance_id,
    c.category,
    c.urgency,
    c.status,
    ST_Y(c.location::geometry) AS lat,
    ST_X(c.location::geometry) AS lng,
    c.ward_id
  FROM complaints c
  WHERE
    c.location IS NOT NULL
    AND c.status NOT IN ('CLOSED', 'CLOSED_UNVERIFIED')
    AND ST_Within(
      c.location,
      ST_MakeEnvelope(min_lng, min_lat, max_lng, max_lat, 4326)
    );
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;

-- ============================================================
-- Get complaint volume by day/week/month (for analytics chart)
-- ============================================================
CREATE OR REPLACE FUNCTION get_complaint_volume(
  start_date   DATE,
  end_date     DATE,
  group_by     VARCHAR DEFAULT 'day',   -- 'day' | 'week' | 'month'
  p_category   VARCHAR DEFAULT NULL,
  p_ward_id    UUID    DEFAULT NULL
)
RETURNS TABLE (
  period        TEXT,
  complaint_count BIGINT,
  category      VARCHAR
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    CASE group_by
      WHEN 'week'  THEN TO_CHAR(DATE_TRUNC('week',  created_at), 'YYYY-WW')
      WHEN 'month' THEN TO_CHAR(DATE_TRUNC('month', created_at), 'YYYY-MM')
      ELSE              TO_CHAR(DATE_TRUNC('day',   created_at), 'YYYY-MM-DD')
    END AS period,
    COUNT(*)::BIGINT AS complaint_count,
    COALESCE(category, 'other') AS category
  FROM complaints
  WHERE
    created_at::date BETWEEN start_date AND end_date
    AND (p_category IS NULL OR category = p_category)
    AND (p_ward_id  IS NULL OR ward_id  = p_ward_id)
  GROUP BY 1, 3
  ORDER BY 1 ASC;
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;

-- ============================================================
-- Get SLA compliance stats per department
-- ============================================================
CREATE OR REPLACE FUNCTION get_sla_compliance(
  start_date    DATE,
  end_date      DATE,
  p_department_id UUID DEFAULT NULL
)
RETURNS TABLE (
  department_id   UUID,
  department_name VARCHAR,
  total_complaints BIGINT,
  resolved_within_sla BIGINT,
  sla_breached    BIGINT,
  compliance_pct  NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    d.id AS department_id,
    d.name AS department_name,
    COUNT(cd.id)::BIGINT AS total_complaints,
    COUNT(CASE
      WHEN c.status IN ('CLOSED', 'CLOSED_UNVERIFIED')
        AND (c.updated_at <= c.sla_deadline OR c.sla_deadline IS NULL)
      THEN 1
    END)::BIGINT AS resolved_within_sla,
    COUNT(CASE
      WHEN c.sla_deadline IS NOT NULL
        AND NOW() > c.sla_deadline
        AND c.status NOT IN ('CLOSED', 'CLOSED_UNVERIFIED')
      THEN 1
    END)::BIGINT AS sla_breached,
    ROUND(
      100.0 * COUNT(CASE
        WHEN c.status IN ('CLOSED', 'CLOSED_UNVERIFIED')
          AND (c.updated_at <= c.sla_deadline OR c.sla_deadline IS NULL)
        THEN 1
      END) / NULLIF(COUNT(cd.id), 0),
      2
    ) AS compliance_pct
  FROM complaint_departments cd
  JOIN departments d ON d.id = cd.department_id
  JOIN complaints c  ON c.id = cd.complaint_id
  WHERE
    c.created_at::date BETWEEN start_date AND end_date
    AND (p_department_id IS NULL OR d.id = p_department_id)
  GROUP BY d.id, d.name
  ORDER BY d.name;
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;
