# PS-CRM — Backend File Split (10 Files)

> **Stack:** FastAPI · Python 3.12 · LangGraph · Supabase · Gemini 2.5 Flash · Bhashini · Telegram Bot API · SMTP Email
> **Notification change:** Phone OTP removed. SMTP Email is the only verification and notification channel for officers, contractors, and system alerts. Citizens use Telegram only.

---

## How the Backend Is Structured

Before diving into the files, here is how the whole backend hangs together. Every section below explains both *what* the file does and *how it communicates* with everything else.

### The Request Flow (High Level)

```
Citizen (Telegram Bot or Web)
        │
        ▼
[FastAPI — main.py]           ← entry point, routes traffic
        │
        ├──► [routers_complaints.py]   ← complaint intake + status changes
        │           │
        │           ▼
        │    [services.py]             ← Bhashini translation + Gemini call
        │           │
        │           ▼
        │    [utils.py]                ← rule engine, state machine, grievance ID
        │           │
        │           ▼
        │    [database.py]             ← write to Supabase
        │
        ├──► [agents.py]               ← LangGraph Supervisor kicks off after INSERT
        │           │
        │           ├── Classification Agent
        │           ├── GeoSpatial Agent
        │           └── Department Routing Agent
        │
        ├──► [agents_followup.py]      ← background agents on SLA + surveys
        │           │
        │           ├── Follow-Up Agent (SLA watch)
        │           ├── Survey Agent (citizen confirmation)
        │           ├── Contractor Agent (proof gate)
        │           └── Predictive Agent (nightly DBSCAN)
        │
        ├──► [routers_admin.py]        ← officers, contractors, wards, assets
        └──► [routers_analytics.py]    ← hotspots, SLA compliance, volume charts
```

### Communication Between Components

- **FastAPI ↔ Supabase:** All data reads/writes go through the Supabase Python client in `database.py`. No raw SQL strings scattered around — PostGIS spatial queries are wrapped in helper functions here.
- **FastAPI ↔ LangGraph Agents:** Agents are not separate microservices. They live in the same Python process as FastAPI. The Supervisor Agent is triggered by a Supabase Realtime subscription event (new complaint INSERT with status=NEW). FastAPI does not call agents directly — the event bus does.
- **Agents ↔ Supabase:** Agents read complaint state from Supabase and write back via the same `database.py` client. Every agent action (assignment, escalation, notification) is appended to `complaint_events` — the immutable audit log.
- **Agents ↔ Services:** Agents call `services.py` to send notifications. Services dispatch to Telegram (citizens) or SMTP Email (officers/contractors/admin) depending on recipient type.
- **Realtime Events:** Supabase Realtime is the event bus. When an agent writes a status change to the DB, Supabase Realtime broadcasts it instantly to the frontend dashboard. No polling, no WebSocket management in FastAPI.
- **Cron Jobs:** The Predictive Agent is called by a Render Cron Job HTTP hit to a protected internal endpoint `POST /internal/run-predictive-agent` at 2 AM nightly.

---

## File 1 — `app/main.py`

**Role:** Application entry point. Boots FastAPI, registers all routers, configures CORS, sets up Supabase Realtime subscription, and mounts the Telegram webhook.

### What it contains

```python
# ── Imports ──────────────────────────────────────────────────────────
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.database import init_supabase_realtime
from app.routers_complaints import router as complaints_router
from app.routers_admin import router as admin_router
from app.routers_analytics import router as analytics_router
from app.services import telegram_app   # python-telegram-bot Application instance

# ── Lifespan (startup / shutdown) ────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # On startup:
    #   1. Initialise Supabase Realtime subscription
    #      → listens to complaints table INSERT events
    #      → triggers Supervisor Agent when status=NEW
    #   2. Set Telegram webhook URL pointing to /telegram/webhook
    await init_supabase_realtime()
    await telegram_app.bot.set_webhook(url=f"{settings.BACKEND_URL}/telegram/webhook")
    yield
    # On shutdown: gracefully stop Realtime subscription

# ── App factory ───────────────────────────────────────────────────────
app = FastAPI(title="PS-CRM API", version="1.0.0", lifespan=lifespan)

# ── CORS ──────────────────────────────────────────────────────────────
# Allow the Vercel frontend + local dev only. No wildcard in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────
app.include_router(complaints_router, prefix="/api/v1")
app.include_router(admin_router,      prefix="/api/v1")
app.include_router(analytics_router,  prefix="/api/v1")

# ── Health check ──────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok"}

# ── Telegram webhook ──────────────────────────────────────────────────
# Telegram POSTs Update objects here. python-telegram-bot processes them.
@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}

# ── Internal cron endpoint (Render Cron Job calls this at 2 AM) ───────
@app.post("/internal/run-predictive-agent")
async def run_predictive(x_internal_key: str = Header(...)):
    # Validates secret header before running
    # Calls agents_followup.run_predictive_agent()
    ...
```

### How it connects to everything else
- Imports and mounts all 3 router files.
- On startup, calls `init_supabase_realtime()` which opens a persistent WebSocket to Supabase. This is the only place Realtime is wired up.
- Telegram webhook is a plain POST endpoint — no separate port or service needed.
- The internal cron endpoint is guarded by a secret header (`X-Internal-Key`) so it cannot be called by anyone except Render's cron scheduler.

---

## File 2 — `app/config.py` + `app/database.py`

**Role:** Configuration loading and Supabase client management. These two are small enough to live together. `config.py` reads `.env`. `database.py` creates the Supabase client and the Realtime subscription.

### `config.py`

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Supabase
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str   # Used server-side only — bypasses RLS when needed by agents
    SUPABASE_ANON_KEY: str           # Used for citizen-facing public reads

    # Gemini
    GEMINI_API_KEY: str

    # Bhashini
    BHASHINI_USER_ID: str
    BHASHINI_API_KEY: str
    BHASHINI_PIPELINE_ID: str

    # Telegram
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_WEBHOOK_SECRET: str

    # SMTP Email
    SMTP_HOST: str
    SMTP_PORT: int = 587
    SMTP_USERNAME: str
    SMTP_PASSWORD: str
    SMTP_FROM_EMAIL: str = "noreply@ps-crm.in"

    # App
    FRONTEND_URL: str
    BACKEND_URL: str
    INTERNAL_CRON_KEY: str   # Secret for /internal/run-predictive-agent

    class Config:
        env_file = ".env"

settings = Settings()
```

### `database.py`

```python
from supabase import create_client, AsyncClient
from app.config import settings

