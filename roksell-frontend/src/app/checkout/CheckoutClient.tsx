"use client";
import { useCart } from "@/store/cart";
import { fmtBRL } from "@/lib/api";
import { viaCEP } from "@/lib/cep";
import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { adminFetch } from "@/lib/admin-api";
import UserLoginButton from "@/components/UserLoginButton";
import { OperatingHoursDay, PaymentMethod, Store } from "@/types";

type CheckoutItem = {
  product_id: string;
  quantity: number;
  custom_name?: string;
  custom_description?: string;
  custom_weight?: string;
  custom_price_cents?: number;
  additional_ids?: string[];
  item_notes?: string;
};

type AddressPayload = {
  postal_code: string;
  street: string;
  number: string;
  complement?: string;
  district?: string;
  city: string;
  state: string;
  reference?: string;
};

type PagamentoMetodo = PaymentMethod;

type CheckoutPayload = {
  phone: string;
  name: string;
  pickup: boolean;
  preorder_confirmed?: boolean;
  address?: AddressPayload;
  items: CheckoutItem[];
  payment: { method: PagamentoMetodo };
  delivery_window_start: string;
  delivery_window_end: string;
  delivery_date: string;
  notes?: string;
  shipping_cents?: number;
  coupon_code?: string;
  store_id: string;
};

type CheckoutPreview = {
  subtotal_cents: number;
  shipping_cents: number;
  discount_cents: number;
  total_cents: number;
  campaign?: { id: string; name: string; value_percent: number } | null;
};

type PedidoResumo = {
  order_id: string;
  total_cents: number;
  tracking_token?: string;
};

type FormState = {
  telefone: string;
  name: string;
  cep: string;
  logradouro: string;
  numero: string;
  complemento: string;
  bairro: string;
  cidade: string;
  uf: string;
  referencia: string;
  notas: string;
  delivery_date: string;
};

type Customer = {
  id: string;
  name: string;
  phone: string;
};

type StockAlertItem = {
  productName: string;
  available?: number;
  requested?: number;
};

function normalizeStoreKey(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "");
}

function shippingErrorFromReason(reason?: string | null): string {
  switch (reason) {
    case "out_of_area":
      return "Entrega fora da area atendida.";
    case "distance_fail":
      return "Nao foi possivel calcular a distancia. Confira numero/endereco e configuracao da loja.";
    case "method_not_supported":
      return "Metodo de frete nao habilitado.";
    default:
      return "Frete indisponivel.";
  }
}

const DEFAULT_STORE_TIMEZONE = "America/Sao_Paulo";

function resolveStoreTimezone(value?: string | null): string {
  return (value || "").trim() || DEFAULT_STORE_TIMEZONE;
}

