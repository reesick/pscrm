# PS-CRM — Feature Implementation Verification Plan

> Source of truth: **PRD.md** (all 12 sections)
> Status key: ✅ Implemented | ⚠️ Partial | ❌ Not Done | 🔍 Cannot Verify Without Backend Access

---

## How to Read This Document

Each feature is traced directly from a PRD section. The "Evidence" column records what was visible in screenshots + Swagger UI + models.py. The "Root Fix Required" column tells you exactly what needs to be built, not patched.

---

## Section 1 — Complaint Intake Pipeline

| # | Feature | PRD Ref | Status | Evidence | Root Fix Required |
|---|---------|---------|--------|----------|-------------------|
| 1.1 | POST /complaints endpoint exists | §8.2 | ✅ | Swagger shows endpoint with correct schema | — |
| 1.2 | Grievance ID generation (MCD-YYYYMMDD-XXXXX) | §8.2 | ✅ | Swagger response includes grievance_id field | — |
| 1.3 | Bhashini translation (raw_text → translated_text) | §5.4 | ⚠️ | Field exists in models, no test confirms live call | Verify BHASHINI env vars are set on Render. Test with Hindi input end-to-end. |
| 1.4 | Rule engine classification (confidence ≥ 0.85) | §5.4 | ⚠️ | ClassificationResult model exists. No keyword_dict.json confirmed | Confirm keyword_dict.json is committed to repo. Test 1.7 from PRD verification checklist. |
| 1.5 | Gemini fallback when confidence < 0.85 | §5.4 | ⚠️ | llm_used field in model. No test confirms Gemini fires | Run PRD check 1.8. Verify GEMINI_API_KEY is set on Render. |
| 1.6 | Multi-department split (complaint_departments rows) | §5.4 | ⚠️ | complaint_departments table in schema. No test run | Run PRD check 1.9: tree-touching-pole complaint must create 2 rows |
| 1.7 | Ward assignment via PostGIS ST_Contains | §5.5 | ⚠️ | assign_ward RPC in setup_instructions.md. Not confirmed live | Run PRD check 1.11. Ward seed data must be present. |
| 1.8 | Asset linking via PostGIS ST_DWithin (50m) | §5.5 | ⚠️ | find_nearest_assets RPC in setup instructions. Not confirmed live | Run PRD check 1.10. Asset seed data (50+ assets) must exist. |
| 1.9 | citizen_email_hash (SHA-256, never plaintext) | §12.2 | ⚠️ | citizen_email_hash field in schema. Hashing logic unverified | Verify in routers_complaints.py that hashlib.sha256 is used before insert. Never store raw email. |
| 1.10 | Phone OTP removed → email-only receipt | IMPL PLAN | ✅ | ComplaintCreateRequest.citizen_email is Optional[EmailStr]. No phone field | — |
| 1.11 | SLA deadline computed from category on intake | §8.2 | ⚠️ | sla_deadline field exists. SLA_HOURS_BY_CATEGORY dict in utils.py spec | Verify sla_deadline is populated on every complaint INSERT. Check for null values in existing records. |
| 1.12 | media_urls stored as array (Supabase Storage) | §9.2 | ⚠️ | media_urls TEXT[] in schema, upload-url endpoint exists in Swagger | Test upload flow end-to-end: get pre-signed URL → upload file → submit complaint with file_path |
| 1.13 | complaint_events append-only log on intake | §9.4 | ⚠️ | table defined with no UPDATE RLS. log_event() helper specified | Verify complaint_created event is written on every POST /complaints. Check RLS: no DELETE policy on complaint_events. |

---

## Section 2 — Agent Pipeline (LangGraph)

