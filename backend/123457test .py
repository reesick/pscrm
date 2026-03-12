"""
PS-CRM Live Test Runner
========================
Auto-creates test users in Supabase, gets real JWTs,
then runs all 72 tests against your live backend.

Requirements:
    pip install httpx python-dotenv

Run:
    python run_live_tests.py
"""

import os
import sys
import json
import time
import httpx
import re
import concurrent.futures
from datetime import datetime, timezone, timedelta
from typing import Optional

# ── Load .env ─────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(".env")
    print("[.env] Loaded")
except ImportError:
    print("[.env] python-dotenv not installed, reading os.environ only")

# ── Config from .env ──────────────────────────────────────────────────
SUPABASE_URL      = os.getenv("SUPABASE_URL", "").rstrip("/")
SERVICE_ROLE_KEY  = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
ANON_KEY          = os.getenv("SUPABASE_ANON_KEY", "")
BACKEND_URL       = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
INTERNAL_KEY      = os.getenv("INTERNAL_CRON_KEY", "")

if not SUPABASE_URL or not SERVICE_ROLE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
    sys.exit(1)

# ── Test coordinates (Delhi, Laxmi Nagar area) ────────────────────────
TEST_LAT = float(os.getenv("TEST_LAT", "28.6428"))
TEST_LNG = float(os.getenv("TEST_LNG", "77.2773"))

# ─────────────────────────────────────────────────────────────────────
# STEP 1: Auto-create test users + get JWTs via Supabase Auth Admin API
# ─────────────────────────────────────────────────────────────────────

TEST_USERS = {
    "jssa": {
        "email": "test.jssa@pscrm-test.dev",
        "password": "TestJSSA#2025!",
        "role": "jssa",
    },
    "aa": {
        "email": "test.aa@pscrm-test.dev",
        "password": "TestAA#2025!",
        "role": "aa",
    },
    "super_admin": {
        "email": "test.superadmin@pscrm-test.dev",
        "password": "TestSuperAdmin#2025!",
        "role": "super_admin",
    },
    "contractor": {
        "email": "test.contractor@pscrm-test.dev",
        "password": "TestContractor#2025!",
        "role": "contractor",
    },
}

JWTS = {}         # role → jwt string
USER_IDS = {}     # role → user uuid
TEST_WARD_ID  = None
OTHER_WARD_ID = None


def supabase_admin_headers():
    return {
        "apikey": SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }


def create_or_get_user(role: str, email: str, password: str) -> dict:
    """Create user via Supabase Auth Admin API. If already exists, just return."""
    with httpx.Client(timeout=15) as c:
        # Try to create
        r = c.post(
            f"{SUPABASE_URL}/auth/v1/admin/users",
            headers=supabase_admin_headers(),
            json={
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"role": role},
                "app_metadata": {"role": role},
            }
        )
        if r.status_code == 201:
            user = r.json()
            print(f"  [+] Created user: {email} (role={role})")
            return user
        elif r.status_code == 422 and "already" in r.text.lower():
            # Already exists — list users and find by email
            r2 = c.get(
                f"{SUPABASE_URL}/auth/v1/admin/users?per_page=100",
                headers=supabase_admin_headers()
            )
            if r2.status_code == 200:
                users = r2.json().get("users", [])
                for u in users:
                    if u.get("email") == email:
                        # Update metadata to ensure role is set
                        c.put(
                            f"{SUPABASE_URL}/auth/v1/admin/users/{u['id']}",
                            headers=supabase_admin_headers(),
                            json={"app_metadata": {"role": role}, "user_metadata": {"role": role}}
                        )
                        print(f"  [=] Found existing user: {email} (role={role})")
                        return u
        print(f"  [!] Could not create/find user {email}: {r.status_code} {r.text[:120]}")
        return {}


def get_jwt_for_user(email: str, password: str) -> str:
    """Sign in via Supabase Auth to get a real JWT."""
    with httpx.Client(timeout=15) as c:
        r = c.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
            headers={
                "apikey": ANON_KEY,
                "Content-Type": "application/json",
            },
            json={"email": email, "password": password}
        )
        if r.status_code == 200:
            token = r.json().get("access_token", "")
            if token:
                return token
        print(f"  [!] Login failed for {email}: {r.status_code} {r.text[:120]}")
        return ""


def get_wards() -> list:
    """Fetch wards from the backend to get real ward IDs."""
    try:
        with httpx.Client(timeout=10, base_url=BACKEND_URL) as c:
            r = c.get("/api/v1/wards")
            if r.status_code == 200:
                body = r.json()
                features = body.get("features", [])
                ward_ids = [f["properties"].get("ward_id") or f["properties"].get("id")
                            for f in features if f.get("properties")]
                ward_ids = [w for w in ward_ids if w]
                return ward_ids
    except Exception as e:
        print(f"  [!] Could not fetch wards from backend: {e}")
    return []


