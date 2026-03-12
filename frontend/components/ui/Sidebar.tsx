"use client";
import Link from 'next/link';
import React from 'react';
import { usePathname } from 'next/navigation';

export function Sidebar({ navItems = [], role = 'user', user }: { navItems: any[], role: string, user: any }) {
  const pathname = usePathname();

  return (
    <aside className="w-60 bg-[#F9FAFB] border-r border-gray-200 h-full flex flex-col shrink-0">
      {/* Logo */}
      <div className="px-5 py-4 border-b border-gray-200">
        <span className="font-bold text-base text-gray-900 tracking-tight">PS-CRM</span>
        <span className="ml-2 text-xs text-gray-400 font-normal">Delhi MCD</span>
      </div>

      {/* Nav items */}
      <nav className="flex-1 px-3 py-3 space-y-0.5">
        {navItems.map((item, idx) => {
          const isActive = pathname === item.href || pathname.startsWith(item.href + '/');
          return (
            <Link
              key={idx}
              href={item.href}
              className={`relative flex items-center gap-3 px-3 py-2 text-sm font-medium rounded transition-colors ${
                isActive
                  ? 'bg-blue-50 text-blue-700'
                  : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
              }`}
            >
              {/* Accent left border indicator for active item */}
              {isActive && (
                <span className="absolute left-0 top-1 bottom-1 w-0.5 bg-blue-700 rounded-full" />
              )}
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* User footer */}
      <div className="px-4 py-4 border-t border-gray-200 text-sm">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-full bg-blue-100 flex items-center justify-center text-blue-700 text-xs font-bold shrink-0 uppercase">
            {user?.user_metadata?.name?.[0] || user?.email?.[0] || 'U'}
          </div>
          <div className="min-w-0">
            <p className="font-semibold text-gray-900 truncate text-sm">{user?.user_metadata?.name || user?.email || 'User'}</p>
            <p className="text-gray-500 capitalize text-xs">{role}</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
