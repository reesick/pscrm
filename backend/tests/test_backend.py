"""
tests/test_backend.py — Pure unit tests for PS-CRM backend.

Coverage:
  * utils.py        — grievance ID, state machine, SLA calculator, keyword classifier
  * models.py       — Pydantic schema validation and enums
  * database.py     — hash_email pure function
  * config.py       — settings fields and types
  * keyword dict    — keyword_dict.json integrity
  * agents_followup — DBSCAN parameter constants
  * security        — PII checks on public response schemas

No external services, no Supabase connections, no mocking.

Run:
    cd d:\\ps-crm\\backend
    pytest tests/test_backend.py -v
"""
from __future__ import annotations

import os
from datetime import datetime

import pytest

# ── Ensure all required env vars are present before any app imports ───────────
# Only applied if NOT already set (e.g. when running in CI without .env).
os.environ.setdefault("SUPABASE_URL",              "https://fakeproject.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZha2UiLCJyb2xlIjoic2VydmljZV9yb2xlIiwiaWF0IjoxNjAwMDAwMDAwLCJleHAiOjI1MDAwMDAwMDB9.fake")
os.environ.setdefault("SUPABASE_ANON_KEY",         "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZha2UiLCJyb2xlIjoiYW5vbiIsImlhdCI6MTYwMDAwMDAwMCwiZXhwIjoyNTAwMDAwMDAwfQ.fake")
os.environ.setdefault("GEMINI_API_KEY",            "fake-gemini-key")
os.environ.setdefault("BHASHINI_USER_ID",          "fake-bhashini-user")
os.environ.setdefault("BHASHINI_API_KEY",          "fake-bhashini-key")
os.environ.setdefault("BHASHINI_PIPELINE_ID",      "fake-pipeline-id")
os.environ.setdefault("TELEGRAM_BOT_TOKEN",        "123456789:AAfakeTokenForTestingPurposesOnly1")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET",   "webhooksecret")
os.environ.setdefault("SMTP_HOST",                 "smtp.example.com")
os.environ.setdefault("SMTP_PORT",                 "587")
os.environ.setdefault("SMTP_USERNAME",             "test@example.com")
os.environ.setdefault("SMTP_PASSWORD",             "testpass")
os.environ.setdefault("SMTP_FROM_EMAIL",           "test@example.com")
os.environ.setdefault("FRONTEND_URL",              "http://localhost:3000")
os.environ.setdefault("BACKEND_URL",               "http://localhost:8000")
os.environ.setdefault("INTERNAL_CRON_KEY",         "supersecretcronkey")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — utils.py
# ══════════════════════════════════════════════════════════════════════════════

class TestGenerateGrievanceId:
    def test_format(self):
        from app.utils import generate_grievance_id
        gid = generate_grievance_id()
        parts = gid.split("-")
        assert len(parts) == 3
        assert parts[0] == "MCD"
        assert len(parts[1]) == 8
        assert parts[1].isdigit()
        assert len(parts[2]) == 5
        assert parts[2].isalnum()

    def test_uniqueness(self):
        from app.utils import generate_grievance_id
        ids = {generate_grievance_id() for _ in range(200)}
        assert len(ids) == 200

    def test_date_component_is_today(self):
        from app.utils import generate_grievance_id
        gid = generate_grievance_id()
        date_part = gid.split("-")[1]
        today = datetime.utcnow().strftime("%Y%m%d")
        assert date_part == today


