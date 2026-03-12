"""
app/agents.py — LangGraph Supervisor, Classification, GeoSpatial, and Routing agents.

These are synchronous/event-triggered agents that fire on every new complaint
via the Supabase Realtime INSERT event wired in database.py.
"""
from __future__ import annotations

from typing import Optional, TypedDict

from langgraph.graph import END, StateGraph

from app.database import assign_ward, find_nearest_assets, get_supabase
from app.models import ClassificationResult
from app.services import GeminiFailure, classify_with_gemini, notify
from app.utils import classify_with_rules, log_event


# ── Shared state flowing through the LangGraph graph ─────────────────

class ComplaintAgentState(TypedDict):
    complaint_id:   str
    raw_text:       str
    translated_text: str
    lat:            float
    lng:            float
    classification: Optional[dict]   # category, urgency, departments, asset_types, confidence
    geo_result:     Optional[dict]   # ward_id, asset_ids
    routing_result: Optional[dict]   # assigned: {dept_name: jssa_id}
    error:          Optional[str]    # if any node fails, set here and graph stops


# ── Validation ────────────────────────────────────────────────────────

_VALID_CATEGORIES = {
    "drainage", "streetlight", "road", "tree",
    "garbage", "water_supply", "other",
}

_VALID_DEPARTMENTS = {
    "Public Works Department", "Electricity Department", "Horticulture Department",
    "Sanitation Department", "Delhi Jal Board",
}


def _validate_classification(result: ClassificationResult) -> bool:
    if result.category not in _VALID_CATEGORIES:
        return False
    if not result.departments:
        return False
    if not all(d in _VALID_DEPARTMENTS for d in result.departments):
        return False
    return True


async def _queue_for_human_review(complaint_id: str) -> None:
    sb = await get_supabase()
    await sb.table("complaints").update({
        "needs_human_review": True,
        "status":             "CLASSIFIED",
    }).eq("id", complaint_id).execute()

    await log_event(
        complaint_id,
        event_type="agent_action",
        actor_type="agent",
        actor_id="classification_agent",
        payload={"action": "queued_for_human_review", "reason": "low_confidence_or_invalid_output"},
    )


# ── JSSA round-robin helper ───────────────────────────────────────────

async def _find_available_jssa(ward_id: str, dept_name: str) -> Optional[dict]:
    """
    Find the least-loaded JSSA in a ward for a given department.
    Least-loaded = JSSA with fewest ASSIGNED complaints currently open.
    """
    sb = await get_supabase()

    # Get department id
    dept_result = await sb.table("departments").select("id").eq("name", dept_name).maybe_single().execute()
    if not dept_result.data:
        return None
    dept_id = dept_result.data["id"]

    # Get all JSSAs in this ward + department
    officers = await sb.table("officers") \
        .select("id, name, department_id, ward_ids") \
        .eq("role", "jssa") \
        .eq("active", True) \
        .eq("department_id", dept_id) \
        .execute()

    if not officers.data:
        return None

    # Filter by ward membership
    ward_officers = [
        o for o in officers.data
        if ward_id in (o.get("ward_ids") or [])
    ]

    if not ward_officers:
        # Fallback: any JSSA in the department
        ward_officers = officers.data

    if not ward_officers:
        return None

    # Count active assignments per officer (least-loaded selection)
    loads: list[tuple[int, dict]] = []
    for officer in ward_officers:
        active = await sb.table("complaint_departments") \
            .select("id", count="exact") \
            .eq("officer_id", officer["id"]) \
            .in_("sub_status", ["NEW", "ASSIGNED", "IN_PROGRESS"]) \
            .execute()
        loads.append((active.count or 0, officer))

    loads.sort(key=lambda x: x[0])
    best_officer = loads[0][1]
    best_officer["department_id"] = dept_id
    return best_officer


# ══════════════════════════════════════════════════════════════════════
# NODE 1 — Classification Agent
# ══════════════════════════════════════════════════════════════════════

async def classification_node(state: ComplaintAgentState) -> ComplaintAgentState:
    """
    1. Run keyword rule engine on translated_text.
    2. If confidence < 0.85, escalate to Gemini.
    3. Validate output — if invalid, queue for human review and stop graph.
    4. Write classification results back to complaints table + log event.
    """
    complaint_id = state["complaint_id"]
    sb = await get_supabase()

    # Step 1: Rule engine
    result: ClassificationResult = classify_with_rules(state["translated_text"])

    # Step 2: Gemini fallback
    if result.confidence < 0.85:
        try:
            result = await classify_with_gemini(state["translated_text"])
        except GeminiFailure:
            # Keep rule-engine result — will be queued for human review
            pass

    # Step 3: Validate
    if not _validate_classification(result) or result.confidence < 0.5:
        await _queue_for_human_review(complaint_id)
        return {**state, "error": "low_confidence_queued"}

    # Step 4: Write classification back to complaints row
    await sb.table("complaints").update({
        "category":                  result.category,
        "urgency":                   result.urgency,
        "llm_used":                  result.llm_used,
        "classification_confidence": result.confidence,
        "status":                    "CLASSIFIED",
    }).eq("id", complaint_id).execute()

    await log_event(
        complaint_id,
        event_type="agent_action",
        actor_type="agent",
        actor_id="classification_agent",
        payload={
            "category":    result.category,
            "urgency":     result.urgency,
            "confidence":  result.confidence,
            "llm_used":    result.llm_used,
            "departments": result.departments,
        },
    )

    return {**state, "classification": result.model_dump()}


# ══════════════════════════════════════════════════════════════════════
# NODE 2 — GeoSpatial Agent
# ══════════════════════════════════════════════════════════════════════

