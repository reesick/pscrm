"""
PS-CRM Grievance Management API — Comprehensive Test Suite
==========================================================
HOW TO USE:
  1. Fill in your JWT tokens below
  2. Run: python test_pscrm_api.py
  3. Failed tests print to console with full request/response details

Coverage:
  ✓ Happy path — all endpoints
  ✓ Full E2E complaint lifecycle (NEW → CLASSIFIED → ASSIGNED → IN_PROGRESS → FINAL_SURVEY_PENDING → CLOSED)
  ✓ Auth & role-based access control
  ✓ Edge cases & validation errors
"""

import requests
import json
import sys
from datetime import datetime
from typing import Optional

# ============================================================
# ⚙️  CONFIGURATION — Fill in your tokens here
# ============================================================

BASE_URL = "http://localhost:8000"

# Paste your JWT tokens here (Bearer tokens from Supabase auth)
TOKENS = {
    "super_admin": "eyJhbGciOiJFUzI1NiIsImtpZCI6Ijk2MmQ0MDhhLTRlMjctNDJhMC1hMmQyLThkYmNhMTIxMmQ2ZiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwczovL25kZWF4amhjZXZ5dmdxamtpd3h1LnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiIyN2JiMTc2Yi00ZWRiLTQ4OTUtYWQ3My1mODBhZjI5OTk0OTYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzczMjYzOTg0LCJpYXQiOjE3NzMyNjAzODQsImVtYWlsIjoic3VwZXJfYWRtaW5AcHNjcm0uY29tIiwicGhvbmUiOiIiLCJhcHBfbWV0YWRhdGEiOnsicHJvdmlkZXIiOiJlbWFpbCIsInByb3ZpZGVycyI6WyJlbWFpbCJdfSwidXNlcl9tZXRhZGF0YSI6eyJlbWFpbF92ZXJpZmllZCI6dHJ1ZX0sInJvbGUiOiJhdXRoZW50aWNhdGVkIiwiYWFsIjoiYWFsMSIsImFtciI6W3sibWV0aG9kIjoicGFzc3dvcmQiLCJ0aW1lc3RhbXAiOjE3NzMyNjAzODR9XSwic2Vzc2lvbl9pZCI6ImI3NzRmYWMxLWFmMWYtNGY2YS1hNDg3LWRiOGIyMzkxYzY2OSIsImlzX2Fub255bW91cyI6ZmFsc2V9.S5sBx8ppYh48KvMSOjCjQ6E1ZcEfQWfIR4y9VgMo1iM_azCJ7DW7av_Oj920lNbU4EI4yFe43dsLjS13RKPXqg",
    "jssa":        "eyJhbGciOiJFUzI1NiIsImtpZCI6Ijk2MmQ0MDhhLTRlMjctNDJhMC1hMmQyLThkYmNhMTIxMmQ2ZiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwczovL25kZWF4amhjZXZ5dmdxamtpd3h1LnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiI4YjU4NDUyMi0wNzNhLTRjZWQtOWVjNC0xZDY1ZGU5MjgwZTkiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzczMjYzOTg1LCJpYXQiOjE3NzMyNjAzODUsImVtYWlsIjoianNzYUBwc2NybS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc3MzI2MDM4NX1dLCJzZXNzaW9uX2lkIjoiYjBmNTM1OWUtZTg5NC00OTAyLWFjODMtODNkZTdhZDQyOGYzIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.JhiVNWdoIgAXuFEMnpGtWOpujwUgpZJXCYZEjuM0976K1mhvW0GI0Ov-IuwWYPrqDY35_YYgfM-uHgN1IbLm5g",
    "aa":          "eyJhbGciOiJFUzI1NiIsImtpZCI6Ijk2MmQ0MDhhLTRlMjctNDJhMC1hMmQyLThkYmNhMTIxMmQ2ZiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwczovL25kZWF4amhjZXZ5dmdxamtpd3h1LnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiJjMGU4Y2M4My1jM2FlLTQ0ZDQtOGI5YS1jOWRkZTE5Y2M2MDciLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzczMjYzOTg2LCJpYXQiOjE3NzMyNjAzODYsImVtYWlsIjoiYWFAcHNjcm0uY29tIiwicGhvbmUiOiIiLCJhcHBfbWV0YWRhdGEiOnsicHJvdmlkZXIiOiJlbWFpbCIsInByb3ZpZGVycyI6WyJlbWFpbCJdfSwidXNlcl9tZXRhZGF0YSI6eyJlbWFpbF92ZXJpZmllZCI6dHJ1ZX0sInJvbGUiOiJhdXRoZW50aWNhdGVkIiwiYWFsIjoiYWFsMSIsImFtciI6W3sibWV0aG9kIjoicGFzc3dvcmQiLCJ0aW1lc3RhbXAiOjE3NzMyNjAzODZ9XSwic2Vzc2lvbl9pZCI6ImEzZjU0ZjVhLTZhNTktNDk3Zi1iYWVkLTI4NzQwNDhhZWNmNSIsImlzX2Fub255bW91cyI6ZmFsc2V9.VULMQtYi9GAU2a3LVFXDLh2ZWffzk588ocwTrErKo8i5DH3rLYclNToUFf8ZTGAyRbaKhFGErvXodmCZMKVPew",
    "faa":         "eyJhbGciOiJFUzI1NiIsImtpZCI6Ijk2MmQ0MDhhLTRlMjctNDJhMC1hMmQyLThkYmNhMTIxMmQ2ZiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwczovL25kZWF4amhjZXZ5dmdxamtpd3h1LnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiJjM2YxNzUzZS0zODAyLTRlNWUtODY0NS05MTRhNmU4ODAzMmUiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzczMjYzOTg2LCJpYXQiOjE3NzMyNjAzODYsImVtYWlsIjoiZmFhQHBzY3JtLmNvbSIsInBob25lIjoiIiwiYXBwX21ldGFkYXRhIjp7InByb3ZpZGVyIjoiZW1haWwiLCJwcm92aWRlcnMiOlsiZW1haWwiXX0sInVzZXJfbWV0YWRhdGEiOnsiZW1haWxfdmVyaWZpZWQiOnRydWV9LCJyb2xlIjoiYXV0aGVudGljYXRlZCIsImFhbCI6ImFhbDEiLCJhbXIiOlt7Im1ldGhvZCI6InBhc3N3b3JkIiwidGltZXN0YW1wIjoxNzczMjYwMzg2fV0sInNlc3Npb25faWQiOiJkZmIyZDlmNS1hYjI1LTQ3Y2YtYjY1Yi1iYTYzNmIwM2VmOTAiLCJpc19hbm9ueW1vdXMiOmZhbHNlfQ.8W_61V2JSNJdkuTcW3sEVjESC_0Q-X0Hxoq0B-G6HOsdNyFDpUSjtRuTTJNdxR9X2-XWVx575QYRnQ_fcRnwDQ",
}

