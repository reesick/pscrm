import random
import string
from datetime import datetime, timedelta
from pathlib import Path
import json
from typing import Optional

from app.models import ClassificationResult


# ── Grievance ID Generator ────────────────────────────────────────────

def generate_grievance_id() -> str:
    """
    Format: MCD-YYYYMMDD-XXXXX
    Example: MCD-20250315-A7K2M
    The random suffix is alphanumeric uppercase — 5 chars = 36^5 = 60M combinations.
    Collision probability negligible for expected volume (~10K complaints/day).
    """
    date_str = datetime.utcnow().strftime("%Y%m%d")
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"MCD-{date_str}-{suffix}"


# ── State Machine ─────────────────────────────────────────────────────

VALID_TRANSITIONS: dict[str, list[str]] = {
    "NEW":                    ["CLASSIFIED"],
    "CLASSIFIED":             ["ASSIGNED"],
    "ASSIGNED":               ["IN_PROGRESS", "ESCALATED"],
    "IN_PROGRESS":            ["MID_SURVEY_PENDING", "ESCALATED"],
    "MID_SURVEY_PENDING":     ["FINAL_SURVEY_PENDING"],
    "FINAL_SURVEY_PENDING":   ["CLOSED", "REOPENED", "CLOSED_UNVERIFIED"],
    "ESCALATED":              ["ASSIGNED", "CLOSED"],
    "REOPENED":               ["ASSIGNED", "ESCALATED"],
    # CLOSED and CLOSED_UNVERIFIED are terminal — no outgoing transitions
}


def validate_transition(from_status: str, to_status: str) -> bool:
    return to_status in VALID_TRANSITIONS.get(from_status, [])


def get_valid_next_states(current_status: str) -> list[str]:
    """Used by frontend to render only valid options in the status dropdown."""
    return VALID_TRANSITIONS.get(current_status, [])


def is_terminal(status: str) -> bool:
    return status in ["CLOSED", "CLOSED_UNVERIFIED"]


# ── SLA Deadline Calculator ───────────────────────────────────────────

SLA_HOURS_BY_CATEGORY: dict[str, int] = {
    "drainage":    48,
    "streetlight": 72,
    "road":        72,
    "tree":        96,
    "garbage":     24,
    "water_supply": 24,
    "other":       72,
}


def compute_sla_deadline(category: str) -> datetime:
    hours = SLA_HOURS_BY_CATEGORY.get(category, 72)
    return datetime.utcnow() + timedelta(hours=hours)


# ── Keyword Rule Engine ───────────────────────────────────────────────

_keyword_dict_path = Path(__file__).parent / "keyword_dict.json"
KEYWORD_DICT: dict = json.loads(_keyword_dict_path.read_text())

URGENCY_BOOSTERS: dict[str, int] = {
    "fire":        5,
    "accident":    5,
    "collapse":    5,
    "flood":       5,
    "dangerous":   4,
    "broken":      3,
    "blocked":     3,
    "smells":      2,
}


def classify_with_rules(text: str) -> ClassificationResult:
    text_lower = text.lower()
    scores: dict[str, float] = {}

    for category, config in KEYWORD_DICT.items():
        matches = [kw for kw in config["keywords"] if kw in text_lower]
        if matches:
            # Confidence = matched_keywords / total_keywords_in_category (capped at 1.0)
            scores[category] = min(1.0, len(matches) / max(1, len(config["keywords"]) * 0.3))

    if not scores:
        return ClassificationResult(
            category="other",
            urgency=2,
            departments=[],
            asset_types=[],
            confidence=0.0,
            llm_used=False,
        )

    best_category = max(scores, key=scores.get)
    confidence = scores[best_category]

    # Urgency from keyword boosters
    urgency = 2  # default
    for keyword, boost in URGENCY_BOOSTERS.items():
        if keyword in text_lower:
            urgency = max(urgency, boost)

    config = KEYWORD_DICT[best_category]
    dept = config.get("department", "Public Works")
    asset = config.get("asset_type", "road_segment")

    return ClassificationResult(
        category=best_category,
        urgency=urgency,
        departments=[dept] if dept else [],
        asset_types=[asset] if asset else [],
        confidence=confidence,
        llm_used=False,
    )


# ── Audit Log Helper ──────────────────────────────────────────────────

async def log_event(
    complaint_id: Optional[str],
    event_type: str,
    actor_type: str,
    actor_id: str = "system",
    from_status: Optional[str] = None,
    to_status: Optional[str] = None,
    payload: Optional[dict] = None,
) -> None:
    """
    Append-only write to complaint_events.
    Called from routers, agents, and services.
    RLS on this table: INSERT only — no UPDATE or DELETE for anyone.
    """
    from app.database import get_supabase
    sb = await get_supabase()
    await sb.table("complaint_events").insert({
        "complaint_id": complaint_id,
        "event_type":   event_type,
        "actor_type":   actor_type,
        "actor_id":     actor_id,
        "from_status":  from_status,
        "to_status":    to_status,
        "payload":      payload or {},
    }).execute()
