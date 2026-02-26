"use client";
import { useEffect, useRef, useState } from "react";
import { adminFetch } from "@/lib/admin-api";
import { useAdminGuard } from "@/lib/use-admin-guard";
import { ProfileBadge } from "@/components/admin/ProfileBadge";
import { AdminSidebar } from "@/components/admin/AdminSidebar";
import { adminMenuWithHome } from "@/config/adminMenu";
import { usePathname } from "next/navigation";
import { useOrgName } from "@/lib/use-org-name";
import { clearAdminToken } from "@/lib/admin-auth";
import { useTenantModules } from "@/lib/use-tenant-modules";
import { Product } from "@/types";

type OrderRow = {
  id: string;
  customer_name: string | null;
  created_at: string;
  delivery_date?: string | null;
  status: string;
  total_cents: number;
  store_id?: string | null;
  notes?: string | null;
};

type OrderItem = {
  name: string;
  product_id: string;
  quantity: number;
  unit_price_cents: number;
};

type OrderDetail = OrderRow & {
  pickup: boolean;
  subtotal_cents: number;
  shipping_cents?: number | null;
  discount_cents?: number | null;
  total_cents: number;
  items: OrderItem[];
  customer_id?: string | null;
  delivery?: {
    postal_code?: string | null;
    street?: string | null;
    number?: string | null;
    complement?: string | null;
    district?: string | null;
    city?: string | null;
    state?: string | null;
    reference?: string | null;
  } | null;
};

type OrdersSummary = {
  open_count: number;
  revenue_today_cents: number;
  orders_today: number;
};

type StatusSummaryItem = {
  status: string;
  count: number;
};

type ProductOption = {
  id: string;
  name: string;
  price_cents: number;
};

type CustomerOption = {
  id: string;
  name: string;
  phone?: string | null;
};

type WhatsAppLog = {
  id: string;
  order_id?: string | null;
  to_phone: string;
  status: string;
  provider_message_id?: string | null;
  error_message?: string | null;
  created_at: string;
};

type StatusOption = { label: string; value: string };
type ConfigPayload = {
  order_statuses?: string[] | null;
  order_status_canceled_color?: string | null;
  order_status_colors?: Record<string, string> | null;
};

type StoreOption = {
  id: string;
  name: string;
  slug?: string;
};

type GroupOptionsPayload = {
  stores: StoreOption[];
};

const DEFAULT_STATUS_VALUES = [
  "received",
  "confirmed",
  "preparing",
  "ready",
  "on_route",
  "delivered",
  "completed",
  "canceled",
];

const STATUS_LABELS: Record<string, string> = {
  pending: "Pendente",
  received: "Recebido",
  confirmed: "Confirmado",
  preparing: "Preparando",
  ready: "Pronto",
  on_route: "Em rota",
  delivered: "Entregue",
  completed: "Concluido",
  canceled: "Cancelado",
};

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

const AUTO_REFRESH_OPTIONS = [3, 10, 15];
const AUTO_REFRESH_KEY = "orders-auto-refresh";
const SOUND_KEY = "orders-sound";

