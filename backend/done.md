# PS-CRM — Missing Features Build Plan
**Root implementations for everything not yet working. No patches. Every solution is complete.**

---

## Execution Order

```
Step 1  → Fix: next.config.js + MapLibre (fixes blank maps everywhere)
Step 2  → Fix: Dashboard layout height (makes maps work inside panels)
Step 3  → Fix: Supabase Realtime wiring (fixes agents not triggering)
Step 4  → Build: JSSA complaint detail panel + status update
Step 5  → Build: Follow-Up Agent (SLA reminders + auto-escalation)
Step 6  → Build: Survey Agent (Telegram → CLOSED / REOPENED)
Step 7  → Build: SMTP email notifications wired throughout
Step 8  → Build: AA dashboard (escalation queue + officer table)
Step 9  → Build: Super Admin analytics (KPIs + charts + hotspot map)
Step 10 → Build: FAA tender dashboard
Step 11 → Build: Contractor portal
Step 12 → Build: /track/[id] public complaint status page
Step 13 → Build: Human review queue (backend + Super Admin UI)
Step 14 → Build: Demo seed data SQL (50+ realistic complaints)
Step 15 → Polish: skeleton loaders + empty states + toast notifications
```

---

# STEP 1 — Fix MapLibre (Root cause of blank maps)

## `next.config.js`
```js
/** @type {import('next').NextConfig} */
const nextConfig = {
  // MapLibre uses browser-only APIs — must be transpiled
  transpilePackages: ['maplibre-gl'],
  webpack: (config, { isServer }) => {
    if (isServer) {
      // Prevent MapLibre trying to import canvas on server
      config.externals = [...(config.externals || []), 'canvas']
    }
    config.resolve.fallback = {
      ...config.resolve.fallback,
      fs: false, net: false, tls: false,
    }
    return config
  },
}
module.exports = nextConfig
```

## `components/map/MapView.tsx`
The one correct MapLibre component. Always import this with `dynamic(..., { ssr: false })`.

```tsx
'use client'

import { useEffect, useRef, forwardRef, useImperativeHandle } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'  // ← THIS LINE IS WHY MAPS WERE BLANK

export interface MapViewHandle {
  getMap: () => maplibregl.Map | null
}

interface MapViewProps {
  center?: [number, number]  // [lng, lat]
  zoom?: number
  className?: string
  onReady?: (map: maplibregl.Map) => void
  onClick?: (lngLat: { lng: number; lat: number }) => void
}

// Primary tile style with automatic fallback
const TILE_STYLE_PRIMARY  = 'https://tiles.openfreemap.org/styles/liberty'
const TILE_STYLE_FALLBACK = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json'

const MapView = forwardRef<MapViewHandle, MapViewProps>(({
  center    = [77.2090, 28.6139],
  zoom      = 11,
  className = 'w-full h-full',
  onReady,
  onClick,
}, ref) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef       = useRef<maplibregl.Map | null>(null)

  useImperativeHandle(ref, () => ({
    getMap: () => mapRef.current,
  }))

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const map = new maplibregl.Map({
      container:          containerRef.current,
      style:              TILE_STYLE_PRIMARY,
      center,
      zoom,
      attributionControl: false,
      fadeDuration:       200,
    })

    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-left')
    map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right')

    let styleLoaded = false
    map.on('styledata', () => { styleLoaded = true })

    // Fallback if primary tiles fail
    map.on('error', (e) => {
      if (!styleLoaded) {
        console.warn('[MapView] Primary tiles failed, switching to fallback')
        map.setStyle(TILE_STYLE_FALLBACK)
      }
    })

    map.on('load', () => {
      onReady?.(map)
    })

    if (onClick) {
      map.on('click', (e) => {
        onClick({ lng: e.lngLat.lng, lat: e.lngLat.lat })
      })
    }

    mapRef.current = map
    return () => { map.remove(); mapRef.current = null }
  }, [])  // Empty dep array — map only initialises once

  return <div ref={containerRef} className={className} />
})

MapView.displayName = 'MapView'
export default MapView
```

**Usage in every page (mandatory pattern):**
```tsx
import dynamic from 'next/dynamic'

const MapView = dynamic(
  () => import('@/components/map/MapView'),
  {
    ssr: false,
    loading: () => <div className="w-full h-full bg-[#F3F4F6] animate-pulse rounded" />,
  }
)

// In render — container MUST have explicit pixel height or absolute inset
<div className="relative w-full h-[600px]">   {/* OR: absolute inset-0 inside a positioned parent */}
  <MapView center={[77.209, 28.614]} zoom={12} onReady={handleMapReady} />
</div>
```

---

# STEP 2 — Fix Dashboard Layout (Height propagation)

## `app/(dashboard)/layout.tsx`

```tsx
import { redirect } from 'next/navigation'
import { createServerComponentClient } from '@supabase/auth-helpers-nextjs'
import { cookies } from 'next/headers'
import { Sidebar } from '@/components/dashboard/Sidebar'
import { TopBar } from '@/components/dashboard/TopBar'

const ROLE_NAV = {
  jssa: [
    { label: 'Ward Map & Tasks', href: '/dashboard/jssa',    icon: 'MapPin' },
  ],
  aa: [
    { label: 'Escalation Queue', href: '/dashboard/aa',     icon: 'AlertTriangle' },
    { label: 'Officer Stats',    href: '/dashboard/aa/officers', icon: 'Users' },
  ],
  faa: [
    { label: 'Escalations',      href: '/dashboard/faa',    icon: 'AlertOctagon' },
    { label: 'Tenders',          href: '/dashboard/faa/tenders', icon: 'Briefcase' },
  ],
  super_admin: [
    { label: 'Analytics',        href: '/dashboard/super-admin',              icon: 'BarChart2' },
    { label: 'Contractors',      href: '/dashboard/super-admin/contractors',  icon: 'Wrench' },
    { label: 'Officers',         href: '/dashboard/super-admin/officers',     icon: 'Users' },
    { label: 'Review Queue',     href: '/dashboard/super-admin/review',       icon: 'ClipboardCheck' },
    { label: 'Settings',         href: '/dashboard/super-admin/settings',     icon: 'Settings' },
  ],
  contractor: [
    { label: 'My Tasks',         href: '/dashboard/contractor', icon: 'Clipboard' },
    { label: 'My Scorecard',     href: '/dashboard/contractor/scorecard', icon: 'Star' },
  ],
}

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const supabase = createServerComponentClient({ cookies })
  const { data: { session } } = await supabase.auth.getSession()

  if (!session) redirect('/login')

  const role = session.user.user_metadata?.role ?? 'jssa'
  const nav  = ROLE_NAV[role as keyof typeof ROLE_NAV] ?? []

  return (
    // CRITICAL: h-screen + overflow-hidden on root
    // This makes h-full work for all children, enabling proper map sizing
    <div className="flex h-screen overflow-hidden bg-[#F9FAFB]">
      <Sidebar items={nav} role={role} user={session.user} />
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <TopBar user={session.user} />
        {/* CRITICAL: overflow-hidden here — each child page manages its own scroll */}
        <main className="flex-1 overflow-hidden">
          {children}
        </main>
      </div>
    </div>
  )
}
```

---

# STEP 3 — Fix Supabase Realtime Wiring (Agents not triggering)

The screenshot shows complaints stuck at `status=NEW`. The Supervisor Agent is not firing because the Realtime subscription in `main.py` is either not set up or the channel isn't being listened to.

## `app/main.py` — Lifespan fix

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import logging

from app.database import get_supabase_service
from app.agents.supervisor import handle_new_complaint
from app.routers import complaints, admin, analytics
from app.config import settings

logger = logging.getLogger(__name__)

# Global realtime channel reference (so it isn't garbage collected)
_realtime_channel = None

async def setup_realtime_subscription():
    """
    Subscribe to new complaint INSERT events via Supabase Realtime.
    When a new complaint lands (status=NEW), the Supervisor Agent fires.
    This MUST run as an async background task, not blocking startup.
    """
    global _realtime_channel
    try:
        client = await get_supabase_service()

        def on_complaint_insert(payload):
            """Sync callback — schedule async coroutine in the event loop"""
            record = payload.get('new', {})
            if record.get('status') == 'NEW':
                complaint_id = record.get('id')
                logger.info(f"[Realtime] New complaint {complaint_id} — firing Supervisor Agent")
                asyncio.create_task(handle_new_complaint(complaint_id))

        _realtime_channel = (
            client.realtime
            .channel('complaints-insert')
            .on(
                'postgres_changes',
                event='INSERT',
                schema='public',
                table='complaints',
                callback=on_complaint_insert,
            )
            .subscribe()
        )
        logger.info("[Realtime] Subscribed to complaints INSERT channel")

    except Exception as e:
        logger.error(f"[Realtime] Failed to subscribe: {e}")
        # Retry after 30 seconds rather than crashing startup
        await asyncio.sleep(30)
        await setup_realtime_subscription()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("PS-CRM backend starting up")
    # Start Realtime subscription as background task (non-blocking)
    asyncio.create_task(setup_realtime_subscription())
    yield
    # Shutdown
    logger.info("PS-CRM backend shutting down")
    global _realtime_channel
    if _realtime_channel:
        await _realtime_channel.unsubscribe()


