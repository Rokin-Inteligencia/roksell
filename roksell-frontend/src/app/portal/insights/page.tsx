"use client";
import { useEffect, useState } from "react";
import { adminFetch } from "@/lib/admin-api";
import { useAdminGuard } from "@/lib/use-admin-guard";
import { useTenantModules } from "@/lib/use-tenant-modules";
import { ProfileBadge } from "@/components/admin/ProfileBadge";
import { AdminSidebar } from "@/components/admin/AdminSidebar";
import { adminMenuWithHome } from "@/config/adminMenu";
import { usePathname } from "next/navigation";
import { useOrgName } from "@/lib/use-org-name";
import { clearAdminToken } from "@/lib/admin-auth";

type InsightResponse = {
  revenue_today_cents: number;
  revenue_week_cents: number;
  revenue_month_cents: number;
  revenue_range_cents: number;
  revenue_by_month: { name: string; revenue_cents: number }[];
  by_category: { name: string; revenue_cents: number }[];
  by_store: { name: string; revenue_cents: number }[];
  by_product: { name: string; revenue_cents: number }[];
  by_product_quantity: { name: string; revenue_cents: number }[];
  top_customers: { name: string; revenue_cents: number }[];
  avg_by_weekday: {
    name: string;
    avg_cents: number;
    avg_including_zero_cents: number;
    total_cents: number;
    days_with_sales: number;
    total_days: number;
  }[];
  avg_by_week_of_month: {
    name: string;
    avg_cents: number;
    avg_including_zero_cents: number;
    total_cents: number;
    days_with_sales: number;
    total_days: number;
  }[];
  total_quantity: number;
  total_orders: number;
};

const formatDateInput = (date: Date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const getCurrentMonthRange = () => {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), 1);
  const end = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  return {
    start: formatDateInput(start),
    end: formatDateInput(end),
  };
};

const fallbackData: InsightResponse = {
  revenue_today_cents: 182500,
  revenue_week_cents: 1287500,
  revenue_month_cents: 4823000,
  revenue_range_cents: 182500,
  revenue_by_month: [
    { name: "2025-12", revenue_cents: 950000 },
    { name: "2026-01", revenue_cents: 1230000 },
    { name: "2026-02", revenue_cents: 880000 },
  ],
  total_quantity: 230,
  total_orders: 42,
  by_category: [
    { name: "Pizzas", revenue_cents: 2100000 },
    { name: "Bebidas", revenue_cents: 950000 },
    { name: "Sobremesas", revenue_cents: 400000 },
  ],
  by_store: [
    { name: "Roksell - Matriz", revenue_cents: 1025000 },
    { name: "Roksell - Delivery", revenue_cents: 620000 },
    { name: "Roksell - Centro", revenue_cents: 180000 },
  ],
  by_product: [
    { name: "Pizza Margherita", revenue_cents: 890000 },
    { name: "Refrigerante Lata", revenue_cents: 520000 },
    { name: "Tiramisu", revenue_cents: 210000 },
  ],
  by_product_quantity: [
    { name: "Pizza Margherita", revenue_cents: 120 },
    { name: "Refrigerante Lata", revenue_cents: 80 },
    { name: "Tiramisu", revenue_cents: 30 },
  ],
  top_customers: [
    { name: "Ana Costa", revenue_cents: 1850000 },
    { name: "Joao Pereira", revenue_cents: 1320000 },
    { name: "Carla Souza", revenue_cents: 980000 },
  ],
  avg_by_weekday: [
    { name: "Domingo", avg_cents: 320000, avg_including_zero_cents: 250000, total_cents: 960000, days_with_sales: 3, total_days: 4 },
    { name: "Segunda", avg_cents: 220000, avg_including_zero_cents: 180000, total_cents: 660000, days_with_sales: 3, total_days: 4 },
    { name: "Terca", avg_cents: 210000, avg_including_zero_cents: 170000, total_cents: 630000, days_with_sales: 3, total_days: 4 },
    { name: "Quarta", avg_cents: 240000, avg_including_zero_cents: 200000, total_cents: 720000, days_with_sales: 3, total_days: 4 },
    { name: "Quinta", avg_cents: 260000, avg_including_zero_cents: 210000, total_cents: 780000, days_with_sales: 3, total_days: 4 },
    { name: "Sexta", avg_cents: 410000, avg_including_zero_cents: 320000, total_cents: 1230000, days_with_sales: 3, total_days: 4 },
    { name: "Sabado", avg_cents: 520000, avg_including_zero_cents: 410000, total_cents: 1560000, days_with_sales: 3, total_days: 4 },
  ],
  avg_by_week_of_month: [
    { name: "Semana 1", avg_cents: 300000, avg_including_zero_cents: 260000, total_cents: 1200000, days_with_sales: 4, total_days: 5 },
    { name: "Semana 2", avg_cents: 340000, avg_including_zero_cents: 300000, total_cents: 1360000, days_with_sales: 4, total_days: 5 },
    { name: "Semana 3", avg_cents: 360000, avg_including_zero_cents: 320000, total_cents: 1440000, days_with_sales: 4, total_days: 5 },
    { name: "Semana 4", avg_cents: 420000, avg_including_zero_cents: 360000, total_cents: 1680000, days_with_sales: 4, total_days: 5 },
  ],
};

