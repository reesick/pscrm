-- ============================================================
-- 009: Seed test officers + performance indexes
-- ============================================================

-- Insert officer rows for the 4 test auth users.
-- Uses INSERT ... ON CONFLICT to make it safe to re-run.

INSERT INTO officers (id, name, email, role, department_id, ward_ids, active)
VALUES
    (
        'dec58235-0940-4575-a1ea-26be3d407dbf',
        'Test JSSA Officer',
        'test.jssa@pscrm-test.dev',
        'jssa',
        (SELECT id FROM departments LIMIT 1),
        ARRAY['b1000000-0000-0000-0000-000000000001']::uuid[],
        true
    ),
    (
        '2def42aa-cc73-441a-913a-6e6ecc903290',
        'Test AA Officer',
        'test.aa@pscrm-test.dev',
        'aa',
        NULL,
        ARRAY['b1000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000002']::uuid[],
        true
    ),
    (
        'a805eab1-f3e7-45cb-b0f8-e91b3ad09618',
        'Test Super Admin',
        'test.superadmin@pscrm-test.dev',
        'super_admin',
        NULL,
        '{}'::uuid[],
        true
    ),
    (
        'f8094e08-15ab-4157-9c1b-3316a9e14a3c',
        'Test Contractor Officer',
        'test.contractor@pscrm-test.dev',
        'contractor',
        NULL,
        '{}'::uuid[],
        true
    )
ON CONFLICT (id) DO UPDATE SET
    role     = EXCLUDED.role,
    ward_ids = EXCLUDED.ward_ids,
    active   = EXCLUDED.active;

-- Also ensure a contractors row exists for the contractor test user
INSERT INTO contractors (id, name, contact_email, active)
VALUES (
    'f8094e08-15ab-4157-9c1b-3316a9e14a3c',
    'Test Contractor',
    'test.contractor@pscrm-test.dev',
    true
)
ON CONFLICT (id) DO NOTHING;

-- Performance indexes (idempotent — already exist from 001_schema but ensuring)
CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints(status);
CREATE INDEX IF NOT EXISTS idx_complaints_ward_id ON complaints(ward_id);
