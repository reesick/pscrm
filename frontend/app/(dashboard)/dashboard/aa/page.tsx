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
          <div className="max-w-4xl mx-auto py-6 px-4">
              <div className="bg-white rounded border border-gray-200 p-6">
              <h2 className="font-semibold text-gray-900 mb-2">Officer Performance</h2>
              <p className="text-sm text-gray-500 mb-4">
                Select an officer to view their stats. Individual officer IDs must be provided — a
                bulk officer-list endpoint is on the backend roadmap.
              </p>
              <EmptyState icon="📊" message="Officer stats are available via /officers/{id}/stats. A bulk officer list endpoint will be added in the next sprint." />
            </div>
          </div>
        )}
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

