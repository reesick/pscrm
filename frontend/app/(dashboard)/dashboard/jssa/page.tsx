"use client";
import React, { useState, useEffect, useRef } from "react";
import { api } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import { useUser } from "@/app/(dashboard)/layout";
import { ComplaintCard } from "@/components/complaints/ComplaintCard";
import { ComplaintDetailPanel } from "@/components/complaints/ComplaintDetailPanel";
import { ComplaintListSkeleton } from "@/components/ui/SkeletonLoader";
import { EmptyState } from "@/components/ui/EmptyState";
import 'maplibre-gl/dist/maplibre-gl.css';

export default function JSSADashboard() {
  const { wardId } = useUser();
  const [complaints, setComplaints] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<any>(null);
  const markers = useRef<{ [id: string]: any }>({});
  const mapLib = useRef<any>(null);

  // ── Helpers ────────────────────────────────────────────────────────
  function getPinColor(urgency: number, slaDeadline?: string): string {
    if (slaDeadline) {
      const msLeft = new Date(slaDeadline).getTime() - Date.now();
      if (msLeft <= 0) return "#DC2626";           // red — SLA breached
      if (msLeft < 4 * 3600 * 1000) return "#EF4444";  // red — critical
      if (msLeft < 12 * 3600 * 1000) return "#F59E0B";  // amber
    }
    if (urgency >= 4) return "#EF4444";
    if (urgency >= 3) return "#F59E0B";
    return "#22C55E";
  }

  // ── Data fetching ──────────────────────────────────────────────────
  async function fetchComplaints() {
    setLoading(true);
    try {
      // Backend scopes by ward_id from JWT automatically for jssa role
      const res: any = await api.complaints.list();
      // Backend returns a plain array (List[ComplaintAdminResponse]), not {items:[]}
      setComplaints(Array.isArray(res) ? res : []);
    } catch (err) {
      console.error(err);
      setComplaints([]);
    } finally {
      setLoading(false);
    }
  }

  // Initial load
  useEffect(() => {
    fetchComplaints();
  }, []);

  // ── Supabase Realtime — live ward updates ─────────────────────────
  useEffect(() => {
    const filter = wardId ? `ward_id=eq.${wardId}` : undefined;
    const channel = supabase
      .channel("jssa-ward-complaints")
      .on(
        "postgres_changes" as any,
        { event: "*", schema: "public", table: "complaints", ...(filter ? { filter } : {}) },
        () => { fetchComplaints(); }
      )
      .subscribe();
    return () => { supabase.removeChannel(channel); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wardId]);

  // ── MapLibre setup ─────────────────────────────────────────────────
  useEffect(() => {
    if (mapContainer.current && !map.current) {
      import('maplibre-gl').then(mod => {
        mapLib.current = mod.default;
        map.current = new mapLib.current.Map({
          container: mapContainer.current!,
          style: "https://tiles.openfreemap.org/styles/liberty",
          center: [77.2090, 28.6139],
          zoom: 12,
        });
      });
    }
    return () => map.current?.remove();
  }, []);

  // Sync map markers whenever complaints change
  useEffect(() => {
    if (!map.current || !mapLib.current) return;

    // Wait for map to be loaded
    const syncMarkers = () => {
      Object.values(markers.current).forEach((m: any) => m.remove());
      markers.current = {};

      complaints.forEach(c => {
        if (!c.lat || !c.lng) return;
        // Validate coordinates are in valid ranges
        const lat = Number(c.lat);
        const lng = Number(c.lng);
        if (isNaN(lat) || isNaN(lng) || lat < -90 || lat > 90 || lng < -180 || lng > 180) return;
        const color = getPinColor(c.urgency || 2, c.sla_deadline);
        const el = document.createElement('div');
        el.className = 'w-4 h-4 rounded-full border-2 border-white shadow cursor-pointer hover:scale-125 transition-transform duration-200';
        el.style.backgroundColor = color;
        el.addEventListener('click', () => setSelectedId(c.grievance_id));

        const marker = new mapLib.current.Marker({ element: el })
          .setLngLat([lng, lat])
          .addTo(map.current!);
        markers.current[c.grievance_id] = marker;
      });
    };

    if (map.current.loaded()) {
      syncMarkers();
    } else {
      map.current.once('load', syncMarkers);
    }
  }, [complaints]);

  // ── Status update handler ─────────────────────────────────────────
  async function handleStatusUpdate(id: string, newStatus: string, proofUrl?: string, note?: string) {
    await api.complaints.updateStatus(id, {
      new_status: newStatus,
      internal_note: note || undefined,
      proof_url: proofUrl || undefined,
    });
    setSelectedId(null);
    fetchComplaints();
  }

  return (
    <div className="flex h-full">
      {/* 60% Map panel — map is always left per PRD §10.4 */}
      <div className="w-3/5 flex-1 relative bg-gray-100">
        <div ref={mapContainer} className="absolute inset-0" />
      </div>

      {/* 40% List panel — right side */}
      <div className="w-2/5 border-l border-gray-200 bg-white flex flex-col z-10 shrink-0">
        <div className="p-4 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
          <div>
            <h2 className="font-semibold text-gray-900">Ward Task Queue</h2>
            <p className="text-xs text-gray-500">
              {loading ? 'Loading…' : `${complaints.length} active issues · live`}
            </p>
          </div>
          <button onClick={fetchComplaints} className="text-sm font-medium text-blue-700 hover:text-blue-800">
            Refresh
          </button>
        </div>

        <div className="flex-1 overflow-y-auto bg-white">
          {loading ? <ComplaintListSkeleton /> : (
            complaints.length === 0
              ? <EmptyState message="No active complaints in your ward. Great job!" icon="🎉" />
              : complaints.map(c => (
                  <div key={c.grievance_id} className={selectedId === c.grievance_id ? 'bg-blue-50/50 relative' : 'relative'}>
                    {selectedId === c.grievance_id && (
                      <div className="absolute left-0 top-0 bottom-0 w-1 bg-blue-500" />
                    )}
                    <ComplaintCard
                      complaint={c}
                      pinColor={getPinColor(c.urgency || 2, c.sla_deadline)}
                      onClick={() => {
                        setSelectedId(c.grievance_id);
                        const lat = Number(c.lat), lng = Number(c.lng);
                        if (map.current && !isNaN(lat) && !isNaN(lng) && lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180) {
                          map.current.flyTo({ center: [lng, lat], zoom: 15, duration: 800 });
                        }
                      }}
                    />
                  </div>
                ))
          )}
        </div>
      </div>

      {/* Slide-in detail panel */}
      {selectedId && (
        <ComplaintDetailPanel
          complaintId={selectedId}
          onClose={() => setSelectedId(null)}
          onStatusUpdate={handleStatusUpdate}
          initialData={complaints.find(c => c.grievance_id === selectedId)}
        />
      )}
    </div>
  );
}
