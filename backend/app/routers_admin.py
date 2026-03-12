"""
app/routers_admin.py — Officer, contractor, ward, asset, and work-order endpoints.

Used by the admin dashboards and the GeoSpatial Agent.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.database import find_nearest_assets, get_current_user, get_supabase, require_role
from app.models import (
    ContractorScorecard,
    ContractorStatusUpdateRequest,
    CurrentUser,
    OfficerStats,
    UserRole,
)
from app.services import send_email, notify
from app.utils import log_event

router = APIRouter(tags=["admin"])


# ── GET /officers/{id}/stats — Officer performance ────────────────────

@router.get("/officers/{officer_id}/stats", response_model=OfficerStats)
async def get_officer_stats(
    officer_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    sb=Depends(get_supabase),
):
    """All metrics computed from complaint_events — no denormalized counters."""
    # Verify officer exists
    officer_row = await sb.table("officers").select("id, name, role").eq("id", officer_id).maybe_single().execute()
    if not officer_row or not officer_row.data:
        raise HTTPException(status_code=404, detail="Officer not found")

    events = await sb.table("complaint_events") \
        .select("*") \
        .eq("actor_id", officer_id) \
        .execute()

    evt_list = events.data or []

    total_assigned  = sum(1 for e in evt_list if e["event_type"] == "status_change" and e.get("to_status") == "ASSIGNED")
    total_resolved  = sum(1 for e in evt_list if e["event_type"] == "status_change" and e.get("to_status") == "CLOSED")
    total_escalated = sum(1 for e in evt_list if e["event_type"] == "status_change" and e.get("to_status") == "ESCALATED")
    total_reopened  = sum(1 for e in evt_list if e["event_type"] == "status_change" and e.get("to_status") == "REOPENED")

    # Compute avg resolution time from ASSIGNED → CLOSED pairs per complaint
    assigned_times: dict[str, datetime] = {}
    resolution_durations: list[float] = []

    for e in sorted(evt_list, key=lambda x: x["created_at"]):
        cid = e.get("complaint_id")
        if not cid:
            continue
        if e.get("to_status") == "ASSIGNED":
            try:
                assigned_times[cid] = datetime.fromisoformat(e["created_at"].replace("Z", "+00:00"))
            except Exception:
                pass
        elif e.get("to_status") == "CLOSED" and cid in assigned_times:
            try:
                closed_at = datetime.fromisoformat(e["created_at"].replace("Z", "+00:00"))
                hours = (closed_at - assigned_times[cid]).total_seconds() / 3600
                resolution_durations.append(hours)
                del assigned_times[cid]
            except Exception:
                pass

    avg_resolution_hours = (
        sum(resolution_durations) / len(resolution_durations) if resolution_durations else 0.0
    )
    reopen_rate_pct = (
        round((total_reopened / total_resolved) * 100, 1) if total_resolved > 0 else 0.0
    )

    return OfficerStats(
        officer_id=officer_row.data["id"],
        name=officer_row.data["name"],
        role=UserRole(officer_row.data["role"]),
        total_assigned=total_assigned,
        total_resolved=total_resolved,
        total_escalated=total_escalated,
        avg_resolution_hours=round(avg_resolution_hours, 1),
        reopen_rate_pct=reopen_rate_pct,
    )


# ── GET /contractors/{id}/scorecard — Contractor scorecard ────────────

@router.get("/contractors/{contractor_id}/scorecard", response_model=ContractorScorecard)
async def get_contractor_scorecard(
    contractor_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    sb=Depends(get_supabase),
):
    """
    Reliability score formula:
    reliability = (on_time_rate * 0.4) + ((1 - rejection_rate) * 0.35) + ((1 - reopen_rate) * 0.25)
    reliability_score = round(reliability * 100)
    """
    contractor_row = await sb.table("contractors") \
        .select("id, name, active") \
        .eq("id", contractor_id) \
        .maybe_single() \
        .execute()

    if not contractor_row or not contractor_row.data:
        raise HTTPException(status_code=404, detail="Contractor not found")

    # Pull work orders for this contractor from complaint_departments
    wo_result = await sb.table("complaint_departments") \
        .select("*, complaints(status, sla_deadline, created_at)") \
        .eq("contractor_id", contractor_id) \
        .execute()

    work_orders = wo_result.data or []
    tasks_assigned = len(work_orders)

    if tasks_assigned == 0:
        return ContractorScorecard(
            contractor_id=contractor_row.data["id"],
            name=contractor_row.data["name"],
            tasks_assigned=0,
            on_time_pct=0.0,
            rejection_rate_pct=0.0,
            reopen_rate_pct=0.0,
            reliability_score=0,
            is_active=contractor_row.data.get("active", True),
        )

    completed = [w for w in work_orders if w.get("sub_status") in ("CLOSED", "COMPLETED")]
    total_completed = len(completed)

    on_time = 0
    for w in completed:
        complaint = w.get("complaints", {})
        if complaint.get("sla_deadline") and complaint.get("updated_at"):
            try:
                sla = datetime.fromisoformat(complaint["sla_deadline"].replace("Z", "+00:00"))
                updated = datetime.fromisoformat(complaint["updated_at"].replace("Z", "+00:00"))
                if updated <= sla:
                    on_time += 1
            except Exception:
                pass

    on_time_rate = (on_time / total_completed) if total_completed > 0 else 0.0

    # rejection_rate = citizen-rejected surveys / total completed tasks
    rejected_count = sum(
        1 for w in work_orders
        if w.get("sub_status") == "REOPENED"
    )
    rejection_rate = (rejected_count / tasks_assigned)

    # reopen_rate = reopened complaints / total closed
    reopen_rate = (rejected_count / total_completed) if total_completed > 0 else 0.0

    reliability = (on_time_rate * 0.4) + ((1 - rejection_rate) * 0.35) + ((1 - reopen_rate) * 0.25)
    reliability_score = round(reliability * 100)

    active_work_orders = [
        {
            "id":         w["id"],
            "complaint_id": w["complaint_id"],
            "sub_status": w["sub_status"],
        }
        for w in work_orders
        if w.get("sub_status") not in ("CLOSED", "COMPLETED", "CANCELLED")
    ]

    return ContractorScorecard(
        contractor_id=contractor_row.data["id"],
        name=contractor_row.data["name"],
        tasks_assigned=tasks_assigned,
        on_time_pct=round(on_time_rate * 100, 1),
        rejection_rate_pct=round(rejection_rate * 100, 1),
        reopen_rate_pct=round(reopen_rate * 100, 1),
        reliability_score=reliability_score,
        is_active=contractor_row.data.get("active", True),
        active_work_orders=active_work_orders,
    )


# ── PATCH /contractors/{id}/status — Activate/deactivate ──────────────

@router.patch("/contractors/{contractor_id}/status")
async def update_contractor_status(
    contractor_id: str,
    body: ContractorStatusUpdateRequest,
    current_user: CurrentUser = Depends(require_role("super_admin")),
    sb=Depends(get_supabase),
):
    """Activate or deactivate a contractor. Super Admin only. Reason is mandatory."""
    contractor = await sb.table("contractors") \
        .select("contact_email, name") \
        .eq("id", contractor_id) \
        .maybe_single() \
        .execute()

    if not contractor or not contractor.data:
        raise HTTPException(status_code=404, detail="Contractor not found")

    await sb.table("contractors") \
        .update({
            "active":               body.is_active,
            "deactivation_reason":  None if body.is_active else body.reason,
        }) \
        .eq("id", contractor_id) \
        .execute()

    # Mandatory audit log entry
    await log_event(
        complaint_id=None,
        event_type="contractor_status_changed",
        actor_type="officer",
        actor_id=current_user.id,
        payload={"is_active": body.is_active, "reason": body.reason},
    )

    # Notify contractor via SMTP
    contact_email = contractor.data.get("contact_email")
    if contact_email:
        if not body.is_active:
            await send_email(
                to=contact_email,
                subject="Your PS-CRM account has been deactivated",
                body_html=f"<p>Your contractor account has been deactivated. Reason: {body.reason}</p>",
            )
        else:
            await send_email(
                to=contact_email,
                subject="Your PS-CRM account has been reactivated",
                body_html=f"<p>Your contractor account has been reactivated. You can now accept new work orders.</p>",
            )

    return {"ok": True, "contractor_id": contractor_id, "is_active": body.is_active}


# ── GET /assets — Query assets by lat/lng radius ───────────────────────

@router.get("/assets")
async def get_assets(
    lat: float = Query(...),
    lng: float = Query(...),
    radius_m: int = Query(default=50),
    asset_type: Optional[str] = Query(default=None),
    current_user: CurrentUser = Depends(get_current_user),
    sb=Depends(get_supabase),
):
    """Query assets within a radius of a GPS point. Used by GeoSpatial Agent and dashboards."""
    assets = await find_nearest_assets(lat, lng, asset_type, radius_m)
    return assets


# ── GET /wards — All ward GeoJSON ─────────────────────────────────────

@router.get("/wards")
async def get_wards(sb=Depends(get_supabase)):
    """
    Returns GeoJSON FeatureCollection — MapLibre renders this as boundary overlays.
    Aggressively cached: ward boundaries change only when MCD redraws them (rare).
    """
    result = await sb.rpc("get_wards_geojson", {}).execute()
    return Response(
        content=result.data,
        media_type="application/json",
        headers={"Cache-Control": "max-age=86400"},
    )


# ── GET /complaints/{id}/work-orders ──────────────────────────────────

@router.get("/complaints/{complaint_id}/work-orders")
async def get_work_orders(
    complaint_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    sb=Depends(get_supabase),
):
    """Returns all work orders (complaint_departments rows) for a complaint. FAA tender view."""
    result = await sb.table("complaint_departments") \
        .select("*, departments(name), officers(name), contractors(name, contact_email)") \
        .eq("complaint_id", complaint_id) \
        .execute()

    return result.data or []


# ── POST /complaints/{id}/work-orders — Create work order ─────────────

@router.post("/complaints/{complaint_id}/work-orders", status_code=201)
async def create_work_order(
    complaint_id: str,
    contractor_id: str,
    department_id: str,
    scope: Optional[str] = None,
    current_user: CurrentUser = Depends(require_role("faa", "super_admin")),
    sb=Depends(get_supabase),
):
    """Assigns a contractor to a complaint department row. FAA initiates tender."""
    # Verify contractor is active
    contractor = await sb.table("contractors") \
        .select("id, name, contact_email, active") \
        .eq("id", contractor_id) \
        .maybe_single() \
        .execute()

    if not contractor or not contractor.data:
        raise HTTPException(status_code=404, detail="Contractor not found")
    if not contractor.data.get("active", True):
        raise HTTPException(status_code=400, detail="Contractor is not active")

    # Update complaint_departments with contractor assignment
    result = await sb.table("complaint_departments") \
        .update({
            "contractor_id": contractor_id,
            "sub_status":    "ASSIGNED",
        }) \
        .eq("complaint_id", complaint_id) \
        .eq("department_id", department_id) \
        .execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Complaint department row not found")

    work_order_id = result.data[0]["id"]

    await log_event(
        complaint_id,
        event_type="work_order_created",
        actor_type="officer",
        actor_id=current_user.id,
        payload={"contractor_id": contractor_id, "work_order_id": work_order_id, "scope": scope},
    )

    # Notify contractor via SMTP
    from app.services import send_contractor_assignment
    await send_contractor_assignment(
        to=contractor.data["contact_email"],
        work_order_id=work_order_id,
        details={"category": scope or ""},
    )

    return {"ok": True, "work_order_id": work_order_id}
