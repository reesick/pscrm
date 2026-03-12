# PS-CRM — Frontend File Split (10 Files)

> **Stack:** Next.js 14 (App Router) · TypeScript · Tailwind CSS · shadcn/ui · MapLibre GL JS · Recharts · Supabase Auth
> **Notification change:** Phone OTP removed. Citizens optionally provide email for receipts. Telegram is the primary citizen notification channel (read-only from frontend's perspective — bot handles it on the backend).

---

## How the Frontend Is Structured

Before diving into the files, here is how the whole frontend hangs together and how it communicates with the backend.

### Request / Data Flow

```
Browser
  │
  ├── Public routes (no auth)
  │     ├── /                  → Landing page — complaint form + status lookup
  │     ├── /track/[id]        → Complaint status tracker (polling or Realtime)
  │     └── /map               → Ward heatmap (no login)
  │
  └── Dashboard routes (JWT required)
        ├── /dashboard/jssa        → Map + task list (Supabase Realtime live updates)
        ├── /dashboard/aa          → Escalation queue + officer stats
        ├── /dashboard/faa         → FAA escalation + tender/work order flow
        ├── /dashboard/super-admin → Analytics KPIs + hotspot map + contractor scorecard
        └── /dashboard/contractor  → Task portal + proof photo upload
```

### Communication Patterns

- **Frontend → FastAPI Backend:** All data mutations (submit complaint, update status, deactivate contractor) go through the FastAPI backend via `lib/api.ts`. The API client attaches the Supabase JWT as a Bearer token automatically for authenticated calls.
- **Frontend → Supabase (direct):** Read-only Realtime subscriptions bypass FastAPI for speed. Dashboard map pins update in real-time when agents write status changes to Supabase, without going through the API. Auth (login/logout) also goes directly to Supabase Auth.
- **Auth Flow:** User logs in via Supabase Auth (email + password). Supabase returns a JWT with a custom `role` claim (`jssa`, `aa`, `faa`, `super_admin`, `contractor`). `middleware.ts` reads this role on every request to `/dashboard/*` and redirects to login if no valid session.
- **Role-based rendering:** The sidebar nav, available actions, and data scope all depend on the role in the JWT. Role is extracted once from the Supabase session and passed down via React context.
- **MapLibre + Supabase Realtime:** The JSSA map subscribes to `complaints` table changes for their ward. When a new complaint is inserted or a status changes, the Realtime event updates the map pin state in React without a page reload.
- **File uploads:** Proof photos and citizen media go directly to Supabase Storage from the browser using a pre-signed URL. The FastAPI backend provides the pre-signed URL via `POST /complaints/upload-url`, but the file bytes never pass through FastAPI.

---

## File 1 — `middleware.ts` + `lib/supabase.ts` + `lib/api.ts`

**Role:** Auth protection for all dashboard routes, Supabase client factory, and the typed FastAPI client. Three small but critical infrastructure files bundled together.

### `middleware.ts`

```typescript
import { createMiddlewareClient } from "@supabase/auth-helpers-nextjs";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export async function middleware(req: NextRequest) {
  const res  = NextResponse.next();
  const supabase = createMiddlewareClient({ req, res });

  // Refresh session if expired (Supabase handles token rotation)
  const { data: { session } } = await supabase.auth.getSession();

  const isProtected = req.nextUrl.pathname.startsWith("/dashboard");
  const isAuthPage  = req.nextUrl.pathname === "/login";

  // Not logged in → redirect to login
  if (isProtected && !session) {
    return NextResponse.redirect(new URL("/login", req.url));
  }

  // Logged in + on login page → redirect to correct dashboard
  if (isAuthPage && session) {
    const role = session.user.user_metadata?.role ?? "jssa";
    return NextResponse.redirect(new URL(`/dashboard/${role}`, req.url));
  }

  // Role-gating: prevent JSSA from accessing /dashboard/super-admin etc.
  if (isProtected && session) {
    const role = session.user.user_metadata?.role;
    const path = req.nextUrl.pathname;

    const ROLE_PATHS: Record<string, string> = {
      jssa:        "/dashboard/jssa",
      aa:          "/dashboard/aa",
      faa:         "/dashboard/faa",
      super_admin: "/dashboard/super-admin",
      contractor:  "/dashboard/contractor",
    };

    const allowedBase = ROLE_PATHS[role];
    if (allowedBase && !path.startsWith(allowedBase) && path !== "/dashboard") {
      return NextResponse.redirect(new URL(allowedBase, req.url));
    }
  }

  return res;
}

export const config = {
  matcher: ["/dashboard/:path*", "/login"],
};
```

### `lib/supabase.ts`

```typescript
import { createClientComponentClient, createServerComponentClient }
  from "@supabase/auth-helpers-nextjs";
import { cookies } from "next/headers";
import type { Database } from "@/types/supabase";  // generated from Supabase CLI

// Client-side (browser): used in React components for Realtime subscriptions + Auth
export const supabase = createClientComponentClient<Database>();

// Server-side (Server Components / Route Handlers): reads cookies for JWT
export function createServerSupabase() {
  return createServerComponentClient<Database>({ cookies });
}
```

### `lib/api.ts`

```typescript
// Typed FastAPI client
// All mutations go through FastAPI (not direct Supabase writes from frontend)
// Reads can come from FastAPI or direct Supabase for Realtime

const BASE = process.env.NEXT_PUBLIC_BACKEND_URL;

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const { data: { session } } = await supabase.auth.getSession();
  const token = session?.access_token;

  const res = await fetch(`${BASE}/api/v1${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { "Authorization": `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: "Unknown error" }));
    throw new Error(err.error ?? `HTTP ${res.status}`);
  }

  return res.json();
}

// Typed endpoint helpers
export const api = {
  complaints: {
    submit:       (body: ComplaintCreateRequest)         => apiFetch("/complaints", { method: "POST", body: JSON.stringify(body) }),
    get:          (id: string)                           => apiFetch(`/complaints/${id}`),
    list:         (params?: ComplaintListParams)         => apiFetch(`/complaints?${toQS(params)}`),
    updateStatus: (id: string, body: StatusUpdateBody)  => apiFetch(`/complaints/${id}/status`, { method: "PATCH", body: JSON.stringify(body) }),
    getUploadUrl: ()                                     => apiFetch("/complaints/upload-url", { method: "POST" }),
  },
  officers: {
    stats: (id: string) => apiFetch(`/officers/${id}/stats`),
  },
  contractors: {
    scorecard:    (id: string)                      => apiFetch(`/contractors/${id}/scorecard`),
    updateStatus: (id: string, body: { is_active: boolean; reason: string }) =>
                  apiFetch(`/contractors/${id}/status`, { method: "PATCH", body: JSON.stringify(body) }),
  },
  analytics: {
    hotspots:        ()                          => apiFetch("/analytics/hotspots"),
    slaCompliance:   (params?: DateRangeParams)  => apiFetch(`/analytics/sla-compliance?${toQS(params)}`),
    complaintVolume: (params?: VolumeParams)     => apiFetch(`/analytics/complaint-volume?${toQS(params)}`),
    wardDensity:     (category?: string)         => apiFetch(`/analytics/ward-density${category ? `?category=${category}` : ""}`),
  },
  wards: {
    all: () => apiFetch("/wards"),
  },
};

function toQS(params?: Record<string, unknown>): string {
  if (!params) return "";
  return new URLSearchParams(
    Object.entries(params).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])
  ).toString();
}
```

---

## File 2 — `app/(public)/page.tsx`

**Role:** Public landing page. Two sections: a complaint submission form for new complaints, and a grievance ID lookup for existing ones. No login required for either.

### Layout

```
┌─────────────────────────────────────┐
│  PS-CRM Logo + tagline              │
│                                     │
│  ┌──────── Submit a Complaint ────┐ │
│  │  Description textarea          │ │
│  │  Location: [map with pin]      │ │
│  │  Language selector             │ │
│  │  Photo upload area             │ │
│  │  [optional] Email for receipt  │ │
│  │  [Submit →]                    │ │
│  └────────────────────────────────┘ │
│                                     │
│  ┌──────── Track Complaint ───────┐ │
│  │  [ MCD-20250315-A7K2M ]  [Go] │ │
│  └────────────────────────────────┘ │
└─────────────────────────────────────┘
```

### Key implementation notes

```typescript
"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { useRouter } from "next/navigation";
import maplibregl from "maplibre-gl";

export default function LandingPage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [grievanceId, setGrievanceId] = useState("");
  const [mapPin, setMapPin] = useState<{ lat: number; lng: number } | null>(null);

  // Complaint form submit
  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    try {
      const result = await api.complaints.submit({
        raw_text:   formData.description,
        lat:        mapPin!.lat,
        lng:        mapPin!.lng,
        media_urls: uploadedUrls,
        channel:    "web",
        citizen_email: formData.email || undefined,
      });
      // Show success state with grievance ID
      // Citizen can copy ID and use the tracker
      setSuccess(result.grievance_id);
    } catch (err) {
      setError(String(err));
    } finally {
      setSubmitting(false);
    }
  }

  // Grievance ID tracker redirect
  function handleTrack() {
    if (grievanceId.trim()) router.push(`/track/${grievanceId.trim()}`);
  }

  return (
    // ... form JSX
    // MapLibre map in a <div ref={mapRef}> with draggable pin
    // File upload using Supabase Storage pre-signed URL from api.complaints.getUploadUrl()
    // Language selector: Hindi | English | Marathi | Tamil | Telugu | Kannada
  );
}
```

### Photo upload flow

```typescript
// 1. Call FastAPI for pre-signed Supabase Storage URL
const { upload_url, file_path } = await api.complaints.getUploadUrl();

// 2. PUT file bytes directly to Supabase Storage (bypasses FastAPI entirely)
await fetch(upload_url, { method: "PUT", body: file, headers: { "Content-Type": file.type } });

// 3. Store file_path in uploadedUrls[] — included in complaint submit body
setUploadedUrls(prev => [...prev, file_path]);
```

---

## File 3 — `app/(public)/track/[id]/page.tsx`

**Role:** Public complaint status page. Anyone with a grievance ID can see the current status, department, officer name (not contact), and the full event timeline. No login required.

### Layout

```
┌────────────────────────────────────────┐
│  ← Back to search                      │
│                                        │
│  MCD-20250315-A7K2M                    │
│  Category: Drainage  [IN PROGRESS 🟡]  │
│  Department: Public Works              │
│  SLA: 12 hours remaining               │
│                                        │
│  ──── Timeline ────────────────────    │
│  ● Complaint received (Mar 15, 10:00)  │
│  ● Classified: Drainage (10:01)        │
│  ● Assigned to JSSA Ward 14 (10:05)    │
│  ● Work begun (Mar 16, 09:00)          │
└────────────────────────────────────────┘
```

### Implementation

```typescript
// This is a Server Component — data is fetched server-side for SEO + fast initial render
import { api } from "@/lib/api";
import { StatusBadge, Timeline } from "@/components/complaints";

export default async function TrackPage({ params }: { params: { id: string } }) {
  const complaint = await api.complaints.get(params.id).catch(() => null);

  if (!complaint) return <NotFoundState id={params.id} />;

  return (
    <div className="max-w-xl mx-auto px-4 py-8">
      <GrievanceHeader complaint={complaint} />
      <SLACountdown deadline={complaint.sla_deadline} />
      <Timeline events={complaint.timeline} />
    </div>
  );
}

// SLA countdown — client component for live countdown
"use client";
function SLACountdown({ deadline }: { deadline: string }) {
  const [timeLeft, setTimeLeft] = useState(computeTimeLeft(deadline));
  useEffect(() => {
    const interval = setInterval(() => setTimeLeft(computeTimeLeft(deadline)), 60000);
    return () => clearInterval(interval);
  }, [deadline]);

  if (timeLeft <= 0) return <p className="text-red-600 text-sm">SLA breached</p>;
  const hours = Math.floor(timeLeft / 3600);
  return <p className="text-sm text-amber-600">{hours} hours remaining within SLA</p>;
}
```

### What this page intentionally excludes (privacy)
- Officer phone numbers
- Internal notes
- Raw GPS coordinates of complaint
- Citizen email/phone hash

---

## File 4 — `app/(public)/map/page.tsx`

**Role:** Public ward heatmap. Shows complaint density per ward, colour-coded by count. Category filter available. No individual complaint pins — privacy protected. No login required.

### Layout

```
┌──────────────────────────────────────────────────────┐
│  Filter: [All] [Drainage] [Roads] [Streetlights] ...  │
│                                                        │
│  ┌────────────────── MapLibre Map ─────────────────┐   │
│  │  Ward boundaries rendered as GeoJSON polygons   │   │
│  │  Colour fill intensity = complaint count        │   │
│  │  Click ward → tooltip: "Ward 14: 23 complaints" │   │
│  └─────────────────────────────────────────────────┘   │
│                                                        │
│  Legend: ██ 0-5  ██ 6-15  ██ 16-30  ██ 30+            │
└──────────────────────────────────────────────────────┘
```

### Implementation

```typescript
"use client";
import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import { api } from "@/lib/api";

const DENSITY_COLORS = ["#EFF6FF", "#BFDBFE", "#60A5FA", "#1D4ED8"];

export default function PublicMapPage() {
  const mapRef   = useRef<HTMLDivElement>(null);
  const mapObj   = useRef<maplibregl.Map | null>(null);
  const [category, setCategory] = useState<string | undefined>();

  useEffect(() => {
    if (!mapRef.current) return;
    mapObj.current = new maplibregl.Map({
      container: mapRef.current,
      style: "https://tiles.openfreemap.org/styles/liberty",  // OpenStreetMap tiles
      center: [77.2090, 28.6139],  // Delhi
      zoom: 11,
    });

    mapObj.current.on("load", () => loadWardData());
    return () => mapObj.current?.remove();
  }, []);

  async function loadWardData() {
    const [wardsGeoJSON, densityData] = await Promise.all([
      api.wards.all(),
      api.analytics.wardDensity(category),
    ]);

    // Merge density counts into GeoJSON feature properties
    const densityMap = Object.fromEntries(densityData.map((d: any) => [d.ward_id, d.count]));
    wardsGeoJSON.features.forEach((f: any) => {
      f.properties.count = densityMap[f.properties.id] ?? 0;
    });

    mapObj.current!.addSource("wards", { type: "geojson", data: wardsGeoJSON });
    mapObj.current!.addLayer({
      id: "ward-fill",
      type: "fill",
      source: "wards",
      paint: {
        "fill-color": [
          "step", ["get", "count"],
          DENSITY_COLORS[0], 6,  DENSITY_COLORS[1],
          16, DENSITY_COLORS[2], 30, DENSITY_COLORS[3]
        ],
        "fill-opacity": 0.75,
      },
    });

    // Click handler → popup with ward name + count
    mapObj.current!.on("click", "ward-fill", (e) => {
      const props = e.features![0].properties;
      new maplibregl.Popup()
        .setLngLat(e.lngLat)
        .setHTML(`<strong>${props.name}</strong><br>${props.count} complaints`)
        .addTo(mapObj.current!);
    });
  }

  // Re-load when category filter changes
  useEffect(() => { if (mapObj.current?.loaded()) loadWardData(); }, [category]);

  return (
    <div className="h-screen flex flex-col">
      <CategoryFilter selected={category} onChange={setCategory} />
      <div ref={mapRef} className="flex-1" />
      <DensityLegend />
    </div>
  );
}
```

### Graceful degradation
If MapLibre fails to load (network error, browser incompatibility), a `<noscript>` fallback and an error boundary render a plain table of ward complaint counts instead. The page is never just blank.

---

## File 5 — `app/(dashboard)/layout.tsx`

**Role:** Shared shell for all authenticated dashboard pages. Provides the sidebar, top bar, auth guard, and role-based navigation. All child dashboard pages (`/dashboard/jssa`, `/dashboard/aa`, etc.) are rendered inside this layout.

### Structure

```
┌─────────────────────────────────────────────────────────┐
│ SIDEBAR (240px fixed, collapses to 56px)                │
│  [PS-CRM logo]                                          │
│  ─── Navigation ───                                     │
│  📍 Dashboard                                           │
│  📋 Complaints                                          │
│  📊 Analytics        ← only for Super Admin             │
│  👷 Contractors      ← only for Super Admin             │
│  ─── User ─────────                                     │
│  [Avatar] Rahul Kumar                                   │
│           JSSA · Ward 14                                │
├─────────────────────────────────────────────────────────┤
│ TOP BAR (sticky)                                        │
│  [Page Title]   [🔍 Search]   [🔔 3]  [Avatar]         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│         CONTENT AREA (slot for child pages)             │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Implementation

```typescript
import { createServerSupabase } from "@/lib/supabase";
import { redirect } from "next/navigation";
import { Sidebar, TopBar } from "@/components/ui";

const ROLE_NAV: Record<string, NavItem[]> = {
  jssa: [
    { href: "/dashboard/jssa",       label: "Dashboard",  icon: "Map" },
    { href: "/dashboard/jssa/complaints", label: "Complaints", icon: "List" },
  ],
  aa: [
    { href: "/dashboard/aa",         label: "Dashboard",  icon: "Inbox" },
    { href: "/dashboard/aa/officers", label: "Officers",  icon: "Users" },
  ],
  super_admin: [
    { href: "/dashboard/super-admin",               label: "Analytics",   icon: "BarChart" },
    { href: "/dashboard/super-admin/contractors",   label: "Contractors", icon: "Briefcase" },
    { href: "/dashboard/super-admin/hotspots",      label: "Hotspots",    icon: "AlertTriangle" },
  ],
  // ... aa, faa, contractor nav items
};

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const supabase = createServerSupabase();
  const { data: { session } } = await supabase.auth.getSession();

  // This is a defence-in-depth check — middleware already handles this
  // but Server Components cannot rely on middleware alone
  if (!session) redirect("/login");

  const role  = session.user.user_metadata?.role ?? "jssa";
  const nav   = ROLE_NAV[role] ?? [];

  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar navItems={nav} role={role} user={session.user} />
      <div className="flex flex-col flex-1 overflow-hidden">
        <TopBar user={session.user} />
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
```

### Role context

```typescript
// UserContext provides role + user info to all child components
// without prop-drilling down the component tree
export const UserContext = createContext<{ role: string; userId: string } | null>(null);
export const useUser = () => useContext(UserContext)!;
```

---

## File 6 — `app/(dashboard)/jssa/page.tsx`

**Role:** The JSSA's primary working interface. A 60/40 split map + complaint list. Map shows complaint pins colour-coded by urgency and SLA status. Supabase Realtime keeps pins live without page refresh. Clicking a pin opens a slide-in detail panel with status update controls.

### Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│ [MapLibre Map 60%]         │ [Complaint List 40%]                     │
│                            │  Sort: [Urgency ▾] [SLA ▾]              │
│  🔴 Drain overflow         │                                          │
│  🟡 Pothole on Ring Rd     │  🔴 MCD-...A7K2M   Drain overflow        │
│  🟢 Broken streetlight     │     Ward 14 · Urgency 5 · 4h left        │
│                            │                                          │
│                            │  🟡 MCD-...B3F1K   Pothole Ring Rd       │
│                            │     Ward 14 · Urgency 3 · 18h left       │
│                            │                                          │
│  [Detail Panel — slides in from right when pin clicked]              │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │ MCD-20250315-A7K2M  [IN PROGRESS 🟡]                         │    │
│  │ Drainage overflow near Laxmi Nagar market                    │    │
│  │                                                              │    │
│  │ ── Status Update ──────────────────────────────────────────  │    │
│  │ [Select next status ▾]  [Proof photo URL]  [Note]  [Update] │    │
│  │                                                              │    │
│  │ ── Timeline ───────────────────────────────────────────────  │    │
│  │ ● ASSIGNED  Mar 15 10:05                                     │    │
│  │ ● IN_PROGRESS  Mar 16 09:00 — proof photo uploaded           │    │
│  └──────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

### Implementation

```typescript
"use client";
import { useState, useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import { supabase } from "@/lib/supabase";
import { api } from "@/lib/api";
import { useUser } from "@/app/(dashboard)/layout";
import { ComplaintDetailPanel } from "@/components/complaints";

export default function JSSADashboard() {
  const { userId, wardId }  = useUser();
  const mapRef              = useRef<HTMLDivElement>(null);
  const mapObj              = useRef<maplibregl.Map | null>(null);
  const [complaints, setComplaints]  = useState<any[]>([]);
  const [selectedId, setSelectedId]  = useState<string | null>(null);

  // Initial load
  useEffect(() => {
    api.complaints.list({ ward_id: wardId }).then(setComplaints);
  }, [wardId]);

  // Supabase Realtime — new complaint or status change in this ward
  useEffect(() => {
    const channel = supabase
      .channel("jssa-complaints")
      .on("postgres_changes", {
        event:  "*",          // INSERT and UPDATE
        schema: "public",
        table:  "complaints",
        filter: `ward_id=eq.${wardId}`,
      }, (payload) => {
        setComplaints(prev => {
          const idx = prev.findIndex(c => c.id === payload.new.id);
          if (idx >= 0) {
            const updated = [...prev];
            updated[idx]  = payload.new;
            return updated;
          }
          return [payload.new, ...prev];  // new complaint → prepend
        });
        // Also update map pin if map is loaded
        updateMapPin(payload.new);
      })
      .subscribe();

    return () => { supabase.removeChannel(channel); };
  }, [wardId]);

  // MapLibre setup
  useEffect(() => {
    if (!mapRef.current) return;
    mapObj.current = new maplibregl.Map({
      container: mapRef.current,
      style: "https://tiles.openfreemap.org/styles/liberty",
      center: [77.2090, 28.6139],
      zoom: 13,
    });
    return () => mapObj.current?.remove();
  }, []);

  function getPinColor(urgency: number, slaDeadline: string): string {
    const slaLeft = new Date(slaDeadline).getTime() - Date.now();
    const slaHours = slaLeft / 3600000;
    if (urgency >= 4 || slaHours < 4)  return "#EF4444";  // red
    if (urgency >= 2 || slaHours < 12) return "#F59E0B";  // orange
    return "#22C55E";                                       // green
  }

  async function handleStatusUpdate(complaintId: string, newStatus: string, proofUrl?: string, note?: string) {
    await api.complaints.updateStatus(complaintId, {
      new_status: newStatus,
      proof_url: proofUrl,
      internal_note: note,
    });
    // Realtime will push the update back — no need to manually refresh
  }

  return (
    <div className="flex h-full gap-0">
      <div ref={mapRef} className="w-[60%] h-full" />
      <div className="w-[40%] h-full overflow-y-auto border-l border-gray-200">
        {complaints.length === 0 && (
          <EmptyState message="No active complaints in your ward." />
        )}
        {complaints.map(c => (
          <ComplaintCard
            key={c.id}
            complaint={c}
            onClick={() => setSelectedId(c.id)}
            pinColor={getPinColor(c.urgency, c.sla_deadline)}
          />
        ))}
      </div>

      {selectedId && (
        <ComplaintDetailPanel
          complaintId={selectedId}
          onClose={() => setSelectedId(null)}
          onStatusUpdate={handleStatusUpdate}
        />
      )}
    </div>
  );
}
```

---

## File 7 — `app/(dashboard)/aa/page.tsx`

**Role:** AA (Area Admin) dashboard. Two tabs: the escalation queue (complaints escalated from JSSAs in the AA's zone), and officer performance metrics for each JSSA in their zone.

### Layout

```
┌──────────────────────────────────────────────────────────┐
│  [Escalation Queue]   [Officer Performance]              │
│                                                          │
│  ── Escalation Queue Tab ───────────────────────────     │
│  ┌───────────────────────────────────────────────────┐   │
│  │ MCD-...A7K2M  ESCALATED 🔴  Drain overflow        │   │
│  │ JSSA: Rahul K.  Escalated at: SLA breach          │   │
│  │ Time in ESCALATED: 3h 20m                         │   │
│  │ [Reassign JSSA] [Resolve Directly] [Start Tender] │   │
│  └───────────────────────────────────────────────────┘   │
│                                                          │
│  ── Officer Performance Tab ────────────────────────     │
│  Name        Assigned  Resolved  Escalated  Avg(h)  Reopen│
│  Rahul K.     14        10         2         18.3    14%   │
│  Priya M.     9         9          0         12.1    0%    │
└──────────────────────────────────────────────────────────┘
```

### Implementation

```typescript
"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import { useUser } from "@/app/(dashboard)/layout";

export default function AADashboard() {
  const { zoneWardIds } = useUser();
  const [tab, setTab]               = useState<"queue" | "officers">("queue");
  const [escalations, setEscalations] = useState<any[]>([]);
  const [officerStats, setOfficerStats] = useState<any[]>([]);

  useEffect(() => {
    // Fetch escalated complaints for AA's zone
    api.complaints.list({ ward_id: zoneWardIds.join(","), status: "ESCALATED" })
      .then(setEscalations);

    // Fetch officer stats for each JSSA in zone
    Promise.all(zoneWardIds.map(wardId => api.officers.stats(wardId)))
      .then(results => setOfficerStats(results.flat()));
  }, [zoneWardIds]);

  // Realtime: update escalation queue when new escalation arrives
  useEffect(() => {
    const ch = supabase.channel("aa-escalations")
      .on("postgres_changes", {
        event: "UPDATE", schema: "public", table: "complaints",
        filter: `status=eq.ESCALATED`,
      }, (payload) => {
        if (zoneWardIds.includes(payload.new.ward_id)) {
          setEscalations(prev => {
            const idx = prev.findIndex(c => c.id === payload.new.id);
            if (idx >= 0) { const u = [...prev]; u[idx] = payload.new; return u; }
            return [payload.new, ...prev];
          });
        }
      }).subscribe();
    return () => { supabase.removeChannel(ch); };
  }, [zoneWardIds]);

  return (
    <div>
      <TabBar tabs={["Escalation Queue", "Officer Performance"]} onSelect={setTab} />
      {tab === "queue" && (
        <EscalationQueue complaints={escalations} />
      )}
      {tab === "officers" && (
        <OfficerTable stats={officerStats} />
      )}
    </div>
  );
}
```

---

## File 8 — `app/(dashboard)/super-admin/page.tsx`

**Role:** The Super Admin analytics hub. KPI summary cards, complaint volume chart, SLA compliance bar chart, and a live hotspot map. All charts use Recharts. Hotspot map uses MapLibre.

### Layout

```
┌───────────────────────────────────────────────────────────────┐
│  [KPI Row]                                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │ 342      │  │ 18.4h    │  │ 87.3%    │  │ 4 🔴     │     │
│  │ Active   │  │ Avg Res. │  │ SLA      │  │ Hotspot  │     │
│  │ Compl.   │  │ Time     │  │ Compliance│ │ Alerts   │     │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘     │
│                                                               │
│  [Complaint Volume Chart]       [SLA Compliance Chart]        │
│  ┌────────────────────────┐     ┌─────────────────────────┐  │
│  │ Bar chart — daily/     │     │ Horizontal bar per dept │  │
│  │ weekly/monthly counts  │     │ Green=compliant, Red=   │  │
│  │                        │     │ breached                │  │
│  └────────────────────────┘     └─────────────────────────┘  │
│                                                               │
│  [Hotspot Map — MapLibre]                                     │
│  ┌──────────────────────────────────────────────────────┐     │
│  │  Cluster circles: green (1-2) orange (3) red (4-5)   │     │
│  │  Click hotspot → complaint list + action buttons     │     │
│  └──────────────────────────────────────────────────────┘     │
└───────────────────────────────────────────────────────────────┘
```

### Implementation

```typescript
"use client";
import { useState, useEffect, useRef } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
         CartesianGrid, Legend } from "recharts";
import maplibregl from "maplibre-gl";
import { api } from "@/lib/api";
import { supabase } from "@/lib/supabase";

export default function SuperAdminDashboard() {
  const [volume,      setVolume]      = useState<any[]>([]);
  const [sla,         setSla]         = useState<any[]>([]);
  const [hotspots,    setHotspots]    = useState<any[]>([]);
  const [kpi,         setKpi]         = useState<any>(null);
  const [groupBy,     setGroupBy]     = useState<"day" | "week" | "month">("day");
  const hotspotMapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    Promise.all([
      api.analytics.complaintVolume({ group_by: groupBy }),
      api.analytics.slaCompliance(),
      api.analytics.hotspots(),
    ]).then(([v, s, h]) => {
      setVolume(v);
      setSla(s);
      setHotspots(h);
      setKpi(computeKPIs(v, s, h));
    });
  }, [groupBy]);

  // Realtime — new hotspots from Predictive Agent nightly run
  useEffect(() => {
    const ch = supabase.channel("hotspots-live")
      .on("postgres_changes", { event: "INSERT", schema: "public", table: "hotspots" },
          (payload) => setHotspots(prev => [...prev, payload.new]))
      .subscribe();
    return () => { supabase.removeChannel(ch); };
  }, []);

  // Hotspot map
  useEffect(() => {
    if (!hotspotMapRef.current || hotspots.length === 0) return;
    const map = new maplibregl.Map({
      container: hotspotMapRef.current,
      style: "https://tiles.openfreemap.org/styles/liberty",
      center: [77.2090, 28.6139], zoom: 11,
    });

    const SEVERITY_COLORS: Record<number, string> = {
      1: "#22C55E", 2: "#22C55E",  // green
      3: "#F59E0B",                 // orange
      4: "#EF4444", 5: "#EF4444",  // red
    };

    hotspots.forEach(h => {
      const el = document.createElement("div");
      el.style.cssText = `
        width: ${20 + h.severity * 10}px;
        height: ${20 + h.severity * 10}px;
        border-radius: 50%;
        background: ${SEVERITY_COLORS[h.severity]}40;
        border: 2px solid ${SEVERITY_COLORS[h.severity]};
        cursor: pointer;
      `;
      new maplibregl.Marker({ element: el })
        .setLngLat([h.lng, h.lat])
        .setPopup(new maplibregl.Popup().setHTML(
          `<strong>${h.category}</strong><br>${h.complaint_count} complaints<br>Severity: ${h.severity}/5`
        ))
        .addTo(map);
    });

    return () => map.remove();
  }, [hotspots]);

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <KPIRow kpi={kpi} hotspotCount={hotspots.length} />

      {/* Charts row */}
      <div className="grid grid-cols-2 gap-6">
        <div className="bg-white border border-gray-200 rounded p-4">
          <div className="flex justify-between mb-3">
            <h3 className="font-semibold text-sm">Complaint Volume</h3>
            <GroupByToggle value={groupBy} onChange={setGroupBy} />
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={volume}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
              <XAxis dataKey="period" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" fill="#3B82F6" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white border border-gray-200 rounded p-4">
          <h3 className="font-semibold text-sm mb-3">SLA Compliance by Department</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={sla} layout="vertical">
              <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" />
              <YAxis dataKey="department_name" type="category" tick={{ fontSize: 11 }} width={100} />
              <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} />
              <Bar dataKey="compliance_pct" fill="#22C55E" radius={[0, 2, 2, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Hotspot map */}
      <div className="bg-white border border-gray-200 rounded overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200">
          <h3 className="font-semibold text-sm">Active Hotspots ({hotspots.length})</h3>
        </div>
        <div ref={hotspotMapRef} className="h-80" />
      </div>
    </div>
  );
}
```

### Contractor scorecard (sub-page)

This lives at `/dashboard/super-admin/contractors` — a table of all contractors with their reliability scores, and action buttons to deactivate. It calls `api.contractors.scorecard(id)` per contractor and renders the reliability formula result.

---

## File 9 — `app/(dashboard)/contractor/page.tsx` + `app/(dashboard)/faa/page.tsx`

**Role:** Two dashboard pages that are smaller in scope and can share a file. The contractor task portal and the FAA escalation/tender page.

### Contractor Portal

```
┌────────────────────────────────────────────────────────┐
│  My Work Orders                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │ WO-20250315-001  [ASSIGNED 🔵]                   │  │
│  │ Drain repair — Ward 14, Laxmi Nagar              │  │
│  │ SLA: 36h remaining                               │  │
│  │ [Upload Mid-Job Photo]  [View on Map]            │  │
│  └──────────────────────────────────────────────────┘  │
│                                                        │
│  My Scorecard                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Tasks: 24   On-time: 87%   Rejection: 8%         │  │
│  │ Reliability Score: 82/100                        │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