class TestStateMachine:
    def test_valid_new_to_classified(self):
        from app.utils import validate_transition
        assert validate_transition("NEW", "CLASSIFIED") is True

    def test_valid_classified_to_assigned(self):
        from app.utils import validate_transition
        assert validate_transition("CLASSIFIED", "ASSIGNED") is True

    def test_valid_assigned_to_inprogress(self):
        from app.utils import validate_transition
        assert validate_transition("ASSIGNED", "IN_PROGRESS") is True

    def test_valid_assigned_to_escalated(self):
        from app.utils import validate_transition
        assert validate_transition("ASSIGNED", "ESCALATED") is True

    def test_valid_escalated_to_assigned(self):
        from app.utils import validate_transition
        assert validate_transition("ESCALATED", "ASSIGNED") is True

    def test_invalid_new_to_closed(self):
        from app.utils import validate_transition
        assert validate_transition("NEW", "CLOSED") is False

    def test_invalid_closed_to_anything(self):
        from app.utils import validate_transition, get_valid_next_states
        assert validate_transition("CLOSED", "NEW") is False
        assert get_valid_next_states("CLOSED") == []

    def test_invalid_skip_states(self):
        from app.utils import validate_transition
        assert validate_transition("NEW", "ASSIGNED") is False
        assert validate_transition("NEW", "IN_PROGRESS") is False

    def test_terminal_states(self):
        from app.utils import is_terminal
        assert is_terminal("CLOSED") is True
        assert is_terminal("CLOSED_UNVERIFIED") is True
        assert is_terminal("ASSIGNED") is False
        assert is_terminal("NEW") is False

    def test_all_valid_transitions_pass(self):
        from app.utils import VALID_TRANSITIONS, validate_transition
        for from_s, tos in VALID_TRANSITIONS.items():
            for to_s in tos:
                assert validate_transition(from_s, to_s) is True, (
                    f"Expected {from_s} -> {to_s} to be valid"
                )

    def test_get_valid_next_states(self):
        from app.utils import get_valid_next_states
        states = get_valid_next_states("ASSIGNED")
        assert "IN_PROGRESS" in states
        assert "ESCALATED" in states
        assert "CLOSED" not in states

    def test_unknown_state_returns_empty(self):
        from app.utils import get_valid_next_states
        assert get_valid_next_states("NONEXISTENT") == []


class TestSlaCalculator:
    def test_garbage_is_24h(self):
        from app.utils import compute_sla_deadline, SLA_HOURS_BY_CATEGORY
        before = datetime.utcnow()
        deadline = compute_sla_deadline("garbage")
        assert SLA_HOURS_BY_CATEGORY["garbage"] == 24
        diff = (deadline - before).total_seconds() / 3600
        assert 23.9 < diff < 24.1

    def test_tree_is_96h(self):
        from app.utils import compute_sla_deadline
        before = datetime.utcnow()
        deadline = compute_sla_deadline("tree")
        diff = (deadline - before).total_seconds() / 3600
        assert 95.9 < diff < 96.1

    def test_unknown_category_defaults_to_72h(self):
        from app.utils import compute_sla_deadline
        before = datetime.utcnow()
        deadline = compute_sla_deadline("alien_invasion")
        diff = (deadline - before).total_seconds() / 3600
        assert 71.9 < diff < 72.1

    def test_all_categories_have_positive_hours(self):
        from app.utils import SLA_HOURS_BY_CATEGORY
        for cat, hours in SLA_HOURS_BY_CATEGORY.items():
            assert hours > 0, f"{cat} has non-positive SLA hours"

    def test_deadline_is_in_the_future(self):
        from app.utils import compute_sla_deadline
        deadline = compute_sla_deadline("road")
        assert deadline > datetime.utcnow()

    def test_drainage_sla_within_bounds(self):
        from app.utils import compute_sla_deadline, SLA_HOURS_BY_CATEGORY
        hours = SLA_HOURS_BY_CATEGORY.get("drainage", 72)
        before = datetime.utcnow()
        deadline = compute_sla_deadline("drainage")
        diff = (deadline - before).total_seconds() / 3600
        assert abs(diff - hours) < 0.1


class TestHashEmail:
    def test_sha256_output_length(self):
        from app.database import hash_email
        result = hash_email("citizen@example.com")
        assert len(result) == 64

    def test_same_input_same_output(self):
        from app.database import hash_email
        assert hash_email("test@test.com") == hash_email("test@test.com")

    def test_different_emails_differ(self):
        from app.database import hash_email
        assert hash_email("a@a.com") != hash_email("b@b.com")

    def test_raw_email_not_in_output(self):
        from app.database import hash_email
        email = "secretemail@example.com"
        assert email not in hash_email(email)

    def test_case_insensitive_normalisation(self):
        from app.database import hash_email
        assert hash_email("USER@EXAMPLE.COM") == hash_email("user@example.com")

    def test_whitespace_normalisation(self):
        from app.database import hash_email
        assert hash_email("  user@example.com  ") == hash_email("user@example.com")

    def test_output_is_lowercase_hex(self):
        from app.database import hash_email
        result = hash_email("test@example.com")
        assert result == result.lower()
        assert all(c in "0123456789abcdef" for c in result)


