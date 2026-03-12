import { createMiddlewareClient } from "@supabase/auth-helpers-nextjs";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export async function middleware(req: NextRequest) {
  const res  = NextResponse.next();
  const supabase = createMiddlewareClient({ req, res });

  // Refresh session if expired (Supabase handles token rotation)
  const { data: { session } } = await supabase.auth.getSession();

  const isProtected = req.nextUrl.pathname.startsWith("/dashboard");
  const isAuthPage  = req.nextUrl.pathname === "/login";

  // Not logged in → redirect to login
  if (isProtected && !session) {
    return NextResponse.redirect(new URL("/login", req.url));
  }

  // Logged in + on login page → redirect to correct dashboard
  if (isAuthPage && session) {
    const role = session.user.user_metadata?.role ?? "jssa";
    return NextResponse.redirect(new URL(`/dashboard/${role}`, req.url));
  }

  // Role-gating: prevent JSSA from accessing /dashboard/super-admin etc.
  if (isProtected && session) {
    const role = session.user.user_metadata?.role;
    const path = req.nextUrl.pathname;

    const ROLE_PATHS: Record<string, string> = {
      jssa:        "/dashboard/jssa",
      aa:          "/dashboard/aa",
      faa:         "/dashboard/faa",
      super_admin: "/dashboard/super-admin",
      contractor:  "/dashboard/contractor",
    };

    const allowedBase = ROLE_PATHS[role];
    if (allowedBase && !path.startsWith(allowedBase)) {
      return NextResponse.redirect(new URL(allowedBase, req.url));
    }
  }

  return res;
}

export const config = {
  matcher: ["/dashboard", "/dashboard/:path*", "/login"],
};