```typescript
// Contractor portal page
"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useUser } from "@/app/(dashboard)/layout";

export default function ContractorPortal() {
  const { userId } = useUser();
  const [workOrders, setWorkOrders] = useState<any[]>([]);
  const [scorecard,  setScorecard]  = useState<any>(null);

  useEffect(() => {
    // Work orders from complaint_departments where contractor_id = userId
    api.complaints.list({ contractor_id: userId }).then(setWorkOrders);
    api.contractors.scorecard(userId).then(setScorecard);
  }, [userId]);

  async function handleProofUpload(workOrderId: string, file: File, type: "mid" | "final") {
    // 1. Get pre-signed upload URL from backend
    const { upload_url, file_path } = await api.complaints.getUploadUrl();
    // 2. Upload directly to Supabase Storage
    await fetch(upload_url, { method: "PUT", body: file });
    // 3. Update complaint status with proof URL
    const newStatus = type === "mid" ? "IN_PROGRESS" : "FINAL_SURVEY_PENDING";
    await api.complaints.updateStatus(workOrderId, { new_status: newStatus, proof_url: file_path });
  }

  return (
    <div className="space-y-6">
      <WorkOrderList orders={workOrders} onUpload={handleProofUpload} />
      {scorecard && <ContractorScorecard data={scorecard} />}
    </div>
  );
}
```

