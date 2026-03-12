"use client";
import React, { useState, useEffect } from 'react';

function computeTimeLeft(deadline: string) {
  return (new Date(deadline).getTime() - Date.now()) / 1000;
}

export function SLACountdown({ deadline }: { deadline: string }) {
  const [timeLeft, setTimeLeft] = useState(computeTimeLeft(deadline));
  
  useEffect(() => {
    const interval = setInterval(() => setTimeLeft(computeTimeLeft(deadline)), 60000);
    return () => clearInterval(interval);
  }, [deadline]);

  if (timeLeft <= 0) return <p className="text-red-600 text-sm">SLA breached</p>;
  const hours = Math.floor(timeLeft / 3600);
  return <p className="text-sm text-amber-600">{hours} hours remaining within SLA</p>;
}

export function SLABar({ deadline, createdAt }: { deadline: string; createdAt: string }) {
  const totalDuration = new Date(deadline).getTime() - new Date(createdAt).getTime();
  const rawElapsed = Date.now() - new Date(createdAt).getTime();
  const elapsed = Math.max(0, rawElapsed);
  
  const pct = Math.min(100, Math.max(0, (elapsed / totalDuration) * 100));
  
  const bg = pct >= 100 ? "bg-red-500" : pct > 80 ? "bg-orange-500" : "bg-green-500";
  
  return (
    <div className="w-full bg-gray-200 rounded-full h-2.5 mt-2 overflow-hidden">
      <div className={`h-2.5 rounded-full ${bg} transition-all duration-500`} style={{ width: pct + "%" }}></div>
    </div>
  );
}