class TestKeywordClassifier:
    def test_drainage_keywords(self):
        from app.utils import classify_with_rules
        result = classify_with_rules("there is a blocked drain outside my house")
        assert result.category == "drainage"

    def test_streetlight_keywords(self):
        from app.utils import classify_with_rules
        result = classify_with_rules("the streetlight on main road is broken and not working")
        assert result.category == "streetlight"

    def test_garbage_keywords(self):
        from app.utils import classify_with_rules
        result = classify_with_rules("garbage not collected for 3 days smells terrible")
        assert result.category == "garbage"

    def test_fire_urgency_booster(self):
        from app.utils import classify_with_rules
        result = classify_with_rules("fire near the drain collapse emergency")
        assert result.urgency >= 4

    def test_unknown_text_returns_other(self):
        from app.utils import classify_with_rules
        result = classify_with_rules("xyz zyx abc def")
        assert result.category == "other"

    def test_returns_classification_result_type(self):
        from app.utils import classify_with_rules
        from app.models import ClassificationResult
        result = classify_with_rules("broken pipe water supply")
        assert isinstance(result, ClassificationResult)

    def test_departments_list_not_empty(self):
        from app.utils import classify_with_rules
        result = classify_with_rules("road is severely damaged and full of potholes")
        assert isinstance(result.departments, list)
        assert len(result.departments) >= 1

    def test_sql_injection_doesnt_crash(self):
        from app.utils import classify_with_rules
        result = classify_with_rules("\'; DROP TABLE complaints; --")
        assert result.category in {
            "drainage", "streetlight", "road", "tree",
            "garbage", "water_supply", "other",
        }

    def test_xss_doesnt_crash(self):
        from app.utils import classify_with_rules
        result = classify_with_rules("<script>alert(\'xss\')</script>")
        assert result is not None

    def test_unicode_text_doesnt_crash(self):
        from app.utils import classify_with_rules
        result = classify_with_rules("\u0928\u093e\u0932\u0940 \u092c\u0902\u0926 \u0939\u0948")
        assert result is not None

    def test_very_long_text(self):
        from app.utils import classify_with_rules
        result = classify_with_rules("drain " * 500)
        assert result.category == "drainage"

    def test_confidence_between_0_and_1(self):
        from app.utils import classify_with_rules
        result = classify_with_rules("streetlight not working")
        assert 0.0 <= result.confidence <= 1.0

    def test_urgency_between_1_and_5(self):
        from app.utils import classify_with_rules
        result = classify_with_rules("broken road")
        assert isinstance(result.urgency, int)
        assert 1 <= result.urgency <= 5

    def test_road_category(self):
        from app.utils import classify_with_rules
        result = classify_with_rules("pothole on the main road causing accidents")
        assert result.category == "road"

    def test_water_supply_category(self):
        from app.utils import classify_with_rules
        result = classify_with_rules("no water supply for 2 days pipe leaking")
        assert result.category == "water_supply"


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — models.py (Pydantic validation)
# ══════════════════════════════════════════════════════════════════════════════

class TestComplaintCreateRequest:
    def test_valid_full_payload(self):
        from app.models import ComplaintCreateRequest, Channel
        req = ComplaintCreateRequest(
            citizen_email="user@example.com",
            raw_text="There is a broken streetlight near park",
            lat=28.6139, lng=77.2090,
            media_urls=["https://example.com/photo.jpg"],
            channel=Channel.WEB,
        )
        assert req.citizen_email == "user@example.com"
        assert req.channel == Channel.WEB

    def test_optional_email(self):
        from app.models import ComplaintCreateRequest, Channel
        req = ComplaintCreateRequest(
            raw_text="Garbage overflow", lat=28.6, lng=77.2, channel=Channel.TELEGRAM,
        )
        assert req.citizen_email is None

    def test_invalid_email_rejected(self):
        from app.models import ComplaintCreateRequest, Channel
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            ComplaintCreateRequest(
                citizen_email="not-an-email", raw_text="test",
                lat=28.6, lng=77.2, channel=Channel.WEB,
            )

    def test_missing_raw_text_rejected(self):
        from app.models import ComplaintCreateRequest, Channel
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            ComplaintCreateRequest(lat=28.6, lng=77.2, channel=Channel.WEB)

    def test_media_urls_defaults_empty(self):
        from app.models import ComplaintCreateRequest, Channel
        req = ComplaintCreateRequest(raw_text="test", lat=0, lng=0, channel=Channel.WEB)
        assert req.media_urls == []

    def test_all_channel_enum_values_accepted(self):
        from app.models import ComplaintCreateRequest, Channel
        for ch in Channel:
            req = ComplaintCreateRequest(raw_text="test", lat=0, lng=0, channel=ch)
            assert req.channel == ch


