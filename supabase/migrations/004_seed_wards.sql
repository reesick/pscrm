-- ============================================================
-- PS-CRM Seed Migration 004 — Delhi MCD Wards (3 wards)
-- Fixed UUIDs for stable cross-reference
-- Real Delhi ward areas with simplified polygon boundaries
-- ============================================================

INSERT INTO wards (id, name, ward_number, boundary, primary_department_id) VALUES
(
  'b1000000-0000-0000-0000-000000000001',
  'Connaught Place',
  1,
  ST_GeomFromText(
    'POLYGON((77.195 28.625, 77.225 28.625, 77.225 28.645, 77.195 28.645, 77.195 28.625))',
    4326
  ),
  'a1000000-0000-0000-0000-000000000001'
),
(
  'b1000000-0000-0000-0000-000000000002',
  'Karol Bagh',
  2,
  ST_GeomFromText(
    'POLYGON((77.175 28.640, 77.210 28.640, 77.210 28.660, 77.175 28.660, 77.175 28.640))',
    4326
  ),
  'a1000000-0000-0000-0000-000000000001'
),
(
  'b1000000-0000-0000-0000-000000000003',
  'Lajpat Nagar',
  3,
  ST_GeomFromText(
    'POLYGON((77.230 28.558, 77.258 28.558, 77.258 28.578, 77.230 28.578, 77.230 28.558))',
    4326
  ),
  'a1000000-0000-0000-0000-000000000001'
)
ON CONFLICT (ward_number) DO NOTHING;
