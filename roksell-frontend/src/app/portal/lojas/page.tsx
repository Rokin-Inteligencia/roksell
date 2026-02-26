"use client";

import { useEffect, useMemo, useState } from "react";
import { adminFetch, adminUpload } from "@/lib/admin-api";
import { useAdminGuard } from "@/lib/use-admin-guard";
import { AdminSidebar } from "@/components/admin/AdminSidebar";
import { adminMenuWithHome } from "@/config/adminMenu";
import { usePathname } from "next/navigation";
import { ProfileBadge } from "@/components/admin/ProfileBadge";
import { useOrgName } from "@/lib/use-org-name";
import { OperatingHoursDay, PaymentMethod, Store } from "@/types";
import { clearAdminToken } from "@/lib/admin-auth";
import { useTenantModules } from "@/lib/use-tenant-modules";
import { getTenantSlug } from "@/lib/portal-auth";
import { UsersManagerPanel } from "@/components/admin/UsersManagerPanel";

type ShippingMethod = "distance" | "district";
type ShippingTierDraft = { km_min: string; km_max: string; amount: string };
type ShippingTierApi = { km_min: number; km_max: number; amount_cents: number };

type StoreForm = {
  name: string;
  lat: string;
  lon: string;
  timezone: string;
  postal_code: string;
  street: string;
  number: string;
  district: string;
  city: string;
  state: string;
  complement: string;
  reference: string;
  phone: string;
  whatsapp_contact_phone: string;
  sla_minutes: string;
  payment_methods: PaymentMethod[];
  order_statuses_input: string;
  order_final_statuses_input: string;
  shipping_method: ShippingMethod;
  shipping_fixed_fee: string;
  cover_image_url: string;
  closed_dates: string[];
  operating_hours: OperatingHoursDay[];
  is_delivery: boolean;
  allow_preorder_when_closed: boolean;
  is_active: boolean;
};

const OPERATING_DAYS = [
  { day: 0, label: "Seg" },
  { day: 1, label: "Ter" },
  { day: 2, label: "Qua" },
  { day: 3, label: "Qui" },
  { day: 4, label: "Sex" },
  { day: 5, label: "Sab" },
  { day: 6, label: "Dom" },
];

const DEFAULT_OPERATING_HOURS: OperatingHoursDay[] = OPERATING_DAYS.map((item) => ({
  day: item.day,
  enabled: false,
  open: "08:00",
  close: "18:00",
}));

const DEFAULT_PAYMENT_METHODS: PaymentMethod[] = ["pix", "cash"];
const DEFAULT_ORDER_STATUSES = ["received", "confirmed", "preparing", "ready", "on_route", "delivered", "completed", "canceled"];
const DEFAULT_FINAL_STATUSES = ["completed", "canceled"];
const DEFAULT_STATUS_COLORS: Record<string, string> = {
  received: "#e2e8f0",
  confirmed: "#dbeafe",
  preparing: "#fef3c7",
  ready: "#fde68a",
  on_route: "#fed7aa",
  delivered: "#bbf7d0",
  completed: "#a7f3d0",
  canceled: "#fecaca",
};
const MAX_DISTANCE_TIERS = 20;
const DEFAULT_STORE_TIMEZONE = "America/Sao_Paulo";

function normalizeStatusList(values: string[]): string[] {
  const unique = Array.from(new Set(values.map((item) => item.trim()).filter(Boolean)));
  if (!unique.includes("canceled")) unique.push("canceled");
  return unique;
}

function defaultColorForStatus(status: string): string {
  return DEFAULT_STATUS_COLORS[status] ?? "#e2e8f0";
}