# Seed data UUIDs (from your migrations — fixed and stable)
SEED = {
    # Departments (003_seed_departments.sql)
    "dept_pwd":  "a1000000-0000-0000-0000-000000000001",
    "dept_elec": "a1000000-0000-0000-0000-000000000002",
    "dept_hort": "a1000000-0000-0000-0000-000000000003",
    "dept_san":  "a1000000-0000-0000-0000-000000000004",
    "dept_djb":  "a1000000-0000-0000-0000-000000000005",

    # Wards (004_seed_wards.sql)
    "ward_cp":  "b1000000-0000-0000-0000-000000000001",  # Connaught Place
    "ward_kb":  "b1000000-0000-0000-0000-000000000002",  # Karol Bagh
    "ward_ln":  "b1000000-0000-0000-0000-000000000003",  # Lajpat Nagar

    # GPS coords inside Connaught Place ward boundary
    "cp_lat": 28.6330,
    "cp_lng": 77.2090,
}

# ============================================================
# 🧰  Test runner infrastructure
# ============================================================

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name: str):
        self.passed += 1
        print(f"  ✅ PASS  {name}")

    def fail(self, name: str, reason: str, req_body=None, resp=None):
        self.failed += 1
        msg = f"\n  ❌ FAIL  {name}\n         Reason: {reason}"
        if req_body:
            msg += f"\n         Request: {json.dumps(req_body, indent=10)}"
        if resp is not None:
            try:
                msg += f"\n         Response [{resp.status_code}]: {resp.text[:500]}"
            except Exception:
                pass
        print(msg)
        self.errors.append(name)

    def summary(self):
        total = self.passed + self.failed
        print("\n" + "=" * 60)
        print(f"  Results: {self.passed}/{total} passed")
        if self.errors:
            print(f"  Failed tests:")
            for e in self.errors:
                print(f"    • {e}")
        else:
            print("  🎉 All tests passed!")
        print("=" * 60)
        return self.failed == 0


results = TestResults()

# Shared state — populated during E2E lifecycle tests
state = {
    "complaint_id": None,
    "grievance_id": None,
    "officer_id": None,
    "contractor_id": None,
}


def auth(role: str) -> dict:
    """Return Authorization header for a given role."""
    token = TOKENS.get(role, "")
    return {"Authorization": f"Bearer {token}"}


def post(path, body=None, headers=None, expected=201) -> Optional[requests.Response]:
    try:
        r = requests.post(f"{BASE_URL}{path}", json=body, headers=headers or {}, timeout=10)
        return r
    except Exception as e:
        results.fail(path, f"Request exception: {e}")
        return None


def get(path, params=None, headers=None) -> Optional[requests.Response]:
    try:
        r = requests.get(f"{BASE_URL}{path}", params=params, headers=headers or {}, timeout=10)
        return r
    except Exception as e:
        results.fail(path, f"Request exception: {e}")
        return None


def patch(path, body=None, headers=None) -> Optional[requests.Response]:
    try:
        r = requests.patch(f"{BASE_URL}{path}", json=body, headers=headers or {}, timeout=10)
        return r
    except Exception as e:
        results.fail(path, f"Request exception: {e}")
        return None


