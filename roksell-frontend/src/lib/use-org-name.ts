import { useEffect, useMemo, useState } from "react";

function isRecord(val: unknown): val is Record<string, unknown> {
  return typeof val === "object" && val !== null;
}

function readName(obj: unknown): string | null {
  if (!isRecord(obj)) return null;
  const name = obj["name"];
  return typeof name === "string" && name.trim() ? name : null;
}

function extractTenantName(data: unknown): string | null {
  if (!isRecord(data)) return null;

  const user = isRecord(data.user) ? data.user : undefined;
  const tenantObj = isRecord(data.tenant) ? data.tenant : undefined;
  const tenantName = typeof data.tenant_name === "string" ? data.tenant_name : null;

  return (
    readName(tenantObj) ||
    tenantName ||
    readName(isRecord(user?.tenant) ? user?.tenant : undefined) ||
    readName(isRecord(user?.organization) ? user?.organization : undefined) ||
    null
  );
}

export function useOrgName() {
  const fallback = useMemo(() => process.env.NEXT_PUBLIC_TENANT_NAME || process.env.NEXT_PUBLIC_TENANT_SLUG || "legacy", []);
  const [orgName, setOrgName] = useState<string>(fallback);

  useEffect(() => {
    let active = true;
    async function fetchName() {
      try {
        const res = await fetch("/api/auth/me", { credentials: "include" });
        if (!res.ok) return;
        const data = await res.json();
        const fromApi = extractTenantName(data);
        if (fromApi && active) setOrgName(fromApi);
      } catch {
        /* ignore and keep fallback */
      }
    }
    fetchName();
    return () => {
      active = false;
    };
  }, [fallback]);

  return orgName;
}
