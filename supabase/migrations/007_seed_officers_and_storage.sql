-- ============================================================
-- 007: Seed officers (matching real auth users) + storage bucket
-- ============================================================

-- Storage bucket for complaint proof photos
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'complaint-proofs',
    'complaint-proofs',
    false,
    10485760,
    ARRAY['image/jpeg', 'image/png', 'image/webp', 'video/mp4']
)
ON CONFLICT (id) DO NOTHING;

-- Storage RLS: use storage.objects RLS policies (not storage.policies table)
-- The storage.policies table doesn't exist on Supabase Cloud;
-- storage access is controlled via RLS on storage.objects.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE policyname = 'Officers can upload proofs'
      AND tablename  = 'objects'
      AND schemaname = 'storage'
  ) THEN
    CREATE POLICY "Officers can upload proofs"
      ON storage.objects
      FOR INSERT
      TO authenticated
      WITH CHECK (bucket_id = 'complaint-proofs');
  END IF;
END$$;

-- ============================================================
-- Officers — auth user UUIDs from app/tests/test1.py JWTs
-- ============================================================
INSERT INTO officers (id, name, email, role, department_id, ward_ids, active)
VALUES
    -- super_admin: full access, no department/ward scope
    (
        '27bb176b-4edb-4895-ad73-f80af2999496',
        'Super Admin',
        'super_admin@pscrm.com',
        'super_admin',
        NULL,
        '{}'::uuid[],
        true
    ),
    -- jssa: field officer in Connaught Place ward, Public Works Department
    (
        '8b584522-073a-4ced-9ec4-1d65de9280e9',
        'JSSA Officer',
        'jssa@pscrm.com',
        'jssa',
        'a1000000-0000-0000-0000-000000000001',  -- Public Works Department
        ARRAY['b1000000-0000-0000-0000-000000000001']::uuid[],  -- Connaught Place ward
        true
    ),
    -- aa: administrative authority, zone-level (all 3 wards)
    (
        'c0e8cc83-c3ae-44d4-8b9a-c9dde19cc607',
        'AA Officer',
        'aa@pscrm.com',
        'aa',
        NULL,
        ARRAY[
            'b1000000-0000-0000-0000-000000000001',
            'b1000000-0000-0000-0000-000000000002',
            'b1000000-0000-0000-0000-000000000003'
        ]::uuid[],
        true
    ),
    -- faa: field appraisal authority, zone-level (all 3 wards)
    (
        'c3f1753e-3802-4e5e-8645-914a6e88032e',
        'FAA Officer',
        'faa@pscrm.com',
        'faa',
        NULL,
        ARRAY[
            'b1000000-0000-0000-0000-000000000001',
            'b1000000-0000-0000-0000-000000000002',
            'b1000000-0000-0000-0000-000000000003'
        ]::uuid[],
        true
    )
ON CONFLICT (id) DO UPDATE SET
    role       = EXCLUDED.role,
    ward_ids   = EXCLUDED.ward_ids,
    active     = EXCLUDED.active;
