"use client";
import React, { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import { useUser } from "@/app/(dashboard)/layout";
import { ComplaintCard } from "@/components/complaints/ComplaintCard";
import { ComplaintDetailPanel } from "@/components/complaints/ComplaintDetailPanel";
import { ComplaintListSkeleton } from "@/components/ui/SkeletonLoader";
import { EmptyState } from "@/components/ui/EmptyState";

type Tab = "queue" | "officers";

export default function AADashboard() {
  const { zoneWardIds } = useUser();
  const [tab, setTab] = useState<Tab>("queue");
  const [escalations, setEscalations] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  async function fetchEscalations() {
    setLoading(true);
    try {
      const res: any = await api.complaints.list({ status: "ESCALATED" });
      setEscalations(Array.isArray(res) ? res : []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchEscalations();
  }, []);

  // Live Realtime — re-fetch when an escalation arrives
  useEffect(() => {
    const channel = supabase
      .channel("aa-escalations")
      .on(
        "postgres_changes" as any,
        { event: "UPDATE", schema: "public", table: "complaints" },
        (payload: any) => {
          if (payload.new?.status === "ESCALATED") fetchEscalations();
        }
      )
      .subscribe();
    return () => { supabase.removeChannel(channel); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleStatusUpdate(id: string, newStatus: string, proofUrl?: string, note?: string) {
    await api.complaints.updateStatus(id, { new_status: newStatus, internal_note: note, proof_url: proofUrl });
    setSelectedId(null);
    fetchEscalations();
  }

  return (
    <div className="h-full flex flex-col">
      {/* Tabs */}
      <div className="border-b border-gray-200 bg-white px-6 pt-4 shrink-0">
        <h1 className="text-xl font-bold text-gray-900 mb-4">Area Admin Dashboard</h1>
        <div className="flex gap-0">
          {(["queue", "officers"] as Tab[]).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-5 py-2 text-sm font-medium border-b-2 transition-colors ${
                tab === t
                  ? "border-blue-700 text-blue-700"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {t === "queue" ? `Escalation Queue (${escalations.length})` : "Officer Performance"}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto bg-gray-50">
        {tab === "queue" && (
          <div className="max-w-3xl mx-auto py-6 px-4 space-y-3">
            {loading ? (
              <ComplaintListSkeleton />
            ) : escalations.length === 0 ? (
              <EmptyState icon="✅" message="No escalated complaints in your zone. All clear!" />
            ) : (
              escalations.map(c => (
                <div
                  key={c.grievance_id}
                  className="bg-white rounded border border-red-100 hover:bg-gray-50 transition-colors cursor-pointer"
                  onClick={() => setSelectedId(c.grievance_id)}
                >
                  <ComplaintCard complaint={c} pinColor="#EF4444" />
                  <div className="px-4 pb-3 flex gap-2">
                    <button
                      className="text-xs font-medium text-blue-700 hover:text-blue-800 bg-blue-50 px-3 py-1 rounded-md"
                      onClick={e => { e.stopPropagation(); setSelectedId(c.grievance_id); }}
                    >
                      Review &amp; Reassign
                    </button>
                    <button
                      className="text-xs font-medium text-green-700 bg-green-50 px-3 py-1 rounded-md hover:bg-green-100"
                      onClick={async e => {
                        e.stopPropagation();
                        await api.complaints.updateStatus(c.grievance_id, { new_status: "ASSIGNED" });
                        fetchEscalations();
                      }}
                    >
                      Return to JSSA
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {tab === "officers" && (
          <OfficerPerformanceTab />
        )}
      </div>

      {selectedId && (
        <ComplaintDetailPanel
          complaintId={selectedId}
          onClose={() => setSelectedId(null)}
          onStatusUpdate={handleStatusUpdate}
          initialData={escalations.find(c => c.grievance_id === selectedId)}
        />
      )}
    </div>
  );
}

function OfficerPerformanceTab() {
  const [officerId, setOfficerId] = useState("");
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleLookup() {
    if (!officerId.trim()) return;
    setLoading(true);
    setError("");
    try {
      const res = await api.officers.stats(officerId.trim());
      setStats(res);
    } catch (err: any) {
      setError(err.message || "Officer not found");
      setStats(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto py-6 px-4 space-y-4">
      <div className="bg-white rounded border border-gray-200 p-6 space-y-4">
        <h2 className="font-semibold text-gray-900">Officer Performance Lookup</h2>
        <div className="flex gap-2">
          <input
            type="text"
            value={officerId}
            onChange={e => setOfficerId(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleLookup()}
            placeholder="Enter Officer UUID"
            className="flex-1 border border-gray-200 rounded-md p-2 text-sm font-mono focus:ring-2 focus:ring-blue-700 focus:outline-none"
          />
          <button
            onClick={handleLookup}
            disabled={loading || !officerId.trim()}
            className="bg-blue-700 text-white text-sm font-semibold px-4 py-2 rounded-md hover:bg-blue-800 disabled:opacity-50 transition-colors"
          >
            {loading ? "Loading..." : "Look Up"}
          </button>
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
      </div>

      {stats && (
        <div className="bg-white rounded border border-gray-200 p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-gray-100 pb-3">
            <div>
              <h3 className="font-bold text-gray-900 text-lg">{stats.name}</h3>
              <p className="text-xs text-gray-500 capitalize">{stats.role}</p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            {[
              { label: "Total Assigned", value: stats.total_assigned, color: "text-blue-700" },
              { label: "Total Resolved", value: stats.total_resolved, color: "text-green-700" },
              { label: "Total Escalated", value: stats.total_escalated, color: "text-red-600" },
              { label: "Avg Resolution", value: stats.avg_resolution_hours + "h", color: "text-amber-700" },
            ].map((s, i) => (
              <div key={i} className="bg-gray-50 rounded-lg p-4 border border-gray-100">
                <p className="text-xs text-gray-500 font-medium">{s.label}</p>
                <p className={`text-2xl font-bold mt-1 ${s.color}`}>{s.value}</p>
              </div>
            ))}
          </div>
          <div className={`text-center py-3 rounded-lg border-2 ${
            stats.reopen_rate_pct < 10 ? "bg-green-50 border-green-200" :
            stats.reopen_rate_pct < 25 ? "bg-amber-50 border-amber-200" :
            "bg-red-50 border-red-200"
          }`}>
            <p className="text-xs font-semibold text-gray-600">Reopen Rate</p>
            <p className={`text-3xl font-bold ${
              stats.reopen_rate_pct < 10 ? "text-green-700" :
              stats.reopen_rate_pct < 25 ? "text-amber-700" : "text-red-700"
            }`}>{stats.reopen_rate_pct}%</p>
          </div>
        </div>
      )}
    </div>
  );
}