async def geospatial_node(state: ComplaintAgentState) -> ComplaintAgentState:
    """
    1. Find nearest asset within 50m using PostGIS (via database.py).
    2. Assign ward from coordinates using ST_Contains.
    3. Update complaint with ward_id + asset_ids.
    """
    complaint_id = state["complaint_id"]
    classification = state["classification"] or {}
    sb = await get_supabase()

    asset_type = (classification.get("asset_types") or [None])[0]

    # PostGIS queries via RPC (defined in migrations/006_functions.sql)
    assets = await find_nearest_assets(state["lat"], state["lng"], asset_type, radius_m=50)
    ward_id = await assign_ward(state["lat"], state["lng"])

    await sb.table("complaints").update({
        "ward_id":   ward_id,
        "asset_ids": [a["id"] for a in assets],
    }).eq("id", complaint_id).execute()

    await log_event(
        complaint_id,
        event_type="agent_action",
        actor_type="agent",
        actor_id="geospatial_agent",
        payload={
            "ward_id":       ward_id,
            "assets_found":  len(assets),
            "asset_unlinked": len(assets) == 0,
        },
    )

    return {
        **state,
        "geo_result": {
            "ward_id":   ward_id,
            "asset_ids": [a["id"] for a in assets],
        },
    }


# ══════════════════════════════════════════════════════════════════════
# NODE 3 — Department Routing Agent
# ══════════════════════════════════════════════════════════════════════

async def routing_node(state: ComplaintAgentState) -> ComplaintAgentState:
    """
    For each department in the classification:
    1. Find the least-loaded available JSSA in the complaint's ward.
    2. Update complaint_departments row with officer_id + sub_status=ASSIGNED.
    3. Notify JSSA via Telegram (or SMTP if no Telegram).
    4. Update parent complaint status to ASSIGNED.
    """
    complaint_id = state["complaint_id"]
    geo_result    = state["geo_result"] or {}
    classification = state["classification"] or {}
    ward_id      = geo_result.get("ward_id")
    departments  = classification.get("departments", [])
    category     = classification.get("category", "other")
    sb           = await get_supabase()

    assigned: dict[str, str] = {}

    for dept_name in departments:
        jssa = await _find_available_jssa(ward_id, dept_name)
        if not jssa:
            continue

        await sb.table("complaint_departments") \
            .update({
                "officer_id": jssa["id"],
                "sub_status": "ASSIGNED",
            }) \
            .eq("complaint_id", complaint_id) \
            .eq("department_id", jssa["department_id"]) \
            .execute()

        assigned[dept_name] = jssa["id"]

        # Notify JSSA — Telegram first, SMTP fallback handled inside notify()
        await notify(
            recipient_id=jssa["id"],
            event_type="new_complaint_assigned",
            payload={"complaint_id": complaint_id, "category": category},
        )

    # Update parent complaint → ASSIGNED
    await sb.table("complaints") \
        .update({"status": "ASSIGNED"}) \
        .eq("id", complaint_id) \
        .execute()

    await log_event(
        complaint_id,
        event_type="status_change",
        actor_type="agent",
        actor_id="routing_agent",
        from_status="CLASSIFIED",
        to_status="ASSIGNED",
        payload={"assignments": assigned},
    )

    return {**state, "routing_result": {"assigned": assigned}}


# ══════════════════════════════════════════════════════════════════════
# SUPERVISOR — LangGraph graph wiring
# ══════════════════════════════════════════════════════════════════════

def build_supervisor_graph():
    graph = StateGraph(ComplaintAgentState)

    graph.add_node("classify",  classification_node)
    graph.add_node("geolocate", geospatial_node)
    graph.add_node("route",     routing_node)

    graph.set_entry_point("classify")

    # Conditional edge: if classification errored (human review queued), stop graph
    graph.add_conditional_edges(
        "classify",
        lambda state: "stop" if state.get("error") else "geolocate",
        {"stop": END, "geolocate": "geolocate"},
    )

    graph.add_edge("geolocate", "route")
    graph.add_edge("route", END)

    return graph.compile()


supervisor_graph = build_supervisor_graph()


async def supervisor_agent_run(complaint_id: str) -> None:
    """
    Entry point called by database.py on Supabase Realtime INSERT event.
    Fetches the full complaint row and initialises the LangGraph state.
    """
    sb = await get_supabase()
    complaint = await sb.table("complaints") \
        .select("*") \
        .eq("id", complaint_id) \
        .maybe_single() \
        .execute()

    if not complaint.data:
        print(f"[Supervisor] Complaint {complaint_id} not found — skipping")
        return

    c = complaint.data

    # Extract lat/lng from PostGIS geometry string "SRID=4326;POINT(lng lat)"
    import re
    lat, lng = 28.6139, 77.2090  # Delhi centre fallback
    if c.get("location"):
        m = re.search(r"POINT\(([0-9.\-]+)\s+([0-9.\-]+)\)", str(c["location"]))
        if m:
            lng, lat = float(m.group(1)), float(m.group(2))

    initial_state = ComplaintAgentState(
        complaint_id=complaint_id,
        raw_text=c.get("raw_text", ""),
        translated_text=c.get("translated_text") or c.get("raw_text", ""),
        lat=lat,
        lng=lng,
        classification=None,
        geo_result=None,
        routing_result=None,
        error=None,
    )

    try:
        await supervisor_graph.ainvoke(initial_state)
    except Exception as e:
        print(f"[Supervisor] Error processing complaint {complaint_id}: {e}")
        await log_event(
            complaint_id,
            event_type="agent_error",
            actor_type="agent",
            actor_id="supervisor",
            payload={"error": str(e)},
        )
