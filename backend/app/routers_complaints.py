"""
app/routers_complaints.py — All complaint-facing endpoints.

Handles: complaint submission, public status lookup, admin list,
status updates, survey responses, and media upload pre-signing.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import JSONResponse

from app.database import get_supabase, get_current_user, require_role, hash_email
from app.models import (
    Channel,
    ComplaintAdminResponse,
    ComplaintCreateRequest,
    ComplaintEventPublic,
    ComplaintPublicResponse,
    ComplaintStatusUpdateRequest,
    CurrentUser,
    SurveyResponse,
    SurveyResponseRequest,
)
from app.services import (
    classify_with_gemini,
    GeminiFailure,
    send_complaint_received,
    translate_to_english,
)
from app.utils import (
    classify_with_rules,
    compute_sla_deadline,
    generate_grievance_id,
    log_event,
    validate_transition,
)

router = APIRouter(tags=["complaints"])


# ── Helpers ───────────────────────────────────────────────────────────

def _build_public_response(row: dict) -> ComplaintPublicResponse:
    events = row.get("complaint_events", [])
    dept_rows = row.get("complaint_departments", [])
    dept_names = [d.get("departments", {}).get("name", "") for d in dept_rows if d.get("departments")]

    timeline = [
        ComplaintEventPublic(
            event_type=e["event_type"],
            actor_type=e["actor_type"],
            from_status=e.get("from_status"),
            to_status=e.get("to_status"),
            created_at=e["created_at"],
        )
        for e in events
    ]

    return ComplaintPublicResponse(
        id=row["id"],
        grievance_id=row["grievance_id"],
        status=row["status"],
        category=row.get("category"),
        department_names=dept_names,
        timeline=timeline,
        sla_deadline=row.get("sla_deadline"),
        created_at=row["created_at"],
    )


def _build_admin_response(row: dict) -> ComplaintAdminResponse:
    base = _build_public_response(row)
    dept_rows = row.get("complaint_departments", [])
    officer_name = None
    for d in dept_rows:
        if d.get("officers"):
            officer_name = d["officers"].get("name")
            break

    internal_notes = [
        e["payload"].get("note", "")
        for e in row.get("complaint_events", [])
        if e.get("payload", {}).get("note")
    ]

    return ComplaintAdminResponse(
        **base.model_dump(),
        ward_id=row.get("ward_id"),
        urgency=row.get("urgency", 2),
        translated_text=row.get("translated_text"),
        assigned_officer_name=officer_name,
        internal_notes=[n for n in internal_notes if n],
        asset_ids=row.get("asset_ids", []),
        classification_confidence=row.get("classification_confidence"),
        llm_used=row.get("llm_used", False),
        lat=row.get("lat"),
        lng=row.get("lng"),
    )


# ── POST /complaints — Submit new complaint ────────────────────────────

@router.post("/complaints", response_model=ComplaintPublicResponse, status_code=201)
async def submit_complaint(
    body: ComplaintCreateRequest,
    sb=Depends(get_supabase),
):
    """
    10-step complaint intake pipeline. No JWT required — email-only for receipt.
    Inserting with status=NEW triggers the Supabase Realtime event →
    Supervisor Agent fires asynchronously.
    """
    # Step 1: Translate if not English
    translated = await translate_to_english(body.raw_text)

    # Step 2: Generate grievance ID (format: MCD-YYYYMMDD-XXXXX)
    grievance_id = generate_grievance_id()

    # Step 3: Rule engine first pass
    classification = classify_with_rules(translated)

    # Step 4: If confidence < 0.85, call Gemini
    if classification.confidence < 0.85:
        try:
            classification = await classify_with_gemini(translated)
        except GeminiFailure:
            pass  # fall back to rule engine result — will be queued for human review later

    # Step 5: Hash email if provided (never store plaintext citizen contact)
    citizen_email_hash = hash_email(body.citizen_email) if body.citizen_email else None

    # Step 6: Compute SLA deadline based on category
    sla_deadline = compute_sla_deadline(classification.category)

    # Step 7: Insert complaint row (status=NEW triggers Realtime → Supervisor Agent)
    complaint_result = await sb.table("complaints").insert({
        "grievance_id":              grievance_id,
        "citizen_email_hash":        citizen_email_hash,
        "raw_text":                  body.raw_text,
        "translated_text":           translated,
        "category":                  classification.category,
        "urgency":                   classification.urgency,
        "status":                    "NEW",
        "channel":                   body.channel.value,
        "location":                  f"SRID=4326;POINT({body.lng} {body.lat})",
        "media_urls":                body.media_urls,
        "sla_deadline":              sla_deadline.isoformat(),
        "llm_used":                  classification.llm_used,
        "classification_confidence": classification.confidence,
        "needs_human_review":        classification.confidence < 0.85,
    }).execute()

    if not complaint_result.data:
        raise HTTPException(status_code=500, detail="Failed to create complaint")

    complaint = complaint_result.data[0]
    complaint_id = complaint["id"]

    # Step 8: Insert complaint_departments rows (one per dept)
    for dept_name in classification.departments:
        dept = await sb.table("departments").select("id").eq("name", dept_name).maybe_single().execute()
        if dept and dept.data:
            await sb.table("complaint_departments").insert({
                "complaint_id":  complaint_id,
                "department_id": dept.data["id"],
                "sub_status":    "NEW",
                "sla_deadline":  sla_deadline.isoformat(),
            }).execute()

    # Step 9: Log creation event
    await log_event(
        complaint_id,
        event_type="complaint_created",
        actor_type="system",
        payload={"channel": body.channel.value},
    )

    # Step 10: Send email receipt if email provided
    if body.citizen_email:
        await send_complaint_received(body.citizen_email, grievance_id)

    # Fetch with relations for response
    full = await sb.table("complaints") \
        .select("*, complaint_departments(*, departments(name)), complaint_events(*)") \
        .eq("id", complaint_id) \
        .maybe_single() \
        .execute()

    if not full or not full.data:
        raise HTTPException(status_code=500, detail="Failed to fetch created complaint")
    return _build_public_response(full.data)


# ── GET /complaints/{id} — Public status lookup ────────────────────────

@router.get("/complaints/{complaint_id}", response_model=ComplaintPublicResponse)
async def get_complaint_public(complaint_id: str, sb=Depends(get_supabase)):
    """Public status lookup. No auth required. Citizens look up by UUID or grievance_id."""
    # Try UUID first, then grievance_id
    try:
        result = await sb.table("complaints") \
            .select("*, complaint_departments(*, departments(name)), complaint_events(event_type, actor_type, from_status, to_status, created_at)") \
            .eq("id", complaint_id) \
            .maybe_single() \
            .execute()
    except Exception:
        result = await sb.table("complaints") \
            .select("*, complaint_departments(*, departments(name)), complaint_events(event_type, actor_type, from_status, to_status, created_at)") \
            .eq("grievance_id", complaint_id.upper()) \
            .maybe_single() \
            .execute()

    if not result or not result.data:
        raise HTTPException(status_code=404, detail="Complaint not found")

    return _build_public_response(result.data)


# ── GET /complaints — Admin list (role-scoped) ─────────────────────────

@router.get("/complaints", response_model=List[ComplaintAdminResponse])
async def list_complaints(
    status: Optional[str] = Query(default=None),
    ward_id: Optional[str] = Query(default=None),
    sla_breached: Optional[bool] = Query(default=None),
    current_user: CurrentUser = Depends(get_current_user),
    sb=Depends(get_supabase),
):
    """Admin complaint list. JWT required. Data is scoped to the caller's role."""
    query = sb.table("complaints").select(
        "*, complaint_departments(*, departments(name), officers(name)), complaint_events(*)"
    )

    # Role-based data scoping — enforced here AND at RLS level in Supabase
    if current_user.role == "jssa":
        if not current_user.ward_id:
            raise HTTPException(status_code=403, detail="JSSA account has no ward assigned")
        query = query.eq("ward_id", current_user.ward_id)
    elif current_user.role == "aa":
        if current_user.zone_ward_ids:
            query = query.in_("ward_id", current_user.zone_ward_ids)
    # super_admin, faa: no filter — sees everything

    if status:
        query = query.eq("status", status)
    if ward_id:
        query = query.eq("ward_id", ward_id)
    if sla_breached:
        query = query.lt("sla_deadline", "now()")

    result = await query \
        .order("urgency", desc=True) \
        .order("created_at", desc=True) \
        .execute()

    return [_build_admin_response(r) for r in (result.data or [])]