### FAA Dashboard

```typescript
// FAA page — escalation queue + tender initiation
export default function FAADashboard() {
  const [escalations, setEscalations] = useState<any[]>([]);
  const [tenderForm, setTenderForm]   = useState<{ complaintIds: string[]; open: boolean }>({ complaintIds: [], open: false });

  useEffect(() => {
    // FAA sees complaints escalated from AA (2nd level escalations)
    api.complaints.list({ status: "ESCALATED", escalation_level: "faa" }).then(setEscalations);
  }, []);

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold">FAA Escalation Queue</h2>
      {escalations.map(c => (
        <EscalationCard
          key={c.id}
          complaint={c}
          onInitiateTender={(ids) => setTenderForm({ complaintIds: ids, open: true })}
        />
      ))}

      {tenderForm.open && (
        <TenderInitiationModal
          complaintIds={tenderForm.complaintIds}
          onClose={() => setTenderForm({ complaintIds: [], open: false })}
          // On submit → POST /complaints/{id}/work-orders
          // → Email SMTP notification to Super Admin for approval
        />
      )}
    </div>
  );
}
```

---

## File 10 — `components/` (All shared components)

**Role:** All reusable UI components used across multiple pages. MapLibre wrappers, complaint cards, detail panel, chart wrappers, and shadcn/ui re-exports. This file represents the components directory — in practice these are multiple component files but they count as one logical grouping in the 10-file budget.

