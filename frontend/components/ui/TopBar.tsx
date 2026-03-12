"use client";
import React, { useState } from 'react';
import { usePathname } from 'next/navigation';

const PATH_TITLES: Record<string, string> = {
  '/dashboard/jssa':        'Ward Dashboard',
  '/dashboard/aa':          'Area Admin',
  '/dashboard/faa':         'First Appellate Authority',
  '/dashboard/super-admin': 'Analytics & Administration',
  '/dashboard/contractor':  'Contractor Portal',
};

export function TopBar({ user, notificationCount = 0 }: { user: any; notificationCount?: number }) {
  const pathname = usePathname();
  const title = Object.entries(PATH_TITLES).find(([k]) => pathname.startsWith(k))?.[1] ?? 'Dashboard';

  return (
    <header className="h-14 border-b border-gray-200 bg-white flex items-center justify-between px-6 shrink-0 sticky top-0 z-10 w-full">
      {/* Page title */}
      <h1 className="font-semibold text-gray-900 text-lg">{title}</h1>

      {/* Global search */}
      <div className="hidden md:flex items-center flex-1 max-w-sm mx-6">
        <div className="relative w-full">
          <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M11 19a8 8 0 100-16 8 8 0 000 16z" />
          </svg>
          <input
            type="text"
            placeholder="Search complaints…"
            className="w-full pl-9 pr-3 py-1.5 text-sm border border-gray-200 rounded-md bg-gray-50 focus:bg-white focus:ring-2 focus:ring-blue-700 focus:outline-none transition-colors"
          />
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* Notification bell */}
        <button className="relative p-2 rounded hover:bg-gray-100 transition-colors" aria-label="Notifications">
          <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
          </svg>
          {notificationCount > 0 && (
            <span className="absolute top-1 right-1 w-4 h-4 bg-blue-700 text-white text-[10px] font-bold rounded-full flex items-center justify-center leading-none">
              {notificationCount > 9 ? '9+' : notificationCount}
            </span>
          )}
        </button>

        {/* User avatar */}
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-700 font-semibold text-sm uppercase">
            {user?.user_metadata?.name?.[0] || user?.email?.[0] || 'U'}
          </div>
          <span className="text-sm text-gray-600 hidden md:block">{user?.user_metadata?.name || user?.email}</span>
        </div>
      </div>
    </header>
  );
}