| # | Feature | PRD Ref | Status | Evidence | Root Fix Required |
|---|---------|---------|--------|----------|-------------------|
| 2.1 | Supervisor Agent fires on complaint INSERT (Realtime) | §5.2 | ⚠️ | init_supabase_realtime() in main.py spec. Cannot confirm live | Verify Realtime publication includes complaints table. Check Render logs on new complaint submission. |
| 2.2 | Classification Agent node in LangGraph graph | §5.2 | ⚠️ | agents.py spec describes graph. Cannot confirm compiled | Run: submit complaint → check status changes NEW→CLASSIFIED within 10 seconds |
| 2.3 | GeoSpatial Agent node | §5.2 | ⚠️ | Same as above | Run: submit complaint with known coords → check ward_id + asset_ids populated |
| 2.4 | Department Routing Agent node | §5.2 | ⚠️ | Same as above | Run: after CLASSIFIED → check status becomes ASSIGNED, JSSA notified |
| 2.5 | Human-in-loop review queue (low confidence) | §2.9 | ❌ | Not visible in Swagger. No /review-queue endpoint | Build: add needs_review flag to complaints. Super Admin endpoint to list them. Manual classify endpoint. |
| 2.6 | Follow-Up Agent SLA reminders (50%, 90%) | §5.6 | ❌ | agents_followup.py spec exists but no Swagger endpoint. Cannot verify | Build: async background task. Test by setting sla_deadline to 50% elapsed. Verify complaint_events has sla_reminder event. |
| 2.7 | Follow-Up Agent auto-escalate at 100% SLA | §5.6 | ❌ | Same — not visible in current system state | Build + test: PRD check 2.5 — set sla_deadline to past, verify ESCALATED within 5 min |
| 2.8 | Survey Agent fires on FINAL_SURVEY_PENDING | §5.2 | ❌ | No Telegram survey observable. survey-response endpoint exists in Swagger | Build: Realtime trigger on status=FINAL_SURVEY_PENDING → send Telegram message. Handle YES/NO reply. |
| 2.9 | Survey 72h auto-close → CLOSED_UNVERIFIED | §5.2 | ❌ | Not observable | Build: asyncio.call_later(72*3600, auto_close_unverified). Test: PRD check 2.10 |
| 2.10 | Contractor Agent proof gate | §5.2 | ⚠️ | Proof gate enforcement IS in routers_complaints.py spec (400 if no proof_url). Need to verify actually coded | Test: PRD check 2.6 — PATCH status to IN_PROGRESS without proof_url → must return 400 |
| 2.11 | Contractor Agent 24h proof escalation | §5.2 | ❌ | Background check logic not observable | Build: asyncio task at work order assign time. 24h later check if still ASSIGNED. |
| 2.12 | Predictive Agent DBSCAN nightly | §5.7 | ❌ | POST /internal/run-predictive-agent exists in Swagger. No hotspots in DB observable | Build: scikit-learn DBSCAN. Test: PRD check 3.1 — seed 7 drainage complaints within 150m → run agent → check hotspots table |
| 2.13 | Render Cron Job at 2:00 AM | §5.7 | ❌ | Not visible (Render config) | Set up: Render Cron Job pointing to /internal/run-predictive-agent with X-Internal-Key header |

---

## Section 3 — State Machine

| # | Feature | PRD Ref | Status | Evidence | Root Fix Required |
|---|---------|---------|--------|----------|-------------------|
| 3.1 | All 10 statuses defined | §5.3 | ✅ | ComplaintStatus enum has all 10 values | — |
| 3.2 | VALID_TRANSITIONS dict enforced on PATCH /status | §5.3 | ⚠️ | Logic in utils.py spec. validate_transition() called in router spec | Test all invalid transitions — each must return 400 |
| 3.3 | CLOSED and CLOSED_UNVERIFIED are terminal (no exit) | §5.3 | ⚠️ | Not in VALID_TRANSITIONS dict for any exit transition | Verify: attempt to PATCH a CLOSED complaint → must return 400 |
| 3.4 | Every transition logged to complaint_events | §9.4 | ⚠️ | log_event() called in router spec after status update | Verify complaint_events row created on every PATCH /status call |
| 3.5 | Proof photo required for IN_PROGRESS transition | §5.3 | ⚠️ | Code path exists in router spec. Not confirmed live | Test PRD check 2.6 |
| 3.6 | Proof photo required for FINAL_SURVEY_PENDING | §5.3 | ⚠️ | Same | Test with proof_url absent |

---

## Section 4 — Notifications

| # | Feature | PRD Ref | Status | Evidence | Root Fix Required |
|---|---------|---------|--------|----------|-------------------|
| 4.1 | SMTP email on complaint received (citizen) | §1.5 | ⚠️ | send_complaint_received() in services spec. SMTP env vars defined | Verify SMTP creds work. Submit complaint with email → check inbox. |
| 4.2 | SMTP email on status update | §1.5 | ❌ | Function defined in spec. Not confirmed wired to status update flow | Wire send_status_update() call into PATCH /status handler |
| 4.3 | SMTP email for SLA warning to officer | §1.5 | ❌ | Function defined. Follow-Up Agent not confirmed running | Depends on Follow-Up Agent being built first (2.6) |
| 4.4 | SMTP email for escalation alert to AA | §1.5 | ❌ | Same dependency | Depends on Follow-Up Agent |
| 4.5 | SMTP email for contractor work order assignment | §1.5 | ❌ | Function defined. Work order creation endpoint exists | Wire send_contractor_assignment() into POST /work-orders handler |
| 4.6 | Telegram notification to citizen on assignment | §4.1 | ❌ | notify() dispatcher in services spec. Not confirmed live | Build: after routing_node assigns JSSA, call notify() for citizen with Telegram chat_id |
| 4.7 | Telegram notification to JSSA on new assignment | §5.2 | ❌ | routing_node spec calls notify(). Not confirmed | Same as above — verify routing_node fires and chat_id is stored |
| 4.8 | Telegram survey message to citizen | §5.2 | ❌ | Survey Agent not built | Depends on Survey Agent (2.8) |
| 4.9 | Unified notify() dispatcher (Telegram vs Email routing) | §1.6 | ⚠️ | Function defined in services spec | End-to-end test after agents are confirmed running |