function formatStatusLabel(value: string) {
  const known = STATUS_LABELS[value];
  if (known) return known;
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function normalizeStatusValues(values?: string[] | null) {
  if (!values || values.length === 0) return [...DEFAULT_STATUS_VALUES];
  const cleaned = values.map((item) => String(item).trim()).filter((item) => item.length > 0);
  const unique = Array.from(new Set(cleaned));
  if (!unique.includes("canceled")) {
    unique.push("canceled");
  }
  return unique.length > 0 ? unique : [...DEFAULT_STATUS_VALUES];
}

function buildStatusOptions(values: string[]): StatusOption[] {
  return [
    { label: "Todos", value: "" },
    ...values.map((value) => ({ value, label: formatStatusLabel(value) })),
  ];
}

export default function OrdersPage() {
  const ready = useAdminGuard();
  const tenantName = useOrgName();
  const pathname = usePathname();
  const { hasModule, ready: modulesReady } = useTenantModules();
  const showRevenueTodayCard = modulesReady ? hasModule("insights") : false;
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

  const [orders, setOrders] = useState<OrderRow[]>([]);
  const [stores, setStores] = useState<StoreOption[]>([]);
  const [selectedStoreIds, setSelectedStoreIds] = useState<string[]>([]);
  const [storeFilterOpen, setStoreFilterOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState("30"); // days
  const [status, setStatus] = useState("");
  const [customer, setCustomer] = useState("");
  const [sortBy, setSortBy] = useState("created_at");
  const [sortDir, setSortDir] = useState("desc");
  const [pageSize, setPageSize] = useState("30");
  const [page, setPage] = useState(1);
  const [filterOpen, setFilterOpen] = useState(false);
  const [selectedOrder, setSelectedOrder] = useState<OrderDetail | null>(null);
  const [panelMode, setPanelMode] = useState<"view" | "edit" | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [whatsappLogs, setWhatsappLogs] = useState<WhatsAppLog[]>([]);
  const [whatsappLoading, setWhatsappLoading] = useState(false);
  const [whatsappError, setWhatsappError] = useState<string | null>(null);
  const [catalog, setCatalog] = useState<ProductOption[]>([]);
  const [editItems, setEditItems] = useState<OrderItem[]>([]);
  const [editCustomerSearch, setEditCustomerSearch] = useState("");
  const [customerOptions, setCustomerOptions] = useState<CustomerOption[]>([]);
  const [editCustomerId, setEditCustomerId] = useState("");
  const [editReceivedDate, setEditReceivedDate] = useState("");
  const [editDeliveryDate, setEditDeliveryDate] = useState("");
  const [saving, setSaving] = useState(false);
  const [statusEditorId, setStatusEditorId] = useState<string | null>(null);
  const [statusOptions, setStatusOptions] = useState<StatusOption[]>(
    buildStatusOptions(DEFAULT_STATUS_VALUES)
  );
  const [statusColors, setStatusColors] = useState<Record<string, string>>({});
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(false);
  const [autoRefreshInterval, setAutoRefreshInterval] = useState(AUTO_REFRESH_OPTIONS[0]);
  const [summary, setSummary] = useState<OrdersSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [openOrders, setOpenOrders] = useState<OrderRow[]>([]);
  const [openOrdersLoading, setOpenOrdersLoading] = useState(false);
  const [openOrdersError, setOpenOrdersError] = useState<string | null>(null);
  const [statusSummary, setStatusSummary] = useState<StatusSummaryItem[]>([]);
  const [statusSummaryLoading, setStatusSummaryLoading] = useState(false);
  const [statusSummaryError, setStatusSummaryError] = useState<string | null>(null);
  const [soundEnabled, setSoundEnabled] = useState(false);
  const [addressCopied, setAddressCopied] = useState(false);
  const openOrdersIdsRef = useRef<Set<string> | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const selectedStoreKey = selectedStoreIds.join(",");

  function appendStoreFilters(qs: URLSearchParams) {
    selectedStoreIds.forEach((storeId) => qs.append("store_ids", storeId));
  }

  async function loadStores() {
    try {
      const options = await adminFetch<GroupOptionsPayload>("/admin/groups/options");
      const accessibleStores = options.stores || [];
      setStores(accessibleStores);
      setSelectedStoreIds((current) => {
        const allowedIds = new Set(accessibleStores.map((store) => store.id));
        const preserved = current.filter((storeId) => allowedIds.has(storeId));
        if (preserved.length > 0) return preserved;
        return accessibleStores.map((store) => store.id);
      });
    } catch {
      setStores([]);
      setSelectedStoreIds([]);
    }
  }

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const qs = new URLSearchParams();
      if (status) qs.set("status", status);
      if (customer) qs.set("customer", customer);
      if (period) qs.set("days", period);
      if (pageSize) qs.set("limit", pageSize);
      if (sortBy) qs.set("order_by", sortBy);
      if (sortDir) qs.set("order_dir", sortDir);
      qs.set("page", String(page));
      appendStoreFilters(qs);
      const res = await adminFetch<OrderRow[]>(`/orders?${qs.toString()}`);
      setOrders(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao carregar pedidos");
    } finally {
      setLoading(false);
    }
  }

  async function loadSummary() {
    setSummaryLoading(true);
    setSummaryError(null);
    try {
      const qs = new URLSearchParams();
      appendStoreFilters(qs);
      const query = qs.toString();
      const res = await adminFetch<OrdersSummary>(`/admin/orders/summary${query ? `?${query}` : ""}`);
      setSummary(res);
    } catch (e) {
      setSummaryError(e instanceof Error ? e.message : "Falha ao carregar resumo");
    } finally {
      setSummaryLoading(false);
    }
  }

  async function loadStatusSummary() {
    setStatusSummaryLoading(true);
    setStatusSummaryError(null);
    try {
      const qs = new URLSearchParams();
      appendStoreFilters(qs);
      const query = qs.toString();
      const res = await adminFetch<{ items: StatusSummaryItem[] }>(
        `/admin/orders/status-summary${query ? `?${query}` : ""}`
      );
      setStatusSummary(res.items ?? []);
    } catch (e) {
      setStatusSummaryError(e instanceof Error ? e.message : "Falha ao carregar status do dia");
    } finally {
      setStatusSummaryLoading(false);
    }
  }

  function getAudioContext() {
    if (typeof window === "undefined") return null;
    const AudioCtx =
      window.AudioContext ||
      (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioCtx) return null;
    if (!audioContextRef.current) {
      audioContextRef.current = new AudioCtx();
    }
    return audioContextRef.current;
  }

  function primeAudioContext() {
    const ctx = getAudioContext();
    if (ctx && ctx.state === "suspended") {
      void ctx.resume();
    }
  }

  function playNotificationSound() {
    if (!soundEnabled) return;
    const ctx = getAudioContext();
    if (!ctx) return;
    if (ctx.state === "suspended") {
      void ctx.resume();
    }
    const now = ctx.currentTime;
    const gain = ctx.createGain();
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(0.2, now + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.6);
    gain.connect(ctx.destination);

    const osc1 = ctx.createOscillator();
    osc1.type = "sine";
    osc1.frequency.setValueAtTime(880, now);
    osc1.frequency.exponentialRampToValueAtTime(660, now + 0.25);

    const osc2 = ctx.createOscillator();
    osc2.type = "sine";
    osc2.frequency.setValueAtTime(1320, now);
    osc2.frequency.exponentialRampToValueAtTime(990, now + 0.25);

    osc1.connect(gain);
    osc2.connect(gain);
    osc1.start(now);
    osc2.start(now);
    osc1.stop(now + 0.35);
    osc2.stop(now + 0.35);
    osc1.onended = () => gain.disconnect();
  }

  async function loadOpenOrders() {
    setOpenOrdersLoading(true);
    setOpenOrdersError(null);
    try {
      const qs = new URLSearchParams();
      appendStoreFilters(qs);
      const query = qs.toString();
      const res = await adminFetch<OrderRow[]>(`/admin/orders/open${query ? `?${query}` : ""}`);
      const ordered = [...res].sort(
        (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
      );
      if (soundEnabled && openOrdersIdsRef.current) {
        const hasNew = ordered.some((order) => !openOrdersIdsRef.current?.has(order.id));
        if (hasNew) playNotificationSound();
      }
      openOrdersIdsRef.current = new Set(ordered.map((order) => order.id));
      setOpenOrders(ordered);
    } catch (e) {
      setOpenOrdersError(e instanceof Error ? e.message : "Falha ao carregar pedidos em aberto");
    } finally {
      setOpenOrdersLoading(false);
    }
  }

  async function loadStatusOptions() {
    try {
      const qs = new URLSearchParams();
      appendStoreFilters(qs);
      const query = qs.toString();
      const cfg = await adminFetch<ConfigPayload>(
        `/admin/orders/status-options${query ? `?${query}` : ""}`
      );
      const values = normalizeStatusValues(cfg.order_statuses ?? null);
      setStatusOptions(buildStatusOptions(values));
      setStatus((current) => (values.includes(current) ? current : ""));
      setStatusColors(
        normalizeStatusColors(
          cfg.order_status_colors ?? null,
          values,
          normalizeHexColor(cfg.order_status_canceled_color ?? null)
        )
      );
    } catch {
      setStatusOptions(buildStatusOptions(DEFAULT_STATUS_VALUES));
      setStatusColors({});
    }
  }

  async function loadDashboard() {
    await Promise.all([loadSummary(), loadOpenOrders(), loadStatusSummary()]);
  }

  async function refreshAll() {
    await Promise.all([load(), loadDashboard(), loadStatusOptions()]);
  }

  useEffect(() => {
    if (ready) {
      loadStores();
      load();
      loadDashboard();
      loadStatusOptions();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const raw = window.localStorage.getItem(AUTO_REFRESH_KEY);
    if (!raw) return;
    try {
      const parsed = JSON.parse(raw) as { enabled?: boolean; interval?: number };
      if (typeof parsed.enabled === "boolean") setAutoRefreshEnabled(parsed.enabled);
      if (AUTO_REFRESH_OPTIONS.includes(parsed.interval ?? -1)) {
        setAutoRefreshInterval(parsed.interval ?? AUTO_REFRESH_OPTIONS[0]);
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(
      AUTO_REFRESH_KEY,
      JSON.stringify({ enabled: autoRefreshEnabled, interval: autoRefreshInterval })
    );
  }, [autoRefreshEnabled, autoRefreshInterval]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const raw = window.localStorage.getItem(SOUND_KEY);
    if (!raw) return;
    try {
      const parsed = JSON.parse(raw) as { enabled?: boolean };
      if (typeof parsed.enabled === "boolean") setSoundEnabled(parsed.enabled);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(SOUND_KEY, JSON.stringify({ enabled: soundEnabled }));
  }, [soundEnabled]);

  useEffect(() => {
    if (!autoRefreshEnabled) return;
    const intervalMs = autoRefreshInterval * 60 * 1000;
    const handle = setInterval(() => {
      if (ready) refreshAll();
    }, intervalMs);
    return () => clearInterval(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    autoRefreshEnabled,
    autoRefreshInterval,
    ready,
    page,
    pageSize,
    status,
    customer,
    period,
    sortBy,
    sortDir,
    selectedStoreKey,
    soundEnabled,
  ]);

  useEffect(() => {
    if (!ready) return;
    setPage(1);
    refreshAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedStoreKey, ready]);

  function normalizeHexColor(value?: string | null) {
    if (!value) return null;
    const trimmed = value.trim();
    if (/^#[0-9a-fA-F]{6}$/.test(trimmed)) return trimmed;
    if (/^#[0-9a-fA-F]{3}$/.test(trimmed)) {
      const r = trimmed[1];
      const g = trimmed[2];
      const b = trimmed[3];
      return `#${r}${r}${g}${g}${b}${b}`;
    }
    return null;
  }

function normalizeStatusColors(
  colors: Record<string, string> | null,
  statuses: string[],
  canceledFallback: string | null
) {
  const result: Record<string, string> = {};
  statuses.forEach((status) => {
    const raw =
      colors?.[status] ??
      (status === "canceled" ? canceledFallback : null) ??
      DEFAULT_STATUS_COLORS[status];
    const normalized = normalizeHexColor(raw);
    if (normalized) result[status] = normalized;
  });
  return result;
}

  function textColorFor(hex: string) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    const luminance = 0.299 * r + 0.587 * g + 0.114 * b;
    return luminance > 160 ? "#1f2937" : "#ffffff";
  }

  function statusLabelFor(value: string) {
    return statusOptions.find((option) => option.value === value)?.label ?? formatStatusLabel(value);
  }

  function statusBadgeStyle(value: string) {
    const color = statusColors[value];
    if (!color) return undefined;
    return {
      backgroundColor: color,
      borderColor: color,
      color: textColorFor(color),
    } as const;
  }

  function rgbaFromHex(hex: string, alpha: number) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  function statusCardStyle(value: string) {
    const color = statusColors[value];
    if (!color) return undefined;
    return {
      backgroundColor: rgbaFromHex(color, 0.24),
      borderColor: color,
      boxShadow: `inset 4px 0 0 ${color}`,
    } as const;
  }

  function statusRowStyle(value: string) {
    const color = statusColors[value];
    if (!color) return undefined;
    return {
      backgroundColor: rgbaFromHex(color, 0.16),
      boxShadow: `inset 4px 0 0 ${color}`,
    } as const;
  }

  function statusCountCardStyle(value: string) {
    const color = statusColors[value];
    if (!color) return undefined;
    return {
      backgroundColor: rgbaFromHex(color, 0.18),
      borderColor: color,
    } as const;
  }

  async function updateStatus(orderId: string, newStatus: string) {
    try {
      await adminFetch(`/admin/orders/${orderId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: newStatus }),
      });
      await refreshAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao atualizar status");
    }
  }

  const formatDateTime = (value?: string | null) => {
    if (!value) return "-";
    return new Date(value).toLocaleString("pt-BR", {
      dateStyle: "short",
      timeStyle: "short",
    });
  };

  const formatDate = (value?: string | null) => {
    if (!value) return "-";
    return new Date(value).toLocaleDateString("pt-BR");
  };

  const toDateInputValue = (value?: string | null) => {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  };

  const formatMoney = (cents: number) =>
    (cents / 100).toLocaleString("pt-BR", {
      style: "currency",
      currency: "BRL",
    });

  const buildDeliveryAddress = (delivery?: OrderDetail["delivery"] | null) => {
    if (!delivery) return "";
    const street = delivery.street || "";
    const number = delivery.number || "";
    const complement = delivery.complement ? ` (${delivery.complement})` : "";
    const district = delivery.district || "";
    const city = delivery.city || "";
    const state = delivery.state || "";
    const postal = delivery.postal_code || "";
    const reference = delivery.reference ? ` | Ref: ${delivery.reference}` : "";
    const line1 = [street, number].filter(Boolean).join(",") + complement;
    const line2 = [district, [city, state].filter(Boolean).join("/")].filter(Boolean).join(" - ");
    const line3 = postal ? `CEP: ${postal}${reference}` : reference.replace(/^ \| /, "");
    return [line1, line2, line3].filter((value) => value && value.trim()).join("\n");
  };

  const copyToClipboard = (text: string) => {
    if (!text) return;
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(text).catch(() => {});
      return;
    }
    if (typeof document === "undefined") return;
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "true");
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    try {
      document.execCommand("copy");
    } catch {
      /* ignore */
    }
    document.body.removeChild(textarea);
  };

  async function loadOrderDetail(orderId: string) {
    setDetailLoading(true);
    setDetailError(null);
    try {
      const res = await adminFetch<OrderDetail>(`/orders/${orderId}`);
      setSelectedOrder(res);
    } catch (e) {
      setDetailError(e instanceof Error ? e.message : "Falha ao carregar pedido");
    } finally {
      setDetailLoading(false);
    }
  }

  async function loadWhatsappLogs(orderId: string) {
    setWhatsappLoading(true);
    setWhatsappError(null);
    try {
      const qs = new URLSearchParams();
      qs.set("order_id", orderId);
      qs.set("limit", "20");
      const res = await adminFetch<WhatsAppLog[]>(`/admin/whatsapp/logs?${qs.toString()}`);
      setWhatsappLogs(res);
    } catch (e) {
      setWhatsappError(e instanceof Error ? e.message : "Falha ao carregar logs do WhatsApp");
      setWhatsappLogs([]);
    } finally {
      setWhatsappLoading(false);
    }
  }

  async function loadCatalog() {
    if (catalog.length) return;
    const res = await adminFetch<{ products: Product[] }>("/catalog");
    const options = (res.products ?? []).map((product) => ({
      id: product.id,
      name: product.name,
      price_cents: product.price_cents,
    }));
    setCatalog(options);
  }

  async function openPanel(orderId: string, mode: "view" | "edit") {
    setPanelMode(mode);
    await loadOrderDetail(orderId);
    if (mode === "edit") {
      await loadCatalog();
    }
  }

  function closePanel() {
    setPanelMode(null);
    setSelectedOrder(null);
    setDetailError(null);
    setEditCustomerSearch("");
    setCustomerOptions([]);
    setWhatsappLogs([]);
    setWhatsappError(null);
    setAddressCopied(false);
  }

  useEffect(() => {
    if (panelMode !== "edit" || !selectedOrder) return;
    setEditItems(selectedOrder.items ?? []);
    setEditCustomerId(selectedOrder.customer_id ?? "");
    setEditReceivedDate(toDateInputValue(selectedOrder.created_at));
    setEditDeliveryDate(selectedOrder.delivery_date ?? "");
  }, [panelMode, selectedOrder]);

  useEffect(() => {
    if (panelMode !== "view" || !selectedOrder) return;
    loadWhatsappLogs(selectedOrder.id);
  }, [panelMode, selectedOrder]);

  useEffect(() => {
    if (panelMode !== "edit") return;
    const term = editCustomerSearch.trim();
    const handle = setTimeout(async () => {
      try {
        const qs = new URLSearchParams();
        qs.set("page", "1");
        qs.set("limit", "20");
        qs.set("active", "all");
        if (term) qs.set("search", term);
        const res = await adminFetch<CustomerOption[]>(`/admin/customers?${qs.toString()}`);
        setCustomerOptions(res);
      } catch (e) {
        setDetailError(e instanceof Error ? e.message : "Falha ao buscar clientes");
      }
    }, 300);
    return () => clearTimeout(handle);
  }, [editCustomerSearch, panelMode]);

  function updateItem(idx: number, next: Partial<OrderItem>) {
    setEditItems((items) =>
      items.map((item, index) => {
        if (index !== idx) return item;
        const updated = { ...item, ...next };
        if (next.product_id) {
          const product = catalogOptions.find((p) => p.id === next.product_id);
          if (product) {
            updated.name = product.name;
            updated.unit_price_cents = product.price_cents;
          }
        }
        return updated;
      })
    );
  }

  function addItem() {
    const fallback = catalogOptions[0];
    if (!fallback) return;
    setEditItems((items) => [
      ...items,
      {
        name: fallback.name,
        product_id: fallback.id,
        quantity: 1,
        unit_price_cents: fallback.price_cents,
      },
    ]);
  }

  function removeItem(idx: number) {
    setEditItems((items) => items.filter((_, index) => index !== idx));
  }

  const subtotalCents = editItems.reduce((sum, item) => sum + item.unit_price_cents * item.quantity, 0);
  const discountCents = selectedOrder?.discount_cents ?? 0;
  const shippingCents = selectedOrder?.shipping_cents ?? 0;
  const estimatedTotalCents = Math.max(subtotalCents + shippingCents - discountCents, 0);
  const catalogOptions = (() => {
    const map = new Map(catalog.map((item) => [item.id, item]));
    if (selectedOrder?.items) {
      selectedOrder.items.forEach((item) => {
        if (!map.has(item.product_id)) {
          map.set(item.product_id, {
            id: item.product_id,
            name: item.name,
            price_cents: item.unit_price_cents,
          });
        }
      });
    }
    return Array.from(map.values());
  })();
  const mergedCustomerOptions =
    selectedOrder?.customer_id && !customerOptions.some((c) => c.id === selectedOrder.customer_id)
      ? [
          {
            id: selectedOrder.customer_id,
            name: selectedOrder.customer_name || "Cliente atual",
          },
          ...customerOptions,
        ]
      : customerOptions;

  async function saveEdit() {
    if (!selectedOrder) return;
    if (!editCustomerId) {
      setDetailError("Selecione um cliente.");
      return;
    }
    if (!editItems.length) {
      setDetailError("Adicione ao menos um item.");
      return;
    }
    try {
      setSaving(true);
      setDetailError(null);
      await adminFetch(`/admin/orders/${selectedOrder.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          customer_id: editCustomerId,
          received_date: editReceivedDate || null,
          delivery_date: editDeliveryDate || null,
          items: editItems.map((item) => ({ product_id: item.product_id, quantity: item.quantity })),
        }),
      });
      await refreshAll();
      closePanel();
    } catch (e) {
      setDetailError(e instanceof Error ? e.message : "Falha ao salvar pedido");
    } finally {
      setSaving(false);
    }
  }

  function toggleStoreFilter(storeId: string) {
    setSelectedStoreIds((current) => {
      const exists = current.includes(storeId);
      if (exists) {
        if (current.length === 1) return current;
        return current.filter((id) => id !== storeId);
      }
      return [...current, storeId];
    });
  }

  const storeName = (id?: string | null) => {
    if (!id) return "-";
    return stores.find((s) => s.id === id)?.name ?? "-";
  };
  const selectedStoresLabel =
    stores.length <= 1
      ? stores[0]?.name ?? "Loja"
      : selectedStoreIds.length === stores.length
        ? "Todas as lojas"
        : `${selectedStoreIds.length} loja(s)`;
  const statusLabel = statusOptions.find((option) => option.value === status)?.label ?? "Todos";
  const sortLabel = sortBy === "delivery_date" ? "Entrega" : "Criacao";
  const sortDirLabel = sortDir === "asc" ? "Crescente" : "Decrescente";
  const filterSummary = `${period}d · ${statusLabel} · ${selectedStoresLabel}${customer ? ` · ${customer}` : ""} · ${sortLabel} ${sortDirLabel}`;
  const openCount = summary?.open_count ?? openOrders.length;
  const revenueTodayCents = summary?.revenue_today_cents ?? 0;
  const ordersToday = summary?.orders_today ?? 0;
  const statusCountMap = new Map(statusSummary.map((item) => [item.status, item.count]));
  const statusCountItems = statusOptions.filter((option) => option.value);

  if (!ready) return null;

  const sidebarItems = adminMenuWithHome;

  return (
    <>
      <main className="min-h-screen text-slate-900 bg-[#f5f3ff] overflow-x-hidden">
      <div className="max-w-7xl w-full min-w-0 mx-auto px-3 sm:px-4 lg:px-6 py-6 sm:py-8">
        <div className="grid gap-6 lg:grid-cols-[260px_minmax(0,1fr)] items-start min-w-0">
          <AdminSidebar
            menu={sidebarItems}
            currentPath={pathname}
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

          <div className="space-y-6 min-w-0">
            <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="space-y-1 text-slate-900 sm:min-w-0 sm:flex-1 sm:pr-4">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-600">Admin - Pedidos</p>
                <h1 className="text-2xl sm:text-3xl font-semibold">Gestao de pedidos</h1>
                <p className="text-sm text-slate-600">
                  Filtre por periodo, status e cliente; ajuste status rapidamente.
                </p>
              </div>
              <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap">
                <div className="flex items-center gap-2 flex-nowrap">
                  <button
                    type="button"
                    onClick={() => {
                      const next = !autoRefreshEnabled;
                      setAutoRefreshEnabled(next);
                      if (next && ready) {
                        refreshAll();
                      }
                    }}
                    className={`inline-flex items-center gap-2 px-2 py-1 rounded-full border text-xs ${
                      autoRefreshEnabled
                        ? "bg-emerald-100 border-emerald-200 text-emerald-700"
                        : "bg-slate-100 border-slate-200 text-slate-600"
                    }`}
                    aria-pressed={autoRefreshEnabled}
                    title="Atualizacao automatica"
                  >
                    <svg
                      viewBox="0 0 24 24"
                      className="h-3.5 w-3.5"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.6"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      aria-hidden="true"
                    >
                      <circle cx="12" cy="12" r="9" />
                      <path d="M12 7v5l3 2" />
                    </svg>
                    {autoRefreshEnabled ? "Auto" : "Auto off"}
                  </button>
                  {autoRefreshEnabled && (
                    <select
                      className="h-7 rounded-lg border border-slate-200 bg-slate-50 px-2 text-xs text-slate-900 w-[92px] min-w-[84px]"
                      value={autoRefreshInterval}
                      onChange={(e) => setAutoRefreshInterval(Number(e.target.value))}
                    >
                      {AUTO_REFRESH_OPTIONS.map((value) => (
                        <option key={value} value={value}>
                          {value} min
                        </option>
                      ))}
                    </select>
                  )}
                  <button
                    type="button"
                    onClick={() => {
                      const next = !soundEnabled;
                      setSoundEnabled(next);
                      if (next) primeAudioContext();
                    }}
                    className={`inline-flex items-center gap-2 px-2 py-1 rounded-full border text-xs ${
                      soundEnabled
                        ? "bg-amber-100 border-amber-200 text-amber-700"
                        : "bg-slate-100 border-slate-200 text-slate-600"
                    }`}
                    aria-pressed={soundEnabled}
                    title="Aviso sonoro"
                  >
                    <svg
                      viewBox="0 0 24 24"
                      className="h-3.5 w-3.5"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.6"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      aria-hidden="true"
                    >
                      <path d="M11 5l-5 4H3v6h3l5 4z" />
                      <path d="M15.5 8.5a5 5 0 0 1 0 7" />
                      <path d="M18.5 5.5a9 9 0 0 1 0 13" />
                    </svg>
                    {soundEnabled ? "Som" : "Som off"}
                  </button>
                  <div className="relative">
                    <button
                      type="button"
                      onClick={() => setStoreFilterOpen((open) => !open)}
                      disabled={stores.length <= 1}
                      className="inline-flex items-center gap-2 px-2 py-1 rounded-full border text-xs bg-slate-100 border-slate-200 text-slate-700 disabled:opacity-60 disabled:cursor-not-allowed"
                      title="Filtro de lojas"
                    >
                      <svg
                        viewBox="0 0 24 24"
                        className="h-3.5 w-3.5"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.6"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        aria-hidden="true"
                      >
                        <path d="M3 5h18" />
                        <path d="M6 12h12" />
                        <path d="M10 19h4" />
                      </svg>
                      {selectedStoresLabel}
                    </button>
                    {storeFilterOpen && stores.length > 1 && (
                      <div className="absolute right-0 z-20 mt-1 w-56 max-h-52 overflow-auto rounded-xl border border-slate-200 bg-white shadow-lg p-2 space-y-1">
                        {stores.map((store) => (
                          <label key={store.id} className="flex items-center gap-2 text-xs text-slate-700">
                            <input
                              type="checkbox"
                              checked={selectedStoreIds.includes(store.id)}
                              onChange={() => toggleStoreFilter(store.id)}
                            />
                            <span>{store.name}</span>
                          </label>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
                <ProfileBadge />
              </div>
            </header>

            {error && <p className="text-sm text-amber-700">{error}</p>}
            {summaryError && <p className="text-sm text-amber-700">{summaryError}</p>}
            {openOrdersError && <p className="text-sm text-amber-700">{openOrdersError}</p>}
            {statusSummaryError && <p className="text-sm text-amber-700">{statusSummaryError}</p>}

            <section className={`grid gap-3 ${showRevenueTodayCard ? "sm:grid-cols-3" : "sm:grid-cols-2"}`}>
              <div className="rounded-2xl bg-white border border-slate-200 p-4 text-slate-900">
                <div className="text-xs uppercase tracking-[0.15em] text-slate-500">Pedidos em aberto</div>
                <div className="text-2xl font-semibold">{summaryLoading ? "..." : openCount}</div>
              </div>
              {showRevenueTodayCard && (
                <div className="rounded-2xl bg-white border border-slate-200 p-4 text-slate-900">
                  <div className="text-xs uppercase tracking-[0.15em] text-slate-500">Faturado hoje</div>
                  <div className="text-2xl font-semibold">
                    {summaryLoading ? "..." : formatMoney(revenueTodayCents)}
                  </div>
                </div>
              )}
              <div className="rounded-2xl bg-white border border-slate-200 p-4 text-slate-900">
                <div className="text-xs uppercase tracking-[0.15em] text-slate-500">Pedidos no dia</div>
                <div className="text-2xl font-semibold">{summaryLoading ? "..." : ordersToday}</div>
              </div>
            </section>

            <section className="grid gap-2 sm:grid-cols-4 lg:grid-cols-6">
              {statusCountItems.map((option) => (
                <div
                  key={`status-count-${option.value}`}
                  className="rounded-xl border border-slate-200 bg-white p-3 text-slate-900"
                  style={statusCountCardStyle(option.value)}
                >
                  <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">
                    {option.label}
                  </div>
                  <div className="text-lg font-semibold">
                    {statusSummaryLoading ? "..." : statusCountMap.get(option.value) ?? 0}
                  </div>
                </div>
              ))}
            </section>

            <section className="rounded-2xl bg-white border border-slate-200 p-4 space-y-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="space-y-1">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Pedidos em aberto</p>
                  <h2 className="text-lg font-semibold">Fila ativa</h2>
                  <p className="text-sm text-slate-600">
                    Widget horizontal com os pedidos que ainda nao foram finalizados.
                  </p>
                </div>
                <span className="text-xs text-slate-600">{openOrders.length} pedidos · {selectedStoresLabel}</span>
              </div>
              {openOrdersLoading ? (
                <p className="text-sm text-slate-600">Carregando pedidos em aberto...</p>
              ) : openOrders.length === 0 ? (
                <p className="text-sm text-slate-600">Nenhum pedido em aberto.</p>
              ) : (
                <div className="flex w-full max-w-full min-w-0 flex-nowrap gap-3 overflow-x-auto overscroll-x-contain pb-2">
                  {openOrders.map((order) => (
                    <div
                      key={`open-${order.id}`}
                      className="min-w-[240px] max-w-[280px] rounded-2xl border border-slate-200 bg-white px-4 py-3 text-left shadow-sm hover:shadow-md transition"
                      style={statusCardStyle(order.status)}
                    >
                      <div className="flex items-center justify-between text-[11px] text-slate-500">
                        <span className="font-mono flex items-center gap-1">
                          #{order.id.slice(-6)}
                          {order.notes && order.notes.trim() && (
                            <span title="Pedido com observacoes" className="text-amber-500">
                              <svg
                                viewBox="0 0 20 20"
                                className="h-3.5 w-3.5"
                                fill="currentColor"
                                aria-hidden="true"
                              >
                                <path d="M10 2.2c4.3 0 7.8 3.5 7.8 7.8S14.3 17.8 10 17.8 2.2 14.3 2.2 10 5.7 2.2 10 2.2zm0 4.1a.8.8 0 0 0-.8.8v4.1a.8.8 0 0 0 1.6 0V7.1a.8.8 0 0 0-.8-.8zm0 8.2a.95.95 0 1 0 0-1.9.95.95 0 0 0 0 1.9z" />
                              </svg>
                            </span>
                          )}
                        </span>
                        <button
                          type="button"
                          onClick={() => openPanel(order.id, "view")}
                          className="px-2 py-0.5 rounded-full bg-white/80 border border-slate-200 text-[10px] text-slate-600 hover:bg-white"
                        >
                          Ver pedido
                        </button>
                      </div>
                      <div className="mt-2 text-sm font-semibold text-slate-900">
                        {order.customer_name || "Cliente"}
                      </div>
                      <div className="text-[11px] text-slate-500">{formatDateTime(order.created_at)}</div>
                      <div className="mt-3 flex items-center justify-between gap-2">
                        <select
                          className="h-8 rounded-full border px-2 text-[11px] bg-slate-50 border-slate-200 text-slate-700"
                          value={order.status}
                          onChange={(e) => {
                            const next = e.target.value;
                            if (next) updateStatus(order.id, next);
                          }}
                          style={statusBadgeStyle(order.status)}
                        >
                          {statusOptions.filter((s) => s.value).map((s) => (
                            <option key={s.value} value={s.value}>
                              {s.label}
                            </option>
                          ))}
                        </select>
                        <span className="text-sm font-semibold text-slate-900">
                          {formatMoney(order.total_cents)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="rounded-2xl bg-white border border-slate-200 p-3 sm:p-4 space-y-3 sm:space-y-4">
              <button
                type="button"
                onClick={() => setFilterOpen((open) => !open)}
                className="w-full flex items-center justify-between text-left gap-3"
                aria-expanded={filterOpen}
              >
                <div>
                  <div className="text-xs uppercase tracking-[0.2em] text-slate-500">Filtro</div>
                  <div className="text-sm text-slate-700">{filterSummary}</div>
                </div>
                <span className="px-3 py-1 rounded-full bg-slate-100 border border-slate-200 text-xs text-slate-700">
                  {filterOpen ? "Fechar" : "Editar"}
                </span>
              </button>
                <div
                  className={`${filterOpen ? "grid" : "hidden"} grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-2 sm:gap-3 text-xs sm:text-sm`}
                >
                <label className="space-y-1">
                  <span>Periodo (dias)</span>
                  <select className="input w-full" value={period} onChange={(e) => setPeriod(e.target.value)}>
                    <option value="7">7</option>
                    <option value="15">15</option>
                    <option value="30">30</option>
                    <option value="60">60</option>
                  </select>
                </label>
                <label className="space-y-1">
                  <span>Status</span>
                  <select className="input w-full" value={status} onChange={(e) => setStatus(e.target.value)}>
                    {statusOptions.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="space-y-1">
                  <span>Ordenar por</span>
                  <select className="input w-full" value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
                    <option value="created_at">Data de criacao</option>
                    <option value="delivery_date">Data de entrega</option>
                  </select>
                </label>
                <label className="space-y-1">
                  <span>Direcao</span>
                  <select className="input w-full" value={sortDir} onChange={(e) => setSortDir(e.target.value)}>
                    <option value="desc">Decrescente</option>
                    <option value="asc">Crescente</option>
                  </select>
                </label>
                <label className="space-y-1">
                  <span>Cliente</span>
                  <input className="input w-full" value={customer} onChange={(e) => setCustomer(e.target.value)} />
                </label>
                <label className="space-y-1">
                  <span>Itens por pagina</span>
                  <select className="input w-full" value={pageSize} onChange={(e) => setPageSize(e.target.value)}>
                    <option value="10">10</option>
                    <option value="30">30</option>
                    <option value="50">50</option>
                  </select>
                </label>
                <div className="flex items-end gap-2 sm:justify-end">
                  <button
                    onClick={() => {
                      setPage(1);
                      setStoreFilterOpen(false);
                      refreshAll();
                    }}
                    className="px-3 py-2 rounded-lg bg-[#6320ee] text-white text-xs sm:text-sm active:scale-95 disabled:opacity-50 w-full sm:w-auto"
                    disabled={loading}
                  >
                    Aplicar filtros
                  </button>
                </div>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-600">
                <span>
                  Pagina {page} | Total retornado: {orders.length}
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    className="px-2 py-1 rounded bg-slate-100 border border-slate-200 disabled:opacity-50"
                    disabled={page === 1}
                  >
                    Anterior
                  </button>
                  <button
                    onClick={() => setPage((p) => p + 1)}
                    className="px-2 py-1 rounded bg-slate-100 border border-slate-200"
                  >
                    Proxima
                  </button>
                </div>
              </div>
            </section>

            <section className="rounded-2xl bg-white border border-slate-200 p-3 sm:p-5 space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="font-semibold">Pedidos</h2>
                {loading && <span className="text-xs text-slate-600">Atualizando...</span>}
              </div>
              {orders.length === 0 ? (
                <p className="text-sm text-slate-600">Nenhum pedido encontrado.</p>
              ) : (
                <>
                  <div className="space-y-3 lg:hidden">
                    {orders.map((order) => (
                      <div
                        key={order.id}
                        className="rounded-xl border border-slate-200 bg-slate-50 p-3 space-y-2"
                        style={statusCardStyle(order.status)}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Cliente</p>
                            <p className="text-sm font-semibold text-slate-900 flex items-center gap-1">
                              <span>{order.customer_name || "-"}</span>
                              {order.notes && order.notes.trim() && (
                                <span title="Pedido com observacoes" className="text-amber-500">
                                  <svg
                                    viewBox="0 0 20 20"
                                    className="h-3.5 w-3.5"
                                    fill="currentColor"
                                    aria-hidden="true"
                                  >
                                    <path d="M10 2.2c4.3 0 7.8 3.5 7.8 7.8S14.3 17.8 10 17.8 2.2 14.3 2.2 10 5.7 2.2 10 2.2zm0 4.1a.8.8 0 0 0-.8.8v4.1a.8.8 0 0 0 1.6 0V7.1a.8.8 0 0 0-.8-.8zm0 8.2a.95.95 0 1 0 0-1.9.95.95 0 0 0 0 1.9z" />
                                  </svg>
                                </span>
                              )}
                            </p>
                          </div>
                          <span
                            className="px-2 py-1 rounded-full bg-slate-100 border border-slate-200 text-[10px] capitalize"
                            style={statusBadgeStyle(order.status)}
                          >
                            {order.status ? statusLabelFor(order.status) : "Indefinido"}
                          </span>
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <p className="text-[10px] uppercase tracking-[0.2em] text-slate-400">Data</p>
                            <p className="text-sm text-slate-900">{formatDateTime(order.created_at)}</p>
                          </div>
                          <div>
                            <p className="text-[10px] uppercase tracking-[0.2em] text-slate-400">Valor</p>
                            <p className="text-sm font-semibold text-slate-900">{formatMoney(order.total_cents)}</p>
                          </div>
                        </div>
                        <div className="flex flex-wrap items-center gap-2">
                          <button
                            onClick={() => openPanel(order.id, "view")}
                            className="px-3 py-2 rounded-lg bg-slate-100 border border-slate-200 text-xs hover:bg-slate-200"
                          >
                            Detalhes
                          </button>
                          <button
                            onClick={() => openPanel(order.id, "edit")}
                            className="px-3 py-2 rounded-lg bg-[#6320ee] text-white text-xs hover:brightness-95"
                          >
                            Editar
                          </button>
                          <button
                            onClick={() =>
                              setStatusEditorId((current) => (current === order.id ? null : order.id))
                            }
                            className="px-3 py-2 rounded-lg bg-white border border-slate-200 text-xs hover:bg-slate-100"
                          >
                            Status
                          </button>
                        </div>
                        {statusEditorId === order.id && (
                          <div className="mt-1">
                            <select
                              className="input w-full bg-slate-50 border border-slate-200 text-slate-900 text-xs"
                              value={order.status}
                              onChange={(e) => {
                                const next = e.target.value;
                                if (next) updateStatus(order.id, next);
                                setStatusEditorId(null);
                              }}
                            >
                                  {statusOptions.filter((s) => s.value).map((s) => (
                                    <option key={s.value} value={s.value}>
                                      {s.label}
                                    </option>
                                  ))}
                                </select>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                  <div className="hidden lg:block">
                    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-50">
                      <table className="w-full text-xs sm:text-sm min-w-[900px]">
                        <thead className="bg-slate-100 text-left">
                          <tr>
                            <th className="px-3 sm:px-4 py-2">Pedido</th>
                            <th className="px-3 sm:px-4 py-2">Cliente</th>
                            <th className="px-3 sm:px-4 py-2">Data</th>
                            <th className="px-3 sm:px-4 py-2">Entrega</th>
                            <th className="px-3 sm:px-4 py-2">Loja</th>
                            <th className="px-3 sm:px-4 py-2">Status</th>
                            <th className="px-3 sm:px-4 py-2">Total</th>
                            <th className="px-3 sm:px-4 py-2 text-right">Acoes</th>
                          </tr>
                        </thead>
                        <tbody>
                          {orders.map((order, idx) => (
                            <tr
                              key={order.id}
                              className={idx % 2 === 0 ? "bg-transparent" : "bg-slate-50"}
                              style={statusRowStyle(order.status)}
                            >
                              <td className="px-3 sm:px-4 py-2 font-mono text-xs">
                                <span className="inline-flex items-center gap-1">
                                  {order.id}
                                  {order.notes && order.notes.trim() && (
                                    <span title="Pedido com observacoes" className="text-amber-500">
                                      <svg
                                        viewBox="0 0 20 20"
                                        className="h-3.5 w-3.5"
                                        fill="currentColor"
                                        aria-hidden="true"
                                      >
                                        <path d="M10 2.2c4.3 0 7.8 3.5 7.8 7.8S14.3 17.8 10 17.8 2.2 14.3 2.2 10 5.7 2.2 10 2.2zm0 4.1a.8.8 0 0 0-.8.8v4.1a.8.8 0 0 0 1.6 0V7.1a.8.8 0 0 0-.8-.8zm0 8.2a.95.95 0 1 0 0-1.9.95.95 0 0 0 0 1.9z" />
                                      </svg>
                                    </span>
                                  )}
                                </span>
                              </td>
                              <td className="px-3 sm:px-4 py-2">{order.customer_name}</td>
                              <td className="px-3 sm:px-4 py-2">
                                {formatDateTime(order.created_at)}
                              </td>
                              <td className="px-3 sm:px-4 py-2">{formatDate(order.delivery_date)}</td>
                              <td className="px-3 sm:px-4 py-2">{storeName(order.store_id)}</td>
                              <td className="px-3 sm:px-4 py-2">
                                <span
                                  className="px-2 py-1 rounded-full bg-slate-100 border border-slate-200 text-xs capitalize"
                                  style={statusBadgeStyle(order.status)}
                                >
                                  {order.status ? statusLabelFor(order.status) : "Indefinido"}
                                </span>
                              </td>
                              <td className="px-3 sm:px-4 py-2">
                                {formatMoney(order.total_cents)}
                              </td>
                              <td className="px-3 sm:px-4 py-2">
                                <div className="flex flex-col items-end gap-2">
                                  <div className="flex flex-wrap gap-2 justify-end">
                                    <button
                                      onClick={() => openPanel(order.id, "view")}
                                      className="px-2 py-1 rounded bg-slate-100 border border-slate-200 text-xs hover:bg-slate-200 w-24 justify-center"
                                    >
                                      Visualizar
                                    </button>
                                    <button
                                      onClick={() => openPanel(order.id, "edit")}
                                      className="px-2 py-1 rounded bg-[#6320ee] text-white text-xs hover:brightness-95 w-24 justify-center"
                                    >
                                      Editar
                                    </button>
                                  </div>
                                  <div className="relative flex items-center justify-end">
                                    <button
                                      onClick={() =>
                                        setStatusEditorId((current) => (current === order.id ? null : order.id))
                                      }
                                      className="px-2 py-1 rounded bg-slate-100 border border-slate-200 text-xs hover:bg-slate-200 inline-flex items-center gap-1 w-24 justify-center"
                                      title="Editar status"
                                    >
                                      <svg
                                        viewBox="0 0 20 20"
                                        className="h-3.5 w-3.5"
                                        fill="none"
                                        stroke="currentColor"
                                        strokeWidth="1.6"
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        aria-hidden="true"
                                      >
                                        <path d="M12 4l4 4" />
                                        <path d="M3 17l4.5-1 8-8-3.5-3.5-8 8L3 17z" />
                                      </svg>
                                      Status
                                    </button>
                                    {statusEditorId === order.id && (
                                      <div className="absolute right-0 top-full mt-2 w-44 rounded-xl border border-slate-200 bg-white shadow-lg shadow-slate-200/70 p-2 z-10">
                                        <select
                                          className="input w-full bg-slate-50 border border-slate-200 text-slate-900 text-xs"
                                          value={order.status}
                                          onChange={(e) => {
                                            const next = e.target.value;
                                            if (next) updateStatus(order.id, next);
                                            setStatusEditorId(null);
                                          }}
                                        >
                                          {statusOptions.filter((s) => s.value).map((s) => (
                                            <option key={s.value} value={s.value}>
                                              {s.label}
                                            </option>
                                          ))}
                                        </select>
                                      </div>
                                    )}
                                  </div>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </>
              )}
            </section>
          </div>
        </div>
      </div>
      </main>
      {panelMode && (
      <div className="fixed inset-0 z-50 bg-slate-900/90 backdrop-blur-sm">
        <div className="absolute inset-y-0 right-0 w-full max-w-2xl bg-white text-slate-900 border-l border-slate-200 shadow-2xl shadow-slate-200/80 flex flex-col">
          <div className="flex items-start justify-between p-4 sm:p-6 border-b border-slate-200">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-slate-600">
                {panelMode === "view" ? "Visualizar pedido" : "Editar pedido"}
              </p>
              <h2 className="text-2xl font-semibold">{selectedOrder?.id ?? "Pedido"}</h2>
              {selectedOrder && (
                <p className="text-xs text-slate-600 mt-1">
                  Recebido em {formatDateTime(selectedOrder.created_at)} - Entrega {formatDate(selectedOrder.delivery_date)} - Tipo{" "}
                  {selectedOrder.pickup ? "Retirada" : "Entrega"}
                </p>
              )}
            </div>
            <button
              onClick={closePanel}
              className="text-sm px-3 py-1 rounded-full bg-slate-100 border border-slate-200 hover:bg-slate-200"
            >
              Fechar
            </button>
          </div>

          <div className="flex-1 overflow-auto p-4 sm:p-6 space-y-4">
            {detailLoading && <p className="text-sm text-slate-600">Carregando pedido...</p>}
            {detailError && <p className="text-sm text-amber-700">{detailError}</p>}

            {!detailLoading && selectedOrder && panelMode === "view" && (
              <div className="space-y-4">
                <div className="grid md:grid-cols-2 gap-4 text-sm">
                  <div className="space-y-1">
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Cliente</p>
                    <p className="font-semibold">{selectedOrder.customer_name || "-"}</p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Status</p>
                    <span
                      className="inline-flex px-2 py-1 rounded-full border text-xs capitalize"
                      style={selectedOrder.status ? statusBadgeStyle(selectedOrder.status) : undefined}
                    >
                      {selectedOrder.status ? statusLabelFor(selectedOrder.status) : "-"}
                    </span>
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Tipo de entrega</p>
                    <p className="font-semibold">{selectedOrder.pickup ? "Retirada na loja" : "Entrega em domicilio"}</p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Data de recebimento</p>
                    <p className="font-semibold">{formatDate(selectedOrder.created_at)}</p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Data de entrega</p>
                    <p className="font-semibold">{formatDate(selectedOrder.delivery_date)}</p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Subtotal</p>
                    <p className="font-semibold">{formatMoney(selectedOrder.subtotal_cents)}</p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Total</p>
                    <p className="font-semibold">{formatMoney(selectedOrder.total_cents)}</p>
                  </div>
                </div>

                {!selectedOrder.pickup && (
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <div className="flex items-center justify-between gap-2 mb-3">
                      <h3 className="text-sm font-semibold">Endereco de entrega</h3>
                      <button
                        onClick={() => {
                          const text = buildDeliveryAddress(selectedOrder.delivery);
                          if (!text) return;
                          copyToClipboard(text);
                          setAddressCopied(true);
                          window.setTimeout(() => setAddressCopied(false), 1500);
                        }}
                        className="px-2 py-1 rounded bg-white border border-slate-200 text-xs hover:bg-slate-100"
                      >
                        {addressCopied ? "Copiado" : "Copiar endereco"}
                      </button>
                    </div>
                    <p className="text-sm text-slate-700 whitespace-pre-wrap">
                      {buildDeliveryAddress(selectedOrder.delivery) || "-"}
                    </p>
                  </div>
                )}

                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <h3 className="text-sm font-semibold mb-3">Itens</h3>
                  {selectedOrder.items.length === 0 ? (
                    <p className="text-xs text-slate-600">Nenhum item.</p>
                  ) : (
                    <div className="space-y-2 text-sm">
                      {selectedOrder.items.map((item, idx) => (
                        <div key={`${item.product_id}-${idx}`} className="flex items-center justify-between">
                          <div>
                            <p className="font-medium">{item.name}</p>
                            <p className="text-xs text-slate-600">
                              {item.quantity} x {formatMoney(item.unit_price_cents)}
                            </p>
                          </div>
                          <span className="text-sm font-semibold">
                            {formatMoney(item.quantity * item.unit_price_cents)}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                

                {selectedOrder.notes && selectedOrder.notes.trim() && (
                  <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
                    <h3 className="text-sm font-semibold mb-2 text-amber-900">Observacoes</h3>
                    <p className="text-sm text-amber-900 whitespace-pre-wrap">{selectedOrder.notes}</p>
                  </div>
                )}
</div>

                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="flex items-center justify-between gap-2 mb-3">
                    <h3 className="text-sm font-semibold">WhatsApp</h3>
                    <button
                      onClick={() => loadWhatsappLogs(selectedOrder.id)}
                      className="px-2 py-1 rounded bg-white border border-slate-200 text-xs hover:bg-slate-100"
                    >
                      Atualizar logs
                    </button>
                  </div>
                  {whatsappLoading && <p className="text-xs text-slate-600">Carregando logs...</p>}
                  {whatsappError && <p className="text-xs text-amber-700">{whatsappError}</p>}
                  {!whatsappLoading && !whatsappError && whatsappLogs.length === 0 && (
                    <p className="text-xs text-slate-600">Nenhum disparo registrado.</p>
                  )}
                  {!whatsappLoading && whatsappLogs.length > 0 && (
                    <div className="space-y-2 text-xs">
                      {whatsappLogs.map((log) => (
                        <div
                          key={log.id}
                          className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-white border border-slate-200 px-3 py-2"
                        >
                          <div>
                            <p className="font-semibold text-slate-900">
                              {log.to_phone}
                              {log.provider_message_id ? ` • ${log.provider_message_id}` : ""}
                            </p>
                            <p className="text-[11px] text-slate-500">
                              {formatDateTime(log.created_at)}
                            </p>
                            {log.error_message && (
                              <p className="text-[11px] text-amber-700">{log.error_message}</p>
                            )}
                          </div>
                          <span className="px-2 py-1 rounded-full bg-slate-100 border border-slate-200 text-[10px] uppercase tracking-[0.2em] text-slate-600">
                            {log.status}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {!detailLoading && selectedOrder && panelMode === "edit" && (
              <div className="space-y-4">
                <div className="grid gap-3 text-sm">
                  <label className="space-y-1">
                    <span>Tipo de entrega</span>
                    <input
                      className="input w-full bg-slate-100"
                      value={selectedOrder.pickup ? "Retirada na loja" : "Entrega em domicilio"}
                      readOnly
                    />
                  </label>
                  <label className="space-y-1">
                    <span>Buscar cliente</span>
                    <input
                      className="input w-full"
                      value={editCustomerSearch}
                      onChange={(e) => setEditCustomerSearch(e.target.value)}
                      placeholder="Digite nome ou telefone"
                    />
                  </label>
                  <label className="space-y-1">
                    <span>Cliente selecionado</span>
                    <select
                      className="input w-full"
                      value={editCustomerId}
                      onChange={(e) => setEditCustomerId(e.target.value)}
                    >
                      <option value="">Selecione...</option>
                      {mergedCustomerOptions.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name} {c.phone ? `(${c.phone})` : ""}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-1">
                    <span>Data de recebimento</span>
                    <input
                      type="date"
                      className="input w-full"
                      value={editReceivedDate}
                      onChange={(e) => setEditReceivedDate(e.target.value)}
                    />
                  </label>
                  <label className="space-y-1">
                    <span>Data de entrega</span>
                    <input
                      type="date"
                      className="input w-full"
                      value={editDeliveryDate}
                      onChange={(e) => setEditDeliveryDate(e.target.value)}
                    />
                  </label>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold">Itens</h3>
                    <button
                      onClick={addItem}
                      className="px-2 py-1 rounded bg-slate-100 border border-slate-200 text-xs hover:bg-slate-200"
                      disabled={!catalog.length}
                    >
                      Adicionar item
                    </button>
                  </div>
                  {editItems.length === 0 ? (
                    <p className="text-xs text-slate-600">Nenhum item selecionado.</p>
                  ) : (
                    <div className="space-y-3">
                      {editItems.map((item, idx) => (
                        <div key={`${item.product_id}-${idx}`} className="grid md:grid-cols-[1fr_100px_80px] gap-2">
                          <select
                            className="input w-full"
                            value={item.product_id}
                            onChange={(e) => updateItem(idx, { product_id: e.target.value })}
                          >
                            {catalogOptions.map((product) => (
                              <option key={product.id} value={product.id}>
                                {product.name} - {formatMoney(product.price_cents)}
                              </option>
                            ))}
                          </select>
                          <input
                            type="number"
                            min={1}
                            className="input w-full"
                            value={item.quantity}
                            onChange={(e) => updateItem(idx, { quantity: Number(e.target.value) || 1 })}
                          />
                          <button
                            onClick={() => removeItem(idx)}
                            className="px-2 py-1 rounded bg-slate-100 border border-slate-200 text-xs hover:bg-slate-200"
                          >
                            Remover
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm space-y-2">
                  <div className="flex items-center justify-between">
                    <span>Subtotal</span>
                    <span className="font-semibold">{formatMoney(subtotalCents)}</span>
                  </div>
                  <div className="flex items-center justify-between text-slate-600">
                    <span>Frete atual</span>
                    <span>{formatMoney(shippingCents)}</span>
                  </div>
                  <div className="flex items-center justify-between text-slate-600">
                    <span>Desconto atual</span>
                    <span>{formatMoney(discountCents)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Total estimado</span>
                    <span className="font-semibold">{formatMoney(estimatedTotalCents)}</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {panelMode === "edit" && (
            <div className="p-6 border-t border-slate-200 flex items-center justify-end gap-3">
              <button
                onClick={closePanel}
                className="px-4 py-2 rounded-lg bg-slate-100 text-slate-900 text-sm font-semibold active:scale-95"
              >
                Cancelar
              </button>
              <button
                onClick={saveEdit}
                disabled={saving}
                className="px-4 py-2 rounded-lg bg-[#6320ee] text-white text-sm font-semibold active:scale-95 disabled:opacity-60"
              >
                Salvar
              </button>
            </div>
          )}
        </div>
      </div>
      )}
    </>
  );
}



