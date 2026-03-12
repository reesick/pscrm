"use client";
import React, { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { VolumeChart } from "@/components/charts/VolumeChart";
import { SLAComplianceChart } from "@/components/charts/SLAComplianceChart";
import 'maplibre-gl/dist/maplibre-gl.css';

// Severity → colour mapping for hotspot circles
const HOTSPOT_COLORS = ["#22C55E", "#84CC16", "#F59E0B", "#EF4444", "#7F1D1D"];

export default function SuperAdminDashboard() {
  const [volume,   setVolume]   = useState<any[]>([]);
  const [sla,      setSla]      = useState<any[]>([]);
  const [hotspots, setHotspots] = useState<any[]>([]);
  const [groupBy,  setGroupBy]  = useState<"day" | "week" | "month">("day");

  const hotspotMapRef = useRef<HTMLDivElement>(null);
  const hotspotMap    = useRef<any>(null);
  const mapLoaded     = useRef(false);

  // Load analytics data
  useEffect(() => {
    api.analytics.complaintVolume({ group_by: groupBy }).then((res: any) => setVolume(Array.isArray(res) ? res : [])).catch(() => {});
    api.analytics.slaCompliance().then((res: any) => setSla(Array.isArray(res) ? res : [])).catch(() => {});
    api.analytics.hotspots().then((res: any) => setHotspots(Array.isArray(res) ? res : [])).catch(() => {});
  }, [groupBy]);

  // Init hotspot map
  useEffect(() => {
    if (!hotspotMapRef.current || hotspotMap.current) return;
    import('maplibre-gl').then(mod => {
      const maplibregl = mod.default;
      hotspotMap.current = new maplibregl.Map({
        container: hotspotMapRef.current!,
        style: "https://tiles.openfreemap.org/styles/liberty",
        center: [77.2090, 28.6139],
        zoom: 10,
      });
      hotspotMap.current.on('load', () => {
        mapLoaded.current = true;
        renderHotspotMarkers();
      });
    });
    return () => hotspotMap.current?.remove();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function renderHotspotMarkers() {
    if (!hotspotMap.current || !mapLoaded.current) return;
    import('maplibre-gl').then(mod => {
      const maplibregl = mod.default;
      hotspots.forEach((h: any) => {
        if (!h.lat || !h.lng) return;
        const size = Math.max(24, Math.min(80, h.radius_m / 5));
        const color = HOTSPOT_COLORS[(h.severity ?? 1) - 1] ?? HOTSPOT_COLORS[2];
        const el = document.createElement('div');
        el.style.cssText = `width:${size}px;height:${size}px;border-radius:50%;background:${color};opacity:0.75;border:2px solid white;cursor:pointer;display:flex;align-items:center;justify-content:center;color:white;font-size:10px;font-weight:700;`;
        el.textContent = String(h.complaint_count);
        new maplibregl.Marker({ element: el })
          .setLngLat([h.lng, h.lat])
          .setPopup(
            new maplibregl.Popup({ offset: 10 }).setHTML(
              `<div style="font-size:13px;line-height:1.5">
                <strong>${h.category}</strong><br/>
                ${h.complaint_count} complaints · Severity ${h.severity}/5<br/>
                Ward: ${h.ward_name}
               </div>`
            )
          )
          .addTo(hotspotMap.current);
      });
    });
  }

  // Re-render markers when hotspots load (map may already be ready)
  useEffect(() => {
    if (mapLoaded.current) renderHotspotMarkers();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hotspots]);

  // ── Derived KPIs ──────────────────────────────────────────────────
  const totalVolume   = volume.reduce((s: number, v: any) => s + (v.count || 0), 0);
  const avgCompliance = sla.length > 0
    ? (sla.reduce((s: number, d: any) => s + (d.compliance_pct || 0), 0) / sla.length).toFixed(1)
    : null;
  const hotspotCount  = hotspots.length;
  const deptCount     = sla.length;

  const KPI_CARDS = [
    { label: "Complaints (30d)",  value: totalVolume || "—",                        sub: "Total reported volume",           color: "text-blue-700",  bg: "bg-blue-50" },
    { label: "Avg SLA Compliance", value: avgCompliance ? avgCompliance + "%" : "—", sub: "Across all departments",          color: "text-green-700", bg: "bg-green-50" },
    { label: "Active Hotspots",   value: hotspotCount,                               sub: "Clusters needing attention",      color: "text-red-600",   bg: "bg-red-50" },
    { label: "Departments",       value: deptCount || "—",                           sub: "With SLA compliance data",        color: "text-purple-700",bg: "bg-purple-50" },
  ];

  return (
    <div className="p-6 bg-gray-50 h-full overflow-y-auto w-full space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Executive Analytics</h1>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        {KPI_CARDS.map((kpi, i) => (
          <div key={i} className="bg-white rounded border border-gray-200 p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">{kpi.label}</p>
            <p className={`text-4xl font-bold mt-2 ${kpi.color}`}>{kpi.value}</p>
            <p className="text-xs text-gray-400 mt-1">{kpi.sub}</p>
          </div>
        ))}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold uppercase text-gray-500 tracking-wide">Complaint Volume</h2>
            <div className="flex gap-1">
              {(["day", "week", "month"] as const).map(g => (
                <button
                  key={g}
                  onClick={() => setGroupBy(g)}
                  className={`px-2 py-1 text-xs rounded font-medium transition-colors ${
                    groupBy === g ? "bg-blue-700 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}
                >
                  {g}
                </button>
              ))}
            </div>
          </div>
          <VolumeChart data={volume} />
        </div>

        <div className="bg-white rounded border border-gray-200 p-6">
          <h2 className="text-sm font-semibold uppercase text-gray-500 mb-6 tracking-wide">SLA Compliance by Department</h2>
          <SLAComplianceChart data={sla} />
        </div>
      </div>

      {/* Hotspot Map */}
      <div className="bg-white rounded border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold uppercase text-gray-500 tracking-wide">Live Infrastructure Hotspots</h2>
          {hotspotCount > 0 && (
            <span className="bg-red-100 text-red-700 text-xs font-semibold px-2.5 py-1 rounded-full">
              🔴 {hotspotCount} active hotspot{hotspotCount !== 1 ? "s" : ""}
            </span>
          )}
        </div>
        <div className="h-[420px] rounded-lg overflow-hidden border border-gray-100 relative">
          <div ref={hotspotMapRef} className="absolute inset-0" />
          <div className="absolute top-3 left-3 bg-white/90 backdrop-blur text-xs font-semibold text-gray-700 px-3 py-1.5 rounded-lg shadow border border-gray-100 z-10">
            🔥 Delhi MCD Predictive Hotspots
          </div>
          {hotspotCount === 0 && (
            <div className="absolute inset-0 flex items-center justify-center bg-gray-50/80 z-10">
              <p className="text-sm text-gray-500">No active hotspots detected. Nightly agent runs at 2 AM.</p>
            </div>
          )}
        </div>
        {/* Severity legend */}
        <div className="flex items-center gap-3 mt-3 text-xs text-gray-500">
          <span className="font-medium">Severity:</span>
          {HOTSPOT_COLORS.map((c, i) => (
            <span key={i} className="flex items-center gap-1">
              <span className="w-3 h-3 rounded-full inline-block" style={{ backgroundColor: c }} />
              {i + 1}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

