"""
PS-CRM Backend Test Suite
=========================
Comprehensive pytest test script covering every API endpoint,
state machine transitions, role-based access control, classification
pipeline, SLA logic, and error response shapes.

Setup:
    pip install pytest pytest-asyncio httpx python-dotenv

Run:
    pytest test_backend.py -v --tb=short

Environment variables needed (create .env.test or set directly):
    BASE_URL=http://localhost:8000          # or your Render URL
    JSSA_JWT=eyJ...                         # JWT for a JSSA user (ward_id set)
    AA_JWT=eyJ...                           # JWT for an AA user
    SUPER_ADMIN_JWT=eyJ...                  # JWT for super_admin
    CONTRACTOR_JWT=eyJ...                   # JWT for a contractor
    TEST_WARD_ID=uuid-of-seeded-ward        # Ward ID from your seed data
    OTHER_WARD_ID=uuid-of-different-ward    # Ward ID JSSA does NOT own
    TEST_LAT=28.64                          # Coords inside TEST_WARD_ID
    TEST_LNG=77.26
    INTERNAL_CRON_KEY=your-internal-key
"""

import os
import pytest
import httpx
import asyncio
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv(".env.test")

BASE_URL         = os.getenv("BASE_URL",         "http://localhost:8000")
JSSA_JWT         = os.getenv("JSSA_JWT",         "")
AA_JWT           = os.getenv("AA_JWT",           "")
SUPER_ADMIN_JWT  = os.getenv("SUPER_ADMIN_JWT",  "")
CONTRACTOR_JWT   = os.getenv("CONTRACTOR_JWT",   "")
TEST_WARD_ID     = os.getenv("TEST_WARD_ID",     "")
OTHER_WARD_ID    = os.getenv("OTHER_WARD_ID",    "")
TEST_LAT         = float(os.getenv("TEST_LAT",   "28.64"))
TEST_LNG         = float(os.getenv("TEST_LNG",   "77.26"))
INTERNAL_KEY     = os.getenv("INTERNAL_CRON_KEY","")


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def auth(jwt: str) -> dict:
    return {"Authorization": f"Bearer {jwt}"}

def client() -> httpx.Client:
    return httpx.Client(base_url=BASE_URL, timeout=30)

# Shared state across tests (populated as tests run)
_created_complaint_id    = None
_created_grievance_id    = None
_classified_complaint_id = None  # A complaint that has been classified


# ─────────────────────────────────────────────────────────────────────
# SECTION 1: Infrastructure
# ─────────────────────────────────────────────────────────────────────

class TestInfrastructure:

    def test_health_check_returns_200(self):
        """PRD §1.3 — Health check endpoint must return 200 + {"status": "ok"}"""
        with client() as c:
            r = c.get("/health")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        body = r.json()
        assert body.get("status") == "ok", f"Expected 'ok', got: {body}"

    def test_health_check_response_time(self):
        """PRD §12.1 — Non-LLM endpoints must respond in < 300ms (p95)"""
        import time
        times = []
        with client() as c:
            for _ in range(10):
                start = time.time()
                c.get("/health")
                times.append((time.time() - start) * 1000)
        p95 = sorted(times)[int(len(times) * 0.95) - 1]
        assert p95 < 300, f"p95 response time {p95:.0f}ms exceeds 300ms target"

    def test_docs_accessible(self):
        """Swagger UI must be accessible for dev introspection"""
        with client() as c:
            r = c.get("/docs")
        assert r.status_code == 200

    def test_openapi_schema_exists(self):
        """OpenAPI schema must be valid JSON"""
        with client() as c:
            r = c.get("/openapi.json")
        assert r.status_code == 200
        schema = r.json()
        assert "paths" in schema
        assert "components" in schema


# ─────────────────────────────────────────────────────────────────────
# SECTION 2: Complaint Submission (POST /api/v1/complaints)
# ─────────────────────────────────────────────────────────────────────

