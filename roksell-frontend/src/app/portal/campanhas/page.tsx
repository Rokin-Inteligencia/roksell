"use client";
import { useEffect, useState, useRef } from "react";
import { adminFetch, adminUpload } from "@/lib/admin-api";
import { useAdminGuard } from "@/lib/use-admin-guard";
import { useTenantModules } from "@/lib/use-tenant-modules";
import { Campaign, Category, Product } from "@/types";
import { ProfileBadge } from "@/components/admin/ProfileBadge";
import { AdminSidebar } from "@/components/admin/AdminSidebar";
import { FieldTooltip } from "@/components/admin/FieldTooltip";
import { PriceInput } from "@/components/catalog/PriceInput";
import { BannerCropModal } from "@/components/admin/BannerCropModal";
import { adminMenuWithHome } from "@/config/adminMenu";
import { usePathname } from "next/navigation";
import { useOrgName } from "@/lib/use-org-name";
import { clearAdminToken } from "@/lib/admin-auth";

function RequiredLabel({ children }: { children: string }) {
  return (
    <span className="text-sm font-medium text-slate-800">
      {children} <span className="text-red-600">*</span>
    </span>
  );
}

type FormState = {
  name: string;
  type: Campaign["type"];
  value_percent: number | string;
  category_id: string;
  min_order_cents: number | string;
  starts_at: string;
  ends_at: string;
  is_active: boolean;
  usage_limit: number | string;
  apply_mode: "first" | "stack";
  store_ids: string[];
  rule_config: RuleConfig;
  banner_enabled: boolean;
  banner_position: "top" | "between";
  banner_popup: boolean;
  banner_display_order: number;
  banner_image_url: string;
};

type RuleCondition = {
  dimension: string;
  operator: string;
  value?: string | number;
  values?: string[];
  product_id?: string;
  category_id?: string;
};

type RuleAction = {
  type: string;
  value_cents?: string | number;
  value_percent?: string;
  product_id?: string;
  category_id?: string;
  gift_qty?: string;
};

type CampaignRule = {
  name: string;
  conditions_logic: "E" | "OU";
  conditions: RuleCondition[];
  action: RuleAction;
  stop_on_match: boolean;
};

type RuleConfig = {
  rules: CampaignRule[];
};

type StoreOption = {
  id: string;
  name: string;
  slug?: string;
};

type GroupOptionsResponse = {
  stores: StoreOption[];
};

const defaultForm: FormState = {
  name: "",
  type: "order_percent",
  value_percent: 10,
  category_id: "",
  min_order_cents: "",
  starts_at: "",
  ends_at: "",
  is_active: true,
  usage_limit: "",
  apply_mode: "first",
  store_ids: [],
  rule_config: {
    rules: [
      {
        name: "Regra 1",
        conditions_logic: "E",
        conditions: [{ dimension: "quantidade_total", operator: ">=", value: "4" }],
        action: { type: "frete_maximo", value_cents: "600" },
        stop_on_match: true,
      },
    ],
  },
  banner_enabled: false,
  banner_position: "top",
  banner_popup: false,
  banner_display_order: 0,
  banner_image_url: "",
};

const conditionDimensions = [
  { value: "quantidade_total", label: "Quantidade total de itens" },
  { value: "quantidade_produto", label: "Quantidade de um produto" },
  { value: "produto", label: "Produto no carrinho" },
  { value: "categoria", label: "Categoria no carrinho" },
  { value: "valor_total", label: "Valor total do pedido (R$)" },
  { value: "tipo_entrega", label: "Tipo de entrega" },
  { value: "cliente", label: "Cliente (ID)" },
];

const conditionOperators = [
  { value: "=", label: "Igual a" },
  { value: "!=", label: "Diferente de" },
  { value: ">=", label: "Maior ou igual" },
  { value: "<=", label: "Menor ou igual" },
  { value: ">", label: "Maior que" },
  { value: "<", label: "Menor que" },
];

const actionOptions = [
  { value: "frete_maximo", label: "Frete máximo (R$)" },
  { value: "frete_desconto", label: "Desconto no frete (R$)" },
  { value: "frete_gratis", label: "Frete grátis" },
  { value: "desconto_total_percentual", label: "Desconto no total (%)" },
  { value: "desconto_total_fixo", label: "Desconto no total (R$)" },
  { value: "desconto_item_percentual", label: "Desconto por produto (%)" },
  { value: "desconto_item_fixo", label: "Desconto por produto (R$)" },
  { value: "desconto_categoria_percentual", label: "Desconto por categoria (%)" },
  { value: "desconto_categoria_fixo", label: "Desconto por categoria (R$)" },
  { value: "brinde_produto", label: "Brinde (produto)" },
];

