# PS-CRM — UI Root Fix Plan

> Every fix here is a **root fix**, not a patch. No workarounds. Every component rebuilt correctly from scratch.
> Design reference: PRD §10 (Design System). Target aesthetic: Linear/Vercel dashboard quality.

---

## Part 1 — Root Cause Analysis (What's Actually Broken)

### Bug 1 — MapLibre map is completely blank (affects /map AND /dashboard/jssa)

**Symptom:** Screenshot 2 (public map) and Screenshot 3 (JSSA dashboard) both show a completely empty map area. Only the legend/filter bar is visible on the public map. The JSSA dashboard map panel is solid grey.

**Root causes (in order of likelihood):**

1. **MapLibre CSS not imported.** MapLibre requires `import 'maplibre-gl/dist/maplibre-gl.css'` at the top of the component. Without it, the map container renders but tiles never display. This is the #1 cause of blank maps.
   ```tsx
   // MISSING — must be in the map component or _app.tsx:
   import 'maplibre-gl/dist/maplibre-gl.css'
   ```

2. **Map container has no explicit height.** MapLibre requires the container div to have a defined pixel height. `height: 100%` on a flex child with no flex parent height = 0px height = blank.
   ```tsx
   // WRONG:
   <div ref={mapRef} className="flex-1" />
   // RIGHT:
   <div ref={mapRef} style={{ width: '100%', height: '600px' }} />
   // OR with Tailwind:
   <div ref={mapRef} className="w-full h-[600px]" />
   ```

3. **next.config.js missing transpilePackages.** Next.js 14 App Router requires MapLibre to be in the transpile list.
   ```js
   // next.config.js
   module.exports = {
     transpilePackages: ['maplibre-gl'],
   }
   ```

4. **Tile URL inaccessible.** OpenFreeMap tiles (`https://tiles.openfreemap.org/styles/liberty`) may be rate-limited or blocked. Switch to a more reliable tile source.

5. **`typeof window` check missing.** MapLibre cannot run server-side. Without a client-only check, Next.js SSR crashes the map init.
   ```tsx
   // Must use dynamic import with ssr: false:
   const MapComponent = dynamic(() => import('@/components/map/MapView'), { ssr: false })
   ```

**Fix:** See Part 3 — Complete component rewrites below.

---

### Bug 2 — JSSA Dashboard map panel is solid grey

**Root cause:** Same as Bug 1 (MapLibre init). Additionally, the 60/40 split layout has the map div with `w-[60%] h-full` but `h-full` resolves to the parent's height which may also be unconstrained.

**Additional issue:** The task queue sidebar (right panel) has no fixed height with overflow-y-auto, causing the whole layout to be taller than the viewport.

---

### Bug 3 — Task queue UI is too raw (Screenshot 3)

**Observed issues:**
- Status badge says "NEW" in tiny grey text — no colour coding
- Category shown as `road`, `water_supply` (raw DB enum values, not human-readable)
- Urgency dots are tiny and inconsistent (some red, some orange, some green — good start but needs refinement)
- SLA date shown as `3/15/2026` — needs relative time ("2h left", "Overdue")
- No hover states on complaint cards
- Complaint description text gets cut off with no ellipsis
- Font is system default, not Inter as specified in PRD §10.3
- No spacing rhythm — cards feel cramped

---

### Bug 4 — Public landing page (Screenshot 1) — functional but aesthetically weak