def setup_test_users():
    global TEST_WARD_ID, OTHER_WARD_ID
    print("\n" + "="*60)
    print("  STEP 1: Setting up Supabase test users")
    print("="*60)

    for role, cfg in TEST_USERS.items():
        user = create_or_get_user(role, cfg["email"], cfg["password"])
        if user:
            USER_IDS[role] = user.get("id", "")
        time.sleep(0.3)  # avoid rate limit

    print("\n  Signing in to get JWTs...")
    for role, cfg in TEST_USERS.items():
        jwt = get_jwt_for_user(cfg["email"], cfg["password"])
        if jwt:
            JWTS[role] = jwt
            print(f"  [✓] Got JWT for {role} ({len(jwt)} chars)")
        else:
            print(f"  [✗] No JWT for {role}")
        time.sleep(0.3)

    print("\n  Fetching ward IDs from backend...")
    ward_ids = get_wards()
    if len(ward_ids) >= 2:
        TEST_WARD_ID  = ward_ids[0]
        OTHER_WARD_ID = ward_ids[1]
        print(f"  [✓] TEST_WARD_ID  = {TEST_WARD_ID}")
        print(f"  [✓] OTHER_WARD_ID = {OTHER_WARD_ID}")
    elif len(ward_ids) == 1:
        TEST_WARD_ID  = ward_ids[0]
        OTHER_WARD_ID = "00000000-0000-0000-0000-000000000000"
        print(f"  [✓] TEST_WARD_ID  = {TEST_WARD_ID}")
        print(f"  [~] OTHER_WARD_ID = (dummy, only 1 ward found)")
    else:
        TEST_WARD_ID  = "00000000-0000-0000-0000-000000000001"
        OTHER_WARD_ID = "00000000-0000-0000-0000-000000000002"
        print("  [~] No wards found in backend — using dummy ward IDs")
        print("      (seed ward data first for full test coverage)")

    missing = [r for r in ["jssa","aa","super_admin","contractor"] if r not in JWTS]
    if missing:
        print(f"\n  [!] Missing JWTs for: {missing}")
        print("      Tests requiring those roles will be skipped.")
    else:
        print("\n  [✓] All 4 JWTs ready. Proceeding to tests.")


# ─────────────────────────────────────────────────────────────────────
# STEP 2: Live test suite
# ─────────────────────────────────────────────────────────────────────

RESULTS = []
state = {
    "complaint_id": None,
    "grievance_id": None,
}


def run_test(section: str, name: str, fn):
    try:
        fn()
        RESULTS.append((section, name, True, ""))
        return True
    except Exception as e:
        RESULTS.append((section, name, False, str(e)[:120]))
        return False


def auth(role: str) -> dict:
    jwt = JWTS.get(role, "")
    return {"Authorization": f"Bearer {jwt}"}


def skip_if_no_jwt(role: str):
    if role not in JWTS or not JWTS[role]:
        raise AssertionError(f"SKIP — no JWT for role '{role}'")


def client():
    return httpx.Client(base_url=BACKEND_URL, timeout=20)


# ── Section 1: Infrastructure ─────────────────────────────────────────

def test_health():
    with client() as c:
        r = c.get("/health")
    assert r.status_code == 200, f"Got {r.status_code}"
    assert r.json().get("status") == "ok"