---

## Section 5 — API Endpoints

| # | Endpoint | PRD Ref | Status | Evidence |
|---|----------|---------|--------|----------|
| 5.1 | POST /api/v1/complaints | §8.2 | ✅ | Swagger ✅ |
| 5.2 | GET /api/v1/complaints | §8.2 | ✅ | Swagger ✅ |
| 5.3 | GET /api/v1/complaints/{id} | §8.2 | ✅ | Swagger ✅ |
| 5.4 | PATCH /api/v1/complaints/{id}/status | §8.2 | ✅ | Swagger ✅ |
| 5.5 | POST /api/v1/complaints/{id}/survey-response | §8.3 | ✅ | Swagger ✅ |
| 5.6 | POST /api/v1/complaints/upload-url | §8.6 | ✅ | Swagger ✅ |
| 5.7 | GET /api/v1/officers/{id}/stats | §8.4 | ✅ | Swagger ✅ |
| 5.8 | GET /api/v1/contractors/{id}/scorecard | §8.4 | ✅ | Swagger ✅ |
| 5.9 | PATCH /api/v1/contractors/{id}/status | §8.4 | ✅ | Swagger ✅ |
| 5.10 | GET /api/v1/assets | §8.6 | ✅ | Swagger ✅ |
| 5.11 | GET /api/v1/wards | §8.6 | ✅ | Swagger ✅ |
| 5.12 | GET /api/v1/analytics/hotspots | §8.5 | ✅ | Swagger ✅ |
| 5.13 | GET /api/v1/analytics/sla-compliance | §8.5 | ✅ | Swagger ✅ |
| 5.14 | GET /api/v1/analytics/complaint-volume | §8.5 | ✅ | Swagger ✅ |
| 5.15 | GET /api/v1/analytics/ward-density | §8.5 | ✅ | Swagger ✅ |
| 5.16 | GET /health | §1.3 | ✅ | Swagger ✅ |
| 5.17 | POST /internal/run-predictive-agent | §5.7 | ✅ | Swagger ✅ |
| 5.18 | GET + POST /api/v1/complaints/{id}/work-orders | §3.6 | ✅ | Swagger ✅ |
| 5.19 | Human review queue endpoints | §2.9 | ❌ | Not in Swagger — missing entirely |

---

## Section 6 — Dashboards (Frontend)

| # | Feature | PRD Ref | Status | Evidence | Root Fix Required |
|---|---------|---------|--------|----------|-------------------|
| 6.1 | Public landing page — complaint form | §4.1 | ✅ | Screenshot 1 shows form with map, description, email | UI needs redesign — see UI Fix doc |
| 6.2 | Public landing — grievance ID tracker | §4.1 | ✅ | Screenshot 1 shows Track Complaint panel | — |
| 6.3 | Public map page — ward heatmap | §3.5 | ❌ | Screenshot 2: map is completely blank. Only legend/filter visible | **Root cause:** MapLibre map not rendering. Tiles not loading. Fix: verify MapLibre CSS imported, container has explicit height, OpenFreeMap tile URL accessible |
| 6.4 | JSSA dashboard — map view with complaint pins | §4.2 | ❌ | Screenshot 3: map panel is 100% blank grey | **Root cause:** Same MapLibre init issue. Map container has no height or CSS not loaded |
| 6.5 | JSSA dashboard — task queue sidebar | §4.2 | ✅ | Screenshot 3: task queue renders with complaints, urgency dots, SLA | UI needs improvement — dots too small, text hierarchy weak |
| 6.6 | JSSA dashboard — Supabase Realtime live updates | §4.2 | 🔍 | Cannot verify from screenshots alone | Test: update complaint from another tab → pin should update without refresh |
| 6.7 | JSSA dashboard — slide-in complaint detail panel | §4.2 | ❌ | Not visible in screenshots | Build: click complaint card → Sheet component slides in with full detail + status update form |
| 6.8 | JSSA dashboard — status update with state machine | §4.2 | ❌ | No UI for status update visible | Build inside detail panel |
| 6.9 | JSSA dashboard — proof photo upload | §4.2 | ❌ | Not visible | Build inside detail panel |
| 6.10 | AA dashboard — escalation queue | §4.3 | 🔍 | No AA dashboard screenshot provided | Build or verify complete |
| 6.11 | AA dashboard — officer performance table | §3.4 | 🔍 | No screenshot | Build or verify complete |
| 6.12 | FAA dashboard | §3.6 | 🔍 | No screenshot | Build or verify complete |
| 6.13 | Super Admin dashboard — KPI cards | §3.2 | 🔍 | No screenshot | Build or verify complete |
| 6.14 | Super Admin dashboard — volume + SLA charts | §3.2 | 🔍 | No screenshot | Build or verify complete |
| 6.15 | Super Admin dashboard — hotspot map | §3.2 | 🔍 | No screenshot | Depends on Predictive Agent being built |
| 6.16 | Super Admin — contractor scorecard | §3.3 | 🔍 | No screenshot | Build or verify complete |
| 6.17 | Contractor portal — task list + proof upload | §3.7 | 🔍 | No screenshot | Build or verify complete |
| 6.18 | Auth — login page + role-based redirect | §1.2 | ✅ | "Go to Login" button visible on landing | Verify role-based redirect works post-login |
| 6.19 | Mobile responsive (375px) | §12.4 | ❌ | Not tested | Needs verification at 375px width |