# ── PATCH /complaints/{id}/status — Status update ─────────────────────

@router.patch("/complaints/{complaint_id}/status")
async def update_status(
    complaint_id: str,
    body: ComplaintStatusUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    sb=Depends(get_supabase),
):
    """
    Updates complaint status. Validates the state machine transition.
    Proof photo URL is required for IN_PROGRESS and FINAL_SURVEY_PENDING.
    """
    complaint = await sb.table("complaints") \
        .select("status, ward_id") \
        .eq("id", complaint_id) \
        .maybe_single() \
        .execute()

    if not complaint or not complaint.data:
        raise HTTPException(status_code=404, detail="Complaint not found")

    current_status = complaint.data["status"]

    # Enforce ward scoping for JSSA
    if current_user.role == "jssa" and complaint.data.get("ward_id") != current_user.ward_id:
        raise HTTPException(status_code=403, detail="Complaint is not in your ward")

    # State machine check
    if not validate_transition(current_status, body.new_status.value):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transition: {current_status} → {body.new_status.value}",
        )

    # Proof photo required for certain transitions
    proof_required_states = {"IN_PROGRESS", "FINAL_SURVEY_PENDING"}
    if body.new_status.value in proof_required_states and not body.proof_url:
        raise HTTPException(
            status_code=400,
            detail=f"Proof photo URL required for transition to {body.new_status.value}",
        )

    # Update complaint
    await sb.table("complaints") \
        .update({"status": body.new_status.value}) \
        .eq("id", complaint_id) \
        .execute()

    # Append to audit log (this DB write triggers Supabase Realtime → frontend updates)
    await log_event(
        complaint_id,
        event_type="status_change",
        actor_type="officer",
        actor_id=current_user.id,
        from_status=current_status,
        to_status=body.new_status.value,
        payload={
            "note":      body.internal_note,
            "proof_url": body.proof_url,
        },
    )

    return {"ok": True, "complaint_id": complaint_id, "new_status": body.new_status.value}


