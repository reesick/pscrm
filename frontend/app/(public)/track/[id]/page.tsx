"use client";
import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { StatusBadge } from "@/components/complaints/StatusBadge";
import { Timeline } from "@/components/complaints/Timeline";
import { SLACountdown } from "@/components/complaints/SLABar";
import { EmptyState } from "@/components/ui/EmptyState";
import Link from "next/link";
import { use } from "react";

export default function TrackPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [complaint, setComplaint] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.complaints.get(id)
      .then(setComplaint)
      .catch(() => setComplaint(null))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="p-12 text-center text-gray-500">Loading complaint details...</div>;
  if (!complaint) return <div className="pt-20"><EmptyState icon="🔍" message="Grievance not found. Please check the ID and try again." /></div>;

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="max-w-xl mx-auto space-y-6">
        <Link href="/" className="text-sm font-medium text-blue-700 hover:underline flex items-center gap-1">
          ← Back to Search
        </Link>
        
          <div className="bg-white border border-gray-200 rounded p-6 space-y-6">
          <div className="flex flex-col gap-2 border-b border-gray-100 pb-4">
            <div className="flex items-center justify-between">
              <h1 className="text-xl font-bold font-mono text-gray-900">{complaint.grievance_id}</h1>
              <StatusBadge status={complaint.status} />
            </div>
            <div className="text-sm text-gray-600">
              <span className="font-semibold text-gray-800">Category:</span> {complaint.category || "Unknown"}
            </div>
            <div className="text-sm text-gray-600">
              <span className="font-semibold text-gray-800">Departments:</span> {complaint.department_names?.join(", ") || "Unassigned"}
            </div>
          </div>

          {complaint.sla_deadline && !["CLOSED", "CLOSED_UNVERIFIED"].includes(complaint.status) && (
            <div className="bg-amber-50 rounded-lg p-4 border border-amber-100">
              <SLACountdown deadline={complaint.sla_deadline} />
            </div>
          )}

          <div>
             <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <span className="w-5 h-5 flex items-center justify-center bg-gray-100 rounded text-xs border border-gray-200">🕒</span>
                Timeline
             </h3>
             <Timeline events={complaint.timeline || [{ to_status: complaint.status, created_at: complaint.created_at }]} />
          </div>
        </div>
      </div>
    </div>
  );
}