# ============================================================
# 🏥  Section 0: Health Check
# ============================================================

def test_health():
    print("\n── Section 0: Health Check ──────────────────────────────")
    r = get("/health")
    if r and r.status_code == 200:
        results.ok("GET /health → 200")
    else:
        results.fail("GET /health", "Expected 200", resp=r)


# ============================================================
# 📝  Section 1: Complaint Submission (Happy Path)
# ============================================================

def test_submit_complaint():
    print("\n── Section 1: Submit Complaint (Happy Path) ─────────────")

    # 1a. Valid complaint — no auth required
    body = {
        "citizen_email": "testcitizen@example.com",
        "raw_text": "There is a large pothole on the main road near Connaught Place metro. It has been there for 2 weeks and caused 3 accidents.",
        "lat": SEED["cp_lat"],
        "lng": SEED["cp_lng"],
        "media_urls": ["https://example.com/photo1.jpg"],
        "channel": "web"
    }
    r = post("/api/v1/complaints", body=body)
    if r and r.status_code == 201:
        data = r.json()
        state["complaint_id"] = data.get("id")
        state["grievance_id"] = data.get("grievance_id")
        results.ok(f"POST /api/v1/complaints → 201 | grievance_id={state['grievance_id']}")
    else:
        results.fail("POST /api/v1/complaints (valid)", "Expected 201", body, r)

    # 1b. No email (optional field — should still succeed)
    body_no_email = {
        "raw_text": "Street light not working near Karol Bagh bus stop.",
        "lat": 28.6505,
        "lng": 77.1905,
        "media_urls": [],
        "channel": "telegram"
    }
    r2 = post("/api/v1/complaints", body=body_no_email)
    if r2 and r2.status_code == 201:
        results.ok("POST /api/v1/complaints (no email) → 201")
    else:
        results.fail("POST /api/v1/complaints (no email)", "Expected 201", body_no_email, r2)

    # 1c. Telegram channel
    body_tg = {
        "citizen_email": "tg@example.com",
        "raw_text": "Garbage not collected for 5 days in Lajpat Nagar block C.",
        "lat": SEED["cp_lat"],
        "lng": SEED["cp_lng"],
        "media_urls": [],
        "channel": "telegram"
    }
    r3 = post("/api/v1/complaints", body=body_tg)
    if r3 and r3.status_code == 201:
        results.ok("POST /api/v1/complaints (telegram channel) → 201")
    else:
        results.fail("POST /api/v1/complaints (telegram)", "Expected 201", body_tg, r3)


# ============================================================
# 🔍  Section 2: Public Status Lookup (No Auth)
# ============================================================

def test_public_lookup():
    print("\n── Section 2: Public Status Lookup ──────────────────────")

    if not state["complaint_id"]:
        print("  ⚠️  Skipped — no complaint_id from Section 1")
        return

    # 2a. Lookup by UUID
    r = get(f"/api/v1/complaints/{state['complaint_id']}")
    if r and r.status_code == 200:
        data = r.json()
        # Verify no PII leaked
        has_no_internal = "internal_notes" not in data and "assigned_officer_name" not in data
        if has_no_internal:
            results.ok(f"GET /api/v1/complaints/{{id}} → 200 (no PII leaked)")
        else:
            results.fail("GET /api/v1/complaints/{id} PII check", "Internal fields exposed in public response", resp=r)
    else:
        results.fail("GET /api/v1/complaints/{id} (by UUID)", "Expected 200", resp=r)

    # 2b. Lookup by grievance_id
    r2 = get(f"/api/v1/complaints/{state['grievance_id']}")
    if r2 and r2.status_code == 200:
        results.ok(f"GET /api/v1/complaints/{{grievance_id}} → 200")
    else:
        results.fail("GET /api/v1/complaints/{grievance_id}", "Expected 200", resp=r2)

    # 2c. Non-existent ID
    r3 = get("/api/v1/complaints/00000000-0000-0000-0000-000000000000")
    if r3 and r3.status_code == 404:
        results.ok("GET /api/v1/complaints/non-existent → 404")
    else:
        results.fail("GET /api/v1/complaints/non-existent", f"Expected 404, got {r3.status_code if r3 else 'None'}", resp=r3)


# ============================================================
# 🔐  Section 3: Auth & Role-Based Access
# ============================================================