### Component tree

```
components/
  ├── map/
  │   ├── ComplaintMap.tsx         — MapLibre wrapper with pin management
  │   ├── WardBoundaryLayer.tsx    — GeoJSON ward polygon layer
  │   └── HotspotCircleLayer.tsx   — Hotspot severity circles
  │
  ├── complaints/
  │   ├── ComplaintCard.tsx         — List item: title, status badge, SLA countdown
  │   ├── ComplaintDetailPanel.tsx  — Slide-in panel: full detail + status update form
  │   ├── StatusBadge.tsx           — Pill badge: colour + text per status
  │   ├── Timeline.tsx              — Vertical event timeline
  │   └── SLABar.tsx                — Progress bar showing % SLA consumed
  │
  ├── charts/
  │   ├── VolumeChart.tsx           — Recharts BarChart wrapper for complaint volume
  │   └── SLAComplianceChart.tsx    — Recharts horizontal BarChart per department
  │
  └── ui/
      ├── Sidebar.tsx               — Collapsible sidebar shell
      ├── TopBar.tsx                — Sticky top navigation bar
      ├── EmptyState.tsx            — Centered empty state with icon + message
      ├── SkeletonLoader.tsx        — Skeleton for loading states (complaint list)
      └── index.ts                  — Re-exports all shadcn/ui components used
```

