"""
app/routers_analytics.py — Analytics endpoints for the Super Admin dashboard.

Hotspots, SLA compliance, complaint volume, ward density.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from app.database import get_current_user, get_supabase, require_role
from app.models import (
    ComplaintVolumePoint,
    CurrentUser,
    HotspotResponse,
    SLAComplianceResponse,
)

router = APIRouter(tags=["analytics"])


def _map_hotspot(row: dict) -> HotspotResponse:
    """Maps a DB hotspot row to HotspotResponse — extracts lat/lng from geometry."""
    return HotspotResponse(
        id=row["id"],
        lat=row.get("lat", 0.0),
        lng=row.get("lng", 0.0),
        radius_m=row.get("radius_meters", 200),
        category=row["category"],
        complaint_count=row["complaint_count"],
        severity=row["severity"],
        ward_name=row.get("ward_name") or row.get("wards", {}).get("name", "Unknown"),
        detected_at=row["detected_at"],
    )


# ── GET /analytics/hotspots ───────────────────────────────────────────

@router.get("/analytics/hotspots", response_model=List[HotspotResponse])
async def get_hotspots(
    current_user: CurrentUser = Depends(require_role("super_admin")),
    sb=Depends(get_supabase),
):
    """
    Active hotspot list — Super Admin only.
    Reads from hotspots table (written nightly by Predictive Agent).
    Returns only unresolved hotspots via the get_hotspots_with_coords RPC
    which extracts lat/lng from the PostGIS center column.
    """
    result = await sb.rpc("get_hotspots_with_coords", {"p_is_resolved": False}).execute()
    return [_map_hotspot(h) for h in (result.data or [])]


# ── GET /analytics/sla-compliance ────────────────────────────────────

@router.get("/analytics/sla-compliance", response_model=List[SLAComplianceResponse])
async def get_sla_compliance(
    date_from: Optional[str] = Query(default=None, description="ISO date string, e.g. 2025-01-01"),
    date_to: Optional[str] = Query(default=None, description="ISO date string, e.g. 2025-12-31"),
    current_user: CurrentUser = Depends(get_current_user),
    sb=Depends(get_supabase),
):
    """
    SLA compliance per department. JWT required.
    Calls the compute_sla_compliance Supabase RPC for grouped SQL computation.
    """
    result = await sb.rpc("compute_sla_compliance", {
        "from_date": date_from,
        "to_date":   date_to,
    }).execute()
    return result.data or []


# ── GET /analytics/complaint-volume ──────────────────────────────────

@router.get("/analytics/complaint-volume", response_model=List[ComplaintVolumePoint])
async def get_complaint_volume(
    group_by: str = Query(default="day", description="Grouping: day | week | month"),
    category: Optional[str] = Query(default=None),
    ward_id: Optional[str] = Query(default=None),
    current_user: CurrentUser = Depends(get_current_user),
    sb=Depends(get_supabase),
):
    """
    Complaint volume time series with flexible grouping.
    Calls the complaint_volume_series Supabase RPC.
    """
    if group_by not in ("day", "week", "month"):
        group_by = "day"

    result = await sb.rpc("complaint_volume_series", {
        "group_by":         group_by,
        "filter_category":  category,
        "filter_ward_id":   ward_id,
    }).execute()
    return result.data or []


# ── GET /analytics/ward-density — Public heatmap ─────────────────────

@router.get("/analytics/ward-density")
async def get_ward_density(
    category: Optional[str] = Query(default=None),
    sb=Depends(get_supabase),
):
    """
    Public endpoint — used by /map page.
    Returns ward_id + complaint count only.
    Privacy: no individual complaint coordinates exposed.
    """
    result = await sb.rpc("ward_complaint_density", {
        "filter_category": category,
    }).execute()
    return result.data or []
