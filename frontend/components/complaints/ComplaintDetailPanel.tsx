"use client";
import React, { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { StatusBadge } from "./StatusBadge";
import { Timeline } from "./Timeline";
import { SLABar } from "./SLABar";
import { Sheet, SheetContent, SheetHeader } from "@/components/ui/sheet";
import { PanelSkeleton } from "@/components/ui/SkeletonLoader";

function ProofUploader({ onUploaded }: { onUploaded: (url: string) => void }) {
  const [uploading, setUploading] = useState(false);
  
  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const { upload_url, file_path } = await api.complaints.getUploadUrl();
      await fetch(upload_url, { method: "PUT", body: file, headers: { "Content-Type": file.type } });
      onUploaded(file_path);
    } catch (err) {
      console.error(err);
      alert("Failed to upload file");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="border border-dashed border-gray-200 rounded p-4 text-center">
      <p className="text-xs text-gray-500 mb-2">Upload Proof Photo</p>
      <input type="file" accept="image/*" onChange={handleFile} disabled={uploading} className="text-xs w-full" />
      {uploading && <p className="text-xs text-blue-700 mt-1">Uploading...</p>}
    </div>
  );
}

export function ComplaintDetailPanel({ complaintId, onClose, onStatusUpdate, initialData }: { complaintId: string, onClose: () => void, onStatusUpdate: any, initialData?: any }) {
  const [complaint, setComplaint] = useState<any>(initialData || null);
  const [nextStatus, setNextStatus] = useState("");
  const [proofUrl,   setProofUrl]   = useState("");
  const [note,       setNote]       = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!initialData) {
      api.complaints.get(complaintId).then(setComplaint).catch(console.error);
    } else {
      setComplaint(initialData);
    }
  }, [complaintId, initialData]);

  if (!complaint) return (
    <Sheet open onOpenChange={onClose}>
      <SheetContent className="w-[480px] sm:w-[540px]">
         <PanelSkeleton />
      </SheetContent>
    </Sheet>
  );

  // Fallback valid transitions
  const VALID_TRANSITIONS: Record<string, string[]> = {
    "NEW": ["CLASSIFIED"],
    "CLASSIFIED": ["ASSIGNED"],
    "ASSIGNED": ["IN_PROGRESS", "ESCALATED"],
    "IN_PROGRESS": ["MID_SURVEY_PENDING", "ESCALATED"],
    "MID_SURVEY_PENDING": ["FINAL_SURVEY_PENDING"],
    "FINAL_SURVEY_PENDING": ["CLOSED", "REOPENED", "CLOSED_UNVERIFIED"],
    "ESCALATED": ["ASSIGNED", "CLOSED"],
    "REOPENED": ["ASSIGNED", "ESCALATED"],
  };
  
  const validNextStates = VALID_TRANSITIONS[complaint.status] || [];
  const proofRequired   = ["IN_PROGRESS", "FINAL_SURVEY_PENDING"].includes(nextStatus);

  return (
    <Sheet open onOpenChange={onClose}>
      <SheetContent className="w-[480px] sm:w-[540px] overflow-y-auto">
        <SheetHeader className="text-left flex flex-row items-center justify-between">
          <code className="text-xs font-mono text-gray-500">{complaint.grievance_id}</code>
          <StatusBadge status={complaint.status} />
        </SheetHeader>

        <div className="space-y-6 mt-6">
          <div className="space-y-2">
            <h3 className="font-semibold text-gray-900">{complaint.category || "Unknown Category"}</h3>
            <p className="text-sm text-gray-700">{complaint.translated_text || complaint.raw_text}</p>
            {complaint.raw_text && complaint.raw_text !== complaint.translated_text && (
              <p className="text-xs text-gray-400 italic">Original: {complaint.raw_text}</p>
            )}
          </div>

          <div className="space-y-1">
            <h4 className="text-xs font-semibold uppercase text-gray-500">SLA Tracking</h4>
            {complaint.sla_deadline && (
              <SLABar deadline={complaint.sla_deadline} createdAt={complaint.created_at || new Date().toISOString()} />
            )}
          </div>

          {validNextStates.length > 0 && (
            <div className="border border-gray-200 bg-gray-50 rounded-lg p-4 space-y-3">
              <label className="text-xs font-semibold uppercase text-gray-600 block">Update Status Action</label>
              <select 
                className="w-full border border-gray-200 bg-white rounded-md p-2 text-sm focus:ring-2 focus:ring-blue-700 focus:outline-none"
                value={nextStatus} 
                onChange={e => setNextStatus(e.target.value)}
              >
                <option value="">Select next status...</option>
                {validNextStates.map(s => <option key={s} value={s}>{s}</option>)}
              </select>

              {proofRequired && (
                <ProofUploader onUploaded={setProofUrl} />
              )}
              {proofUrl && <p className="text-xs text-green-600">✓ Proof photo uploaded</p>}

              <textarea
                className="w-full border border-gray-200 rounded-md p-2 text-sm focus:ring-2 focus:ring-blue-700 focus:outline-none"
                placeholder="Internal note (optional)"
                value={note} 
                onChange={e => setNote(e.target.value)}
                rows={2}
              />

              <button
                disabled={!nextStatus || (proofRequired && !proofUrl) || submitting}
                onClick={async () => {
                  setSubmitting(true);
                  try {
                    await onStatusUpdate(complaintId, nextStatus, proofUrl, note);
                    onClose();
                  } catch(e) { 
                    console.error(e); 
                    alert("Failed to update status");
                  } finally {
                    setSubmitting(false);
                  }
                }}
                className="w-full bg-blue-700 text-white text-sm font-semibold py-2 rounded-md disabled:opacity-50 hover:bg-blue-800 transition-colors"
              >
                {submitting ? "Updating..." : "Submit Update"}
              </button>
            </div>
          )}

          <div className="space-y-3">
            <h4 className="text-xs font-semibold uppercase text-gray-500 border-b border-gray-200 pb-2">Event Timeline</h4>
            <Timeline events={complaint.timeline || [{ to_status: complaint.status, created_at: complaint.created_at }]} />
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