### ComplaintDetailPanel

```typescript
// The most complex component — slide-in drawer from the right side
// Shows full complaint detail + allows JSSA to update status, add notes, upload proof

"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { StatusBadge, Timeline, SLABar } from "@/components/complaints";
import { Sheet, SheetContent, SheetHeader } from "@/components/ui";

export function ComplaintDetailPanel({ complaintId, onClose, onStatusUpdate }: Props) {
  const [complaint, setComplaint] = useState<any>(null);
  const [nextStatus, setNextStatus] = useState("");
  const [proofUrl,   setProofUrl]   = useState("");
  const [note,       setNote]       = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.complaints.get(complaintId).then(setComplaint);
  }, [complaintId]);

  if (!complaint) return <PanelSkeleton />;

  const validNextStates = getValidNextStates(complaint.status);
  const proofRequired   = ["IN_PROGRESS", "FINAL_SURVEY_PENDING"].includes(nextStatus);

  return (
    <Sheet open onOpenChange={onClose}>
      <SheetContent className="w-[480px] overflow-y-auto">
        <SheetHeader>
          <code className="text-xs font-mono text-gray-500">{complaint.grievance_id}</code>
          <StatusBadge status={complaint.status} />
        </SheetHeader>

        <div className="space-y-4 mt-4">
          {/* Complaint text */}
          <p className="text-sm text-gray-700">{complaint.translated_text}</p>
          {complaint.raw_text !== complaint.translated_text && (
            <p className="text-xs text-gray-400 italic">Original: {complaint.raw_text}</p>
          )}

          {/* SLA progress */}
          <SLABar deadline={complaint.sla_deadline} createdAt={complaint.created_at} />

          {/* Status update form */}
          {validNextStates.length > 0 && (
            <div className="border border-gray-200 rounded p-3 space-y-2">
              <label className="text-xs font-semibold uppercase text-gray-500">Update Status</label>
              <select className="w-full border border-gray-200 rounded p-2 text-sm"
                      value={nextStatus} onChange={e => setNextStatus(e.target.value)}>
                <option value="">Select...</option>
                {validNextStates.map(s => <option key={s} value={s}>{s}</option>)}
              </select>

              {proofRequired && (
                <ProofUploader onUploaded={setProofUrl} />
              )}

              <textarea
                className="w-full border border-gray-200 rounded p-2 text-sm"
                placeholder="Internal note (optional)"
                value={note} onChange={e => setNote(e.target.value)}
                rows={2}
              />

              <button
                disabled={!nextStatus || (proofRequired && !proofUrl) || submitting}
                onClick={() => onStatusUpdate(complaintId, nextStatus, proofUrl, note)}
                className="w-full bg-blue-600 text-white text-sm font-semibold py-2 rounded
                           disabled:opacity-40 hover:bg-blue-700 transition-colors"
              >
                {submitting ? "Updating..." : "Update Status"}
              </button>
            </div>
          )}

          {/* Event timeline */}
          <Timeline events={complaint.timeline} />
        </div>
      </SheetContent>
    </Sheet>
  );
}
```