function normalizeHexColor(value: string | null | undefined): string | null {
  if (!value) return null;
  const trimmed = value.trim();
  if (/^#[0-9a-fA-F]{6}$/.test(trimmed)) return trimmed.toLowerCase();
  if (/^#[0-9a-fA-F]{3}$/.test(trimmed)) {
    const r = trimmed[1];
    const g = trimmed[2];
    const b = trimmed[3];
    return `#${r}${r}${g}${g}${b}${b}`.toLowerCase();
  }
  return null;
}

function buildStatusColors(
  statuses: string[],
  colors?: Record<string, string> | null,
  canceledFallback?: string | null
): Record<string, string> {
  const result: Record<string, string> = {};
  statuses.forEach((status) => {
    const raw = colors?.[status] ?? (status === "canceled" ? canceledFallback : null) ?? defaultColorForStatus(status);
    result[status] = normalizeHexColor(raw) ?? defaultColorForStatus(status);
  });
  return result;
}

function formatStatusLabel(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function normalizeHours(hours?: OperatingHoursDay[] | null): OperatingHoursDay[] {
  if (!hours || hours.length === 0) return DEFAULT_OPERATING_HOURS.map((item) => ({ ...item }));
  const byDay = new Map(hours.map((item) => [item.day, item]));
  return OPERATING_DAYS.map((day) => ({
    day: day.day,
    enabled: byDay.get(day.day)?.enabled ?? false,
    open: byDay.get(day.day)?.open ?? "08:00",
    close: byDay.get(day.day)?.close ?? "18:00",
  }));
}

function parseCsv(value: string): string[] {
  return Array.from(new Set(value.split(",").map((item) => item.trim()).filter(Boolean)));
}

function normalizePostalCode(value: string): string | null {
  const digits = value.replace(/\D+/g, "");
  if (!digits) return null;
  return digits;
}

function toAmountInput(cents?: number | null): string {
  return ((Number(cents || 0) / 100) || 0).toFixed(2);
}

function parseAmountInput(value: string): number | null {
  const normalized = value.replace(",", ".").trim();
  if (!normalized) return null;
  const parsed = Number(normalized);
  if (!Number.isFinite(parsed) || parsed < 0) return null;
  return Math.round(parsed * 100);
}

function normalizeTiers(tiers?: ShippingTierApi[] | null): ShippingTierDraft[] {
  if (!tiers || tiers.length === 0) return [];
  return tiers.map((tier) => ({
    km_min: String(tier.km_min),
    km_max: String(tier.km_max),
    amount: toAmountInput(tier.amount_cents),
  }));
}

const EMPTY_FORM: StoreForm = {
  name: "",
  lat: "",
  lon: "",
  timezone: DEFAULT_STORE_TIMEZONE,
  postal_code: "",
  street: "",
  number: "",
  district: "",
  city: "",
  state: "",
  complement: "",
  reference: "",
  phone: "",
  whatsapp_contact_phone: "",
  sla_minutes: "45",
  payment_methods: [...DEFAULT_PAYMENT_METHODS],
  order_statuses_input: DEFAULT_ORDER_STATUSES.join(", "),
  order_final_statuses_input: DEFAULT_FINAL_STATUSES.join(", "),
  shipping_method: "distance",
  shipping_fixed_fee: "0.00",
  cover_image_url: "",
  closed_dates: [],
  operating_hours: DEFAULT_OPERATING_HOURS.map((item) => ({ ...item })),
  is_delivery: true,
  allow_preorder_when_closed: true,
  is_active: true,
};

export default function StoresAdminPage() {
  const ready = useAdminGuard();
  const tenantName = useOrgName();
  const pathname = usePathname();
  const { hasModule, ready: modulesReady } = useTenantModules();
  const moduleAllowed = hasModule("stores");
  const moduleBlocked = modulesReady && !moduleAllowed;
  const [tenantSlug] = useState(() => getTenantSlug() || process.env.NEXT_PUBLIC_TENANT_SLUG || "");
  const vitrineBaseUrl = (process.env.NEXT_PUBLIC_VITRINE_BASE_URL || "https://www.rokin.com.br").replace(/\/$/, "");

  const [stores, setStores] = useState<Store[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [showUsersModal, setShowUsersModal] = useState(false);
  const [editing, setEditing] = useState<Store | null>(null);
  const [form, setForm] = useState<StoreForm>(EMPTY_FORM);
  const [shippingTiers, setShippingTiers] = useState<ShippingTierDraft[]>([]);
  const [shippingError, setShippingError] = useState<string | null>(null);
  const [showCalendarModal, setShowCalendarModal] = useState(false);
  const [calendarMonth, setCalendarMonth] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });
  const [orderStatusColors, setOrderStatusColors] = useState<Record<string, string>>(
    buildStatusColors(DEFAULT_ORDER_STATUSES)
  );
  const [coverFile, setCoverFile] = useState<File | null>(null);
  const [copiedStoreId, setCopiedStoreId] = useState<string | null>(null);

  const activeStores = useMemo(() => stores.filter((store) => store.is_active).length, [stores]);
  const orderStatusList = useMemo(
    () => normalizeStatusList(parseCsv(form.order_statuses_input)),
    [form.order_statuses_input]
  );

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

  function buildStoreLink(store: Store): string {
    if (!tenantSlug) return "";
    const storeSlug = store.slug?.trim() || store.id;
    return `${vitrineBaseUrl}/vitrine/${tenantSlug}/${encodeURIComponent(storeSlug)}`;
  }

  function copyStoreLink(store: Store) {
    const link = buildStoreLink(store);
    if (!link || typeof navigator === "undefined") return;
    navigator.clipboard.writeText(link).catch(() => {});
    setCopiedStoreId(store.id);
    window.setTimeout(() => setCopiedStoreId(null), 1200);
  }

  function setHour(day: number, patch: Partial<OperatingHoursDay>) {
    setForm((prev) => ({
      ...prev,
      operating_hours: prev.operating_hours.map((item) => (item.day === day ? { ...item, ...patch } : item)),
    }));
  }

  function formatIsoDate(value: Date): string {
    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, "0");
    const day = String(value.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  function shiftMonth(base: Date, offset: number): Date {
    return new Date(base.getFullYear(), base.getMonth() + offset, 1);
  }

  function buildCalendarDays(month: Date) {
    const start = new Date(month.getFullYear(), month.getMonth(), 1);
    const startWeekday = (start.getDay() + 6) % 7;
    const daysInMonth = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
    const cells: Array<{ date?: Date; label?: number }> = [];
    for (let i = 0; i < startWeekday; i += 1) {
      cells.push({});
    }
    for (let day = 1; day <= daysInMonth; day += 1) {
      cells.push({
        date: new Date(month.getFullYear(), month.getMonth(), day),
        label: day,
      });
    }
    return cells;
  }

  function updateTier(index: number, patch: Partial<ShippingTierDraft>) {
    setShippingTiers((prev) => prev.map((item, idx) => (idx === index ? { ...item, ...patch } : item)));
  }

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await adminFetch<Store[]>("/admin/stores");
      setStores(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao carregar lojas");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (ready && modulesReady && moduleAllowed) load();
  }, [ready, modulesReady, moduleAllowed]);

  useEffect(() => {
    if (!(showModal || showUsersModal || showCalendarModal)) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [showModal, showUsersModal, showCalendarModal]);

  useEffect(() => {
    setOrderStatusColors((prev) => {
      const next = buildStatusColors(orderStatusList, prev, prev.canceled);
      return next;
    });
  }, [orderStatusList]);

  function openCreate() {
    setError(null);
    setEditing(null);
    setForm({ ...EMPTY_FORM, operating_hours: DEFAULT_OPERATING_HOURS.map((item) => ({ ...item })) });
    setShippingTiers([]);
    setShippingError(null);
    setCoverFile(null);
    setOrderStatusColors(buildStatusColors(DEFAULT_ORDER_STATUSES));
    const now = new Date();
    setCalendarMonth(new Date(now.getFullYear(), now.getMonth(), 1));
    setShowCalendarModal(false);
    setShowModal(true);
  }

  async function openSettings(store: Store) {
    setError(null);
    setEditing(store);
    setForm({
      name: store.name,
      lat: String(store.lat ?? ""),
      lon: String(store.lon ?? ""),
      timezone: store.timezone || DEFAULT_STORE_TIMEZONE,
      postal_code: store.postal_code ?? "",
      street: store.street ?? "",
      number: store.number ?? "",
      district: store.district ?? "",
      city: store.city ?? "",
      state: store.state ?? "",
      complement: store.complement ?? "",
      reference: store.reference ?? "",
      phone: store.phone ?? "",
      whatsapp_contact_phone: store.whatsapp_contact_phone ?? "",
      sla_minutes: String(store.sla_minutes ?? 45),
      payment_methods: store.payment_methods?.length ? store.payment_methods : [...DEFAULT_PAYMENT_METHODS],
      order_statuses_input: (store.order_statuses?.length ? store.order_statuses : DEFAULT_ORDER_STATUSES).join(", "),
      order_final_statuses_input: (store.order_final_statuses?.length ? store.order_final_statuses : DEFAULT_FINAL_STATUSES).join(", "),
      shipping_method: store.shipping_method === "district" ? "district" : "distance",
      shipping_fixed_fee: toAmountInput(store.shipping_fixed_fee_cents),
      cover_image_url: store.cover_image_url ?? "",
      closed_dates: (store.closed_dates || []).slice().sort(),
      operating_hours: normalizeHours(store.operating_hours),
      is_delivery: store.is_delivery,
      allow_preorder_when_closed: store.allow_preorder_when_closed !== false,
      is_active: store.is_active,
    });
    setShippingError(null);
    setCoverFile(null);
    setOrderStatusColors(
      buildStatusColors(
        normalizeStatusList(store.order_statuses?.length ? store.order_statuses : DEFAULT_ORDER_STATUSES),
        store.order_status_colors ?? null,
        store.order_status_canceled_color ?? null
      )
    );
    const now = new Date();
    setCalendarMonth(new Date(now.getFullYear(), now.getMonth(), 1));
    setShowCalendarModal(false);
    setShowModal(true);

    try {
      const tiers = await adminFetch<ShippingTierApi[]>(`/admin/shipping/tiers?store_id=${encodeURIComponent(store.id)}`);
      setShippingTiers(normalizeTiers(tiers));
    } catch (e) {
      setShippingTiers([]);
      setShippingError(e instanceof Error ? e.message : "Falha ao carregar tabela de frete da loja");
    }
  }

  async function save() {
    const fixedFee = parseAmountInput(form.shipping_fixed_fee);
    const sla = Number(form.sla_minutes);
    if (fixedFee === null) return setError("Taxa fixa de frete invalida.");
    if (!Number.isFinite(sla) || sla <= 0) return setError("SLA invalido.");

    const orderStatuses = normalizeStatusList(parseCsv(form.order_statuses_input));
    const finalStatuses = normalizeStatusList(parseCsv(form.order_final_statuses_input)).filter((status) =>
      orderStatuses.includes(status)
    );
    const normalizedStatusColors = buildStatusColors(orderStatuses, orderStatusColors, orderStatusColors.canceled);

    const payload = {
      name: form.name.trim(),
      lat: Number(form.lat),
      lon: Number(form.lon),
      timezone: form.timezone,
      postal_code: normalizePostalCode(form.postal_code),
      street: form.street.trim() || null,
      number: form.number.trim() || null,
      district: form.district.trim() || null,
      city: form.city.trim() || null,
      state: form.state.trim() || null,
      complement: form.complement.trim() || null,
      reference: form.reference.trim() || null,
      phone: form.phone.trim() || null,
      whatsapp_contact_phone: form.whatsapp_contact_phone.trim() || null,
      sla_minutes: Math.round(sla),
      payment_methods: form.payment_methods,
      order_statuses: orderStatuses,
      order_final_statuses: finalStatuses,
      order_status_colors: normalizedStatusColors,
      order_status_canceled_color: normalizedStatusColors.canceled ?? null,
      shipping_method: form.shipping_method,
      shipping_fixed_fee_cents: fixedFee,
      cover_image_url: form.cover_image_url.trim() || null,
      closed_dates: form.closed_dates,
      operating_hours: form.operating_hours,
      is_delivery: form.is_delivery,
      allow_preorder_when_closed: form.allow_preorder_when_closed,
      is_active: form.is_active,
    };

    const tiersPayload =
      form.shipping_method === "distance"
        ? shippingTiers.map((tier, idx) => {
            const kmMin = Number(tier.km_min.replace(",", "."));
            const kmMax = Number(tier.km_max.replace(",", "."));
            const amount = parseAmountInput(tier.amount);
            if (!Number.isFinite(kmMin) || !Number.isFinite(kmMax) || amount === null) {
              throw new Error(`Preencha a faixa ${idx + 1}`);
            }
            if (kmMax <= kmMin) throw new Error(`Faixa ${idx + 1} invalida`);
            return { km_min: kmMin, km_max: kmMax, amount_cents: amount };
          })
        : [];

    try {
      setLoading(true);
      setError(null);
      setShippingError(null);

      const saved = editing
        ? await adminFetch<Store>(`/admin/stores/${editing.id}`, { method: "PATCH", body: JSON.stringify(payload) })
        : await adminFetch<Store>("/admin/stores", { method: "POST", body: JSON.stringify(payload) });

      await adminFetch(`/admin/shipping/tiers?store_id=${encodeURIComponent(saved.id)}`, {
        method: "PUT",
        body: JSON.stringify(tiersPayload),
      });

      if (coverFile) {
        const formData = new FormData();
        formData.append("file", coverFile);
        await adminUpload<Store>(`/admin/stores/${saved.id}/cover`, formData);
      }

      setShowModal(false);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao salvar loja");
    } finally {
      setLoading(false);
    }
  }

  async function removeCover() {
    if (!editing) return;
    try {
      const updated = await adminFetch<Store>(`/admin/stores/${editing.id}/cover`, { method: "DELETE" });
      setForm((prev) => ({ ...prev, cover_image_url: updated.cover_image_url ?? "" }));
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao remover capa");
    }
  }

  if (!ready) return null;

  return (
    <main className="min-h-screen text-slate-900 bg-[#f5f3ff]">
      <div className="max-w-7xl w-full mx-auto px-3 sm:px-4 lg:px-6 py-8">
        <div className="grid gap-6 lg:grid-cols-[260px_minmax(0,1fr)] items-start">
          <AdminSidebar
            menu={adminMenuWithHome}
            currentPath={pathname}
            collapsible
            orgName={tenantName}
            footer={
              <button
                onClick={logout}
                className="block px-3 py-2 w-full text-left rounded-lg bg-[#6320ee] text-[#f8f0fb] font-semibold hover:brightness-95 transition"
              >
                Sair
              </button>
            }
          />

          <div className="space-y-6">
            <header className="flex flex-wrap items-center justify-between gap-3">
              <div className="space-y-1">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-600">Admin - Lojas</p>
                <h1 className="text-3xl font-semibold">Lojas e configuracoes</h1>
              </div>
              <ProfileBadge />
            </header>

            {moduleBlocked ? (
              <section className="rounded-2xl bg-white border border-slate-200 p-4">
                <h2 className="text-lg font-semibold">Cadastro de lojas indisponivel</h2>
              </section>
            ) : (
              <>
                {error && !showModal && <p className="text-sm text-red-500">{error}</p>}

                <section className="rounded-2xl bg-white border border-slate-200 p-4 flex items-center justify-between">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-slate-600">Lojas ativas</p>
                    <h3 className="text-xl font-semibold">{activeStores}</h3>
                  </div>
                  <button onClick={openCreate} className="px-4 py-2 rounded-lg bg-[#6320ee] text-white text-sm font-semibold">
                    Nova loja
                  </button>
                </section>

                <section className="rounded-2xl bg-white border border-slate-200 p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <h2 className="text-lg font-semibold">Lojas</h2>
                    {loading && <span className="text-xs text-slate-600">Atualizando...</span>}
                  </div>
                  <div className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-50">
                    <table className="w-full text-xs sm:text-sm min-w-[760px]">
                      <thead className="bg-slate-100 text-left">
                        <tr>
                          <th className="px-3 py-2">Nome</th>
                          <th className="px-3 py-2">Endereco</th>
                          <th className="px-3 py-2">Entrega</th>
                          <th className="px-3 py-2">Status</th>
                          <th className="px-3 py-2 text-right">Acoes</th>
                        </tr>
                      </thead>
                      <tbody>
                        {stores.map((store) => (
                          <tr key={store.id}>
                            <td className="px-3 py-2 font-medium">{store.name}</td>
                            <td className="px-3 py-2">
                              {store.street
                                ? `${store.street}${store.number ? `, ${store.number}` : ""} - ${store.city ?? ""}/${store.state ?? ""}`
                                : "-"}
                            </td>
                            <td className="px-3 py-2">{store.is_delivery ? "Entrega" : "Pickup"}</td>
                            <td className="px-3 py-2">{store.is_active ? "Ativa" : "Inativa"}</td>
                            <td className="px-3 py-2 text-right">
                              <div className="flex items-center justify-end gap-2">
                                <button
                                  type="button"
                                  onClick={() => copyStoreLink(store)}
                                  className="px-3 py-1 rounded-lg bg-white border border-slate-200 text-slate-700 text-xs"
                                >
                                  {copiedStoreId === store.id ? "Copiado" : "Copiar link"}
                                </button>
                                <button
                                  onClick={() => openSettings(store)}
                                  className="px-3 py-1 rounded-lg bg-[#6320ee] text-white text-xs"
                                >
                                  Configuracoes
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>

                <section className="rounded-2xl bg-white border border-slate-200 p-4 space-y-3">
                  <h2 className="text-lg font-semibold">Usuarios e permissoes</h2>
                  <button
                    onClick={() => setShowUsersModal(true)}
                    className="px-4 py-2 rounded-lg bg-slate-100 border border-slate-200 text-slate-700 text-sm font-semibold"
                  >
                    Gerenciar usuarios e permissoes
                  </button>
                </section>
              </>
            )}
          </div>
        </div>
      </div>

      {!moduleBlocked && showModal && (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-slate-900/90 backdrop-blur-sm px-4 py-6 overflow-y-auto">
          <div className="w-full max-w-5xl rounded-3xl bg-white border border-slate-200 p-6 space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-neutral-500">{editing ? "Configuracoes" : "Nova"} loja</p>
                <h3 className="text-xl font-semibold">{editing ? editing.name : "Cadastrar loja"}</h3>
              </div>
              <button onClick={() => setShowModal(false)} className="text-sm px-3 py-1 rounded-full bg-neutral-100 border border-neutral-200">
                Fechar
              </button>
            </div>
            {error && <p className="text-sm text-red-500">{error}</p>}

            <section className="rounded-2xl border border-slate-200 p-4 space-y-2">
              <h4 className="text-base font-semibold">Endereco</h4>
              <div className="grid md:grid-cols-2 gap-2 text-sm">
                <input className="input" placeholder="Nome" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
                <input className="input" placeholder="Fuso horario" value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} />
                <input className="input" placeholder="Latitude" value={form.lat} onChange={(e) => setForm({ ...form, lat: e.target.value })} />
                <input className="input" placeholder="Longitude" value={form.lon} onChange={(e) => setForm({ ...form, lon: e.target.value })} />
                <input className="input" placeholder="CEP" value={form.postal_code} onChange={(e) => setForm({ ...form, postal_code: e.target.value })} />
                <input className="input" placeholder="Rua" value={form.street} onChange={(e) => setForm({ ...form, street: e.target.value })} />
                <input className="input" placeholder="Numero" value={form.number} onChange={(e) => setForm({ ...form, number: e.target.value })} />
                <input className="input" placeholder="Bairro" value={form.district} onChange={(e) => setForm({ ...form, district: e.target.value })} />
                <input className="input" placeholder="Cidade" value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} />
                <input className="input" placeholder="UF" value={form.state} onChange={(e) => setForm({ ...form, state: e.target.value })} />
                <input className="input" placeholder="Complemento" value={form.complement} onChange={(e) => setForm({ ...form, complement: e.target.value })} />
                <input className="input" placeholder="Referencia" value={form.reference} onChange={(e) => setForm({ ...form, reference: e.target.value })} />
              </div>
            </section>

            <section className="rounded-2xl border border-slate-200 p-4 space-y-2">
              <h4 className="text-base font-semibold">Numero de contato</h4>
              <div className="grid md:grid-cols-2 gap-2 text-sm">
                <input
                  className="input"
                  placeholder="Telefone da loja"
                  value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                />
                <input
                  className="input"
                  placeholder="Contato WhatsApp"
                  value={form.whatsapp_contact_phone}
                  onChange={(e) => setForm({ ...form, whatsapp_contact_phone: e.target.value })}
                />
              </div>
            </section>

            <section className="rounded-2xl border border-slate-200 p-4 space-y-2">
              <h4 className="text-base font-semibold">SLA de entrega</h4>
              <div className="max-w-[240px]">
                <input
                  className="input w-full"
                  type="number"
                  min="1"
                  placeholder="SLA (minutos)"
                  value={form.sla_minutes}
                  onChange={(e) => setForm({ ...form, sla_minutes: e.target.value })}
                />
              </div>
            </section>

            <section className="rounded-2xl border border-slate-200 p-4 space-y-2">
              <h4 className="text-base font-semibold">Formas de pagamento</h4>
              <div className="flex flex-wrap gap-4 text-sm">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={form.payment_methods.includes("pix")}
                    onChange={() => {
                      setForm((prev) => ({
                        ...prev,
                        payment_methods: prev.payment_methods.includes("pix")
                          ? prev.payment_methods.filter((item) => item !== "pix")
                          : [...prev.payment_methods, "pix"],
                      }));
                    }}
                  />
                  PIX
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={form.payment_methods.includes("cash")}
                    onChange={() => {
                      setForm((prev) => ({
                        ...prev,
                        payment_methods: prev.payment_methods.includes("cash")
                          ? prev.payment_methods.filter((item) => item !== "cash")
                          : [...prev.payment_methods, "cash"],
                      }));
                    }}
                  />
                  Dinheiro
                </label>
              </div>
            </section>

            <section className="rounded-2xl border border-slate-200 p-4 space-y-2">
              <h4 className="text-base font-semibold">Status dos pedidos</h4>
              <input
                className="input w-full"
                value={form.order_statuses_input}
                onChange={(e) => setForm({ ...form, order_statuses_input: e.target.value })}
                placeholder="status separados por virgula"
              />
              <input
                className="input w-full"
                value={form.order_final_statuses_input}
                onChange={(e) => setForm({ ...form, order_final_statuses_input: e.target.value })}
                placeholder="status finais separados por virgula"
              />
              <div className="grid gap-2 pt-1">
                {orderStatusList.map((status) => (
                  <div key={status} className="grid grid-cols-[minmax(0,1fr)_110px_120px] gap-2 items-center">
                    <span className="text-sm text-slate-700">{formatStatusLabel(status)}</span>
                    <input
                      type="color"
                      className="h-9 w-full rounded-lg border border-slate-200 bg-white p-1"
                      value={orderStatusColors[status] ?? defaultColorForStatus(status)}
                      onChange={(e) =>
                        setOrderStatusColors((prev) => ({
                          ...prev,
                          [status]: e.target.value,
                        }))
                      }
                    />
                    <input
                      className="input h-9"
                      value={orderStatusColors[status] ?? defaultColorForStatus(status)}
                      onChange={(e) =>
                        setOrderStatusColors((prev) => ({
                          ...prev,
                          [status]: e.target.value,
                        }))
                      }
                      placeholder="#e2e8f0"
                    />
                  </div>
                ))}
              </div>
            </section>

            <section className="rounded-2xl border border-slate-200 p-4 space-y-2">
              <h4 className="text-base font-semibold">Frete</h4>
              <div className="grid md:grid-cols-2 gap-2 text-sm">
                <select className="input" value={form.shipping_method} onChange={(e) => setForm({ ...form, shipping_method: e.target.value as ShippingMethod })}>
                  <option value="distance">Por distancia</option>
                  <option value="district" disabled>Por bairro (em breve)</option>
                </select>
                <input className="input" type="number" step="0.01" min="0" value={form.shipping_fixed_fee} onChange={(e) => setForm({ ...form, shipping_fixed_fee: e.target.value })} placeholder="Taxa fixa" />
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Tabela por distancia</span>
                  <button type="button" onClick={() => setShippingTiers((prev) => prev.length >= MAX_DISTANCE_TIERS ? prev : [...prev, { km_min: "", km_max: "", amount: "" }])} className="px-3 py-1 rounded-lg bg-slate-100 border border-slate-200 text-xs">Adicionar faixa</button>
                </div>
                {shippingTiers.map((tier, index) => (
                  <div key={index} className="grid grid-cols-[1fr_1fr_1fr_auto] gap-2">
                    <input className="input" placeholder="De km" value={tier.km_min} onChange={(e) => updateTier(index, { km_min: e.target.value })} />
                    <input className="input" placeholder="Ate km" value={tier.km_max} onChange={(e) => updateTier(index, { km_max: e.target.value })} />
                    <input className="input" placeholder="Valor R$" value={tier.amount} onChange={(e) => updateTier(index, { amount: e.target.value })} />
                    <button type="button" onClick={() => setShippingTiers((prev) => prev.filter((_, idx) => idx !== index))} className="px-3 py-1 rounded-lg bg-white border border-red-200 text-red-600 text-xs">Remover</button>
                  </div>
                ))}
                {shippingError && <p className="text-xs text-red-600">{shippingError}</p>}
              </div>
            </section>

            <section className="rounded-2xl border border-slate-200 p-4 space-y-2">
              <h4 className="text-base font-semibold">Horario e calendario</h4>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm text-slate-600">
                  {form.closed_dates.length} data(s) selecionada(s) no calendario.
                </p>
                <button
                  type="button"
                  className="px-3 py-2 rounded-lg bg-slate-100 border border-slate-200 text-sm"
                  onClick={() => setShowCalendarModal(true)}
                >
                  Abrir calendario
                </button>
              </div>
              <div className="grid md:grid-cols-2 gap-2">
                {OPERATING_DAYS.map((day) => {
                  const entry = form.operating_hours.find((item) => item.day === day.day);
                  return (
                    <div key={day.day} className="rounded-lg border border-slate-200 p-2 text-xs space-y-1">
                      <label className="flex items-center gap-2"><input type="checkbox" checked={entry?.enabled ?? false} onChange={(e) => setHour(day.day, { enabled: e.target.checked })} /> {day.label}</label>
                      <div className="flex gap-1">
                        <input type="time" className="input h-8" value={entry?.open ?? "08:00"} onChange={(e) => setHour(day.day, { open: e.target.value })} disabled={!entry?.enabled} />
                        <input type="time" className="input h-8" value={entry?.close ?? "18:00"} onChange={(e) => setHour(day.day, { close: e.target.value })} disabled={!entry?.enabled} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>

            <section className="rounded-2xl border border-slate-200 p-4 space-y-2">
              <h4 className="text-base font-semibold">Capa da vitrine</h4>
              <input className="input w-full" placeholder="URL da capa" value={form.cover_image_url} onChange={(e) => setForm({ ...form, cover_image_url: e.target.value })} />
              <div className="flex gap-2 items-center">
                <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => setCoverFile(e.target.files?.[0] ?? null)} />
                {editing && <button type="button" onClick={removeCover} className="px-3 py-1 rounded-lg bg-white border border-red-200 text-red-600 text-xs">Remover capa</button>}
              </div>
            </section>

            <section className="rounded-2xl border border-slate-200 p-4 flex flex-wrap gap-4 text-sm">
              <label className="flex items-center gap-2"><input type="checkbox" checked={form.is_delivery} onChange={(e) => setForm({ ...form, is_delivery: e.target.checked })} /> Entrega habilitada</label>
              <label className="flex items-center gap-2"><input type="checkbox" checked={form.allow_preorder_when_closed} onChange={(e) => setForm({ ...form, allow_preorder_when_closed: e.target.checked })} /> Permitir encomenda com loja fechada</label>
              <label className="flex items-center gap-2"><input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} /> Loja ativa</label>
            </section>

            <div className="flex justify-end gap-3">
              <button onClick={() => setShowModal(false)} className="px-4 py-2 rounded-lg bg-neutral-100 text-neutral-800 text-sm">Cancelar</button>
              <button onClick={save} disabled={loading || !form.name.trim() || !form.lat.trim() || !form.lon.trim()} className="px-4 py-2 rounded-lg bg-[#6320ee] text-white text-sm font-semibold disabled:opacity-50">
                {editing ? "Salvar configuracoes" : "Criar loja"}
              </button>
            </div>
          </div>
        </div>
      )}

      {showCalendarModal && (
        <div className="fixed inset-0 z-[65] flex items-center justify-center bg-slate-900/80 backdrop-blur-sm px-4">
          <div className="w-full max-w-lg rounded-3xl bg-white text-[#211a1d] shadow-2xl p-6 space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between gap-2">
              <div>
                <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Calendario</p>
                <h3 className="text-lg font-semibold">Datas de funcionamento</h3>
              </div>
              <button
                type="button"
                onClick={() => setShowCalendarModal(false)}
                className="text-sm px-3 py-1 rounded-full bg-neutral-100 border border-neutral-200 hover:bg-neutral-200"
              >
                Fechar
              </button>
            </div>

            <div className="flex items-center justify-between">
              <button
                type="button"
                onClick={() => setCalendarMonth((prev) => shiftMonth(prev, -1))}
                className="px-2 py-1 rounded-lg bg-slate-100 border border-slate-200 text-sm"
              >
                {"<"}
              </button>
              <div className="text-sm font-semibold">
                {calendarMonth.toLocaleString("pt-BR", { month: "long", year: "numeric" })}
              </div>
              <button
                type="button"
                onClick={() => setCalendarMonth((prev) => shiftMonth(prev, 1))}
                className="px-2 py-1 rounded-lg bg-slate-100 border border-slate-200 text-sm"
              >
                {">"}
              </button>
            </div>

            <div className="grid grid-cols-7 gap-2 text-xs text-slate-500">
              {["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"].map((day) => (
                <div key={day} className="text-center font-semibold">
                  {day}
                </div>
              ))}
            </div>

            <div className="grid grid-cols-7 gap-2">
              {buildCalendarDays(calendarMonth).map((cell, idx) => {
                if (!cell.date) return <div key={`empty-${idx}`} className="h-10" />;
                const iso = formatIsoDate(cell.date);
                const selected = form.closed_dates.includes(iso);
                return (
                  <button
                    key={iso}
                    type="button"
                    onClick={() => {
                      const next = selected
                        ? form.closed_dates.filter((item) => item !== iso)
                        : Array.from(new Set([...form.closed_dates, iso])).sort();
                      setForm((prev) => ({ ...prev, closed_dates: next }));
                    }}
                    className={`h-10 rounded-xl text-sm font-semibold border transition ${
                      selected
                        ? "bg-emerald-500 text-white border-emerald-500"
                        : "bg-white text-slate-700 border-slate-200 hover:border-emerald-300"
                    }`}
                  >
                    {cell.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {showUsersModal && (
        <div className="fixed inset-0 z-[70] flex items-start justify-center bg-slate-900/90 backdrop-blur-sm px-4 py-6 overflow-y-auto">
          <div className="w-full max-w-6xl rounded-3xl bg-white border border-slate-200 p-6 space-y-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-2xl font-semibold">Usuarios e permissoes</h2>
              </div>
              <button onClick={() => setShowUsersModal(false)} className="text-sm px-3 py-1 rounded-full bg-slate-100 border border-slate-200">Fechar</button>
            </div>
            <UsersManagerPanel />
          </div>
        </div>
      )}
    </main>
  );
}
