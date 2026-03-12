-- ============================================================
-- PS-CRM RLS Policies Migration 002
-- Row Level Security for all tables
-- ============================================================

-- Enable RLS on all tables
ALTER TABLE departments        ENABLE ROW LEVEL SECURITY;
ALTER TABLE wards              ENABLE ROW LEVEL SECURITY;
ALTER TABLE officers           ENABLE ROW LEVEL SECURITY;
ALTER TABLE contractors        ENABLE ROW LEVEL SECURITY;
ALTER TABLE assets             ENABLE ROW LEVEL SECURITY;
ALTER TABLE complaints         ENABLE ROW LEVEL SECURITY;
ALTER TABLE complaint_departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE complaint_events   ENABLE ROW LEVEL SECURITY;
ALTER TABLE hotspots           ENABLE ROW LEVEL SECURITY;
ALTER TABLE work_orders        ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- HELPER FUNCTIONS  (SECURITY DEFINER — run as superuser)
-- ============================================================

-- Get current authenticated user's role (from officers table)
CREATE OR REPLACE FUNCTION public.get_user_role()
RETURNS TEXT AS $$
  SELECT role FROM officers WHERE id = auth.uid() AND active = TRUE
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- Get current authenticated user's ward_ids (from officers table)
CREATE OR REPLACE FUNCTION public.get_user_ward_ids()
RETURNS UUID[] AS $$
  SELECT COALESCE(ward_ids, '{}') FROM officers WHERE id = auth.uid()
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- Check if current user is an active officer
CREATE OR REPLACE FUNCTION public.is_officer()
RETURNS BOOLEAN AS $$
  SELECT EXISTS(SELECT 1 FROM officers WHERE id = auth.uid() AND active = TRUE)
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- Check if current user is an active contractor
CREATE OR REPLACE FUNCTION public.is_contractor()
RETURNS BOOLEAN AS $$
  SELECT EXISTS(SELECT 1 FROM contractors WHERE id = auth.uid() AND active = TRUE)
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- ============================================================
-- DEPARTMENTS  — public read, service role write
-- ============================================================
CREATE POLICY departments_public_read ON departments
  FOR SELECT USING (TRUE);

-- ============================================================
-- WARDS  — public read
-- ============================================================
CREATE POLICY wards_public_read ON wards
  FOR SELECT USING (TRUE);

-- ============================================================
-- ASSETS  — authenticated read
-- ============================================================
CREATE POLICY assets_authenticated_read ON assets
  FOR SELECT TO authenticated USING (TRUE);

-- ============================================================
-- COMPLAINTS
-- ============================================================

-- Public SELECT (for /track/[grievance_id] without login)
CREATE POLICY complaints_public_select ON complaints
  FOR SELECT USING (TRUE);

-- Officers can insert (service role backend bypasses this anyway)
CREATE POLICY complaints_officer_insert ON complaints
  FOR INSERT TO authenticated
  WITH CHECK (public.is_officer());

-- Update: scoped by role
CREATE POLICY complaints_officer_update ON complaints
  FOR UPDATE TO authenticated
  USING (
    public.get_user_role() IN ('super_admin', 'faa', 'aa')
    OR (
      public.get_user_role() = 'jssa'
      AND ward_id = ANY(public.get_user_ward_ids())
    )
  );

-- ============================================================
-- COMPLAINT_DEPARTMENTS
-- ============================================================
CREATE POLICY cd_select ON complaint_departments
  FOR SELECT TO authenticated
  USING (
    public.get_user_role() IN ('super_admin', 'faa', 'aa')
    OR officer_id = auth.uid()
    OR EXISTS (
      SELECT 1 FROM complaints c
      WHERE c.id = complaint_id
        AND c.ward_id = ANY(public.get_user_ward_ids())
    )
  );

CREATE POLICY cd_insert ON complaint_departments
  FOR INSERT TO authenticated
  WITH CHECK (public.is_officer());

CREATE POLICY cd_update ON complaint_departments
  FOR UPDATE TO authenticated
  USING (
    public.get_user_role() IN ('super_admin', 'faa', 'aa')
    OR officer_id = auth.uid()
  );

-- ============================================================
-- COMPLAINT_EVENTS  — append-only (NO UPDATE/DELETE policies = blocked)
-- ============================================================
CREATE POLICY events_public_select ON complaint_events
  FOR SELECT USING (TRUE);

CREATE POLICY events_insert ON complaint_events
  FOR INSERT TO authenticated
  WITH CHECK (TRUE);
-- Intentionally no UPDATE or DELETE policy — immutable audit trail

-- ============================================================
-- OFFICERS
-- ============================================================
CREATE POLICY officers_self_or_admin_read ON officers
  FOR SELECT TO authenticated
  USING (
    id = auth.uid()
    OR public.get_user_role() IN ('super_admin', 'faa', 'aa')
  );

CREATE POLICY officers_super_admin_all ON officers
  FOR ALL TO authenticated
  USING (public.get_user_role() = 'super_admin')
  WITH CHECK (public.get_user_role() = 'super_admin');

-- ============================================================
-- CONTRACTORS
-- ============================================================
CREATE POLICY contractors_self_or_admin_read ON contractors
  FOR SELECT TO authenticated
  USING (
    id = auth.uid()
    OR public.get_user_role() IN ('super_admin', 'faa')
  );

CREATE POLICY contractors_super_admin_all ON contractors
  FOR ALL TO authenticated
  USING (public.get_user_role() = 'super_admin')
  WITH CHECK (public.get_user_role() = 'super_admin');

-- ============================================================
-- HOTSPOTS  — super admin only
-- ============================================================
CREATE POLICY hotspots_super_admin ON hotspots
  FOR ALL TO authenticated
  USING (public.get_user_role() = 'super_admin');

-- ============================================================
-- WORK_ORDERS
-- ============================================================
CREATE POLICY work_orders_select ON work_orders
  FOR SELECT TO authenticated
  USING (
    public.get_user_role() IN ('super_admin', 'faa', 'aa')
    OR (public.is_contractor() AND contractor_id = auth.uid())
  );

CREATE POLICY work_orders_faa_insert ON work_orders
  FOR INSERT TO authenticated
  WITH CHECK (public.get_user_role() IN ('faa', 'super_admin'));

CREATE POLICY work_orders_update ON work_orders
  FOR UPDATE TO authenticated
  USING (public.get_user_role() IN ('super_admin', 'faa'));
