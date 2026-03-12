"""
Run migration 007: create storage bucket + seed officers
Uses supabase-py so no direct DB connection needed.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from supabase._async.client import create_client as create_async_client

SUPABASE_URL = "https://ndeaxjhcevyvgqjkiwxu.supabase.co"

# Read service role key from .env
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
service_key = None
for line in open(env_path):
    line = line.strip()
    if line.startswith("SUPABASE_SERVICE_ROLE_KEY="):
        service_key = line.split("=", 1)[1]
        break

if not service_key:
    raise SystemExit("SUPABASE_SERVICE_ROLE_KEY not found in .env")


async def main():
    sb = await create_async_client(SUPABASE_URL, service_key)

    # ── Storage bucket ────────────────────────────────────────
    print("Creating storage bucket 'complaint-proofs'...")
    try:
        await sb.storage.create_bucket(
            "complaint-proofs",
            options={"public": False, "file_size_limit": 10 * 1024 * 1024},
        )
        print("  ✅ Bucket created")
    except Exception as e:
        if "already exists" in str(e).lower() or "Duplicate" in str(e):
            print("  ℹ️  Bucket already exists — skipped")
        else:
            print(f"  ⚠️  Bucket creation error: {e}")

    # ── Officers ──────────────────────────────────────────────
    print("Seeding officers...")
    officers = [
        {
            "id":            "27bb176b-4edb-4895-ad73-f80af2999496",
            "name":          "Super Admin",
            "email":         "super_admin@pscrm.com",
            "role":          "super_admin",
            "department_id": None,
            "ward_ids":      [],
            "active":        True,
        },
        {
            "id":            "8b584522-073a-4ced-9ec4-1d65de9280e9",
            "name":          "JSSA Officer",
            "email":         "jssa@pscrm.com",
            "role":          "jssa",
            "department_id": "a1000000-0000-0000-0000-000000000001",
            "ward_ids":      ["b1000000-0000-0000-0000-000000000001"],
            "active":        True,
        },
        {
            "id":            "c0e8cc83-c3ae-44d4-8b9a-c9dde19cc607",
            "name":          "AA Officer",
            "email":         "aa@pscrm.com",
            "role":          "aa",
            "department_id": None,
            "ward_ids":      [
                "b1000000-0000-0000-0000-000000000001",
                "b1000000-0000-0000-0000-000000000002",
                "b1000000-0000-0000-0000-000000000003",
            ],
            "active":        True,
        },
        {
            "id":            "c3f1753e-3802-4e5e-8645-914a6e88032e",
            "name":          "FAA Officer",
            "email":         "faa@pscrm.com",
            "role":          "faa",
            "department_id": None,
            "ward_ids":      [
                "b1000000-0000-0000-0000-000000000001",
                "b1000000-0000-0000-0000-000000000002",
                "b1000000-0000-0000-0000-000000000003",
            ],
            "active":        True,
        },
    ]

    result = await sb.table("officers").upsert(officers, on_conflict="id").execute()
    if result.data:
        print(f"  ✅ {len(result.data)} officer(s) upserted")
        for row in result.data:
            print(f"     {row['role']:12} {row['email']}")
    else:
        print(f"  ⚠️  Upsert returned no data: {result}")


if __name__ == "__main__":
    asyncio.run(main())