function fmtDateShort(value?: string | null) {
  if (!value) return "-";
  const d = new Date(value);
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function fmtDateShort(value?: string | null) {
  if (!value) return "-";
  const d = new Date(value);
  return d.toLocaleDateString("pt-BR");
}

export default function CampaignsAdmin() {
  const ready = useAdminGuard();
  const tenantName = useOrgName();
  const pathname = usePathname();
  const { hasModule, hasModuleAction, ready: modulesReady } = useTenantModules();
  const moduleAllowed = hasModule("campaigns");
  const moduleBlocked = modulesReady && !moduleAllowed;
  const canEditCampaigns = hasModuleAction("campaigns", "edit");
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

  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [stores, setStores] = useState<StoreOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"active" | "all" | "inactive">("active");
  const [filterOpen, setFilterOpen] = useState(false);
  const [form, setForm] = useState<FormState>(defaultForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [bannerFile, setBannerFile] = useState<File | null>(null);
  const [bannerPreview, setBannerPreview] = useState<string | null>(null);
  const [currentBannerUrl, setCurrentBannerUrl] = useState<string | null>(null);
  const [removeBanner, setRemoveBanner] = useState(false);
  const [showCropModal, setShowCropModal] = useState(false);
  const [fileToCrop, setFileToCrop] = useState<File | null>(null);
  const formRef = useRef<HTMLDivElement>(null);
  const fieldRefs = useRef<Record<string, HTMLDivElement | null>>({});

  function buildRuleConfigPayload(config: RuleConfig): RuleConfig {
    return {
      rules: config.rules.map((rule) => ({
        name: rule.name.trim() || "Regra",
        conditions_logic: rule.conditions_logic,
        stop_on_match: rule.stop_on_match,
        conditions: rule.conditions.map((condition) => ({
          dimension: condition.dimension,
          operator: condition.operator,
          value:
            condition.dimension === "valor_total"
              ? inputToCents(String(condition.value ?? "")) || 0
              : condition.value ?? "",
          product_id: condition.product_id || undefined,
          category_id: condition.category_id || undefined,
          values: condition.values,
        })),
        action: {
          type: rule.action.type,
          value_cents:
            rule.action.value_cents !== undefined && rule.action.value_cents !== null && rule.action.value_cents !== ""
              ? Number.parseInt(String(rule.action.value_cents), 10)
              : "",
          value_percent: rule.action.value_percent ?? "",
          product_id: rule.action.product_id || undefined,
          category_id: rule.action.category_id || undefined,
          gift_qty: rule.action.gift_qty ?? "",
        },
      })),
    };
  }

  function centsToInput(value: number | string) {
    if (value === "" || value === null || value === undefined) return "";
    const numeric = typeof value === "number" ? value : Number(value);
    if (!Number.isFinite(numeric)) return "";
    return (numeric / 100).toFixed(2);
  }

  function inputToCents(value: string) {
    const cleaned = value.replace(",", ".").replace(/[^0-9.]/g, "");
    const parsed = Number.parseFloat(cleaned);
    if (!Number.isFinite(parsed)) return "";
    return Math.round(parsed * 100);
  }

  /** Formata centavos para exibição R$ X,XX (sempre com ,00 se inteiro). */
  function formatMinOrderDisplay(cents: number | string): string {
    if (cents === "" || cents === null || cents === undefined) return "R$ 0,00";
    const c = typeof cents === "number" ? cents : Number(cents);
    if (!Number.isFinite(c) || c < 0) return "R$ 0,00";
    const reais = Math.floor(c / 100);
    const centavos = c % 100;
    return `R$ ${reais},${centavos.toString().padStart(2, "0")}`;
  }

  function handleMinOrderChange(e: React.ChangeEvent<HTMLInputElement>) {
    const raw = e.target.value.replace(/[^0-9,]/g, "");
    if (!raw) {
      setForm((f) => ({ ...f, min_order_cents: "" }));
      return;
    }
    const parsed = inputToCents(raw);
    setForm((f) => ({ ...f, min_order_cents: parsed === "" ? "" : parsed }));
  }

  function normalizeRuleConfigFromApi(config: RuleConfig | null | undefined): RuleConfig {
    if (!config || !Array.isArray(config.rules)) return defaultForm.rule_config;
    return {
      rules: config.rules.map((rule) => ({
        ...rule,
        conditions: rule.conditions.map((condition) => ({
          ...condition,
          value:
            condition.dimension === "valor_total"
              ? centsToInput(Number(condition.value || 0))
              : (condition.value ?? ""),
        })),
        action: {
          ...rule.action,
          value_cents: rule.action.value_cents === null || rule.action.value_cents === undefined ? "" : String(rule.action.value_cents),
        },
      })),
    };
  }

  function resetBannerState() {
    if (bannerPreview?.startsWith("blob:")) {
      URL.revokeObjectURL(bannerPreview);
    }
    setBannerFile(null);
    setBannerPreview(null);
    setCurrentBannerUrl(null);
    setRemoveBanner(false);
    setShowCropModal(false);
    setFileToCrop(null);
  }

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const qs = new URLSearchParams();
      if (search.trim()) qs.set("search", search.trim());
      const data = await adminFetch<Campaign[]>(`/admin/campaigns?${qs.toString()}`);
      setCampaigns(data);
      const catalog = await adminFetch<{ categories: Category[]; products: unknown[] }>("/catalog");
      setCategories(catalog.categories || []);
      setProducts((catalog.products as Product[]) || []);
      const options = await adminFetch<GroupOptionsResponse>("/admin/groups/options");
      setStores(options.stores || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao carregar campanhas");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (ready && modulesReady && moduleAllowed) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, modulesReady, moduleAllowed]);

  const visibleCampaigns = campaigns.filter((campaign) => {
    if (statusFilter === "all") return true;
    if (statusFilter === "active") return campaign.is_active;
    return !campaign.is_active;
  });

  async function save() {
    if (!canEditCampaigns) return;
    const errors: Record<string, string> = {};
    if (!form.name.trim()) errors.name = "Nome é obrigatório.";
    if (form.type === "category_percent" && !form.category_id) errors.category_id = "Selecione a categoria.";
    if (form.type === "rule") {
      if (!form.rule_config?.rules?.length) errors.rule_config = "Adicione ao menos uma regra.";
    }
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) {
      const firstKey = ["name", "category_id", "rule_config"].find((k) => errors[k]);
      const el = firstKey && formRefs.current[firstKey];
      if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
      setError("Preencha os campos obrigatórios.");
      return;
    }
    setError(null);
    try {
      setSaving(true);
      setError(null);

      const errors: string[] = [];
      if (!form.name.trim()) errors.push("name");
      if (form.type === "category_percent" && !form.category_id) errors.push("category_id");
      if (form.type !== "rule" && (form.value_percent === "" || Number(form.value_percent) < 0 || Number(form.value_percent) > 100)) {
        errors.push("value_percent");
      }
      if (form.banner_enabled && !removeBanner && !currentBannerUrl && !bannerFile) errors.push("banner");

      if (errors.length > 0) {
        const first = errors[0];
        const el = fieldRefs.current[first] ?? formRef.current;
        if (el) {
          el.scrollIntoView({ behavior: "smooth", block: "center" });
        }
        setError(
          first === "name"
            ? "Preencha o nome da campanha."
            : first === "category_id"
              ? "Selecione a categoria para desconto por categoria."
              : first === "value_percent"
                ? "Informe o valor percentual entre 0 e 100."
                : "Adicione uma imagem para ativar o banner."
        );
        setSaving(false);
        return;
      }

      const wantsFileUpload = !!bannerFile;
      const bannerEnabledRequested = form.banner_enabled && !removeBanner;
      const hasStoredBanner = Boolean(currentBannerUrl);
      const bannerEnabledForPayload = bannerEnabledRequested && (!wantsFileUpload || hasStoredBanner);
      if (bannerEnabledRequested && !hasStoredBanner && !wantsFileUpload) {
        setError("Adicione uma imagem para ativar o banner.");
        return;
      }

      const payload: Record<string, unknown> = {
        name: form.name.trim(),
        type: form.type,
        value_percent: form.type === "rule" ? 0 : Number(form.value_percent),
        category_id: form.type === "category_percent" ? form.category_id || null : null,
        min_order_cents:
          form.min_order_cents === "" || form.min_order_cents === undefined
            ? null
            : Number(form.min_order_cents),
        starts_at: form.starts_at ? new Date(form.starts_at).toISOString() : null,
        ends_at: form.ends_at ? new Date(form.ends_at).toISOString() : null,
        is_active: form.is_active,
        usage_limit: form.usage_limit === "" ? null : Number(form.usage_limit),
        apply_mode: form.apply_mode,
        store_ids: form.store_ids,
        rule_config:
          form.type === "rule"
            ? buildRuleConfigPayload(form.rule_config)
            : null,
        banner_enabled: bannerEnabledForPayload,
        banner_position: bannerEnabledForPayload ? form.banner_position : null,
        banner_popup: bannerEnabledForPayload ? form.banner_popup : false,
        banner_display_order: form.banner_display_order,
      };
      if (removeBanner) {
        payload.banner_enabled = false;
        payload.banner_position = null;
        payload.banner_popup = false;
        payload.banner_image_url = null;
      }
      let campaignId = editingId;
      if (editingId) {
        await adminFetch(`/admin/campaigns/${editingId}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
      } else {
        const created = await adminFetch<Campaign>(`/admin/campaigns`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
        campaignId = created.id;
      }
      if (bannerFile && campaignId && !removeBanner) {
        const formData = new FormData();
        const blob = await cropBannerToBlob(bannerFile, bannerPositionY);
        formData.append("file", blob, bannerFile.name);
        await adminUpload(`/admin/campaigns/${campaignId}/banner`, formData);
        if (bannerEnabledRequested && !bannerEnabledForPayload) {
          await adminFetch(`/admin/campaigns/${campaignId}`, {
            method: "PATCH",
            body: JSON.stringify({
              banner_enabled: true,
              banner_position: form.banner_position,
              banner_popup: form.banner_popup,
            }),
          });
        }
      }
      setForm(defaultForm);
      setEditingId(null);
      setShowForm(false);
      resetBannerState();
      setFieldErrors({});
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao salvar campanha");
    } finally {
      setSaving(false);
    }
  }

  function onEdit(c: Campaign) {
    if (!canEditCampaigns) return;
    resetBannerState();
    setEditingId(c.id);
    setForm({
      name: c.name,
      type: c.type,
      value_percent: c.value_percent,
      category_id: c.category_id || "",
      min_order_cents: c.min_order_cents ?? 0,
      starts_at: c.starts_at ? new Date(c.starts_at).toISOString().slice(0, 16) : "",
      ends_at: c.ends_at ? new Date(c.ends_at).toISOString().slice(0, 16) : "",
      is_active: c.is_active,
      usage_limit: c.usage_limit ?? "",
      apply_mode: (c.apply_mode as FormState["apply_mode"]) || "first",
      store_ids: c.store_ids ?? [],
      rule_config: normalizeRuleConfigFromApi(c.rule_config as RuleConfig),
      banner_enabled: c.banner_enabled ?? false,
      banner_position: c.banner_position === "between" ? "between" : "top",
      banner_popup: c.banner_popup ?? false,
      banner_display_order: c.banner_display_order ?? 0,
      banner_image_url: c.banner_image_url || "",
    });
    setCurrentBannerUrl(c.banner_image_url || null);
    setBannerPreview(c.banner_image_url || null);
    setRemoveBanner(false);
    setShowForm(true);
  }

  async function toggleActive(c: Campaign) {
    if (!canEditCampaigns) return;
    try {
      setSaving(true);
      await adminFetch(`/admin/campaigns/${c.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !c.is_active }),
      });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao atualizar status");
    } finally {
      setSaving(false);
    }
  }

  if (!ready) return null;

  const sidebarItems = adminMenuWithHome;

  return (
    <main className="min-h-screen text-slate-900 bg-[#f5f3ff]">
      <div className="max-w-7xl w-full mx-auto px-3 sm:px-4 lg:px-6 py-8">
        <div className="grid gap-6 lg:grid-cols-[260px_minmax(0,1fr)] items-start">
          <AdminSidebar
            menu={sidebarItems}
            currentPath={pathname}
            collapsible
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
              <div className="text-slate-900 space-y-1">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-600">Admin • Campanhas</p>
                <h1 className="text-3xl font-semibold">Gestão de campanhas</h1>
                <p className="text-sm text-slate-600">
                  Configure cupons e regras para desconto no pedido, frete ou categoria.
                </p>
              </div>
              <ProfileBadge />
            </header>
            {moduleBlocked ? (
              <section className="rounded-2xl bg-white border border-slate-200 p-4 space-y-2">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Modulo inativo</p>
                <h2 className="text-lg font-semibold">Campanhas indisponiveis</h2>
                <p className="text-sm text-slate-600">
                  Este modulo nao esta habilitado para a sua empresa. Fale com o administrador para liberar o acesso.
                </p>
              </section>
            ) : (
              <>
                <section className="rounded-3xl bg-white border border-slate-200 p-3 sm:p-5 space-y-4 shadow-sm">
              <div className="flex flex-wrap items-center gap-3 justify-between">
                <div className="space-y-1">
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Campanhas</p>
                  <h2 className="text-lg font-semibold text-slate-900">Gerencie campanhas</h2>
                </div>
                <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto sm:justify-end">
                  <div className="relative flex-1 sm:flex-initial flex items-center gap-2">
                    {filterOpen && (
                      <div className="absolute right-0 top-full mt-1 z-10 rounded-xl border border-slate-200 bg-white p-3 shadow-lg min-w-[200px] space-y-2">
                        <select
                          className="input w-full"
                          value={statusFilter}
                          onChange={(e) => setStatusFilter(e.target.value as typeof statusFilter)}
                        >
                          <option value="active">Somente ativas</option>
                          <option value="all">Todas</option>
                          <option value="inactive">Somente inativas</option>
                        </select>
                        <input
                          className="input w-full"
                          placeholder="Buscar campanha"
                          value={search}
                          onChange={(e) => setSearch(e.target.value)}
                        />
                        <button
                          onClick={() => {
                            load();
                            setFilterOpen(false);
                          }}
                          className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm bg-slate-100 hover:bg-white/20"
                          disabled={loading}
                        >
                          {loading ? "Carregando..." : "Buscar"}
                        </button>
                      </div>
                    )}
                    <button
                      type="button"
                      onClick={() => setFilterOpen((o) => !o)}
                      className="p-2 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-100"
                      aria-label="Filtros"
                    >
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
                      </svg>
                    </button>
                  </div>
                  <button
                    onClick={() => {
                      setShowForm(true);
                      setEditingId(null);
                      setForm(defaultForm);
                      resetBannerState();
                      setError(null);
                      setFieldErrors({});
                    }}
                    disabled={!canEditCampaigns}
                    className="px-3 py-2 rounded-lg bg-[#6320ee] text-white text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Nova campanha
                  </button>
                </div>
              </div>

              {error && <p className="text-sm text-red-300">{error}</p>}



              <div className="flex items-center justify-between text-sm">
                <div>
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-600">Campanhas</p>
                  <h2 className="text-lg font-semibold text-slate-900">Cadastradas</h2>
                </div>
                <span className="text-xs px-2 py-1 rounded-full bg-slate-100 border border-slate-200 text-slate-900">
                  {visibleCampaigns.length} campanha(s)
                </span>
              </div>
              {visibleCampaigns.length === 0 ? (
                <p className="text-sm text-slate-600">Nenhuma campanha cadastrada.</p>
              ) : (
                <>
                  <div className="space-y-3 sm:hidden">
                    {visibleCampaigns.map((c) => (
                      <div key={c.id} className="rounded-xl border border-slate-200 bg-slate-50 p-3 space-y-2">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <p className="text-sm font-semibold text-slate-900">{c.name}</p>
                            <p className="text-xs text-slate-600">
                              Vigência: {fmtDateShort(c.starts_at)} a {fmtDateShort(c.ends_at)}
                            </p>
                            <p className="text-xs text-slate-500">Aplicada {c.usage_count} vez(es)</p>
                          </div>
                          <span
                            className={`text-[10px] px-2 py-1 rounded-full border shrink-0 ${
                              c.is_active
                                ? "bg-emerald-200 border-emerald-300 text-emerald-900"
                                : "bg-red-200 border-red-300 text-red-900"
                            }`}
                          >
                            {c.is_active ? "Ativa" : "Inativa"}
                          </span>
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                          <button
                            onClick={() => onEdit(c)}
                            disabled={!canEditCampaigns}
                            className="w-full px-3 py-2 rounded-lg bg-slate-100 border border-slate-200 text-slate-900 text-xs disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            Editar
                          </button>
                          <button
                            onClick={() => toggleActive(c)}
                            disabled={!canEditCampaigns}
                            className="w-full px-3 py-2 rounded-lg bg-[#6320ee] text-white text-xs hover:brightness-95 disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            {c.is_active ? "Inativar" : "Ativar"}
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="hidden sm:block">
                    <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-slate-50">
                      <table className="w-full text-xs sm:text-sm min-w-[400px]">
                        <thead className="bg-slate-100 text-left text-slate-700">
                          <tr>
                            <th className="px-3 sm:px-4 py-2">Nome</th>
                            <th className="px-3 sm:px-4 py-2">Vigência</th>
                            <th className="px-3 sm:px-4 py-2">Vezes aplicada</th>
                            <th className="px-3 sm:px-4 py-2 text-right">Ações</th>
                          </tr>
                        </thead>
                        <tbody>
                          {visibleCampaigns.map((c, idx) => (
                            <tr key={c.id} className={idx % 2 === 0 ? "bg-transparent" : "bg-slate-50/50"}>
                              <td className="px-3 sm:px-4 py-2">
                                <div className="font-semibold flex items-center gap-2 text-slate-900">
                                  {c.name}
                                  <span
                                    className={`text-[10px] px-2 py-1 rounded-full border ${
                                      c.is_active
                                        ? "bg-emerald-200 border-emerald-300 text-emerald-900"
                                        : "bg-red-200 border-red-300 text-red-900"
                                    }`}
                                  >
                                    {c.is_active ? "Ativa" : "Inativa"}
                                  </span>
                                </div>
                              </td>
                              <td className="px-3 sm:px-4 py-2">
                                {fmtDateShort(c.starts_at)} a {fmtDateShort(c.ends_at)}
                              </td>
                              <td className="px-3 sm:px-4 py-2">{c.usage_count}</td>
                              <td className="px-3 sm:px-4 py-2 text-right space-x-2">
                                <button
                                  onClick={() => onEdit(c)}
                                  disabled={!canEditCampaigns}
                                  className="px-3 py-1 rounded-lg bg-slate-100 border border-slate-200 text-slate-900 text-xs disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                  Editar
                                </button>
                                <button
                                  onClick={() => toggleActive(c)}
                                  disabled={!canEditCampaigns}
                                  className="px-3 py-1 rounded-lg bg-[#6320ee] text-white text-xs hover:brightness-95 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                  {c.is_active ? "Inativar" : "Ativar"}
                                </button>
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
              </>
            )}
          </div>
        </div>
      </div>
      {!moduleBlocked && canEditCampaigns && showForm && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-start sm:items-center justify-center px-4 py-6 overflow-y-auto">
          <section className="w-full max-w-3xl rounded-3xl bg-white text-[#211a1d] border border-slate-200 p-5 sm:p-6 space-y-4 shadow-2xl max-h-[calc(100vh-3rem)] sm:max-h-[calc(100vh-4rem)] overflow-y-auto pr-1">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-[0.16em] text-neutral-500">
                  {editingId ? "Editar campanha" : "Nova campanha"}
                </p>
                <h2 className="text-lg font-semibold">Configuracao</h2>
              </div>
              <button
                onClick={() => {
                  setShowForm(false);
                  setEditingId(null);
                  setForm(defaultForm);
                  resetBannerState();
                  setError(null);
                  setFieldErrors({});
                }}
                className="text-sm px-3 py-1 rounded-full bg-neutral-100 border border-neutral-200 hover:bg-neutral-200"
              >
                Fechar
              </button>
            </div>

            {error && <p className="text-sm text-red-600">{error}</p>}

            <div ref={formRef} className="grid md:grid-cols-2 gap-3 text-sm">
              <div ref={(el) => { fieldRefs.current.name = el; }} className="space-y-1">
                <span className="inline-flex items-center gap-1">
                  Nome <span className="text-red-500">*</span>
                  <FieldTooltip text="Nome identificador da campanha (ex.: Black Friday)." />
                </span>
                <input
                  className={`input w-full ${fieldErrors.name ? "border-red-400 ring-1 ring-red-200" : ""}`}
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  aria-required
                />
              </div>
              <div className="space-y-1">
                <span className="inline-flex items-center gap-1">
                  Tipo <span className="text-red-500">*</span>
                  <FieldTooltip text="Tipo de desconto: no total do pedido, no frete, por categoria ou por regras." />
                </span>
                <select
                  className={`input w-full ${fieldErrors.type ? "border-red-400 ring-1 ring-red-200" : ""}`}
                  value={form.type}
                  onChange={(e) => setForm({ ...form, type: e.target.value as FormState["type"], category_id: "" })}
                >
                  <option value="order_percent">Desconto no total (%)</option>
                  <option value="shipping_percent">Desconto no frete (%)</option>
                  <option value="category_percent">Desconto por categoria (%)</option>
                  <option value="rule">Campanha por regras</option>
                </select>
              </div>
              {form.type !== "rule" && (
                <div ref={(el) => { fieldRefs.current.value_percent = el; }} className="space-y-1">
                  <span className="inline-flex items-center gap-1">
                    Valor (%) <span className="text-red-500">*</span>
                    <FieldTooltip text="Percentual de desconto entre 0 e 100." />
                  </span>
                  <input
                    className="input w-full"
                    type="number"
                    min={0}
                    max={100}
                    value={form.value_percent}
                    onChange={(e) => setForm({ ...form, value_percent: Number(e.target.value) })}
                  />
                </div>
              )}

              {form.type === "category_percent" && (
                <div ref={(el) => { fieldRefs.current.category_id = el; }} className="space-y-1">
                  <span className="inline-flex items-center gap-1">
                    Categoria <span className="text-red-500">*</span>
                    <FieldTooltip text="Categoria que receberá o desconto percentual." />
                  </span>
                  <select
                    className={`input w-full ${fieldErrors.category_id ? "border-red-400 ring-1 ring-red-200" : ""}`}
                    value={form.category_id}
                    onChange={(e) => setForm({ ...form, category_id: e.target.value })}
                  >
                    <option value="">Selecione...</option>
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="space-y-1">
                <span className="inline-flex items-center gap-1">
                  Pedido mínimo (R$)
                  <FieldTooltip text="Valor mínimo do pedido em reais para a campanha ser aplicada. Deixe em zero para não exigir mínimo." />
                </span>
                <PriceInput
                  valueCents={typeof form.min_order_cents === "number" ? form.min_order_cents : (Number(form.min_order_cents) || 0)}
                  onChange={(cents) => setForm({ ...form, min_order_cents: cents })}
                  className="input w-full"
                />
              </div>
              <div className="space-y-1">
                <span className="inline-flex items-center gap-1">
                  Limite de uso
                  <FieldTooltip text="Número máximo de vezes que a campanha pode ser aplicada. Deixe vazio para ilimitado." />
                </span>
                <input
                  className="input w-full"
                  type="number"
                  min={1}
                  value={form.usage_limit}
                  onChange={(e) =>
                    setForm({ ...form, usage_limit: e.target.value === "" ? "" : Number(e.target.value) })
                  }
                  placeholder="Opcional"
                />
              </div>
              <div className="space-y-1">
                <span className="inline-flex items-center gap-1">
                  Aplicação
                  <FieldTooltip text="Parar ao aplicar: só uma campanha por pedido. Acumular: permite somar mais de uma campanha." />
                </span>
                <select
                  className="input w-full"
                  value={form.apply_mode}
                  onChange={(e) => setForm({ ...form, apply_mode: e.target.value as FormState["apply_mode"] })}
                >
                  <option value="first">Parar ao aplicar</option>
                  <option value="stack">Acumular campanhas</option>
                </select>
              </div>
              <div className="space-y-1">
                <span className="inline-flex items-center gap-1">
                  Início
                  <FieldTooltip text="Data e hora em que a campanha passa a valer." />
                </span>
                <input
                  className="input w-full"
                  type="datetime-local"
                  value={form.starts_at}
                  onChange={(e) => setForm({ ...form, starts_at: e.target.value })}
                />
              </div>
              <div className="space-y-1">
                <span className="inline-flex items-center gap-1">
                  Fim
                  <FieldTooltip text="Data e hora em que a campanha deixa de valer." />
                </span>
                <input
                  className="input w-full"
                  type="datetime-local"
                  value={form.ends_at}
                  onChange={(e) => setForm({ ...form, ends_at: e.target.value })}
                />
              </div>

              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                />
                <span className="inline-flex items-center gap-1">
                  Ativa
                  <FieldTooltip text="Campanhas inativas não são aplicadas no checkout." />
                </span>
              </label>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Lojas</p>
                  <p className="text-xs text-slate-600">Selecione onde a campanha vale.</p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2 text-sm">
                {stores.length === 0 ? (
                  <span className="text-xs text-slate-600">Nenhuma loja cadastrada.</span>
                ) : (
                  stores.map((store) => (
                    <label key={store.id} className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1">
                      <input
                        type="checkbox"
                        checked={form.store_ids.includes(store.id)}
                        onChange={(e) => {
                          const next = e.target.checked
                            ? [...form.store_ids, store.id]
                            : form.store_ids.filter((id) => id !== store.id);
                          setForm({ ...form, store_ids: next });
                        }}
                      />
                      <span>{store.name}</span>
                    </label>
                  ))
                )}
              </div>
            </div>

            {form.type === "rule" && (
              <div ref={(r) => { formRefs.current.rule_config = r; }} className="rounded-2xl border border-slate-200 bg-slate-50 p-3 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Regras</p>
                    <p className="text-xs text-slate-600">Use E/OU nas condicoes e defina a acao.</p>
                    {fieldErrors.rule_config && <p className="text-xs text-red-600 mt-1">{fieldErrors.rule_config}</p>}
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      const next = [...form.rule_config.rules];
                      next.push({
                        name: `Regra ${next.length + 1}`,
                        conditions_logic: "E",
                        conditions: [{ dimension: "quantidade_total", operator: ">=", value: "1" }],
                        action: { type: "frete_gratis" },
                        stop_on_match: true,
                      });
                      setForm({ ...form, rule_config: { rules: next } });
                    }}
                    className="px-3 py-1 rounded-lg bg-white border border-slate-200 text-xs"
                  >
                    Adicionar regra
                  </button>
                </div>
                <div className="space-y-3">
                  {form.rule_config.rules.map((rule, ruleIndex) => (
                    <div key={`${ruleIndex}-${rule.name}`} className="rounded-2xl border border-slate-200 bg-white p-3 space-y-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <input
                          className="input text-sm w-full sm:w-auto"
                          value={rule.name}
                          onChange={(e) => {
                            const next = [...form.rule_config.rules];
                            next[ruleIndex] = { ...rule, name: e.target.value };
                            setForm({ ...form, rule_config: { rules: next } });
                          }}
                          placeholder="Nome da regra"
                        />
                        <div className="flex items-center gap-2">
                          <select
                            className="input text-xs"
                            value={rule.conditions_logic}
                            onChange={(e) => {
                              const next = [...form.rule_config.rules];
                              next[ruleIndex] = { ...rule, conditions_logic: e.target.value as CampaignRule["conditions_logic"] };
                              setForm({ ...form, rule_config: { rules: next } });
                            }}
                          >
                            <option value="E">E</option>
                            <option value="OU">OU</option>
                          </select>
                          <label className="inline-flex items-center gap-2 text-xs">
                            <input
                              type="checkbox"
                              checked={rule.stop_on_match}
                              onChange={(e) => {
                                const next = [...form.rule_config.rules];
                                next[ruleIndex] = { ...rule, stop_on_match: e.target.checked };
                                setForm({ ...form, rule_config: { rules: next } });
                              }}
                            />
                            Parar ao aplicar
                          </label>
                          <button
                            type="button"
                            onClick={() => {
                              const next = form.rule_config.rules.filter((_, idx) => idx !== ruleIndex);
                              setForm({ ...form, rule_config: { rules: next.length ? next : defaultForm.rule_config.rules } });
                            }}
                            className="text-xs text-red-600"
                          >
                            Remover
                          </button>
                        </div>
                      </div>

                      <div className="space-y-2">
                        {rule.conditions.map((condition, conditionIndex) => (
                          <div key={`${ruleIndex}-${conditionIndex}`} className="grid md:grid-cols-5 gap-2">
                            <select
                              className="input text-xs"
                              value={condition.dimension}
                              onChange={(e) => {
                                const next = [...form.rule_config.rules];
                                const updated = { ...condition, dimension: e.target.value };
                                next[ruleIndex].conditions[conditionIndex] = updated;
                                setForm({ ...form, rule_config: { rules: next } });
                              }}
                            >
                              {conditionDimensions.map((dim) => (
                                <option key={dim.value} value={dim.value}>
                                  {dim.label}
                                </option>
                              ))}
                            </select>
                            <select
                              className="input text-xs"
                              value={condition.operator}
                              onChange={(e) => {
                                const next = [...form.rule_config.rules];
                                next[ruleIndex].conditions[conditionIndex] = { ...condition, operator: e.target.value };
                                setForm({ ...form, rule_config: { rules: next } });
                              }}
                            >
                              {conditionOperators.map((op) => (
                                <option key={op.value} value={op.value}>
                                  {op.label}
                                </option>
                              ))}
                            </select>
                            {(condition.dimension === "produto" || condition.dimension === "quantidade_produto") && (
                              <select
                                className="input text-xs"
                                value={condition.product_id || ""}
                                onChange={(e) => {
                                  const next = [...form.rule_config.rules];
                                  next[ruleIndex].conditions[conditionIndex] = { ...condition, product_id: e.target.value };
                                  setForm({ ...form, rule_config: { rules: next } });
                                }}
                              >
                                <option value="">Produto...</option>
                                {products.map((product) => (
                                  <option key={product.id} value={product.id}>
                                    {product.name}
                                  </option>
                                ))}
                              </select>
                            )}
                            {condition.dimension === "categoria" && (
                              <select
                                className="input text-xs"
                                value={condition.category_id || ""}
                                onChange={(e) => {
                                  const next = [...form.rule_config.rules];
                                  next[ruleIndex].conditions[conditionIndex] = { ...condition, category_id: e.target.value };
                                  setForm({ ...form, rule_config: { rules: next } });
                                }}
                              >
                                <option value="">Categoria...</option>
                                {categories.map((c) => (
                                  <option key={c.id} value={c.id}>
                                    {c.name}
                                  </option>
                                ))}
                              </select>
                            )}
                            {condition.dimension === "tipo_entrega" && (
                              <select
                                className="input text-xs"
                                value={condition.value || ""}
                                onChange={(e) => {
                                  const next = [...form.rule_config.rules];
                                  next[ruleIndex].conditions[conditionIndex] = { ...condition, value: e.target.value };
                                  setForm({ ...form, rule_config: { rules: next } });
                                }}
                              >
                                <option value="">Selecione...</option>
                                <option value="entrega">Entrega</option>
                                <option value="retirada">Retirada</option>
                              </select>
                            )}
                            {(condition.dimension === "quantidade_total" ||
                              condition.dimension === "valor_total" ||
                              condition.dimension === "cliente" ||
                              condition.dimension === "quantidade_produto") && (
                              <input
                                className="input text-xs"
                                placeholder="Valor"
                                value={condition.value || ""}
                                onChange={(e) => {
                                  const next = [...form.rule_config.rules];
                                  next[ruleIndex].conditions[conditionIndex] = { ...condition, value: e.target.value };
                                  setForm({ ...form, rule_config: { rules: next } });
                                }}
                              />
                            )}
                            <button
                              type="button"
                              onClick={() => {
                                const next = [...form.rule_config.rules];
                                next[ruleIndex].conditions = next[ruleIndex].conditions.filter((_, idx) => idx !== conditionIndex);
                                setForm({ ...form, rule_config: { rules: next } });
                              }}
                              className="text-xs text-red-600"
                            >
                              Remover
                            </button>
                          </div>
                        ))}
                        <button
                          type="button"
                          onClick={() => {
                            const next = [...form.rule_config.rules];
                            next[ruleIndex].conditions.push({ dimension: "quantidade_total", operator: ">=", value: "1" });
                            setForm({ ...form, rule_config: { rules: next } });
                          }}
                          className="px-2 py-1 rounded bg-slate-100 border border-slate-200 text-xs"
                        >
                          Adicionar condicao
                        </button>
                      </div>

                      <div className="grid md:grid-cols-4 gap-2 items-end">
                        <label className="space-y-1">
                          <span className="text-xs">Acao</span>
                          <select
                            className="input text-xs"
                            value={rule.action.type}
                            onChange={(e) => {
                              const next = [...form.rule_config.rules];
                              next[ruleIndex] = { ...rule, action: { type: e.target.value } };
                              setForm({ ...form, rule_config: { rules: next } });
                            }}
                          >
                            {actionOptions.map((action) => (
                              <option key={action.value} value={action.value}>
                                {action.label}
                              </option>
                            ))}
                          </select>
                        </label>
                        {(rule.action.type === "desconto_total_percentual" ||
                          rule.action.type === "desconto_item_percentual" ||
                          rule.action.type === "desconto_categoria_percentual") && (
                          <label className="space-y-1">
                            <span className="text-xs">Percentual</span>
                            <input
                              className="input text-xs"
                              type="number"
                              min={0}
                              max={100}
                              value={rule.action.value_percent || ""}
                              onChange={(e) => {
                                const next = [...form.rule_config.rules];
                                next[ruleIndex] = {
                                  ...rule,
                                  action: { ...rule.action, value_percent: e.target.value },
                                };
                                setForm({ ...form, rule_config: { rules: next } });
                              }}
                            />
                          </label>
                        )}
                        {(rule.action.type === "frete_maximo" ||
                          rule.action.type === "frete_desconto" ||
                          rule.action.type === "desconto_total_fixo" ||
                          rule.action.type === "desconto_item_fixo" ||
                          rule.action.type === "desconto_categoria_fixo") && (
                          <label className="space-y-1">
                            <span className="text-xs">Valor (R$)</span>
                            <input
                              className="input text-xs"
                              type="text"
                              inputMode="decimal"
                              value={centsToInput(rule.action.value_cents || "")}
                              onChange={(e) => {
                                const next = [...form.rule_config.rules];
                                next[ruleIndex] = {
                                  ...rule,
                                  action: { ...rule.action, value_cents: String(inputToCents(e.target.value) || "") },
                                };
                                setForm({ ...form, rule_config: { rules: next } });
                              }}
                            />
                          </label>
                        )}
                        {(rule.action.type === "desconto_item_percentual" ||
                          rule.action.type === "desconto_item_fixo" ||
                          rule.action.type === "brinde_produto") && (
                          <label className="space-y-1">
                            <span className="text-xs">Produto</span>
                            <select
                              className="input text-xs"
                              value={rule.action.product_id || ""}
                              onChange={(e) => {
                                const next = [...form.rule_config.rules];
                                next[ruleIndex] = {
                                  ...rule,
                                  action: { ...rule.action, product_id: e.target.value },
                                };
                                setForm({ ...form, rule_config: { rules: next } });
                              }}
                            >
                              <option value="">Selecione...</option>
                              {products.map((product) => (
                                <option key={product.id} value={product.id}>
                                  {product.name}
                                </option>
                              ))}
                            </select>
                          </label>
                        )}
                        {(rule.action.type === "desconto_categoria_percentual" ||
                          rule.action.type === "desconto_categoria_fixo") && (
                          <label className="space-y-1">
                            <span className="text-xs">Categoria</span>
                            <select
                              className="input text-xs"
                              value={rule.action.category_id || ""}
                              onChange={(e) => {
                                const next = [...form.rule_config.rules];
                                next[ruleIndex] = {
                                  ...rule,
                                  action: { ...rule.action, category_id: e.target.value },
                                };
                                setForm({ ...form, rule_config: { rules: next } });
                              }}
                            >
                              <option value="">Selecione...</option>
                              {categories.map((c) => (
                                <option key={c.id} value={c.id}>
                                  {c.name}
                                </option>
                              ))}
                            </select>
                          </label>
                        )}
                        {rule.action.type === "brinde_produto" && (
                          <label className="space-y-1">
                            <span className="text-xs">Quantidade</span>
                            <input
                              className="input text-xs"
                              type="number"
                              min={1}
                              value={rule.action.gift_qty || "1"}
                              onChange={(e) => {
                                const next = [...form.rule_config.rules];
                                next[ruleIndex] = {
                                  ...rule,
                                  action: { ...rule.action, gift_qty: e.target.value },
                                };
                                setForm({ ...form, rule_config: { rules: next } });
                              }}
                            />
                          </label>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div ref={(el) => { fieldRefs.current.banner = el; }} className="rounded-2xl border border-slate-200 bg-slate-50 p-3 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Banner</p>
                  <p className="text-xs text-slate-600">Dimensões recomendadas: {BANNER_WIDTH}×{BANNER_HEIGHT} px (proporção 3:1). JPG, PNG ou WebP até 5MB.</p>
                </div>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={form.banner_enabled}
                    onChange={(e) => {
                      const enabled = e.target.checked;
                      setForm({
                        ...form,
                        banner_enabled: enabled,
                        banner_popup: enabled ? form.banner_popup : false,
                      });
                    }}
                  />
                  <span>Ativar banner</span>
                </label>
              </div>
              {form.banner_enabled && (
                <div className="grid md:grid-cols-2 gap-3 text-sm">
                  <label className="space-y-1 md:col-span-2">
                    <span className="inline-flex items-center gap-2 flex-wrap">
                      Imagem do banner
                      <span className="text-xs font-normal text-slate-500">(1200 × 400 px)</span>
                    </span>
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      className="input w-full"
                      onChange={(e) => {
                        const file = e.target.files?.[0] ?? null;
                        if (bannerPreview?.startsWith("blob:")) {
                          URL.revokeObjectURL(bannerPreview);
                        }
                        if (file) {
                          setFileToCrop(file);
                          setShowCropModal(true);
                          setRemoveBanner(false);
                        } else {
                          setBannerFile(null);
                          setBannerPreview(currentBannerUrl);
                        }
                      }}
                    />
                    <span className="text-xs text-slate-500">JPG, PNG ou WebP até 5MB. Após selecionar, ajuste o enquadramento às dimensões da plataforma.</span>
                  </label>
                  {showCropModal && fileToCrop && (
                    <BannerCropModal
                      file={fileToCrop}
                      onConfirm={(croppedFile) => {
                        setBannerFile(croppedFile);
                        setBannerPreview(URL.createObjectURL(croppedFile));
                        setForm((f) => ({ ...f, banner_enabled: true }));
                        setFileToCrop(null);
                        setShowCropModal(false);
                      }}
                      onCancel={() => {
                        setFileToCrop(null);
                        setShowCropModal(false);
                      }}
                    />
                  )}
                  {bannerPreview && (
                    <div className="md:col-span-2 space-y-2">
                      <p className="text-xs font-medium text-slate-600">Pré-visualização (ajuste a posição antes de salvar)</p>
                      <div
                        className="w-full rounded-xl overflow-hidden border border-slate-200 bg-slate-100"
                        style={{ aspectRatio: BANNER_ASPECT }}
                      >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={bannerPreview}
                          alt="Banner"
                          className="w-full h-full object-cover object-center"
                          style={{ objectPosition: `50% ${bannerPositionY}%` }}
                        />
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-slate-500">Posição vertical:</span>
                        <input
                          type="range"
                          min={0}
                          max={100}
                          value={bannerPositionY}
                          onChange={(e) => setBannerPositionY(Number(e.target.value))}
                          className="flex-1 max-w-xs"
                        />
                        <span className="text-xs text-slate-600 w-8">{bannerPositionY}%</span>
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          if (bannerPreview.startsWith("blob:")) {
                            URL.revokeObjectURL(bannerPreview);
                          }
                          setBannerFile(null);
                          setBannerPreview(null);
                          setCurrentBannerUrl(null);
                          setRemoveBanner(true);
                          setForm({ ...form, banner_enabled: false, banner_popup: false });
                        }}
                        className="px-3 py-2 rounded-lg border border-slate-200 text-sm hover:bg-slate-100"
                      >
                        Remover imagem
                      </button>
                    </div>
                  )}
                  <label className="space-y-1">
                    <span>Posicao</span>
                    <select
                      className="input w-full"
                      value={form.banner_position}
                      onChange={(e) =>
                        setForm({ ...form, banner_position: e.target.value as FormState["banner_position"] })
                      }
                    >
                      <option value="top">Topo da pagina</option>
                      <option value="between">Entre categorias</option>
                    </select>
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={form.banner_popup}
                      onChange={(e) => setForm({ ...form, banner_popup: e.target.checked })}
                    />
                    <span>Popup na primeira visita</span>
                  </label>
                  <label className="space-y-1">
                    <span className="inline-flex items-center gap-1">
                      Ordem de exibição
                      <FieldTooltip text="Número que define a ordem dos banners (menor aparece primeiro). Usado no carrossel e na fila de popups." />
                    </span>
                    <input
                      className="input w-full"
                      type="number"
                      min={0}
                      value={form.banner_display_order}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          banner_display_order: Math.max(0, Number(e.target.value) || 0),
                        })
                      }
                    />
                  </label>
                </div>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <button
                onClick={save}
                className="px-4 py-2 rounded-lg bg-[#6320ee] text-white font-semibold hover:brightness-95 active:scale-95 disabled:opacity-60"
                disabled={saving}
              >
                {saving ? "Salvando..." : editingId ? "Atualizar campanha" : "Criar campanha"}
              </button>
              {editingId && (
                <button
                  onClick={() => {
                    setForm(defaultForm);
                    setEditingId(null);
                  }}
                  className="px-4 py-2 rounded-lg bg-neutral-100 border border-neutral-200 text-sm"
                  disabled={saving}
                >
                  Cancelar edicao
                </button>
              )}
            </div>
          </section>
        </div>
      )}
    </main>
  );
}




