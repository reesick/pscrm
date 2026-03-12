import React from 'react';
import { StatusBadge } from './StatusBadge';

export function ComplaintCard({ complaint, onClick, pinColor }: { complaint: any; onClick?: () => void; pinColor?: string }) {
  if (!complaint) return null;

  return (
    <div 
      onClick={onClick}
      className="p-4 border-b border-gray-100 hover:bg-gray-50 cursor-pointer transition-colors"
    >
      <div className="flex items-start gap-3">
        {pinColor && (
          <div className="w-3 h-3 rounded-full mt-1.5 flex-shrink-0" style={{ backgroundColor: pinColor }} />
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2 mb-1">
            <code className="text-xs font-mono text-gray-500 truncate">{complaint.grievance_id}</code>
            <StatusBadge status={complaint.status} />
          </div>
          <p className="text-sm font-medium text-gray-900 truncate">
            {complaint.category || "Unknown Category"}
          </p>
          <p className="text-xs text-gray-500 mt-1 truncate">
            {complaint.translated_text || complaint.raw_text}
          </p>
          <div className="flex items-center gap-3 mt-2 text-[11px] text-gray-400">
             <span>Urgency: {complaint.urgency || "?"}/5</span>
             {complaint.sla_deadline && (
                <span>SLA: {new Date(complaint.sla_deadline).toLocaleDateString()}</span>
             )}
          </div>
        </div>
      </div>
    </div>
  );
}
