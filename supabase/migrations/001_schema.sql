-- ============================================================
-- PS-CRM Schema Migration 001
-- Smart Public Service CRM — Delhi MCD
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Auto-update updated_at trigger
CREATE OR REPLACE FUNCTION trigger_set_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- DEPARTMENTS
-- ============================================================
CREATE TABLE IF NOT EXISTS departments (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name       VARCHAR(150) NOT NULL UNIQUE,
  code       VARCHAR(20)  NOT NULL UNIQUE,
  created_at TIMESTAMPTZ  DEFAULT NOW(),
  updated_at TIMESTAMPTZ  DEFAULT NOW()
);
CREATE TRIGGER set_departments_updated_at
  BEFORE UPDATE ON departments
  FOR EACH ROW EXECUTE FUNCTION trigger_set_timestamp();

-- ============================================================
-- WARDS
-- ============================================================
CREATE TABLE IF NOT EXISTS wards (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name                  VARCHAR(100) NOT NULL,
  ward_number           INTEGER UNIQUE,
  boundary              GEOMETRY(Polygon, 4326) NOT NULL,
  primary_department_id UUID REFERENCES departments(id),
  created_at            TIMESTAMPTZ DEFAULT NOW(),
  updated_at            TIMESTAMPTZ DEFAULT NOW()
);
CREATE TRIGGER set_wards_updated_at
  BEFORE UPDATE ON wards
  FOR EACH ROW EXECUTE FUNCTION trigger_set_timestamp();
CREATE INDEX IF NOT EXISTS idx_wards_boundary ON wards USING GIST(boundary);

-- ============================================================
-- OFFICERS
-- ============================================================
CREATE TABLE IF NOT EXISTS officers (
  id               UUID PRIMARY KEY,  -- matches auth.users id
  name             VARCHAR(150) NOT NULL,
  email            VARCHAR(255) NOT NULL UNIQUE,
  role             VARCHAR(30)  NOT NULL CHECK (role IN ('jssa', 'aa', 'faa', 'super_admin')),
  department_id    UUID REFERENCES departments(id),
  ward_ids         UUID[]   DEFAULT '{}',
  active           BOOLEAN  DEFAULT TRUE,
  telegram_chat_id BIGINT,
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  updated_at       TIMESTAMPTZ DEFAULT NOW()
);
CREATE TRIGGER set_officers_updated_at
  BEFORE UPDATE ON officers
  FOR EACH ROW EXECUTE FUNCTION trigger_set_timestamp();
CREATE INDEX IF NOT EXISTS idx_officers_role ON officers(role);
CREATE INDEX IF NOT EXISTS idx_officers_active ON officers(active);

-- ============================================================
-- CONTRACTORS
-- ============================================================
CREATE TABLE IF NOT EXISTS contractors (
  id                   UUID PRIMARY KEY,  -- matches auth.users id
  name                 VARCHAR(150) NOT NULL,
  contact_email        VARCHAR(255) NOT NULL,
  active               BOOLEAN DEFAULT TRUE,
  deactivation_reason  TEXT,
  telegram_chat_id     BIGINT,
  created_at           TIMESTAMPTZ DEFAULT NOW(),
  updated_at           TIMESTAMPTZ DEFAULT NOW()
);
CREATE TRIGGER set_contractors_updated_at
  BEFORE UPDATE ON contractors
  FOR EACH ROW EXECUTE FUNCTION trigger_set_timestamp();