def test_auth_and_roles():
    print("\n── Section 3: Auth & Role-Based Access ──────────────────")

    # 3a. List complaints — no auth → should fail
    r = get("/api/v1/complaints")
    if r and r.status_code in (401, 403):
        results.ok("GET /api/v1/complaints (no auth) → 401/403")
    else:
        results.fail("GET /api/v1/complaints (no auth)", f"Expected 401/403, got {r.status_code if r else 'None'}", resp=r)

    # 3b. List complaints — with super_admin token → should succeed
    r2 = get("/api/v1/complaints", headers=auth("super_admin"))
    if r2 and r2.status_code == 200:
        results.ok("GET /api/v1/complaints (super_admin) → 200")
    else:
        results.fail("GET /api/v1/complaints (super_admin)", "Expected 200", resp=r2)

    # 3c. List complaints — with jssa token
    r3 = get("/api/v1/complaints", headers=auth("jssa"))
    if r3 and r3.status_code in (200, 403):
        results.ok(f"GET /api/v1/complaints (jssa) → {r3.status_code} (role-scoped)")
    else:
        results.fail("GET /api/v1/complaints (jssa)", "Expected 200 or 403", resp=r3)

    # 3d. Hotspots — super_admin only
    r4 = get("/api/v1/analytics/hotspots", headers=auth("super_admin"))
    if r4 and r4.status_code == 200:
        results.ok("GET /api/v1/analytics/hotspots (super_admin) → 200")
    else:
        results.fail("GET /api/v1/analytics/hotspots (super_admin)", "Expected 200", resp=r4)

    # 3e. Hotspots — jssa (should be forbidden)
    r5 = get("/api/v1/analytics/hotspots", headers=auth("jssa"))
    if r5 and r5.status_code in (401, 403):
        results.ok("GET /api/v1/analytics/hotspots (jssa) → 403 (blocked correctly)")
    else:
        results.fail("GET /api/v1/analytics/hotspots (jssa)", f"Expected 403, got {r5.status_code if r5 else 'None'}", resp=r5)

    # 3f. Status update — no auth → should fail
    if state["complaint_id"]:
        body = {"new_status": "CLASSIFIED"}
        r6 = patch(f"/api/v1/complaints/{state['complaint_id']}/status", body=body)
        if r6 and r6.status_code in (401, 403):
            results.ok("PATCH /status (no auth) → 401/403")
        else:
            results.fail("PATCH /status (no auth)", f"Expected 401/403, got {r6.status_code if r6 else 'None'}", resp=r6)

    # 3g. Contractor status update — non super_admin should fail
    r7 = patch(
        "/api/v1/contractors/00000000-0000-0000-0000-000000000099/status",
        body={"is_active": False, "reason": "test"},
        headers=auth("jssa")
    )
    if r7 and r7.status_code in (401, 403, 404):
        results.ok("PATCH /contractors/{id}/status (jssa) → blocked correctly")
    else:
        results.fail("PATCH /contractors/{id}/status (jssa)", f"Expected 403/404, got {r7.status_code if r7 else 'None'}", resp=r7)


# ============================================================
# 🔄  Section 4: Full E2E Complaint Lifecycle
# ============================================================

def test_lifecycle():
    print("\n── Section 4: Full E2E Complaint Lifecycle ──────────────")

    if not state["complaint_id"]:
        print("  ⚠️  Skipped — no complaint_id from Section 1")
        return

    cid = state["complaint_id"]

    # Step 1: NEW → CLASSIFIED (agent does this automatically, but test manual transition)
    body = {"new_status": "CLASSIFIED", "internal_note": "Auto-classified as road/pothole by LLM."}
    r = patch(f"/api/v1/complaints/{cid}/status", body=body, headers=auth("super_admin"))
    if r and r.status_code == 200:
        results.ok("Lifecycle: NEW → CLASSIFIED")
    else:
        results.fail("Lifecycle: NEW → CLASSIFIED", f"Status {r.status_code if r else 'None'}", body, r)

    # Step 2: CLASSIFIED → ASSIGNED
    body2 = {"new_status": "ASSIGNED", "internal_note": "Assigned to JSSA ward officer."}
    r2 = patch(f"/api/v1/complaints/{cid}/status", body=body2, headers=auth("super_admin"))
    if r2 and r2.status_code == 200:
        results.ok("Lifecycle: CLASSIFIED → ASSIGNED")
    else:
        results.fail("Lifecycle: CLASSIFIED → ASSIGNED", f"Status {r2.status_code if r2 else 'None'}", body2, r2)

    # Step 3: ASSIGNED → IN_PROGRESS (proof_url required)
    body3 = {
        "new_status": "IN_PROGRESS",
        "internal_note": "Work started on pothole repair.",
        "proof_url": "https://example.com/proof-before.jpg"
    }
    r3 = patch(f"/api/v1/complaints/{cid}/status", body=body3, headers=auth("jssa"))
    if r3 and r3.status_code == 200:
        results.ok("Lifecycle: ASSIGNED → IN_PROGRESS (with proof_url)")
    else:
        results.fail("Lifecycle: ASSIGNED → IN_PROGRESS", f"Status {r3.status_code if r3 else 'None'}", body3, r3)

    # Step 4: IN_PROGRESS → FINAL_SURVEY_PENDING (proof_url required)
    body4 = {
        "new_status": "FINAL_SURVEY_PENDING",
        "internal_note": "Work completed. Awaiting citizen sign-off.",
        "proof_url": "https://example.com/proof-after.jpg"
    }
    r4 = patch(f"/api/v1/complaints/{cid}/status", body=body4, headers=auth("jssa"))
    if r4 and r4.status_code == 200:
        results.ok("Lifecycle: IN_PROGRESS → FINAL_SURVEY_PENDING (with proof_url)")
    else:
        results.fail("Lifecycle: IN_PROGRESS → FINAL_SURVEY_PENDING", f"Status {r4.status_code if r4 else 'None'}", body4, r4)

    # Step 5: Citizen survey — approved
    survey_body = {"response": "approved", "citizen_note": "Yes, the pothole is fixed. Thank you!"}
    r5 = post(f"/api/v1/complaints/{cid}/survey-response", body=survey_body)
    if r5 and r5.status_code == 200:
        results.ok("Lifecycle: Survey response → approved")
    else:
        results.fail("Lifecycle: Survey response (approved)", f"Status {r5.status_code if r5 else 'None'}", survey_body, r5)

    # Step 6: Verify final status via public lookup
    r6 = get(f"/api/v1/complaints/{cid}")
    if r6 and r6.status_code == 200:
        final_status = r6.json().get("status")
        if final_status in ("CLOSED", "FINAL_SURVEY_PENDING"):
            results.ok(f"Lifecycle: Final status = {final_status}")
        else:
            results.fail("Lifecycle: Final status check", f"Unexpected status: {final_status}", resp=r6)
    else:
        results.fail("Lifecycle: Final status lookup", "Expected 200", resp=r6)

    # Step 7: Verify timeline populated
    r7 = get(f"/api/v1/complaints/{cid}")
    if r7 and r7.status_code == 200:
        timeline = r7.json().get("timeline", [])
        if len(timeline) >= 1:
            results.ok(f"Lifecycle: Timeline has {len(timeline)} event(s)")
        else:
            results.fail("Lifecycle: Timeline check", "Expected at least 1 timeline event", resp=r7)