### StatusBadge

```typescript
const STATUS_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  NEW:                   { bg: "bg-gray-100",   text: "text-gray-700",   label: "NEW" },
  CLASSIFIED:            { bg: "bg-blue-50",    text: "text-blue-700",   label: "CLASSIFIED" },
  ASSIGNED:              { bg: "bg-blue-100",   text: "text-blue-800",   label: "ASSIGNED" },
  IN_PROGRESS:           { bg: "bg-amber-100",  text: "text-amber-800",  label: "IN PROGRESS" },
  MID_SURVEY_PENDING:    { bg: "bg-amber-50",   text: "text-amber-700",  label: "MID SURVEY" },
  FINAL_SURVEY_PENDING:  { bg: "bg-purple-100", text: "text-purple-800", label: "FINAL SURVEY" },
  ESCALATED:             { bg: "bg-red-100",    text: "text-red-800",    label: "ESCALATED" },
  REOPENED:              { bg: "bg-red-100",    text: "text-red-700",    label: "REOPENED" },
  CLOSED:                { bg: "bg-green-100",  text: "text-green-800",  label: "CLOSED" },
  CLOSED_UNVERIFIED:     { bg: "bg-gray-100",   text: "text-gray-500",   label: "UNVERIFIED" },
};

export function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] ?? STATUS_STYLES["NEW"];
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold uppercase tracking-wide ${style.bg} ${style.text}`}>
      {style.label}
    </span>
  );
}
```

### SkeletonLoader

```typescript
// Used on complaint list, dashboard KPIs, and officer tables while data loads
// Prevents layout shift when data arrives