# ── Singleton Supabase client ─────────────────────────────────────────
# Uses SERVICE_ROLE_KEY — agents need to bypass RLS for cross-ward reads.
# Citizen-facing reads that must respect RLS pass the user's JWT explicitly.
_supabase: AsyncClient = None

async def get_supabase() -> AsyncClient:
    global _supabase
    if _supabase is None:
        _supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    return _supabase

# ── Supabase Realtime subscription ───────────────────────────────────
async def init_supabase_realtime():
    sb = await get_supabase()
    channel = sb.channel("complaints-new")
    channel.on(
        "postgres_changes",
        event="INSERT",
        schema="public",
        table="complaints",
        filter="status=eq.NEW",
        callback=on_new_complaint   # → triggers Supervisor Agent
    )
    await channel.subscribe()

async def on_new_complaint(payload: dict):
    from app.agents import supervisor_agent
    complaint_id = payload["new"]["id"]
    await supervisor_agent.run(complaint_id)

# ── PostGIS helper queries ────────────────────────────────────────────
# find_nearest_assets: ST_DWithin radius query — returns list of Asset rows
# assign_ward: ST_Contains check — returns ward_id UUID
# These are called by GeoSpatial Agent (agents.py)

async def find_nearest_assets(lat: float, lng: float, asset_type: str, radius_m: int = 50):
    sb = await get_supabase()
    # Raw PostGIS query via Supabase RPC (defined as a DB function)
    result = await sb.rpc("find_nearest_assets", {
        "input_lat": lat, "input_lng": lng,
        "input_type": asset_type, "radius_m": radius_m
    }).execute()
    return result.data

async def assign_ward(lat: float, lng: float) -> str:
    sb = await get_supabase()
    result = await sb.rpc("assign_ward", {"input_lat": lat, "input_lng": lng}).execute()
    return result.data[0]["id"] if result.data else None
```

### Key design decisions
- **Service role key** is used server-side so agents can read across ward boundaries (e.g., the Predictive Agent reads all complaints city-wide). But for citizen-facing public complaint reads, the anon key is used with Supabase RLS enforced.
- **PostGIS queries** are wrapped as Supabase DB functions (RPC calls), not raw SQL strings in Python. This keeps Python clean and lets the PostGIS logic live in the DB migration file.
- **Realtime callback** is wired here and calls into `agents.py` — the only cross-file call triggered by an event rather than an HTTP request.

---

## File 3 — `app/models.py`

**Role:** All Pydantic schemas for request bodies, response shapes, and internal data structures. One file, fully typed. No logic here — just shapes.

### Structure overview

```python
from pydantic import BaseModel, UUID4, EmailStr
from typing import Optional, List
from datetime import datetime
from enum import Enum

# ── Enums ─────────────────────────────────────────────────────────────
class ComplaintStatus(str, Enum):
    NEW = "NEW"
    CLASSIFIED = "CLASSIFIED"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    MID_SURVEY_PENDING = "MID_SURVEY_PENDING"
    FINAL_SURVEY_PENDING = "FINAL_SURVEY_PENDING"
    ESCALATED = "ESCALATED"
    REOPENED = "REOPENED"
    CLOSED = "CLOSED"
    CLOSED_UNVERIFIED = "CLOSED_UNVERIFIED"

class UserRole(str, Enum):
    JSSA = "jssa"
    AA = "aa"
    FAA = "faa"
    SUPER_ADMIN = "super_admin"
    CONTRACTOR = "contractor"

class Channel(str, Enum):
    TELEGRAM = "telegram"
    WEB = "web"
    CALL = "call"

