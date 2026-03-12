-- ============================================================
-- PS-CRM Seed Migration 003 — Departments
-- Fixed UUIDs for stable cross-reference in code and other seeds
-- ============================================================

INSERT INTO departments (id, name, code) VALUES
  ('a1000000-0000-0000-0000-000000000001', 'Public Works Department',  'PWD'),
  ('a1000000-0000-0000-0000-000000000002', 'Electricity Department',   'ELEC'),
  ('a1000000-0000-0000-0000-000000000003', 'Horticulture Department',  'HORT'),
  ('a1000000-0000-0000-0000-000000000004', 'Sanitation Department',    'SAN'),
  ('a1000000-0000-0000-0000-000000000005', 'Delhi Jal Board',          'DJB')
ON CONFLICT (code) DO NOTHING;