export function ComplaintListSkeleton() {
  return (
    <div className="space-y-2 p-4">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="animate-pulse border border-gray-100 rounded p-3">
          <div className="h-3 bg-gray-200 rounded w-1/3 mb-2" />
          <div className="h-2 bg-gray-100 rounded w-2/3" />
        </div>
      ))}
    </div>
  );
}
```

### EmptyState

```typescript
export function EmptyState({ message, icon = "📭" }: { message: string; icon?: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-64 text-gray-400">
      <span className="text-4xl mb-3">{icon}</span>
      <p className="text-sm text-center max-w-xs">{message}</p>
    </div>
  );
}
// Used as: <EmptyState message="No active complaints in your ward." />
// Never renders a blank screen
```

---

## Summary Table

| # | File | What it owns |
|---|------|--------------|
| 1 | `middleware.ts` + `lib/supabase.ts` + `lib/api.ts` | Auth protection, Supabase client, typed FastAPI client |
| 2 | `app/(public)/page.tsx` | Landing — complaint form + grievance lookup |
| 3 | `app/(public)/track/[id]/page.tsx` | Public status tracker |
| 4 | `app/(public)/map/page.tsx` | Public ward heatmap (no auth) |
| 5 | `app/(dashboard)/layout.tsx` | Auth guard + sidebar + top bar + role context |
| 6 | `app/(dashboard)/jssa/page.tsx` | JSSA map + task list + detail panel + Realtime |
| 7 | `app/(dashboard)/aa/page.tsx` | AA escalation queue + officer performance table |
| 8 | `app/(dashboard)/super-admin/page.tsx` | KPIs + charts + hotspot map + contractor scorecard |
| 9 | `app/(dashboard)/contractor/page.tsx` + `faa/page.tsx` | Contractor portal + FAA escalation/tender |
| 10 | `components/` | Map wrappers, complaint cards, charts, UI primitives |

**Plus (not counted):**
- `app/login/page.tsx` — Supabase Auth UI
- `types/supabase.ts` — Auto-generated DB types from Supabase CLI
- `next.config.js`, `tailwind.config.js`, `tsconfig.json`
- `.env.local` (environment variables)