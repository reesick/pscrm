"""
app/agents_followup.py — Follow-Up, Survey, Contractor, and Predictive agents.

Four background agents started as asyncio tasks inside app/main.py lifespan:
  - Follow-Up Agent:   monitors SLA deadlines every 60 s
  - Survey Agent:      fires when status → FINAL_SURVEY_PENDING
  - Contractor Agent:  fires when a work-order is assigned to a contractor
  - Predictive Agent:  DBSCAN hotspot detection (called nightly, or via Render Cron)
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from sklearn.cluster import DBSCAN

from app.database import get_supabase
from app.services import notify, send_sla_warning_email, telegram_send
from app.utils import SLA_HOURS_BY_CATEGORY, log_event

# ── idempotency helpers ───────────────────────────────────────────────

async def _already_logged(complaint_id: str, event_type: str, payload_key: str, payload_value: str) -> bool:
    """True if a complaint_event row already exists with matching type + payload key-value."""
    sb = await get_supabase()
    result = await sb.table("complaint_events") \
        .select("id", count="exact") \
        .eq("complaint_id", complaint_id) \
        .eq("event_type", event_type) \
        .eq(f"payload->>{payload_key}", payload_value) \
        .execute()
    return bool(result.count and result.count > 0)


# ══════════════════════════════════════════════════════════════════════
# FOLLOW-UP AGENT — SLA monitoring
# ══════════════════════════════════════════════════════════════════════

async def check_sla_deadlines() -> None:
    """
    Runs every 60 seconds.
    For every complaint that is ASSIGNED or IN_PROGRESS:
      - At 50 % of SLA budget elapsed  → send a warning
      - At 90 % of SLA budget elapsed  → send another warning
      - At 100 % of SLA budget elapsed → escalate
    All actions are idempotent (checked via complaint_events).
    """
    sb = await get_supabase()
    now = datetime.now(timezone.utc)

    active = await sb.table("complaints") \
        .select("id, category, status, created_at, ward_id") \
        .in_("status", ["ASSIGNED", "IN_PROGRESS"]) \
        .execute()

    for complaint in (active.data or []):
        complaint_id = complaint["id"]
        category     = complaint.get("category", "other")
        sla_hours    = SLA_HOURS_BY_CATEGORY.get(category, 72)

        created_at = datetime.fromisoformat(complaint["created_at"].replace("Z", "+00:00"))
        elapsed_h  = (now - created_at).total_seconds() / 3600
        pct        = elapsed_h / sla_hours

        if pct >= 1.0:
            await escalate_complaint(complaint_id, pct)
        elif pct >= 0.9:
            await send_sla_warning(complaint_id, pct=90)
        elif pct >= 0.5:
            await send_sla_warning(complaint_id, pct=50)


async def send_sla_warning(complaint_id: str, pct: int) -> None:
    """Send SLA warning at 50 % or 90 % of budget — idempotent."""
    marker = f"{pct}pct"
    if await _already_logged(complaint_id, "sla_warning", "pct", marker):
        return

    sb = await get_supabase()
    complaint = await sb.table("complaints") \
        .select("id, category, ward_id") \
        .eq("id", complaint_id) \
        .maybe_single() \
        .execute()
    if not complaint.data:
        return

    # Notify all JSSAs assigned to this complaint
    depts = await sb.table("complaint_departments") \
        .select("officer_id") \
        .eq("complaint_id", complaint_id) \
        .in_("sub_status", ["ASSIGNED", "IN_PROGRESS"]) \
        .execute()

    officer_ids = {d["officer_id"] for d in (depts.data or []) if d.get("officer_id")}

    for officer_id in officer_ids:
        officer = await sb.table("officers").select("id, email").eq("id", officer_id).maybe_single().execute()
        if officer.data and officer.data.get("email"):
            await send_sla_warning_email(
                to=officer.data["email"],
                grievance_id=complaint_id,
                pct=pct,
            )
        await notify(officer_id, "sla_warning", {"complaint_id": complaint_id, "pct": pct})

    await log_event(
        complaint_id,
        event_type="sla_warning",
        actor_type="agent",
        actor_id="followup_agent",
        payload={"pct": marker},
    )


async def escalate_complaint(complaint_id: str, elapsed_pct: float) -> None:
    """
    Escalate a complaint that has breached its SLA — idempotent.
    Escalation ladder: JSSA overdue → notify AA; AA overdue → notify FAA; FAA overdue → Super Admin.
    """
    if await _already_logged(complaint_id, "escalation", "reason", "sla_breach"):
        return

    sb = await get_supabase()

    # Fetch current assignees
    depts = await sb.table("complaint_departments") \
        .select("officer_id, department_id") \
        .eq("complaint_id", complaint_id) \
        .execute()

    for dept in (depts.data or []):
        officer_id = dept.get("officer_id")
        if not officer_id:
            continue

        officer = await sb.table("officers") \
            .select("id, role, zone_id") \
            .eq("id", officer_id) \
            .maybe_single() \
            .execute()
        if not officer.data:
            continue

        officer_role = officer.data.get("role")
        supervisor_role = {"jssa": "aa", "aa": "faa", "faa": "super_admin"}.get(officer_role)
        if not supervisor_role:
            continue

        # Find supervisor in the same zone
        supervisor_result = await sb.table("officers") \
            .select("id") \
            .eq("role", supervisor_role) \
            .eq("zone_id", officer.data.get("zone_id")) \
            .limit(1) \
            .execute()

        if supervisor_result.data:
            supervisor_id = supervisor_result.data[0]["id"]
            await notify(
                supervisor_id,
                "sla_breach_escalation",
                {"complaint_id": complaint_id, "elapsed_pct": round(elapsed_pct * 100, 1)},
            )

    await log_event(
        complaint_id,
        event_type="escalation",
        actor_type="agent",
        actor_id="followup_agent",
        payload={"reason": "sla_breach", "elapsed_pct": round(elapsed_pct * 100, 1)},
    )


async def start_followup_agent() -> None:
    """Infinite asyncio task — called once from main.py lifespan."""
    print("[FollowUp Agent] Started — checking SLA deadlines every 60 s")
    while True:
        try:
            await check_sla_deadlines()
        except Exception as e:
            import traceback
            print(f"[FollowUp Agent] Error in check_sla_deadlines: {e}\n{traceback.format_exc()}")
        await asyncio.sleep(60)


# ══════════════════════════════════════════════════════════════════════
# SURVEY AGENT — Citizen satisfaction survey after resolution
# ══════════════════════════════════════════════════════════════════════

# Active auto-close tasks keyed by complaint_id
_survey_timers: dict[str, asyncio.Task] = {}


async def _auto_close_unverified(complaint_id: str) -> None:
    """Wait 72 h after FINAL_SURVEY_PENDING → set CLOSED_UNVERIFIED if no response."""
    await asyncio.sleep(72 * 3600)
    sb = await get_supabase()

    # Only act if still in FINAL_SURVEY_PENDING
    current = await sb.table("complaints") \
        .select("status") \
        .eq("id", complaint_id) \
        .maybe_single() \
        .execute()
    if not current.data or current.data["status"] != "FINAL_SURVEY_PENDING":
        return

    await sb.table("complaints") \
        .update({"status": "CLOSED_UNVERIFIED"}) \
        .eq("id", complaint_id) \
        .execute()

    await log_event(
        complaint_id,
        event_type="status_change",
        actor_type="agent",
        actor_id="survey_agent",
        from_status="FINAL_SURVEY_PENDING",
        to_status="CLOSED_UNVERIFIED",
        payload={"reason": "no_survey_response_72h"},
    )


async def on_final_survey_pending(complaint_id: str) -> None:
    """
    Called from routers_complaints PATCH when status transitions to FINAL_SURVEY_PENDING.
    Sends survey message to citizen via Telegram, starts 72-h auto-close timer.
    """
    sb = await get_supabase()

    complaint = await sb.table("complaints") \
        .select("citizen_telegram_chat_id, id") \
        .eq("id", complaint_id) \
        .maybe_single() \
        .execute()
    if not complaint.data:
        return

    telegram_id = complaint.data.get("citizen_telegram_chat_id")
    if telegram_id:
        survey_text = (
            "Your complaint has been marked as resolved. "
            "Are you satisfied?\n"
            "Reply:\n"
            "✅ /approve — Satisfied, close it\n"
            "❌ /reject — Not satisfied, reopen it\n"
            "(If you don't respond within 72 h, it will be auto-closed.)"
        )
        await telegram_send(str(telegram_id), survey_text)

    # Start 72-h auto-close timer (cancel any existing timer)
    if complaint_id in _survey_timers:
        _survey_timers[complaint_id].cancel()
    _survey_timers[complaint_id] = asyncio.create_task(_auto_close_unverified(complaint_id))


async def handle_citizen_survey_reply(telegram_id: str, text: str) -> None:
    """
    Called by services.py Telegram handle_message when a citizen replies
    to the survey. Maps /approve → CLOSED, /reject → REOPENED.
    """
    sb = await get_supabase()

    # Find the complaint in FINAL_SURVEY_PENDING belonging to this Telegram user
    complaint = await sb.table("complaints") \
        .select("id, status") \
        .eq("citizen_telegram_chat_id", telegram_id) \
        .eq("status", "FINAL_SURVEY_PENDING") \
        .order("created_at", desc=True) \
        .limit(1) \
        .maybe_single() \
        .execute()

    if not complaint.data:
        return

    complaint_id = complaint.data["id"]
    lowered = text.strip().lower()

    if lowered in ("/approve", "approve", "yes", "✅"):
        new_status   = "CLOSED"
        survey_value = "approved"
    elif lowered in ("/reject", "reject", "no", "❌"):
        new_status   = "REOPENED"
        survey_value = "rejected"
    else:
        return  # Not a survey reply

    # Cancel auto-close timer
    if complaint_id in _survey_timers:
        _survey_timers[complaint_id].cancel()
        del _survey_timers[complaint_id]

    await sb.table("complaints") \
        .update({"status": new_status, "survey_response": survey_value}) \
        .eq("id", complaint_id) \
        .execute()

    await log_event(
        complaint_id,
        event_type="survey_response",
        actor_type="citizen",
        actor_id=telegram_id,
        from_status="FINAL_SURVEY_PENDING",
        to_status=new_status,
        payload={"survey": survey_value},
    )

    reply = "Thank you! Complaint closed. 🎉" if new_status == "CLOSED" \
        else "We're sorry to hear that. Your complaint has been reopened."
    await telegram_send(telegram_id, reply)


# ══════════════════════════════════════════════════════════════════════
# CONTRACTOR AGENT — Work-order proof verification
# ══════════════════════════════════════════════════════════════════════

_contractor_timers: dict[str, asyncio.Task] = {}


async def _check_proof_timeout(complaint_id: str) -> None:
    """24 h after contractor assignment — if no proof, escalate."""
    await asyncio.sleep(24 * 3600)
    sb = await get_supabase()

    dept_row = await sb.table("complaint_departments") \
        .select("proof_url, contractor_id") \
        .eq("complaint_id", complaint_id) \
        .is_("proof_url", "null") \
        .limit(1) \
        .maybe_single() \
        .execute()

    if not dept_row.data:
        return  # Proof was submitted

    contractor_id = dept_row.data.get("contractor_id")
    if contractor_id:
        await notify(
            contractor_id,
            "proof_overdue",
            {"complaint_id": complaint_id, "hours_overdue": 24},
        )

    # Also escalate to AA
    complaint = await sb.table("complaints") \
        .select("ward_id") \
        .eq("id", complaint_id) \
        .maybe_single() \
        .execute()
    if complaint.data:
        ward_id = complaint.data.get("ward_id")
        aa_result = await sb.table("officers") \
            .select("id") \
            .eq("role", "aa") \
            .contains("ward_ids", [ward_id]) \
            .limit(1) \
            .execute()
        if aa_result.data:
            await notify(
                aa_result.data[0]["id"],
                "contractor_proof_overdue",
                {"complaint_id": complaint_id, "contractor_id": contractor_id},
            )

    await log_event(
        complaint_id,
        event_type="escalation",
        actor_type="agent",
        actor_id="contractor_agent",
        payload={"reason": "proof_not_submitted_24h", "contractor_id": contractor_id},
    )


async def on_work_order_assigned(complaint_id: str) -> None:
    """
    Called from routers_admin POST /work-orders when a contractor is assigned.
    Starts 24-h proof-submission timer.
    """
    if complaint_id in _contractor_timers:
        _contractor_timers[complaint_id].cancel()
    _contractor_timers[complaint_id] = asyncio.create_task(
        _check_proof_timeout(complaint_id)
    )


async def check_proof_submitted(complaint_id: str) -> bool:
    """Returns True if every complaint_departments row with a contractor has a proof_url."""
    sb = await get_supabase()
    missing = await sb.table("complaint_departments") \
        .select("id", count="exact") \
        .eq("complaint_id", complaint_id) \
        .not_.is_("contractor_id", "null") \
        .is_("proof_url", "null") \
        .execute()
    return (missing.count or 0) == 0


# ══════════════════════════════════════════════════════════════════════
# PREDICTIVE AGENT — DBSCAN hotspot detection (runs nightly)
# ══════════════════════════════════════════════════════════════════════

# ~200 m in decimal degrees at Delhi's latitude
_DBSCAN_EPS       = 0.0018
_DBSCAN_MIN       = 5


async def run_predictive_agent() -> dict:
    """
    DBSCAN hotspot detection over the last 30 days.
    For each category:
      1. Pull all complaint coordinates + urgency from DB for last 90 days.
      2. Run DBSCAN(eps=0.0018, min_samples=5).
      3. For clusters with ≥ 5 members, compute centroid + severity.
      4. Upsert into hotspots table.

    Returns a summary dict for the /internal/run-predictive-agent response.
    """
    sb = await get_supabase()

    # Fetch complaint coordinates via RPC defined in 007_analytics_functions.sql
    result = await sb.rpc("get_complaints_with_coords_last_90_days", {}).execute()
    rows = result.data or []

    if not rows:
        return {"hotspots_upserted": 0, "categories_scanned": 0}

    categories = list({r["category"] for r in rows if r.get("category")})
    total_upserted = 0

    for category in categories:
        cat_rows = [r for r in rows if r["category"] == category and r.get("lat") and r.get("lng")]
        if len(cat_rows) < _DBSCAN_MIN:
            continue

        coords = np.array([[r["lat"], r["lng"]] for r in cat_rows])
        urgencies = np.array([r.get("urgency", 3) for r in cat_rows])

        db = DBSCAN(eps=_DBSCAN_EPS, min_samples=_DBSCAN_MIN).fit(coords)
        labels = db.labels_

        cluster_ids = set(labels) - {-1}  # -1 = noise
        for cluster_id in cluster_ids:
            mask     = labels == cluster_id
            members  = coords[mask]
            avg_urg  = float(urgencies[mask].mean())
            density  = int(mask.sum())

            if density < _DBSCAN_MIN:
                continue

            centroid_lat = float(members[:, 0].mean())
            centroid_lng = float(members[:, 1].mean())

            # severity 1–5: scaled by density and avg_urgency
            severity = min(5, round((density / _DBSCAN_MIN) * avg_urg))
            severity = max(1, severity)

            # Upsert hotspot (insert or update by location+category uniqueness)
            await sb.table("hotspots").upsert(
                {
                    "lat":         centroid_lat,
                    "lng":         centroid_lng,
                    "category":    category,
                    "severity":    severity,
                    "density":     density,
                    "is_resolved": False,
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                },
                on_conflict="lat,lng,category",
            ).execute()

            total_upserted += 1

    return {
        "hotspots_upserted":  total_upserted,
        "categories_scanned": len(categories),
        "complaints_analysed": len(rows),
        "run_at": datetime.now(timezone.utc).isoformat(),
    }