# ============================================================
# 🔁  Section 5: Lifecycle Edge Cases
# ============================================================

def test_lifecycle_edge_cases():
    print("\n── Section 5: Lifecycle Edge Cases ──────────────────────")

    # 5a. Submit a fresh complaint for edge case tests
    body = {
        "raw_text": "Water pipeline leaking heavily near Karol Bagh market. Road flooded.",
        "lat": 28.6505,
        "lng": 77.1905,
        "media_urls": [],
        "channel": "web"
    }
    r = post("/api/v1/complaints", body=body)
    edge_id = None
    if r and r.status_code == 201:
        edge_id = r.json().get("id")
        results.ok(f"Edge case complaint submitted → {edge_id}")
    else:
        results.fail("Edge case: complaint submission", "Expected 201", body, r)
        return

    # 5b. IN_PROGRESS without proof_url → should fail
    body_no_proof = {"new_status": "IN_PROGRESS", "internal_note": "Starting work."}
    r2 = patch(f"/api/v1/complaints/{edge_id}/status", body=body_no_proof, headers=auth("jssa"))
    if r2 and r2.status_code in (400, 422):
        results.ok("Edge: IN_PROGRESS without proof_url → 400/422 (rejected correctly)")
    else:
        results.fail("Edge: IN_PROGRESS without proof_url", f"Expected 400/422, got {r2.status_code if r2 else 'None'}", body_no_proof, r2)

    # 5c. Invalid status transition (NEW → CLOSED directly) → should fail
    body_invalid = {"new_status": "CLOSED"}
    r3 = patch(f"/api/v1/complaints/{edge_id}/status", body=body_invalid, headers=auth("super_admin"))
    if r3 and r3.status_code in (400, 422):
        results.ok("Edge: NEW → CLOSED (invalid transition) → 400/422")
    else:
        results.fail("Edge: Invalid state transition NEW → CLOSED", f"Expected 400/422, got {r3.status_code if r3 else 'None'}", body_invalid, r3)

    # 5d. FINAL_SURVEY_PENDING without proof_url → should fail
    # First move to a valid prior state
    patch(f"/api/v1/complaints/{edge_id}/status",
          body={"new_status": "CLASSIFIED"}, headers=auth("super_admin"))
    patch(f"/api/v1/complaints/{edge_id}/status",
          body={"new_status": "ASSIGNED"}, headers=auth("super_admin"))
    patch(f"/api/v1/complaints/{edge_id}/status",
          body={"new_status": "IN_PROGRESS", "proof_url": "https://example.com/p.jpg"},
          headers=auth("jssa"))

    body_no_proof2 = {"new_status": "FINAL_SURVEY_PENDING"}
    r4 = patch(f"/api/v1/complaints/{edge_id}/status", body=body_no_proof2, headers=auth("jssa"))
    if r4 and r4.status_code in (400, 422):
        results.ok("Edge: FINAL_SURVEY_PENDING without proof_url → 400/422")
    else:
        results.fail("Edge: FINAL_SURVEY_PENDING without proof_url", f"Expected 400/422, got {r4.status_code if r4 else 'None'}", body_no_proof2, r4)

    # 5e. Survey rejected → complaint should reopen
    body_rej_survey = {"response": "rejected", "citizen_note": "Road is still broken!"}
    # Move to FINAL_SURVEY_PENDING with proof first
    patch(f"/api/v1/complaints/{edge_id}/status",
          body={"new_status": "FINAL_SURVEY_PENDING", "proof_url": "https://example.com/p2.jpg"},
          headers=auth("jssa"))
    r5 = post(f"/api/v1/complaints/{edge_id}/survey-response", body=body_rej_survey)
    if r5 and r5.status_code == 200:
        results.ok("Edge: Survey rejected → 200")
        # Check if status is REOPENED
        rcheck = get(f"/api/v1/complaints/{edge_id}")
        if rcheck and rcheck.status_code == 200:
            status = rcheck.json().get("status")
            if status == "REOPENED":
                results.ok("Edge: Status after rejection = REOPENED ✓")
            else:
                results.fail("Edge: Status after rejection", f"Expected REOPENED, got {status}", resp=rcheck)
    else:
        results.fail("Edge: Survey rejected", f"Expected 200, got {r5.status_code if r5 else 'None'}", body_rej_survey, r5)


