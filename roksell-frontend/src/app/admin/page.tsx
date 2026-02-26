"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useSuperAdminGuard } from "@/lib/use-super-admin-guard";
import { adminFetch } from "@/lib/admin-api";
import Link from "next/link";

const MODULE_LABELS: Record<string, string> = {
  inventory: "Estoque",
  stores: "Cadastro de lojas",
  campaigns: "Campanhas",
  insights: "Insights",
  messages: "Mensagens",
};

const STATUS_OPTIONS = ["active", "suspended", "canceled"] as const;

const DEFAULT_TENANT_FORM = {
  name: "",
  slug: "",
  status: "active",
  users_limit: 5,
  stores_limit: "",
  legal_name: "",
  trade_name: "",
  state_registration: "",
  municipal_registration: "",
  contact_name: "",
  contact_email: "",
  contact_phone: "",
  financial_contact_name: "",
  financial_contact_email: "",
  financial_contact_phone: "",
  billing_postal_code: "",
  billing_street: "",
  billing_number: "",
  billing_district: "",
  billing_city: "",
  billing_state: "",
  billing_complement: "",
  onboarding_origin: "admin_manual",
  activation_mode: "manual",
  payment_provider: "",
  payment_reference: "",
  activation_notes: "",
  signup_payload_text: "",
  activated_at: "",
  person_type: "company",
  document: "",
  payment_link_enabled: false,
  payment_link_config_text: "",
};

const DEFAULT_USER_FORM = {
  name: "",
  email: "",
  password: "",
  role: "owner",
  max_active_sessions: 3,
};

type TenantSummary = {
  id: string;
  name: string;
  slug: string;
  status: string;
  users_limit: number;
  stores_limit?: number | null;
  legal_name?: string | null;
  trade_name?: string | null;
  state_registration?: string | null;
  municipal_registration?: string | null;
  contact_name?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  financial_contact_name?: string | null;
  financial_contact_email?: string | null;
  financial_contact_phone?: string | null;
  billing_postal_code?: string | null;
  billing_street?: string | null;
  billing_number?: string | null;
  billing_district?: string | null;
  billing_city?: string | null;
  billing_state?: string | null;
  billing_complement?: string | null;
  onboarding_origin?: string | null;
  activation_mode?: string | null;
  payment_provider?: string | null;
  payment_reference?: string | null;
  activation_notes?: string | null;
  signup_payload?: Record<string, unknown> | null;
  activated_at?: string | null;
  users_count: number;
  stores_count: number;
  created_at: string;
  person_type?: string | null;
  document?: string | null;
  payment_link_enabled?: boolean;
  payment_link_config?: Record<string, unknown> | null;
};

type TenantForm = {
  name: string;
  slug: string;
  status: string;
  users_limit: number;
  stores_limit: string;
  legal_name: string;
  trade_name: string;
  state_registration: string;
  municipal_registration: string;
  contact_name: string;
  contact_email: string;
  contact_phone: string;
  financial_contact_name: string;
  financial_contact_email: string;
  financial_contact_phone: string;
  billing_postal_code: string;
  billing_street: string;
  billing_number: string;
  billing_district: string;
  billing_city: string;
  billing_state: string;
  billing_complement: string;
  onboarding_origin: string;
  activation_mode: string;
  payment_provider: string;
  payment_reference: string;
  activation_notes: string;
  signup_payload_text: string;
  activated_at: string;
  person_type: string;
  document: string;
  payment_link_enabled: boolean;
  payment_link_config_text: string;
};

type TenantUser = {
  id: string;
  name: string;
  email: string;
  role: string;
  is_active: boolean;
  max_active_sessions?: number;
  default_store_id?: string | null;
};

type UserForm = {
  name: string;
  email: string;
  password: string;
  role: string;
  max_active_sessions: number;
};

type MessagingConfig = {
  whatsapp_enabled: boolean;
  whatsapp_token: string;
  whatsapp_phone_number_id: string;
  telegram_enabled: boolean;
  telegram_bot_token: string;
  telegram_chat_id: string;
};

type PlanSummary = {
  id: string;
  name: string;
  description?: string | null;
  is_active: boolean;
  modules: string[];
};

type TenantPlan = {
  plan_id?: string | null;
  plan_name?: string | null;
  status?: string | null;
  modules: string[];
};

type CentralDashboard = {
  active_tenants_count: number;
  active_users_now_count: number;
  active_stores_count: number;
  orders_today_count: number;
  orders_month_count: number;
};