**Observed issues:**
- "PS" logo badge is a plain blue square — looks like a placeholder
- Description/Location/etc labels have inconsistent weight
- Map embedded in the form has no border radius
- "Choose File" button is the native browser button (unstyled)
- Submit button uses a generic blue — needs to match the accent system (#1D4ED8)
- The right column (Track Complaint + Officer Portal + Public Heatmap) feels like three disconnected boxes
- No visual hierarchy between the form and the side panel
- Missing loading state on form submission

---

## Part 2 — Design System to Implement

> Directly from PRD §10. These CSS variables must be defined globally.

```css
/* globals.css */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400&display=swap');

:root {
  /* Color tokens — PRD §10.2 */
  --bg:           #FFFFFF;
  --surface:      #F9FAFB;
  --border:       #E5E7EB;
  --text-primary: #111827;
  --text-secondary: #6B7280;
  --text-disabled: #9CA3AF;
  --accent:       #1D4ED8;
  --accent-light: #EFF6FF;
  --success:      #10B981;
  --warning:      #F59E0B;
  --danger:       #EF4444;
  --neutral-badge: #F3F4F6;

  /* Typography — PRD §10.3 */
  --font-sans: 'Inter', -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}

* { box-sizing: border-box; }
body {
  font-family: var(--font-sans);
  font-size: 14px;
  line-height: 22px;
  color: var(--text-primary);
  background: var(--bg);
  -webkit-font-smoothing: antialiased;
}
```

---

## Part 3 — Complete Component Fixes (Root Level)

### Fix 1 — `next.config.js` (must be done first)

```js
// next.config.js
/** @type {import('next').NextConfig} */
const nextConfig = {
  transpilePackages: ['maplibre-gl'],
  // Prevent MapLibre SSR crash
  webpack: (config) => {
    config.resolve.fallback = { fs: false, net: false, tls: false };
    return config;
  },
};

module.exports = nextConfig;
```

---

### Fix 2 — `app/globals.css` (global styles foundation)

```css
@import url('https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,400;0,14..32,500;0,14..32,600;0,14..32,700&family=JetBrains+Mono:wght@400&display=swap');
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --bg:             #FFFFFF;
  --surface:        #F9FAFB;
  --border:         #E5E7EB;
  --text-primary:   #111827;
  --text-secondary: #6B7280;
  --text-disabled:  #9CA3AF;
  --accent:         #1D4ED8;
  --accent-light:   #EFF6FF;
  --success:        #10B981;
  --warning:        #F59E0B;
  --danger:         #EF4444;
  --neutral-badge:  #F3F4F6;
  --font-sans:      'Inter', -apple-system, sans-serif;
  --font-mono:      'JetBrains Mono', monospace;
}

html, body { height: 100%; }
body {
  font-family: var(--font-sans);
  font-size: 14px;
  line-height: 22px;
  color: var(--text-primary);
  background: var(--bg);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* Consistent scrollbars */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
```

---

### Fix 3 — `tailwind.config.ts` (extend with design tokens)

```ts
import type { Config } from 'tailwindcss'

export default {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      colors: {
        surface:  '#F9FAFB',
        border:   '#E5E7EB',
        accent:   { DEFAULT: '#1D4ED8', light: '#EFF6FF' },
        success:  '#10B981',
        warning:  '#F59E0B',
        danger:   '#EF4444',
      },
      fontSize: {
        'display': ['30px', { lineHeight: '60px', fontWeight: '700' }],
        'h1':      ['24px', { lineHeight: '32px', fontWeight: '600' }],
        'h2':      ['18px', { lineHeight: '28px', fontWeight: '600' }],
        'h3':      ['16px', { lineHeight: '24px', fontWeight: '500' }],
        'body':    ['14px', { lineHeight: '22px', fontWeight: '400' }],
        'small':   ['12px', { lineHeight: '18px', fontWeight: '400' }],
        'mono':    ['13px', { lineHeight: '20px', fontWeight: '400' }],
      },
    },
  },
  plugins: [],
} satisfies Config
```

---

### Fix 4 — `components/map/MapView.tsx` (the correct MapLibre component)

**This file must ONLY be imported with `dynamic(() => import(...), { ssr: false })`**

```tsx
// components/map/MapView.tsx
'use client'

import { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'

// Reliable tile source with fallback
const TILE_STYLE = 'https://tiles.openfreemap.org/styles/liberty'
// Fallback: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json'

interface MapViewProps {
  center?:    [number, number]   // [lng, lat]
  zoom?:      number
  className?: string
  onMapReady?: (map: maplibregl.Map) => void
}

export default function MapView({
  center    = [77.2090, 28.6139],
  zoom      = 11,
  className = 'w-full h-full',
  onMapReady,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef       = useRef<maplibregl.Map | null>(null)

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const map = new maplibregl.Map({
      container:   containerRef.current,
      style:       TILE_STYLE,
      center,
      zoom,
      attributionControl: false,
    })

    map.addControl(
      new maplibregl.AttributionControl({ compact: true }),
      'bottom-right'
    )

    map.on('load', () => {
      onMapReady?.(map)
    })

    map.on('error', (e) => {
      console.warn('[MapLibre] Error:', e)
      // Fallback to Carto tiles if OpenFreeMap fails
      if (TILE_STYLE.includes('openfreemap')) {
        map.setStyle('https://basemaps.cartocdn.com/gl/positron-gl-style/style.json')
      }
    })

    mapRef.current = map

    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [])

  return <div ref={containerRef} className={className} />
}
```

**Usage in any page:**
```tsx
// ALWAYS import with ssr: false
import dynamic from 'next/dynamic'
const MapView = dynamic(() => import('@/components/map/MapView'), { ssr: false })

// Then use with explicit height:
<div className="w-full h-[600px]">
  <MapView onMapReady={(map) => { /* add layers here */ }} />
</div>
```

---

### Fix 5 — `components/complaints/StatusBadge.tsx` (PRD §10.5)

```tsx
// components/complaints/StatusBadge.tsx
const STATUS_CONFIG: Record<string, { bg: string; text: string; label: string; dot: string }> = {
  NEW:                  { bg: 'bg-gray-100',    text: 'text-gray-700',   dot: 'bg-gray-400',   label: 'New' },
  CLASSIFIED:           { bg: 'bg-blue-50',     text: 'text-blue-700',   dot: 'bg-blue-500',   label: 'Classified' },
  ASSIGNED:             { bg: 'bg-blue-100',    text: 'text-blue-800',   dot: 'bg-blue-600',   label: 'Assigned' },
  IN_PROGRESS:          { bg: 'bg-amber-50',    text: 'text-amber-800',  dot: 'bg-amber-500',  label: 'In Progress' },
  MID_SURVEY_PENDING:   { bg: 'bg-amber-50',    text: 'text-amber-700',  dot: 'bg-amber-400',  label: 'Mid Survey' },
  FINAL_SURVEY_PENDING: { bg: 'bg-purple-50',   text: 'text-purple-800', dot: 'bg-purple-500', label: 'Final Survey' },
  ESCALATED:            { bg: 'bg-red-50',      text: 'text-red-700',    dot: 'bg-red-500',    label: 'Escalated' },
  REOPENED:             { bg: 'bg-red-50',      text: 'text-red-700',    dot: 'bg-red-400',    label: 'Reopened' },
  CLOSED:               { bg: 'bg-green-50',    text: 'text-green-800',  dot: 'bg-green-500',  label: 'Closed' },
  CLOSED_UNVERIFIED:    { bg: 'bg-gray-100',    text: 'text-gray-500',   dot: 'bg-gray-400',   label: 'Unverified' },
}

export function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG['NEW']
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-semibold tracking-wide ${cfg.bg} ${cfg.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  )
}
```

---

### Fix 6 — `components/complaints/ComplaintCard.tsx` (JSSA task queue item)

```tsx
// components/complaints/ComplaintCard.tsx
import { StatusBadge } from './StatusBadge'
import { formatDistanceToNow, isPast } from 'date-fns'

const CATEGORY_ICONS: Record<string, string> = {
  drainage:     '💧',
  streetlight:  '💡',
  road:         '🛣️',
  tree:         '🌳',
  garbage:      '🗑️',
  water_supply: '🚿',
  other:        '📋',
}

const CATEGORY_LABELS: Record<string, string> = {
  drainage:     'Drainage',
  streetlight:  'Streetlight',
  road:         'Road',
  tree:         'Tree / Horticulture',
  garbage:      'Garbage',
  water_supply: 'Water Supply',
  other:        'Other',
}

const URGENCY_COLORS: Record<number, string> = {
  1: 'bg-gray-300',
  2: 'bg-gray-400',
  3: 'bg-amber-400',
  4: 'bg-orange-500',
  5: 'bg-red-500',
}

function SLAChip({ deadline }: { deadline: string | null }) {
  if (!deadline) return null
  const date    = new Date(deadline)
  const overdue = isPast(date)
  const label   = overdue
    ? `Overdue ${formatDistanceToNow(date, { addSuffix: true })}`
    : formatDistanceToNow(date, { addSuffix: true })

  return (
    <span className={`text-[11px] font-medium ${overdue ? 'text-red-600' : 'text-gray-500'}`}>
      SLA {label}
    </span>
  )
}

interface ComplaintCardProps {
  complaint:  any
  selected?:  boolean
  onClick:    () => void
}

export function ComplaintCard({ complaint, selected, onClick }: ComplaintCardProps) {
  const urgency = complaint.urgency ?? 1
  const dotColor = URGENCY_COLORS[urgency] ?? URGENCY_COLORS[1]

  return (
    <button
      onClick={onClick}
      className={`
        w-full text-left px-4 py-3.5 border-b border-[#E5E7EB]
        transition-colors duration-100
        ${selected
          ? 'bg-[#EFF6FF] border-l-2 border-l-[#1D4ED8]'
          : 'bg-white hover:bg-[#F9FAFB] border-l-2 border-l-transparent'
        }
      `}
    >
      {/* Top row: grievance ID + status badge */}
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full flex-shrink-0 ${dotColor}`} />
          <code className="text-[11px] font-mono text-gray-500 tracking-tight">
            {complaint.grievance_id}
          </code>
        </div>
        <StatusBadge status={complaint.status} />
      </div>

      {/* Category + description */}
      <div className="flex items-start gap-2 mb-2">
        <span className="text-sm flex-shrink-0 mt-0.5">
          {CATEGORY_ICONS[complaint.category] ?? '📋'}
        </span>
        <div>
          <p className="text-[13px] font-medium text-gray-900 leading-tight mb-0.5">
            {CATEGORY_LABELS[complaint.category] ?? complaint.category ?? 'Uncategorised'}
          </p>
          <p className="text-[12px] text-gray-500 leading-snug line-clamp-2">
            {complaint.translated_text ?? complaint.raw_text ?? '—'}
          </p>
        </div>
      </div>

      {/* Bottom row: urgency + SLA */}
      <div className="flex items-center justify-between">
        <span className="text-[11px] text-gray-500">
          Urgency {urgency}/5
        </span>
        <SLAChip deadline={complaint.sla_deadline} />
      </div>
    </button>
  )
}
```

---

### Fix 7 — `app/(dashboard)/jssa/page.tsx` — Complete root rewrite

```tsx
// app/(dashboard)/jssa/page.tsx
'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import dynamic from 'next/dynamic'
import maplibregl from 'maplibre-gl'
import { supabase } from '@/lib/supabase'
import { api } from '@/lib/api'
import { ComplaintCard } from '@/components/complaints/ComplaintCard'
import { ComplaintDetailPanel } from '@/components/complaints/ComplaintDetailPanel'
import { SkeletonCard } from '@/components/ui/SkeletonCard'
import { EmptyState } from '@/components/ui/EmptyState'
import { useUser } from '@/app/(dashboard)/layout'