# ── POST /complaints/{id}/survey-response — Record citizen survey ──────

@router.post("/complaints/{complaint_id}/survey-response")
async def record_survey_response(
    complaint_id: str,
    body: SurveyResponseRequest,
    sb=Depends(get_supabase),
):
    """Records citizen survey result. Called internally by Survey Agent."""
    complaint = await sb.table("complaints") \
        .select("status, grievance_id, ward_id") \
        .eq("id", complaint_id) \
        .maybe_single() \
        .execute()

    if not complaint or not complaint.data:
        raise HTTPException(status_code=404, detail="Complaint not found")

    if complaint.data["status"] != "FINAL_SURVEY_PENDING":
        raise HTTPException(
            status_code=400,
            detail="Complaint is not in FINAL_SURVEY_PENDING state",
        )

    if body.response == SurveyResponse.APPROVED:
        new_status = "CLOSED"
    elif body.response == SurveyResponse.REJECTED:
        new_status = "REOPENED"
    else:
        new_status = "CLOSED_UNVERIFIED"

    await sb.table("complaints") \
        .update({"status": new_status}) \
        .eq("id", complaint_id) \
        .execute()

    await log_event(
        complaint_id,
        event_type="survey_response",
        actor_type="citizen",
        from_status="FINAL_SURVEY_PENDING",
        to_status=new_status,
        payload={"response": body.response.value, "note": body.citizen_note},
    )

    return {"ok": True, "new_status": new_status}


# ── POST /complaints/upload-url — Pre-signed upload URL ───────────────

@router.post("/complaints/upload-url")
async def get_upload_url(
    current_user: CurrentUser = Depends(get_current_user),
    sb=Depends(get_supabase),
):
    """
    Generates a Supabase Storage pre-signed upload URL.
    Officers use this to upload proof photos before updating complaint status.
    """
    import uuid, time
    filename = f"{current_user.id}/{int(time.time())}_{uuid.uuid4().hex[:8]}.jpg"
    result = await sb.storage.from_("complaint-proofs").create_signed_upload_url(filename)
    return {
        "upload_url":  result.get("signedURL"),
        "path":        filename,
        "public_url":  f"{sb.storage_url}/object/public/complaint-proofs/{filename}",
    }
