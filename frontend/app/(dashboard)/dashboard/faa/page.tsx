"use client";
import React, { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { ComplaintCard } from "@/components/complaints/ComplaintCard";
import { ComplaintDetailPanel } from "@/components/complaints/ComplaintDetailPanel";
import { ComplaintListSkeleton } from "@/components/ui/SkeletonLoader";
import { EmptyState } from "@/components/ui/EmptyState";

export default function FAADashboard() {
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

  useEffect(() => { fetchEscalations(); }, []);

  async function handleStatusUpdate(id: string, newStatus: string, proofUrl?: string, note?: string) {
    await api.complaints.updateStatus(id, { new_status: newStatus, internal_note: note, proof_url: proofUrl });
    setSelectedId(null);
    fetchEscalations();
  }

  return (
    <div className="h-full flex flex-col">
      <div className="px-6 py-5 border-b border-gray-200 bg-white shrink-0">
        <h1 className="text-xl font-bold text-gray-900">First Appellate Authority</h1>
        <p className="text-sm text-gray-500 mt-1">
          Severe escalations that have exceeded AA-level resolution deadline.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto bg-gray-50">
        <div className="max-w-3xl mx-auto py-6 px-4 space-y-3">
          {loading ? (
            <ComplaintListSkeleton />
          ) : escalations.length === 0 ? (
            <EmptyState icon="⚖️" message="No complaints at the FAA level. Good governance!" />
          ) : (
            escalations.map(c => (
              <div
                key={c.grievance_id}
                className="bg-white rounded border border-orange-100 hover:bg-gray-50 transition-colors cursor-pointer"
                onClick={() => setSelectedId(c.grievance_id)}
              >
                <ComplaintCard complaint={c} pinColor="#F97316" />
                <div className="px-4 pb-3 flex gap-2">
                  <button
                    className="text-xs font-medium text-blue-700 bg-blue-50 px-3 py-1 rounded-md hover:bg-blue-100"
                    onClick={e => { e.stopPropagation(); setSelectedId(c.grievance_id); }}
                  >
                    Review Details
                  </button>
                  <button
                    className="text-xs font-medium text-purple-700 bg-purple-50 px-3 py-1 rounded-md hover:bg-purple-100"
                    onClick={async e => {
                      e.stopPropagation();
                      // Initiate tender: update note then close for procurement
                      await api.complaints.updateStatus(c.grievance_id, {
                        new_status: "ASSIGNED",
                        internal_note: "Tender initiated by FAA — procurement team notified.",
                      });
                      fetchEscalations();
                    }}
                  >
                    Initiate Tender
                  </button>
                  <button
                    className="text-xs font-medium text-green-700 bg-green-50 px-3 py-1 rounded-md hover:bg-green-100"
                    onClick={async e => {
                      e.stopPropagation();
                      await api.complaints.updateStatus(c.grievance_id, {
                        new_status: "CLOSED",
                        internal_note: "Resolved directly at FAA level.",
                      });
                      fetchEscalations();
                    }}
                  >
                    Resolve Directly
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
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