export default function InsightsAdmin() {
  const ready = useAdminGuard();
  const tenantName = useOrgName();
  const pathname = usePathname();
  const { hasModule, ready: modulesReady } = useTenantModules();
  const moduleAllowed = hasModule("insights");
  const moduleBlocked = modulesReady && !moduleAllowed;

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
  const [data, setData] = useState<InsightResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [, setLoading] = useState(false);
  const [startDate, setStartDate] = useState(() => getCurrentMonthRange().start);
  const [endDate, setEndDate] = useState(() => getCurrentMonthRange().end);
  const [filterOpen, setFilterOpen] = useState(false);
  const quickRanges = [7, 30, 90];

  async function load(range?: { start?: string; end?: string }) {
    setLoading(true);
    setError(null);
    try {
      const qs = new URLSearchParams();
      if (range?.start) qs.set("start_date", range.start);
      if (range?.end) qs.set("end_date", range.end);
      const res = await adminFetch<InsightResponse>(`/admin/insights${qs.toString() ? `?${qs.toString()}` : ""}`);
      setData(res);
    } catch {
      // MantÃ©m UI funcional com dados de exemplo se a rota ainda nÃ£o existir
      setError("Usando dados de exemplo; conecte /admin/insights no backend.");
      setData(fallbackData);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (ready && modulesReady && moduleAllowed) load({ start: startDate, end: endDate });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, modulesReady, moduleAllowed]);

  if (!ready) return null;
  if (!data && !moduleBlocked) return null;

  const resolvedData = data ?? fallbackData;
  const currency = (v: number) =>
    (v / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

  const monthlySeries = resolvedData.revenue_by_month.map((item) => ({
    period: item.name,
    revenue_cents: item.revenue_cents,
  }));

  const formatDateShort = (value: string) => {
    const [year, month, day] = value.split("-");
    if (!year || !month || !day) return value;
    return `${day}/${month}/${year}`;
  };

  const filterSummary = startDate && endDate
    ? `${formatDateShort(startDate)} - ${formatDateShort(endDate)}`
    : "Sem filtro aplicado";

  const applyQuickRange = (days: number) => {
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - (days - 1));
    const startValue = formatDateInput(start);
    const endValue = formatDateInput(end);
    setStartDate(startValue);
    setEndDate(endValue);
    load({ start: startValue, end: endValue });
  };

  const sidebarItems = adminMenuWithHome;

  return (
    <main className="min-h-screen text-slate-900 bg-[#f5f3ff]">
      <div className="max-w-7xl w-full mx-auto px-3 sm:px-4 lg:px-6 py-8">
        <div className="grid gap-6 lg:grid-cols-[260px_minmax(0,1fr)] items-start">
          <AdminSidebar
            menu={sidebarItems}
            collapsible
            orgName={tenantName}
            currentPath={pathname}
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
              <div className="text-slate-900">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Admin Â· Insights</p>
                <h1 className="text-3xl font-semibold">VisÃ£o de faturamento</h1>
                <p className="text-sm text-slate-600">
                  MÃ©tricas por tenant: dia, semana, mÃªs e detalhamento por categoria/produto.
                </p>
              </div>
              <ProfileBadge />
            </header>

            {moduleBlocked ? (
              <section className="rounded-2xl bg-white border border-slate-200 p-4 space-y-2">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Modulo inativo</p>
                <h2 className="text-lg font-semibold">Insights indisponiveis</h2>
                <p className="text-sm text-slate-600">
                  Este modulo nao esta habilitado para a sua empresa. Fale com o administrador para liberar o acesso.
                </p>
              </section>
            ) : (
              <>
                {error && <p className="text-sm text-amber-700">{error}</p>}

                <section className="rounded-2xl bg-white p-3 sm:p-4 border border-slate-200 space-y-3 sm:space-y-4">
              <button
                type="button"
                onClick={() => setFilterOpen((open) => !open)}
                className="w-full flex items-center justify-between text-left gap-3"
              >
                <div>
                  <div className="text-xs uppercase tracking-[0.2em] text-slate-500">Filtro</div>
                  <div className="text-sm text-slate-700">{filterSummary}</div>
                </div>
                <span className="px-3 py-1 rounded-full bg-slate-100 border border-slate-200 text-xs text-slate-700">
                  {filterOpen ? "Fechar" : "Editar"}
                </span>
              </button>

              {filterOpen && (
                <div className="grid gap-2 sm:gap-3 sm:grid-cols-[1fr_1fr_auto] items-end">
                  <label className="space-y-1 text-xs sm:text-sm text-slate-700">
                    <span>Data inA-cio</span>
                    <input
                      type="date"
                      className="input w-full bg-white border border-slate-200 text-slate-900 placeholder:text-slate-400 focus:border-[#6320ee]/40 text-sm"
                      value={startDate}
                      onChange={(e) => setStartDate(e.target.value)}
                    />
                  </label>
                  <label className="space-y-1 text-xs sm:text-sm text-slate-700">
                    <span>Data fim</span>
                    <input
                      type="date"
                      className="input w-full bg-white border border-slate-200 text-slate-900 placeholder:text-slate-400 focus:border-[#6320ee]/40 text-sm"
                      value={endDate}
                      onChange={(e) => setEndDate(e.target.value)}
                    />
                  </label>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => load({ start: startDate, end: endDate })}
                      className="px-3 sm:px-4 py-2 rounded-lg bg-[#6320ee] text-white text-xs sm:text-sm font-semibold active:scale-95"
                    >
                      Aplicar filtro
                    </button>
                    <button
                      onClick={() => {
                        setStartDate("");
                        setEndDate("");
                        load();
                      }}
                      className="px-3 py-2 rounded-lg bg-slate-100 border border-slate-200 text-slate-700 text-xs sm:text-sm hover:bg-slate-200"
                    >
                      Limpar
                    </button>
                  </div>
                </div>
              )}
            </section>

            <section className="grid md:grid-cols-3 gap-4">
              <StatCard label="Hoje" value={currency(resolvedData.revenue_today_cents)} />
              <StatCard label="Semana" value={currency(resolvedData.revenue_week_cents)} />
              <StatCard label="Mes" value={currency(resolvedData.revenue_month_cents)} />
              <StatCard label="Faturamento no Periodo" value={currency(resolvedData.revenue_range_cents)} />
              <StatCard
                label="Ticket medio produto"
                value={currency(
                  resolvedData.total_quantity
                    ? Math.round(resolvedData.revenue_range_cents / resolvedData.total_quantity)
                    : 0
                )}
              />
              <StatCard
                label="Ticket medio por venda"
                value={currency(
                  resolvedData.total_orders
                    ? Math.round(resolvedData.revenue_range_cents / resolvedData.total_orders)
                    : 0
                )}
              />
            </section>

            <section className="grid md:grid-cols-1 gap-4">
              <RevenueLineCard
                title="Evolucao de faturamento"
                series={monthlySeries}
                currency={currency}
              />
            </section>

            <section className="grid md:grid-cols-2 gap-4">
              <BreakdownCard
                title="Faturamento por loja"
                items={resolvedData.by_store ?? []}
                currency={currency}
                total={resolvedData.revenue_range_cents}
                showPercent
                totalLabel="Faturamento no periodo"
              />
            </section>

            <section className="grid md:grid-cols-2 gap-4">
              <BreakdownCard
                title="Por categoria"
                items={resolvedData.by_category}
                currency={currency}
                total={resolvedData.revenue_range_cents}
                showPercent
              />
              <BreakdownCard
                title="Por produto"
                items={resolvedData.by_product}
                currency={currency}
                total={resolvedData.revenue_range_cents}
                showPercent
              />
            </section>

            <section className="grid md:grid-cols-2 gap-4">
              <BreakdownCard
                title="Top clientes por valor"
                items={resolvedData.top_customers}
                currency={currency}
                showPercent={false}
              />
              <BreakdownCard
                title="Quantidade vendida por produto"
                items={resolvedData.by_product_quantity}
                currency={(v) => `${v} unid.`}
                total={resolvedData.total_quantity}
                totalLabel="Total vendido"
                showPercent
              />
            </section>

            <section className="rounded-2xl bg-white border border-slate-200 p-4 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Medias</p>
                  <h2 className="text-lg font-semibold text-slate-900">Filtro rapido</h2>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  {quickRanges.map((days) => (
                    <button
                      key={`range-${days}`}
                      type="button"
                      onClick={() => applyQuickRange(days)}
                      className="px-3 py-1 rounded-full border border-slate-200 bg-slate-50 text-slate-700 hover:border-[#6320ee]"
                    >
                      {days} dias
                    </button>
                  ))}
                </div>
              </div>
              <p className="text-xs text-slate-500">
                Ajuste rapido do periodo para calcular as medias por dia e semana.
              </p>
            </section>

            <section className="grid md:grid-cols-2 gap-4">
              <AverageBarCard
                title="Media por dia da semana"
                subtitle="Valor medio em dias com venda"
                items={resolvedData.avg_by_weekday}
                currency={currency}
              />
              <AverageBarCard
                title="Media por semana do mes"
                subtitle="Valor medio em dias com venda"
                items={resolvedData.avg_by_week_of_month}
                currency={currency}
              />
            </section>
              </>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-white border border-slate-200 p-4 text-slate-900">
      <div className="text-xs uppercase tracking-[0.15em] text-slate-700">{label}</div>
      <div className="text-2xl font-semibold">{value}</div>
    </div>
  );
}

function BreakdownCard({
  title,
  items,
  currency,
  total,
  showPercent,
  totalLabel = "Total",
}: {
  title: string;
  items: { name: string; revenue_cents: number }[];
  currency: (v: number) => string;
  total?: number;
  showPercent?: boolean;
  totalLabel?: string;
}) {
  return (
    <div className="rounded-2xl bg-white border border-slate-200 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
        <span className="text-xs text-slate-600">Top 10</span>
      </div>
      {typeof total !== "undefined" && (
        <div className="text-xs text-slate-600">
          {totalLabel}: <span className="font-semibold text-slate-900">{currency(total)}</span>
        </div>
      )}
      <div className="space-y-2">
        {items.slice(0, 10).map((item, idx) => (
          <div key={`${item.name}-${idx}`} className="flex items-center justify-between text-sm text-slate-700">
            <div className="flex items-center gap-2">
              <span className="w-5 text-xs text-slate-400">#{idx + 1}</span>
              <span>{item.name}</span>
            </div>
            <div className="flex items-center gap-2">
              {showPercent && total ? (
                <span className="text-[11px] text-slate-400">
                  {((item.revenue_cents / total) * 100).toFixed(1)}%
                </span>
              ) : null}
              <span className="font-semibold text-slate-900">{currency(item.revenue_cents)}</span>
            </div>
          </div>
        ))}
        {items.length === 0 && <p className="text-xs text-slate-400">Sem dados ainda.</p>}
      </div>
    </div>
  );
}

function RevenueLineCard({
  title,
  series,
  currency,
}: {
  title: string;
  series: { period: string; revenue_cents: number }[];
  currency: (v: number) => string;
}) {
  const [hovered, setHovered] = useState<number | null>(null);
  if (!series.length) {
    return (
      <div className="rounded-2xl bg-white border border-slate-200 p-4 space-y-3">
        <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
        <p className="text-xs text-slate-400">Sem dados no periodo.</p>
      </div>
    );
  }

  const total = series.reduce((acc, item) => acc + item.revenue_cents, 0);
  const max = Math.max(...series.map((s) => s.revenue_cents), 1);
  const maxIndex = series.findIndex((item) => item.revenue_cents === max);
  const chartTop = 12;
  const chartBottom = 92;
  const chartHeight = chartBottom - chartTop;
  const points = series.map((s, idx) => {
    const x = series.length === 1 ? 0 : (idx / (series.length - 1)) * 100;
    const y = chartBottom - (s.revenue_cents / max) * chartHeight;
    return { x, y };
  });

  const labelForPeriod = (period: string) => {
    const [year, month] = period.split("-");
    if (!year || !month) return period;
    return `${month}/${year}`;
  };

  const areaPath = `M ${points[0].x},${chartBottom} L ${points
    .map((p) => `${p.x},${p.y}`)
    .join(" ")} L ${points[points.length - 1].x},${chartBottom} Z`;

  return (
    <div className="rounded-2xl bg-white border border-slate-200 p-4 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
          <p className="text-xs text-slate-600">Mes a mes</p>
        </div>
        <div className="text-right text-xs text-slate-600">
          <div>
            Total: <span className="font-semibold text-slate-900">{currency(total)}</span>
          </div>
          {maxIndex >= 0 && (
            <div>
              Pico:{" "}
              <span className="font-semibold text-slate-900">
                {labelForPeriod(series[maxIndex].period)}
              </span>
            </div>
          )}
        </div>
      </div>
      <div className="grid gap-3 lg:grid-cols-[72px_1fr] items-stretch">
        <div className="flex flex-col justify-between text-[11px] text-slate-600">
          <span>{currency(max)}</span>
          <span>{currency(Math.round(max / 2))}</span>
          <span>0</span>
        </div>
        <div className="relative">
          <svg viewBox="0 0 100 100" className="w-full h-56">
            <defs>
              <linearGradient id="revenueGradient" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="#F5D6B3" stopOpacity="0.45" />
                <stop offset="100%" stopColor="#F5D6B3" stopOpacity="0.02" />
              </linearGradient>
            </defs>
            <line x1="0" y1={chartTop} x2="100" y2={chartTop} stroke="rgba(99,32,238,0.18)" />
            <line x1="0" y1={(chartTop + chartBottom) / 2} x2="100" y2={(chartTop + chartBottom) / 2} stroke="rgba(99,32,238,0.12)" />
            <line x1="0" y1={chartBottom} x2="100" y2={chartBottom} stroke="rgba(99,32,238,0.18)" />
            <path d={areaPath} fill="url(#revenueGradient)" />
            <polyline
              fill="none"
              stroke="#E6C3A2"
              strokeWidth="2"
              points={points.map((p) => `${p.x},${p.y}`).join(" ")}
            />
            {points.map((p, idx) => (
              <g
                key={`pt-${idx}`}
                onMouseEnter={() => setHovered(idx)}
                onMouseLeave={() => setHovered(null)}
              >
                <circle
                  cx={p.x}
                  cy={p.y}
                  r={idx === hovered ? 3.6 : 2.6}
                  fill={idx === hovered ? "#F5D6B3" : "#E6C3A2"}
                  stroke={idx === hovered ? "#1f1b2e" : "none"}
                  strokeWidth={idx === hovered ? 1 : 0}
                />
                <text
                  x={p.x}
                  y={p.y - 6}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontSize="3.6"
                  fill="rgba(31,27,46,0.85)"
                >
                  {currency(series[idx].revenue_cents)}
                </text>
                <text
                  x={p.x}
                  y={chartBottom + 5}
                  textAnchor="middle"
                  dominantBaseline="hanging"
                  fontSize="3.4"
                  fill="rgba(107,100,128,0.9)"
                >
                  {labelForPeriod(series[idx].period)}
                </text>
              </g>
            ))}
          </svg>
          {hovered !== null && (
            <div className="absolute top-2 right-2 text-xs bg-slate-900/90 text-white px-3 py-2 rounded-lg border border-slate-700/40">
              <div>{labelForPeriod(series[hovered].period)}</div>
              <div className="font-semibold">{currency(series[hovered].revenue_cents)}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function AverageBarCard({
  title,
  subtitle,
  items,
  currency,
}: {
  title: string;
  subtitle?: string;
  items: {
    name: string;
    avg_cents: number;
    avg_including_zero_cents: number;
    total_cents: number;
    days_with_sales: number;
    total_days: number;
  }[];
  currency: (v: number) => string;
}) {
  if (!items.length) {
    return (
      <div className="rounded-2xl bg-white border border-slate-200 p-4 space-y-3">
        <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
        <p className="text-xs text-slate-400">Sem dados no periodo.</p>
      </div>
    );
  }
  const max = Math.max(...items.map((item) => item.avg_cents), 1);
  return (
    <div className="rounded-2xl bg-white border border-slate-200 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
          {subtitle && <p className="text-xs text-slate-600">{subtitle}</p>}
        </div>
        <span className="text-[11px] text-slate-500">Media</span>
      </div>
      <div className="space-y-2">
        {items.map((item, idx) => {
          const width = `${Math.round((item.avg_cents / max) * 100)}%`;
          return (
            <div key={`${item.name}-${idx}`} className="space-y-2">
              {idx > 0 && <div className="h-px w-full bg-slate-100" />}
              <div className="flex items-center gap-3 text-sm text-slate-700">
                <div className="w-20 text-xs text-slate-500">{item.name}</div>
                <div className="flex-1">
                  <div className="h-2 rounded-full bg-slate-100">
                    <div className="h-2 rounded-full bg-[#F5D6B3]" style={{ width }} />
                  </div>
                  <div className="mt-1 flex flex-wrap gap-2 text-[11px] text-slate-500">
                    <span>{currency(item.avg_including_zero_cents)} com dias sem venda</span>
                    <span>â€¢</span>
                    <span>
                      Dias com venda: {item.days_with_sales}/{item.total_days}
                    </span>
                    <span>â€¢</span>
                    <span>Total: {currency(item.total_cents)}</span>
                  </div>
                </div>
                <div className="w-24 text-right text-xs font-semibold text-slate-900">
                  {currency(item.avg_cents)}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}