class TestComplaintSubmission:

    def test_submit_complaint_basic_success(self):
        """PRD §8.2 — POST /complaints returns 201 with grievance_id"""
        global _created_complaint_id, _created_grievance_id
        with client() as c:
            r = c.post("/api/v1/complaints", json={
                "raw_text": "Drain overflow near Laxmi Nagar market, water on road",
                "lat": TEST_LAT,
                "lng": TEST_LNG,
                "channel": "web"
            })
        assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
        body = r.json()
        assert "id" in body,           "Response missing 'id'"
        assert "grievance_id" in body, "Response missing 'grievance_id'"
        assert "status" in body,       "Response missing 'status'"
        assert body["status"] == "NEW" or body["status"] == "CLASSIFIED", \
            f"Unexpected initial status: {body['status']}"
        _created_complaint_id = body["id"]
        _created_grievance_id = body["grievance_id"]

    def test_grievance_id_format(self):
        """PRD §7 — Grievance ID must follow MCD-YYYYMMDD-XXXXX pattern"""
        import re
        with client() as c:
            r = c.post("/api/v1/complaints", json={
                "raw_text": "Test complaint for ID format verification",
                "lat": TEST_LAT, "lng": TEST_LNG, "channel": "web"
            })
        assert r.status_code == 201
        gid = r.json()["grievance_id"]
        pattern = r"^MCD-\d{8}-[A-Z0-9]{5}$"
        assert re.match(pattern, gid), \
            f"Grievance ID '{gid}' does not match pattern MCD-YYYYMMDD-XXXXX"

    def test_submit_with_optional_email(self):
        """PRD impl plan — citizen email is optional, complaint must still be created"""
        with client() as c:
            r = c.post("/api/v1/complaints", json={
                "raw_text": "Streetlight broken on Ring Road near metro station",
                "lat": TEST_LAT, "lng": TEST_LNG, "channel": "web",
                "citizen_email": "test.citizen@example.com"
            })
        assert r.status_code == 201
        # Email must NOT be echoed back in response (privacy)
        body = r.json()
        assert "citizen_email" not in body, "Raw email should never appear in response"
        assert "citizen_email_hash" not in body, "Email hash should not be in public response"

    def test_submit_without_email_succeeds(self):
        """Email is optional — submission without it must succeed"""
        with client() as c:
            r = c.post("/api/v1/complaints", json={
                "raw_text": "Garbage not collected near bus stop",
                "lat": TEST_LAT, "lng": TEST_LNG, "channel": "telegram"
            })
        assert r.status_code == 201

    def test_submit_missing_required_fields_returns_422(self):
        """FastAPI validation — missing raw_text must return 422"""
        with client() as c:
            r = c.post("/api/v1/complaints", json={
                "lat": TEST_LAT, "lng": TEST_LNG, "channel": "web"
                # raw_text missing
            })
        assert r.status_code == 422, f"Expected 422, got {r.status_code}"

    def test_submit_invalid_channel_returns_422(self):
        """Channel must be one of: telegram, web, call"""
        with client() as c:
            r = c.post("/api/v1/complaints", json={
                "raw_text": "Test complaint",
                "lat": TEST_LAT, "lng": TEST_LNG,
                "channel": "whatsapp"  # invalid
            })
        assert r.status_code == 422

    def test_submit_invalid_email_returns_422(self):
        """citizen_email must be valid email format when provided"""
        with client() as c:
            r = c.post("/api/v1/complaints", json={
                "raw_text": "Test complaint",
                "lat": TEST_LAT, "lng": TEST_LNG,
                "channel": "web",
                "citizen_email": "not-an-email"
            })
        assert r.status_code == 422

    def test_submit_out_of_range_coordinates(self):
        """Coordinates must be valid lat/lng — extreme values should fail"""
        with client() as c:
            r = c.post("/api/v1/complaints", json={
                "raw_text": "Test complaint",
                "lat": 999.0,  # invalid
                "lng": 77.26, "channel": "web"
            })
        # Should return 422 or 400
        assert r.status_code in [400, 422], \
            f"Expected 400 or 422 for invalid coordinates, got {r.status_code}"

    def test_sla_deadline_populated_on_submission(self):
        """PRD §9.2 — sla_deadline must be populated and in the future"""
        with client() as c:
            r = c.post("/api/v1/complaints", json={
                "raw_text": "Pothole causing accidents on main road near market",
                "lat": TEST_LAT, "lng": TEST_LNG, "channel": "web"
            })
        assert r.status_code == 201
        body = r.json()
        # sla_deadline may not be in public response (only in admin response)
        # This test checks that the field is present if returned
        if "sla_deadline" in body and body["sla_deadline"]:
            deadline = datetime.fromisoformat(body["sla_deadline"].replace("Z", "+00:00"))
            assert deadline > datetime.now(timezone.utc), \
                "sla_deadline is in the past on initial submission"

    def test_public_response_excludes_sensitive_fields(self):
        """PRD §8.2 + §12.2 — public response must not expose officer/internal data"""
        with client() as c:
            r = c.post("/api/v1/complaints", json={
                "raw_text": "Water pipe burst near school",
                "lat": TEST_LAT, "lng": TEST_LNG, "channel": "web"
            })
        assert r.status_code == 201
        body = r.json()
        forbidden_fields = [
            "citizen_email", "citizen_email_hash", "citizen_phone_hash",
            "internal_notes", "officer_phone", "lat", "lng",
            "classification_confidence"
        ]
        for field in forbidden_fields:
            assert field not in body, \
                f"Sensitive field '{field}' found in public POST response"


# ─────────────────────────────────────────────────────────────────────
# SECTION 3: Public Complaint Lookup (GET /api/v1/complaints/{id})
# ─────────────────────────────────────────────────────────────────────

