"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { adminFetch } from "@/lib/admin-api";
import { clearAdminToken } from "@/lib/admin-auth";
import { useAdminGuard } from "@/lib/use-admin-guard";
import { ProfileBadge } from "@/components/admin/ProfileBadge";
import { AdminSidebar } from "@/components/admin/AdminSidebar";
import { adminMenuWithHome } from "@/config/adminMenu";
import { useOrgName } from "@/lib/use-org-name";
import { useTenantModules } from "@/lib/use-tenant-modules";

type HomeInsights = {
  revenue_today_cents: number;
  revenue_month_cents: number;
  orders_today: number;
  orders_month: number;
};

export default function AdminHome() {
  const ready = useAdminGuard();
  const tenantName = useOrgName();
  const pathname = usePathname();
  const [metrics, setMetrics] = useState<HomeInsights | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { hasModule, ready: modulesReady } = useTenantModules();
  const insightsEnabled = modulesReady && hasModule("insights");

  async function logout() {
    try {
      await fetch("/api/auth/logout", { method: "POST", credentials: "include" });
    } catch {
      /* ignore */
    } finally {
      clearAdminToken();
      window.location.href = "/portal/login";
    }
  }

  useEffect(() => {
    if (!ready || !insightsEnabled) {
      setMetrics(null);
      setError(null);
      return;
    }
    let cancelled = false;
    async function loadMetrics() {
      try {
        const res = await adminFetch<HomeInsights>("/admin/insights");
        if (!cancelled) setMetrics(res);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Falha ao carregar indicadores");
      }
    }
    loadMetrics();
    return () => {
      cancelled = true;
    };
  }, [insightsEnabled, ready]);

  if (!ready) return null;

  const fmtCurrency = (valueCents: number) =>
    (valueCents / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

  const revenueToday = metrics?.revenue_today_cents ?? 0;
  const revenueMonth = metrics?.revenue_month_cents ?? 0;
  const ordersToday = metrics?.orders_today ?? 0;
  const ordersMonth = metrics?.orders_month ?? 0;
  const ticketMonth = ordersMonth ? Math.round(revenueMonth / ordersMonth) : 0;

  return (
    <main className="min-h-screen text-slate-900 bg-[#f5f3ff]">
      <div className="max-w-7xl w-full mx-auto px-3 sm:px-4 lg:px-6 py-8">
        <div className="grid gap-6 lg:grid-cols-[260px_minmax(0,1fr)] items-start">
          <AdminSidebar
            menu={adminMenuWithHome}
            currentPath={pathname}
            orgName={tenantName}
            footer={
              <button
                onClick={logout}
                className="px-3 py-2 w-full text-left rounded-lg bg-[#6320ee] text-[#f8f0fb] font-semibold hover:brightness-95 transition"
              >
                Sair
              </button>
            }
          />

          <div className="space-y-6">
            <header className="flex flex-wrap items-center justify-between gap-3">
                <div className="space-y-1 text-slate-900">
                <h1 className="text-3xl font-semibold">Visão geral</h1>
                <p className="text-sm text-slate-600">
                  Métricas principais e atalhos operacionais. Acesse Insights para detalhes completos.
                </p>
              </div>
              <ProfileBadge />
            </header>

            {error && <p className="text-sm text-amber-700">{error}</p>}

            {/* KPIs principais */}
            {insightsEnabled && (
              <section className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
                <KpiCard label="Faturamento (hoje)" value={fmtCurrency(revenueToday)} trend="-" delay={0} />
                <KpiCard label="Pedidos (hoje)" value={`${ordersToday}`} trend="-" delay={120} />
                <KpiCard label="Ticket medio (mes atual)" value={fmtCurrency(ticketMonth)} trend="-" delay={240} />
                <KpiCard label="Faturamento (mes atual)" value={fmtCurrency(revenueMonth)} trend="-" delay={360} />
              </section>
            )}

            {/* Central operacional */}
            <section className="space-y-3">
              <div className="flex items-center justify-between text-slate-900">
                <h2 className="text-xl font-semibold">Central operacional</h2>
                <Link href="/portal/insights" className="text-sm underline underline-offset-4 text-slate-600">
                  Abrir insights
                </Link>
              </div>
              <div className="grid sm:grid-cols-2 lg:grid-cols-2 gap-3">
                <WidgetCard title="Pedidos em atraso" value="0" detail="Atualize integrações para ver dados reais" delay={120} />
                <WidgetCard title="Entregas hoje" value="0" detail="Roteirização em breve" delay={240} />
                <WidgetCard title="Estoque crítico" value="-" detail="Defina níveis mínimos no módulo Estoque" locked delay={360} />
                <WidgetCard title="Campanhas ativas" value="-" detail="Disponível no módulo Campanhas" locked delay={480} />
              </div>
            </section>
          </div>
        </div>
      </div>
    </main>
  );
}
function KpiCard({
  label,
  value,
  trend,
  delay,
}: {
  label: string;
  value: string;
  trend: string;
  delay?: number;
}) {
  return (
    <div
      className="rounded-2xl bg-white border border-slate-200 p-4 shadow-lg shadow-slate-200/60 text-slate-900 opacity-0 animate-[fade-up_0.8s_ease_forwards]"
      style={delay ? { animationDelay: `${delay}ms` } : undefined}
    >
      <div className="text-xs uppercase tracking-[0.14em] text-slate-700">{label}</div>
      <div className="text-2xl font-semibold mt-1">{value}</div>
      <div className="text-xs text-slate-600 mt-1">Tendência: {trend}</div>
    </div>
  );
}

function WidgetCard({
  title,
  value,
  detail,
  locked,
  delay,
}: {
  title: string;
  value: string;
  detail: string;
  locked?: boolean;
  delay?: number;
}) {
  return (
    <div
      className="rounded-2xl bg-white border border-slate-200 p-4 shadow shadow-slate-200/50 opacity-0 animate-[fade-up_0.8s_ease_forwards]"
      style={delay ? { animationDelay: `${delay}ms` } : undefined}
    >
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">{title}</h3>
        {locked ? (
          <span className="text-[10px] px-2 py-1 rounded-full bg-slate-200 border border-slate-200">Em breve</span>
        ) : null
        }
      </div>
      <div className="text-2xl font-semibold mt-2">{value}</div>
      <p className="text-xs text-slate-600 mt-1">{detail}</p>
    </div>
  );
}