export default function AdminCentral() {
  const ready = useSuperAdminGuard();
  const [tenants, setTenants] = useState<TenantSummary[]>([]);
  const [plans, setPlans] = useState<PlanSummary[]>([]);
  const [selectedTenant, setSelectedTenant] = useState<TenantSummary | null>(null);
  const [tenantForm, setTenantForm] = useState<TenantForm>(DEFAULT_TENANT_FORM);
  const [selectedPlanId, setSelectedPlanId] = useState<string>("");
  const [selectedPlanModules, setSelectedPlanModules] = useState<string[]>([]);
  const [messagingConfig, setMessagingConfig] = useState<MessagingConfig>({
    whatsapp_enabled: false,
    whatsapp_token: "",
    whatsapp_phone_number_id: "",
    telegram_enabled: false,
    telegram_bot_token: "",
    telegram_chat_id: "",
  });
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tenantModalOpen, setTenantModalOpen] = useState(false);

  const [usersModalOpen, setUsersModalOpen] = useState(false);
  const [users, setUsers] = useState<TenantUser[]>([]);
  const [userForm, setUserForm] = useState<UserForm>(DEFAULT_USER_FORM);
  const [userEditingId, setUserEditingId] = useState<string | null>(null);
  const [firstAccessTestLoading, setFirstAccessTestLoading] = useState(false);
  const [dashboard, setDashboard] = useState<CentralDashboard | null>(null);
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [showCustomersSection, setShowCustomersSection] = useState(false);
  const customersSectionRef = useRef<HTMLElement | null>(null);

  function toLocalDateTimeInput(value?: string | null): string {
    if (!value) return "";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return "";
    const shifted = new Date(parsed.getTime() - parsed.getTimezoneOffset() * 60000);
    return shifted.toISOString().slice(0, 16);
  }

  useEffect(() => {
    if (ready) {
      loadTenants();
      loadPlans();
      loadDashboard();
    }
  }, [ready]);

  useEffect(() => {
    if (!showCustomersSection) return;
    customersSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [showCustomersSection]);

  const filteredTenants = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return tenants;
    return tenants.filter((tenant) => [tenant.name, tenant.slug].some((v) => v.toLowerCase().includes(q)));
  }, [search, tenants]);

  async function loadTenants() {
    setLoading(true);
    setError(null);
    try {
      const data = await adminFetch<TenantSummary[]>("/admin/central/tenants");
      setTenants(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar empresas");
    } finally {
      setLoading(false);
    }
  }

  async function loadPlans() {
    try {
      const data = await adminFetch<PlanSummary[]>("/admin/central/plans");
      setPlans(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar planos");
    }
  }

  async function loadDashboard() {
    setDashboardLoading(true);
    try {
      const data = await adminFetch<CentralDashboard>("/admin/central/dashboard");
      setDashboard(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar dashboard");
    } finally {
      setDashboardLoading(false);
    }
  }

  function openTenantModal(tenant?: TenantSummary) {
    if (tenant) {
      setSelectedTenant(tenant);
      setTenantForm({
        name: tenant.name,
        slug: tenant.slug,
        status: tenant.status ?? "active",
        users_limit: tenant.users_limit,
        stores_limit: tenant.stores_limit ? String(tenant.stores_limit) : "",
        legal_name: tenant.legal_name ?? "",
        trade_name: tenant.trade_name ?? "",
        state_registration: tenant.state_registration ?? "",
        municipal_registration: tenant.municipal_registration ?? "",
        contact_name: tenant.contact_name ?? "",
        contact_email: tenant.contact_email ?? "",
        contact_phone: tenant.contact_phone ?? "",
        financial_contact_name: tenant.financial_contact_name ?? "",
        financial_contact_email: tenant.financial_contact_email ?? "",
        financial_contact_phone: tenant.financial_contact_phone ?? "",
        billing_postal_code: tenant.billing_postal_code ?? "",
        billing_street: tenant.billing_street ?? "",
        billing_number: tenant.billing_number ?? "",
        billing_district: tenant.billing_district ?? "",
        billing_city: tenant.billing_city ?? "",
        billing_state: tenant.billing_state ?? "",
        billing_complement: tenant.billing_complement ?? "",
        onboarding_origin: tenant.onboarding_origin ?? "admin_manual",
        activation_mode: tenant.activation_mode ?? "manual",
        payment_provider: tenant.payment_provider ?? "",
        payment_reference: tenant.payment_reference ?? "",
        activation_notes: tenant.activation_notes ?? "",
        signup_payload_text: tenant.signup_payload ? JSON.stringify(tenant.signup_payload, null, 2) : "",
        activated_at: toLocalDateTimeInput(tenant.activated_at),
        person_type: tenant.person_type ?? "company",
        document: tenant.document ?? "",
        payment_link_enabled: tenant.payment_link_enabled ?? false,
        payment_link_config_text: tenant.payment_link_config
          ? JSON.stringify(tenant.payment_link_config, null, 2)
          : "",
      });
      loadTenantPlan(tenant.slug);
      loadMessagingConfig(tenant.slug);
    } else {
      setSelectedTenant(null);
      setTenantForm(DEFAULT_TENANT_FORM);
      setSelectedPlanId("");
      setSelectedPlanModules([]);
      setMessagingConfig({
        whatsapp_enabled: false,
        whatsapp_token: "",
        whatsapp_phone_number_id: "",
        telegram_enabled: false,
        telegram_bot_token: "",
        telegram_chat_id: "",
      });
    }
    setTenantModalOpen(true);
  }

  function closeTenantModal() {
    setTenantModalOpen(false);
    setSelectedTenant(null);
    setStatusMessage(null);
    setError(null);
  }

  async function loadTenantPlan(slug: string) {
    try {
      const res = await adminFetch<TenantPlan>(`/admin/central/tenants/${slug}/plan`);
      const planId = res.plan_id ?? "";
      setSelectedPlanId(planId);
      setSelectedPlanModules(res.modules ?? []);
    } catch {
      setSelectedPlanId("");
      setSelectedPlanModules([]);
    }
  }

  async function loadMessagingConfig(slug: string) {
    try {
      const res = await adminFetch<MessagingConfig>(`/admin/central/tenants/${slug}/messaging`);
      setMessagingConfig({
        whatsapp_enabled: !!res.whatsapp_enabled,
        whatsapp_token: res.whatsapp_token || "",
        whatsapp_phone_number_id: res.whatsapp_phone_number_id || "",
        telegram_enabled: !!res.telegram_enabled,
        telegram_bot_token: res.telegram_bot_token || "",
        telegram_chat_id: res.telegram_chat_id || "",
      });
    } catch {
      setMessagingConfig({
        whatsapp_enabled: false,
        whatsapp_token: "",
        whatsapp_phone_number_id: "",
        telegram_enabled: false,
        telegram_bot_token: "",
        telegram_chat_id: "",
      });
    }
  }

  async function saveTenant(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setStatusMessage(null);
    setError(null);
    try {
      let paymentLinkConfig: Record<string, unknown> | null = null;
      let signupPayload: Record<string, unknown> | null = null;
      const configText = tenantForm.payment_link_config_text.trim();
      if (configText) {
        try {
          const parsed = JSON.parse(configText);
          if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
            paymentLinkConfig = parsed;
          } else {
            setError("ConfiguraÃ§Ã£o do link deve ser um objeto JSON.");
            setLoading(false);
            return;
          }
        } catch {
          setError("ConfiguraÃ§Ã£o do link deve ser um JSON vÃ¡lido.");
          setLoading(false);
          return;
        }
      }

      const signupText = tenantForm.signup_payload_text.trim();
      if (signupText) {
        try {
          const parsed = JSON.parse(signupText);
          if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
            signupPayload = parsed;
          } else {
            setError("Payload de cadastro deve ser um objeto JSON.");
            setLoading(false);
            return;
          }
        } catch {
          setError("Payload de cadastro deve ser um JSON valido.");
          setLoading(false);
          return;
        }
      }

      let activatedAt: string | null = null;
      if (tenantForm.activated_at.trim()) {
        const parsed = new Date(tenantForm.activated_at.trim());
        if (Number.isNaN(parsed.getTime())) {
          setError("Data/hora de ativacao invalida.");
          setLoading(false);
          return;
        }
        activatedAt = parsed.toISOString();
      }

      const billingPostalDigits = tenantForm.billing_postal_code.replace(/\D/g, "");
      if (billingPostalDigits && billingPostalDigits.length !== 8) {
        setError("CEP de cobranca deve ter 8 digitos.");
        setLoading(false);
        return;
      }

      const payload = {
        name: tenantForm.name.trim(),
        slug: tenantForm.slug.trim().toLowerCase(),
        status: tenantForm.status,
        users_limit: Number(tenantForm.users_limit),
        stores_limit: tenantForm.stores_limit ? Number(tenantForm.stores_limit) : null,
        legal_name: tenantForm.legal_name.trim() || null,
        trade_name: tenantForm.trade_name.trim() || null,
        state_registration: tenantForm.state_registration.trim() || null,
        municipal_registration: tenantForm.municipal_registration.trim() || null,
        contact_name: tenantForm.contact_name.trim() || null,
        contact_email: tenantForm.contact_email.trim() || null,
        contact_phone: tenantForm.contact_phone.trim() || null,
        financial_contact_name: tenantForm.financial_contact_name.trim() || null,
        financial_contact_email: tenantForm.financial_contact_email.trim() || null,
        financial_contact_phone: tenantForm.financial_contact_phone.trim() || null,
        billing_postal_code: billingPostalDigits || null,
        billing_street: tenantForm.billing_street.trim() || null,
        billing_number: tenantForm.billing_number.trim() || null,
        billing_district: tenantForm.billing_district.trim() || null,
        billing_city: tenantForm.billing_city.trim() || null,
        billing_state: tenantForm.billing_state.trim() || null,
        billing_complement: tenantForm.billing_complement.trim() || null,
        onboarding_origin: tenantForm.onboarding_origin.trim() || null,
        activation_mode: tenantForm.activation_mode.trim() || null,
        payment_provider: tenantForm.payment_provider.trim() || null,
        payment_reference: tenantForm.payment_reference.trim() || null,
        activation_notes: tenantForm.activation_notes.trim() || null,
        signup_payload: signupPayload,
        activated_at: activatedAt,
        person_type: tenantForm.person_type,
        document: tenantForm.document.trim() || null,
        payment_link_enabled: tenantForm.payment_link_enabled,
        payment_link_config: paymentLinkConfig,
      };

      const targetSlug = payload.slug;

      if (selectedTenant) {
        await adminFetch(`/admin/central/tenants/${selectedTenant.slug}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
      } else {
        await adminFetch(`/admin/central/tenants`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }

      if (selectedPlanId) {
        await adminFetch(`/admin/central/tenants/${targetSlug}/plan`, {
          method: "PUT",
          body: JSON.stringify({ plan_id: selectedPlanId }),
        });
      }

      if (selectedPlanModules.includes("messages")) {
        await adminFetch(`/admin/central/tenants/${targetSlug}/messaging`, {
          method: "PATCH",
          body: JSON.stringify({
            whatsapp_enabled: messagingConfig.whatsapp_enabled,
            whatsapp_token: messagingConfig.whatsapp_token,
            whatsapp_phone_number_id: messagingConfig.whatsapp_phone_number_id,
            telegram_enabled: messagingConfig.telegram_enabled,
            telegram_bot_token: messagingConfig.telegram_bot_token,
            telegram_chat_id: messagingConfig.telegram_chat_id,
          }),
        });
      }

      setStatusMessage("Empresa salva com sucesso.");
      await loadTenants();
      if (selectedTenant) {
        const refreshed = await adminFetch<TenantSummary[]>("/admin/central/tenants");
        const updated = refreshed.find((item) => item.slug === targetSlug) ?? null;
        setSelectedTenant(updated);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar empresa");
    } finally {
      setLoading(false);
    }
  }

  function openUsersModal(tenant: TenantSummary) {
    setSelectedTenant(tenant);
    setUsersModalOpen(true);
    setUserForm(DEFAULT_USER_FORM);
    setUserEditingId(null);
    loadUsers(tenant.slug);
  }

  function closeUsersModal() {
    setUsersModalOpen(false);
    setUsers([]);
    setUserForm(DEFAULT_USER_FORM);
    setUserEditingId(null);
    setFirstAccessTestLoading(false);
  }

  async function loadUsers(slug: string) {
    setLoading(true);
    try {
      const data = await adminFetch<TenantUser[]>(`/admin/central/tenants/${slug}/users`);
      setUsers(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar usuarios");
    } finally {
      setLoading(false);
    }
  }

  function startEditUser(user: TenantUser) {
    setUserEditingId(user.id);
    setUserForm({
      name: user.name,
      email: user.email,
      password: "",
      role: user.role,
      max_active_sessions: user.max_active_sessions ?? 3,
    });
  }

  async function saveUser(e: FormEvent) {
    e.preventDefault();
    if (!selectedTenant) return;
    if (!Number.isInteger(userForm.max_active_sessions) || userForm.max_active_sessions < 1 || userForm.max_active_sessions > 20) {
      setError("Limite de sessoes deve ser entre 1 e 20.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      if (userEditingId) {
        await adminFetch(`/admin/central/tenants/${selectedTenant.slug}/users/${userEditingId}`, {
          method: "PATCH",
          body: JSON.stringify({
            name: userForm.name.trim(),
            email: userForm.email.trim(),
            role: userForm.role,
            max_active_sessions: userForm.max_active_sessions,
            password: userForm.password || null,
          }),
        });
      } else {
        await adminFetch(`/admin/central/tenants/${selectedTenant.slug}/users`, {
          method: "POST",
          body: JSON.stringify({
            name: userForm.name.trim(),
            email: userForm.email.trim(),
            password: userForm.password,
            role: userForm.role,
            max_active_sessions: userForm.max_active_sessions,
          }),
        });
      }
      setUserForm(DEFAULT_USER_FORM);
      setUserEditingId(null);
      await loadUsers(selectedTenant.slug);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar usuario");
    } finally {
      setLoading(false);
    }
  }

  async function toggleUser(user: TenantUser) {
    if (!selectedTenant) return;
    setLoading(true);
    try {
      await adminFetch(`/admin/central/tenants/${selectedTenant.slug}/users/${user.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !user.is_active }),
      });
      await loadUsers(selectedTenant.slug);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao atualizar status");
    } finally {
      setLoading(false);
    }
  }

  async function enableFirstAccessTestForTenant() {
    if (!selectedTenant) return;
    setFirstAccessTestLoading(true);
    setError(null);
    try {
      await adminFetch(`/admin/central/tenants/${selectedTenant.slug}/onboarding-test-enable`, {
        method: "POST",
      });
      setStatusMessage(
        `Primeiro acesso de teste habilitado para ${selectedTenant.slug}. Faça login no portal desse tenant para validar.`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao habilitar primeiro acesso para teste");
    } finally {
      setFirstAccessTestLoading(false);
    }
  }

  if (!ready) return null;

  const messagesEnabled = selectedPlanModules.includes("messages");

  return (
    <main className="min-h-screen bg-[#f5f3ff] text-slate-900">
      <div className="max-w-6xl w-full mx-auto px-6 py-10 space-y-8">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-2">
            <p className="text-xs uppercase tracking-[0.26em] text-slate-500">Admin central</p>
            <h1 className="text-3xl font-semibold">Painel administrativo</h1>
            <p className="text-sm text-slate-600">
              Visao geral da plataforma e atalhos para gerenciamento.
            </p>
          </div>
        </header>

        {statusMessage && <p className="text-sm text-emerald-700">{statusMessage}</p>}
        {error && <p className="text-sm text-red-600">{error}</p>}

        <section className="rounded-3xl bg-white border border-slate-200 shadow-sm shadow-slate-200/60 p-6 space-y-4">
          <div className="space-y-1">
            <h2 className="text-xl font-semibold">Insights</h2>
            <p className="text-sm text-slate-600">Indicadores principais do ambiente administrativo.</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {[
              {
                label: "Clientes ativos",
                value: dashboard?.active_tenants_count,
                helper: "Empresas com status ativo",
              },
              {
                label: "Usuarios ativos agora",
                value: dashboard?.active_users_now_count,
                helper: "Ultimos 15 minutos",
              },
              {
                label: "Lojas ativas",
                value: dashboard?.active_stores_count,
                helper: "Lojas habilitadas",
              },
              {
                label: "Pedidos hoje",
                value: dashboard?.orders_today_count,
                helper: "Inseridos no dia atual",
              },
              {
                label: "Pedidos no mes",
                value: dashboard?.orders_month_count,
                helper: "Inseridos no mes atual",
              },
            ].map((card) => (
              <article key={card.label} className="rounded-2xl border border-slate-200 bg-slate-50 p-4 space-y-1">
                <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{card.label}</p>
                <p className="text-2xl font-semibold text-slate-900">
                  {dashboardLoading ? "..." : card.value ?? 0}
                </p>
                <p className="text-xs text-slate-500">{card.helper}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="rounded-3xl bg-white border border-slate-200 shadow-sm shadow-slate-200/60 p-6 space-y-4">
          <div className="space-y-1">
            <h2 className="text-xl font-semibold">Menus de cadastro</h2>
            <p className="text-sm text-slate-600">Acesse rapidamente os modulos principais.</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <button
              type="button"
              onClick={() => setShowCustomersSection(true)}
              className="rounded-2xl border border-slate-200 bg-slate-50 p-4 min-h-[130px] text-center flex flex-col items-center justify-center hover:border-[#6320ee]/40 hover:bg-[#f5f0ff] transition"
            >
              <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Clientes</p>
              <p className="text-lg font-semibold text-slate-900">Cadastro de clientes</p>
              <p className="text-xs text-slate-600">Gerencie empresas, limites, modulos e usuarios.</p>
            </button>
            <Link
              href="/admin/planos"
              className="rounded-2xl border border-slate-200 bg-slate-50 p-4 min-h-[130px] text-center flex flex-col items-center justify-center hover:border-[#6320ee]/40 hover:bg-[#f5f0ff] transition"
            >
              <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Planos</p>
              <p className="text-lg font-semibold text-slate-900">Cadastro e configuracao de planos</p>
              <p className="text-xs text-slate-600">Defina modulos e disponibilidade de cada plano.</p>
            </Link>
          </div>
        </section>

        {showCustomersSection && (
        <section
          id="clientes-cadastro"
          ref={customersSectionRef}
          className="rounded-3xl bg-white border border-slate-200 shadow-sm shadow-slate-200/60 p-6 space-y-4"
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold">Empresas</h2>
              <p className="text-sm text-slate-600">Clique para editar e gerenciar usuarios.</p>
            </div>
            <div className="flex items-center gap-3">
              <input
                className="input w-60"
                placeholder="Buscar empresa..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <button
                onClick={() => openTenantModal()}
                className="px-4 py-2 rounded-lg bg-[#6320ee] text-white font-semibold"
              >
                Nova empresa
              </button>
            </div>
          </div>

          <div className="overflow-hidden rounded-2xl border border-slate-200 bg-slate-50">
            <table className="w-full text-sm">
              <thead className="bg-slate-100 text-left text-slate-700">
                <tr>
                  <th className="px-4 py-2">Empresa</th>
                  <th className="px-4 py-2">Slug</th>
                  <th className="px-4 py-2">Status</th>
                  <th className="px-4 py-2">Usuarios</th>
                  <th className="px-4 py-2">Lojas</th>
                  <th className="px-4 py-2 text-right">Acoes</th>
                </tr>
              </thead>
              <tbody>
                {filteredTenants.length === 0 ? (
                  <tr>
                    <td className="px-4 py-4 text-center text-slate-600" colSpan={6}>
                      Nenhuma empresa encontrada.
                    </td>
                  </tr>
                ) : (
                  filteredTenants.map((tenant, idx) => (
                    <tr key={tenant.id} className={idx % 2 === 0 ? "bg-transparent" : "bg-slate-50"}>
                      <td className="px-4 py-3">
                        <div className="font-semibold">{tenant.name}</div>
                        <div className="text-xs text-slate-500">
                          Criada em {new Date(tenant.created_at).toLocaleDateString("pt-BR")}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-slate-600">{tenant.slug}</td>
                      <td className="px-4 py-3">
                        <span
                          className={`text-[11px] px-2 py-1 rounded-full border ${
                            tenant.status === "active"
                              ? "bg-emerald-200 border-emerald-300 text-emerald-900"
                              : "bg-amber-200 border-amber-300 text-amber-900"
                          }`}
                        >
                          {tenant.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-700">
                        {tenant.users_count}/{tenant.users_limit}
                      </td>
                      <td className="px-4 py-3 text-slate-700">
                        {tenant.stores_limit ? `${tenant.stores_count}/${tenant.stores_limit}` : tenant.stores_count}
                      </td>
                      <td className="px-4 py-3 text-right space-x-2">
                        <button
                          onClick={() => openTenantModal(tenant)}
                          className="px-3 py-1 rounded-lg border border-slate-200 text-sm hover:bg-slate-100"
                        >
                          Editar
                        </button>
                        <button
                          onClick={() => openUsersModal(tenant)}
                          className="px-3 py-1 rounded-lg bg-[#6320ee] text-white text-sm"
                        >
                          Usuarios
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
        )}
      </div>

      {tenantModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/90 backdrop-blur-sm px-4">
          <div className="w-full max-w-3xl max-h-[90vh] overflow-y-auto rounded-3xl bg-white border border-slate-200 shadow-2xl shadow-slate-200/80 p-6 space-y-5 text-slate-900">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Empresa</p>
                <h2 className="text-2xl font-semibold">
                  {selectedTenant ? "Editar empresa" : "Nova empresa"}
                </h2>
              </div>
              <button
                onClick={closeTenantModal}
                className="text-sm px-3 py-1 rounded-full bg-slate-100 border border-slate-200 hover:bg-slate-200"
              >
                Fechar
              </button>
            </div>

            <form onSubmit={saveTenant} className="space-y-4">
              <div className="grid md:grid-cols-2 gap-4 text-sm">
                <label className="space-y-1">
                  <span>Nome da empresa</span>
                  <input
                    className="input w-full"
                    value={tenantForm.name}
                    onChange={(e) => setTenantForm({ ...tenantForm, name: e.target.value })}
                    required
                  />
                </label>
                <label className="space-y-1">
                  <span>Slug</span>
                  <input
                    className="input w-full"
                    value={tenantForm.slug}
                    onChange={(e) => setTenantForm({ ...tenantForm, slug: e.target.value })}
                    required
                  />
                </label>
                <label className="space-y-1">
                  <span>Status</span>
                  <select
                    className="input w-full"
                    value={tenantForm.status}
                    onChange={(e) => setTenantForm({ ...tenantForm, status: e.target.value })}
                  >
                    {STATUS_OPTIONS.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="space-y-1">
                  <span>Limite de usuarios</span>
                  <input
                    type="number"
                    min={1}
                    className="input w-full"
                    value={tenantForm.users_limit}
                    onChange={(e) => setTenantForm({ ...tenantForm, users_limit: Number(e.target.value) })}
                    required
                  />
                </label>
                <label className="space-y-1">
                  <span>Limite de lojas</span>
                  <input
                    type="number"
                    min={1}
                    className="input w-full"
                    value={tenantForm.stores_limit}
                    onChange={(e) => setTenantForm({ ...tenantForm, stores_limit: e.target.value })}
                    placeholder="Sem limite"
                  />
                </label>
                <label className="space-y-1">
                  <span>Razao social</span>
                  <input
                    className="input w-full"
                    value={tenantForm.legal_name}
                    onChange={(e) => setTenantForm({ ...tenantForm, legal_name: e.target.value })}
                  />
                </label>
                <label className="space-y-1">
                  <span>Nome fantasia</span>
                  <input
                    className="input w-full"
                    value={tenantForm.trade_name}
                    onChange={(e) => setTenantForm({ ...tenantForm, trade_name: e.target.value })}
                  />
                </label>
                <label className="space-y-1">
                  <span>Inscricao estadual</span>
                  <input
                    className="input w-full"
                    value={tenantForm.state_registration}
                    onChange={(e) => setTenantForm({ ...tenantForm, state_registration: e.target.value })}
                  />
                </label>
                <label className="space-y-1">
                  <span>Inscricao municipal</span>
                  <input
                    className="input w-full"
                    value={tenantForm.municipal_registration}
                    onChange={(e) => setTenantForm({ ...tenantForm, municipal_registration: e.target.value })}
                  />
                </label>
                <label className="space-y-1">
                  <span>Contato principal</span>
                  <input
                    className="input w-full"
                    value={tenantForm.contact_name}
                    onChange={(e) => setTenantForm({ ...tenantForm, contact_name: e.target.value })}
                  />
                </label>
                <label className="space-y-1">
                  <span>Email principal</span>
                  <input
                    type="email"
                    className="input w-full"
                    value={tenantForm.contact_email}
                    onChange={(e) => setTenantForm({ ...tenantForm, contact_email: e.target.value })}
                  />
                </label>
                <label className="space-y-1">
                  <span>Telefone principal</span>
                  <input
                    className="input w-full"
                    value={tenantForm.contact_phone}
                    onChange={(e) => setTenantForm({ ...tenantForm, contact_phone: e.target.value })}
                  />
                </label>
                <label className="space-y-1">
                  <span>Contato financeiro</span>
                  <input
                    className="input w-full"
                    value={tenantForm.financial_contact_name}
                    onChange={(e) => setTenantForm({ ...tenantForm, financial_contact_name: e.target.value })}
                  />
                </label>
                <label className="space-y-1">
                  <span>Email financeiro</span>
                  <input
                    type="email"
                    className="input w-full"
                    value={tenantForm.financial_contact_email}
                    onChange={(e) =>
                      setTenantForm({ ...tenantForm, financial_contact_email: e.target.value })
                    }
                  />
                </label>
                <label className="space-y-1">
                  <span>Telefone financeiro</span>
                  <input
                    className="input w-full"
                    value={tenantForm.financial_contact_phone}
                    onChange={(e) =>
                      setTenantForm({ ...tenantForm, financial_contact_phone: e.target.value })
                    }
                  />
                </label>
                <label className="space-y-1">
                  <span>CEP cobranca</span>
                  <input
                    className="input w-full"
                    value={tenantForm.billing_postal_code}
                    onChange={(e) => setTenantForm({ ...tenantForm, billing_postal_code: e.target.value })}
                  />
                </label>
                <label className="space-y-1">
                  <span>Rua cobranca</span>
                  <input
                    className="input w-full"
                    value={tenantForm.billing_street}
                    onChange={(e) => setTenantForm({ ...tenantForm, billing_street: e.target.value })}
                  />
                </label>
                <label className="space-y-1">
                  <span>Numero cobranca</span>
                  <input
                    className="input w-full"
                    value={tenantForm.billing_number}
                    onChange={(e) => setTenantForm({ ...tenantForm, billing_number: e.target.value })}
                  />
                </label>
                <label className="space-y-1">
                  <span>Bairro cobranca</span>
                  <input
                    className="input w-full"
                    value={tenantForm.billing_district}
                    onChange={(e) => setTenantForm({ ...tenantForm, billing_district: e.target.value })}
                  />
                </label>
                <label className="space-y-1">
                  <span>Cidade cobranca</span>
                  <input
                    className="input w-full"
                    value={tenantForm.billing_city}
                    onChange={(e) => setTenantForm({ ...tenantForm, billing_city: e.target.value })}
                  />
                </label>
                <label className="space-y-1">
                  <span>UF cobranca</span>
                  <input
                    className="input w-full"
                    maxLength={2}
                    value={tenantForm.billing_state}
                    onChange={(e) => setTenantForm({ ...tenantForm, billing_state: e.target.value })}
                  />
                </label>
                <label className="space-y-1 md:col-span-2">
                  <span>Complemento cobranca</span>
                  <input
                    className="input w-full"
                    value={tenantForm.billing_complement}
                    onChange={(e) => setTenantForm({ ...tenantForm, billing_complement: e.target.value })}
                  />
                </label>
                <label className="space-y-1">
                  <span>Origem onboarding</span>
                  <input
                    className="input w-full"
                    value={tenantForm.onboarding_origin}
                    onChange={(e) => setTenantForm({ ...tenantForm, onboarding_origin: e.target.value })}
                    placeholder="admin_manual, landing_page, sales_team"
                  />
                </label>
                <label className="space-y-1">
                  <span>Modo de ativacao</span>
                  <input
                    className="input w-full"
                    value={tenantForm.activation_mode}
                    onChange={(e) => setTenantForm({ ...tenantForm, activation_mode: e.target.value })}
                    placeholder="manual, automatic_webhook"
                  />
                </label>
                <label className="space-y-1">
                  <span>Provedor pagamento</span>
                  <input
                    className="input w-full"
                    value={tenantForm.payment_provider}
                    onChange={(e) => setTenantForm({ ...tenantForm, payment_provider: e.target.value })}
                    placeholder="mercado_pago, pagseguro..."
                  />
                </label>
                <label className="space-y-1">
                  <span>Referencia pagamento</span>
                  <input
                    className="input w-full"
                    value={tenantForm.payment_reference}
                    onChange={(e) => setTenantForm({ ...tenantForm, payment_reference: e.target.value })}
                    placeholder="id da cobranca/link"
                  />
                </label>
                <label className="space-y-1 md:col-span-2">
                  <span>Ativado em</span>
                  <input
                    type="datetime-local"
                    className="input w-full"
                    value={tenantForm.activated_at}
                    onChange={(e) => setTenantForm({ ...tenantForm, activated_at: e.target.value })}
                  />
                </label>
                <label className="space-y-1 md:col-span-2">
                  <span>Notas de ativacao</span>
                  <textarea
                    className="input w-full min-h-[90px]"
                    value={tenantForm.activation_notes}
                    onChange={(e) => setTenantForm({ ...tenantForm, activation_notes: e.target.value })}
                  />
                </label>
                <label className="space-y-1">
                  <span>Tipo de pessoa</span>
                  <select
                    className="input w-full"
                    value={tenantForm.person_type}
                    onChange={(e) => setTenantForm({ ...tenantForm, person_type: e.target.value })}
                  >
                    <option value="individual">Pessoa fisica (CPF)</option>
                    <option value="company">Pessoa juridica (CNPJ)</option>
                  </select>
                </label>
                <label className="space-y-1">
                  <span>Documento</span>
                  <input
                    className="input w-full"
                    value={tenantForm.document}
                    onChange={(e) => setTenantForm({ ...tenantForm, document: e.target.value })}
                    placeholder="CPF ou CNPJ"
                  />
                </label>
                <label className="flex items-center gap-2 md:col-span-2">
                  <input
                    type="checkbox"
                    className="accent-[#6320ee]"
                    checked={tenantForm.payment_link_enabled}
                    onChange={(e) =>
                      setTenantForm({ ...tenantForm, payment_link_enabled: e.target.checked })
                    }
                  />
                  <span>Link de pagamento ativo</span>
                </label>
                <label className="space-y-1 md:col-span-2">
                  <span>Configuracao do link (JSON)</span>
                  <textarea
                    className="input w-full min-h-[120px] font-mono text-xs"
                    placeholder='{"provider":"pix","expires_in_days":3}'
                    value={tenantForm.payment_link_config_text}
                    onChange={(e) =>
                      setTenantForm({ ...tenantForm, payment_link_config_text: e.target.value })
                    }
                  />
                </label>
                <label className="space-y-1 md:col-span-2">
                  <span>Payload de cadastro futuro (JSON)</span>
                  <textarea
                    className="input w-full min-h-[120px] font-mono text-xs"
                    placeholder='{"company":{"legal_name":"ACME LTDA"},"payment":{"id":"pay_123"}}'
                    value={tenantForm.signup_payload_text}
                    onChange={(e) =>
                      setTenantForm({ ...tenantForm, signup_payload_text: e.target.value })
                    }
                  />
                </label>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 space-y-3">
                <div>
                  <h3 className="text-lg font-semibold">Plano</h3>
                  <p className="text-xs text-slate-500">Selecione o plano para definir modulos e limites.</p>
                </div>
                <div className="grid md:grid-cols-2 gap-3 text-sm">
                  <label className="space-y-1">
                    <span>Plano</span>
                    <select
                      className="input w-full"
                      value={selectedPlanId}
                      onChange={(e) => {
                        const planId = e.target.value;
                        setSelectedPlanId(planId);
                        const plan = plans.find((item) => item.id === planId);
                        setSelectedPlanModules(plan?.modules ?? []);
                      }}
                    >
                      <option value="">Sem plano</option>
                      {plans.map((plan) => (
                        <option key={plan.id} value={plan.id}>
                          {plan.name}
                          {plan.is_active ? "" : " (Inativo)"}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="md:col-span-2 text-xs text-slate-600">
                    Modulos inclusos:{" "}
                    {selectedPlanModules.length > 0
                      ? selectedPlanModules.map((key) => MODULE_LABELS[key] || key).join(", ")
                      : "Nenhum modulo"}
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-4 space-y-3">
                <div>
                  <h3 className="text-lg font-semibold">Mensagens (WhatsApp/Telegram)</h3>
                  <p className="text-xs text-slate-500">
                    Configure tokens e numeros por empresa. Disponivel apenas se o modulo Mensagens estiver ativo.
                  </p>
                </div>
                {!messagesEnabled && (
                  <p className="text-xs text-amber-700">
                    Habilite o modulo Mensagens para liberar esta configuracao.
                  </p>
                )}
                <div className="grid md:grid-cols-2 gap-4 text-sm">
                  <label className="flex items-center gap-2 md:col-span-2">
                    <input
                      type="checkbox"
                      className="accent-[#6320ee]"
                      checked={messagingConfig.whatsapp_enabled}
                      onChange={(e) =>
                        setMessagingConfig({ ...messagingConfig, whatsapp_enabled: e.target.checked })
                      }
                      disabled={!messagesEnabled}
                    />
                    <span>WhatsApp habilitado</span>
                  </label>
                  <label className="space-y-1">
                    <span>WhatsApp Token</span>
                    <input
                      className="input w-full"
                      value={messagingConfig.whatsapp_token}
                      onChange={(e) =>
                        setMessagingConfig({ ...messagingConfig, whatsapp_token: e.target.value })
                      }
                      placeholder="EAAG..."
                      disabled={!messagesEnabled}
                    />
                  </label>
                  <label className="space-y-1">
                    <span>WhatsApp Phone Number ID</span>
                    <input
                      className="input w-full"
                      value={messagingConfig.whatsapp_phone_number_id}
                      onChange={(e) =>
                        setMessagingConfig({ ...messagingConfig, whatsapp_phone_number_id: e.target.value })
                      }
                      placeholder="1234567890"
                      disabled={!messagesEnabled}
                    />
                  </label>
                  <label className="flex items-center gap-2 md:col-span-2">
                    <input
                      type="checkbox"
                      className="accent-[#6320ee]"
                      checked={messagingConfig.telegram_enabled}
                      onChange={(e) =>
                        setMessagingConfig({ ...messagingConfig, telegram_enabled: e.target.checked })
                      }
                      disabled={!messagesEnabled}
                    />
                    <span>Telegram habilitado</span>
                  </label>
                  <label className="space-y-1">
                    <span>Telegram Bot Token</span>
                    <input
                      className="input w-full"
                      value={messagingConfig.telegram_bot_token}
                      onChange={(e) =>
                        setMessagingConfig({ ...messagingConfig, telegram_bot_token: e.target.value })
                      }
                      placeholder="123456:ABC..."
                      disabled={!messagesEnabled}
                    />
                  </label>
                  <label className="space-y-1">
                    <span>Telegram Chat ID</span>
                    <input
                      className="input w-full"
                      value={messagingConfig.telegram_chat_id}
                      onChange={(e) =>
                        setMessagingConfig({ ...messagingConfig, telegram_chat_id: e.target.value })
                      }
                      placeholder="-1001234567890"
                      disabled={!messagesEnabled}
                    />
                  </label>
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="text-xs text-slate-500">
                  Dica: mantenha o limite coerente com o contrato para evitar bloqueios inesperados.
                </div>
                <div className="flex items-center gap-3">
                  {selectedTenant && (
                    <button
                      type="button"
                      onClick={() => selectedTenant && openUsersModal(selectedTenant)}
                      className="px-4 py-2 rounded-lg bg-slate-100 border border-slate-200 text-slate-700"
                    >
                      Gerenciar usuarios
                    </button>
                  )}
                  <button
                    type="submit"
                    disabled={loading}
                    className="px-4 py-2 rounded-lg bg-[#6320ee] text-white font-semibold"
                  >
                    {loading ? "Salvando..." : "Salvar"}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {usersModalOpen && selectedTenant && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/90 backdrop-blur-sm px-4">
          <div className="w-full max-w-4xl max-h-[90vh] overflow-y-auto rounded-3xl bg-white border border-slate-200 shadow-2xl shadow-slate-200/80 p-6 space-y-5 text-slate-900">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Usuarios</p>
                <h2 className="text-2xl font-semibold">{selectedTenant.name}</h2>
                <p className="text-xs text-slate-500">{selectedTenant.slug}</p>
              </div>
              <button
                onClick={closeUsersModal}
                className="text-sm px-3 py-1 rounded-full bg-slate-100 border border-slate-200 hover:bg-slate-200"
              >
                Fechar
              </button>
            </div>

            <div className="overflow-hidden rounded-2xl border border-slate-200 bg-slate-50">
              <table className="w-full text-sm">
                <thead className="bg-slate-100 text-left text-slate-700">
                  <tr>
                    <th className="px-4 py-2">Nome</th>
                    <th className="px-4 py-2">Email</th>
                    <th className="px-4 py-2">Perfil</th>
                    <th className="px-4 py-2">Sessoes</th>
                    <th className="px-4 py-2">Status</th>
                    <th className="px-4 py-2 text-right">Acoes</th>
                  </tr>
                </thead>
                <tbody>
                  {users.length === 0 ? (
                    <tr>
                      <td className="px-4 py-4 text-center text-slate-600" colSpan={6}>
                        Nenhum usuario cadastrado.
                      </td>
                    </tr>
                  ) : (
                    users.map((user, idx) => (
                      <tr key={user.id} className={idx % 2 === 0 ? "bg-transparent" : "bg-slate-50"}>
                        <td className="px-4 py-2 font-medium">{user.name}</td>
                        <td className="px-4 py-2 text-slate-600">{user.email}</td>
                        <td className="px-4 py-2">{user.role}</td>
                        <td className="px-4 py-2">{user.max_active_sessions ?? 3}</td>
                        <td className="px-4 py-2">
                          <span
                            className={`text-[10px] px-2 py-1 rounded-full border ${
                              user.is_active
                                ? "bg-emerald-200 border-emerald-300 text-emerald-900"
                                : "bg-red-200 border-red-300 text-red-900"
                            }`}
                          >
                            {user.is_active ? "Ativo" : "Inativo"}
                          </span>
                        </td>
                        <td className="px-4 py-2 text-right space-x-2">
                          <button
                            onClick={() => startEditUser(user)}
                            className="px-3 py-1 rounded-lg border border-slate-200 text-xs"
                          >
                            Editar
                          </button>
                          <button
                            onClick={() => toggleUser(user)}
                            className="px-3 py-1 rounded-lg bg-[#6320ee] text-white text-xs"
                          >
                            {user.is_active ? "Inativar" : "Ativar"}
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            <form onSubmit={saveUser} className="space-y-4">
              <div className="grid md:grid-cols-2 gap-4 text-sm">
                <label className="space-y-1">
                  <span>Nome</span>
                  <input
                    className="input w-full"
                    value={userForm.name}
                    onChange={(e) => setUserForm({ ...userForm, name: e.target.value })}
                    required
                  />
                </label>
                <label className="space-y-1">
                  <span>Email</span>
                  <input
                    type="email"
                    className="input w-full"
                    value={userForm.email}
                    onChange={(e) => setUserForm({ ...userForm, email: e.target.value })}
                    required
                  />
                </label>
                <label className="space-y-1">
                  <span>Senha {userEditingId ? "(opcional)" : ""}</span>
                  <input
                    type="password"
                    className="input w-full"
                    value={userForm.password}
                    onChange={(e) => setUserForm({ ...userForm, password: e.target.value })}
                    required={!userEditingId}
                  />
                </label>
                <label className="space-y-1">
                  <span>Perfil</span>
                  <select
                    className="input w-full"
                    value={userForm.role}
                    onChange={(e) => setUserForm({ ...userForm, role: e.target.value })}
                  >
                    <option value="owner">Owner</option>
                    <option value="manager">Manager</option>
                    <option value="operator">Operator</option>
                  </select>
                </label>
                <label className="space-y-1">
                  <span>Maximo de sessoes</span>
                  <input
                    type="number"
                    min={1}
                    max={20}
                    className="input w-full"
                    value={userForm.max_active_sessions}
                    onChange={(e) =>
                      setUserForm({ ...userForm, max_active_sessions: Number(e.target.value) })
                    }
                  />
                </label>
              </div>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={enableFirstAccessTestForTenant}
                  disabled={loading || firstAccessTestLoading}
                  className="px-4 py-2 rounded-lg bg-white border border-slate-200 text-slate-700 font-semibold disabled:opacity-60"
                >
                  {firstAccessTestLoading ? "Marcando..." : "Marcar primeiro acesso (teste)"}
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 rounded-lg bg-[#6320ee] text-white font-semibold"
                >
                  {userEditingId ? "Salvar usuario" : "Adicionar usuario"}
                </button>
                {userEditingId && (
                  <button
                    type="button"
                    onClick={() => {
                      setUserEditingId(null);
                      setUserForm(DEFAULT_USER_FORM);
                    }}
                    className="px-3 py-2 rounded-lg bg-slate-100 border border-slate-200 text-slate-700"
                  >
                    Cancelar
                  </button>
                )}
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}
