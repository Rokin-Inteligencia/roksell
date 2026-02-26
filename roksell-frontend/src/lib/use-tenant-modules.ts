"use client";
import { useEffect, useMemo, useState } from "react";
import { adminFetch } from "@/lib/admin-api";

type ModulesResponse = {
  modules: string[];
  module_access?: Record<string, { view?: boolean; edit?: boolean }>;
};

export function useTenantModules() {
  const [modules, setModules] = useState<string[] | null>(null);
  const [moduleAccess, setModuleAccess] = useState<Record<string, { view?: boolean; edit?: boolean }> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const res = await adminFetch<ModulesResponse>("/admin/modules");
        if (active) {
          setModules(res.modules ?? []);
          setModuleAccess(res.module_access ?? null);
        }
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "Falha ao carregar modulos");
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => {
      active = false;
    };
  }, []);

  const moduleSet = useMemo(() => (modules ? new Set(modules) : null), [modules]);

  function hasModule(key: string) {
    if (error) return true;
    if (!moduleSet) return true;
    return moduleSet.has(key);
  }

  function hasModuleAction(key: string, action: "view" | "edit" = "view") {
    if (error) return action === "view";
    if (!moduleSet) return action === "view";
    if (!moduleSet.has(key)) return false;
    if (!moduleAccess) return action === "view";
    const access = moduleAccess[key];
    if (!access) return false;
    if (action === "edit") return Boolean(access.edit);
    return Boolean(access.view ?? true);
  }

  return { modules, loading, error, hasModule, hasModuleAction, ready: modules !== null || Boolean(error) };
}