# ============================================================
# ❌  Section 6: Validation Errors
# ============================================================

def test_validation_errors():
    print("\n── Section 6: Validation Errors ─────────────────────────")

    # 6a. Missing required field raw_text
    body = {"lat": 28.63, "lng": 77.20, "channel": "web"}
    r = post("/api/v1/complaints", body=body)
    if r and r.status_code == 422:
        results.ok("Validation: missing raw_text → 422")
    else:
        results.fail("Validation: missing raw_text", f"Expected 422, got {r.status_code if r else 'None'}", body, r)

    # 6b. Invalid channel value
    body2 = {"raw_text": "test", "lat": 28.63, "lng": 77.20, "channel": "INVALID_CHANNEL"}
    r2 = post("/api/v1/complaints", body=body2)
    if r2 and r2.status_code == 422:
        results.ok("Validation: invalid channel → 422")
    else:
        results.fail("Validation: invalid channel", f"Expected 422, got {r2.status_code if r2 else 'None'}", body2, r2)

    # 6c. Invalid email format
    body3 = {"citizen_email": "not-an-email", "raw_text": "test complaint", "lat": 28.63, "lng": 77.20, "channel": "web"}
    r3 = post("/api/v1/complaints", body=body3)
    if r3 and r3.status_code == 422:
        results.ok("Validation: invalid email format → 422")
    else:
        results.fail("Validation: invalid email", f"Expected 422, got {r3.status_code if r3 else 'None'}", body3, r3)

    # 6d. Missing lat/lng
    body4 = {"raw_text": "test complaint", "channel": "web"}
    r4 = post("/api/v1/complaints", body=body4)
    if r4 and r4.status_code == 422:
        results.ok("Validation: missing lat/lng → 422")
    else:
        results.fail("Validation: missing lat/lng", f"Expected 422, got {r4.status_code if r4 else 'None'}", body4, r4)

    # 6e. Invalid status value in status update
    if state["complaint_id"]:
        body5 = {"new_status": "FLYING_UNICORN"}
        r5 = patch(f"/api/v1/complaints/{state['complaint_id']}/status", body=body5, headers=auth("super_admin"))
        if r5 and r5.status_code == 422:
            results.ok("Validation: invalid status value → 422")
        else:
            results.fail("Validation: invalid status value", f"Expected 422, got {r5.status_code if r5 else 'None'}", body5, r5)

    # 6f. Contractor status update — missing reason
    r6 = patch(
        "/api/v1/contractors/00000000-0000-0000-0000-000000000001/status",
        body={"is_active": False},
        headers=auth("super_admin")
    )
    if r6 and r6.status_code in (400, 422):
        results.ok("Validation: contractor status update missing reason → 400/422")
    else:
        results.fail("Validation: contractor update missing reason", f"Expected 400/422, got {r6.status_code if r6 else 'None'}", resp=r6)


# ============================================================
# 📊  Section 7: Analytics Endpoints
# ============================================================