function nowPartsInTimezone(timeZone: string): { isoDate: string; weekday: number; minutes: number } {
  const now = new Date();
  try {
    const dateParts = new Intl.DateTimeFormat("en-CA", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).formatToParts(now);
    const year = dateParts.find((part) => part.type === "year")?.value ?? "1970";
    const month = dateParts.find((part) => part.type === "month")?.value ?? "01";
    const day = dateParts.find((part) => part.type === "day")?.value ?? "01";

    const weekdayLabel = new Intl.DateTimeFormat("en-US", { timeZone, weekday: "short" }).format(now);
    const weekdayMap: Record<string, number> = {
      Mon: 0,
      Tue: 1,
      Wed: 2,
      Thu: 3,
      Fri: 4,
      Sat: 5,
      Sun: 6,
    };
    const weekday = weekdayMap[weekdayLabel] ?? 0;

    const timeParts = new Intl.DateTimeFormat("en-GB", {
      timeZone,
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).formatToParts(now);
    const hour = Number(timeParts.find((part) => part.type === "hour")?.value ?? "0");
    const minute = Number(timeParts.find((part) => part.type === "minute")?.value ?? "0");
    const minutes = hour * 60 + minute;

    return { isoDate: `${year}-${month}-${day}`, weekday, minutes };
  } catch {
    const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
    return {
      isoDate: local.toISOString().slice(0, 10),
      weekday: (now.getDay() + 6) % 7,
      minutes: now.getHours() * 60 + now.getMinutes(),
    };
  }
}

function todayIsoDate(timeZone = DEFAULT_STORE_TIMEZONE): string {
  return nowPartsInTimezone(timeZone).isoDate;
}

function isDateAllowedByCalendar(date: string, calendarDates: string[]): boolean {
  if (!date) return false;
  if (calendarDates.length === 0) return true;
  return calendarDates.includes(date);
}

function weekdayFromIso(date: string): number {
  const base = new Date(`${date}T00:00:00`);
  const jsDay = base.getDay(); // Sunday=0
  return (jsDay + 6) % 7; // Monday=0
}

function isDateAllowedByHours(date: string, hours: OperatingHoursDay[]): boolean {
  if (!date) return false;
  if (!hours || hours.length === 0) return true;
  const weekday = weekdayFromIso(date);
  const entry = hours.find((item) => item.day === weekday);
  return Boolean(entry?.enabled);
}

function isDateAllowed(date: string, calendarDates: string[], hours: OperatingHoursDay[]): boolean {
  if (!isDateAllowedByCalendar(date, calendarDates)) return false;
  if (!isDateAllowedByHours(date, hours)) return false;
  return true;
}

function nextOpenDate(date: string, calendarDates: string[], hours: OperatingHoursDay[]): string | null {
  function toIsoDate(value: Date): string {
    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, "0");
    const day = String(value.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }
  const base = new Date(`${date}T00:00:00`);
  for (let i = 0; i <= 90; i += 1) {
    const candidate = new Date(base);
    candidate.setDate(base.getDate() + i);
    const iso = toIsoDate(candidate);
    if (isDateAllowed(iso, calendarDates, hours)) {
      return iso;
    }
  }
  return null;
}

function isStoreOpenNow(
  calendarDates: string[],
  hours: OperatingHoursDay[],
  timeZone = DEFAULT_STORE_TIMEZONE
): boolean {
  const now = nowPartsInTimezone(timeZone);
  const today = now.isoDate;
  if (!isDateAllowedByCalendar(today, calendarDates)) return false;
  if (!hours || hours.length === 0) return true;
  const entry = hours.find((item) => item.day === now.weekday);
  if (!entry || !entry.enabled || !entry.open || !entry.close) return false;
  const [openHour, openMinute] = entry.open.split(":").map((value) => Number(value));
  const [closeHour, closeMinute] = entry.close.split(":").map((value) => Number(value));
  if (!Number.isFinite(openHour) || !Number.isFinite(closeHour)) return false;
  const openMinutes = openHour * 60 + (openMinute || 0);
  const closeMinutes = closeHour * 60 + (closeMinute || 0);
  return openMinutes <= now.minutes && now.minutes < closeMinutes;
}

function formatOpenDateLabel(dateIso: string | null): string {
  if (!dateIso) return "data indisponivel";
  const parsed = new Date(`${dateIso}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return dateIso;
  return new Intl.DateTimeFormat("pt-BR", {
    weekday: "long",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  })
    .format(parsed)
    .replace(",", "");
}

function formatPostalCode(value?: string | null): string {
  const digits = String(value || "").replace(/\D/g, "");
  if (digits.length !== 8) return String(value || "").trim();
  return `${digits.slice(0, 5)}-${digits.slice(5)}`;
}

function buildPickupAddress(store: Store | null): string {
  if (!store) return "";
  const part1 = [store.street || "", store.number || ""].filter(Boolean).join(", ");
  const part2 = [store.district || "", [store.city || "", store.state || ""].filter(Boolean).join("/")].filter(Boolean).join(" - ");
  const postal = formatPostalCode(store.postal_code);
  const parts = [part1, part2, postal ? `CEP ${postal}` : ""].filter(Boolean);
  return parts.join(" | ");
}

export default function CheckoutClient() {
  const { items, clear } = useCart();
  const [retirada, setRetirada] = useState<boolean | null>(null);
  const [form, setForm] = useState<FormState>({
    telefone: "",
    name: "",
    cep: "",
    logradouro: "",
    numero: "",
    complemento: "",
    bairro: "",
    cidade: "",
    uf: "",
    referencia: "",
    notas: "",
    delivery_date: todayIsoDate(),
  });
  const [method, setMethod] = useState<PagamentoMetodo | null>(null);
  const [cashNeedsChange, setCashNeedsChange] = useState<boolean | null>(null);
  const [cashChangeFor, setCashChangeFor] = useState("");
  const [loading, setLoading] = useState<boolean>(false);
  const [availableMethods, setAvailableMethods] = useState<PagamentoMetodo[]>([]);
  const [paymentMethodsError, setPaymentMethodsError] = useState<string | null>(null);
  const [previewShippingCents, setPreviewShippingCents] = useState<number | null>(null);

  // frete
  const [freteCentavos, setFreteCentavos] = useState<number | null>(0);
  const [loadingFrete, setLoadingFrete] = useState<boolean>(false);
  const [erroFrete, setErroFrete] = useState<string | null>(null);

  // vendedor / busca cliente
  const [vendorError, setVendorError] = useState<string | null>(null);
  const [vendorLogged, setVendorLogged] = useState(false);

  // lojas
  const [stores, setStores] = useState<Store[]>([]);
  const [storesError, setStoresError] = useState<string | null>(null);
  const [storesLoading, setStoresLoading] = useState(false);

  const [showCustomerModal, setShowCustomerModal] = useState(false);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customersLoading, setCustomersLoading] = useState(false);
  const [customerQuery, setCustomerQuery] = useState("");
  const [coupon, setCoupon] = useState("");
  const [stockAlertItems, setStockAlertItems] = useState<StockAlertItem[] | null>(null);
  const [pickupAddressCopied, setPickupAddressCopied] = useState(false);
  const [showPreorderAlert, setShowPreorderAlert] = useState(false);
  const [preorderDateLabel, setPreorderDateLabel] = useState("data indisponivel");
  const [couponStatus, setCouponStatus] = useState<{
    loading: boolean;
    error: string | null;
    discount_cents: number;
    campaign_name?: string | null;
  }>({ loading: false, error: null, discount_cents: 0, campaign_name: null });
  const [submitAttempted, setSubmitAttempted] = useState(false);

  const router = useRouter();
  const searchParams = useSearchParams();
  const tenant = searchParams.get("tenant") || "";
  const storeParam = (searchParams.get("store") || searchParams.get("store_id") || "").trim();
  const tenantParam = tenant ? `?tenant=${encodeURIComponent(tenant)}` : "";
  const telefoneValido = form.telefone.trim().length > 0;
  const nameValido = form.name.trim().length > 0;
  const storeIdFromParam = useMemo(() => {
    if (!storeParam) return "";
    const exact = stores.find((store) => store.id === storeParam);
    if (exact) return exact.id;
    const bySlug = stores.find((store) => store.slug === storeParam);
    if (bySlug) return bySlug.id;
    const normalizedQuery = normalizeStoreKey(storeParam);
    if (!normalizedQuery) return "";
    const byName = stores.find((store) => normalizeStoreKey(store.name) === normalizedQuery);
    return byName?.id || "";
  }, [stores, storeParam]);

  const selectedStore = useMemo(
    () => stores.find((store) => store.id === storeIdFromParam) || null,
    [stores, storeIdFromParam]
  );
  const storeTimezone = useMemo(
    () => resolveStoreTimezone(selectedStore?.timezone),
    [selectedStore?.timezone]
  );
  const minDeliveryDate = useMemo(() => todayIsoDate(storeTimezone), [storeTimezone]);
  const vitrineBackUrl = useMemo(() => {
    if (!tenant) return "/";
    const storeRef = (storeParam || selectedStore?.slug || storeIdFromParam || "").trim();
    if (!storeRef) return `/vitrine/${tenant}`;
    return `/vitrine/${tenant}/${encodeURIComponent(storeRef)}`;
  }, [tenant, storeParam, selectedStore?.slug, storeIdFromParam]);
  const pickupAddress = useMemo(() => buildPickupAddress(selectedStore), [selectedStore]);
  const calendarDates = useMemo(
    () => (selectedStore?.closed_dates || []).filter(Boolean).sort(),
    [selectedStore]
  );
  const operatingHours = useMemo(
    () => (selectedStore?.operating_hours || []).filter(Boolean),
    [selectedStore]
  );
  const storeAllowsPreorderWhenClosed = selectedStore?.allow_preorder_when_closed !== false;
  const nextOpenDateLabel = useMemo(() => {
    const nextDate = nextOpenDate(todayIsoDate(storeTimezone), calendarDates, operatingHours);
    return formatOpenDateLabel(nextDate);
  }, [calendarDates, operatingHours, storeTimezone]);
  const pickupOptionEnabled = useMemo(() => {
    if (!selectedStore) return false;
    const storeWithPickup = selectedStore as Store & { is_pickup?: boolean };
    return storeWithPickup.is_pickup ?? true;
  }, [selectedStore]);
  const deliveryOptionEnabled = Boolean(selectedStore?.is_delivery);
  const hasFulfillmentSelection = retirada !== null;
  const isPickup = retirada === true;
  const isDelivery = retirada === false;
  const deliveryDateOpen = useMemo(
    () => isDateAllowed(form.delivery_date, calendarDates, operatingHours),
    [form.delivery_date, calendarDates, operatingHours]
  );
  const showValidation = submitAttempted;
  const missingStore = !storeIdFromParam || !selectedStore;
  const missingFulfillment = !hasFulfillmentSelection;
  const missingPayment = method === null;
  const missingCashChangeFor =
    method === "cash" && cashNeedsChange === true && cashChangeFor.trim().length === 0;
  const missingPhone = !telefoneValido;
  const missingName = !nameValido;
  const missingDeliveryDate = !form.delivery_date || form.delivery_date < minDeliveryDate;
  const deliveryDateUnavailable = !deliveryDateOpen;
  const isCEPValido = useMemo(
    () => /^\d{5}-?\d{3}$/.test(form.cep ?? ""),
    [form.cep]
  );
  const missingCep = isDelivery && form.cep.trim().length === 0;
  const invalidCep = isDelivery && form.cep.trim().length > 0 && !isCEPValido;
  const missingStreet = isDelivery && form.logradouro.trim().length === 0;
  const missingNumber = isDelivery && form.numero.trim().length === 0;
  const missingDistrict = isDelivery && form.bairro.trim().length === 0;
  const missingCity = isDelivery && form.cidade.trim().length === 0;
  const missingState = isDelivery && form.uf.trim().length === 0;
  const shippingInvalid = isDelivery && (freteCentavos === null || loadingFrete || !!erroFrete);
  const hasValidationErrors =
    missingStore ||
    missingFulfillment ||
    missingPayment ||
    missingCashChangeFor ||
    missingPhone ||
    missingName ||
    missingDeliveryDate ||
    deliveryDateUnavailable ||
    missingCep ||
    invalidCep ||
    missingStreet ||
    missingNumber ||
    missingDistrict ||
    missingCity ||
    missingState ||
    shippingInvalid;

  async function copyPickupAddress() {
    if (!pickupAddress) return;
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(pickupAddress);
      } else if (typeof document !== "undefined") {
        const textarea = document.createElement("textarea");
        textarea.value = pickupAddress;
        textarea.setAttribute("readonly", "true");
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
      }
      setPickupAddressCopied(true);
      window.setTimeout(() => setPickupAddressCopied(false), 1200);
    } catch {
      setPickupAddressCopied(false);
    }
  }

  function inputClass(invalid: boolean) {
    return `input ${invalid ? "border-red-400 ring-1 ring-red-200 focus:border-red-500 focus:ring-red-200" : ""}`;
  }

  useEffect(() => {
    refreshVendorInfo();
    loadStores();
    loadPaymentMethods();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const today = todayIsoDate(storeTimezone);
    if (form.delivery_date < today || !deliveryDateOpen) {
      const baseDate = form.delivery_date < today ? today : form.delivery_date;
      const adjustedDate = nextOpenDate(baseDate, calendarDates, operatingHours);
      if (adjustedDate && adjustedDate !== form.delivery_date) {
        setForm((prev) => ({ ...prev, delivery_date: adjustedDate }));
      }
    }
  }, [deliveryDateOpen, form.delivery_date, calendarDates, operatingHours, storeTimezone]);

  useEffect(() => {
    if (retirada === true && !pickupOptionEnabled) {
      setRetirada(null);
      return;
    }
    if (retirada === false && !deliveryOptionEnabled) {
      setRetirada(null);
    }
  }, [retirada, pickupOptionEnabled, deliveryOptionEnabled]);

  useEffect(() => {
    if (method && !availableMethods.includes(method)) {
      setMethod(null);
    }
  }, [method, availableMethods]);

  useEffect(() => {
    if (method !== "cash") {
      setCashNeedsChange(null);
      setCashChangeFor("");
    }
  }, [method]);

  useEffect(() => {
    setPreorderDateLabel(nextOpenDateLabel);
  }, [nextOpenDateLabel]);

  useEffect(() => {
    setPickupAddressCopied(false);
  }, [pickupAddress, isPickup]);

  const enderecoEntregaCompleto = useMemo(() => {
    if (!isDelivery) return true;
    return (
      form.logradouro.trim().length > 0 &&
      form.numero.trim().length > 0 &&
      form.bairro.trim().length > 0 &&
      form.cidade.trim().length > 0 &&
      form.uf.trim().length > 0
    );
  }, [isDelivery, form.logradouro, form.numero, form.bairro, form.cidade, form.uf]);

  async function onCEPBlur() {
    if (!isCEPValido) return;
    const r = await viaCEP(form.cep);
    if (r) setForm((v) => ({ ...v, ...r }));
  }

  async function refreshVendorInfo() {
    try {
      const res = await fetch("/api/auth/me", { method: "GET", credentials: "include" });
      if (res.ok) {
        await res.json();
        setVendorLogged(true);
        return;
      }
    } catch {
      /* ignore */
    }
    setVendorLogged(false);
  }

  async function loadStores() {
    try {
      setStoresLoading(true);
      setStoresError(null);
      const res = await fetch(`/api/stores${tenantParam}`, { cache: "no-store" });
      if (!res.ok) {
        const txt = await res.text();
        throw new Error(txt || `Falha ao carregar lojas (${res.status})`);
      }
      const data: Store[] = await res.json();
      setStores(data);
    } catch (e) {
      setStoresError(e instanceof Error ? e.message : "Falha ao carregar lojas");
    } finally {
      setStoresLoading(false);
    }
  }

  async function loadPaymentMethods() {
    try {
      setPaymentMethodsError(null);
      const res = await fetch(`/api/catalog${tenantParam}`, { cache: "no-store" });
      if (!res.ok) {
        const txt = await res.text();
        throw new Error(txt || `Falha ao carregar pagamentos (${res.status})`);
      }
      const data: { payment_methods?: string[] } = await res.json();
      const methods = Array.isArray(data.payment_methods) ? data.payment_methods : [];
      const normalized = methods.filter(
        (value): value is PagamentoMetodo => value === "pix" || value === "cash"
      );
      const resolved: PagamentoMetodo[] =
        normalized.length > 0 ? normalized : (["pix", "cash"] satisfies PagamentoMetodo[]);
      setForm((prev) => {
        const today = todayIsoDate(storeTimezone);
        const baseDate = prev.delivery_date >= today ? prev.delivery_date : today;
        const adjustedDate = nextOpenDate(baseDate, calendarDates, operatingHours) ?? today;
        if (adjustedDate === prev.delivery_date) return prev;
        return { ...prev, delivery_date: adjustedDate };
      });
      setAvailableMethods(resolved);
    } catch (e) {
      setPaymentMethodsError(e instanceof Error ? e.message : "Falha ao carregar pagamentos");
    }
  }

  // recalcula frete quando muda retirada/CEP/itens
  useEffect(() => {
    async function calculaFrete() {
      if (!isDelivery) {
        setFreteCentavos(0);
        setErroFrete(null);
        setPreviewShippingCents(null);
        return;
      }
      if (!isCEPValido) {
        setFreteCentavos(null);
        setErroFrete(null);
        setPreviewShippingCents(null);
        return;
      }
      if (!enderecoEntregaCompleto) {
        setFreteCentavos(null);
        setErroFrete("Preencha o endereco completo para calcular o frete.");
        setPreviewShippingCents(null);
        return;
      }
      if (items.length === 0) {
        setFreteCentavos(null);
        setErroFrete(null);
        setPreviewShippingCents(null);
        return;
      }
      const store = selectedStore;
      if (!store) {
        setFreteCentavos(null);
        setErroFrete("Loja de atendimento nao encontrada na URL.");
        setPreviewShippingCents(null);
        return;
      }
      if (!store.is_delivery) {
        setFreteCentavos(null);
        setErroFrete("Loja selecionada nao faz entregas");
        setPreviewShippingCents(null);
        return;
      }

      try {
        setLoadingFrete(true);
        setErroFrete(null);
        const resp = await fetch(`/api/shipping${tenantParam}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            postal_code: form.cep.replace(/\D/g, ""),
            pickup: false,
            items: items.map((i) => ({
              product_id: String(i.productId),
              quantity: i.quantity,
            })),
            store_id: store.id,
            address: {
              street: form.logradouro,
              number: form.numero,
              district: form.bairro,
              city: form.cidade,
              state: form.uf,
              postal_code: form.cep,
              complement: form.complemento,
            },
          }),
        });

        if (!resp.ok) {
          const t = await resp.text();
          throw new Error(t || `Falha ao calcular frete (${resp.status})`);
        }

        const data: {
          amount_cents?: number | null;
          undefined?: boolean;
          reason?: string | null;
        } = await resp.json();
        if (data.undefined || data.amount_cents == null) {
          setFreteCentavos(null);
          setErroFrete(shippingErrorFromReason(data.reason));
          setPreviewShippingCents(null);
          return;
        }
        setFreteCentavos(Number(data.amount_cents) || 0);
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        setErroFrete(msg);
        setFreteCentavos(null);
        setPreviewShippingCents(null);
      } finally {
        setLoadingFrete(false);
      }
    }

    calculaFrete();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isDelivery, isCEPValido, enderecoEntregaCompleto, form.cep, items, selectedStore]);

  const effectiveShippingCents = useMemo(
    () => (isDelivery ? previewShippingCents ?? freteCentavos ?? 0 : 0),
    [isDelivery, previewShippingCents, freteCentavos],
  );
  const displayFreteCentavos = isDelivery ? previewShippingCents ?? freteCentavos : 0;
  const subtotalCents = useMemo(
    () => items.reduce((sum, item) => sum + item.price * item.quantity, 0),
    [items],
  );
  const totalCentavos = useMemo(() => {
    const discount = couponStatus.discount_cents || 0;
    return subtotalCents + effectiveShippingCents - discount;
  }, [subtotalCents, effectiveShippingCents, couponStatus.discount_cents]);

  useEffect(() => {
    // Se a loja mudar (mudanca de URL), exige nova selecao de forma de entrega.
    setRetirada(null);
  }, [storeIdFromParam]);

  useEffect(() => {
    // Reset discount when coupon cleared
    if (coupon.trim() === "") {
      setCouponStatus({ loading: false, error: null, discount_cents: 0, campaign_name: null });
      setPreviewShippingCents(null);
    }
  }, [coupon]);

  useEffect(() => {
    // Revalida cupom quando itens ou frete mudam
    const handle = setTimeout(() => {
      const trimmed = coupon.trim();
      if (trimmed) {
        validateCoupon();
      } else if (
        items.length > 0 &&
        storeIdFromParam &&
        hasFulfillmentSelection &&
        (isPickup || freteCentavos !== null) &&
        !erroFrete
      ) {
        runPreview({ couponCode: null, silent: true });
      }
    }, 400);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, freteCentavos, hasFulfillmentSelection, isPickup, storeIdFromParam, erroFrete]);

  async function openCustomerModal() {
    if (!vendorLogged) return;
    setShowCustomerModal(true);
    if (customers.length > 0) return;
    try {
      setCustomersLoading(true);
      const data = await adminFetch<Customer[]>("/admin/customers?limit=100");
      setCustomers(data);
    } catch (e) {
      setVendorError(e instanceof Error ? e.message : "Falha ao carregar clientes");
    } finally {
      setCustomersLoading(false);
    }
  }

  const filteredCustomers = customers.filter((c) =>
    c.name.toLowerCase().includes(customerQuery.toLowerCase()),
  );

  function selectCustomer(c: Customer) {
    setForm((prev) => ({ ...prev, name: c.name, telefone: c.phone || prev.telefone }));
    setShowCustomerModal(false);
  }

  function parseStockAlert(detail: unknown): StockAlertItem[] | null {
    if (detail && typeof detail === "object") {
      const payload = detail as {
        code?: string;
        message?: string;
        product_name?: string;
        productName?: string;
        available?: number;
        requested?: number;
        items?: Array<{
          product_name?: string;
          productName?: string;
          available?: number;
          requested?: number;
        }>;
      };
      if (payload.code === "INSUFFICIENT_STOCK") {
        if (Array.isArray(payload.items) && payload.items.length > 0) {
          return payload.items.map((item) => ({
            productName: item.product_name || item.productName || "Produto",
            available: typeof item.available === "number" ? item.available : undefined,
            requested: typeof item.requested === "number" ? item.requested : undefined,
          }));
        }
        const name = payload.product_name || payload.productName || payload.message || "Produto";
        return [
          {
            productName: name,
            available: typeof payload.available === "number" ? payload.available : undefined,
            requested: typeof payload.requested === "number" ? payload.requested : undefined,
          },
        ];
      }
    }
    if (typeof detail === "string") {
      const match = detail.match(/Estoque insuficiente para (.+)$/i);
      if (match?.[1]) {
        return [{ productName: match[1].trim() }];
      }
    }
    return null;
  }

  function parsePreorderConfirm(detail: unknown): { next_open_date?: string | null } | null {
    if (!detail || typeof detail !== "object") return null;
    const payload = detail as {
      code?: string;
      next_open_date?: string | null;
    };
    if (payload.code !== "PREORDER_CONFIRM_REQUIRED") return null;
    return { next_open_date: payload.next_open_date };
  }

  async function submit(preorderConfirmed = false) {
    if (items.length === 0) return;
    setSubmitAttempted(true);
    if (hasValidationErrors) {
      return;
    }
    const store = selectedStore;
    if (!store) {
      alert("Loja de atendimento nao encontrada na URL.");
      return;
    }
    if (retirada === null) {
      alert("Selecione a forma de entrega.");
      return;
    }
    if (!pickupOptionEnabled && !deliveryOptionEnabled) {
      alert("Esta loja nao possui forma de atendimento disponivel.");
      return;
    }
    if (isDelivery && !store.is_delivery) {
      alert("A loja selecionada nao faz entregas.");
      return;
    }
    const openNowAtSubmit = isStoreOpenNow(calendarDates, operatingHours, storeTimezone);
    const nextOpenAtSubmit = nextOpenDate(todayIsoDate(storeTimezone), calendarDates, operatingHours);
    const nextOpenLabelAtSubmit = formatOpenDateLabel(nextOpenAtSubmit);
    if (!openNowAtSubmit && !storeAllowsPreorderWhenClosed) {
      alert("A loja esta fechada no momento e nao aceita encomendas.");
      return;
    }
    if (!openNowAtSubmit && storeAllowsPreorderWhenClosed && !preorderConfirmed) {
      setPreorderDateLabel(nextOpenLabelAtSubmit);
      setShowPreorderAlert(true);
      return;
    }
    if (!method || !availableMethods.includes(method)) {
      alert("Selecione uma forma de pagamento valida.");
      return;
    }
    // exige frete quando entrega
    if (isDelivery && (freteCentavos === null || loadingFrete || erroFrete)) return;

    setLoading(true);
    try {
      const agora = new Date().toISOString();
      const daquiUmaHora = new Date(Date.now() + 60 * 60 * 1000).toISOString();

      const payload: CheckoutPayload = {
        phone: form.telefone,
        name: form.name,
        pickup: isPickup,
        preorder_confirmed: preorderConfirmed || undefined,
        items: items.map((i) => ({
          product_id: String(i.productId),
          quantity: i.quantity,
          custom_name: i.isCustom ? i.custom?.name : undefined,
          custom_description: i.isCustom ? i.custom?.description : undefined,
          custom_weight: i.isCustom ? i.custom?.weight : undefined,
          custom_price_cents: i.isCustom ? i.price : undefined,
          additional_ids: i.additionals?.map((item) => item.id) ?? [],
          item_notes: i.itemNotes || undefined,
        })),
        payment: { method },
        delivery_window_start: agora,
        delivery_window_end: daquiUmaHora,
        delivery_date: form.delivery_date,
        notes: (() => {
          const notesParts: string[] = [];
          const baseNotes = form.notas.trim();
          if (baseNotes) notesParts.push(baseNotes);
          if (method === "cash" && cashNeedsChange === true && cashChangeFor.trim()) {
            notesParts.push(`Troco para: ${cashChangeFor.trim()}`);
          }
          return notesParts.length > 0 ? notesParts.join(" | ") : undefined;
        })(),
        shipping_cents: isPickup ? 0 : (freteCentavos ?? 0),
        coupon_code: coupon.trim() || undefined,
        store_id: store.id,
      };

      if (isDelivery) {
        payload.address = {
          postal_code: form.cep,
          street: form.logradouro,
          number: form.numero,
          complement: form.complemento || undefined,
          district: form.bairro || undefined,
          city: form.cidade,
          state: form.uf,
          reference: form.referencia || undefined,
        };
      }

      const resp = await fetch(`/api/checkout${tenantParam}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!resp.ok) {
        const raw = await resp.text();
        let detail: unknown = raw;
        try {
          const parsed = JSON.parse(raw);
          if (parsed && typeof parsed === "object" && "detail" in parsed) {
            detail = (parsed as { detail?: unknown }).detail;
          }
        } catch {
          /* ignore */
        }
        const stockItems = parseStockAlert(detail);
        if (stockItems) {
          setStockAlertItems(stockItems);
          return;
        }
        const preorderConfirm = parsePreorderConfirm(detail);
        if (preorderConfirm) {
          setPreorderDateLabel(formatOpenDateLabel(preorderConfirm.next_open_date ?? null));
          setShowPreorderAlert(true);
          return;
        }
        const msg =
          typeof detail === "string" && detail.trim().length > 0 ? detail : raw || `Falha (${resp.status})`;
        throw new Error(msg);
      }

      const res: PedidoResumo = await resp.json();
      setShowPreorderAlert(false);
      clear();
      const params = new URLSearchParams();
      if (tenant) params.set("tenant", tenant);
      const storeBackRef = (storeParam || store.slug || store.id || "").trim();
      if (storeBackRef) params.set("store", storeBackRef);
      if (res.tracking_token) params.set("token", res.tracking_token);
      const suffix = params.toString();
      router.push(`/pedido/${res.order_id}${suffix ? `?${suffix}` : ""}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      console.error("[checkout] erro =>", msg);
      alert(msg);
    } finally {
      setLoading(false);
    }
  }

  async function runPreview({ couponCode, silent }: { couponCode: string | null; silent: boolean }) {
    if (items.length === 0) {
      if (!silent) {
        setCouponStatus({
          loading: false,
          error: "Adicione itens antes de aplicar cupom.",
          discount_cents: 0,
          campaign_name: null,
        });
      }
      return;
    }
    if (!storeIdFromParam) {
      if (!silent) {
        setCouponStatus({
          loading: false,
          error: "Loja de atendimento nao encontrada na URL.",
          discount_cents: 0,
          campaign_name: null,
        });
      }
      return;
    }
    if (!hasFulfillmentSelection) {
      if (!silent) {
        setCouponStatus({
          loading: false,
          error: "Selecione a forma de entrega antes de aplicar o cupom.",
          discount_cents: 0,
          campaign_name: null,
        });
      }
      return;
    }
    if (isDelivery && (freteCentavos === null || !!erroFrete)) {
      if (!silent) {
        setCouponStatus({
          loading: false,
          error: "Calcule o frete primeiro para aplicar cupom em entrega.",
          discount_cents: 0,
          campaign_name: null,
        });
      }
      return;
    }

    try {
      if (!silent) {
        setCouponStatus((s) => ({ ...s, loading: true, error: null }));
      }
      const body = {
        items: items.map((i) => ({
          product_id: String(i.productId),
          quantity: i.quantity,
          custom_name: i.isCustom ? i.custom?.name : undefined,
          custom_description: i.isCustom ? i.custom?.description : undefined,
          custom_weight: i.isCustom ? i.custom?.weight : undefined,
          custom_price_cents: i.isCustom ? i.price : undefined,
          additional_ids: i.additionals?.map((item) => item.id) ?? [],
          item_notes: i.itemNotes || undefined,
        })),
        pickup: isPickup,
        shipping_cents: isPickup ? 0 : (freteCentavos ?? 0),
        coupon_code: couponCode,
        store_id: storeIdFromParam,
      };
      const res = await fetch(`/api/checkout/preview${tenantParam}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t || "Cupom invalido");
      }
      const data: CheckoutPreview = await res.json();
      if (typeof data.shipping_cents === "number") {
        setPreviewShippingCents(data.shipping_cents);
      }
      setCouponStatus({
        loading: false,
        error: null,
        discount_cents: data.discount_cents,
        campaign_name: data.campaign?.name || null,
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      if (!silent) {
        setCouponStatus({ loading: false, error: msg, discount_cents: 0, campaign_name: null });
      }
    }
  }

  async function validateCoupon() {
    const code = coupon.trim();
    if (code === "") {
      setCouponStatus({ loading: false, error: null, discount_cents: 0, campaign_name: null });
      setPreviewShippingCents(null);
      return;
    }
    await runPreview({ couponCode: code, silent: false });
  }

  const cardSurface =
    "rounded-[28px] border border-white/70 bg-white/85 backdrop-blur shadow-xl shadow-[#6320ee]/10";


  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,#f6f2ff_0%,#f7f4ff_40%,#fcfbff_100%)] text-slate-900">
      <div className="relative">
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute -top-36 right-[-12%] h-[320px] w-[320px] rounded-full bg-[#6320ee]/12 blur-3xl" />
          <div className="absolute -bottom-36 left-[-8%] h-[280px] w-[280px] rounded-full bg-[#c4b5ff]/20 blur-3xl" />
        </div>
        <div className="relative max-w-3xl mx-auto px-3 sm:px-4 py-4 space-y-4">
      {/* Voltar aos produtos */}
      <div className={`${cardSurface} relative h-14 px-3`}>
        <div className="absolute left-3 top-1/2 -translate-y-1/2">
          <UserLoginButton
            onLogin={refreshVendorInfo}
            onLogout={() => {
              setVendorLogged(false);
            }}
          />
        </div>
        <h1 className="h-full flex items-center justify-center text-xl font-semibold text-center tracking-[0.02em]">
          Finalizar pedido
        </h1>
        <button
          onClick={() => router.push(vitrineBackUrl)}
          className="absolute right-3 top-1/2 -translate-y-1/2 px-3 py-1.5 text-sm rounded-xl border border-neutral-200 bg-white hover:bg-neutral-100 active:scale-95"
        >
          Voltar
        </button>
      </div>

      {/* Modo vendedor */}
      {vendorLogged && (
        <section className={`${cardSurface} p-4 sm:p-5 space-y-3`}>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.14em] text-neutral-500">Modo vendedor</p>
              <h2 className="text-lg font-semibold">Buscar cliente cadastrado</h2>
            </div>
            <span className="text-xs px-2 py-1 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200">
              Conectado
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={openCustomerModal}
              className="px-4 py-2 rounded-xl bg-[#6320ee] text-white font-semibold hover:brightness-95 active:scale-95"
            >
              Buscar cliente
            </button>
            <p className="text-sm text-neutral-600">
              Procure pelo nome e preencha automaticamente telefone e nome do comprador.
            </p>
            {vendorError && <span className="text-sm text-red-600">{vendorError}</span>}
          </div>
        </section>
      )}

      <section className={`${cardSurface} p-4 sm:p-5 space-y-3`}>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.16em] text-neutral-500">Resumo</p>
            <h2 className="text-lg font-semibold text-neutral-900">Itens do pedido</h2>
          </div>
          <span className="text-[11px] uppercase tracking-[0.18em] text-[#5c31d6] bg-[#ede7ff] px-3 py-1 rounded-full">
            {items.length} item(ns)
          </span>
        </div>
        {items.map((i) => (
          <div
            key={i.lineId}
            className="flex justify-between items-center rounded-2xl border border-neutral-200 bg-white/90 p-3"
          >
            <div>
              <div className="font-semibold text-neutral-900">{i.name}</div>
              <div className="text-sm text-neutral-600">
                {fmtBRL(i.price / 100)}
                {i.isCustom && (
                  <span className="ml-2 text-xs text-neutral-500">(custom)</span>
                )}
              </div>
              {i.additionals && i.additionals.length > 0 && (
                <div className="text-xs text-neutral-500 mt-1">
                  Adicionais: {i.additionals.map((item) => item.name).join(", ")}
                </div>
              )}
              {i.itemNotes && (
                <div className="text-xs text-neutral-500 mt-1">Obs: {i.itemNotes}</div>
              )}
            </div>
            <div className="text-right">
              <div className="text-xs text-neutral-500">Quantidade</div>
              <div className="font-semibold">{i.quantity}</div>
            </div>
          </div>
        ))}
        {items.length === 0 && (
          <div className="rounded-2xl border border-dashed border-neutral-300 bg-white/70 p-4 text-sm text-neutral-500">
            Carrinho vazio
          </div>
        )}
      </section>

      <section className={`${cardSurface} p-4 sm:p-5 space-y-3`}>
        <div>
          <p className="text-xs uppercase tracking-[0.16em] text-neutral-500">Dados</p>
          <h2 className="text-lg font-semibold text-neutral-900">Informacoes de entrega e pagamento</h2>
        </div>
        <label className="block">
          <span className="text-sm flex items-center gap-1">
            Telefone <span className="text-red-600">*</span>
          </span>
          <input
            required
            type="tel"
            className={inputClass(showValidation && missingPhone)}
            value={form.telefone}
            onChange={(e) => setForm({ ...form, telefone: e.target.value })}
          />
          {showValidation && missingPhone && (
            <span className="mt-1 block text-xs text-red-600">Informe o telefone.</span>
          )}
        </label>
        <label className="block">
          <span className="text-sm flex items-center gap-1">
            Nome <span className="text-red-600">*</span>
          </span>
          <input
            required
            className={inputClass(showValidation && missingName)}
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          {showValidation && missingName && (
            <span className="mt-1 block text-xs text-red-600">Informe o nome.</span>
          )}
        </label>

        <div className="grid sm:grid-cols-2 gap-2">
          <label className="block">
            <span className="text-sm flex items-center gap-1">
              Data de entrega <span className="text-red-600">*</span>
            </span>
            <input
              className={inputClass(showValidation && (missingDeliveryDate || deliveryDateUnavailable))}
              type="date"
              min={minDeliveryDate}
              value={form.delivery_date}
              onChange={(e) => {
                const selectedDate = e.target.value;
                const baseDate = selectedDate < minDeliveryDate ? minDeliveryDate : selectedDate;
                const adjustedDate = nextOpenDate(baseDate, calendarDates, operatingHours) ?? baseDate;
                setForm({ ...form, delivery_date: adjustedDate });
              }}
            />
            {showValidation && missingDeliveryDate && (
              <span className="mt-1 block text-xs text-red-600">Selecione uma data valida.</span>
            )}
            {showValidation && !missingDeliveryDate && deliveryDateUnavailable && (
              <span className="mt-1 block text-xs text-red-600">
                A loja nao atende na data selecionada.
              </span>
            )}
            {!deliveryDateOpen && (
              <span className="mt-1 block text-xs text-red-600">
                A loja nao funciona na data selecionada.
              </span>
            )}
          </label>
          <label className="block">
            <span className="text-sm">Observações</span>
            <input
              className="input"
              value={form.notas}
              onChange={(e) => setForm({ ...form, notas: e.target.value })}
            />
          </label>
        </div>

        <div className="space-y-2">
          <span className="text-sm flex items-center gap-1">
            Forma de entrega <span className="text-red-600">*</span>
          </span>
          <div className="grid sm:grid-cols-2 gap-2">
            {pickupOptionEnabled && (
              <button
                type="button"
                onClick={() => setRetirada(true)}
                className={`rounded-xl border px-3 py-2 text-sm font-semibold transition ${
                  isPickup
                    ? "border-[#6320ee] bg-[#ede7ff] text-[#4a19b3] shadow-sm ring-1 ring-[#d9ccff]"
                    : "border-neutral-200 bg-white/90 text-neutral-700 hover:border-[#c4b5ff]"
                }`}
              >
                Retirada
              </button>
            )}
            {deliveryOptionEnabled && (
              <button
                type="button"
                onClick={() => setRetirada(false)}
                className={`rounded-xl border px-3 py-2 text-sm font-semibold transition ${
                  isDelivery
                    ? "border-[#6320ee] bg-[#ede7ff] text-[#4a19b3] shadow-sm ring-1 ring-[#d9ccff]"
                    : "border-neutral-200 bg-white/90 text-neutral-700 hover:border-[#c4b5ff]"
                }`}
              >
                Entrega
              </button>
            )}
          </div>
          {!pickupOptionEnabled && !deliveryOptionEnabled && (
            <span className="text-xs text-red-600">Esta loja nao possui forma de atendimento disponivel.</span>
          )}
          {storesLoading && <span className="text-xs text-neutral-500">Carregando dados da loja...</span>}
          {storesError && <span className="text-xs text-red-600">{storesError}</span>}
          {showValidation && missingStore && (
            <span className="text-xs text-red-600">Abra o checkout a partir da URL da loja.</span>
          )}
          {showValidation && missingFulfillment && (
            <span className="text-xs text-red-600">Selecione a forma de entrega.</span>
          )}
        </div>

        {isPickup && selectedStore && (
          <button
            type="button"
            onClick={copyPickupAddress}
            className={`w-full text-left rounded-xl border px-3 py-3 transition ${
              pickupAddressCopied
                ? "border-emerald-300 bg-emerald-50"
                : "border-neutral-200 bg-neutral-50 hover:border-[#c4b5ff]"
            }`}
            title="Clique para copiar o endereco de retirada"
          >
            <p className="text-[11px] uppercase tracking-[0.16em] text-neutral-500">
              {pickupAddressCopied ? "Copiado" : "Endereco de retirada"}
            </p>
            <p className="text-sm font-semibold text-neutral-900">
              {pickupAddress || "Endereco de retirada nao informado"}
            </p>
            <p className="text-xs text-neutral-500">{selectedStore.name}</p>
          </button>
        )}

        {isDelivery && (
          <div className="grid grid-cols-2 gap-2">
            <label className="col-span-2">
              <span className="text-sm flex items-center gap-1">
                CEP <span className="text-red-600">*</span>
              </span>
              <input
                className={inputClass(showValidation && (missingCep || invalidCep))}
                value={form.cep}
                onChange={(e) => setForm({ ...form, cep: e.target.value })}
                onBlur={onCEPBlur}
              />
              {showValidation && missingCep && (
                <span className="mt-1 block text-xs text-red-600">Informe o CEP.</span>
              )}
              {showValidation && !missingCep && invalidCep && (
                <span className="mt-1 block text-xs text-red-600">CEP invalido.</span>
              )}
            </label>
            <label className="col-span-2">
              <span className="text-sm flex items-center gap-1">
                Logradouro <span className="text-red-600">*</span>
              </span>
              <input
                className={inputClass(showValidation && missingStreet)}
                value={form.logradouro}
                onChange={(e) =>
                  setForm({ ...form, logradouro: e.target.value })
                }
              />
              {showValidation && missingStreet && (
                <span className="mt-1 block text-xs text-red-600">Informe o logradouro.</span>
              )}
            </label>
            <label>
              <span className="text-sm flex items-center gap-1">
                Número <span className="text-red-600">*</span>
              </span>
              <input
                className={inputClass(showValidation && missingNumber)}
                value={form.numero}
                onChange={(e) => setForm({ ...form, numero: e.target.value })}
              />
              {showValidation && missingNumber && (
                <span className="mt-1 block text-xs text-red-600">Informe o numero.</span>
              )}
            </label>
            <label>
              <span className="text-sm">Compl.</span>
              <input
                className="input"
                value={form.complemento}
                onChange={(e) =>
                  setForm({ ...form, complemento: e.target.value })
                }
              />
            </label>
            <label className="col-span-2">
              <span className="text-sm flex items-center gap-1">
                Bairro <span className="text-red-600">*</span>
              </span>
              <input
                className={inputClass(showValidation && missingDistrict)}
                value={form.bairro}
                onChange={(e) => setForm({ ...form, bairro: e.target.value })}
              />
              {showValidation && missingDistrict && (
                <span className="mt-1 block text-xs text-red-600">Informe o bairro.</span>
              )}
            </label>
            <label>
              <span className="text-sm flex items-center gap-1">
                Cidade <span className="text-red-600">*</span>
              </span>
              <input
                className={inputClass(showValidation && missingCity)}
                value={form.cidade}
                onChange={(e) => setForm({ ...form, cidade: e.target.value })}
              />
              {showValidation && missingCity && (
                <span className="mt-1 block text-xs text-red-600">Informe a cidade.</span>
              )}
            </label>
            <label>
              <span className="text-sm flex items-center gap-1">
                UF <span className="text-red-600">*</span>
              </span>
              <input
                className={inputClass(showValidation && missingState)}
                value={form.uf}
                onChange={(e) => setForm({ ...form, uf: e.target.value })}
              />
              {showValidation && missingState && (
                <span className="mt-1 block text-xs text-red-600">Informe a UF.</span>
              )}
            </label>
          </div>
        )}

        <div className="space-y-2">
          <span className="text-sm flex items-center gap-1">
            Forma de pagamento <span className="text-red-600">*</span>
          </span>
          <div className="grid sm:grid-cols-2 gap-2">
            {availableMethods.includes("pix") && (
              <button
                type="button"
                onClick={() => setMethod("pix")}
                className={`rounded-xl border px-3 py-2 text-sm font-semibold transition ${
                  method === "pix"
                    ? "border-[#6320ee] bg-[#ede7ff] text-[#4a19b3] shadow-sm ring-1 ring-[#d9ccff]"
                    : "border-neutral-200 bg-white/90 text-neutral-700 hover:border-[#c4b5ff]"
                }`}
              >
                PIX
              </button>
            )}
            {availableMethods.includes("cash") && (
              <button
                type="button"
                onClick={() => setMethod("cash")}
                className={`rounded-xl border px-3 py-2 text-sm font-semibold transition ${
                  method === "cash"
                    ? "border-[#6320ee] bg-[#ede7ff] text-[#4a19b3] shadow-sm ring-1 ring-[#d9ccff]"
                    : "border-neutral-200 bg-white/90 text-neutral-700 hover:border-[#c4b5ff]"
                }`}
              >
                Dinheiro
              </button>
            )}
          </div>
          {showValidation && missingPayment && (
            <span className="text-xs text-red-600">Selecione a forma de pagamento.</span>
          )}
          {method === "cash" && (
            <div className="mt-2 rounded-xl border border-neutral-200 bg-white/80 px-3 py-2 space-y-1">
              <div className="grid grid-cols-[auto_auto_1fr] items-center gap-2">
                <p className="text-xs text-neutral-600 whitespace-nowrap">Precisa de troco?</p>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setCashNeedsChange(false);
                      setCashChangeFor("");
                    }}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition ${
                      cashNeedsChange === false
                        ? "border-[#6320ee] bg-[#ede7ff] text-[#4a19b3]"
                        : "border-neutral-200 bg-white text-neutral-700 hover:border-[#c4b5ff]"
                    }`}
                  >
                    Nao
                  </button>
                  <button
                    type="button"
                    onClick={() => setCashNeedsChange(true)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition ${
                      cashNeedsChange === true
                        ? "border-[#6320ee] bg-[#ede7ff] text-[#4a19b3]"
                        : "border-neutral-200 bg-white text-neutral-700 hover:border-[#c4b5ff]"
                    }`}
                  >
                    Sim
                  </button>
                </div>
                <div className="min-w-0">
                  {cashNeedsChange === true && (
                    <input
                      className={`${inputClass(showValidation && missingCashChangeFor)} placeholder:text-xs`}
                      placeholder="Para quanto?"
                      value={cashChangeFor}
                      onChange={(e) => setCashChangeFor(e.target.value)}
                    />
                  )}
                </div>
              </div>
              {showValidation && missingCashChangeFor && (
                <span className="text-xs text-red-600">Informe o valor do troco.</span>
              )}
            </div>
          )}
        </div>
        {paymentMethodsError && <div className="text-xs text-red-600">{paymentMethodsError}</div>}

        <label className="block">
          <span className="text-sm">Cupom</span>
          <div className="flex gap-2">
            <input
              className="input flex-1"
              value={coupon}
              onChange={(e) => setCoupon(e.target.value)}
              onBlur={validateCoupon}
            />
            <button
              type="button"
              onClick={validateCoupon}
              className="px-3 py-2 rounded-xl border border-neutral-200 bg-white hover:bg-neutral-100 text-sm font-medium"
              disabled={couponStatus.loading}
            >
              {couponStatus.loading ? "Validando..." : "Aplicar"}
            </button>
          </div>
          <div className="text-xs mt-1">
            {couponStatus.loading && <span className="text-neutral-500">Validando cupom...</span>}
            {couponStatus.error && <span className="text-red-600">{couponStatus.error}</span>}
            {!couponStatus.error && couponStatus.discount_cents > 0 && (
              <span className="text-emerald-700">
                {coupon.trim() ? "Cupom aplicado" : "Campanha aplicada"}
                {couponStatus.campaign_name ? ` (${couponStatus.campaign_name})` : ""}: -{" "}
                {fmtBRL(couponStatus.discount_cents / 100)}
              </span>
            )}
          </div>
        </label>

        {/* Resumo */}
        <div className="space-y-2 pt-3 border-t border-neutral-200">
          <div className="flex justify-between text-sm">
            <span className="text-neutral-600">Subtotal</span>
            <span className="font-medium text-neutral-900">{fmtBRL(subtotalCents / 100)}</span>
          </div>
          {couponStatus.discount_cents > 0 && (
            <div className="flex justify-between text-sm text-emerald-700">
              <span>Desconto</span>
              <span className="font-medium">-{fmtBRL(couponStatus.discount_cents / 100)}</span>
            </div>
          )}

          {isDelivery && (
            <div className="flex justify-between items-center text-sm">
              <span className="text-neutral-600">Frete</span>
              <span className="text-right">
                {loadingFrete && "calculando..."}
                {erroFrete && (
                  //<span className="text-red-600">erro ao calcular</span>
                  <span className="text-red-600">{String(erroFrete)}</span>
                )}
                {!loadingFrete &&
                  !erroFrete &&
                  (displayFreteCentavos === null
                    ? "-"
                    : fmtBRL((displayFreteCentavos || 0) / 100))}
              </span>
            </div>
          )}
          {showValidation && shippingInvalid && (
            <div className="text-xs text-red-600">
              Calcule o frete antes de finalizar o pedido.
            </div>
          )}

        <div className="flex justify-between items-center rounded-xl border border-neutral-200 bg-white/80 px-3 py-2 font-semibold">
          <span className="text-neutral-700">Total</span>
          <span className="text-lg text-neutral-900">{fmtBRL(totalCentavos / 100)}</span>
        </div>
      </div>

      {showValidation && hasValidationErrors && (
        <div className="text-xs text-red-600">
          Preencha os campos obrigatorios destacados.
        </div>
      )}

      <button
        disabled={
          loading ||
          items.length === 0 ||
          (isDelivery && loadingFrete)
        }
          onClick={() => submit()}
          className="w-full py-3.5 rounded-2xl bg-gradient-to-r from-[#6320ee] to-[#4f16c8] text-white font-semibold tracking-[0.01em] shadow-lg shadow-[#6320ee]/25 hover:brightness-95 active:scale-95 disabled:opacity-50 disabled:shadow-none"
        >
          {loading ? "Enviando..." : "Finalizar pedido"}
        </button>
      </section>
        </div>
      </div>

      {showPreorderAlert && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm px-4">
          <div className="w-full max-w-md rounded-3xl bg-white text-slate-900 shadow-2xl p-6 space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.18em] text-amber-600">Encomenda</p>
                <h3 className="text-xl font-semibold">Loja fechada no momento</h3>
              </div>
              <button
                onClick={() => setShowPreorderAlert(false)}
                className="text-sm px-3 py-1 rounded-full bg-neutral-100 border border-neutral-200 hover:bg-neutral-200"
              >
                Fechar
              </button>
            </div>
            <div className="space-y-2 text-sm text-neutral-700">
              <p>
                Esta loja esta fechada agora. Se voce continuar, o pedido sera registrado como encomenda para o
                proximo dia de funcionamento.
              </p>
              <p className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-amber-900">
                Proxima data: <span className="font-semibold">{preorderDateLabel}</span>
              </p>
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowPreorderAlert(false)}
                className="px-4 py-2 rounded-lg bg-neutral-100 text-neutral-800 text-sm font-semibold hover:bg-neutral-200"
              >
                Cancelar
              </button>
              <button
                onClick={() => {
                  setShowPreorderAlert(false);
                  submit(true);
                }}
                className="px-4 py-2 rounded-lg bg-amber-600 text-white text-sm font-semibold hover:brightness-95"
              >
                Continuar
              </button>
            </div>
          </div>
        </div>
      )}

      {stockAlertItems && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm px-4">
          <div className="w-full max-w-md rounded-3xl bg-white text-slate-900 shadow-2xl p-6 space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.18em] text-amber-600">Estoque</p>
                <h3 className="text-xl font-semibold">Ops, estoque insuficiente</h3>
              </div>
              <button
                onClick={() => setStockAlertItems(null)}
                className="text-sm px-3 py-1 rounded-full bg-neutral-100 border border-neutral-200 hover:bg-neutral-200"
              >
                Fechar
              </button>
            </div>
            <div className="space-y-2 text-sm text-neutral-700">
              <p>Nao foi possivel finalizar seu pedido porque alguns itens excedem o estoque disponivel.</p>
              <div className="space-y-2">
                {stockAlertItems.map((item, idx) => (
                  <div
                    key={`${item.productName}-${idx}`}
                    className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
                  >
                    <div className="font-semibold text-amber-900">{item.productName}</div>
                    <div>
                      Estoque disponivel: <span className="font-semibold">{item.available ?? 0}</span>
                      {typeof item.requested === "number" && (
                        <>
                          {" "}
                          (voce pediu <span className="font-semibold">{item.requested}</span>)
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </div>
              <p>Por favor, ajuste as quantidades no carrinho para continuar.</p>
            </div>
            <div className="flex justify-end">
              <button
                onClick={() => setStockAlertItems(null)}
                className="px-4 py-2 rounded-lg bg-amber-600 text-white text-sm font-semibold hover:brightness-95"
              >
                Entendi
              </button>
            </div>
          </div>
        </div>
      )}

      {showCustomerModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm px-4">
          <div className="w-full max-w-3xl rounded-3xl bg-white text-slate-900 shadow-2xl p-6 space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.18em] text-neutral-500">Clientes</p>
                <h3 className="text-xl font-semibold">Selecione um cliente</h3>
              </div>
              <button
                onClick={() => setShowCustomerModal(false)}
                className="text-sm px-3 py-1 rounded-full bg-neutral-100 border border-neutral-200 hover:bg-neutral-200"
              >
                Fechar
              </button>
            </div>

            <div className="flex items-center gap-3">
              <input
                className="input w-full"
                placeholder="Buscar pelo nome..."
                value={customerQuery}
                onChange={(e) => setCustomerQuery(e.target.value)}
              />
              {customersLoading && <span className="text-sm text-neutral-500">Carregando...</span>}
            </div>

            <div className="max-h-80 overflow-y-auto space-y-2">
              {filteredCustomers.length === 0 && !customersLoading && (
                <p className="text-sm text-neutral-500">Nenhum cliente encontrado.</p>
              )}
              {filteredCustomers.map((c) => (
                <button
                  key={c.id}
                  onClick={() => selectCustomer(c)}
                  className="w-full text-left px-3 py-2 rounded-xl border border-neutral-200 hover:border-[#6320ee] hover:bg-[#f7f3ff] transition"
                >
                  <div className="font-semibold">{c.name}</div>
                  <div className="text-sm text-neutral-600">{c.phone || "Sem telefone"}</div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
