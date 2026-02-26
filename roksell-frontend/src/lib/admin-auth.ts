function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const target = `${name}=`;
  const parts = document.cookie.split("; ");
  for (const part of parts) {
    if (part.startsWith(target)) {
      return decodeURIComponent(part.slice(target.length));
    }
  }
  return null;
}

export function getAdminToken(): string | null {
  // Token in HttpOnly cookie is not accessible via JS.
  return null;
}

export function clearAdminToken() {
  if (typeof window === "undefined") return;
  fetch("/api/auth/logout", { method: "POST", credentials: "include" }).catch(() => {});
  clearTenantSlug();
}

export function getTenantSlug(): string | null {
  return readCookie("tenant_slug");
}

export function clearTenantSlug() {
  if (typeof window === "undefined") return;
  const secure = window.location.protocol === "https:";
  const secureFlag = secure ? "; secure" : "";
  document.cookie = `tenant_slug=; path=/; max-age=0; samesite=lax${secureFlag}`;
}