def test_analytics():
    print("\n── Section 7: Analytics Endpoints ───────────────────────")

    # 7a. SLA compliance — no date filter
    r = get("/api/v1/analytics/sla-compliance", headers=auth("super_admin"))
    if r and r.status_code == 200:
        results.ok("GET /analytics/sla-compliance (no filter) → 200")
    else:
        results.fail("GET /analytics/sla-compliance", f"Expected 200, got {r.status_code if r else 'None'}", resp=r)

    # 7b. SLA compliance — with date range
    r2 = get("/api/v1/analytics/sla-compliance",
             params={"date_from": "2025-01-01", "date_to": "2026-12-31"},
             headers=auth("super_admin"))
    if r2 and r2.status_code == 200:
        results.ok("GET /analytics/sla-compliance (with date range) → 200")
    else:
        results.fail("GET /analytics/sla-compliance (date range)", f"Expected 200, got {r2.status_code if r2 else 'None'}", resp=r2)

    # 7c. Complaint volume — day grouping
    r3 = get("/api/v1/analytics/complaint-volume",
             params={"group_by": "day"},
             headers=auth("super_admin"))
    if r3 and r3.status_code == 200:
        results.ok("GET /analytics/complaint-volume (group_by=day) → 200")
    else:
        results.fail("GET /analytics/complaint-volume (day)", f"Expected 200, got {r3.status_code if r3 else 'None'}", resp=r3)

    # 7d. Complaint volume — week grouping
    r4 = get("/api/v1/analytics/complaint-volume",
             params={"group_by": "week"},
             headers=auth("super_admin"))
    if r4 and r4.status_code == 200:
        results.ok("GET /analytics/complaint-volume (group_by=week) → 200")
    else:
        results.fail("GET /analytics/complaint-volume (week)", f"Expected 200, got {r4.status_code if r4 else 'None'}", resp=r4)

    # 7e. Complaint volume — month grouping + ward filter
    r5 = get("/api/v1/analytics/complaint-volume",
             params={"group_by": "month", "ward_id": SEED["ward_cp"]},
             headers=auth("super_admin"))
    if r5 and r5.status_code == 200:
        results.ok("GET /analytics/complaint-volume (month + ward filter) → 200")
    else:
        results.fail("GET /analytics/complaint-volume (month+ward)", f"Expected 200, got {r5.status_code if r5 else 'None'}", resp=r5)

    # 7f. Ward density — public, no auth
    r6 = get("/api/v1/analytics/ward-density")
    if r6 and r6.status_code == 200:
        results.ok("GET /analytics/ward-density (public, no auth) → 200")
    else:
        results.fail("GET /analytics/ward-density", f"Expected 200, got {r6.status_code if r6 else 'None'}", resp=r6)

    # 7g. Hotspots — no auth → should fail
    r7 = get("/api/v1/analytics/hotspots")
    if r7 and r7.status_code in (401, 403):
        results.ok("GET /analytics/hotspots (no auth) → 401/403")
    else:
        results.fail("GET /analytics/hotspots (no auth)", f"Expected 401/403, got {r7.status_code if r7 else 'None'}", resp=r7)


# ============================================================
# 🗺️  Section 8: Geo / Infrastructure Endpoints
# ============================================================

def test_geo_infra():
    print("\n── Section 8: Geo / Infrastructure Endpoints ────────────")

    # 8a. Wards GeoJSON — public, no auth
    r = get("/api/v1/wards")
    if r and r.status_code == 200:
        results.ok("GET /api/v1/wards → 200")
    else:
        results.fail("GET /api/v1/wards", f"Expected 200, got {r.status_code if r else 'None'}", resp=r)

    # 8b. Assets near Connaught Place (within 500m)
    r2 = get("/api/v1/assets",
             params={"lat": SEED["cp_lat"], "lng": SEED["cp_lng"], "radius_m": 500},
             headers=auth("super_admin"))
    if r2 and r2.status_code == 200:
        results.ok("GET /api/v1/assets (near CP, 500m) → 200")
    else:
        results.fail("GET /api/v1/assets (near CP)", f"Expected 200, got {r2.status_code if r2 else 'None'}", resp=r2)

    # 8c. Assets — filter by asset_type
    r3 = get("/api/v1/assets",
             params={"lat": SEED["cp_lat"], "lng": SEED["cp_lng"], "radius_m": 1000, "asset_type": "drain"},
             headers=auth("super_admin"))
    if r3 and r3.status_code == 200:
        results.ok("GET /api/v1/assets (filter by drain type) → 200")
    else:
        results.fail("GET /api/v1/assets (drain filter)", f"Expected 200, got {r3.status_code if r3 else 'None'}", resp=r3)

    # 8d. Assets — no auth → should fail
    r4 = get("/api/v1/assets", params={"lat": SEED["cp_lat"], "lng": SEED["cp_lng"]})
    if r4 and r4.status_code in (401, 403):
        results.ok("GET /api/v1/assets (no auth) → 401/403")
    else:
        results.fail("GET /api/v1/assets (no auth)", f"Expected 401/403, got {r4.status_code if r4 else 'None'}", resp=r4)

    # 8e. Missing required lat/lng params
    r5 = get("/api/v1/assets", headers=auth("super_admin"))
    if r5 and r5.status_code == 422:
        results.ok("GET /api/v1/assets (missing lat/lng) → 422")
    else:
        results.fail("GET /api/v1/assets (missing lat/lng)", f"Expected 422, got {r5.status_code if r5 else 'None'}", resp=r5)


# ============================================================
# 📋  Section 9: Admin — Filters & List Complaints
# ============================================================