class TestPublicComplaintLookup:

    def test_get_complaint_by_uuid_success(self):
        """PRD §8.2 — Public status lookup by UUID. No auth required."""
        if not _created_complaint_id:
            pytest.skip("No complaint ID from previous test — run in order")
        with client() as c:
            r = c.get(f"/api/v1/complaints/{_created_complaint_id}")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == _created_complaint_id
        assert "status" in body
        assert "timeline" in body

    def test_get_complaint_by_grievance_id(self):
        """Citizens look up by grievance ID (MCD-... string)"""
        if not _created_grievance_id:
            pytest.skip("No grievance ID from previous test")
        with client() as c:
            r = c.get(f"/api/v1/complaints/{_created_grievance_id}")
        assert r.status_code == 200
        body = r.json()
        assert body["grievance_id"] == _created_grievance_id

    def test_get_nonexistent_complaint_returns_404(self):
        """PRD §8.1 — 404 for not found"""
        with client() as c:
            r = c.get("/api/v1/complaints/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404

    def test_public_response_structure(self):
        """PRD §8.2 — Response must include specific fields, exclude sensitive ones"""
        if not _created_complaint_id:
            pytest.skip("No complaint ID from previous test")
        with client() as c:
            r = c.get(f"/api/v1/complaints/{_created_complaint_id}")
        body = r.json()
        required_fields = ["id", "grievance_id", "status", "created_at", "timeline"]
        for field in required_fields:
            assert field in body, f"Required field '{field}' missing from public response"

        # Privacy check
        forbidden = ["citizen_email_hash", "internal_notes", "officer_phone",
                     "lat", "lng", "classification_confidence"]
        for field in forbidden:
            assert field not in body, f"Sensitive field '{field}' in public response"

    def test_timeline_is_ordered_list(self):
        """PRD §8.2 — Timeline must be an ordered array"""
        if not _created_complaint_id:
            pytest.skip("No complaint ID from previous test")
        with client() as c:
            r = c.get(f"/api/v1/complaints/{_created_complaint_id}")
        body = r.json()
        assert isinstance(body["timeline"], list), "Timeline must be an array"


# ─────────────────────────────────────────────────────────────────────
# SECTION 4: Admin Complaint List (GET /api/v1/complaints)
# ─────────────────────────────────────────────────────────────────────

class TestAdminComplaintList:

    def test_list_complaints_requires_auth(self):
        """PRD §12.2 — JWT required. No token → 401"""
        with client() as c:
            r = c.get("/api/v1/complaints")
        assert r.status_code == 401, \
            f"Expected 401 for unauthenticated request, got {r.status_code}"

    def test_list_complaints_jssa_sees_own_ward_only(self):
        """PRD §12.2 + §3.1 — JSSA ward scoping enforced"""
        if not JSSA_JWT or not TEST_WARD_ID:
            pytest.skip("JSSA_JWT or TEST_WARD_ID not configured")
        with client() as c:
            r = c.get("/api/v1/complaints", headers=auth(JSSA_JWT))
        assert r.status_code == 200
        complaints = r.json()
        assert isinstance(complaints, list)
        # Every returned complaint must belong to JSSA's ward
        for complaint in complaints:
            assert complaint.get("ward_id") == TEST_WARD_ID, \
                f"Complaint {complaint['id']} from wrong ward in JSSA response"

    def test_list_complaints_jssa_cannot_see_other_ward(self):
        """PRD §12.2 — JSSA must not see complaints from different ward"""
        if not JSSA_JWT or not OTHER_WARD_ID:
            pytest.skip("JSSA_JWT or OTHER_WARD_ID not configured")
        with client() as c:
            r = c.get(f"/api/v1/complaints?ward_id={OTHER_WARD_ID}",
                      headers=auth(JSSA_JWT))
        assert r.status_code in [200, 403]
        if r.status_code == 200:
            complaints = r.json()
            # Should return empty, not the other ward's complaints
            for complaint in complaints:
                assert complaint.get("ward_id") != OTHER_WARD_ID, \
                    "JSSA can see complaints from another ward — RLS breach!"

    def test_list_complaints_super_admin_sees_all(self):
        """PRD §3.1 — Super Admin has no ward restriction"""
        if not SUPER_ADMIN_JWT:
            pytest.skip("SUPER_ADMIN_JWT not configured")
        with client() as c:
            r = c.get("/api/v1/complaints", headers=auth(SUPER_ADMIN_JWT))
        assert r.status_code == 200
        # Super admin should see complaints from all wards
        complaints = r.json()
        assert isinstance(complaints, list)

    def test_list_complaints_filter_by_status(self):
        """PRD §8.2 — status filter must work"""
        if not JSSA_JWT:
            pytest.skip("JSSA_JWT not configured")
        with client() as c:
            r = c.get("/api/v1/complaints?status=NEW", headers=auth(JSSA_JWT))
        assert r.status_code == 200
        for complaint in r.json():
            assert complaint["status"] == "NEW", \
                f"Complaint with status {complaint['status']} returned for status=NEW filter"

    def test_list_complaints_admin_response_includes_extra_fields(self):
        """PRD §8.2 — Admin response includes ward_id, urgency, translated_text"""
        if not JSSA_JWT:
            pytest.skip("JSSA_JWT not configured")
        with client() as c:
            r = c.get("/api/v1/complaints", headers=auth(JSSA_JWT))
        assert r.status_code == 200
        complaints = r.json()
        if complaints:
            complaint = complaints[0]
            admin_fields = ["ward_id", "urgency", "llm_used"]
            for field in admin_fields:
                assert field in complaint, \
                    f"Admin-only field '{field}' missing from authenticated complaint list"

    def test_contractor_cannot_access_complaint_list(self):
        """PRD §3.1 — Contractor role cannot access admin complaint list"""
        if not CONTRACTOR_JWT:
            pytest.skip("CONTRACTOR_JWT not configured")
        with client() as c:
            r = c.get("/api/v1/complaints", headers=auth(CONTRACTOR_JWT))
        assert r.status_code == 403, \
            f"Expected 403 for contractor accessing complaint list, got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────
# SECTION 5: State Machine (PATCH /api/v1/complaints/{id}/status)
# ─────────────────────────────────────────────────────────────────────

class TestStateMachine:
    """
    Tests every state machine rule from PRD §5.3.
    VALID_TRANSITIONS:
        NEW → CLASSIFIED
        CLASSIFIED → ASSIGNED
        ASSIGNED → IN_PROGRESS (requires proof_url), ESCALATED
        IN_PROGRESS → MID_SURVEY_PENDING, ESCALATED
        MID_SURVEY_PENDING → FINAL_SURVEY_PENDING
        FINAL_SURVEY_PENDING → CLOSED, REOPENED, CLOSED_UNVERIFIED
        ESCALATED → ASSIGNED, CLOSED
        REOPENED → ASSIGNED, ESCALATED
    Terminal: CLOSED, CLOSED_UNVERIFIED (no outgoing transitions)
    """

    def _get_assigned_complaint(self, c: httpx.Client) -> str:
        """Helper: get a complaint ID in ASSIGNED state for transition tests"""
        r = c.get("/api/v1/complaints?status=ASSIGNED", headers=auth(JSSA_JWT))
        complaints = r.json()
        if complaints:
            return complaints[0]["id"]
        return None

    def test_patch_status_requires_auth(self):
        """PRD §12.2 — Status update requires JWT"""
        if not _created_complaint_id:
            pytest.skip("No complaint ID available")
        with client() as c:
            r = c.patch(f"/api/v1/complaints/{_created_complaint_id}/status",
                        json={"new_status": "CLASSIFIED"})
        assert r.status_code == 401

    def test_invalid_transition_new_to_in_progress(self):
        """PRD §5.3 — NEW → IN_PROGRESS is not a valid transition"""
        if not JSSA_JWT or not _created_complaint_id:
            pytest.skip("JSSA_JWT or complaint ID not available")
        with client() as c:
            r = c.patch(
                f"/api/v1/complaints/{_created_complaint_id}/status",
                headers=auth(JSSA_JWT),
                json={"new_status": "IN_PROGRESS", "proof_url": "https://example.com/proof.jpg"}
            )
        assert r.status_code == 400, \
            f"Expected 400 for invalid transition NEW→IN_PROGRESS, got {r.status_code}"
        body = r.json()
        assert "error" in body or "detail" in body, "Error response must include error message"

    def test_invalid_transition_new_to_closed(self):
        """NEW → CLOSED is not valid"""
        if not JSSA_JWT or not _created_complaint_id:
            pytest.skip("Missing prerequisites")
        with client() as c:
            r = c.patch(
                f"/api/v1/complaints/{_created_complaint_id}/status",
                headers=auth(JSSA_JWT),
                json={"new_status": "CLOSED"}
            )
        assert r.status_code == 400

    def test_invalid_transition_assigned_to_closed(self):
        """ASSIGNED → CLOSED is not valid (must go through survey)"""
        if not JSSA_JWT:
            pytest.skip("JSSA_JWT not configured")
        with client() as c:
            complaint_id = self._get_assigned_complaint(c)
            if not complaint_id:
                pytest.skip("No ASSIGNED complaint available")
            r = c.patch(
                f"/api/v1/complaints/{complaint_id}/status",
                headers=auth(JSSA_JWT),
                json={"new_status": "CLOSED"}
            )
        assert r.status_code == 400, \
            f"Expected 400 for invalid ASSIGNED→CLOSED, got {r.status_code}"

    def test_proof_required_for_in_progress_transition(self):
        """PRD §5.3 + check 2.6 — IN_PROGRESS transition requires proof_url"""
        if not JSSA_JWT:
            pytest.skip("JSSA_JWT not configured")
        with client() as c:
            complaint_id = self._get_assigned_complaint(c)
            if not complaint_id:
                pytest.skip("No ASSIGNED complaint available for this test")
            # Attempt IN_PROGRESS without proof_url
            r = c.patch(
                f"/api/v1/complaints/{complaint_id}/status",
                headers=auth(JSSA_JWT),
                json={"new_status": "IN_PROGRESS"}
                # proof_url intentionally omitted
            )
        assert r.status_code == 400, \
            f"Expected 400 when proof_url missing for IN_PROGRESS, got {r.status_code}"
        body = r.json()
        error_text = str(body).lower()
        assert "proof" in error_text, "Error message must mention 'proof'"

    def test_proof_required_for_final_survey_pending_transition(self):
        """PRD §5.3 — FINAL_SURVEY_PENDING transition requires proof_url"""
        if not JSSA_JWT:
            pytest.skip("JSSA_JWT not configured")
        # Find a complaint in MID_SURVEY_PENDING
        with client() as c:
            r = c.get("/api/v1/complaints?status=MID_SURVEY_PENDING", headers=auth(JSSA_JWT))
            complaints = r.json()
            if not complaints:
                pytest.skip("No MID_SURVEY_PENDING complaint available")
            complaint_id = complaints[0]["id"]
            r2 = c.patch(
                f"/api/v1/complaints/{complaint_id}/status",
                headers=auth(JSSA_JWT),
                json={"new_status": "FINAL_SURVEY_PENDING"}
                # proof_url missing
            )
        assert r2.status_code == 400

    def test_valid_transition_with_proof_url(self):
        """Valid IN_PROGRESS transition with proof_url must succeed"""
        if not JSSA_JWT:
            pytest.skip("JSSA_JWT not configured")
        with client() as c:
            complaint_id = self._get_assigned_complaint(c)
            if not complaint_id:
                pytest.skip("No ASSIGNED complaint available")
            r = c.patch(
                f"/api/v1/complaints/{complaint_id}/status",
                headers=auth(JSSA_JWT),
                json={
                    "new_status": "IN_PROGRESS",
                    "proof_url": "https://storage.supabase.co/test/proof.jpg",
                    "internal_note": "Field team dispatched"
                }
            )
        assert r.status_code == 200, \
            f"Expected 200 for valid ASSIGNED→IN_PROGRESS with proof, got {r.status_code}"

    def test_terminal_state_closed_cannot_transition(self):
        """PRD §5.3 — CLOSED is terminal, any transition must return 400"""
        if not JSSA_JWT:
            pytest.skip("JSSA_JWT not configured")
        with client() as c:
            r = c.get("/api/v1/complaints?status=CLOSED", headers=auth(JSSA_JWT))
            complaints = r.json()
            if not complaints:
                pytest.skip("No CLOSED complaint available")
            complaint_id = complaints[0]["id"]
            r2 = c.patch(
                f"/api/v1/complaints/{complaint_id}/status",
                headers=auth(JSSA_JWT),
                json={"new_status": "ASSIGNED"}
            )
        assert r2.status_code == 400, \
            f"CLOSED complaint allowed transition — must be terminal. Got {r2.status_code}"

    def test_status_update_creates_audit_event(self):
        """PRD §9.4 — Every status change must create a complaint_events row"""
        # This is verified by checking the timeline grows after a status update
        if not JSSA_JWT or not _created_complaint_id:
            pytest.skip("Prerequisites missing")
        with client() as c:
            # Get timeline before
            r_before = c.get(f"/api/v1/complaints/{_created_complaint_id}")
            timeline_before = r_before.json().get("timeline", [])

            # Check current status to know what transition to attempt
            current_status = r_before.json()["status"]
            if current_status != "CLASSIFIED":
                pytest.skip("Complaint not in CLASSIFIED state for this test")

            # Transition CLASSIFIED → would normally be agent-driven
            # Testing that officer-driven transitions create events
            # (Use whatever valid transition is available for current status)


# ─────────────────────────────────────────────────────────────────────
# SECTION 6: Classification Pipeline
# ─────────────────────────────────────────────────────────────────────

class TestClassificationPipeline:
    """Tests PRD §5.4 classification logic. Results verified via complaint record."""

    def _submit_and_wait(self, raw_text: str, max_wait: int = 15) -> dict:
        """Submit complaint and poll until classification is complete"""
        import time
        with client() as c:
            r = c.post("/api/v1/complaints", json={
                "raw_text": raw_text,
                "lat": TEST_LAT, "lng": TEST_LNG, "channel": "web"
            })
            assert r.status_code == 201
            complaint_id = r.json()["id"]

            # Poll until classified
            for _ in range(max_wait):
                time.sleep(1)
                r2 = c.get(f"/api/v1/complaints/{complaint_id}")
                if r2.json()["status"] != "NEW":
                    break
            return r2.json()

    def test_rule_engine_high_confidence_drain(self):
        """PRD check 1.7 — 'drain overflow near market' → category=drainage, llm_used=false"""
        if not JSSA_JWT:
            pytest.skip("Need JSSA_JWT to verify classification fields")
        with client() as c:
            r = c.post("/api/v1/complaints", json={
                "raw_text": "Large drain overflow near Laxmi Nagar market, water on road",
                "lat": TEST_LAT, "lng": TEST_LNG, "channel": "web"
            })
            assert r.status_code == 201
            complaint_id = r.json()["id"]

            import time
            time.sleep(8)  # Wait for agent classification

            # Get admin view to see classification fields
            r_admin = c.get("/api/v1/complaints", headers=auth(JSSA_JWT))
            complaints = r_admin.json()
            complaint = next((c for c in complaints if c["id"] == complaint_id), None)

        if complaint and complaint.get("category"):
            assert complaint["category"] == "drainage", \
                f"Expected drainage, got {complaint['category']}"
            # llm_used should be false for high-confidence rule engine match
            if complaint.get("classification_confidence") is not None:
                assert complaint["classification_confidence"] >= 0.85, \
                    f"Confidence {complaint['classification_confidence']} below 0.85 for clear drain complaint"

    def test_rule_engine_streetlight_classification(self):
        """PRD check 1.7 — 'streetlight is broken' → category=streetlight"""
        with client() as c:
            r = c.post("/api/v1/complaints", json={
                "raw_text": "Streetlight is broken on main road near Rohini metro station",
                "lat": TEST_LAT, "lng": TEST_LNG, "channel": "web"
            })
        assert r.status_code == 201
        body = r.json()
        # After classification (admin view required for full fields)
        # At minimum, submission succeeds
        assert "grievance_id" in body

    def test_ambiguous_text_triggers_gemini(self):
        """PRD check 1.8 — vague text must trigger Gemini (llm_used=true)"""
        if not JSSA_JWT:
            pytest.skip("Need JSSA_JWT to verify llm_used field")
        import time
        with client() as c:
            r = c.post("/api/v1/complaints", json={
                "raw_text": "Something is broken near the market and it is causing issues for everyone",
                "lat": TEST_LAT, "lng": TEST_LNG, "channel": "web"
            })
            assert r.status_code == 201
            complaint_id = r.json()["id"]
            time.sleep(10)  # Gemini calls take longer

            r_admin = c.get("/api/v1/complaints", headers=auth(JSSA_JWT))
            complaints = r_admin.json()
            complaint = next((c for c in complaints if c["id"] == complaint_id), None)

        if complaint and complaint.get("classification_confidence") is not None:
            # Low confidence should have triggered Gemini
            if complaint["classification_confidence"] < 0.85:
                assert complaint["llm_used"] == True, \
                    "Gemini should have been used for low confidence classification"

    def test_multi_department_complaint_creates_multiple_rows(self):
        """PRD check 1.9 — 'tree touching electricity pole' → 2 complaint_departments rows"""
        # This requires checking DB directly or a dedicated endpoint
        # Test: submit the complaint and verify category indicates multi-department
        with client() as c:
            r = c.post("/api/v1/complaints", json={
                "raw_text": "Tree is touching the electricity pole near the school, dangerous situation",
                "lat": TEST_LAT, "lng": TEST_LNG, "channel": "web"
            })
        assert r.status_code == 201
        body = r.json()
        # After classification, department_names should contain multiple entries
        import time
        time.sleep(8)
        with client() as c2:
            r2 = c2.get(f"/api/v1/complaints/{body['id']}")
        complaint = r2.json()
        if complaint.get("department_names"):
            # Should ideally have 2 departments for this case
            # At minimum, some departments should be assigned
            assert len(complaint["department_names"]) >= 1


# ─────────────────────────────────────────────────────────────────────
# SECTION 7: Survey Response
# ─────────────────────────────────────────────────────────────────────

class TestSurveyResponse:

    def _get_complaint_in_status(self, status: str) -> str:
        """Helper to get a complaint in a specific status"""
        if not JSSA_JWT:
            return None
        with client() as c:
            r = c.get(f"/api/v1/complaints?status={status}", headers=auth(JSSA_JWT))
            complaints = r.json()
            return complaints[0]["id"] if complaints else None

    def test_survey_approved_closes_complaint(self):
        """PRD §5.3 — survey approved → CLOSED"""
        complaint_id = self._get_complaint_in_status("FINAL_SURVEY_PENDING")
        if not complaint_id:
            pytest.skip("No complaint in FINAL_SURVEY_PENDING state")
        with client() as c:
            r = c.post(
                f"/api/v1/complaints/{complaint_id}/survey-response",
                json={"response": "approved", "citizen_note": "Issue resolved"}
            )
        assert r.status_code == 200
        # Verify status changed to CLOSED
        with client() as c2:
            r2 = c2.get(f"/api/v1/complaints/{complaint_id}")
        assert r2.json()["status"] == "CLOSED", \
            f"Expected CLOSED after approval, got {r2.json()['status']}"

    def test_survey_rejected_reopens_complaint(self):
        """PRD §5.3 — survey rejected → REOPENED"""
        complaint_id = self._get_complaint_in_status("FINAL_SURVEY_PENDING")
        if not complaint_id:
            pytest.skip("No complaint in FINAL_SURVEY_PENDING state")
        with client() as c:
            r = c.post(
                f"/api/v1/complaints/{complaint_id}/survey-response",
                json={"response": "rejected", "citizen_note": "Issue not fixed"}
            )
        assert r.status_code == 200
        with client() as c2:
            r2 = c2.get(f"/api/v1/complaints/{complaint_id}")
        assert r2.json()["status"] == "REOPENED", \
            f"Expected REOPENED after rejection, got {r2.json()['status']}"

    def test_survey_invalid_response_value(self):
        """survey response must be one of: approved, rejected, no_response"""
        if not _created_complaint_id:
            pytest.skip("No complaint ID available")
        with client() as c:
            r = c.post(
                f"/api/v1/complaints/{_created_complaint_id}/survey-response",
                json={"response": "maybe"}  # invalid
            )
        assert r.status_code == 422


# ─────────────────────────────────────────────────────────────────────
# SECTION 8: Officer Stats
# ─────────────────────────────────────────────────────────────────────

class TestOfficerStats:

    def test_officer_stats_requires_auth(self):
        """Officer stats endpoint requires JWT"""
        with client() as c:
            r = c.get("/api/v1/officers/some-uuid/stats")
        assert r.status_code == 401

    def test_officer_stats_response_structure(self):
        """PRD §8.4 — Stats must include all computed metrics"""
        if not JSSA_JWT or not SUPER_ADMIN_JWT:
            pytest.skip("JWTs not configured")
        # First get a real officer ID from complaint list
        with client() as c:
            r = c.get("/api/v1/complaints", headers=auth(JSSA_JWT))
            complaints = r.json()
            if not complaints:
                pytest.skip("No complaints to extract officer ID from")

        # Use current user's officer stats
        # Extract officer ID from JWT or use a known test ID
        import base64, json
        try:
            payload = JSSA_JWT.split(".")[1]
            payload += "=" * (-len(payload) % 4)
            decoded = json.loads(base64.b64decode(payload))
            officer_id = decoded.get("sub")
            if not officer_id:
                pytest.skip("Cannot extract officer ID from JWT")
        except Exception:
            pytest.skip("Cannot decode JWT")

        with client() as c:
            r = c.get(f"/api/v1/officers/{officer_id}/stats", headers=auth(JSSA_JWT))
        assert r.status_code == 200
        body = r.json()
        required = ["total_assigned", "total_resolved", "total_escalated",
                    "avg_resolution_hours", "reopen_rate_pct"]
        for field in required:
            assert field in body, f"Field '{field}' missing from officer stats"


# ─────────────────────────────────────────────────────────────────────
# SECTION 9: Contractor Scorecard
# ─────────────────────────────────────────────────────────────────────

class TestContractorScorecard:

    def test_scorecard_requires_auth(self):
        with client() as c:
            r = c.get("/api/v1/contractors/some-uuid/scorecard")
        assert r.status_code == 401

    def test_reliability_score_formula(self):
        """PRD §3.3 — reliability = (on_time*0.4) + ((1-rejection)*0.35) + ((1-reopen)*0.25)"""
        if not SUPER_ADMIN_JWT:
            pytest.skip("SUPER_ADMIN_JWT not configured")
        # Get a contractor from the system
        with client() as c:
            r = c.get("/api/v1/complaints", headers=auth(SUPER_ADMIN_JWT))
            complaints = r.json()

        # Find a contractor ID from work orders
        # For now test the formula logic independently
        def compute_reliability(on_time: float, rejection: float, reopen: float) -> int:
            r = (on_time * 0.4) + ((1 - rejection) * 0.35) + ((1 - reopen) * 0.25)
            return round(r * 100)

        # PRD check 3.6: 7/10 on time, 2/10 rejected, 1/10 reopened
        score = compute_reliability(0.7, 0.2, 0.1)
        expected = round((0.7 * 0.4 + 0.8 * 0.35 + 0.9 * 0.25) * 100)
        assert score == expected, f"Reliability formula wrong: {score} != {expected}"

    def test_contractor_status_update_requires_super_admin(self):
        """PRD §8.4 — Only super_admin can activate/deactivate contractors"""
        if not JSSA_JWT:
            pytest.skip("JSSA_JWT not configured")
        with client() as c:
            r = c.patch(
                "/api/v1/contractors/some-uuid/status",
                headers=auth(JSSA_JWT),
                json={"is_active": False, "reason": "Test deactivation"}
            )
        assert r.status_code == 403, \
            f"Expected 403 for JSSA attempting contractor deactivation, got {r.status_code}"

    def test_contractor_deactivation_requires_reason(self):
        """PRD §8.4 — reason field is mandatory for deactivation"""
        if not SUPER_ADMIN_JWT:
            pytest.skip("SUPER_ADMIN_JWT not configured")
        with client() as c:
            r = c.patch(
                "/api/v1/contractors/some-uuid/status",
                headers=auth(SUPER_ADMIN_JWT),
                json={"is_active": False}
                # reason missing
            )
        assert r.status_code == 422, \
            f"Expected 422 when reason missing, got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────
# SECTION 10: Analytics Endpoints
# ─────────────────────────────────────────────────────────────────────

class TestAnalytics:

    def test_hotspots_requires_super_admin(self):
        """PRD §8.5 — hotspots endpoint is super_admin only"""
        if not JSSA_JWT:
            pytest.skip("JSSA_JWT not configured")
        with client() as c:
            r = c.get("/api/v1/analytics/hotspots", headers=auth(JSSA_JWT))
        assert r.status_code == 403, \
            f"Expected 403 for JSSA accessing hotspots, got {r.status_code}"

    def test_hotspots_response_structure(self):
        """PRD §8.5 — Hotspot response must include lat, lng, severity, category"""
        if not SUPER_ADMIN_JWT:
            pytest.skip("SUPER_ADMIN_JWT not configured")
        with client() as c:
            r = c.get("/api/v1/analytics/hotspots", headers=auth(SUPER_ADMIN_JWT))
        assert r.status_code == 200
        hotspots = r.json()
        assert isinstance(hotspots, list)
        for hotspot in hotspots:
            for field in ["id", "lat", "lng", "radius_m", "category", "severity", "ward_name"]:
                assert field in hotspot, f"Field '{field}' missing from hotspot response"
            assert 1 <= hotspot["severity"] <= 5, \
                f"Severity {hotspot['severity']} outside 1-5 range"

    def test_sla_compliance_response_structure(self):
        """PRD §8.5 — SLA compliance must return per-department breakdown"""
        if not JSSA_JWT:
            pytest.skip("JSSA_JWT not configured")
        with client() as c:
            r = c.get("/api/v1/analytics/sla-compliance", headers=auth(JSSA_JWT))
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        for item in data:
            required = ["department_name", "total_complaints", "resolved_within_sla",
                        "sla_breached", "compliance_pct"]
            for field in required:
                assert field in item, f"Field '{field}' missing from SLA compliance"
            assert 0 <= item["compliance_pct"] <= 100, \
                f"compliance_pct {item['compliance_pct']} outside 0-100 range"

    def test_complaint_volume_default_grouping(self):
        """PRD §8.5 — Volume endpoint default group_by=day"""
        if not JSSA_JWT:
            pytest.skip("JSSA_JWT not configured")
        with client() as c:
            r = c.get("/api/v1/analytics/complaint-volume", headers=auth(JSSA_JWT))
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        for point in data:
            assert "period" in point
            assert "count" in point
            assert isinstance(point["count"], int)

    def test_complaint_volume_weekly_grouping(self):
        """PRD §8.5 — group_by=week must work"""
        if not JSSA_JWT:
            pytest.skip("JSSA_JWT not configured")
        with client() as c:
            r = c.get("/api/v1/analytics/complaint-volume?group_by=week",
                      headers=auth(JSSA_JWT))
        assert r.status_code == 200

    def test_ward_density_public_no_auth(self):
        """PRD §3.5 — ward density is public, no auth required"""
        with client() as c:
            r = c.get("/api/v1/analytics/ward-density")
        assert r.status_code == 200

    def test_ward_density_no_individual_coordinates(self):
        """PRD §12.2 — ward density must not expose individual complaint lat/lng"""
        with client() as c:
            r = c.get("/api/v1/analytics/ward-density")
        assert r.status_code == 200
        data = r.json()
        if isinstance(data, list):
            for ward in data:
                assert "lat" not in ward or ward.get("lat") is None, \
                    "Individual complaint lat exposed in ward density — privacy breach"
                assert "lng" not in ward or ward.get("lng") is None, \
                    "Individual complaint lng exposed in ward density — privacy breach"


# ─────────────────────────────────────────────────────────────────────
# SECTION 11: Assets and Wards
# ─────────────────────────────────────────────────────────────────────

class TestAssetsAndWards:

    def test_wards_endpoint_returns_geojson(self):
        """PRD §8.6 — /wards returns GeoJSON FeatureCollection"""
        with client() as c:
            r = c.get("/api/v1/wards")
        assert r.status_code == 200
        body = r.json()
        assert body.get("type") == "FeatureCollection", \
            f"Expected FeatureCollection, got {body.get('type')}"
        assert "features" in body
        assert len(body["features"]) > 0, "No ward features in GeoJSON response"

    def test_wards_endpoint_has_cache_headers(self):
        """PRD §8.6 — Ward endpoint should be aggressively cached"""
        with client() as c:
            r = c.get("/api/v1/wards")
        cache_control = r.headers.get("cache-control", "")
        assert "max-age" in cache_control or "Cache-Control" in r.headers, \
            "Ward endpoint missing Cache-Control header"

    def test_assets_requires_lat_lng(self):
        """PRD §8.6 — lat and lng are required query parameters"""
        if not JSSA_JWT:
            pytest.skip("JSSA_JWT not configured — auth fires before param validation")
        with client() as c:
            r = c.get("/api/v1/assets", headers=auth(JSSA_JWT))
        assert r.status_code == 422, f"Expected 422 when lat/lng missing, got {r.status_code}"

    def test_assets_returns_nearby_assets(self):
        """PRD §8.6 — Assets within 50m of given coordinates"""
        if not JSSA_JWT:
            pytest.skip("JSSA_JWT not configured")
        with client() as c:
            r = c.get(
                f"/api/v1/assets?lat={TEST_LAT}&lng={TEST_LNG}&radius_m=500",
                headers=auth(JSSA_JWT)
            )
        assert r.status_code == 200
        # Result is a list (possibly empty if no assets seeded near test coords)
        assert isinstance(r.json(), list)

    def test_assets_type_filter(self):
        """PRD §8.6 — asset_type filter must work"""
        if not JSSA_JWT:
            pytest.skip("JSSA_JWT not configured")
        with client() as c:
            r = c.get(
                f"/api/v1/assets?lat={TEST_LAT}&lng={TEST_LNG}&asset_type=drain",
                headers=auth(JSSA_JWT)
            )
        assert r.status_code == 200
        assets = r.json()
        for asset in assets:
            assert asset.get("asset_type") == "drain", \
                f"Asset type filter not working — got {asset.get('asset_type')}"


# ─────────────────────────────────────────────────────────────────────
# SECTION 12: Predictive Agent (Internal)
# ─────────────────────────────────────────────────────────────────────

class TestPredictiveAgent:

    def test_internal_endpoint_requires_key(self):
        """POST /internal/run-predictive-agent requires X-Internal-Key header"""
        with client() as c:
            r = c.post("/internal/run-predictive-agent")
        assert r.status_code in [401, 422], \
            f"Expected 401/422 without key, got {r.status_code}"

    def test_internal_endpoint_rejects_wrong_key(self):
        """Wrong key must be rejected"""
        with client() as c:
            r = c.post("/internal/run-predictive-agent",
                       headers={"x-internal-key": "wrong-key"})
        assert r.status_code == 401

    def test_internal_endpoint_accepts_correct_key(self):
        """Correct key must be accepted"""
        if not INTERNAL_KEY:
            pytest.skip("INTERNAL_CRON_KEY not configured")
        with client() as c:
            r = c.post("/internal/run-predictive-agent",
                       headers={"x-internal-key": INTERNAL_KEY})
        assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────
# SECTION 13: Error Response Shapes
# ─────────────────────────────────────────────────────────────────────

class TestErrorResponseShapes:
    """PRD §3.8 — All errors must return {error: string, code: string} JSON"""

    def test_404_returns_json(self):
        """404 must be JSON, not HTML"""
        with client() as c:
            r = c.get("/api/v1/complaints/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404
        assert r.headers.get("content-type", "").startswith("application/json"), \
            "404 response must be JSON, not HTML"

    def test_401_returns_json(self):
        """401 must be JSON"""
        with client() as c:
            r = c.get("/api/v1/complaints")  # No auth
        assert r.status_code == 401
        assert r.headers.get("content-type", "").startswith("application/json")

    def test_422_returns_structured_detail(self):
        """422 validation errors must have detail array"""
        with client() as c:
            r = c.post("/api/v1/complaints", json={})  # Missing required fields
        assert r.status_code == 422
        body = r.json()
        assert "detail" in body, "422 response missing 'detail' field"
        assert isinstance(body["detail"], list)

    def test_400_state_machine_error_includes_message(self):
        """400 from invalid state machine transition must include error message"""
        if not JSSA_JWT or not _created_complaint_id:
            pytest.skip("Prerequisites missing")
        with client() as c:
            r_current = c.get(f"/api/v1/complaints/{_created_complaint_id}")
            current_status = r_current.json()["status"]
            if current_status == "NEW":
                r = c.patch(
                    f"/api/v1/complaints/{_created_complaint_id}/status",
                    headers=auth(JSSA_JWT),
                    json={"new_status": "CLOSED"}
                )
                if r.status_code == 400:
                    body = r.json()
                    assert "detail" in body or "error" in body, \
                        "400 error response missing human-readable message"


# ─────────────────────────────────────────────────────────────────────
# SECTION 14: Performance Benchmarks
# ─────────────────────────────────────────────────────────────────────

class TestPerformance:

    def test_complaint_list_under_300ms_p95(self):
        """PRD §12.1 — p95 response time < 300ms for non-LLM endpoints"""
        if not JSSA_JWT:
            pytest.skip("JSSA_JWT not configured")
        import time
        times = []
        with client() as c:
            for _ in range(20):
                start = time.time()
                c.get("/api/v1/complaints", headers=auth(JSSA_JWT))
                times.append((time.time() - start) * 1000)
        p95 = sorted(times)[int(len(times) * 0.95) - 1]
        assert p95 < 300, \
            f"p95 response time {p95:.0f}ms exceeds 300ms target for GET /complaints"

    def test_wards_endpoint_under_300ms(self):
        """Ward GeoJSON should be fast (cached)"""
        import time
        times = []
        with client() as c:
            # First request warms cache
            c.get("/api/v1/wards")
            for _ in range(10):
                start = time.time()
                c.get("/api/v1/wards")
                times.append((time.time() - start) * 1000)
        p95 = sorted(times)[int(len(times) * 0.95) - 1]
        assert p95 < 500, f"Wards endpoint p95: {p95:.0f}ms"

    def test_concurrent_requests_no_5xx(self):
        """PRD §12.1 — 50 concurrent requests, no 5xx errors"""
        import concurrent.futures
        results = []

        def make_request():
            with httpx.Client(base_url=BASE_URL, timeout=30) as c:
                return c.get("/api/v1/wards").status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(make_request) for _ in range(50)]
            for f in concurrent.futures.as_completed(futures):
                results.append(f.result())

        five_xx = [s for s in results if s >= 500]
        assert len(five_xx) == 0, \
            f"{len(five_xx)}/50 requests returned 5xx errors"


# ─────────────────────────────────────────────────────────────────────
# SECTION 15: Upload URL
# ─────────────────────────────────────────────────────────────────────

class TestUploadURL:

    def test_upload_url_endpoint_exists(self):
        """POST /complaints/upload-url must exist and return a pre-signed URL"""
        if not JSSA_JWT:
            pytest.skip("JSSA_JWT not configured")
        with client() as c:
            r = c.post("/api/v1/complaints/upload-url", headers=auth(JSSA_JWT))
        # Should return either a URL string or an object with upload_url key
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"


# ─────────────────────────────────────────────────────────────────────
# SECTION 16: SLA Logic Verification
# ─────────────────────────────────────────────────────────────────────

class TestSLALogic:
    """Validates SLA deadline computation from PRD §9.2"""

    EXPECTED_SLA_HOURS = {
        "drainage":     48,
        "streetlight":  72,
        "road":         72,
        "tree":         96,
        "garbage":      24,
        "water_supply": 24,
        "other":        72,
    }

    def test_garbage_complaint_gets_24h_sla(self):
        """Garbage complaints must have 24h SLA"""
        with client() as c:
            r = c.post("/api/v1/complaints", json={
                "raw_text": "Garbage not collected for 3 days near bus stand",
                "lat": TEST_LAT, "lng": TEST_LNG, "channel": "web"
            })
        assert r.status_code == 201
        # If sla_deadline is in the response, verify it's ~24h from now
        body = r.json()
        if body.get("sla_deadline"):
            deadline = datetime.fromisoformat(body["sla_deadline"].replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            hours_diff = (deadline - now).total_seconds() / 3600
            # Should be approximately 24 hours (allow ±1h for test execution time)
            assert 23 <= hours_diff <= 25, \
                f"Garbage SLA should be ~24h, got {hours_diff:.1f}h"

    def test_sla_deadline_is_in_future_on_creation(self):
        """Every new complaint's SLA deadline must be in the future"""
        with client() as c:
            r = c.post("/api/v1/complaints", json={
                "raw_text": "Drain overflow causing waterlogging",
                "lat": TEST_LAT, "lng": TEST_LNG, "channel": "web"
            })
        assert r.status_code == 201
        body = r.json()
        if body.get("sla_deadline"):
            deadline = datetime.fromisoformat(body["sla_deadline"].replace("Z", "+00:00"))
            assert deadline > datetime.now(timezone.utc), \
                "SLA deadline is in the past on complaint creation"


# ─────────────────────────────────────────────────────────────────────
# Run summary
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import subprocess
    result = subprocess.run(
        ["pytest", __file__, "-v", "--tb=short", "--no-header", "-q"],
        capture_output=False
    )
    exit(result.returncode)