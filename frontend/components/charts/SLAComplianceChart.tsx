import React from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

export function SLAComplianceChart({ data }: { data: any[] }) {
  if (!data || data.length === 0) {
    return <div className="h-[220px] flex items-center justify-center text-sm text-gray-400 border border-dashed border-gray-200 rounded-lg">No SLA data available</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 20, left: 10, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" horizontal={false} />
        <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11, fill: '#6B7280' }} unit="%" axisLine={false} tickLine={false} />
        <YAxis dataKey="department_name" type="category" tick={{ fontSize: 11, fill: '#6B7280' }} width={90} axisLine={false} tickLine={false} />
        <Tooltip formatter={(v: any) => Number(v).toFixed(1) + "%"} cursor={{ fill: '#F3F4F6' }} contentStyle={{ fontSize: '12px', borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
        <Bar dataKey="compliance_pct" fill="#10B981" radius={[0, 4, 4, 0]} barSize={20} />
      </BarChart>
    </ResponsiveContainer>
  );
}
