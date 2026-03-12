"""
Seed officer rows for the 4 test auth users so that
get_current_user can resolve their role/ward from the officers table.

Safe to re-run — uses upsert (ON CONFLICT DO UPDATE).
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from supabase._async.client import create_client as create_async_client


SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

WARD_1 = "b1000000-0000-0000-0000-000000000001"
WARD_2 = "b1000000-0000-0000-0000-000000000002"


async def main():
    sb = await create_async_client(SUPABASE_URL, SUPABASE_KEY)

    # Get a department_id to use for JSSA officer
    dept = await sb.table("departments").select("id").limit(1).execute()
    dept_id = dept.data[0]["id"] if dept.data else None
    print(f"Using department_id: {dept_id}")

    officers = [
        {
            "id": "dec58235-0940-4575-a1ea-26be3d407dbf",
            "name": "Test JSSA Officer",
            "email": "test.jssa@pscrm-test.dev",
            "role": "jssa",
            "department_id": dept_id,
            "ward_ids": [WARD_1],
            "active": True,
        },
        {
            "id": "2def42aa-cc73-441a-913a-6e6ecc903290",
            "name": "Test AA Officer",
            "email": "test.aa@pscrm-test.dev",
            "role": "aa",
            "department_id": None,
            "ward_ids": [WARD_1, WARD_2],
            "active": True,
        },
        {
            "id": "a805eab1-f3e7-45cb-b0f8-e91b3ad09618",
            "name": "Test Super Admin",
            "email": "test.superadmin@pscrm-test.dev",
            "role": "super_admin",
            "department_id": None,
            "ward_ids": [],
            "active": True,
        },
        {
            "id": "f8094e08-15ab-4157-9c1b-3316a9e14a3c",
            "name": "Test Contractor Officer",
            "email": "test.contractor@pscrm-test.dev",
            "role": "contractor",
            "department_id": None,
            "ward_ids": [],
            "active": True,
        },
    ]

    for o in officers:
        try:
            result = await sb.table("officers").upsert(o, on_conflict="id").execute()
            print(f"  [OK] {o['role']:12s} → {o['id']}")
        except Exception as e:
            print(f"  [ERR] {o['role']:12s} → {e}")

    # Also insert a contractors row for the contractor user
    try:
        await sb.table("contractors").upsert({
            "id": "f8094e08-15ab-4157-9c1b-3316a9e14a3c",
            "name": "Test Contractor",
            "contact_email": "test.contractor@pscrm-test.dev",
            "active": True,
        }, on_conflict="id").execute()
        print(f"  [OK] contractors  → f8094e08...")
    except Exception as e:
        print(f"  [ERR] contractors → {e}")

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
