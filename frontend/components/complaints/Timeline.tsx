import React from 'react';

export function Timeline({ events = [] }: { events?: any[] }) {
  if (!events || events.length === 0) {
    return <div className="text-gray-500 text-sm">No events found.</div>;
  }

  return (
    <div className="relative border-l border-gray-200 ml-3 space-y-4">
      {events.map((e, idx) => (
        <div key={idx} className="relative pl-6">
          <span className="absolute -left-1.5 top-1.5 w-3 h-3 bg-blue-500 rounded-full border-2 border-white" />
          <div className="text-sm">
            <p className="font-semibold text-gray-900">{e.event_type || e.to_status}</p>
            <p className="text-gray-500 text-xs mt-0.5">
              {e.created_at ? new Date(e.created_at).toLocaleString() : ""}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