class TestComplaintStatusUpdateRequest:
    def test_valid_status(self):
        from app.models import ComplaintStatusUpdateRequest, ComplaintStatus
        req = ComplaintStatusUpdateRequest(new_status=ComplaintStatus.IN_PROGRESS)
        assert req.new_status == ComplaintStatus.IN_PROGRESS

    def test_invalid_status_rejected(self):
        from app.models import ComplaintStatusUpdateRequest
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            ComplaintStatusUpdateRequest(new_status="FLYING")

    def test_optional_proof_url_defaults_none(self):
        from app.models import ComplaintStatusUpdateRequest, ComplaintStatus
        req = ComplaintStatusUpdateRequest(new_status=ComplaintStatus.ASSIGNED)
        assert req.proof_url is None

    def test_internal_note_accepted(self):
        from app.models import ComplaintStatusUpdateRequest, ComplaintStatus
        req = ComplaintStatusUpdateRequest(
            new_status=ComplaintStatus.IN_PROGRESS,
            internal_note="Work in progress",
        )
        assert req.internal_note == "Work in progress"


class TestEnums:
    def test_complaint_statuses_complete(self):
        from app.models import ComplaintStatus
        statuses = [s.value for s in ComplaintStatus]
        assert "NEW" in statuses
        assert "CLOSED" in statuses
        assert "CLOSED_UNVERIFIED" in statuses
        assert len(statuses) == 10

    def test_user_roles(self):
        from app.models import UserRole
        roles = [r.value for r in UserRole]
        assert "jssa" in roles
        assert "super_admin" in roles

    def test_channels(self):
        from app.models import Channel
        channels = [c.value for c in Channel]
        assert "telegram" in channels
        assert "web" in channels

    def test_survey_response_values(self):
        from app.models import SurveyResponse
        values = [s.value for s in SurveyResponse]
        assert "approved" in values
        assert "rejected" in values


class TestClassificationResultModel:
    def test_valid_result(self):
        from app.models import ClassificationResult
        r = ClassificationResult(
            category="drainage", urgency=3,
            departments=["Public Works"], asset_types=["drain"],
            confidence=0.95, llm_used=False,
        )
        assert r.category == "drainage"
        assert r.confidence == 0.95

    def test_model_dump_is_json_serialisable(self):
        import json
        from app.models import ClassificationResult
        r = ClassificationResult(
            category="garbage", urgency=1,
            departments=["Sanitation"], asset_types=[],
            confidence=0.7, llm_used=False,
        )
        json.dumps(r.model_dump())  # Should not raise


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — Security (pure, no network)
# ══════════════════════════════════════════════════════════════════════════════

class TestSecurityChecks:
    def test_public_response_has_no_citizen_email(self):
        from app.models import ComplaintPublicResponse
        fields = ComplaintPublicResponse.model_fields.keys()
        assert "citizen_email" not in fields
        assert "citizen_email_hash" not in fields

    def test_admin_response_has_no_citizen_email(self):
        from app.models import ComplaintAdminResponse
        fields = ComplaintAdminResponse.model_fields.keys()
        assert "citizen_email" not in fields
        assert "citizen_email_hash" not in fields

    def test_hash_email_is_irreversible(self):
        from app.database import hash_email
        original = "private@citizen.com"
        hashed = hash_email(original)
        assert original not in hashed
        assert "@" not in hashed

    def test_classifier_handles_null_bytes(self):
        from app.utils import classify_with_rules
        result = classify_with_rules("drain \x00 blocked")
        assert result is not None

    def test_classifier_handles_emoji_input(self):
        from app.utils import classify_with_rules
        result = classify_with_rules("\U0001f6b0" * 50 + " water supply problem")
        assert result is not None


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — Config
# ══════════════════════════════════════════════════════════════════════════════

class TestConfig:
    def test_settings_loads(self):
        from app.config import settings
        assert settings.SUPABASE_URL.startswith("https://")
        assert settings.SMTP_PORT == 587

    def test_all_required_fields_present(self):
        from app.config import settings
        required = [
            "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_ANON_KEY",
            "GEMINI_API_KEY", "BHASHINI_USER_ID", "BHASHINI_API_KEY",
            "TELEGRAM_BOT_TOKEN", "SMTP_HOST", "SMTP_PORT",
            "FRONTEND_URL", "BACKEND_URL", "INTERNAL_CRON_KEY",
        ]
        for field in required:
            assert hasattr(settings, field), f"Missing config field: {field}"

    def test_smtp_port_is_int(self):
        from app.config import settings
        assert isinstance(settings.SMTP_PORT, int)

    def test_supabase_url_is_non_empty_string(self):
        from app.config import settings
        assert isinstance(settings.SUPABASE_URL, str)
        assert len(settings.SUPABASE_URL) > 0

    def test_internal_cron_key_minimum_length(self):
        from app.config import settings
        assert len(settings.INTERNAL_CRON_KEY) >= 8


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — Keyword dict integrity
# ══════════════════════════════════════════════════════════════════════════════

