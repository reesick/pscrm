"use client";
import React, { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { useUser } from "@/app/(dashboard)/layout";
import { StatusBadge } from "@/components/complaints/StatusBadge";
import { SLACountdown } from "@/components/complaints/SLABar";
import { ComplaintListSkeleton } from "@/components/ui/SkeletonLoader";
import { EmptyState } from "@/components/ui/EmptyState";

type Tab = "tasks" | "scorecard";

export default function ContractorPortal() {
  const { userId } = useUser();
  const [tab, setTab] = useState<Tab>("tasks");
  const [workOrders, setWorkOrders] = useState<any[]>([]);
  const [scorecard, setScorecard] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  async function loadData() {
    setLoading(true);
    try {
      // Backend scopes list to this contractor's assigned work orders
      const [res, sc] = await Promise.all([
        api.complaints.list().catch(() => []),
        api.contractors.scorecard(userId).catch(() => null),
      ]);
      setWorkOrders(Array.isArray(res) ? res : []);
      setScorecard(sc);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadData(); }, [userId]);

  async function handleProofUpload(complaintId: string) {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/*";
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) return;
      try {
        const { upload_url, file_path } = await api.complaints.getUploadUrl();
        await fetch(upload_url, { method: "PUT", body: file, headers: { "Content-Type": file.type } });
        await api.complaints.updateStatus(complaintId, {
          new_status: "IN_PROGRESS",
          proof_url: file_path,
        });
        loadData();
        alert("Proof photo uploaded and status updated to In Progress.");
      } catch (err) {
        alert("Upload failed. Please try again.");
      }
    };
    input.click();
  }

  return (
    <div className="h-full flex flex-col">
      <div className="px-6 py-5 border-b border-gray-200 bg-white shrink-0">
        <h1 className="text-xl font-bold text-gray-900">Contractor Portal</h1>
        <p className="text-sm text-gray-500 mt-1">Your assigned work orders and performance record.</p>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 bg-white px-6 flex shrink-0">
        {(["tasks", "scorecard"] as Tab[]).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-5 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t ? "border-blue-700 text-blue-700" : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {t === "tasks" ? `My Work Orders (${workOrders.length})` : "My Scorecard"}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto bg-gray-50">
        {/* Work Orders Tab */}
        {tab === "tasks" && (
          <div className="max-w-3xl mx-auto py-6 px-4 space-y-4">
            {loading ? (
              <ComplaintListSkeleton />
            ) : workOrders.length === 0 ? (
              <EmptyState icon="🚧" message="No work orders assigned yet. Check back soon." />
            ) : (
              workOrders.map(c => (
                <div key={c.grievance_id} className="bg-white rounded border border-gray-200 p-5 space-y-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <code className="text-xs text-gray-400 font-mono">{c.grievance_id}</code>
                      <p className="font-semibold text-gray-900 mt-0.5">{c.category || "Unknown Category"}</p>
                      <p className="text-sm text-gray-600 mt-1">{c.translated_text || c.raw_text}</p>
                    </div>
                    <StatusBadge status={c.status} />
                  </div>

                  {c.sla_deadline && (
                    <div className="bg-amber-50 rounded-lg px-3 py-2 border border-amber-100">
                      <SLACountdown deadline={c.sla_deadline} />
                    </div>
                  )}

                  <div className="flex gap-2 pt-1">
                    {["ASSIGNED", "NEW"].includes(c.status) && (
                      <button
                        onClick={() => handleProofUpload(c.grievance_id)}
                        className="text-xs font-semibold bg-blue-700 text-white px-3 py-1.5 rounded-md hover:bg-blue-800 transition-colors"
                      >
                        Upload Mid-Job Photo
                      </button>
                    )}
                    {c.status === "IN_PROGRESS" && (
                      <button
                        onClick={() => handleProofUpload(c.grievance_id)}
                        className="text-xs font-semibold bg-green-600 text-white px-3 py-1.5 rounded-md hover:bg-green-700 transition-colors"
                      >
                        Upload Final Proof
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* Scorecard Tab */}
        {tab === "scorecard" && (
          <div className="max-w-2xl mx-auto py-6 px-4">
            {loading ? (
              <div className="bg-white rounded border border-gray-200 p-6 animate-pulse space-y-3">
                <div className="h-4 bg-gray-200 rounded w-1/3" />
                <div className="h-8 bg-gray-100 rounded w-full" />
              </div>
            ) : !scorecard ? (
              <EmptyState icon="📉" message="Scorecard not available yet. Complete some work orders first." />
            ) : (
                  <div className="bg-white rounded border border-gray-200 p-6 space-y-6">
                <h2 className="font-bold text-gray-900 text-lg">{scorecard.name}</h2>

                <div className="grid grid-cols-2 gap-4">
                  {[
                    { label: "Tasks Assigned", value: scorecard.tasks_assigned },
                    { label: "On-time Completion", value: scorecard.on_time_pct + "%" },
                    { label: "Citizen Rejection Rate", value: scorecard.rejection_rate_pct + "%" },
                    { label: "Reopen Rate", value: scorecard.reopen_rate_pct + "%" },
                  ].map((s, i) => (
                    <div key={i} className="bg-gray-50 rounded-lg p-4 border border-gray-100">
                      <p className="text-xs text-gray-500 font-medium">{s.label}</p>
                      <p className="text-2xl font-bold text-gray-900 mt-1">{s.value}</p>
                    </div>
                  ))}
                </div>

                <div className={`rounded p-5 text-center border-2 ${
                  scorecard.reliability_score >= 80 ? "bg-green-50 border-green-200" :
                  scorecard.reliability_score >= 50 ? "bg-amber-50 border-amber-200" :
                  "bg-red-50 border-red-200"
                }`}>
                  <p className="text-sm font-semibold text-gray-600 mb-1">Reliability Score</p>
                  <p className={`text-5xl font-bold ${
                    scorecard.reliability_score >= 80 ? "text-green-700" :
                    scorecard.reliability_score >= 50 ? "text-amber-700" : "text-red-700"
                  }`}>{scorecard.reliability_score}<span className="text-2xl">/100</span></p>
                  <p className="text-xs text-gray-500 mt-2">
                    Formula: (on-time × 0.4) + (1 − rejection × 0.35) + (1 − reopen × 0.25)
                  </p>
                </div>

                {!scorecard.is_active && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
                    ⚠ Your account is currently <strong>deactivated</strong>. Contact the Super Admin for details.
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

