"use client";
import { useEffect, useState } from "react";

type AdminGuardOptions = {
  skipOnboardingCheck?: boolean;
};

/**
 * Client-only guard that redirects to /roksell/login if no admin session exists.
 * Returns true when it is safe to render the protected page.
 */
export function useAdminGuard(options: AdminGuardOptions = {}) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let active = true;
    async function check() {
      try {
        const res = await fetch("/api/auth/me", { credentials: "include" });
        if (!res.ok) {
          window.location.href = "/roksell/login";
          return;
        }
        if (!options.skipOnboardingCheck) {
          const path = window.location.pathname;
          const isOnboardingPage = path.startsWith("/roksell/primeiro-acesso");
          if (!isOnboardingPage) {
            try {
              const onboardingRes = await fetch("/api/admin/onboarding/state", { credentials: "include" });
              if (onboardingRes.ok) {
                const onboarding = await onboardingRes.json();
                if (onboarding?.needs_onboarding) {
                  window.location.href = "/roksell/primeiro-acesso";
                  return;
                }
              }
            } catch {
              // ignore onboarding check failures to avoid blocking the portal
            }
          }
        }
        if (active) setReady(true);
      } catch {
        window.location.href = "/roksell/login";
      }
    }
    check();
    return () => {
      active = false;
    };
  }, [options.skipOnboardingCheck]);

  return ready;
}
