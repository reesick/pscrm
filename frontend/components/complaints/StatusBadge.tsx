import React from 'react';

const STATUS_STYLES: Record<string, { bg: string; text: string; label: string; extra?: string }> = {
  NEW:                   { bg: "bg-gray-100",   text: "text-gray-700",   label: "NEW" },
  CLASSIFIED:            { bg: "bg-blue-50",    text: "text-blue-700",   label: "CLASSIFIED" },
  ASSIGNED:              { bg: "bg-blue-50",    text: "text-blue-700",   label: "ASSIGNED" },
  IN_PROGRESS:           { bg: "bg-amber-100",  text: "text-amber-800",  label: "IN PROGRESS" },
  MID_SURVEY_PENDING:    { bg: "bg-amber-50",   text: "text-amber-700",  label: "MID SURVEY" },
  FINAL_SURVEY_PENDING:  { bg: "bg-purple-100", text: "text-purple-800", label: "FINAL SURVEY" },
  ESCALATED:             { bg: "bg-red-100",    text: "text-red-800",    label: "ESCALATED" },
  REOPENED:              { bg: "bg-red-100",   text: "text-red-700",    label: "REOPENED", extra: "border border-dashed border-red-400" },
  CLOSED:                { bg: "bg-green-100",  text: "text-green-800",  label: "CLOSED" },
  CLOSED_UNVERIFIED:     { bg: "bg-gray-100",   text: "text-gray-500",   label: "UNVERIFIED" },
};

export function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] ?? STATUS_STYLES["NEW"];
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold uppercase tracking-wide ${style.bg} ${style.text} ${style.extra ?? ""}`}>
      {style.label}
    </span>
  );
}
