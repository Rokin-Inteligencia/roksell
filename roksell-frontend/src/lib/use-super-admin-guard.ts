"use client";

import { useEffect, useState } from "react";
import { clearAdminToken, clearTenantSlug, getTenantSlug } from "@/lib/admin-auth";

const SUPER_ADMIN_SLUG = process.env.NEXT_PUBLIC_SUPER_ADMIN_SLUG || "rokin";

/**
 * Guard for /admin routes - requires a logged in user from the super admin tenant.
 */
export function useSuperAdminGuard() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let active = true;
    async function check() {
      try {
        const res = await fetch("/api/auth/me", { credentials: "include" });
        const tenantSlug = getTenantSlug();
        if (!res.ok || !tenantSlug || tenantSlug !== SUPER_ADMIN_SLUG) {
          clearAdminToken();
          clearTenantSlug();
          window.location.href = "/admin/login";
          return;
        }
        if (active) setReady(true);
      } catch {
        clearAdminToken();
        clearTenantSlug();
        window.location.href = "/admin/login";
      }
    }
    check();
    return () => {
      active = false;
    };
  }, []);

  return ready;
}