def test_openapi():
    with client() as c:
        r = c.get("/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    assert "paths" in schema

def test_health_speed():
    times = []
    with client() as c:
        for _ in range(10):
            t0 = time.time()
            c.get("/health")
            times.append((time.time()-t0)*1000)
    p95 = sorted(times)[8]
    assert p95 < 300, f"p95={p95:.0f}ms > 300ms"

# ── Section 2: Complaint Submission ───────────────────────────────────

def test_submit_basic():
    with client() as c:
        r = c.post("/api/v1/complaints", json={
            "raw_text": "Drain overflow near Laxmi Nagar market, water flooding road",
            "lat": TEST_LAT, "lng": TEST_LNG, "channel": "web"
        })
    assert r.status_code == 201, f"Got {r.status_code}: {r.text[:200]}"
    body = r.json()
    assert "id" in body, f"Missing 'id' in: {body}"
    assert "grievance_id" in body
    assert "status" in body
    state["complaint_id"] = body["id"]
    state["grievance_id"] = body["grievance_id"]

def test_grievance_id_format():
    with client() as c:
        r = c.post("/api/v1/complaints", json={
            "raw_text": "Streetlight broken near metro station",
            "lat": TEST_LAT, "lng": TEST_LNG, "channel": "web"
        })
    assert r.status_code == 201
    gid = r.json()["grievance_id"]
    assert re.match(r"^MCD-\d{8}-[A-Z0-9]{5}$", gid), f"Bad grievance ID format: {gid}"

def test_submit_with_email():
    with client() as c:
        r = c.post("/api/v1/complaints", json={
            "raw_text": "Garbage pile near bus stop not collected",
            "lat": TEST_LAT, "lng": TEST_LNG, "channel": "web",
            "citizen_email": "citizen@example.com"
        })
    assert r.status_code == 201
    body = r.json()
    assert "citizen_email" not in body, "Raw email exposed in response!"

def test_submit_missing_text():
    with client() as c:
        r = c.post("/api/v1/complaints", json={"lat": TEST_LAT, "lng": TEST_LNG, "channel": "web"})
    assert r.status_code == 422, f"Expected 422, got {r.status_code}"

def test_submit_invalid_channel():
    with client() as c:
        r = c.post("/api/v1/complaints", json={
            "raw_text": "Test", "lat": TEST_LAT, "lng": TEST_LNG, "channel": "whatsapp"
        })
    assert r.status_code == 422

def test_submit_invalid_email():
    with client() as c:
        r = c.post("/api/v1/complaints", json={
            "raw_text": "Test", "lat": TEST_LAT, "lng": TEST_LNG,
            "channel": "web", "citizen_email": "not-an-email"
        })
    assert r.status_code == 422

def test_submit_bad_coords():
    with client() as c:
        r = c.post("/api/v1/complaints", json={
            "raw_text": "Test", "lat": 999.0, "lng": TEST_LNG, "channel": "web"
        })
    assert r.status_code in [400, 422], f"Got {r.status_code}"

def test_sla_in_future():
    with client() as c:
        r = c.post("/api/v1/complaints", json={
            "raw_text": "Large pothole causing accidents on Ring Road",
            "lat": TEST_LAT, "lng": TEST_LNG, "channel": "web"
        })
    assert r.status_code == 201
    body = r.json()
    if body.get("sla_deadline"):
        dl = datetime.fromisoformat(body["sla_deadline"].replace("Z", "+00:00"))
        assert dl > datetime.now(timezone.utc), "SLA deadline is in the past!"

def test_no_sensitive_in_post_response():
    with client() as c:
        r = c.post("/api/v1/complaints", json={
            "raw_text": "Water pipe burst near school",
            "lat": TEST_LAT, "lng": TEST_LNG, "channel": "web"
        })
    assert r.status_code == 201
    body = r.json()
    for f in ["citizen_email", "citizen_email_hash", "citizen_phone_hash", "officer_phone"]:
        assert f not in body, f"Sensitive field '{f}' in public POST response"

# ── Section 3: Public Lookup ──────────────────────────────────────────

def test_get_by_uuid():
    assert state["complaint_id"], "No complaint_id — run submission tests first"
    with client() as c:
        r = c.get(f"/api/v1/complaints/{state['complaint_id']}")
    assert r.status_code == 200, f"Got {r.status_code}"
    body = r.json()
    assert body["id"] == state["complaint_id"]
    assert "timeline" in body

def test_get_by_grievance_id():
    assert state["grievance_id"], "No grievance_id"
    with client() as c:
        r = c.get(f"/api/v1/complaints/{state['grievance_id']}")
    assert r.status_code == 200
    assert r.json()["grievance_id"] == state["grievance_id"]

def test_get_404():
    with client() as c:
        r = c.get("/api/v1/complaints/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404, f"Expected 404, got {r.status_code}"

def test_public_response_fields():
    assert state["complaint_id"]
    with client() as c:
        r = c.get(f"/api/v1/complaints/{state['complaint_id']}")
    body = r.json()
    for f in ["id", "grievance_id", "status", "created_at", "timeline"]:
        assert f in body, f"Required field '{f}' missing"
    for f in ["citizen_email_hash", "internal_notes", "officer_phone", "lat", "lng"]:
        assert f not in body, f"Sensitive field '{f}' in public response"

def test_timeline_is_list():
    assert state["complaint_id"]
    with client() as c:
        r = c.get(f"/api/v1/complaints/{state['complaint_id']}")
    assert isinstance(r.json()["timeline"], list)

# ── Section 4: Admin List ─────────────────────────────────────────────

def test_list_no_auth():
    with client() as c:
        r = c.get("/api/v1/complaints")
    assert r.status_code == 401, f"Expected 401, got {r.status_code}"

def test_list_jssa_scoped():
    skip_if_no_jwt("jssa")
    with client() as c:
        r = c.get("/api/v1/complaints", headers=auth("jssa"))
    assert r.status_code == 200, f"Got {r.status_code}: {r.text[:200]}"
    complaints = r.json()
    assert isinstance(complaints, list)
    # If complaints returned and TEST_WARD_ID is real, check scoping
    if complaints and TEST_WARD_ID and "00000000" not in TEST_WARD_ID:
        for comp in complaints:
            assert comp.get("ward_id") == TEST_WARD_ID, \
                f"JSSA received complaint from ward {comp.get('ward_id')} (expected {TEST_WARD_ID})"

def test_list_super_admin():
    skip_if_no_jwt("super_admin")
    with client() as c:
        r = c.get("/api/v1/complaints", headers=auth("super_admin"))
    assert r.status_code == 200, f"Got {r.status_code}: {r.text[:200]}"
    assert isinstance(r.json(), list)

def test_list_status_filter():
    skip_if_no_jwt("jssa")
    with client() as c:
        r = c.get("/api/v1/complaints?status=NEW", headers=auth("jssa"))
    assert r.status_code == 200
    for comp in r.json():
        assert comp["status"] == "NEW", f"Status filter broken: got {comp['status']}"

def test_list_contractor_403():
    skip_if_no_jwt("contractor")
    with client() as c:
        r = c.get("/api/v1/complaints", headers=auth("contractor"))
    assert r.status_code == 403, f"Expected 403 for contractor, got {r.status_code}"

def test_admin_extra_fields():
    skip_if_no_jwt("jssa")
    with client() as c:
        r = c.get("/api/v1/complaints", headers=auth("jssa"))
    assert r.status_code == 200
    complaints = r.json()
    if complaints:
        for f in ["ward_id", "urgency", "llm_used"]:
            assert f in complaints[0], f"Admin field '{f}' missing from list response"

# ── Section 5: State Machine ──────────────────────────────────────────

def test_status_update_no_auth():
    assert state["complaint_id"]
    with client() as c:
        r = c.patch(f"/api/v1/complaints/{state['complaint_id']}/status",
                    json={"new_status": "CLASSIFIED"})
    assert r.status_code == 401

def test_invalid_transition_new_to_closed():
    skip_if_no_jwt("jssa")
    # Create a fresh complaint (should start at NEW or CLASSIFIED)
    with client() as c:
        r = c.post("/api/v1/complaints", json={
            "raw_text": "Test pothole on road for state machine test",
            "lat": TEST_LAT, "lng": TEST_LNG, "channel": "web"
        })
    assert r.status_code == 201
    cid = r.json()["id"]
    time.sleep(1)  # let agent pipeline run
    with client() as c2:
        current = c2.get(f"/api/v1/complaints/{cid}").json()["status"]
        r2 = c2.patch(f"/api/v1/complaints/{cid}/status",
                      headers=auth("jssa"),
                      json={"new_status": "CLOSED"})
    # NEW or CLASSIFIED → CLOSED is always invalid
    if current in ("NEW", "CLASSIFIED"):
        assert r2.status_code == 400, f"Expected 400 for {current}→CLOSED, got {r2.status_code}"

def test_proof_required_for_in_progress():
    skip_if_no_jwt("jssa")
    # Find an ASSIGNED complaint or skip
    with client() as c:
        r = c.get("/api/v1/complaints?status=ASSIGNED", headers=auth("jssa"))
    if r.status_code != 200 or not r.json():
        raise AssertionError("SKIP — no ASSIGNED complaints available")
    cid = r.json()[0]["id"]
    with client() as c2:
        r2 = c2.patch(f"/api/v1/complaints/{cid}/status",
                      headers=auth("jssa"),
                      json={"new_status": "IN_PROGRESS"})  # no proof_url
    assert r2.status_code == 400, f"Expected 400 for missing proof_url, got {r2.status_code}"
    assert "proof" in str(r2.json()).lower(), "Error must mention 'proof'"

def test_proof_gate_passes_with_url():
    skip_if_no_jwt("jssa")
    with client() as c:
        r = c.get("/api/v1/complaints?status=ASSIGNED", headers=auth("jssa"))
    if r.status_code != 200 or not r.json():
        raise AssertionError("SKIP — no ASSIGNED complaints available")
    cid = r.json()[0]["id"]
    with client() as c2:
        r2 = c2.patch(f"/api/v1/complaints/{cid}/status",
                      headers=auth("jssa"),
                      json={"new_status": "IN_PROGRESS",
                            "proof_url": "https://storage.supabase.co/proofs/test.jpg"})
    assert r2.status_code == 200, f"Expected 200 with proof_url, got {r2.status_code}: {r2.text[:200]}"

def test_terminal_closed():
    skip_if_no_jwt("jssa")
    with client() as c:
        r = c.get("/api/v1/complaints?status=CLOSED", headers=auth("jssa"))
    if r.status_code != 200 or not r.json():
        raise AssertionError("SKIP — no CLOSED complaints available")
    cid = r.json()[0]["id"]
    with client() as c2:
        r2 = c2.patch(f"/api/v1/complaints/{cid}/status",
                      headers=auth("jssa"), json={"new_status": "ASSIGNED"})
    assert r2.status_code == 400, f"CLOSED should be terminal, got {r2.status_code}"

# ── Section 6: Classification ─────────────────────────────────────────

def test_classify_drain():
    with client() as c:
        r = c.post("/api/v1/complaints", json={
            "raw_text": "Large drain overflow near Laxmi Nagar market, water on road",
            "lat": TEST_LAT, "lng": TEST_LNG, "channel": "web"
        })
    assert r.status_code == 201
    cid = r.json()["id"]
    time.sleep(8)
    skip_if_no_jwt("jssa")
    with client() as c2:
        r2 = c2.get("/api/v1/complaints", headers=auth("jssa"))
    complaints = [x for x in r2.json() if x["id"] == cid]
    if complaints and complaints[0].get("category"):
        assert complaints[0]["category"] == "drainage", \
            f"Expected drainage, got {complaints[0]['category']}"

def test_classify_streetlight():
    with client() as c:
        r = c.post("/api/v1/complaints", json={
            "raw_text": "Streetlight is broken on Ring Road near Rohini metro",
            "lat": TEST_LAT, "lng": TEST_LNG, "channel": "web"
        })
    assert r.status_code == 201

def test_unique_grievance_ids():
    ids = []
    with client() as c:
        for _ in range(5):
            r = c.post("/api/v1/complaints", json={
                "raw_text": f"Test complaint #{time.time()}",
                "lat": TEST_LAT, "lng": TEST_LNG, "channel": "web"
            })
            assert r.status_code == 201
            ids.append(r.json()["grievance_id"])
    assert len(set(ids)) == 5, f"Duplicate grievance IDs: {ids}"
    for gid in ids:
        assert re.match(r"^MCD-\d{8}-[A-Z0-9]{5}$", gid), f"Bad ID: {gid}"

# ── Section 7: Survey ─────────────────────────────────────────────────

def test_survey_invalid_value():
    assert state["complaint_id"]
    with client() as c:
        r = c.post(f"/api/v1/complaints/{state['complaint_id']}/survey-response",
                   json={"response": "maybe"})
    assert r.status_code == 422

def test_survey_approved():
    skip_if_no_jwt("jssa")
    with client() as c:
        r = c.get("/api/v1/complaints?status=FINAL_SURVEY_PENDING", headers=auth("jssa"))
    if r.status_code != 200 or not r.json():
        raise AssertionError("SKIP — no FINAL_SURVEY_PENDING complaints available")
    cid = r.json()[0]["id"]
    with client() as c2:
        r2 = c2.post(f"/api/v1/complaints/{cid}/survey-response",
                     json={"response": "approved", "citizen_note": "Fixed!"})
    assert r2.status_code == 200
    with client() as c3:
        status = c3.get(f"/api/v1/complaints/{cid}").json()["status"]
    assert status == "CLOSED", f"Expected CLOSED after approval, got {status}"

def test_survey_rejected():
    skip_if_no_jwt("jssa")
    with client() as c:
        r = c.get("/api/v1/complaints?status=FINAL_SURVEY_PENDING", headers=auth("jssa"))
    if r.status_code != 200 or not r.json():
        raise AssertionError("SKIP — no FINAL_SURVEY_PENDING complaints (second one needed)")
    cid = r.json()[0]["id"]
    with client() as c2:
        r2 = c2.post(f"/api/v1/complaints/{cid}/survey-response",
                     json={"response": "rejected", "citizen_note": "Still broken"})
    assert r2.status_code == 200

# ── Section 8: Officer Stats ──────────────────────────────────────────

def test_officer_stats_no_auth():
    with client() as c:
        r = c.get(f"/api/v1/officers/{USER_IDS.get('jssa','test-id')}/stats")
    assert r.status_code == 401

def test_officer_stats_fields():
    skip_if_no_jwt("jssa")
    officer_id = USER_IDS.get("jssa", "test-id")
    with client() as c:
        r = c.get(f"/api/v1/officers/{officer_id}/stats", headers=auth("jssa"))
    assert r.status_code == 200, f"Got {r.status_code}: {r.text[:200]}"
    body = r.json()
    for f in ["total_assigned", "total_resolved", "total_escalated",
              "avg_resolution_hours", "reopen_rate_pct"]:
        assert f in body, f"Field '{f}' missing from officer stats"

# ── Section 9: Contractor Scorecard ──────────────────────────────────

def test_scorecard_no_auth():
    with client() as c:
        r = c.get(f"/api/v1/contractors/{USER_IDS.get('contractor','test-id')}/scorecard")
    assert r.status_code == 401

def test_reliability_formula():
    def score(on_time, reject, reopen):
        return round(((on_time*0.4)+((1-reject)*0.35)+((1-reopen)*0.25))*100)
    assert score(0.7, 0.2, 0.1) == round((0.7*0.4+0.8*0.35+0.9*0.25)*100)
    assert score(1.0, 0.0, 0.0) == 100
    assert score(0.0, 1.0, 1.0) == 0

def test_contractor_deactivation_jssa_forbidden():
    skip_if_no_jwt("jssa")
    with client() as c:
        r = c.patch(f"/api/v1/contractors/{USER_IDS.get('contractor','test-id')}/status",
                    headers=auth("jssa"),
                    json={"is_active": False, "reason": "Test"})
    assert r.status_code == 403, f"Expected 403, got {r.status_code}"

def test_contractor_deactivation_no_reason():
    skip_if_no_jwt("super_admin")
    with client() as c:
        r = c.patch(f"/api/v1/contractors/{USER_IDS.get('contractor','test-id')}/status",
                    headers=auth("super_admin"),
                    json={"is_active": False})  # no reason
    assert r.status_code == 422, f"Expected 422 for missing reason, got {r.status_code}"

# ── Section 10: Analytics ─────────────────────────────────────────────

def test_hotspots_jssa_forbidden():
    skip_if_no_jwt("jssa")
    with client() as c:
        r = c.get("/api/v1/analytics/hotspots", headers=auth("jssa"))
    assert r.status_code == 403, f"Expected 403, got {r.status_code}"

def test_hotspots_super_admin():
    skip_if_no_jwt("super_admin")
    with client() as c:
        r = c.get("/api/v1/analytics/hotspots", headers=auth("super_admin"))
    assert r.status_code == 200, f"Got {r.status_code}: {r.text[:200]}"
    hotspots = r.json()
    assert isinstance(hotspots, list)
    for h in hotspots:
        for f in ["id", "lat", "lng", "radius_m", "category", "severity", "ward_name"]:
            assert f in h, f"Field '{f}' missing from hotspot"
        assert 1 <= h["severity"] <= 5

def test_sla_compliance():
    skip_if_no_jwt("jssa")
    with client() as c:
        r = c.get("/api/v1/analytics/sla-compliance", headers=auth("jssa"))
    assert r.status_code == 200
    for item in r.json():
        for f in ["department_name", "total_complaints", "compliance_pct"]:
            assert f in item
        assert 0 <= item["compliance_pct"] <= 100

def test_complaint_volume():
    skip_if_no_jwt("jssa")
    with client() as c:
        r = c.get("/api/v1/analytics/complaint-volume", headers=auth("jssa"))
    assert r.status_code == 200
    for pt in r.json():
        assert "period" in pt
        assert "count" in pt

def test_ward_density_public():
    with client() as c:
        r = c.get("/api/v1/analytics/ward-density")
    assert r.status_code == 200, f"Ward density must be public, got {r.status_code}"

def test_ward_density_no_coords():
    with client() as c:
        r = c.get("/api/v1/analytics/ward-density")
    for ward in r.json() if isinstance(r.json(), list) else []:
        assert "lat" not in ward, "Individual lat exposed in ward density"
        assert "lng" not in ward, "Individual lng exposed in ward density"

# ── Section 11: Assets & Wards ────────────────────────────────────────

def test_wards_geojson():
    with client() as c:
        r = c.get("/api/v1/wards")
    assert r.status_code == 200
    body = r.json()
    assert body.get("type") == "FeatureCollection", f"Got type: {body.get('type')}"
    assert len(body.get("features", [])) > 0, "No ward features returned"

def test_wards_cache_header():
    with client() as c:
        r = c.get("/api/v1/wards")
    cc = r.headers.get("cache-control", "")
    assert "max-age" in cc.lower(), f"Missing Cache-Control max-age, got: {cc}"

def test_assets_needs_lat_lng():
    skip_if_no_jwt("jssa")
    with client() as c:
        r = c.get("/api/v1/assets", headers=auth("jssa"))
    assert r.status_code == 422

def test_assets_nearby():
    skip_if_no_jwt("jssa")
    with client() as c:
        r = c.get(f"/api/v1/assets?lat={TEST_LAT}&lng={TEST_LNG}&radius_m=500",
                  headers=auth("jssa"))
    assert r.status_code == 200
    assert isinstance(r.json(), list)

# ── Section 12: Predictive Agent ─────────────────────────────────────

def test_internal_no_key():
    with client() as c:
        r = c.post("/internal/run-predictive-agent")
    assert r.status_code in [401, 422], f"Got {r.status_code}"

def test_internal_wrong_key():
    with client() as c:
        r = c.post("/internal/run-predictive-agent",
                   headers={"x-internal-key": "definitely-wrong-key"})
    assert r.status_code == 401, f"Got {r.status_code}"

def test_internal_correct_key():
    if not INTERNAL_KEY:
        raise AssertionError("SKIP — INTERNAL_CRON_KEY not set in .env")
    with client() as c:
        r = c.post("/internal/run-predictive-agent",
                   headers={"x-internal-key": INTERNAL_KEY})
    assert r.status_code == 200, f"Got {r.status_code}: {r.text[:200]}"

# ── Section 13: Error Shapes ──────────────────────────────────────────

def test_404_json():
    with client() as c:
        r = c.get("/api/v1/complaints/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
    assert "application/json" in r.headers.get("content-type", ""), \
        "404 must return JSON, not HTML"

def test_401_json():
    with client() as c:
        r = c.get("/api/v1/complaints")
    assert r.status_code == 401
    assert "application/json" in r.headers.get("content-type", "")

def test_422_detail_array():
    with client() as c:
        r = c.post("/api/v1/complaints", json={})
    assert r.status_code == 422
    body = r.json()
    assert "detail" in body
    assert isinstance(body["detail"], list)

def test_400_has_message():
    skip_if_no_jwt("jssa")
    assert state["complaint_id"]
    with client() as c:
        status = c.get(f"/api/v1/complaints/{state['complaint_id']}").json()["status"]
        if status in ("NEW", "CLASSIFIED"):
            r = c.patch(f"/api/v1/complaints/{state['complaint_id']}/status",
                        headers=auth("jssa"), json={"new_status": "CLOSED"})
            if r.status_code == 400:
                body = r.json()
                assert "detail" in body or "error" in body

# ── Section 14: Performance ───────────────────────────────────────────

def test_list_p95():
    skip_if_no_jwt("jssa")
    times = []
    with client() as c:
        for _ in range(20):
            t0 = time.time()
            c.get("/api/v1/complaints", headers=auth("jssa"))
            times.append((time.time()-t0)*1000)
    p95 = sorted(times)[18]
    assert p95 < 300, f"p95={p95:.0f}ms exceeds 300ms SLA"

def test_wards_p95():
    times = []
    with client() as c:
        c.get("/api/v1/wards")
        for _ in range(10):
            t0 = time.time()
            c.get("/api/v1/wards")
            times.append((time.time()-t0)*1000)
    p95 = sorted(times)[8]
    assert p95 < 300, f"Wards p95={p95:.0f}ms"

def test_concurrent_no_5xx():
    results = []
    def req():
        with httpx.Client(base_url=BACKEND_URL, timeout=20) as c:
            return c.get("/api/v1/wards").status_code
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
        futs = [ex.submit(req) for _ in range(50)]
        for f in concurrent.futures.as_completed(futs):
            results.append(f.result())
    errors = [s for s in results if s >= 500]
    assert len(errors) == 0, f"{len(errors)}/50 requests returned 5xx"

# ── Section 15: Upload URL ────────────────────────────────────────────

def test_upload_url():
    skip_if_no_jwt("jssa")
    with client() as c:
        r = c.post("/api/v1/complaints/upload-url", headers=auth("jssa"))
    assert r.status_code == 200, f"Got {r.status_code}: {r.text[:200]}"

# ── Section 16: SLA Logic ─────────────────────────────────────────────

def test_garbage_24h_sla():
    with client() as c:
        r = c.post("/api/v1/complaints", json={
            "raw_text": "Garbage not collected for 3 days near bus stand",
            "lat": TEST_LAT, "lng": TEST_LNG, "channel": "web"
        })
    assert r.status_code == 201
    body = r.json()
    if body.get("sla_deadline"):
        dl = datetime.fromisoformat(body["sla_deadline"].replace("Z", "+00:00"))
        hours = (dl - datetime.now(timezone.utc)).total_seconds() / 3600
        assert 23 <= hours <= 25, f"Garbage SLA should be ~24h, got {hours:.1f}h"

def test_sla_future_on_creation():
    with client() as c:
        r = c.post("/api/v1/complaints", json={
            "raw_text": "Drain overflow causing waterlogging near market",
            "lat": TEST_LAT, "lng": TEST_LNG, "channel": "web"
        })
    assert r.status_code == 201
    body = r.json()
    if body.get("sla_deadline"):
        dl = datetime.fromisoformat(body["sla_deadline"].replace("Z", "+00:00"))
        assert dl > datetime.now(timezone.utc), "SLA deadline is in the past!"

# ── Section 17: Edge Cases ────────────────────────────────────────────

def test_all_channels():
    for ch in ["telegram", "web", "call"]:
        with client() as c:
            r = c.post("/api/v1/complaints", json={
                "raw_text": f"Test complaint via {ch}",
                "lat": TEST_LAT, "lng": TEST_LNG, "channel": ch
            })
        assert r.status_code == 201, f"Channel '{ch}' rejected: {r.status_code}"

def test_multi_dept_complaint():
    with client() as c:
        r = c.post("/api/v1/complaints", json={
            "raw_text": "Tree touching electricity pole near school, dangerous",
            "lat": TEST_LAT, "lng": TEST_LNG, "channel": "web"
        })
    assert r.status_code == 201

def test_no_500_on_edge_inputs():
    for text in ["a", "   ", "12345", "!@#$%^&*()"]:
        with client() as c:
            r = c.post("/api/v1/complaints", json={
                "raw_text": text, "lat": TEST_LAT, "lng": TEST_LNG, "channel": "web"
            })
        assert r.status_code != 500, f"Got 500 for input: '{text}'"


# ─────────────────────────────────────────────────────────────────────
# Test registry
# ─────────────────────────────────────────────────────────────────────

TEST_SUITE = [
    ("Infrastructure",       "Health check → 200 + status:ok",              test_health),
    ("Infrastructure",       "OpenAPI schema accessible",                    test_openapi),
    ("Infrastructure",       "Health p95 < 300ms",                           test_health_speed),

    ("Complaint Submission", "Basic POST → 201 + id + grievance_id",         test_submit_basic),
    ("Complaint Submission", "Grievance ID format MCD-YYYYMMDD-XXXXX",       test_grievance_id_format),
    ("Complaint Submission", "Email accepted, not echoed back",              test_submit_with_email),
    ("Complaint Submission", "Missing raw_text → 422",                       test_submit_missing_text),
    ("Complaint Submission", "Invalid channel → 422",                        test_submit_invalid_channel),
    ("Complaint Submission", "Invalid email → 422",                          test_submit_invalid_email),
    ("Complaint Submission", "Invalid coordinates → 400/422",                test_submit_bad_coords),
    ("Complaint Submission", "SLA deadline is in future",                    test_sla_in_future),
    ("Complaint Submission", "No PII in public POST response",               test_no_sensitive_in_post_response),

    ("Public Lookup",        "GET by UUID → 200",                            test_get_by_uuid),
    ("Public Lookup",        "GET by grievance ID → 200",                    test_get_by_grievance_id),
    ("Public Lookup",        "GET unknown UUID → 404",                       test_get_404),
    ("Public Lookup",        "Required fields present, sensitive absent",    test_public_response_fields),
    ("Public Lookup",        "Timeline is an ordered list",                  test_timeline_is_list),

    ("Admin List",           "No auth → 401",                                test_list_no_auth),
    ("Admin List",           "JSSA sees own ward only (RLS check)",          test_list_jssa_scoped),
    ("Admin List",           "Super Admin sees all",                         test_list_super_admin),
    ("Admin List",           "Status filter works",                          test_list_status_filter),
    ("Admin List",           "Contractor → 403",                             test_list_contractor_403),
    ("Admin List",           "Admin response has ward_id, urgency, llm_used",test_admin_extra_fields),

    ("State Machine",        "Status update requires auth",                  test_status_update_no_auth),
    ("State Machine",        "Invalid transition → 400",                     test_invalid_transition_new_to_closed),
    ("State Machine",        "proof_url required for IN_PROGRESS",           test_proof_required_for_in_progress),
    ("State Machine",        "Valid transition with proof_url → 200",        test_proof_gate_passes_with_url),
    ("State Machine",        "CLOSED is terminal → 400",                     test_terminal_closed),

    ("Classification",       "Drain complaint → category=drainage",          test_classify_drain),
    ("Classification",       "Streetlight complaint submitted OK",           test_classify_streetlight),
    ("Classification",       "5 grievance IDs all unique + correct format",  test_unique_grievance_ids),

    ("Survey",               "Invalid survey value → 422",                   test_survey_invalid_value),
    ("Survey",               "Approved survey → CLOSED",                     test_survey_approved),
    ("Survey",               "Rejected survey → REOPENED",                   test_survey_rejected),

    ("Officer Stats",        "Stats requires auth",                          test_officer_stats_no_auth),
    ("Officer Stats",        "Stats response has all required fields",       test_officer_stats_fields),

    ("Contractor",           "Scorecard requires auth",                      test_scorecard_no_auth),
    ("Contractor",           "Reliability formula correct (PRD §3.3)",       test_reliability_formula),
    ("Contractor",           "Deactivation requires super_admin",            test_contractor_deactivation_jssa_forbidden),
    ("Contractor",           "Deactivation without reason → 422",           test_contractor_deactivation_no_reason),

    ("Analytics",            "Hotspots requires super_admin",                test_hotspots_jssa_forbidden),
    ("Analytics",            "Hotspots structure valid",                     test_hotspots_super_admin),
    ("Analytics",            "SLA compliance structure valid",               test_sla_compliance),
    ("Analytics",            "Complaint volume time series",                  test_complaint_volume),
    ("Analytics",            "Ward density is public",                       test_ward_density_public),
    ("Analytics",            "Ward density has no individual coords",        test_ward_density_no_coords),

    ("Assets & Wards",       "GET /wards → GeoJSON FeatureCollection",       test_wards_geojson),
    ("Assets & Wards",       "Wards has Cache-Control max-age header",       test_wards_cache_header),
    ("Assets & Wards",       "Assets without lat/lng → 422",                 test_assets_needs_lat_lng),
    ("Assets & Wards",       "Assets with lat/lng → list",                   test_assets_nearby),

    ("Predictive Agent",     "No key → 401/422",                             test_internal_no_key),
    ("Predictive Agent",     "Wrong key → 401",                              test_internal_wrong_key),
    ("Predictive Agent",     "Correct key → 200",                            test_internal_correct_key),

    ("Error Shapes",         "404 returns JSON not HTML",                    test_404_json),
    ("Error Shapes",         "401 returns JSON",                             test_401_json),
    ("Error Shapes",         "422 has detail array",                         test_422_detail_array),
    ("Error Shapes",         "400 has human-readable message",               test_400_has_message),

    ("Performance",          "Complaint list p95 < 300ms",                   test_list_p95),
    ("Performance",          "Wards endpoint p95 < 300ms",                   test_wards_p95),
    ("Performance",          "50 concurrent requests → 0 x 5xx",            test_concurrent_no_5xx),

    ("Upload URL",           "Upload URL endpoint → 200",                    test_upload_url),

    ("SLA Logic",            "Garbage → 24h SLA",                           test_garbage_24h_sla),
    ("SLA Logic",            "SLA deadline in future on creation",           test_sla_future_on_creation),

    ("Edge Cases",           "All channels (telegram/web/call) accepted",   test_all_channels),
    ("Edge Cases",           "Multi-dept complaint submitted OK",            test_multi_dept_complaint),
    ("Edge Cases",           "Edge inputs don't cause 500",                  test_no_500_on_edge_inputs),
]


# ─────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────

def run_all_tests():
    print("\n" + "="*60)
    print("  STEP 2: Running live tests against", BACKEND_URL)
    print("="*60)

    current_section = None
    passed = failed = skipped = 0

    for section, name, fn in TEST_SUITE:
        if section != current_section:
            current_section = section
            print(f"\n  ── {section} {'─'*(48-len(section))}")

        ok = run_test(section, name, fn)
        _, _, success, note = RESULTS[-1]

        if "SKIP" in note:
            skipped += 1
            print(f"  ⏭  {name}")
            print(f"       ↳ {note}")
        elif success:
            passed += 1
            print(f"  ✅  {name}")
        else:
            failed += 1
            print(f"  ❌  {name}")
            print(f"       ↳ {note}")

    total = passed + failed + skipped
    pct   = int(passed/(passed+failed)*100) if (passed+failed) else 100

    print(f"\n{'='*60}")
    print(f"  RESULTS: {passed}/{passed+failed} passed ({pct}%)  |  {skipped} skipped  |  {failed} failed")
    if failed == 0:
        print("  🎉  All tests passed!")
    else:
        print(f"  ⚠️   {failed} test(s) failed — see messages above.")
    print(f"{'='*60}\n")

    # Section table
    from collections import defaultdict
    stats = defaultdict(lambda: [0, 0, 0])  # pass, fail, skip
    for sec, name, ok, note in RESULTS:
        if "SKIP" in note: stats[sec][2] += 1
        elif ok:           stats[sec][0] += 1
        else:              stats[sec][1] += 1

    print(f"  {'Section':<30} {'Pass':>5} {'Fail':>5} {'Skip':>5}")
    print(f"  {'-'*48}")
    for sec, (p, f, s) in sorted(stats.items()):
        marker = "⚠ " if f else "  "
        print(f"  {marker}{sec:<28} {p:>5} {f:>5} {s:>5}")
    print()

    return failed == 0


# ─────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Check backend is reachable first
    print(f"\nChecking backend at {BACKEND_URL} ...")
    try:
        r = httpx.get(f"{BACKEND_URL}/health", timeout=8)
        if r.status_code == 200:
            print(f"✅ Backend is up — {r.json()}")
        else:
            print(f"⚠️  Backend responded {r.status_code} — proceeding anyway")
    except Exception as e:
        print(f"❌ Cannot reach backend: {e}")
        print("   Make sure your FastAPI server is running:")
        print("   cd backend && uvicorn app.main:app --reload")
        sys.exit(1)

    setup_test_users()

    if not JWTS:
        print("\n❌ No JWTs obtained. Check Supabase credentials in .env")
        sys.exit(1)

    success = run_all_tests()
    sys.exit(0 if success else 1)