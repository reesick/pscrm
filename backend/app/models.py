from pydantic import BaseModel, UUID4, EmailStr, field_validator
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
    citizen_email: Optional[EmailStr] = None  # Optional — used for email receipt only
    raw_text: str
    lat: float
    lng: float
    media_urls: List[str] = []
    channel: Channel

    @field_validator("lat")
    @classmethod
    def validate_lat(cls, v: float) -> float:
        if v < -90 or v > 90:
            raise ValueError("Latitude must be between -90 and 90")
        return v

    @field_validator("lng")
    @classmethod
    def validate_lng(cls, v: float) -> float:
        if v < -180 or v > 180:
            raise ValueError("Longitude must be between -180 and 180")
        return v


class ComplaintStatusUpdateRequest(BaseModel):
    # Sent by JSSA to update status
    new_status: ComplaintStatus
    internal_note: Optional[str] = None
    proof_url: Optional[str] = None   # Required for IN_PROGRESS and FINAL_SURVEY_PENDING


class ComplaintPublicResponse(BaseModel):
    # Returned to citizens — NO officer phone, NO internal notes, NO lat/lng
    id: UUID4
    grievance_id: str
    status: ComplaintStatus
    category: Optional[str] = None
    department_names: List[str] = []
    timeline: List["ComplaintEventPublic"] = []
    sla_deadline: Optional[datetime] = None
    created_at: datetime


class ComplaintAdminResponse(ComplaintPublicResponse):
    # Returned to JSSA/AA/Admin — adds officer info, internal notes
    ward_id: Optional[UUID4] = None
    urgency: int = 2
    translated_text: Optional[str] = None
    assigned_officer_name: Optional[str] = None
    internal_notes: List[str] = []
    asset_ids: List[UUID4] = []
    classification_confidence: Optional[float] = None
    llm_used: bool = False
    lat: Optional[float] = None   # Extracted from PostGIS location column
    lng: Optional[float] = None   # Extracted from PostGIS location column


# ── Complaint event (timeline entry) ─────────────────────────────────

class ComplaintEventPublic(BaseModel):
    event_type: str
    actor_type: str
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    created_at: datetime
    # payload excluded from public view — internal data only


# ── Survey ────────────────────────────────────────────────────────────

class SurveyResponseRequest(BaseModel):
    response: SurveyResponse
    citizen_note: Optional[str] = None


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
    active_work_orders: List[dict] = []


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
    category: Optional[str] = None
    ward_name: Optional[str] = None


# ── Classification result (internal — not exposed via API) ────────────

class ClassificationResult(BaseModel):
    category: str
    urgency: int           # 1–5
    departments: List[str]
    asset_types: List[str]
    confidence: float      # 0.0–1.0
    llm_used: bool


# ── Auth helpers (internal) ───────────────────────────────────────────

class CurrentUser(BaseModel):
    id: str
    role: str
    ward_id: Optional[str] = None
    zone_ward_ids: List[str] = []
    email: Optional[str] = None


# Rebuild forward references
ComplaintPublicResponse.model_rebuild()
ComplaintAdminResponse.model_rebuild()
