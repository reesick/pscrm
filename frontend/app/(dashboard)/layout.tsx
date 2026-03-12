"use client";
import React, { useEffect, useState, createContext, useContext } from "react";
import { Sidebar } from "@/components/ui/Sidebar";
import { TopBar } from "@/components/ui/TopBar";
import { supabase } from "@/lib/supabase";
import { useRouter } from "next/navigation";

// ── User context — available to all child dashboard pages ─────────────
interface UserContextType {
  role: string;
  userId: string;
  wardId: string | null;
  zoneWardIds: string[];
  user: any;
}

export const UserContext = createContext<UserContextType | null>(null);

export function useUser(): UserContextType {
  const ctx = useContext(UserContext);
  if (!ctx) throw new Error("useUser must be called inside DashboardLayout");
  return ctx;
}

// ── Role → nav items mapping ──────────────────────────────────────────
const ROLE_NAV: Record<string, { label: string; href: string }[]> = {
  jssa: [
    { label: "Ward Map & Tasks", href: "/dashboard/jssa" },
  ],
  aa: [
    { label: "Escalation Queue",     href: "/dashboard/aa" },
    { label: "Officer Performance",  href: "/dashboard/aa" },
  ],
  faa: [
    { label: "Escalation Queue", href: "/dashboard/faa" },
  ],
  super_admin: [
    { label: "Analytics Hub",  href: "/dashboard/super-admin" },
    { label: "Contractors",    href: "/dashboard/super-admin" },
    { label: "Hotspots",       href: "/dashboard/super-admin" },
  ],
  contractor: [
    { label: "My Work Orders", href: "/dashboard/contractor" },
    { label: "My Scorecard",   href: "/dashboard/contractor" },
  ],
};

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    supabase.auth.getSession().then((res: any) => {
      const session = res.data?.session;
      if (!session) {
        router.push("/login");
      } else {
        setUser(session.user);
      }
      setLoading(false);
    });
  }, [router]);

  if (loading) return (
    <div className="h-screen flex items-center justify-center bg-gray-50 text-gray-500 font-medium">
      Authenticating…
    </div>
  );
  if (!user) return null;

  const role        = user.user_metadata?.role || "jssa";
  const userId      = user.id as string;
  const wardId      = user.user_metadata?.ward_id ?? (user.user_metadata?.ward_ids?.[0] ?? null) as string | null;
  const zoneWardIds: string[] = user.user_metadata?.zone_ward_ids ?? user.user_metadata?.ward_ids ?? [];
  const navItems    = ROLE_NAV[role] ?? [];

  return (
    <UserContext.Provider value={{ role, userId, wardId, zoneWardIds, user }}>
      <div className="flex h-screen overflow-hidden bg-gray-50 text-gray-900">
        <Sidebar navItems={navItems} role={role} user={user} />
        <div className="flex-1 flex flex-col min-w-0">
          <TopBar user={user} />
          <main className="flex-1 overflow-auto relative rounded-tl-xl border-t border-l border-gray-200 bg-white">
            {children}
          </main>
        </div>
      </div>
    </UserContext.Provider>
  );
}
