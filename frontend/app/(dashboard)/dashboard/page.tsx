"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";

const ROLE_PATHS: Record<string, string> = {
  jssa: "/dashboard/jssa",
  aa: "/dashboard/aa",
  faa: "/dashboard/faa",
  super_admin: "/dashboard/super-admin",
  contractor: "/dashboard/contractor",
};

export default function DashboardRedirect() {
  const router = useRouter();

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) {
        router.replace("/login");
        return;
      }
      const role = session.user.user_metadata?.role ?? "jssa";
      router.replace(ROLE_PATHS[role] ?? "/dashboard/jssa");
    });
  }, [router]);

  return (
    <div className="h-full flex items-center justify-center text-gray-500 text-sm">
      Redirecting…
    </div>
  );
}