-- ============================================================
-- ASSETS  (Infrastructure Asset Registry)
-- ============================================================
CREATE TABLE IF NOT EXISTS assets (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  asset_type    VARCHAR(80) NOT NULL CHECK (asset_type IN (
                  'pole', 'drain', 'road_segment', 'tree', 'water_main', 'garbage_point'
                )),
  location      GEOMETRY(Point, 4326) NOT NULL,
  ward_id       UUID REFERENCES wards(id),
  department_id UUID REFERENCES departments(id),
  external_ref  VARCHAR(100),
  metadata      JSONB DEFAULT '{}',
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE TRIGGER set_assets_updated_at
  BEFORE UPDATE ON assets
  FOR EACH ROW EXECUTE FUNCTION trigger_set_timestamp();
CREATE INDEX IF NOT EXISTS idx_assets_location   ON assets USING GIST(location);
CREATE INDEX IF NOT EXISTS idx_assets_ward_id    ON assets(ward_id);
CREATE INDEX IF NOT EXISTS idx_assets_type       ON assets(asset_type);

-- ============================================================
-- COMPLAINTS  (Central table)
-- ============================================================
CREATE TABLE IF NOT EXISTS complaints (
  id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  grievance_id              VARCHAR(50)  NOT NULL UNIQUE,
  citizen_phone_hash        VARCHAR(64),
  citizen_email_hash        VARCHAR(64),
  citizen_telegram_chat_id  BIGINT,
  raw_text                  TEXT NOT NULL,
  translated_text           TEXT,
  category                  VARCHAR(100),
  urgency                   SMALLINT DEFAULT 3 CHECK (urgency BETWEEN 1 AND 5),
  status                    VARCHAR(50) NOT NULL DEFAULT 'NEW' CHECK (status IN (
                              'NEW', 'CLASSIFIED', 'ASSIGNED', 'IN_PROGRESS',
                              'MID_SURVEY_PENDING', 'FINAL_SURVEY_PENDING',
                              'ESCALATED', 'REOPENED', 'CLOSED', 'CLOSED_UNVERIFIED'
                            )),
  channel                   VARCHAR(20) NOT NULL CHECK (channel IN ('telegram', 'web', 'call')),
  location                  GEOMETRY(Point, 4326),
  ward_id                   UUID REFERENCES wards(id),
  asset_ids                 UUID[]   DEFAULT '{}',
  media_urls                TEXT[]   DEFAULT '{}',
  sla_deadline              TIMESTAMPTZ,
  llm_used                  BOOLEAN  DEFAULT FALSE,
  classification_confidence FLOAT    DEFAULT 0.0,
  needs_human_review        BOOLEAN  DEFAULT FALSE,
  created_at                TIMESTAMPTZ DEFAULT NOW(),
  updated_at                TIMESTAMPTZ DEFAULT NOW()
);
CREATE TRIGGER set_complaints_updated_at
  BEFORE UPDATE ON complaints
  FOR EACH ROW EXECUTE FUNCTION trigger_set_timestamp();
CREATE INDEX IF NOT EXISTS idx_complaints_status       ON complaints(status);
CREATE INDEX IF NOT EXISTS idx_complaints_ward_id      ON complaints(ward_id);
CREATE INDEX IF NOT EXISTS idx_complaints_urgency      ON complaints(urgency);
CREATE INDEX IF NOT EXISTS idx_complaints_sla          ON complaints(sla_deadline);
CREATE INDEX IF NOT EXISTS idx_complaints_grievance_id ON complaints(grievance_id);
CREATE INDEX IF NOT EXISTS idx_complaints_location     ON complaints USING GIST(location);
CREATE INDEX IF NOT EXISTS idx_complaints_created_at   ON complaints(created_at DESC);

-- ============================================================
-- COMPLAINT_DEPARTMENTS  (Junction: one row per dept per complaint)
-- ============================================================
CREATE TABLE IF NOT EXISTS complaint_departments (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  complaint_id  UUID NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
  department_id UUID NOT NULL REFERENCES departments(id),
  officer_id    UUID REFERENCES officers(id),
  sub_status    VARCHAR(50) NOT NULL DEFAULT 'PENDING',
  sla_deadline  TIMESTAMPTZ,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE TRIGGER set_cd_updated_at
  BEFORE UPDATE ON complaint_departments
  FOR EACH ROW EXECUTE FUNCTION trigger_set_timestamp();
CREATE INDEX IF NOT EXISTS idx_cd_complaint_id ON complaint_departments(complaint_id);
CREATE INDEX IF NOT EXISTS idx_cd_officer_id   ON complaint_departments(officer_id);
CREATE INDEX IF NOT EXISTS idx_cd_dept_id      ON complaint_departments(department_id);

-- ============================================================
-- COMPLAINT_EVENTS  (Immutable append-only audit log)
-- ============================================================
CREATE TABLE IF NOT EXISTS complaint_events (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  complaint_id UUID NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
  event_type   VARCHAR(80) NOT NULL,
  actor_type   VARCHAR(30) NOT NULL CHECK (actor_type IN ('agent', 'officer', 'citizen', 'system')),
  actor_id     VARCHAR(255),
  from_status  VARCHAR(50),
  to_status    VARCHAR(50),
  payload      JSONB DEFAULT '{}',
  created_at   TIMESTAMPTZ DEFAULT NOW()
  -- NO updated_at — this table is immutable
);
CREATE INDEX IF NOT EXISTS idx_events_complaint_id ON complaint_events(complaint_id);
CREATE INDEX IF NOT EXISTS idx_events_event_type   ON complaint_events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_created_at   ON complaint_events(created_at);

-- ============================================================
-- HOTSPOTS  (Predictive analytics output)
-- ============================================================
CREATE TABLE IF NOT EXISTS hotspots (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  center         GEOMETRY(Point, 4326) NOT NULL,
  radius_meters  INTEGER NOT NULL,
  category       VARCHAR(100) NOT NULL,
  complaint_count INTEGER NOT NULL,
  severity       SMALLINT NOT NULL CHECK (severity BETWEEN 1 AND 5),
  ward_id        UUID REFERENCES wards(id),
  is_active      BOOLEAN  DEFAULT TRUE,
  detected_at    TIMESTAMPTZ DEFAULT NOW(),
  resolved_at    TIMESTAMPTZ,
  created_at     TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_hotspots_active ON hotspots(is_active);
CREATE INDEX IF NOT EXISTS idx_hotspots_center ON hotspots USING GIST(center);

-- ============================================================
-- WORK_ORDERS  (FAA tender flow)
-- ============================================================
CREATE TABLE IF NOT EXISTS work_orders (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  complaint_ids  UUID[]   NOT NULL,
  contractor_id  UUID REFERENCES contractors(id),
  scope          TEXT,
  estimated_cost NUMERIC(12, 2),
  status         VARCHAR(50) DEFAULT 'PENDING_APPROVAL' CHECK (status IN (
                   'PENDING_APPROVAL', 'APPROVED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED'
                 )),
  created_by     UUID REFERENCES officers(id),
  approved_by    UUID REFERENCES officers(id),
  created_at     TIMESTAMPTZ DEFAULT NOW(),
  updated_at     TIMESTAMPTZ DEFAULT NOW()
);
CREATE TRIGGER set_wo_updated_at
  BEFORE UPDATE ON work_orders
  FOR EACH ROW EXECUTE FUNCTION trigger_set_timestamp();