class SurveyResponse(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    NO_RESPONSE = "no_response"

# ── Complaint schemas ──────────────────────────────────────────────────
class ComplaintCreateRequest(BaseModel):
    # Sent by citizen via web form or Telegram bot handler
    citizen_email: Optional[EmailStr]  # Optional — used for email receipt
    raw_text: str
    lat: float
    lng: float
    media_urls: List[str] = []
    channel: Channel

class ComplaintStatusUpdateRequest(BaseModel):
    # Sent by JSSA to update status
    new_status: ComplaintStatus
    internal_note: Optional[str]
    proof_url: Optional[str]   # Required for IN_PROGRESS and FINAL_SURVEY_PENDING

class ComplaintPublicResponse(BaseModel):
    # Returned to citizens — NO officer phone, NO internal notes, NO lat/lng
    id: UUID4
    grievance_id: str
    status: ComplaintStatus
    category: Optional[str]
    department_names: List[str]
    timeline: List["ComplaintEventPublic"]
    sla_deadline: Optional[datetime]
    created_at: datetime

class ComplaintAdminResponse(ComplaintPublicResponse):
    # Returned to JSSA/AA/Admin — adds officer info, internal notes
    ward_id: UUID4
    urgency: int
    translated_text: str
    assigned_officer_name: Optional[str]
    internal_notes: List[str]
    asset_ids: List[UUID4]
    classification_confidence: Optional[float]
    llm_used: bool

# ── Complaint event (timeline entry) ─────────────────────────────────
class ComplaintEventPublic(BaseModel):
    event_type: str
    actor_type: str
    from_status: Optional[str]
    to_status: Optional[str]
    created_at: datetime
    # payload excluded from public view — internal data only

# ── Survey ────────────────────────────────────────────────────────────
class SurveyResponseRequest(BaseModel):
    response: SurveyResponse
    citizen_note: Optional[str]

# ── Officer schemas ───────────────────────────────────────────────────
class OfficerStats(BaseModel):
    officer_id: UUID4
    name: str
    role: UserRole
    total_assigned: int
    total_resolved: int
    total_escalated: int
    avg_resolution_hours: float
    reopen_rate_pct: float

# ── Contractor schemas ────────────────────────────────────────────────
class ContractorScorecard(BaseModel):
    contractor_id: UUID4
    name: str
    tasks_assigned: int
    on_time_pct: float
    rejection_rate_pct: float
    reopen_rate_pct: float
    reliability_score: int   # 0–100, computed: (on_time*0.4) + ((1-rejection)*0.35) + ((1-reopen)*0.25)
    is_active: bool
    active_work_orders: List[dict]

class ContractorStatusUpdateRequest(BaseModel):
    is_active: bool
    reason: str   # Mandatory — logged to complaint_events audit trail

# ── Analytics schemas ─────────────────────────────────────────────────
class HotspotResponse(BaseModel):
    id: UUID4
    lat: float
    lng: float
    radius_m: int
    category: str
    complaint_count: int
    severity: int   # 1–5
    ward_name: str
    detected_at: datetime

class SLAComplianceResponse(BaseModel):
    department_name: str
    total_complaints: int
    resolved_within_sla: int
    sla_breached: int
    compliance_pct: float

class ComplaintVolumePoint(BaseModel):
    period: str          # e.g. "2025-03-01" for day grouping
    count: int
    category: Optional[str]
    ward_name: Optional[str]

# ── Classification result (internal — not exposed via API) ────────────
class ClassificationResult(BaseModel):
    category: str
    urgency: int           # 1–5
    departments: List[str]
    asset_types: List[str]
    confidence: float      # 0.0–1.0
    llm_used: bool
```

### Why one file
All schemas in one place means you never chase a schema across four `models/` subdirectories. FastAPI's auto-generated OpenAPI docs will show all schemas cleanly.

---

## File 4 — `app/routers_complaints.py`

**Role:** All complaint-facing endpoints. This is the busiest router. It handles: complaint submission, public status lookup, admin complaint list, status updates, survey responses, and media upload pre-signing.

### Endpoints

```
POST   /complaints                        — Submit new complaint (no JWT, email-only for receipt)
GET    /complaints/{id}                   — Public status lookup (no auth)
GET    /complaints                        — Admin list (JWT, role-scoped)
PATCH  /complaints/{id}/status            — Update status (JWT, state machine validated)
POST   /complaints/{id}/survey-response   — Record citizen survey result (internal agent call)
POST   /complaints/upload-url             — Get Supabase Storage pre-signed upload URL
```

### Complaint submission pipeline (the most complex endpoint)

```python
@router.post("/complaints", response_model=ComplaintPublicResponse, status_code=201)
async def submit_complaint(body: ComplaintCreateRequest, sb=Depends(get_supabase)):
    # Step 1: Translate if not English
    translated = await translate_to_english(body.raw_text)

    # Step 2: Generate grievance ID  (format: MCD-YYYYMMDD-XXXXX)
    grievance_id = generate_grievance_id()

    # Step 3: Rule engine first pass
    classification = classify_with_rules(translated)

    # Step 4: If confidence < 0.85, call Gemini
    if classification.confidence < 0.85:
        classification = await classify_with_gemini(translated)

    # Step 5: Hash email if provided (never store plaintext citizen contact)
    # NOTE: We removed phone OTP. Citizens optionally provide email for receipt only.
    # The hash is stored, the raw email is never persisted.
    citizen_email_hash = sha256(body.citizen_email) if body.citizen_email else None

    # Step 6: Compute SLA deadline based on category config
    sla_deadline = compute_sla_deadline(classification.category)

    # Step 7: Insert complaint row (status=NEW triggers Realtime → Supervisor Agent)
    complaint = await sb.table("complaints").insert({
        "grievance_id":              grievance_id,
        "citizen_email_hash":        citizen_email_hash,
        "raw_text":                  body.raw_text,
        "translated_text":           translated,
        "category":                  classification.category,
        "urgency":                   classification.urgency,
        "status":                    "NEW",
        "channel":                   body.channel,
        "location":                  f"SRID=4326;POINT({body.lng} {body.lat})",
        "media_urls":                body.media_urls,
        "sla_deadline":              sla_deadline.isoformat(),
        "llm_used":                  classification.llm_used,
        "classification_confidence": classification.confidence,
    }).execute()

    # Step 8: Insert complaint_departments rows (one per dept)
    for dept_name in classification.departments:
        dept = await sb.table("departments").select("id").eq("name", dept_name).single().execute()
        await sb.table("complaint_departments").insert({
            "complaint_id":  complaint.data[0]["id"],
            "department_id": dept.data["id"],
            "sub_status":    "NEW",
            "sla_deadline":  sla_deadline.isoformat(),
        }).execute()

    # Step 9: Log creation event to complaint_events (append-only)
    await log_event(complaint.data[0]["id"], event_type="complaint_created",
                    actor_type="system", payload={"channel": body.channel})

    # Step 10: If email provided, send receipt via SMTP
    if body.citizen_email:
        await send_complaint_received(body.citizen_email, grievance_id)

    # At this point the INSERT triggers Supabase Realtime → database.py callback
    # → supervisor_agent.run(complaint_id) fires asynchronously
    return build_public_response(complaint.data[0])
```

### Admin complaint list — role scoping

```python
@router.get("/complaints", response_model=List[ComplaintAdminResponse])
async def list_complaints(
    status: Optional[str] = None,
    ward_id: Optional[str] = None,
    sla_breached: Optional[bool] = None,
    current_user=Depends(get_current_user),  # extracts role from JWT
    sb=Depends(get_supabase)
):
    query = sb.table("complaints").select("*, complaint_departments(*)")

    # Role-based data scoping — enforced here AND at RLS level in Supabase
    if current_user.role == "jssa":
        query = query.eq("ward_id", current_user.ward_id)
    elif current_user.role == "aa":
        query = query.in_("ward_id", current_user.zone_ward_ids)
    # super_admin: no filter — sees everything

    if status:        query = query.eq("status", status)
    if sla_breached:  query = query.lt("sla_deadline", "now()")

    result = await query.order("urgency", desc=True).order("created_at", desc=True).execute()
    return [build_admin_response(r) for r in result.data]
```

### Status update — state machine gating

```python
@router.patch("/complaints/{complaint_id}/status")
async def update_status(
    complaint_id: str,
    body: ComplaintStatusUpdateRequest,
    current_user=Depends(get_current_user),
    sb=Depends(get_supabase)
):
    complaint = await sb.table("complaints").select("status").eq("id", complaint_id).single().execute()
    current_status = complaint.data["status"]

    # State machine check — returns 400 if transition is invalid
    if not validate_transition(current_status, body.new_status):
        raise HTTPException(400, f"Invalid transition: {current_status} → {body.new_status}")

    # Proof photo required for certain transitions
    proof_required = body.new_status in ["IN_PROGRESS", "FINAL_SURVEY_PENDING"]
    if proof_required and not body.proof_url:
        raise HTTPException(400, f"Proof photo required for transition to {body.new_status}")

    # Update complaint
    await sb.table("complaints").update({"status": body.new_status}).eq("id", complaint_id).execute()

    # Append to audit log
    await log_event(complaint_id, event_type="status_change",
                    actor_type="officer", actor_id=current_user.id,
                    from_status=current_status, to_status=body.new_status,
                    payload={"note": body.internal_note, "proof_url": body.proof_url})

    # This DB write triggers Supabase Realtime → frontend dashboards update instantly
```

---

## File 5 — `app/routers_admin.py`

**Role:** All officer, contractor, ward, and asset endpoints. Used by the admin dashboards and the GeoSpatial Agent.

### Endpoints

```
GET    /officers/{id}/stats              — Officer performance (computed from complaint_events)
GET    /contractors/{id}/scorecard       — Contractor scorecard with reliability score
PATCH  /contractors/{id}/status          — Activate/deactivate contractor (Super Admin only)
GET    /assets                           — Query assets by lat/lng radius (GeoSpatial Agent calls this)
GET    /wards                            — All ward GeoJSON (cached, for map rendering)
GET    /complaints/{id}/work-orders      — Work orders for a complaint (FAA tender view)
POST   /complaints/{id}/work-orders      — Create work order + assign contractor (FAA)
```

### Officer stats — computed on read

```python
@router.get("/officers/{officer_id}/stats", response_model=OfficerStats)
async def get_officer_stats(officer_id: str, sb=Depends(get_supabase)):
    # All metrics computed from complaint_events — no denormalized counters
    # This keeps the numbers always accurate, even if old events are re-examined

    events = await sb.table("complaint_events")\
        .select("*")\
        .eq("actor_id", officer_id)\
        .execute()

    # Count assignments, resolutions, escalations from event_type field
    # Compute avg resolution time from timestamps of ASSIGNED → CLOSED pairs
    # Compute reopen rate from REOPENED events
    ...
```

### Contractor scorecard — reliability formula

```python
@router.get("/contractors/{contractor_id}/scorecard", response_model=ContractorScorecard)
async def get_contractor_scorecard(contractor_id: str, sb=Depends(get_supabase)):
    # Pull all work orders for this contractor from complaint_departments table
    # where contractor_id matches

    # on_time_rate   = completed before sla_deadline / total_completed
    # rejection_rate = citizen-rejected surveys / total completed tasks
    # reopen_rate    = reopened complaints / total closed complaints

    reliability = (on_time_rate * 0.4) + ((1 - rejection_rate) * 0.35) + ((1 - reopen_rate) * 0.25)
    reliability_score = round(reliability * 100)
    ...
```

### Contractor deactivation — audit trail required

```python
@router.patch("/contractors/{contractor_id}/status")
async def update_contractor_status(
    contractor_id: str,
    body: ContractorStatusUpdateRequest,
    current_user=Depends(require_role("super_admin")),
    sb=Depends(get_supabase)
):
    await sb.table("contractors").update({"is_active": body.is_active}).eq("id", contractor_id).execute()

    # Mandatory audit log entry — reason field required in request body
    await log_event(
        complaint_id=None,  # Not complaint-specific — use contractor_events table or system event
        event_type="contractor_status_changed",
        actor_type="officer",
        actor_id=current_user.id,
        payload={"is_active": body.is_active, "reason": body.reason}
    )

    # Notify contractor via SMTP
    contractor = await sb.table("contractors").select("contact_email, name").eq("id", contractor_id).single().execute()
    if not body.is_active:
        await send_email(
            to=contractor.data["contact_email"],
            subject="Your PS-CRM account has been deactivated",
            body_html=f"<p>Your contractor account has been deactivated. Reason: {body.reason}</p>"
        )
```

### Ward GeoJSON endpoint

```python
@router.get("/wards")
async def get_wards(sb=Depends(get_supabase)):
    # Returns GeoJSON FeatureCollection — MapLibre renders this as boundary overlays
    # Aggressively cached: ward boundaries only change when MCD redraws them (rare)
    # Cache-Control: max-age=86400 (24 hours)
    result = await sb.rpc("get_wards_geojson").execute()
    return Response(content=result.data, media_type="application/json",
                    headers={"Cache-Control": "max-age=86400"})
```

---

## File 6 — `app/routers_analytics.py`

**Role:** Analytics endpoints consumed by the Super Admin dashboard. Hotspots, SLA compliance, complaint volume.

### Endpoints

```
GET /analytics/hotspots           — Active hotspot list (Super Admin only)
GET /analytics/sla-compliance     — SLA compliance per department (JWT, role-gated)
GET /analytics/complaint-volume   — Volume time series, grouped by day/week/month
GET /analytics/ward-density       — Complaint count per ward (public map heatmap)
```

### Hotspot endpoint

```python
@router.get("/analytics/hotspots", response_model=List[HotspotResponse])
async def get_hotspots(current_user=Depends(require_role("super_admin")), sb=Depends(get_supabase)):
    # Reads from `hotspots` table — written nightly by Predictive Agent
    # Only returns hotspots where is_resolved=false
    result = await sb.table("hotspots")\
        .select("*, wards(name)")\
        .eq("is_resolved", False)\
        .order("severity", desc=True)\
        .execute()
    return [map_hotspot(h) for h in result.data]
```

### SLA compliance — computed from complaint_events

```python
@router.get("/analytics/sla-compliance", response_model=List[SLAComplianceResponse])
async def get_sla_compliance(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    current_user=Depends(get_current_user),
    sb=Depends(get_supabase)
):
    # Calls a Supabase RPC function that does the grouped SQL computation
    # Returns: per department → total, within_sla, breached, compliance_%
    result = await sb.rpc("compute_sla_compliance", {
        "from_date": date_from, "to_date": date_to
    }).execute()
    return result.data
```

### Complaint volume — flexible grouping

```python
@router.get("/analytics/complaint-volume", response_model=List[ComplaintVolumePoint])
async def get_complaint_volume(
    group_by: str = "day",      # day | week | month
    category: Optional[str] = None,
    ward_id: Optional[str] = None,
    current_user=Depends(get_current_user),
    sb=Depends(get_supabase)
):
    # Calls Supabase RPC: date_trunc grouping + optional filters
    result = await sb.rpc("complaint_volume_series", {
        "group_by": group_by,
        "filter_category": category,
        "filter_ward_id": ward_id
    }).execute()
    return result.data
```

### Ward density — public (no auth required)

```python
@router.get("/analytics/ward-density")
async def get_ward_density(category: Optional[str] = None, sb=Depends(get_supabase)):
    # Public endpoint — used by /map page
    # Returns ward_id + complaint count only — NO individual complaint coordinates
    # Privacy: citizens cannot see their own complaint's location from this endpoint
    result = await sb.rpc("ward_complaint_density", {"filter_category": category}).execute()
    return result.data
```

---

## File 7 — `app/agents.py`

**Role:** The synchronous (event-triggered) LangGraph agents: Supervisor, Classification, GeoSpatial, and Department Routing. These fire on every new complaint.

### How LangGraph works here

LangGraph lets you define a graph of nodes (functions) connected by edges (transition logic). State is passed between nodes as a typed dict. The Supervisor Agent is the graph entry point — it calls the other agents as nodes in sequence.

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional, List
import uuid

# ── Shared state shape flowing through the graph ──────────────────────
class ComplaintAgentState(TypedDict):
    complaint_id: str
    raw_text: str
    translated_text: str
    lat: float
    lng: float
    classification: Optional[dict]   # category, urgency, departments, asset_types, confidence
    geo_result: Optional[dict]       # ward_id, asset_ids, nearest_asset
    routing_result: Optional[dict]   # assigned_jssa_ids per department
    error: Optional[str]             # if any node fails, set here

# ── Classification Agent node ─────────────────────────────────────────
async def classification_node(state: ComplaintAgentState) -> ComplaintAgentState:
    # 1. Run rule engine on translated_text
    result = classify_with_rules(state["translated_text"])

    # 2. If confidence < 0.85, escalate to Gemini
    if result.confidence < 0.85:
        result = await classify_with_gemini(state["translated_text"])

    # 3. Validate Gemini output — if invalid, queue for human review
    if not validate_classification(result):
        await queue_for_human_review(state["complaint_id"])
        # Mark complaint status = HUMAN_REVIEW_PENDING
        # Don't continue graph — agent stops here for this complaint
        return {**state, "error": "low_confidence_queued"}

    # 4. Write classification back to complaint row
    await sb.table("complaints").update({
        "category":                  result.category,
        "urgency":                   result.urgency,
        "llm_used":                  result.llm_used,
        "classification_confidence": result.confidence,
        "status":                    "CLASSIFIED"
    }).eq("id", state["complaint_id"]).execute()

    await log_event(state["complaint_id"], "agent_action", "agent", "classification_agent",
                    payload={"category": result.category, "urgency": result.urgency})

    return {**state, "classification": result.dict()}

# ── GeoSpatial Agent node ─────────────────────────────────────────────
async def geospatial_node(state: ComplaintAgentState) -> ComplaintAgentState:
    # 1. Find nearest asset within 50m (PostGIS via database.py)
    asset_type = state["classification"]["asset_types"][0] if state["classification"]["asset_types"] else None
    assets = await find_nearest_assets(state["lat"], state["lng"], asset_type)

    # 2. Assign ward from coordinates
    ward_id = await assign_ward(state["lat"], state["lng"])

    # 3. Update complaint with ward + asset data
    await sb.table("complaints").update({
        "ward_id":   ward_id,
        "asset_ids": [a["id"] for a in assets]
    }).eq("id", state["complaint_id"]).execute()

    await log_event(state["complaint_id"], "agent_action", "agent", "geospatial_agent",
                    payload={"ward_id": ward_id, "assets_found": len(assets),
                             "asset_unlinked": len(assets) == 0})

    return {**state, "geo_result": {"ward_id": ward_id, "asset_ids": [a["id"] for a in assets]}}

# ── Department Routing Agent node ─────────────────────────────────────
async def routing_node(state: ComplaintAgentState) -> ComplaintAgentState:
    ward_id = state["geo_result"]["ward_id"]
    departments = state["classification"]["departments"]
    assigned = {}

    for dept_name in departments:
        # Find available JSSAs for this ward + department
        # Round-robin / least-loaded selection
        jssa = await find_available_jssa(ward_id, dept_name)

        # Update complaint_departments row
        await sb.table("complaint_departments")\
            .update({"officer_id": jssa["id"], "sub_status": "ASSIGNED"})\
            .eq("complaint_id", state["complaint_id"])\
            .eq("department_id", jssa["department_id"])\
            .execute()

        assigned[dept_name] = jssa["id"]

        # Notify JSSA via Telegram
        await notify(
            recipient_id=jssa["id"],
            event_type="new_complaint_assigned",
            payload={"complaint_id": state["complaint_id"], "category": state["classification"]["category"]}
        )

    # Update parent complaint to ASSIGNED
    await sb.table("complaints").update({"status": "ASSIGNED"}).eq("id", state["complaint_id"]).execute()

    await log_event(state["complaint_id"], "status_change", "agent", "routing_agent",
                    from_status="CLASSIFIED", to_status="ASSIGNED",
                    payload={"assignments": assigned})

    return {**state, "routing_result": {"assigned": assigned}}

# ── Supervisor Agent — LangGraph graph wiring ─────────────────────────
def build_supervisor_graph():
    graph = StateGraph(ComplaintAgentState)

    graph.add_node("classify",  classification_node)
    graph.add_node("geolocate", geospatial_node)
    graph.add_node("route",     routing_node)

    graph.set_entry_point("classify")

    # Conditional edge: if classification errored (human review), stop
    graph.add_conditional_edges(
        "classify",
        lambda state: "stop" if state.get("error") else "geolocate",
        {"stop": END, "geolocate": "geolocate"}
    )
    graph.add_edge("geolocate", "route")
    graph.add_edge("route", END)

    return graph.compile()

supervisor_graph = build_supervisor_graph()

async def supervisor_agent_run(complaint_id: str):
    # Called by database.py on Realtime INSERT event
    complaint = await sb.table("complaints").select("*").eq("id", complaint_id).single().execute()
    c = complaint.data
    initial_state = ComplaintAgentState(
        complaint_id=complaint_id,
        raw_text=c["raw_text"],
        translated_text=c["translated_text"],
        lat=c["lat"], lng=c["lng"],
        classification=None, geo_result=None, routing_result=None, error=None
    )
    await supervisor_graph.ainvoke(initial_state)
```

### Error handling
If Gemini call fails (API timeout, invalid key), `classify_with_gemini` catches the exception and returns the rule engine result with a low confidence score. The complaint is then queued for human review rather than returning a 500 error to the citizen.

---

## File 8 — `app/agents_followup.py`

**Role:** The background/continuous agents: Follow-Up (SLA watching), Survey (citizen confirmation), Contractor (proof gating), and Predictive (nightly DBSCAN clustering).

### Follow-Up Agent

```python
# Subscribes to Supabase Realtime on ASSIGNED and IN_PROGRESS complaints
# Maintains an in-memory schedule of {complaint_id: sla_deadline}
# APScheduler (or asyncio tasks) checks deadlines every minute

async def start_followup_agent():
    sb = await get_supabase()
    channel = sb.channel("sla-watch")
    channel.on("postgres_changes", event="UPDATE", table="complaints",
               filter="status=in.(ASSIGNED,IN_PROGRESS)", callback=on_complaint_active)
    await channel.subscribe()

async def on_complaint_active(payload: dict):
    complaint = payload["new"]
    schedule_sla_checks(complaint["id"], complaint["sla_deadline"])

async def check_sla_deadlines():
    # Runs every minute via asyncio background task
    now = datetime.utcnow()
    for complaint_id, sla_deadline in list(sla_schedule.items()):
        elapsed_pct = (now - complaint_created_at[complaint_id]) / (sla_deadline - complaint_created_at[complaint_id])

        if elapsed_pct >= 1.0 and not already_escalated(complaint_id):
            await escalate_complaint(complaint_id)

        elif elapsed_pct >= 0.9 and not already_warned_90(complaint_id):
            await send_sla_warning(complaint_id, pct=90)

        elif elapsed_pct >= 0.5 and not already_reminded_50(complaint_id):
            await send_sla_reminder(complaint_id, pct=50)

async def escalate_complaint(complaint_id: str):
    await sb.table("complaints").update({"status": "ESCALATED"}).eq("id", complaint_id).execute()
    await log_event(complaint_id, "escalation", "agent", "followup_agent",
                    from_status="ASSIGNED", to_status="ESCALATED",
                    payload={"reason": "SLA_BREACH"})

    # Notify AA via Telegram (if registered) + SMTP Email
    await notify(recipient_id=get_aa_for_complaint(complaint_id),
                 event_type="sla_escalation",
                 payload={"complaint_id": complaint_id})

# Idempotency: before sending any notification, check complaint_events
# for existing notification of that type for that complaint
# → prevents double-sends on agent restart
def already_escalated(complaint_id: str) -> bool:
    events = get_events_for_complaint(complaint_id)
    return any(e["event_type"] == "escalation" for e in events)
```

### Survey Agent

```python
# Triggered when complaint transitions to FINAL_SURVEY_PENDING
# Listens on Realtime channel for that status change

async def on_final_survey_pending(payload: dict):
    complaint_id = payload["new"]["id"]
    grievance_id = payload["new"]["grievance_id"]

    # Send Telegram survey message to citizen
    citizen_chat_id = await get_citizen_chat_id(complaint_id)
    await telegram_send_survey(citizen_chat_id, grievance_id)

    # Register 72h timeout — after which auto-close as CLOSED_UNVERIFIED
    asyncio.get_event_loop().call_later(
        72 * 3600,
        lambda: asyncio.create_task(auto_close_unverified(complaint_id))
    )

async def handle_citizen_survey_reply(telegram_chat_id: str, reply_text: str):
    # Called by Telegram bot handler when citizen sends a message
    # that matches an active survey

    complaint_id = await get_open_survey_complaint(telegram_chat_id)
    if not complaint_id:
        return  # No active survey for this user

    approved = reply_text.strip().upper() in ["YES", "Y", "HA", "हाँ"]
    rejected = reply_text.strip().upper() in ["NO", "N", "NAHI", "नहीं"]

    if approved:
        await post_survey_response(complaint_id, "approved")
    elif rejected:
        await post_survey_response(complaint_id, "rejected")
        # Reopens complaint + escalates to AA + SMTP alert to AA

async def auto_close_unverified(complaint_id: str):
    # Fires if citizen hasn't responded in 72h
    current = await get_complaint_status(complaint_id)
    if current == "FINAL_SURVEY_PENDING":
        await sb.table("complaints").update({"status": "CLOSED_UNVERIFIED"}).eq("id", complaint_id).execute()
        await log_event(complaint_id, "status_change", "agent", "survey_agent",
                        from_status="FINAL_SURVEY_PENDING", to_status="CLOSED_UNVERIFIED",
                        payload={"reason": "citizen_no_response_72h"})
```

### Contractor Agent

```python
# Triggered when a work order is assigned to a contractor
# Blocks status transitions if proof photos are missing
# This is enforced at the API layer in routers_complaints.py (proof_url check)
# The Contractor Agent adds the secondary enforcement: 24h escalation if no proof uploaded

async def on_work_order_assigned(payload: dict):
    work_order_id = payload["new"]["id"]
    contractor_id = payload["new"]["contractor_id"]
    complaint_id  = payload["new"]["complaint_id"]

    # Schedule 24h proof check
    asyncio.get_event_loop().call_later(
        24 * 3600,
        lambda: asyncio.create_task(check_proof_submitted(complaint_id, contractor_id))
    )

async def check_proof_submitted(complaint_id: str, contractor_id: str):
    complaint = await get_complaint(complaint_id)
    # If still ASSIGNED (meaning IN_PROGRESS transition never happened = no proof uploaded)
    if complaint["status"] == "ASSIGNED":
        # Escalate to AA + email contractor
        await notify(recipient_id=get_aa_for_complaint(complaint_id),
                     event_type="contractor_proof_missing",
                     payload={"complaint_id": complaint_id, "contractor_id": contractor_id})

        contractor = await get_contractor(contractor_id)
        await send_email(
            to=contractor["contact_email"],
            subject=f"Action Required: Proof photo missing for complaint {complaint_id[:8]}",
            body_html="<p>Please upload your mid-job proof photo within 24 hours to avoid escalation.</p>"
        )
```

### Predictive Agent (DBSCAN)

```python
from sklearn.cluster import DBSCAN
import numpy as np

async def run_predictive_agent():
    # Called nightly by Render Cron → POST /internal/run-predictive-agent

    # 1. Fetch all complaints in last 90 days with coordinates
    sb = await get_supabase()
    result = await sb.rpc("get_complaints_with_coords_last_90_days").execute()
    complaints = result.data

    if len(complaints) < 5:
        return  # Not enough data

    # 2. Group by category and run DBSCAN per category
    from itertools import groupby
    complaints.sort(key=lambda c: c["category"])

    new_hotspots = []
    for category, group in groupby(complaints, key=lambda c: c["category"]):
        group_list = list(group)
        coords = np.array([[c["lat"], c["lng"]] for c in group_list])

        # eps = 200m in degrees ≈ 0.0018 degrees latitude
        # min_samples = 5
        db = DBSCAN(eps=0.0018, min_samples=5, metric="haversine").fit(np.radians(coords))

        # 3. Collect cluster centroids
        labels = db.labels_
        for label in set(labels):
            if label == -1:
                continue  # Noise points, not a cluster

            cluster_mask  = labels == label
            cluster_items = [group_list[i] for i, m in enumerate(cluster_mask) if m]

            # Only flag as hotspot if 5+ complaints in last 30 days
            recent = [c for c in cluster_items if is_within_30_days(c["created_at"])]
            if len(recent) < 5:
                continue

            avg_urgency  = sum(c["urgency"] for c in recent) / len(recent)
            density      = len(recent)
            severity     = min(5, round((density / 5) * avg_urgency))
            cluster_lats = [c["lat"] for c in recent]
            cluster_lngs = [c["lng"] for c in recent]
            center_lat   = sum(cluster_lats) / len(cluster_lats)
            center_lng   = sum(cluster_lngs) / len(cluster_lngs)
            ward_id      = await assign_ward(center_lat, center_lng)

            new_hotspots.append({
                "lat": center_lat, "lng": center_lng,
                "radius_m": 200, "category": category,
                "complaint_count": len(recent),
                "severity": severity,
                "ward_id": ward_id,
                "is_resolved": False
            })

    # 4. Upsert hotspots (replace old ones with fresh nightly run)
    await sb.table("hotspots").delete().eq("is_resolved", False).execute()
    if new_hotspots:
        await sb.table("hotspots").insert(new_hotspots).execute()
    # Supabase Realtime broadcasts the new hotspot rows to Super Admin dashboard instantly
```

---

## File 9 — `app/services.py`

**Role:** All external service integrations. Telegram bot, SMTP email, Bhashini translation, Gemini LLM, and the unified notification dispatcher that decides which channel to use per recipient type.

### SMTP Email

```python
import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from app.config import settings

async def send_email(to: str, subject: str, body_html: str) -> bool:
    msg = MIMEMultipart("alternative")
    msg["From"]    = settings.SMTP_FROM_EMAIL
    msg["To"]      = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body_html, "html"))
    try:
        await aiosmtplib.send(msg,
            hostname=settings.SMTP_HOST, port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME, password=settings.SMTP_PASSWORD,
            start_tls=True)
        return True
    except Exception as e:
        print(f"[SMTP] Failed to send to {to}: {e}")
        return False

# Typed wrappers — called by routers and agents
async def send_complaint_received(to: str, grievance_id: str):
    await send_email(to, f"Complaint Received — {grievance_id}",
        f"<p>Your complaint <strong>{grievance_id}</strong> has been received and is being processed.</p>")

async def send_status_update(to: str, grievance_id: str, new_status: str):
    await send_email(to, f"Status Update — {grievance_id}",
        f"<p>Your complaint <strong>{grievance_id}</strong> status has changed to <strong>{new_status}</strong>.</p>")

async def send_sla_warning_email(to: str, grievance_id: str, pct: int):
    await send_email(to, f"SLA Warning ({pct}%) — {grievance_id}",
        f"<p>Complaint <strong>{grievance_id}</strong> has consumed {pct}% of its SLA window.</p>")

async def send_escalation_alert(to: str, grievance_id: str, reason: str):
    await send_email(to, f"Escalation Alert — {grievance_id}",
        f"<p>Complaint <strong>{grievance_id}</strong> has been escalated. Reason: {reason}</p>")

async def send_contractor_assignment(to: str, work_order_id: str, details: dict):
    await send_email(to, f"New Work Order Assigned — {work_order_id[:8]}",
        f"<p>You have been assigned work order <strong>{work_order_id[:8]}</strong>. "
        f"Category: {details.get('category')}. Please log in to view details and upload proof photos.</p>")
```

### Telegram Bot

```python
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from app.config import settings

telegram_app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

# ── /start command ─────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to PS-CRM. Use /complaint to file a new complaint, "
        "or /status <grievance_id> to check your complaint status."
    )

# ── /complaint — multi-step conversation ──────────────────────────────
# Uses ConversationHandler (step 1: description, step 2: location, step 3: photo)
# On completion → POSTs to /api/v1/complaints internally
# Stores citizen telegram_chat_id for future notifications

# ── /status <id> ───────────────────────────────────────────────────────
async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: /status <grievance_id>")
        return
    grievance_id = ctx.args[0]
    # Call internal GET /complaints/{id} and format response as Telegram message

# ── Message handler — survey replies ──────────────────────────────────
async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # If user has an active survey → route to survey agent handler
    await handle_citizen_survey_reply(str(update.effective_chat.id), update.message.text)

# ── Send helper — called by notification dispatcher and agents ─────────
async def telegram_send(chat_id: str, text: str):
    await telegram_app.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")

telegram_app.add_handler(CommandHandler("start", cmd_start))
telegram_app.add_handler(CommandHandler("status", cmd_status))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
```

### Bhashini Translation

```python
import httpx
from app.config import settings

BHASHINI_URL = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"

async def translate_to_english(text: str, source_lang: str = "auto") -> str:
    if source_lang == "en" or _is_english(text):
        return text

    payload = {
        "pipelineTasks": [{"taskType": "translation", "config": {"language": {"sourceLanguage": source_lang, "targetLanguage": "en"}}}],
        "inputData": {"input": [{"source": text}]}
    }
    headers = {"userID": settings.BHASHINI_USER_ID, "ulcaApiKey": settings.BHASHINI_API_KEY}

    async with httpx.AsyncClient() as client:
        resp = await client.post(BHASHINI_URL, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()["pipelineResponse"][0]["output"][0]["target"]

async def translate_from_english(text: str, target_lang: str) -> str:
    # Used to send Telegram notifications in citizen's preferred language
    ...
```

### Gemini Classification

```python
import google.generativeai as genai
from app.config import settings
from app.models import ClassificationResult

genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

CLASSIFICATION_PROMPT = """
You are a civic complaint classification system for Delhi MCD.
Given the complaint text below, return a JSON object with exactly these fields:
- category: one of [drainage, streetlight, road, tree, garbage, water_supply, other]
- urgency: integer 1-5 (1=low, 5=critical)
- departments: list of department names from [Public Works, Electricity, Horticulture, Sanitation, Water Supply]
- asset_types: list of asset types from [pole, drain, road_segment, tree, water_main, garbage_point]

Respond with JSON only. No explanation.

Complaint: {complaint_text}
"""

async def classify_with_gemini(text: str) -> ClassificationResult:
    try:
        response = model.generate_content(CLASSIFICATION_PROMPT.format(complaint_text=text))
        import json
        data = json.loads(response.text)
        return ClassificationResult(**data, confidence=0.95, llm_used=True)
    except Exception as e:
        # Fallback: return rule engine result or queue for human review
        raise GeminiFailure(str(e))
```

### Unified Notification Dispatcher

```python
async def notify(recipient_id: str, event_type: str, payload: dict):
    """
    Routes notification to correct channel based on recipient type.
    - Citizens      → Telegram only (chat_id stored at bot interaction time)
    - JSSA/AA/FAA   → Telegram if they have a registered chat_id, else SMTP Email
    - Contractors   → SMTP Email always (contact_email field)
    - Super Admin   → Both Telegram + SMTP Email
    """
    recipient = await resolve_recipient(recipient_id)

    message = format_notification(event_type, payload, recipient["preferred_language"])

    if recipient["type"] == "citizen":
        if recipient.get("telegram_chat_id"):
            await telegram_send(recipient["telegram_chat_id"], message)

    elif recipient["type"] in ["jssa", "aa", "faa"]:
        if recipient.get("telegram_chat_id"):
            await telegram_send(recipient["telegram_chat_id"], message)
        elif recipient.get("email"):
            await send_email(recipient["email"], subject_from_event(event_type), f"<p>{message}</p>")

    elif recipient["type"] == "contractor":
        await send_email(recipient["contact_email"], subject_from_event(event_type), f"<p>{message}</p>")

    elif recipient["type"] == "super_admin":
        if recipient.get("telegram_chat_id"):
            await telegram_send(recipient["telegram_chat_id"], message)
        if recipient.get("email"):
            await send_email(recipient["email"], subject_from_event(event_type), f"<p>{message}</p>")
```

---

## File 10 — `app/utils.py`

**Role:** Pure utility functions. Grievance ID generator, state machine validator, keyword rule engine. No external calls, no DB access. Fully testable in isolation.

### Grievance ID Generator

```python
import random, string
from datetime import datetime

def generate_grievance_id() -> str:
    """
    Format: MCD-YYYYMMDD-XXXXX
    Example: MCD-20250315-A7K2M
    The random suffix is alphanumeric uppercase — 5 chars = 36^5 = 60M combinations
    Collision probability negligible for expected volume (~10K complaints/day)
    """
    date_str = datetime.utcnow().strftime("%Y%m%d")
    suffix   = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"MCD-{date_str}-{suffix}"
```

### State Machine

```python
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
```

### Keyword Rule Engine

```python
import json, re
from pathlib import Path
from app.models import ClassificationResult

# keyword_dict.json — configurable without code changes
# {
#   "drainage":    { "keywords": ["drain","sewer","waterlogging","nala","overflow"], "department": "Public Works", "asset_type": "drain" },
#   "streetlight": { "keywords": ["streetlight","lamp post","electric pole","light out"], "department": "Electricity", "asset_type": "pole" },
#   ...
# }
KEYWORD_DICT = json.loads(Path("app/keyword_dict.json").read_text())

URGENCY_BOOSTERS = {
    "fire":        5, "accident": 5, "collapse": 5, "flood":  5,
    "dangerous":   4, "broken":   3, "blocked":  3, "smells": 2,
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
        return ClassificationResult(category="other", urgency=2, departments=[], asset_types=[], confidence=0.0, llm_used=False)

    best_category = max(scores, key=scores.get)
    confidence    = scores[best_category]

    # Urgency from keyword boosters
    urgency = 2  # default
    for keyword, boost in URGENCY_BOOSTERS.items():
        if keyword in text_lower:
            urgency = max(urgency, boost)

    config = KEYWORD_DICT[best_category]
    return ClassificationResult(
        category=best_category,
        urgency=urgency,
        departments=[config["department"]],
        asset_types=[config["asset_type"]],
        confidence=confidence,
        llm_used=False
    )
```

### SLA Deadline Calculator

```python
from datetime import datetime, timedelta

SLA_HOURS_BY_CATEGORY: dict[str, int] = {
    "drainage":    48,
    "streetlight": 72,
    "road":        72,
    "tree":        96,
    "garbage":     24,
    "water_supply":24,
    "other":       72,
}

def compute_sla_deadline(category: str) -> datetime:
    hours = SLA_HOURS_BY_CATEGORY.get(category, 72)
    return datetime.utcnow() + timedelta(hours=hours)
```

### Audit Log Helper

```python
async def log_event(
    complaint_id: str,
    event_type: str,
    actor_type: str,
    actor_id: str = "system",
    from_status: str = None,
    to_status: str = None,
    payload: dict = None
):
    """
    Append-only write to complaint_events.
    Called from routers, agents, and services.
    RLS on this table: INSERT only — no UPDATE or DELETE for anyone.
    """
    sb = await get_supabase()
    await sb.table("complaint_events").insert({
        "complaint_id": complaint_id,
        "event_type":   event_type,
        "actor_type":   actor_type,
        "actor_id":     actor_id,
        "from_status":  from_status,
        "to_status":    to_status,
        "payload":      payload or {}
    }).execute()
```

---

## Summary Table

| # | File | Lines (est.) | What it owns |
|---|------|-------------|--------------|
| 1 | `main.py` | ~80 | App boot, CORS, routers, Telegram webhook, cron endpoint |
| 2 | `config.py` + `database.py` | ~120 | Settings, Supabase client, Realtime, PostGIS helpers |
| 3 | `models.py` | ~150 | All Pydantic schemas and enums |
| 4 | `routers_complaints.py` | ~250 | Complaint intake pipeline, status updates, surveys |
| 5 | `routers_admin.py` | ~200 | Officers, contractors, wards, assets, work orders |
| 6 | `routers_analytics.py` | ~120 | Hotspots, SLA compliance, volume, ward density |
| 7 | `agents.py` | ~200 | Supervisor + Classification + GeoSpatial + Routing |
| 8 | `agents_followup.py` | ~250 | Follow-Up + Survey + Contractor + Predictive (DBSCAN) |
| 9 | `services.py` | ~250 | Telegram bot, SMTP email, Bhashini, Gemini, notify() |
| 10 | `utils.py` | ~150 | Grievance ID, state machine, rule engine, log_event |

**Plus (not counted):**
- `keyword_dict.json` — keyword configuration
- `requirements.txt`
- `Dockerfile`
- `.env.example`
- `supabase/migrations/` — SQL files (schema, RLS, RPC functions, seed data)