class TestKeywordDict:
    def test_dict_loads_without_error(self):
        from app.utils import KEYWORD_DICT
        assert isinstance(KEYWORD_DICT, dict)
        assert len(KEYWORD_DICT) > 0

    def test_all_categories_have_keywords(self):
        from app.utils import KEYWORD_DICT
        for cat, data in KEYWORD_DICT.items():
            assert "keywords" in data, f"Category {cat} missing \'keywords\'"
            assert len(data["keywords"]) > 0, f"Category {cat} has empty keywords"

    def test_all_categories_have_department(self):
        from app.utils import KEYWORD_DICT
        for cat, data in KEYWORD_DICT.items():
            assert "department" in data, f"Category {cat} missing \'department\'"
            assert data["department"], f"Category {cat} has empty department"

    def test_expected_categories_present(self):
        from app.utils import KEYWORD_DICT
        expected = {"drainage", "streetlight", "road", "tree", "garbage", "water_supply", "other"}
        assert expected.issubset(set(KEYWORD_DICT.keys()))

    def test_keywords_are_lowercase(self):
        from app.utils import KEYWORD_DICT
        for cat, data in KEYWORD_DICT.items():
            for kw in data["keywords"]:
                assert kw == kw.lower(), f"Keyword \'{kw}\' in {cat} is not lowercase"

    def test_no_duplicate_category_keys(self):
        from app.utils import KEYWORD_DICT
        keys = list(KEYWORD_DICT.keys())
        assert len(keys) == len(set(keys))


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — DBSCAN constants and algorithm validation
# ══════════════════════════════════════════════════════════════════════════════

class TestPredictiveAgentConstants:
    def test_dbscan_eps(self):
        from app.agents_followup import _DBSCAN_EPS
        assert _DBSCAN_EPS == 0.0018

    def test_dbscan_min_samples(self):
        from app.agents_followup import _DBSCAN_MIN
        assert _DBSCAN_MIN == 5

    def test_tight_cluster_detected(self):
        import numpy as np
        from sklearn.cluster import DBSCAN
        from app.agents_followup import _DBSCAN_EPS, _DBSCAN_MIN
        # 10 points within 0.0009 degrees of each other — well within eps
        coords = np.array([
            [28.6139 + i * 0.00008, 77.2090 + i * 0.00008]
            for i in range(10)
        ])
        db = DBSCAN(eps=_DBSCAN_EPS, min_samples=_DBSCAN_MIN).fit(coords)
        assert set(db.labels_) == {0}

    def test_scattered_points_all_noise(self):
        import numpy as np
        from sklearn.cluster import DBSCAN
        from app.agents_followup import _DBSCAN_EPS, _DBSCAN_MIN
        # 5 points more than 1 degree apart
        coords = np.array([[28.0 + i, 77.0 + i] for i in range(5)])
        db = DBSCAN(eps=_DBSCAN_EPS, min_samples=_DBSCAN_MIN).fit(coords)
        assert set(db.labels_) == {-1}

    def test_min_cluster_size_boundary(self):
        import numpy as np
        from sklearn.cluster import DBSCAN
        from app.agents_followup import _DBSCAN_EPS, _DBSCAN_MIN
        # Exactly min_samples points in one spot — should form a cluster
        coords = np.array([[28.6, 77.2]] * _DBSCAN_MIN)
        db = DBSCAN(eps=_DBSCAN_EPS, min_samples=_DBSCAN_MIN).fit(coords)
        assert 0 in db.labels_

    def test_below_min_cluster_size_is_noise(self):
        import numpy as np
        from sklearn.cluster import DBSCAN
        from app.agents_followup import _DBSCAN_EPS, _DBSCAN_MIN
        # One fewer than min_samples — all noise
        coords = np.array([[28.6, 77.2]] * (_DBSCAN_MIN - 1))
        db = DBSCAN(eps=_DBSCAN_EPS, min_samples=_DBSCAN_MIN).fit(coords)
        assert set(db.labels_) == {-1}