---

## Section 7 — Security & Data Privacy

| # | Feature | PRD Ref | Status | Evidence | Root Fix Required |
|---|---------|---------|--------|----------|-------------------|
| 7.1 | JWT auth on all non-public endpoints | §12.2 | ⚠️ | authorization header in Swagger for protected endpoints | Test: call GET /complaints without JWT → must return 401 |
| 7.2 | RLS: JSSA sees only their ward | §12.2 | ⚠️ | Policy defined in setup SQL | Test PRD check 1.2: JSSA queries complaint from other ward → 0 results |
| 7.3 | complaint_events append-only (no UPDATE/DELETE RLS) | §12.2 | ⚠️ | Policy spec says INSERT only | Verify: attempt UPDATE on complaint_events via Supabase client → must fail |
| 7.4 | Officer phone/email not in public API responses | §12.2 | ✅ | ComplaintPublicResponse excludes officer details | — |
| 7.5 | Internal notes excluded from public responses | §12.2 | ✅ | internal_notes not in ComplaintPublicResponse | — |
| 7.6 | citizen_email_hash SHA-256 (never plaintext) | §12.2 | ⚠️ | Field exists. Hashing not confirmed in running code | Verify in routers_complaints.py |
| 7.7 | File uploads restricted to images, max 10MB | §12.2 | ⚠️ | Supabase Storage policy needs to be set | Set storage bucket policy: allowed MIME types image/* only, max 10MB |

---

## Section 8 — Performance

| # | Feature | PRD Ref | Status | Evidence | Root Fix Required |
|---|---------|---------|--------|----------|-------------------|
| 8.1 | API response < 300ms (p95, non-LLM) | §12.1 | 🔍 | Not tested | Run: load test with 50 concurrent GET /complaints requests. Target p95 < 300ms |
| 8.2 | Gemini classification < 5 seconds | §12.1 | 🔍 | Not tested | Log classification time. Alert if > 5s. |
| 8.3 | Map initial load < 2 seconds on 4G | §12.1 | ❌ | Map is blank — cannot even measure | Fix map first, then test |
| 8.4 | Supabase Realtime update < 3 seconds | §12.1 | 🔍 | Not tested | Test: status change → dashboard pin update latency |

---

## Priority Order for Root Fixes

### P0 — Must Fix Before Anything Else
1. **MapLibre not rendering** (affects public map + JSSA dashboard) — frontend CSS/init bug
2. **State machine enforcement** — test every invalid transition returns 400
3. **Proof gate enforcement** — verify 400 on missing proof_url

### P1 — Core Agent Pipeline
4. **Supervisor Agent → Realtime trigger** — verify NEW → CLASSIFIED → ASSIGNED flow end-to-end
5. **Follow-Up Agent** — SLA reminders + auto-escalation
6. **Survey Agent** — FINAL_SURVEY_PENDING → Telegram → response → status change

### P2 — Dashboard Completeness
7. **JSSA detail panel** — complaint detail + status update + proof upload
8. **AA dashboard** — escalation queue + officer table
9. **Super Admin analytics** — KPIs + charts + hotspot map
10. **Contractor portal** — task list + proof upload

### P3 — Polish
11. **Human review queue** endpoint + Super Admin UI
12. **Mobile responsive** at 375px
13. **Loading states + empty states** on all data-fetching components
14. **Demo seed data** — 50+ realistic complaints across 5 wards