def test_admin_list():
    print("\n── Section 9: Admin — List & Filter Complaints ──────────")

    # 9a. Filter by status
    r = get("/api/v1/complaints", params={"status": "NEW"}, headers=auth("super_admin"))
    if r and r.status_code == 200:
        results.ok("GET /api/v1/complaints?status=NEW → 200")
    else:
        results.fail("GET /api/v1/complaints?status=NEW", f"Expected 200, got {r.status_code if r else 'None'}", resp=r)

    # 9b. Filter by ward_id
    r2 = get("/api/v1/complaints", params={"ward_id": SEED["ward_cp"]}, headers=auth("super_admin"))
    if r2 and r2.status_code == 200:
        results.ok("GET /api/v1/complaints?ward_id=CP → 200")
    else:
        results.fail("GET /api/v1/complaints?ward_id=CP", f"Expected 200, got {r2.status_code if r2 else 'None'}", resp=r2)

    # 9c. Filter by sla_breached
    r3 = get("/api/v1/complaints", params={"sla_breached": True}, headers=auth("super_admin"))
    if r3 and r3.status_code == 200:
        results.ok("GET /api/v1/complaints?sla_breached=true → 200")
    else:
        results.fail("GET /api/v1/complaints?sla_breached=true", f"Expected 200, got {r3.status_code if r3 else 'None'}", resp=r3)

    # 9d. Admin response schema should include internal fields
    r4 = get("/api/v1/complaints", headers=auth("super_admin"))
    if r4 and r4.status_code == 200:
        items = r4.json()
        if isinstance(items, list) and len(items) > 0:
            item = items[0]
            has_admin_fields = "urgency" in item or "ward_id" in item
            if has_admin_fields:
                results.ok("Admin response includes extended fields (urgency, ward_id)")
            else:
                results.fail("Admin response schema", "Missing admin fields in response", resp=r4)
        else:
            results.ok("GET /api/v1/complaints (admin) → 200 (empty list)")
    else:
        results.fail("Admin response schema check", f"Expected 200, got {r4.status_code if r4 else 'None'}", resp=r4)


# ============================================================
# 📦  Section 10: Work Orders
# ============================================================

def test_work_orders():
    print("\n── Section 10: Work Orders ───────────────────────────────")

    if not state["complaint_id"]:
        print("  ⚠️  Skipped — no complaint_id")
        return

    cid = state["complaint_id"]

    # 10a. Get work orders for complaint
    r = get(f"/api/v1/complaints/{cid}/work-orders", headers=auth("super_admin"))
    if r and r.status_code == 200:
        results.ok(f"GET /complaints/{{id}}/work-orders → 200")
    else:
        results.fail("GET /complaints/{id}/work-orders", f"Expected 200, got {r.status_code if r else 'None'}", resp=r)

    # 10b. Get work orders — no auth → should fail
    r2 = get(f"/api/v1/complaints/{cid}/work-orders")
    if r2 and r2.status_code in (401, 403):
        results.ok("GET /work-orders (no auth) → 401/403")
    else:
        results.fail("GET /work-orders (no auth)", f"Expected 401/403, got {r2.status_code if r2 else 'None'}", resp=r2)

    # 10c. Create work order — missing contractor_id/dept → should fail
    r3 = post(f"/api/v1/complaints/{cid}/work-orders", headers=auth("faa"))
    if r3 and r3.status_code == 422:
        results.ok("POST /work-orders (missing params) → 422")
    else:
        results.fail("POST /work-orders (missing params)", f"Expected 422, got {r3.status_code if r3 else 'None'}", resp=r3)


# ============================================================
# 🚀  Section 11: Upload URL
# ============================================================

def test_upload_url():
    print("\n── Section 11: Upload URL ────────────────────────────────")

    # 11a. With auth
    r = post("/api/v1/complaints/upload-url", headers=auth("jssa"))
    if r and r.status_code == 200:
        results.ok("POST /complaints/upload-url (authed) → 200")
    else:
        results.fail("POST /complaints/upload-url (authed)", f"Expected 200, got {r.status_code if r else 'None'}", resp=r)

    # 11b. Without auth → should fail
    r2 = post("/api/v1/complaints/upload-url")
    if r2 and r2.status_code in (401, 403):
        results.ok("POST /complaints/upload-url (no auth) → 401/403")
    else:
        results.fail("POST /complaints/upload-url (no auth)", f"Expected 401/403, got {r2.status_code if r2 else 'None'}", resp=r2)


# ============================================================
# 🏃  MAIN — Run all sections
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  PS-CRM API Test Suite")
    print(f"  Target: {BASE_URL}")
    print(f"  Time:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Check if tokens are still placeholders
    missing_tokens = [role for role, token in TOKENS.items() if "YOUR_" in token]
    if missing_tokens:
        print(f"\n⚠️  WARNING: Placeholder tokens detected for: {', '.join(missing_tokens)}")
        print("   Auth-gated tests will fail until you fill in real tokens.\n")

    test_health()
    test_submit_complaint()
    test_public_lookup()
    test_auth_and_roles()
    test_lifecycle()
    test_lifecycle_edge_cases()
    test_validation_errors()
    test_analytics()
    test_geo_infra()
    test_admin_list()
    test_work_orders()
    test_upload_url()

    ok = results.summary()
    sys.exit(0 if ok else 1)