// CRITICAL: ssr: false prevents MapLibre SSR crash
const MapView = dynamic(() => import('@/components/map/MapView'), { ssr: false })

const PIN_COLORS: Record<string, string> = {
  red:    '#EF4444',
  orange: '#F59E0B',
  green:  '#22C55E',
}

function getPinColor(urgency: number, slaDeadline: string | null): 'red' | 'orange' | 'green' {
  if (!slaDeadline) return urgency >= 4 ? 'red' : 'orange'
  const hoursLeft = (new Date(slaDeadline).getTime() - Date.now()) / 3600000
  if (urgency >= 4 || hoursLeft < 4)  return 'red'
  if (urgency >= 2 || hoursLeft < 12) return 'orange'
  return 'green'
}

export default function JSSADashboard() {
  const { wardId } = useUser()
  const mapRef     = useRef<maplibregl.Map | null>(null)
  const markersRef = useRef<Map<string, maplibregl.Marker>>(new Map())

  const [complaints, setComplaints] = useState<any[]>([])
  const [loading,    setLoading]    = useState(true)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [sortBy,     setSortBy]     = useState<'urgency' | 'sla'>('urgency')

  // ── Initial load ───────────────────────────────────────────────
  useEffect(() => {
    if (!wardId) return
    api.complaints.list({ ward_id: wardId })
      .then(setComplaints)
      .finally(() => setLoading(false))
  }, [wardId])

  // ── Supabase Realtime ──────────────────────────────────────────
  useEffect(() => {
    if (!wardId) return
    const channel = supabase
      .channel(`jssa-ward-${wardId}`)
      .on('postgres_changes', {
        event: '*', schema: 'public', table: 'complaints',
        filter: `ward_id=eq.${wardId}`,
      }, (payload: any) => {
        setComplaints(prev => {
          const idx = prev.findIndex(c => c.id === payload.new.id)
          if (idx >= 0) {
            const updated = [...prev]
            updated[idx] = payload.new
            return updated
          }
          return [payload.new, ...prev]
        })
        // Update map pin
        updatePin(payload.new)
      })
      .subscribe()
    return () => { supabase.removeChannel(channel) }
  }, [wardId])

  // ── Map pin management ─────────────────────────────────────────
  const updatePin = useCallback((complaint: any) => {
    if (!mapRef.current || !complaint.lat || !complaint.lng) return
    const map       = mapRef.current
    const color     = getPinColor(complaint.urgency, complaint.sla_deadline)
    const hexColor  = PIN_COLORS[color]
    const existing  = markersRef.current.get(complaint.id)

    if (existing) {
      // Update color — recreate the element
      existing.remove()
    }

    const el = document.createElement('div')
    el.style.cssText = `
      width: 28px; height: 28px; border-radius: 50%;
      background: ${hexColor}20; border: 2px solid ${hexColor};
      display: flex; align-items: center; justify-content: center;
      cursor: pointer; transition: transform 0.15s ease;
      font-size: 12px;
    `
    const icons: Record<string, string> = {
      drainage: '💧', streetlight: '💡', road: '🛣️', tree: '🌳', garbage: '🗑️', other: '📋'
    }
    el.textContent = icons[complaint.category] ?? '📋'
    el.addEventListener('mouseenter', () => { el.style.transform = 'scale(1.2)' })
    el.addEventListener('mouseleave', () => { el.style.transform = 'scale(1)' })
    el.addEventListener('click',      () => setSelectedId(complaint.id))

    const marker = new maplibregl.Marker({ element: el })
      .setLngLat([complaint.lng, complaint.lat])
      .addTo(map)

    markersRef.current.set(complaint.id, marker)
  }, [])

  const onMapReady = useCallback((map: maplibregl.Map) => {
    mapRef.current = map
    // Add ward boundaries if available
    api.wards.all().then((geojson: any) => {
      map.addSource('wards', { type: 'geojson', data: geojson })
      map.addLayer({
        id: 'ward-outline', type: 'line', source: 'wards',
        paint: { 'line-color': '#1D4ED8', 'line-width': 1.5, 'line-opacity': 0.4 },
      })
    }).catch(() => {})
    // Add all complaint pins
    complaints.forEach(updatePin)
  }, [complaints, updatePin])

  // Add pins when complaints load
  useEffect(() => {
    if (mapRef.current) complaints.forEach(updatePin)
  }, [complaints, updatePin])

  // ── Sorted complaints ──────────────────────────────────────────
  const sorted = [...complaints].sort((a, b) => {
    if (sortBy === 'urgency') return (b.urgency ?? 0) - (a.urgency ?? 0)
    if (!a.sla_deadline) return 1
    if (!b.sla_deadline) return -1
    return new Date(a.sla_deadline).getTime() - new Date(b.sla_deadline).getTime()
  })

  const selected = complaints.find(c => c.id === selectedId) ?? null

  return (
    <div className="flex h-full overflow-hidden">
      {/* ── Map panel (60%) ──────────────────────────────────────── */}
      <div className="flex-[6] h-full relative">
        {/* CRITICAL: explicit px height. h-full only works if parent is bounded */}
        <div className="absolute inset-0">
          <MapView
            center={[77.2090, 28.6139]}
            zoom={13}
            className="w-full h-full"
            onMapReady={onMapReady}
          />
        </div>

        {/* Map overlay — complaint count badge */}
        <div className="absolute top-4 left-4 bg-white border border-[#E5E7EB] rounded-lg px-3 py-2 shadow-sm z-10">
          <p className="text-[13px] font-medium text-gray-900">
            {complaints.length} active issues
          </p>
          <p className="text-[11px] text-gray-500">Ward {wardId?.slice(0, 8)}…</p>
        </div>
      </div>

      {/* ── Task queue panel (40%) ──────────────────────────────── */}
      <div className="flex-[4] h-full flex flex-col border-l border-[#E5E7EB] bg-white">
        {/* Panel header */}
        <div className="px-4 py-3 border-b border-[#E5E7EB] flex items-center justify-between flex-shrink-0">
          <div>
            <h2 className="text-[15px] font-semibold text-gray-900">Ward Task Queue</h2>
            <p className="text-[12px] text-gray-500">{complaints.length} active issues · live</p>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setSortBy('urgency')}
              className={`text-[12px] px-2.5 py-1 rounded-md transition-colors ${
                sortBy === 'urgency'
                  ? 'bg-[#EFF6FF] text-[#1D4ED8] font-medium'
                  : 'text-gray-500 hover:bg-gray-100'
              }`}
            >
              Urgency
            </button>
            <button
              onClick={() => setSortBy('sla')}
              className={`text-[12px] px-2.5 py-1 rounded-md transition-colors ${
                sortBy === 'sla'
                  ? 'bg-[#EFF6FF] text-[#1D4ED8] font-medium'
                  : 'text-gray-500 hover:bg-gray-100'
              }`}
            >
              SLA
            </button>
          </div>
        </div>

        {/* Complaint list */}
        <div className="flex-1 overflow-y-auto">
          {loading && Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}

          {!loading && sorted.length === 0 && (
            <EmptyState
              icon="📭"
              message="No active complaints in your ward."
              sub="New complaints will appear here in real-time."
            />
          )}

          {!loading && sorted.map(c => (
            <ComplaintCard
              key={c.id}
              complaint={c}
              selected={selectedId === c.id}
              onClick={() => setSelectedId(prev => prev === c.id ? null : c.id)}
            />
          ))}
        </div>
      </div>

      {/* ── Detail panel (slide-in) ──────────────────────────────── */}
      {selectedId && (
        <ComplaintDetailPanel
          complaintId={selectedId}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  )
}
```

---

### Fix 8 — `app/(public)/map/page.tsx` — Public map complete fix

```tsx
// app/(public)/map/page.tsx
'use client'

import { useState, useEffect, useCallback } from 'react'
import dynamic from 'next/dynamic'
import maplibregl from 'maplibre-gl'
import { api } from '@/lib/api'

// CRITICAL: ssr: false
const MapView = dynamic(() => import('@/components/map/MapView'), { ssr: false })

const CATEGORIES = ['All', 'Drainage', 'Roads', 'Streetlights', 'Garbage', 'Trees', 'Water']
const CAT_MAP: Record<string, string> = {
  'Drainage': 'drainage', 'Roads': 'road', 'Streetlights': 'streetlight',
  'Garbage': 'garbage', 'Trees': 'tree', 'Water': 'water_supply',
}
const DENSITY_STEPS = [
  { max: 5,   color: '#DBEAFE' },
  { max: 15,  color: '#93C5FD' },
  { max: 30,  color: '#3B82F6' },
  { max: 999, color: '#1D4ED8' },
]

export default function PublicMapPage() {
  const [selected,  setSelected]  = useState('All')
  const [mapReady,  setMapReady]  = useState(false)
  const [mapInst,   setMapInst]   = useState<maplibregl.Map | null>(null)
  const [loading,   setLoading]   = useState(true)

  const loadWardData = useCallback(async (map: maplibregl.Map, category?: string) => {
    setLoading(true)
    try {
      const [wardsGeoJSON, densityData] = await Promise.all([
        api.wards.all(),
        api.analytics.wardDensity(category),
      ])

      const densityMap: Record<string, number> = {}
      if (Array.isArray(densityData)) {
        densityData.forEach((d: any) => { densityMap[d.ward_id] = d.count ?? 0 })
      }

      const geoJSON = wardsGeoJSON as any
      geoJSON.features.forEach((f: any) => {
        f.properties.complaint_count = densityMap[f.properties.id] ?? 0
      })

      // Update or add source
      if (map.getSource('wards')) {
        (map.getSource('wards') as maplibregl.GeoJSONSource).setData(geoJSON)
      } else {
        map.addSource('wards', { type: 'geojson', data: geoJSON })

        map.addLayer({
          id:   'ward-fill',
          type: 'fill',
          source: 'wards',
          paint: {
            'fill-color': [
              'step', ['get', 'complaint_count'],
              '#F0F9FF',  5,  '#BFDBFE',
              15, '#60A5FA', 30, '#1D4ED8',
            ],
            'fill-opacity': 0.7,
          },
        })

        map.addLayer({
          id:   'ward-outline',
          type: 'line',
          source: 'wards',
          paint: { 'line-color': '#1D4ED8', 'line-width': 1, 'line-opacity': 0.5 },
        })

        // Hover popup
        const popup = new maplibregl.Popup({
          closeButton: false, closeOnClick: false,
          className: 'ward-popup',
        })

        map.on('mouseenter', 'ward-fill', (e: any) => {
          map.getCanvas().style.cursor = 'pointer'
          const props = e.features[0].properties
          popup.setLngLat(e.lngLat).setHTML(`
            <div style="font-family: Inter, sans-serif; padding: 8px 12px;">
              <p style="font-size:13px; font-weight:600; margin:0 0 2px">${props.name}</p>
              <p style="font-size:12px; color:#6B7280; margin:0">${props.complaint_count} active complaints</p>
            </div>
          `).addTo(map)
        })

        map.on('mouseleave', 'ward-fill', () => {
          map.getCanvas().style.cursor = ''
          popup.remove()
        })
      }
    } catch (err) {
      console.error('[PublicMap] Error loading ward data:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  const onMapReady = useCallback((map: maplibregl.Map) => {
    setMapInst(map)
    setMapReady(true)
    loadWardData(map)
  }, [loadWardData])

  // Reload when category filter changes
  useEffect(() => {
    if (!mapInst || !mapReady) return
    const cat = selected === 'All' ? undefined : CAT_MAP[selected]
    loadWardData(mapInst, cat)
  }, [selected, mapInst, mapReady, loadWardData])

  return (
    <div className="flex flex-col h-screen bg-white">
      {/* Filter bar */}
      <div className="flex items-center gap-1.5 px-4 py-2.5 border-b border-[#E5E7EB] flex-shrink-0">
        <span className="text-[12px] font-medium text-gray-500 mr-1">Filter:</span>
        {CATEGORIES.map(cat => (
          <button
            key={cat}
            onClick={() => setSelected(cat)}
            className={`px-3 py-1 rounded-full text-[12px] font-medium transition-colors ${
              selected === cat
                ? 'bg-[#1D4ED8] text-white'
                : 'text-gray-600 hover:bg-gray-100 border border-[#E5E7EB]'
            }`}
          >
            {cat}
          </button>
        ))}
        {loading && (
          <span className="ml-auto text-[12px] text-gray-400 animate-pulse">Loading…</span>
        )}
      </div>

      {/* Map — explicit height required */}
      <div className="flex-1 relative">
        <MapView
          center={[77.2090, 28.6139]}
          zoom={11}
          className="absolute inset-0 w-full h-full"
          onMapReady={onMapReady}
        />

        {/* Density legend — bottom left */}
        <div className="absolute bottom-8 left-4 bg-white rounded-lg border border-[#E5E7EB] px-3 py-2.5 shadow-sm z-10">
          <p className="text-[11px] font-semibold text-gray-600 mb-2">Complaint Density</p>
          <div className="flex items-center gap-1">
            {['#F0F9FF', '#BFDBFE', '#60A5FA', '#1D4ED8'].map((color, i) => (
              <div
                key={i}
                style={{ backgroundColor: color }}
                className="w-6 h-3 rounded-sm border border-black/5"
              />
            ))}
          </div>
          <div className="flex justify-between mt-1">
            <span className="text-[10px] text-gray-400">0</span>
            <span className="text-[10px] text-gray-400">Critical</span>
          </div>
        </div>
      </div>
    </div>
  )
}
```

---

### Fix 9 — `components/ui/EmptyState.tsx`

```tsx
export function EmptyState({
  icon = '📭',
  message,
  sub,
}: { icon?: string; message: string; sub?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
      <span className="text-4xl mb-3 opacity-50">{icon}</span>
      <p className="text-[14px] font-medium text-gray-700 mb-1">{message}</p>
      {sub && <p className="text-[12px] text-gray-400 max-w-[200px]">{sub}</p>}
    </div>
  )
}
```

---

### Fix 10 — `components/ui/SkeletonCard.tsx`

```tsx
export function SkeletonCard() {
  return (
    <div className="px-4 py-3.5 border-b border-[#E5E7EB] animate-pulse">
      <div className="flex items-center justify-between mb-2">
        <div className="h-2.5 bg-gray-200 rounded-full w-32" />
        <div className="h-4 bg-gray-200 rounded-full w-16" />
      </div>
      <div className="h-3 bg-gray-200 rounded-full w-3/4 mb-1.5" />
      <div className="h-3 bg-gray-100 rounded-full w-1/2" />
    </div>
  )
}
```

---

### Fix 11 — `app/(dashboard)/layout.tsx` — Sidebar fix

**Current issue:** Sidebar and content area height not properly bounded, causing map `h-full` to resolve to 0.

```tsx
// app/(dashboard)/layout.tsx
// The outer container MUST be h-screen with overflow-hidden
// The main content area MUST be overflow-hidden too

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  // ... auth check ...

  return (
    <div className="flex h-screen overflow-hidden bg-[#F9FAFB]">
      <Sidebar navItems={nav} role={role} user={session.user} />
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <TopBar user={session.user} />
        {/* CRITICAL: overflow-hidden here, not overflow-y-auto
            Each child page manages its own scroll */}
        <main className="flex-1 overflow-hidden">
          {children}
        </main>
      </div>
    </div>
  )
}
```

---

## Part 4 — Complete UI Redesign: Public Landing Page

The current landing page is functional but visually weak. Here is the complete redesign spec:

### `app/(public)/page.tsx` — Full rewrite

```tsx
'use client'

import { useState, useRef, useEffect } from 'react'
import dynamic from 'next/dynamic'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import maplibregl from 'maplibre-gl'

const MapView = dynamic(() => import('@/components/map/MapView'), { ssr: false })

export default function LandingPage() {
  const router = useRouter()
  const [step, setStep] = useState<'form' | 'success'>('form')
  const [submitting, setSubmitting] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [resultId, setResultId] = useState('')

  // Form fields
  const [description, setDescription] = useState('')
  const [email,       setEmail]       = useState('')
  const [pin,         setPin]         = useState<{ lat: number; lng: number } | null>(null)
  const [uploadedUrl, setUploadedUrl] = useState<string | null>(null)
  const [uploading,   setUploading]   = useState(false)

  // Track input
  const [trackId, setTrackId] = useState('')

  const mapRef = useRef<maplibregl.Map | null>(null)
  const markerRef = useRef<maplibregl.Marker | null>(null)

  const onMapReady = (map: maplibregl.Map) => {
    mapRef.current = map
    map.on('click', (e) => {
      const { lng, lat } = e.lngLat
      setPin({ lat, lng })

      // Move or create marker
      if (markerRef.current) {
        markerRef.current.setLngLat([lng, lat])
      } else {
        markerRef.current = new maplibregl.Marker({ color: '#1D4ED8' })
          .setLngLat([lng, lat])
          .addTo(map)
      }
    })
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const { upload_url, file_path } = await api.complaints.getUploadUrl()
      await fetch(upload_url, { method: 'PUT', body: file, headers: { 'Content-Type': file.type } })
      setUploadedUrl(file_path)
    } catch {
      setErrorMsg('Photo upload failed. You can still submit without it.')
    } finally {
      setUploading(false)
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!description.trim())      { setErrorMsg('Please describe the issue.'); return }
    if (!pin)                     { setErrorMsg('Please pin the location on the map.'); return }
    setErrorMsg(null)
    setSubmitting(true)
    try {
      const result = await api.complaints.submit({
        raw_text:       description,
        lat:            pin.lat,
        lng:            pin.lng,
        channel:        'web',
        citizen_email:  email || undefined,
        media_urls:     uploadedUrl ? [uploadedUrl] : [],
      })
      setResultId(result.grievance_id)
      setStep('success')
    } catch (err: any) {
      setErrorMsg(err.message ?? 'Something went wrong. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  if (step === 'success') {
    return (
      <div className="min-h-screen bg-[#F9FAFB] flex items-center justify-center p-4">
        <div className="bg-white border border-[#E5E7EB] rounded-xl p-8 max-w-md w-full text-center shadow-sm">
          <div className="w-12 h-12 bg-green-50 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-6 h-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 className="text-[20px] font-semibold text-gray-900 mb-2">Complaint Submitted</h2>
          <p className="text-[14px] text-gray-500 mb-6">
            Your complaint has been received and will be classified within minutes.
          </p>
          <div className="bg-[#F9FAFB] border border-[#E5E7EB] rounded-lg px-4 py-3 mb-6">
            <p className="text-[11px] text-gray-500 mb-1">Your Grievance ID</p>
            <code className="text-[18px] font-mono font-semibold text-[#1D4ED8] tracking-wide">
              {resultId}
            </code>
          </div>
          <p className="text-[12px] text-gray-400 mb-4">Save this ID to track your complaint status.</p>
          <button
            onClick={() => router.push(`/track/${resultId}`)}
            className="w-full bg-[#1D4ED8] text-white font-semibold text-[14px] py-2.5 rounded-lg hover:bg-blue-700 transition-colors"
          >
            Track My Complaint →
          </button>
          <button
            onClick={() => { setStep('form'); setDescription(''); setPin(null); setUploadedUrl(null) }}
            className="w-full mt-2 text-[13px] text-gray-500 py-2 hover:text-gray-700 transition-colors"
          >
            Submit another complaint
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#F9FAFB]">
      {/* Header */}
      <header className="bg-white border-b border-[#E5E7EB] px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 bg-[#1D4ED8] rounded-md flex items-center justify-center">
              <span className="text-white text-[11px] font-bold">PS</span>
            </div>
            <span className="font-semibold text-[15px] text-gray-900">PS-CRM</span>
            <span className="text-[12px] text-gray-400">Delhi MCD</span>
          </div>
          <div className="flex items-center gap-3">
            <a href="/map" className="text-[13px] text-gray-600 hover:text-gray-900 transition-colors">
              Ward Map
            </a>
            <a
              href="/login"
              className="text-[13px] font-medium text-[#1D4ED8] border border-[#1D4ED8] px-3 py-1.5 rounded-lg hover:bg-[#EFF6FF] transition-colors"
            >
              Officer Login
            </a>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-5xl mx-auto px-4 py-8 grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6">

        {/* ── Left: Complaint form ──────────────────────────── */}
        <div className="bg-white border border-[#E5E7EB] rounded-xl overflow-hidden shadow-sm">
          <div className="px-6 pt-6 pb-4 border-b border-[#E5E7EB]">
            <h1 className="text-[20px] font-semibold text-gray-900 mb-0.5">Submit a Complaint</h1>
            <p className="text-[13px] text-gray-500">Report civic issues directly to the MCD.</p>
          </div>

          <form onSubmit={handleSubmit} className="px-6 py-5 space-y-5">
            {/* Description */}
            <div>
              <label className="block text-[13px] font-medium text-gray-700 mb-1.5">
                Description <span className="text-red-500">*</span>
              </label>
              <textarea
                value={description}
                onChange={e => setDescription(e.target.value)}
                placeholder="Describe the issue (e.g., Broken streetlight near the park entirely out)"
                rows={3}
                className="w-full border border-[#E5E7EB] rounded-lg px-3 py-2.5 text-[14px] text-gray-900 placeholder-gray-400 resize-none focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/30 focus:border-[#1D4ED8] transition-colors"
              />
            </div>

            {/* Location map */}
            <div>
              <label className="block text-[13px] font-medium text-gray-700 mb-1.5">
                Location <span className="text-red-500">*</span>
              </label>
              {/* CRITICAL: explicit height */}
              <div className="w-full h-48 rounded-lg overflow-hidden border border-[#E5E7EB]">
                <MapView
                  center={[77.2090, 28.6139]}
                  zoom={11}
                  className="w-full h-full"
                  onMapReady={onMapReady}
                />
              </div>
              <p className="mt-1.5 text-[12px] text-gray-400">
                {pin
                  ? `📍 Pinned at ${pin.lat.toFixed(4)}, ${pin.lng.toFixed(4)}`
                  : 'Click on the map to drop a pin precisely where the issue is.'
                }
              </p>
            </div>

            {/* Proof photo */}
            <div>
              <label className="block text-[13px] font-medium text-gray-700 mb-1.5">
                Proof Photo <span className="text-[12px] font-normal text-gray-400">(Optional)</span>
              </label>
              <label className={`
                flex items-center gap-3 px-3 py-2.5 border rounded-lg cursor-pointer transition-colors
                ${uploading ? 'bg-gray-50 border-gray-200' : 'border-[#E5E7EB] hover:bg-gray-50'}
              `}>
                <span className="text-[13px] font-medium text-[#1D4ED8]">
                  {uploading ? 'Uploading…' : uploadedUrl ? '✓ Photo attached' : 'Choose File'}
                </span>
                <span className="text-[13px] text-gray-400">
                  {uploadedUrl ? uploadedUrl.split('/').pop() : 'No file chosen'}
                </span>
                <input
                  type="file" accept="image/*" className="sr-only"
                  onChange={handleFileUpload} disabled={uploading}
                />
              </label>
            </div>

            {/* Email */}
            <div>
              <label className="block text-[13px] font-medium text-gray-700 mb-1.5">
                Email for Receipt <span className="text-[12px] font-normal text-gray-400">(Optional)</span>
              </label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="citizen@example.com"
                className="w-full border border-[#E5E7EB] rounded-lg px-3 py-2.5 text-[14px] text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/30 focus:border-[#1D4ED8] transition-colors"
              />
            </div>

            {/* Error */}
            {errorMsg && (
              <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2.5">
                <p className="text-[13px] text-red-700">{errorMsg}</p>
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={submitting}
              className="w-full bg-[#1D4ED8] text-white font-semibold text-[14px] py-3 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
            >
              {submitting && (
                <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                </svg>
              )}
              {submitting ? 'Submitting…' : 'Submit Complaint'}
            </button>
          </form>
        </div>

        {/* ── Right column ─────────────────────────────────── */}
        <div className="space-y-4">
          {/* Track complaint */}
          <div className="bg-white border border-[#E5E7EB] rounded-xl p-5 shadow-sm">
            <h2 className="text-[15px] font-semibold text-gray-900 mb-1">Track Complaint</h2>
            <p className="text-[12px] text-gray-500 mb-3">
              Enter your Grievance ID to view the current status, timeline, and SLA details.
            </p>
            <div className="flex gap-2">
              <input
                type="text"
                value={trackId}
                onChange={e => setTrackId(e.target.value)}
                placeholder="MCD-20250315-XXXXX"
                onKeyDown={e => e.key === 'Enter' && trackId.trim() && router.push(`/track/${trackId.trim()}`)}
                className="flex-1 border border-[#E5E7EB] rounded-lg px-3 py-2 text-[13px] font-mono focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/30 focus:border-[#1D4ED8] transition-colors"
              />
              <button
                onClick={() => trackId.trim() && router.push(`/track/${trackId.trim()}`)}
                disabled={!trackId.trim()}
                className="bg-gray-900 text-white text-[13px] font-medium px-4 rounded-lg hover:bg-gray-700 disabled:opacity-40 transition-colors"
              >
                Go
              </button>
            </div>
          </div>

          {/* Officer portal */}
          <div className="bg-white border border-[#E5E7EB] rounded-xl p-5 shadow-sm">
            <h2 className="text-[14px] font-semibold text-[#1D4ED8] mb-1">Officer Portal</h2>
            <p className="text-[12px] text-gray-500 mb-3">
              Are you an MCD official or registered contractor? Log in to your dashboard to manage complaints.
            </p>
            <a
              href="/login"
              className="block w-full text-center border border-[#E5E7EB] text-[13px] font-medium text-gray-700 py-2.5 rounded-lg hover:bg-gray-50 transition-colors"
            >
              Go to Login
            </a>
          </div>

          {/* Public heatmap */}
          <div className="bg-white border border-[#E5E7EB] rounded-xl p-5 shadow-sm">
            <h2 className="text-[14px] font-semibold text-[#1D4ED8] mb-1">Public Heatmap</h2>
            <p className="text-[12px] text-gray-500 mb-3">
              View the live public map showing complaint density across all wards.
            </p>
            <a
              href="/map"
              className="block w-full text-center border border-[#E5E7EB] text-[13px] font-medium text-gray-700 py-2.5 rounded-lg hover:bg-gray-50 transition-colors"
            >
              View Ward Map
            </a>
          </div>
        </div>
      </main>
    </div>
  )
}
```

---

## Part 5 — Implementation Order

Do these in exact order. Each step builds on the previous.

```
Step 1: next.config.js — add transpilePackages + webpack fallback
Step 2: globals.css   — add Inter font import + CSS variables
Step 3: tailwind.config.ts — add design tokens
Step 4: components/map/MapView.tsx — correct MapLibre component with ssr:false
Step 5: app/(dashboard)/layout.tsx — fix h-screen + overflow-hidden
Step 6: components/complaints/StatusBadge.tsx — colour-coded badges
Step 7: components/complaints/ComplaintCard.tsx — polished card component
Step 8: components/ui/EmptyState.tsx + SkeletonCard.tsx
Step 9: app/(public)/map/page.tsx — public map complete rewrite
Step 10: app/(dashboard)/jssa/page.tsx — JSSA dashboard complete rewrite
Step 11: app/(public)/page.tsx — landing page complete rewrite
Step 12: Test all 3 pages: landing, /map, /dashboard/jssa
         Verify: MapLibre tiles load, pins appear, task queue styled correctly
```

---

## Part 6 — Features Still to Build (Not Just UI Fixes)

These are missing features (from Feature Verification doc) that need full development:

| Priority | Feature | Files to Create/Modify |
|----------|---------|------------------------|
| P0 | Complaint detail panel (slide-in Sheet) | `components/complaints/ComplaintDetailPanel.tsx` |
| P0 | Status update form inside detail panel | Same file |
| P0 | Proof photo upload in detail panel | Same file |
| P1 | AA dashboard — escalation queue + officer table | `app/(dashboard)/aa/page.tsx` |
| P1 | Super Admin analytics page | `app/(dashboard)/super-admin/page.tsx` |
| P1 | Complaint track page | `app/(public)/track/[id]/page.tsx` |
| P2 | FAA dashboard — escalation + tender form | `app/(dashboard)/faa/page.tsx` |
| P2 | Contractor portal | `app/(dashboard)/contractor/page.tsx` |
| P2 | Super Admin contractor scorecard sub-page | `app/(dashboard)/super-admin/contractors/page.tsx` |
| P3 | Human review queue (backend + frontend) | New endpoint + Super Admin sub-page |
| P3 | Mobile responsive adjustments (375px) | All dashboard pages |