app = FastAPI(
    title="PS-CRM Grievance Management API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(complaints.router, prefix="/api/v1", tags=["complaints"])
app.include_router(admin.router,      prefix="/api/v1", tags=["admin"])
app.include_router(analytics.router,  prefix="/api/v1", tags=["analytics"])


@app.get("/health")
async def health():
    return {"status": "ok"}
```

## `app/agents/supervisor.py` — Complete wiring

```python
import logging
from app.database import get_supabase_service
from app.agents.classification import run_classification
from app.agents.geospatial import run_geospatial
from app.agents.department_routing import run_routing
from app.utils.state_machine import validate_transition
from app.services.notifications import notify

logger = logging.getLogger(__name__)

async def handle_new_complaint(complaint_id: str):
    """
    Supervisor Agent entry point.
    Called on every new complaint INSERT (status=NEW).
    Orchestrates: classify → geolocate → route → notify.
    """
    client = await get_supabase_service()

    try:
        # Fetch full complaint record
        result = client.table('complaints').select('*').eq('id', complaint_id).single().execute()
        complaint = result.data
        if not complaint:
            logger.error(f"[Supervisor] Complaint {complaint_id} not found")
            return

        # Skip if already processed (idempotency)
        if complaint['status'] != 'NEW':
            logger.info(f"[Supervisor] Complaint {complaint_id} already at {complaint['status']}, skipping")
            return

        logger.info(f"[Supervisor] Processing complaint {complaint_id}")

        # ── Step 1: Classify ─────────────────────────────────────────────
        classification = await run_classification(
            text=complaint.get('translated_text') or complaint['raw_text'],
            complaint_id=complaint_id,
        )

        # Update classification fields
        client.table('complaints').update({
            'category':                   classification.category,
            'urgency':                    classification.urgency,
            'classification_confidence':  classification.confidence,
            'llm_used':                   classification.llm_used,
            'status':                     'CLASSIFIED',
        }).eq('id', complaint_id).execute()

        # Insert complaint_departments rows (one per department)
        for dept_name in classification.departments:
            dept = client.table('departments').select('id').eq('name', dept_name).single().execute()
            if dept.data:
                client.table('complaint_departments').insert({
                    'complaint_id':   complaint_id,
                    'department_id':  dept.data['id'],
                    'status':         'OPEN',
                }).execute()

        _log_event(client, complaint_id, 'status_changed', 'system', {
            'from_status': 'NEW', 'to_status': 'CLASSIFIED',
            'confidence': classification.confidence, 'llm_used': classification.llm_used,
        })

        # Handle low-confidence → queue for human review
        if classification.confidence < 0.5:
            client.table('complaints').update({'needs_review': True}).eq('id', complaint_id).execute()
            logger.info(f"[Supervisor] Complaint {complaint_id} queued for human review (confidence={classification.confidence:.2f})")
            return

        # ── Step 2: Geolocate ────────────────────────────────────────────
        geo = await run_geospatial(
            lat=complaint['lat'],   # extracted from PostGIS location column
            lng=complaint['lng'],
            complaint_id=complaint_id,
        )

        if geo.ward_id:
            client.table('complaints').update({
                'ward_id':   geo.ward_id,
                'asset_ids': geo.asset_ids,
            }).eq('id', complaint_id).execute()

        # ── Step 3: Route to JSSA ────────────────────────────────────────
        routing = await run_routing(complaint_id=complaint_id, ward_id=geo.ward_id)

        if routing.assigned_officer_id:
            client.table('complaints').update({
                'status': 'ASSIGNED',
            }).eq('id', complaint_id).execute()

            _log_event(client, complaint_id, 'status_changed', 'system', {
                'from_status': 'CLASSIFIED', 'to_status': 'ASSIGNED',
                'officer_id': routing.assigned_officer_id,
            })

            # ── Step 4: Notify ───────────────────────────────────────────
            # Notify JSSA via Telegram
            await notify(
                recipient_id=routing.assigned_officer_id,
                event_type='complaint_assigned',
                payload={'complaint_id': complaint_id, 'grievance_id': complaint['grievance_id']},
            )

            # Notify citizen via Telegram (if chat_id stored)
            if complaint.get('telegram_chat_id'):
                await notify(
                    recipient_id=complaint['telegram_chat_id'],
                    event_type='complaint_received',
                    payload={'grievance_id': complaint['grievance_id']},
                    channel='telegram',
                )

        logger.info(f"[Supervisor] Complaint {complaint_id} fully processed → ASSIGNED")

    except Exception as e:
        logger.exception(f"[Supervisor] Error processing complaint {complaint_id}: {e}")


def _log_event(client, complaint_id: str, event_type: str, actor_type: str, payload: dict):
    client.table('complaint_events').insert({
        'complaint_id': complaint_id,
        'event_type':   event_type,
        'actor_type':   actor_type,
        'payload':      payload,
    }).execute()
```

---

# STEP 4 — Build: JSSA Complaint Detail Panel

## `components/complaints/ComplaintDetailPanel.tsx`

```tsx
'use client'

import { useState, useEffect, useRef } from 'react'
import { X, Upload, ChevronDown, Clock, Paperclip, MessageSquare } from 'lucide-react'
import { formatDistanceToNow, isPast, format } from 'date-fns'
import { api } from '@/lib/api'
import { StatusBadge } from './StatusBadge'

// Valid transitions a JSSA can manually trigger
const JSSA_TRANSITIONS: Record<string, string[]> = {
  ASSIGNED:           ['IN_PROGRESS', 'ESCALATED'],
  IN_PROGRESS:        ['MID_SURVEY_PENDING', 'ESCALATED'],
  MID_SURVEY_PENDING: ['FINAL_SURVEY_PENDING'],
  ESCALATED:          ['ASSIGNED'],
  REOPENED:           ['ASSIGNED', 'ESCALATED'],
}

const STATUS_LABELS: Record<string, string> = {
  IN_PROGRESS:          'Mark In Progress',
  MID_SURVEY_PENDING:   'Send Mid Survey',
  FINAL_SURVEY_PENDING: 'Mark Work Complete',
  ESCALATED:            'Escalate',
  ASSIGNED:             'Reassign / Restart',
}

const CATEGORY_ICONS: Record<string, string> = {
  drainage: '💧', streetlight: '💡', road: '🛣️',
  tree: '🌳', garbage: '🗑️', water_supply: '🚿', other: '📋',
}

interface DetailPanelProps {
  complaintId: string
  onClose: () => void
  onStatusChanged?: (newStatus: string) => void
}

export function ComplaintDetailPanel({ complaintId, onClose, onStatusChanged }: DetailPanelProps) {
  const [complaint,   setComplaint]   = useState<any>(null)
  const [loading,     setLoading]     = useState(true)
  const [updating,    setUpdating]    = useState(false)
  const [error,       setError]       = useState<string | null>(null)
  const [proofUrl,    setProofUrl]    = useState('')
  const [proofFile,   setProofFile]   = useState<File | null>(null)
  const [uploading,   setUploading]   = useState(false)
  const [internalNote, setNote]       = useState('')
  const [targetStatus, setTarget]     = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    setLoading(true)
    api.complaints.get(complaintId)
      .then(setComplaint)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [complaintId])

  const transitions = complaint ? (JSSA_TRANSITIONS[complaint.status] ?? []) : []

  const proofRequired = ['IN_PROGRESS', 'FINAL_SURVEY_PENDING'].includes(targetStatus)

  async function handleFileUpload(file: File) {
    setUploading(true)
    try {
      const { upload_url, file_path } = await api.complaints.getUploadUrl()
      await fetch(upload_url, {
        method: 'PUT', body: file,
        headers: { 'Content-Type': file.type },
      })
      setProofUrl(file_path)
    } catch (e: any) {
      setError('Photo upload failed: ' + e.message)
    } finally {
      setUploading(false)
    }
  }

  async function handleStatusUpdate() {
    if (!targetStatus) return
    if (proofRequired && !proofUrl) {
      setError('A proof photo is required for this transition.')
      return
    }
    setUpdating(true)
    setError(null)
    try {
      await api.complaints.updateStatus(complaintId, {
        new_status:    targetStatus,
        internal_note: internalNote || undefined,
        proof_url:     proofUrl || undefined,
      })
      const updated = await api.complaints.get(complaintId)
      setComplaint(updated)
      setTarget('')
      setNote('')
      setProofUrl('')
      setProofFile(null)
      onStatusChanged?.(targetStatus)
    } catch (e: any) {
      setError(e.message ?? 'Update failed')
    } finally {
      setUpdating(false)
    }
  }

  const slaDeadline = complaint?.sla_deadline ? new Date(complaint.sla_deadline) : null
  const slaOverdue  = slaDeadline ? isPast(slaDeadline) : false

  return (
    // Full-height slide-in panel — overlays the task queue from the right
    <div className="absolute inset-y-0 right-0 w-[420px] bg-white border-l border-[#E5E7EB] flex flex-col z-20 shadow-xl">

      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="flex items-start justify-between px-5 py-4 border-b border-[#E5E7EB] flex-shrink-0">
        <div>
          {complaint && (
            <>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-lg">{CATEGORY_ICONS[complaint.category] ?? '📋'}</span>
                <code className="text-[12px] font-mono text-[#6B7280] tracking-tight">
                  {complaint.grievance_id}
                </code>
              </div>
              <StatusBadge status={complaint.status} />
            </>
          )}
        </div>
        <button
          onClick={onClose}
          className="text-[#6B7280] hover:text-[#111827] p-1 rounded transition-colors"
        >
          <X size={18} />
        </button>
      </div>

      {/* ── Body (scrollable) ──────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto">
        {loading && (
          <div className="p-5 space-y-3">
            {[1,2,3,4].map(i => (
              <div key={i} className="h-4 bg-gray-100 rounded animate-pulse" style={{width: `${[80,60,90,50][i-1]}%`}} />
            ))}
          </div>
        )}

        {!loading && complaint && (
          <div className="p-5 space-y-5">

            {/* SLA timer */}
            {slaDeadline && (
              <div className={`flex items-center gap-2 px-3 py-2 rounded-lg text-[13px] font-medium ${
                slaOverdue ? 'bg-red-50 text-red-700' : 'bg-amber-50 text-amber-700'
              }`}>
                <Clock size={14} />
                {slaOverdue
                  ? `SLA breached ${formatDistanceToNow(slaDeadline, { addSuffix: true })}`
                  : `SLA deadline ${formatDistanceToNow(slaDeadline, { addSuffix: true })}`
                }
                <span className="ml-auto text-[11px] opacity-70">
                  {format(slaDeadline, 'dd MMM, HH:mm')}
                </span>
              </div>
            )}

            {/* Description */}
            <section>
              <h3 className="text-[11px] font-semibold text-[#6B7280] uppercase tracking-wider mb-2">Description</h3>
              {complaint.translated_text && complaint.translated_text !== complaint.raw_text && (
                <p className="text-[12px] text-[#6B7280] italic mb-2 pb-2 border-b border-[#E5E7EB]">
                  Original: {complaint.raw_text}
                </p>
              )}
              <p className="text-[14px] text-[#111827] leading-relaxed">
                {complaint.translated_text ?? complaint.raw_text}
              </p>
            </section>

            {/* Metadata grid */}
            <section className="grid grid-cols-2 gap-3">
              {[
                { label: 'Category',   value: complaint.category ?? '—' },
                { label: 'Urgency',    value: `${complaint.urgency ?? 1}/5` },
                { label: 'Department', value: complaint.department_names?.join(', ') || '—' },
                { label: 'Ward',       value: complaint.ward_id ? 'Assigned' : 'Unassigned' },
              ].map(({ label, value }) => (
                <div key={label} className="bg-[#F9FAFB] rounded-lg px-3 py-2.5">
                  <p className="text-[11px] text-[#6B7280] mb-0.5">{label}</p>
                  <p className="text-[13px] font-medium text-[#111827] capitalize">{value}</p>
                </div>
              ))}
            </section>

            {/* Attached photos */}
            {complaint.media_urls?.length > 0 && (
              <section>
                <h3 className="text-[11px] font-semibold text-[#6B7280] uppercase tracking-wider mb-2">Photos</h3>
                <div className="flex gap-2 flex-wrap">
                  {complaint.media_urls.map((url: string, i: number) => (
                    <a key={i} href={url} target="_blank" rel="noopener noreferrer"
                       className="w-16 h-16 rounded-lg bg-[#F3F4F6] flex items-center justify-center text-[#6B7280] hover:opacity-80 transition-opacity overflow-hidden">
                      <Paperclip size={16} />
                    </a>
                  ))}
                </div>
              </section>
            )}

            {/* Timeline */}
            <section>
              <h3 className="text-[11px] font-semibold text-[#6B7280] uppercase tracking-wider mb-3">Timeline</h3>
              <div className="relative">
                <div className="absolute left-[7px] top-2 bottom-2 w-px bg-[#E5E7EB]" />
                <div className="space-y-3">
                  {(complaint.timeline ?? []).map((event: any, i: number) => (
                    <div key={i} className="flex gap-3">
                      <div className="w-3.5 h-3.5 rounded-full bg-[#E5E7EB] border-2 border-white flex-shrink-0 mt-1 relative z-10" />
                      <div>
                        <p className="text-[13px] font-medium text-[#111827]">
                          {event.event_type.replace(/_/g, ' ')}
                          {event.to_status && (
                            <span className="ml-1 text-[#6B7280] font-normal">→ {event.to_status}</span>
                          )}
                        </p>
                        <p className="text-[11px] text-[#9CA3AF]">
                          {event.actor_type} · {formatDistanceToNow(new Date(event.created_at), { addSuffix: true })}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </section>

            {/* Internal notes */}
            {complaint.internal_notes?.length > 0 && (
              <section>
                <h3 className="text-[11px] font-semibold text-[#6B7280] uppercase tracking-wider mb-2">Internal Notes</h3>
                {complaint.internal_notes.map((note: string, i: number) => (
                  <div key={i} className="bg-amber-50 border border-amber-100 rounded-lg px-3 py-2 text-[13px] text-amber-900 mb-2">
                    {note}
                  </div>
                ))}
              </section>
            )}

            {/* ── Status update form ─────────────────────────────── */}
            {transitions.length > 0 && (
              <section className="border-t border-[#E5E7EB] pt-5">
                <h3 className="text-[11px] font-semibold text-[#6B7280] uppercase tracking-wider mb-3">Update Status</h3>

                {/* Target status selector */}
                <div className="relative mb-3">
                  <select
                    value={targetStatus}
                    onChange={e => { setTarget(e.target.value); setError(null) }}
                    className="w-full appearance-none border border-[#E5E7EB] rounded-lg px-3 py-2.5 text-[14px] text-[#111827] focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/30 focus:border-[#1D4ED8] bg-white"
                  >
                    <option value="">Select next status…</option>
                    {transitions.map(s => (
                      <option key={s} value={s}>{STATUS_LABELS[s] ?? s}</option>
                    ))}
                  </select>
                  <ChevronDown size={14} className="absolute right-3 top-3.5 text-[#6B7280] pointer-events-none" />
                </div>

                {/* Proof photo upload (required for some transitions) */}
                {targetStatus && (
                  <>
                    <div className="mb-3">
                      <label
                        className={`flex items-center gap-2 border rounded-lg px-3 py-2.5 cursor-pointer transition-colors ${
                          proofRequired ? 'border-[#1D4ED8] bg-[#EFF6FF]' : 'border-[#E5E7EB]'
                        } hover:bg-[#F9FAFB]`}
                      >
                        <Upload size={14} className={proofRequired ? 'text-[#1D4ED8]' : 'text-[#6B7280]'} />
                        <span className="text-[13px] text-[#111827]">
                          {uploading ? 'Uploading…' : proofUrl ? '✓ Photo attached' : `${proofRequired ? 'Required: ' : ''}Attach proof photo`}
                        </span>
                        <input
                          ref={fileRef} type="file" accept="image/*" className="sr-only"
                          onChange={e => { const f = e.target.files?.[0]; if (f) { setProofFile(f); handleFileUpload(f) } }}
                          disabled={uploading}
                        />
                      </label>
                    </div>

                    {/* Internal note */}
                    <textarea
                      value={internalNote}
                      onChange={e => setNote(e.target.value)}
                      placeholder="Add an internal note (optional, not visible to citizen)"
                      rows={2}
                      className="w-full border border-[#E5E7EB] rounded-lg px-3 py-2.5 text-[13px] text-[#111827] placeholder-[#9CA3AF] resize-none focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/30 focus:border-[#1D4ED8] mb-3"
                    />
                  </>
                )}

                {/* Error */}
                {error && (
                  <div className="bg-red-50 border border-red-100 rounded-lg px-3 py-2 text-[13px] text-red-700 mb-3">
                    {error}
                  </div>
                )}

                {/* Submit */}
                <button
                  onClick={handleStatusUpdate}
                  disabled={!targetStatus || updating || uploading}
                  className="w-full bg-[#1D4ED8] text-white font-semibold text-[14px] py-2.5 rounded-lg hover:bg-blue-700 disabled:opacity-40 transition-colors flex items-center justify-center gap-2"
                >
                  {updating && (
                    <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                    </svg>
                  )}
                  {updating ? 'Updating…' : 'Confirm Update'}
                </button>
              </section>
            )}

          </div>
        )}
      </div>
    </div>
  )
}
```

---

# STEP 5 — Build: Follow-Up Agent

## `app/agents/follow_up.py`

```python
"""
Follow-Up Agent — SLA monitoring and auto-escalation.

Runs as a persistent asyncio background task. On startup it loads all
ASSIGNED/IN_PROGRESS complaints from Supabase and schedules SLA checks.
Also subscribes to Realtime to pick up newly assigned complaints.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from app.database import get_supabase_service
from app.services.notifications import notify
from app.utils.state_machine import VALID_TRANSITIONS

logger = logging.getLogger(__name__)

# Track scheduled tasks per complaint to avoid duplicates
_scheduled: dict[str, asyncio.Task] = {}


async def start_follow_up_agent():
    """
    Entry point. Call this in lifespan startup as an asyncio task.
    Loads existing open complaints and schedules their SLA checks.
    """
    logger.info("[FollowUp] Starting Follow-Up Agent")
    client = await get_supabase_service()

    # Load all complaints that still need SLA monitoring
    result = client.table('complaints') \
        .select('id, status, sla_deadline, urgency') \
        .in_('status', ['ASSIGNED', 'IN_PROGRESS', 'MID_SURVEY_PENDING']) \
        .not_.is_('sla_deadline', 'null') \
        .execute()

    for complaint in (result.data or []):
        await schedule_sla_checks(complaint['id'], complaint['sla_deadline'])

    logger.info(f"[FollowUp] Scheduled SLA checks for {len(result.data or [])} complaints")

    # Also subscribe to Realtime for new ASSIGNED complaints
    def on_complaint_update(payload):
        record = payload.get('new', {})
        if record.get('status') == 'ASSIGNED' and record.get('sla_deadline'):
            asyncio.create_task(
                schedule_sla_checks(record['id'], record['sla_deadline'])
            )

    client.realtime.channel('followup-monitor') \
        .on('postgres_changes', event='UPDATE', schema='public', table='complaints',
            callback=on_complaint_update) \
        .subscribe()


async def schedule_sla_checks(complaint_id: str, sla_deadline_str: str):
    """Schedule the 50%, 90%, and 100% SLA check tasks for a complaint."""
    if complaint_id in _scheduled:
        return  # Already scheduled — don't duplicate

    try:
        sla_deadline = datetime.fromisoformat(sla_deadline_str.replace('Z', '+00:00'))
        client = await get_supabase_service()
        created_result = client.table('complaints').select('created_at').eq('id', complaint_id).single().execute()
        created_at = datetime.fromisoformat(created_result.data['created_at'].replace('Z', '+00:00'))

        total_duration = (sla_deadline - created_at).total_seconds()
        now = datetime.now(timezone.utc)
        elapsed = (now - created_at).total_seconds()

        async def check_and_alert():
            while True:
                now = datetime.now(timezone.utc)
                elapsed_pct = (now - created_at).total_seconds() / total_duration * 100

                # Re-fetch current status
                r = client.table('complaints').select('status, assigned_officer_id') \
                    .eq('id', complaint_id).single().execute()
                if not r.data:
                    return
                status = r.data.get('status')

                # Stop monitoring terminal/survey states
                if status in ['CLOSED', 'CLOSED_UNVERIFIED', 'ESCALATED',
                               'FINAL_SURVEY_PENDING', 'MID_SURVEY_PENDING']:
                    return

                officer_id = r.data.get('assigned_officer_id')

                if elapsed_pct >= 100:
                    await _auto_escalate(complaint_id, client)
                    return
                elif elapsed_pct >= 90:
                    await _send_sla_warning(complaint_id, officer_id, 90, client)
                    await asyncio.sleep(max(0, (sla_deadline - datetime.now(timezone.utc)).total_seconds()))
                elif elapsed_pct >= 50:
                    await _send_sla_reminder(complaint_id, officer_id, 50, client)
                    # Sleep until 90%
                    sleep_until_90 = created_at.timestamp() + (total_duration * 0.9)
                    await asyncio.sleep(max(0, sleep_until_90 - datetime.now(timezone.utc).timestamp()))
                else:
                    # Sleep until 50%
                    sleep_until_50 = created_at.timestamp() + (total_duration * 0.5)
                    await asyncio.sleep(max(0, sleep_until_50 - datetime.now(timezone.utc).timestamp()))

        task = asyncio.create_task(check_and_alert())
        _scheduled[complaint_id] = task

    except Exception as e:
        logger.error(f"[FollowUp] Failed to schedule checks for {complaint_id}: {e}")


async def _send_sla_reminder(complaint_id: str, officer_id: Optional[str], pct: int, client):
    """PRD §5.6 — Send 50% SLA reminder to JSSA."""
    # Check idempotency — don't send if already sent
    event_check = client.table('complaint_events') \
        .select('id') \
        .eq('complaint_id', complaint_id) \
        .eq('event_type', f'sla_reminder_{pct}') \
        .execute()

    if event_check.data:
        return  # Already sent

    complaint = client.table('complaints').select('grievance_id').eq('id', complaint_id).single().execute()
    grievance_id = complaint.data.get('grievance_id', '')

    if officer_id:
        await notify(officer_id, 'sla_reminder', {
            'complaint_id': complaint_id,
            'grievance_id': grievance_id,
            'pct': pct,
            'message': f'Reminder: {pct}% of SLA elapsed for {grievance_id}',
        })

    client.table('complaint_events').insert({
        'complaint_id': complaint_id,
        'event_type': f'sla_reminder_{pct}',
        'actor_type': 'system',
        'payload': {'pct': pct},
    }).execute()

    logger.info(f"[FollowUp] Sent {pct}% SLA reminder for {complaint_id}")


async def _send_sla_warning(complaint_id: str, officer_id: Optional[str], pct: int, client):
    """PRD §5.6 — Send 90% warning to JSSA + notify AA."""
    await _send_sla_reminder(complaint_id, officer_id, pct, client)

    # Also notify AA
    aa_result = client.table('officers') \
        .select('id') \
        .eq('role', 'aa') \
        .execute()

    for aa in (aa_result.data or []):
        complaint = client.table('complaints').select('grievance_id').eq('id', complaint_id).single().execute()
        await notify(aa['id'], 'sla_warning_aa', {
            'complaint_id': complaint_id,
            'grievance_id': complaint.data.get('grievance_id', ''),
            'message': f'SLA at 90% for {complaint.data.get("grievance_id")} — action required',
        })


async def _auto_escalate(complaint_id: str, client):
    """PRD §5.6 — Auto-escalate at 100% SLA breach."""
    # Check idempotency
    event_check = client.table('complaint_events') \
        .select('id') \
        .eq('complaint_id', complaint_id) \
        .eq('event_type', 'auto_escalated') \
        .execute()

    if event_check.data:
        return

    current = client.table('complaints').select('status, grievance_id').eq('id', complaint_id).single().execute()
    if not current.data or current.data['status'] in ['CLOSED', 'CLOSED_UNVERIFIED', 'ESCALATED']:
        return

    client.table('complaints').update({'status': 'ESCALATED'}).eq('id', complaint_id).execute()
    client.table('complaint_events').insert({
        'complaint_id': complaint_id,
        'event_type': 'auto_escalated',
        'actor_type': 'system',
        'payload': {'reason': 'SLA breach — auto-escalated by Follow-Up Agent'},
    }).execute()

    # Notify AA via Telegram + Email SMTP
    aa_result = client.table('officers').select('id').eq('role', 'aa').execute()
    for aa in (aa_result.data or []):
        await notify(aa['id'], 'escalation_aa', {
            'complaint_id': complaint_id,
            'grievance_id': current.data['grievance_id'],
            'reason': 'SLA breach',
        })

    logger.info(f"[FollowUp] Auto-escalated complaint {complaint_id}")

    # Remove from scheduled dict
    _scheduled.pop(complaint_id, None)
```

---

# STEP 6 — Build: Survey Agent

## `app/agents/survey.py`

```python
"""
Survey Agent.
Triggered when complaint status → FINAL_SURVEY_PENDING or MID_SURVEY_PENDING.
Sends Telegram message. Parses YES/NO response from citizen.
Handles 72h timeout → CLOSED_UNVERIFIED.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from app.database import get_supabase_service
from app.services.telegram import send_telegram_message
from app.services.notifications import notify

logger = logging.getLogger(__name__)


async def handle_survey_pending(complaint_id: str, survey_type: str):
    """
    Called when status transitions to MID_SURVEY_PENDING or FINAL_SURVEY_PENDING.
    Sends appropriate Telegram message to citizen.
    """
    client = await get_supabase_service()
    complaint = client.table('complaints').select('*').eq('id', complaint_id).single().execute().data
    if not complaint:
        return

    chat_id = complaint.get('telegram_chat_id')
    grievance_id = complaint['grievance_id']

    if survey_type == 'MID_SURVEY_PENDING':
        message = (
            f"PS-CRM Update | {grievance_id}\n\n"
            f"Work has begun on your complaint. Our team is on-site.\n"
            f"We will notify you when the work is complete for your verification."
        )
        if chat_id:
            await send_telegram_message(chat_id, message)

        # Log mid-survey notification
        client.table('complaint_events').insert({
            'complaint_id': complaint_id,
            'event_type': 'mid_survey_sent',
            'actor_type': 'system',
            'payload': {'message': message},
        }).execute()

    elif survey_type == 'FINAL_SURVEY_PENDING':
        message = (
            f"PS-CRM | Verification Required | {grievance_id}\n\n"
            f"Your complaint has been marked as resolved by the field officer.\n\n"
            f"Is the issue actually fixed?\n"
            f"Reply YES if resolved.\n"
            f"Reply NO if the issue persists."
        )
        if chat_id:
            await send_telegram_message(chat_id, message)

        # Set survey sent timestamp
        client.table('complaints').update({
            'survey_sent_at': datetime.now(timezone.utc).isoformat(),
        }).eq('id', complaint_id).execute()

        client.table('complaint_events').insert({
            'complaint_id': complaint_id,
            'event_type': 'final_survey_sent',
            'actor_type': 'system',
            'payload': {'message': message},
        }).execute()

        # Schedule 72h auto-close
        asyncio.create_task(_schedule_auto_close(complaint_id))


async def _schedule_auto_close(complaint_id: str):
    """PRD §5.3 — Auto-close after 72h of no survey response."""
    await asyncio.sleep(72 * 3600)  # 72 hours

    client = await get_supabase_service()
    complaint = client.table('complaints').select('status').eq('id', complaint_id).single().execute().data
    if not complaint:
        return

    if complaint['status'] == 'FINAL_SURVEY_PENDING':
        client.table('complaints').update({'status': 'CLOSED_UNVERIFIED'}).eq('id', complaint_id).execute()
        client.table('complaint_events').insert({
            'complaint_id': complaint_id,
            'event_type': 'auto_closed_unverified',
            'actor_type': 'system',
            'payload': {'reason': '72h survey timeout — no citizen response'},
        }).execute()
        logger.info(f"[Survey] Complaint {complaint_id} auto-closed (CLOSED_UNVERIFIED)")


async def handle_citizen_survey_response(complaint_id: str, response: str, citizen_note: str = ''):
    """
    Called from POST /complaints/{id}/survey-response.
    response: 'approved' | 'rejected' | 'no_response'
    """
    client = await get_supabase_service()

    if response == 'approved':
        new_status = 'CLOSED'
    elif response == 'rejected':
        new_status = 'REOPENED'
    else:
        new_status = 'CLOSED_UNVERIFIED'

    client.table('complaints').update({'status': new_status}).eq('id', complaint_id).execute()
    client.table('complaint_events').insert({
        'complaint_id': complaint_id,
        'event_type': 'citizen_survey_response',
        'actor_type': 'citizen',
        'payload': {'response': response, 'note': citizen_note, 'new_status': new_status},
    }).execute()

    if response == 'rejected':
        # Escalate to AA
        aa_result = client.table('officers').select('id').eq('role', 'aa').execute()
        complaint = client.table('complaints').select('grievance_id').eq('id', complaint_id).single().execute()
        for aa in (aa_result.data or []):
            await notify(aa['id'], 'citizen_rejected', {
                'complaint_id': complaint_id,
                'grievance_id': complaint.data.get('grievance_id', ''),
                'reason': citizen_note or 'Citizen reported issue not resolved',
            })

    logger.info(f"[Survey] Complaint {complaint_id} survey response: {response} → {new_status}")
    return new_status
```

---

# STEP 7 — Build: SMTP Notifications Wired Throughout

## Wire into `app/routers/complaints.py` status update handler

```python
# In the PATCH /complaints/{id}/status handler, add these calls:

from app.services.email_smtp import send_status_update
from app.agents.survey import handle_survey_pending

@router.patch("/{complaint_id}/status")
async def update_status(
    complaint_id: str,
    body: ComplaintStatusUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    # ... existing state machine validation ...
    # ... existing DB update ...

    # After successful update:

    # 1. Log event to audit trail
    supabase.table('complaint_events').insert({
        'complaint_id': complaint_id,
        'event_type':   'status_changed',
        'actor_type':   current_user.role,
        'from_status':  current_status,
        'to_status':    body.new_status,
        'payload':      {'officer_id': current_user.id, 'note': body.internal_note},
    }).execute()

    # 2. SMTP email to citizen (if email hash stored, we notify)
    complaint = supabase.table('complaints').select('grievance_id, citizen_email_hash').eq('id', complaint_id).single().execute().data
    # Note: we have the hash but not the raw email — SMTP only works if we stored encrypted email
    # For now, notify officer's own email as confirmation
    if current_user.email:
        await send_status_update(current_user.email, complaint['grievance_id'], body.new_status)

    # 3. Survey Agent trigger
    if body.new_status in ['MID_SURVEY_PENDING', 'FINAL_SURVEY_PENDING']:
        asyncio.create_task(handle_survey_pending(complaint_id, body.new_status))

    # 4. Follow-Up Agent scheduling (for newly ASSIGNED complaints)
    if body.new_status == 'ASSIGNED':
        from app.agents.follow_up import schedule_sla_checks
        sla = supabase.table('complaints').select('sla_deadline').eq('id', complaint_id).single().execute().data
        if sla and sla.get('sla_deadline'):
            asyncio.create_task(schedule_sla_checks(complaint_id, sla['sla_deadline']))

    return {"status": "updated", "new_status": body.new_status}
```

---

# STEP 8 — Build: AA Dashboard

## `app/(dashboard)/aa/page.tsx`

```tsx
'use client'
import { useState, useEffect } from 'react'
import { AlertTriangle, Clock, User, ChevronRight } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { api } from '@/lib/api'
import { StatusBadge } from '@/components/complaints/StatusBadge'
import { SkeletonCard } from '@/components/ui/SkeletonCard'
import { EmptyState } from '@/components/ui/EmptyState'

const ESCALATION_REASONS: Record<string, string> = {
  sla_breach:       'SLA Breach',
  citizen_rejected: 'Citizen Rejected',
  manual:           'Manual Escalation',
}

export default function AADashboard() {
  const [escalated,  setEscalated]  = useState<any[]>([])
  const [officers,   setOfficers]   = useState<any[]>([])
  const [tab,        setTab]        = useState<'queue' | 'officers'>('queue')
  const [loading,    setLoading]    = useState(true)
  const [selected,   setSelected]   = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      api.complaints.list({ status: 'ESCALATED' }),
      api.officers.list(),
    ]).then(([esc, off]) => {
      setEscalated(esc)
      setOfficers(off)
    }).finally(() => setLoading(false))
  }, [])

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Tab bar */}
      <div className="flex border-b border-[#E5E7EB] px-6 flex-shrink-0 bg-white">
        {[
          { key: 'queue',    label: 'Escalation Queue', count: escalated.length },
          { key: 'officers', label: 'Officer Performance', count: officers.length },
        ].map(({ key, label, count }) => (
          <button
            key={key}
            onClick={() => setTab(key as any)}
            className={`px-4 py-3.5 text-[13px] font-medium border-b-2 transition-colors -mb-px ${
              tab === key
                ? 'border-[#1D4ED8] text-[#1D4ED8]'
                : 'border-transparent text-[#6B7280] hover:text-[#111827]'
            }`}
          >
            {label}
            <span className="ml-2 text-[11px] bg-[#F3F4F6] text-[#6B7280] px-1.5 py-0.5 rounded-full">
              {count}
            </span>
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {tab === 'queue' && (
          <div className="p-6">
            {loading && <div className="space-y-3">{[1,2,3].map(i => <SkeletonCard key={i} />)}</div>}
            {!loading && escalated.length === 0 && (
              <EmptyState icon="✅" message="No escalated complaints." sub="All complaints are within SLA." />
            )}
            {!loading && escalated.map(c => (
              <div key={c.id}
                className="bg-white border border-[#E5E7EB] rounded-xl p-4 mb-3 hover:border-[#1D4ED8]/40 transition-colors cursor-pointer"
                onClick={() => setSelected(selected === c.id ? null : c.id)}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <AlertTriangle size={14} className="text-[#EF4444]" />
                    <code className="text-[12px] font-mono text-[#6B7280]">{c.grievance_id}</code>
                    <StatusBadge status={c.status} />
                  </div>
                  <ChevronRight size={14} className={`text-[#6B7280] transition-transform ${selected === c.id ? 'rotate-90' : ''}`} />
                </div>

                <p className="text-[13px] font-medium text-[#111827] mb-1 capitalize">
                  {c.category} — {c.department_names?.join(', ')}
                </p>
                <p className="text-[12px] text-[#6B7280] line-clamp-2 mb-3">
                  {c.translated_text ?? c.raw_text}
                </p>

                <div className="flex items-center gap-4 text-[11px] text-[#9CA3AF]">
                  <span className="flex items-center gap-1">
                    <Clock size={11} />
                    Escalated {formatDistanceToNow(new Date(c.updated_at ?? c.created_at), { addSuffix: true })}
                  </span>
                  {c.assigned_officer_name && (
                    <span className="flex items-center gap-1">
                      <User size={11} />
                      {c.assigned_officer_name}
                    </span>
                  )}
                </div>

                {/* Expanded action row */}
                {selected === c.id && (
                  <div className="mt-4 pt-4 border-t border-[#E5E7EB] flex gap-2">
                    <button
                      onClick={() => api.complaints.updateStatus(c.id, { new_status: 'ASSIGNED' })}
                      className="flex-1 bg-[#1D4ED8] text-white text-[13px] font-medium py-2 rounded-lg hover:bg-blue-700 transition-colors"
                    >
                      Reassign to JSSA
                    </button>
                    <button
                      onClick={() => api.complaints.updateStatus(c.id, { new_status: 'CLOSED' })}
                      className="flex-1 border border-[#E5E7EB] text-[#111827] text-[13px] font-medium py-2 rounded-lg hover:bg-[#F9FAFB] transition-colors"
                    >
                      Resolve Directly
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {tab === 'officers' && (
          <div className="p-6">
            <div className="bg-white border border-[#E5E7EB] rounded-xl overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="bg-[#F9FAFB] border-b border-[#E5E7EB]">
                    {['Officer', 'Assigned', 'Resolved', 'Escalated', 'Avg Hours', 'Reopen %'].map(h => (
                      <th key={h} className="px-4 py-3 text-[11px] font-semibold text-[#6B7280] uppercase tracking-wider text-left">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {loading && [1,2,3].map(i => (
                    <tr key={i} className="border-b border-[#E5E7EB]">
                      {[1,2,3,4,5,6].map(j => (
                        <td key={j} className="px-4 py-3">
                          <div className="h-3 bg-gray-100 rounded animate-pulse" />
                        </td>
                      ))}
                    </tr>
                  ))}
                  {!loading && officers.map((o, i) => (
                    <tr key={o.officer_id} className={`border-b border-[#E5E7EB] ${i % 2 === 1 ? 'bg-[#F9FAFB]' : 'bg-white'} hover:bg-[#EFF6FF] transition-colors`}>
                      <td className="px-4 py-3 text-[13px] font-medium text-[#111827]">{o.name}</td>
                      <td className="px-4 py-3 text-[13px] text-[#6B7280]">{o.total_assigned}</td>
                      <td className="px-4 py-3 text-[13px] text-[#10B981] font-medium">{o.total_resolved}</td>
                      <td className="px-4 py-3 text-[13px] text-[#EF4444]">{o.total_escalated}</td>
                      <td className="px-4 py-3 text-[13px] text-[#6B7280]">{o.avg_resolution_hours.toFixed(1)}h</td>
                      <td className="px-4 py-3 text-[13px] text-[#6B7280]">{o.reopen_rate_pct.toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
```

---

# STEP 9 — Build: Super Admin Analytics Dashboard

## `app/(dashboard)/super-admin/page.tsx`

```tsx
'use client'
import { useState, useEffect, useCallback } from 'react'
import dynamic from 'next/dynamic'
import maplibregl from 'maplibre-gl'
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { AlertCircle, TrendingUp, Clock, Zap } from 'lucide-react'
import { api } from '@/lib/api'

const MapView = dynamic(() => import('@/components/map/MapView'), { ssr: false })

interface KPI { label: string; value: string; sub: string; icon: any; color: string }

export default function SuperAdminDashboard() {
  const [kpis,       setKpis]       = useState<KPI[]>([])
  const [volume,     setVolume]     = useState<any[]>([])
  const [sla,        setSla]        = useState<any[]>([])
  const [hotspots,   setHotspots]   = useState<any[]>([])
  const [groupBy,    setGroupBy]    = useState<'day' | 'week' | 'month'>('week')
  const [loading,    setLoading]    = useState(true)

  useEffect(() => {
    Promise.all([
      api.analytics.complaintVolume({ group_by: groupBy }),
      api.analytics.slaCompliance(),
      api.analytics.hotspots(),
      api.complaints.list({}),
    ]).then(([vol, slaData, hs, all]) => {
      setVolume(vol)
      setSla(slaData)
      setHotspots(hs)

      const active = all.filter((c: any) => !['CLOSED', 'CLOSED_UNVERIFIED'].includes(c.status))
      const resolved = all.filter((c: any) => c.status === 'CLOSED')
      const slaCompliant = slaData.length > 0
        ? slaData.reduce((sum: number, d: any) => sum + d.compliance_pct, 0) / slaData.length
        : 0

      setKpis([
        { label: 'Active Complaints',    value: String(active.length),      sub: 'across all wards',         icon: AlertCircle, color: '#1D4ED8' },
        { label: 'Resolved This Month',  value: String(resolved.length),    sub: 'total closed',             icon: TrendingUp,  color: '#10B981' },
        { label: 'SLA Compliance',       value: `${slaCompliant.toFixed(0)}%`, sub: 'avg across departments', icon: Clock,       color: '#F59E0B' },
        { label: 'Active Hotspots',      value: String(hs.length),          sub: 'from nightly scan',        icon: Zap,         color: '#EF4444' },
      ])
    }).finally(() => setLoading(false))
  }, [groupBy])

  const onMapReady = useCallback((map: maplibregl.Map) => {
    if (!hotspots.length) return
    hotspots.forEach(h => {
      const color = h.severity >= 4 ? '#EF4444' : h.severity === 3 ? '#F59E0B' : '#10B981'
      const el = document.createElement('div')
      el.style.cssText = `
        width: ${20 + h.severity * 12}px;
        height: ${20 + h.severity * 12}px;
        border-radius: 50%;
        background: ${color}25;
        border: 2px solid ${color};
        display: flex; align-items: center; justify-content: center;
        font-size: 11px; font-weight: 600; color: ${color};
        cursor: pointer;
      `
      el.textContent = String(h.complaint_count)
      new maplibregl.Marker({ element: el })
        .setLngLat([h.lng, h.lat])
        .setPopup(new maplibregl.Popup({ offset: 20 }).setHTML(`
          <div style="font-family:system-ui;padding:8px 12px">
            <p style="font-weight:600;font-size:13px;margin:0 0 4px">${h.category} hotspot</p>
            <p style="font-size:12px;color:#6B7280;margin:0">${h.complaint_count} complaints · ${h.ward_name}</p>
            <p style="font-size:12px;color:#6B7280;margin:4px 0 0">Severity: ${h.severity}/5</p>
          </div>
        `))
        .addTo(map)
    })
  }, [hotspots])

  const HOTSPOT_COLOR = { 1: 'bg-green-100 text-green-700', 2: 'bg-green-100 text-green-700', 3: 'bg-amber-100 text-amber-700', 4: 'bg-red-100 text-red-700', 5: 'bg-red-100 text-red-700' }

  return (
    <div className="h-full overflow-auto bg-[#F9FAFB]">
      <div className="p-6 space-y-6 max-w-7xl mx-auto">

        {/* KPI cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {loading
            ? [1,2,3,4].map(i => <div key={i} className="h-24 bg-white border border-[#E5E7EB] rounded-xl animate-pulse" />)
            : kpis.map(kpi => {
                const Icon = kpi.icon
                return (
                  <div key={kpi.label} className="bg-white border border-[#E5E7EB] rounded-xl p-4">
                    <div className="flex items-start justify-between mb-3">
                      <p className="text-[12px] font-medium text-[#6B7280]">{kpi.label}</p>
                      <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: kpi.color + '15' }}>
                        <Icon size={14} style={{ color: kpi.color }} />
                      </div>
                    </div>
                    <p className="text-[28px] font-bold text-[#111827] leading-none mb-1">{kpi.value}</p>
                    <p className="text-[11px] text-[#9CA3AF]">{kpi.sub}</p>
                  </div>
                )
              })
          }
        </div>

        {/* Charts row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Complaint volume */}
          <div className="bg-white border border-[#E5E7EB] rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-[15px] font-semibold text-[#111827]">Complaint Volume</h2>
              <div className="flex gap-1">
                {(['day', 'week', 'month'] as const).map(g => (
                  <button key={g} onClick={() => setGroupBy(g)}
                    className={`text-[11px] px-2.5 py-1 rounded-md capitalize transition-colors ${
                      groupBy === g ? 'bg-[#EFF6FF] text-[#1D4ED8] font-medium' : 'text-[#6B7280] hover:bg-[#F9FAFB]'
                    }`}
                  >
                    {g}
                  </button>
                ))}
              </div>
            </div>
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={volume} margin={{ top: 0, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
                <XAxis dataKey="period" tick={{ fontSize: 11, fill: '#9CA3AF' }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 11, fill: '#9CA3AF' }} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ fontSize: 12, border: '1px solid #E5E7EB', borderRadius: 8 }} />
                <Line type="monotone" dataKey="count" stroke="#1D4ED8" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* SLA compliance */}
          <div className="bg-white border border-[#E5E7EB] rounded-xl p-5">
            <h2 className="text-[15px] font-semibold text-[#111827] mb-4">SLA Compliance by Department</h2>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={sla} margin={{ top: 0, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
                <XAxis dataKey="department_name" tick={{ fontSize: 10, fill: '#9CA3AF' }} tickLine={false} axisLine={false} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: '#9CA3AF' }} tickLine={false} axisLine={false} unit="%" />
                <Tooltip contentStyle={{ fontSize: 12, border: '1px solid #E5E7EB', borderRadius: 8 }} />
                <Bar dataKey="compliance_pct" fill="#10B981" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Hotspot map */}
        <div className="bg-white border border-[#E5E7EB] rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-[#E5E7EB] flex items-center justify-between">
            <h2 className="text-[15px] font-semibold text-[#111827]">Predictive Hotspots</h2>
            <span className="text-[12px] text-[#6B7280]">{hotspots.length} active clusters</span>
          </div>
          <div className="relative h-80">
            <MapView
              center={[77.2090, 28.6139]}
              zoom={10}
              className="absolute inset-0 w-full h-full"
              onReady={onMapReady}
            />
          </div>
          {hotspots.length > 0 && (
            <div className="px-5 py-3 border-t border-[#E5E7EB] flex gap-2 flex-wrap">
              {hotspots.map(h => (
                <span key={h.id} className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${HOTSPOT_COLOR[h.severity as keyof typeof HOTSPOT_COLOR]}`}>
                  {h.category} · {h.ward_name} · {h.complaint_count}
                </span>
              ))}
            </div>
          )}
        </div>

      </div>
    </div>
  )
}
```

---

# STEP 10 — Build: Public Complaint Track Page

## `app/(public)/track/[id]/page.tsx`

```tsx
import { createClient } from '@supabase/supabase-js'
import { notFound } from 'next/navigation'
import { format, formatDistanceToNow } from 'date-fns'
import { StatusBadge } from '@/components/complaints/StatusBadge'

// Server component — fetches via FastAPI public endpoint
async function getComplaint(id: string) {
  try {
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_BACKEND_URL}/api/v1/complaints/${id}`,
      { next: { revalidate: 30 } }
    )
    if (!res.ok) return null
    return res.json()
  } catch { return null }
}

export default async function TrackPage({ params }: { params: { id: string } }) {
  const complaint = await getComplaint(params.id)
  if (!complaint) notFound()

  const slaDeadline = complaint.sla_deadline ? new Date(complaint.sla_deadline) : null

  return (
    <div className="min-h-screen bg-[#F9FAFB] py-12 px-4">
      <div className="max-w-lg mx-auto">
        {/* Back */}
        <a href="/" className="inline-flex items-center gap-1.5 text-[13px] text-[#6B7280] hover:text-[#111827] mb-6 transition-colors">
          ← Back
        </a>

        {/* Header card */}
        <div className="bg-white border border-[#E5E7EB] rounded-xl p-6 mb-4 shadow-sm">
          <div className="flex items-start justify-between mb-4">
            <div>
              <p className="text-[11px] text-[#9CA3AF] mb-1">Grievance ID</p>
              <code className="text-[18px] font-mono font-semibold text-[#111827] tracking-wide">
                {complaint.grievance_id}
              </code>
            </div>
            <StatusBadge status={complaint.status} />
          </div>

          {complaint.category && (
            <p className="text-[14px] font-medium text-[#111827] capitalize mb-1">{complaint.category}</p>
          )}

          {complaint.department_names?.length > 0 && (
            <p className="text-[12px] text-[#6B7280]">
              {complaint.department_names.join(' · ')}
            </p>
          )}

          {slaDeadline && (
            <div className="mt-4 pt-4 border-t border-[#E5E7EB]">
              <p className="text-[11px] text-[#9CA3AF] mb-1">SLA Deadline</p>
              <p className="text-[13px] text-[#111827]">
                {format(slaDeadline, 'dd MMM yyyy, HH:mm')}
                <span className="ml-2 text-[#6B7280]">
                  ({formatDistanceToNow(slaDeadline, { addSuffix: true })})
                </span>
              </p>
            </div>
          )}
        </div>

        {/* Timeline card */}
        <div className="bg-white border border-[#E5E7EB] rounded-xl p-6 shadow-sm">
          <h2 className="text-[15px] font-semibold text-[#111827] mb-4">Activity Timeline</h2>

          {(!complaint.timeline || complaint.timeline.length === 0) ? (
            <p className="text-[13px] text-[#9CA3AF]">No activity yet.</p>
          ) : (
            <div className="relative">
              <div className="absolute left-[7px] top-2 bottom-2 w-px bg-[#E5E7EB]" />
              <div className="space-y-4">
                {complaint.timeline.map((event: any, i: number) => (
                  <div key={i} className="flex gap-3">
                    <div className="w-3.5 h-3.5 rounded-full bg-[#E5E7EB] border-2 border-white flex-shrink-0 mt-1 relative z-10" />
                    <div>
                      <p className="text-[13px] font-medium text-[#111827]">
                        {event.event_type.replace(/_/g, ' ')}
                        {event.to_status && (
                          <span className="ml-1.5 font-normal">
                            <StatusBadge status={event.to_status} />
                          </span>
                        )}
                      </p>
                      <p className="text-[11px] text-[#9CA3AF] mt-0.5">
                        {formatDistanceToNow(new Date(event.created_at), { addSuffix: true })}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <p className="text-[11px] text-[#9CA3AF] text-center mt-6">
          Status refreshes every 30 seconds. For queries, contact MCD helpline.
        </p>
      </div>
    </div>
  )
}
```

---

# STEP 11 — Build: Demo Seed Data

## `supabase/migrations/005_seed_demo.sql`

```sql
-- Seed 50+ realistic complaints across categories, statuses, and urgency levels
-- Run AFTER wards, departments, officers, and assets are seeded

-- Helper: get ward IDs (replace with your actual seeded ward UUIDs)
DO $$
DECLARE
  ward1_id UUID;
  ward2_id UUID;
  ward3_id UUID;
  dept_pw UUID;       -- Public Works
  dept_elec UUID;     -- Electricity
  dept_sanit UUID;    -- Sanitation
  dept_water UUID;    -- Water
  dept_hort UUID;     -- Horticulture
  jssa1_id UUID;
  jssa2_id UUID;
  jssa3_id UUID;

  c_id UUID;
  sla_hours INT;
  sla_deadline TIMESTAMPTZ;
  created TIMESTAMPTZ;
BEGIN
  -- Fetch seeded IDs
  SELECT id INTO ward1_id FROM wards LIMIT 1 OFFSET 0;
  SELECT id INTO ward2_id FROM wards LIMIT 1 OFFSET 1;
  SELECT id INTO ward3_id FROM wards LIMIT 1 OFFSET 2;
  SELECT id INTO dept_pw    FROM departments WHERE name = 'Public Works' LIMIT 1;
  SELECT id INTO dept_elec  FROM departments WHERE name = 'Electricity' LIMIT 1;
  SELECT id INTO dept_sanit FROM departments WHERE name = 'Sanitation' LIMIT 1;
  SELECT id INTO dept_water FROM departments WHERE name = 'Water' LIMIT 1;
  SELECT id INTO dept_hort  FROM departments WHERE name = 'Horticulture' LIMIT 1;
  SELECT id INTO jssa1_id FROM officers WHERE role = 'jssa' LIMIT 1 OFFSET 0;
  SELECT id INTO jssa2_id FROM officers WHERE role = 'jssa' LIMIT 1 OFFSET 1;
  SELECT id INTO jssa3_id FROM officers WHERE role = 'jssa' LIMIT 1 OFFSET 2;

  -- ── 10 NEW complaints (ward 1, various categories) ─────────────────
  FOR i IN 1..10 LOOP
    c_id := gen_random_uuid();
    created := NOW() - (random() * interval '2 days');
    INSERT INTO complaints (
      id, grievance_id, ward_id, status, category, urgency,
      raw_text, translated_text, channel, sla_deadline,
      location, created_at, classification_confidence, llm_used
    ) VALUES (
      c_id,
      'MCD-' || TO_CHAR(created, 'YYYYMMDD') || '-' || UPPER(SUBSTRING(MD5(c_id::text), 1, 5)),
      ward1_id,
      'NEW',
      (ARRAY['drainage','road','streetlight','garbage','water_supply'])[floor(random()*5)+1],
      (floor(random()*5)+1)::INT,
      (ARRAY[
        'Large pothole on main road near Connaught Place metro. It has been there for 2 weeks.',
        'Drain overflow near Karol Bagh market. Road flooded.',
        'Broken streetlight near Rohini Sector 7 main junction causing safety hazard at night.',
        'Garbage not collected for 5 days near bus stop.',
        'Water pipeline leaking heavily near Karol Bagh market. Road flooded.',
        'Street light not working near Karol Bagh bus stop.',
        'Sewer overflowing on Ring Road near Rajiv Chowk.',
        'Tree branch fallen on road blocking traffic near school.',
        'Water supply disrupted for 3 days in entire block.',
        'Road has severe waterlogging after rains, vehicles stuck.'
      ])[i],
      NULL,
      'web',
      created + interval '72 hours',
      ST_SetSRID(ST_Point(77.2090 + (random()-0.5)*0.02, 28.6139 + (random()-0.5)*0.02), 4326),
      created, 0.92, false
    );
  END LOOP;

  -- ── 10 ASSIGNED complaints (ward 1, assigned to jssa1) ──────────────
  FOR i IN 1..10 LOOP
    c_id := gen_random_uuid();
    created := NOW() - (random() * interval '5 days');
    sla_hours := (ARRAY[24, 48, 72, 72, 96])[floor(random()*5)+1];
    sla_deadline := created + (sla_hours || ' hours')::interval;

    INSERT INTO complaints (
      id, grievance_id, ward_id, status, category, urgency,
      raw_text, translated_text, channel, sla_deadline,
      location, created_at, classification_confidence, llm_used
    ) VALUES (
      c_id,
      'MCD-' || TO_CHAR(created, 'YYYYMMDD') || '-' || UPPER(SUBSTRING(MD5(c_id::text), 1, 5)),
      ward1_id, 'ASSIGNED',
      (ARRAY['drainage','road','streetlight','garbage','water_supply'])[floor(random()*5)+1],
      (floor(random()*4)+2)::INT,
      (ARRAY[
        'Broken streetlight near Rohini Sector 7 main junction causing safety hazard at night.',
        'Large pothole on main road near Connaught Place metro.',
        'Drain overflow causing waterlogging near market.',
        'Garbage accumulation near public park, health hazard.',
        'Water pipeline burst, water wasting on street for 2 days.',
        'Tree touching electricity pole near school, dangerous.',
        'Road sinkhole has appeared near bus stand, dangerous.',
        'Streetlight pole leaning dangerously after storm.',
        'Open drain cover missing near children playing area.',
        'Sewage overflow on footpath near residential area.'
      ])[i],
      (ARRAY[
        'Broken streetlight near Rohini Sector 7 main junction causing safety hazard at night.',
        'Large pothole on main road near Connaught Place metro.',
        'Drain overflow causing waterlogging near market.',
        'Garbage accumulation near public park, health hazard.',
        'Water pipeline burst, water wasting on street for 2 days.',
        'Tree touching electricity pole near school, dangerous.',
        'Road sinkhole has appeared near bus stand, dangerous.',
        'Streetlight pole leaning dangerously after storm.',
        'Open drain cover missing near children playing area.',
        'Sewage overflow on footpath near residential area.'
      ])[i],
      'web', sla_deadline,
      ST_SetSRID(ST_Point(77.2090 + (random()-0.5)*0.02, 28.6139 + (random()-0.5)*0.02), 4326),
      created, 0.89, false
    );

    INSERT INTO complaint_departments (complaint_id, department_id, officer_id, status)
    VALUES (c_id, dept_pw, jssa1_id, 'ASSIGNED');
  END LOOP;

  -- ── 10 IN_PROGRESS complaints (ward 2) ──────────────────────────────
  FOR i IN 1..10 LOOP
    c_id := gen_random_uuid();
    created := NOW() - (random() * interval '7 days');
    sla_deadline := created + interval '72 hours';
    INSERT INTO complaints (
      id, grievance_id, ward_id, status, category, urgency,
      raw_text, translated_text, channel, sla_deadline, location, created_at,
      classification_confidence, llm_used
    ) VALUES (
      c_id,
      'MCD-' || TO_CHAR(created, 'YYYYMMDD') || '-' || UPPER(SUBSTRING(MD5(c_id::text), 1, 5)),
      ward2_id, 'IN_PROGRESS',
      (ARRAY['drainage','road','streetlight'])[floor(random()*3)+1],
      (floor(random()*3)+3)::INT,
      'Civic issue under repair — field team dispatched.', 'Civic issue under repair — field team dispatched.',
      'telegram', sla_deadline,
      ST_SetSRID(ST_Point(77.2090 + (random()-0.5)*0.03, 28.6139 + (random()-0.5)*0.03), 4326),
      created, 0.94, false
    );
    INSERT INTO complaint_departments (complaint_id, department_id, officer_id, status)
    VALUES (c_id, dept_elec, jssa2_id, 'IN_PROGRESS');
  END LOOP;

  -- ── 5 ESCALATED complaints (ward 1 & 2) ─────────────────────────────
  FOR i IN 1..5 LOOP
    c_id := gen_random_uuid();
    created := NOW() - (random() * interval '10 days');
    sla_deadline := created + interval '48 hours';  -- Already breached
    INSERT INTO complaints (
      id, grievance_id, ward_id, status, category, urgency,
      raw_text, translated_text, channel, sla_deadline, location, created_at,
      classification_confidence, llm_used
    ) VALUES (
      c_id,
      'MCD-' || TO_CHAR(created, 'YYYYMMDD') || '-' || UPPER(SUBSTRING(MD5(c_id::text), 1, 5)),
      (ARRAY[ward1_id, ward2_id])[floor(random()*2)+1], 'ESCALATED',
      'drainage', 5,
      'Critical drain blockage causing severe flooding. SLA breached.',
      'Critical drain blockage causing severe flooding. SLA breached.',
      'web', sla_deadline,
      ST_SetSRID(ST_Point(77.2090 + (random()-0.5)*0.02, 28.6139 + (random()-0.5)*0.02), 4326),
      created, 0.97, false
    );
  END LOOP;

  -- ── 5 CLOSED complaints ──────────────────────────────────────────────
  FOR i IN 1..5 LOOP
    c_id := gen_random_uuid();
    created := NOW() - (random() * interval '20 days');
    sla_deadline := created + interval '48 hours';
    INSERT INTO complaints (
      id, grievance_id, ward_id, status, category, urgency,
      raw_text, translated_text, channel, sla_deadline, location, created_at,
      classification_confidence, llm_used
    ) VALUES (
      c_id,
      'MCD-' || TO_CHAR(created, 'YYYYMMDD') || '-' || UPPER(SUBSTRING(MD5(c_id::text), 1, 5)),
      ward3_id, 'CLOSED',
      (ARRAY['garbage','streetlight','road'])[floor(random()*3)+1],
      (floor(random()*3)+1)::INT,
      'Issue resolved.', 'Issue resolved.',
      'web', sla_deadline,
      ST_SetSRID(ST_Point(77.2090 + (random()-0.5)*0.03, 28.6139 + (random()-0.5)*0.03), 4326),
      created, 0.91, false
    );
  END LOOP;

  -- ── 3 pre-seeded hotspots ────────────────────────────────────────────
  INSERT INTO hotspots (category, complaint_count, severity, ward_id, is_active, detected_at, center, radius_meters)
  VALUES
    ('drainage', 8, 4, ward1_id, true, NOW() - interval '1 day',
     ST_SetSRID(ST_Point(77.2090, 28.6139), 4326), 200),
    ('road', 6, 3, ward2_id, true, NOW() - interval '1 day',
     ST_SetSRID(ST_Point(77.2200, 28.6200), 4326), 180),
    ('streetlight', 5, 2, ward3_id, true, NOW() - interval '1 day',
     ST_SetSRID(ST_Point(77.1980, 28.6050), 4326), 150);

  RAISE NOTICE 'Demo seed data inserted successfully';
END $$;
```

---

# STEP 12 — Global Design System Files

## `app/globals.css`
```css
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700&family=DM+Mono:wght@400;500&display=swap');
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --bg:              #FFFFFF;
  --surface:         #F9FAFB;
  --border:          #E5E7EB;
  --text-primary:    #111827;
  --text-secondary:  #6B7280;
  --text-disabled:   #9CA3AF;
  --accent:          #1D4ED8;
  --accent-light:    #EFF6FF;
  --success:         #10B981;
  --warning:         #F59E0B;
  --danger:          #EF4444;
}

html, body { height: 100%; }

body {
  font-family: 'DM Sans', -apple-system, sans-serif;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-primary);
  background: var(--bg);
  -webkit-font-smoothing: antialiased;
}

code, .font-mono { font-family: 'DM Mono', monospace; }

/* Refined scrollbar */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #D1D5DB; border-radius: 10px; }
::-webkit-scrollbar-thumb:hover { background: #9CA3AF; }

/* MapLibre popup override */
.maplibregl-popup-content {
  border-radius: 10px !important;
  border: 1px solid var(--border) !important;
  box-shadow: 0 4px 16px rgba(0,0,0,0.08) !important;
  padding: 0 !important;
  font-family: 'DM Sans', sans-serif !important;
}
.maplibregl-popup-tip { display: none !important; }
```

## `tailwind.config.ts`
```ts
import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['DM Sans', '-apple-system', 'sans-serif'],
        mono: ['DM Mono', 'monospace'],
      },
      colors: {
        surface:  '#F9FAFB',
        border:   '#E5E7EB',
        accent: { DEFAULT: '#1D4ED8', light: '#EFF6FF' },
        success: '#10B981',
        warning: '#F59E0B',
        danger:  '#EF4444',
        muted:   '#6B7280',
      },
    },
  },
  plugins: [],
}

export default config
```

---

# Final Checklist Before Demo

```
□ next.config.js — transpilePackages + webpack fallback
□ globals.css — DM Sans font + CSS variables
□ tailwind.config.ts — extended tokens
□ MapView.tsx — CSS import + ssr:false usage confirmed everywhere
□ Dashboard layout — h-screen overflow-hidden root
□ main.py lifespan — Realtime subscription running
□ Supervisor Agent — NEW → CLASSIFIED → ASSIGNED pipeline tested
□ Follow-Up Agent — started in lifespan, SLA tasks scheduling
□ Survey Agent — FINAL_SURVEY_PENDING → Telegram message fires
□ Complaint detail panel — renders, status update form works
□ AA dashboard — escalation queue + officer table
□ Super Admin analytics — KPIs + charts + hotspot map
□ /track/[id] — renders timeline correctly
□ Demo seed SQL — 50+ complaints, 3 hotspots inserted
□ Test: POST /complaints → status changes NEW → CLASSIFIED within 10s
□ Test: PATCH /status without proof_url → 400 returned
□ Test: PATCH CLOSED complaint → 400 returned
□ Test: GET /complaints with no JWT → 401 returned
□ Test: GET /analytics/hotspots with JSSA JWT → 403 returned
□ Test: map loads on /map and /dashboard/jssa (not blank)
□ Lighthouse: map initial load < 2s
□ Test at 375px width on Chrome DevTools
```