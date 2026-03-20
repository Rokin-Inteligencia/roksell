"use client";
import { useEffect, useState } from "react";
import { adminFetch } from "@/lib/admin-api";
import { useAdminGuard } from "@/lib/use-admin-guard";
import { ProfileBadge } from "@/components/admin/ProfileBadge";
import { AdminSidebar } from "@/components/admin/AdminSidebar";
import { adminMenuWithHome } from "@/config/adminMenu";
import { usePathname } from "next/navigation";
import { useOrgName } from "@/lib/use-org-name";
import { clearAdminToken } from "@/lib/admin-auth";
import { useTenantModules } from "@/lib/use-tenant-modules";

type Customer = {
  id: string;
  name: string;
  phone?: string;
  birthday?: string | null;
  origin_store_id?: string | null;
  origin_store_name?: string | null;
  created_at?: string;
  is_active?: boolean;
};

type StoreOption = {
  id: string;
  name: string;
};

type GroupOptionsPayload = {
  stores: StoreOption[];
};

function toDateInputValue(value?: string | null) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function formatBirthday(value?: string | null) {
  if (!value) return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "-";
  return d.toLocaleDateString("pt-BR");
}

export default function CustomersPage() {
  const ready = useAdminGuard();
  const tenantName = useOrgName();
  const pathname = usePathname();
  const { hasModule, hasModuleAction, ready: modulesReady } = useTenantModules();
  const moduleAllowed = hasModule("customers");
  const moduleBlocked = modulesReady && !moduleAllowed;
  const canEditCustomers = hasModuleAction("customers", "edit");
  async function logout() {
    try {
      await fetch("/api/auth/logout", { method: "POST", credentials: "include" });
    } catch {
      /* ignore */
    } finally {
      clearAdminToken();
      window.location.href = "/roksell/login";
    }
  }

  const [customers, setCustomers] = useState<Customer[]>([]);
  const [stores, setStores] = useState<StoreOption[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [filterOpen, setFilterOpen] = useState(false);

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState("30");
  const [activeFilter, setActiveFilter] = useState<"true" | "false" | "all">("true");
  const [selected, setSelected] = useState<Customer | null>(null);
  const [editData, setEditData] = useState<{ name: string; phone: string; birthday: string }>({
    name: "",
    phone: "",
    birthday: "",
  });
  const [showModal, setShowModal] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createPhone, setCreatePhone] = useState("");
  const [createStoreId, setCreateStoreId] = useState("");
  const [createBirthday, setCreateBirthday] = useState("");
  const [createActive, setCreateActive] = useState(true);
  const [createSaving, setCreateSaving] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  async function loadStores() {
    try {
      const options = await adminFetch<GroupOptionsPayload>("/admin/groups/options");
      setStores(options.stores || []);
    } catch {
      setStores([]);
    }
  }

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const qs = new URLSearchParams();
      qs.set("page", String(page));
      qs.set("limit", pageSize);
      if (activeFilter !== "all") qs.set("active", activeFilter);
      if (debouncedSearch) qs.set("search", debouncedSearch);
      const res = await adminFetch<Customer[]>(`/admin/customers?${qs.toString()}`);
      setCustomers(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao carregar clientes");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const handle = setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => clearTimeout(handle);
  }, [search]);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, activeFilter]);

  useEffect(() => {
    if (ready && modulesReady && moduleAllowed) {
      load();
      loadStores();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, modulesReady, moduleAllowed, page, pageSize, debouncedSearch, activeFilter]);

  async function openCreateModal() {
    setShowCreateModal(true);
    setCreateName("");
    setCreatePhone("");
    setCreateStoreId(stores[0]?.id ?? "");
    setCreateBirthday("");
    setCreateActive(true);
    setCreateError(null);
    await loadStores();
  }

  async function submitCreate() {
    const name = createName.trim();
    const phone = createPhone.trim();
    if (!name) {
      setCreateError("Nome é obrigatório.");
      return;
    }
    if (!phone) {
      setCreateError("Telefone é obrigatório.");
      return;
    }
    setCreateSaving(true);
    setCreateError(null);
    try {
      await adminFetch<Customer>("/admin/customers", {
        method: "POST",
        body: JSON.stringify({
          name,
          phone,
          origin_store_id: createStoreId || null,
          birthday: createBirthday || null,
          is_active: createActive,
        }),
      });
      setShowCreateModal(false);
      setPage(1);
      await load();
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : "Falha ao cadastrar cliente");
    } finally {
      setCreateSaving(false);
    }
  }

  function onSelect(customer: Customer) {
    if (!canEditCustomers) return;
    setSelected(customer);
    setEditData({
      name: customer.name,
      phone: customer.phone ?? "",
      birthday: toDateInputValue(customer.birthday),
    });
    setShowModal(true);
  }

  async function save() {
    if (!canEditCustomers) return;
    if (!selected) return;
    const name = editData.name.trim();
    const phone = editData.phone.trim();

    if (!name) {
      setError("Nome é obrigatório.");
      return;
    }
    if (!phone) {
      setError("Telefone é obrigatório.");
      return;
    }

    const payload: Record<string, unknown> = {
      name,
      phone,
      birthday: editData.birthday || null,
    };
    try {
      setLoading(true);
      setError(null);
      await adminFetch(`/admin/customers/${selected.id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      await load();
      setShowModal(false);
      setSelected(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao salvar cliente");
    } finally {
      setLoading(false);
    }
  }

  async function toggleActive(customer: Customer) {
    if (!canEditCustomers) return;
    try {
      setLoading(true);
      setError(null);
      await adminFetch(`/admin/customers/${customer.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !(customer.is_active ?? true) }),
      });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao atualizar status");
    } finally {
      setLoading(false);
    }
  }

  if (!ready) return null;

  const sidebarItems = adminMenuWithHome;
  const statusLabel = activeFilter === "all" ? "Todos" : activeFilter === "true" ? "Ativos" : "Inativos";
  const filterSummary = `Status ${statusLabel} | ${pageSize} por pagina${search ? ` | ${search}` : ""}`;

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
                className="block px-3 py-2 w-full text-left rounded-lg bg-[#6320ee] text-[#f8f0fb] font-semibold hover:brightness-95 transition"
              >
                Sair
              </button>
            }
          />

          <div className="space-y-6">
            <header className="flex flex-wrap items-center justify-between gap-3">
              <div className="text-slate-900 space-y-1">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-600">Admin – Clientes</p>
                <h1 className="text-3xl font-semibold">Gestão de clientes</h1>
                <p className="text-sm text-slate-600">Cadastre, liste e edite clientes (nome, telefone e dados opcionais).</p>
              </div>
              <ProfileBadge />
            </header>
            {moduleBlocked ? (
              <section className="rounded-2xl bg-white border border-slate-200 p-4 space-y-2">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Modulo inativo</p>
                <h2 className="text-lg font-semibold">Clientes indisponivel</h2>
                <p className="text-sm text-slate-600">
                  Este modulo nao esta habilitado para a sua empresa. Fale com o administrador para liberar o acesso.
                </p>
              </section>
            ) : (
              <>
                {error && <p className="text-sm text-amber-700">{error}</p>}

                <section className="rounded-3xl bg-white border border-slate-200 p-3 sm:p-5 space-y-4 shadow-sm">
                  <div className="flex flex-wrap items-center gap-3 justify-between">
                    <div className="space-y-1">
                      <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Clientes</p>
                      <h2 className="text-lg font-semibold text-slate-900">Base cadastrada</h2>
                    </div>
                    <button
                      type="button"
                      onClick={() => openCreateModal()}
                      disabled={!canEditCustomers}
                      className="px-3 py-2 rounded-lg bg-[#6320ee] text-white text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Cadastrar cliente
                    </button>
                  </div>
                </section>

                <section className="rounded-2xl bg-white border border-slate-200 p-3 sm:p-4 space-y-3 sm:space-y-4">
                  <button
                    type="button"
                    onClick={() => setFilterOpen((open) => !open)}
                    className="sm:hidden w-full flex items-center justify-between text-left gap-3"
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
                    className={`${filterOpen ? "grid" : "hidden"} grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 sm:gap-3 text-xs sm:text-sm sm:grid`}
                  >
                    <label className="space-y-1">
                      <span>Itens por pagina</span>
                      <select className="input w-full" value={pageSize} onChange={(e) => setPageSize(e.target.value)}>
                        <option value="30">30</option>
                        <option value="50">50</option>
                        <option value="100">100</option>
                      </select>
                    </label>
                    <label className="space-y-1">
                      <span>Status</span>
                      <select
                        className="input w-full"
                        value={activeFilter}
                        onChange={(e) => setActiveFilter(e.target.value as typeof activeFilter)}
                      >
                        <option value="true">Ativos</option>
                        <option value="false">Inativos</option>
                        <option value="all">Todos</option>
                      </select>
                    </label>
                    <label className="space-y-1 sm:col-span-2 lg:col-span-1">
                      <span>Buscar</span>
                      <input
                        className="input w-full"
                        placeholder="Nome ou telefone"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                      />
                    </label>
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-600">
                    <span>Pagina {page}</span>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                        className="px-3 py-1 rounded bg-slate-100 border border-slate-200 disabled:opacity-50"
                        disabled={page === 1 || loading}
                      >
                        Anterior
                      </button>
                      <button
                        onClick={() => setPage((p) => p + 1)}
                        className="px-3 py-1 rounded bg-slate-100 border border-slate-200 disabled:opacity-50"
                        disabled={loading}
                      >
                        Proxima
                      </button>
                    </div>
                  </div>

                  {customers.length === 0 ? (
                    <p className="text-sm text-slate-600">Nenhum cliente encontrado.</p>
                  ) : (
                    <>
                      <div className="space-y-3 sm:hidden">
                        {customers.map((customer) => (
                          <div key={customer.id} className="rounded-xl border border-slate-200 bg-slate-50 p-3 space-y-2">
                            <div className="flex items-start justify-between gap-2">
                              <div>
                                <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Cliente</p>
                                <p className="text-sm font-semibold text-slate-900">{customer.name}</p>
                              </div>
                              <span
                                className={`text-[10px] px-2 py-1 rounded-full border ${
                                  customer.is_active === false
                                    ? "bg-red-200 border-red-300 text-red-900"
                                    : "bg-emerald-200 border-emerald-300 text-emerald-900"
                                }`}
                              >
                                {customer.is_active === false ? "Inativo" : "Ativo"}
                              </span>
                            </div>
                            <div className="grid grid-cols-2 gap-2 text-xs text-slate-700">
                              <div>
                                <p className="text-[10px] uppercase tracking-[0.2em] text-slate-400">Telefone</p>
                                <p>{customer.phone || "-"}</p>
                              </div>
                              <div>
                                <p className="text-[10px] uppercase tracking-[0.2em] text-slate-400">Nascimento</p>
                                <p>{formatBirthday(customer.birthday)}</p>
                              </div>
                            </div>
                            <div className="text-xs text-slate-600">
                              Cadastro:{" "}
                              {customer.created_at ? new Date(customer.created_at).toLocaleDateString("pt-BR") : "-"}
                            </div>
                            <div className="text-xs text-slate-600">Loja origem: {customer.origin_store_name || "-"}</div>
                            <div className="flex flex-wrap gap-2">
                              <button
                                onClick={() => onSelect(customer)}
                                disabled={!canEditCustomers}
                                className="px-3 py-2 rounded-lg bg-[#6320ee] text-white text-xs hover:brightness-95 disabled:opacity-50 disabled:cursor-not-allowed"
                              >
                                Editar
                              </button>
                              <button
                                onClick={() => toggleActive(customer)}
                                disabled={!canEditCustomers}
                                className="px-3 py-2 rounded-lg bg-slate-100 border border-slate-200 text-slate-900 text-xs hover:bg-slate-200 disabled:opacity-50 disabled:cursor-not-allowed"
                              >
                                {customer.is_active === false ? "Ativar" : "Inativar"}
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                      <div className="hidden sm:block">
                        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-50">
                          <table className="w-full text-xs sm:text-sm min-w-[860px]">
                            <thead className="bg-slate-100 text-left">
                              <tr>
                                <th className="px-3 sm:px-4 py-2 font-semibold text-slate-700">Nome</th>
                                <th className="px-3 sm:px-4 py-2 font-semibold text-slate-700">Telefone</th>
                                <th className="px-3 sm:px-4 py-2 font-semibold text-slate-700">Nascimento</th>
                                <th className="px-3 sm:px-4 py-2 font-semibold text-slate-700">Loja origem</th>
                                <th className="px-3 sm:px-4 py-2 font-semibold text-slate-700">Cadastro</th>
                                <th className="px-3 sm:px-4 py-2 text-right font-semibold text-slate-700">Ações</th>
                              </tr>
                            </thead>
                            <tbody>
                              {customers.map((customer, idx) => (
                                <tr key={customer.id} className={idx % 2 === 0 ? "bg-transparent" : "bg-slate-50"}>
                                  <td className="px-3 sm:px-4 py-2">
                                    <div className="flex items-center gap-2">
                                      <span>{customer.name}</span>
                                      <span
                                        className={`text-[10px] px-2 py-1 rounded-full border ${
                                          customer.is_active === false
                                            ? "bg-red-200 border-red-300 text-red-900"
                                            : "bg-emerald-200 border-emerald-300 text-emerald-900"
                                        }`}
                                      >
                                        {customer.is_active === false ? "Inativo" : "Ativo"}
                                      </span>
                                    </div>
                                  </td>
                                  <td className="px-3 sm:px-4 py-2">{customer.phone || "-"}</td>
                                  <td className="px-3 sm:px-4 py-2">{formatBirthday(customer.birthday)}</td>
                                  <td className="px-3 sm:px-4 py-2">{customer.origin_store_name || "-"}</td>
                                  <td className="px-3 sm:px-4 py-2">
                                    {customer.created_at
                                      ? new Date(customer.created_at).toLocaleDateString("pt-BR")
                                      : "-"}
                                  </td>
                                  <td className="px-3 sm:px-4 py-2 text-right">
                                    <button
                                      onClick={() => onSelect(customer)}
                                      disabled={!canEditCustomers}
                                      className="px-3 py-1 rounded-lg bg-[#6320ee] text-white text-xs hover:brightness-95 disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                      Editar
                                    </button>
                                    <button
                                      onClick={() => toggleActive(customer)}
                                      disabled={!canEditCustomers}
                                      className="ml-2 px-3 py-1 rounded-lg bg-slate-100 border border-slate-200 text-slate-900 text-xs hover:bg-slate-200 disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                      {customer.is_active === false ? "Ativar" : "Inativar"}
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

      {showCreateModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/90 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl w-full max-w-lg max-h-[90vh] overflow-hidden flex flex-col text-slate-900">
            <div className="flex items-center justify-between p-4 border-b border-slate-200">
              <h2 className="text-xl font-semibold">Cadastrar cliente</h2>
              <button
                type="button"
                onClick={() => setShowCreateModal(false)}
                className="p-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-600"
                aria-label="Fechar"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="flex-1 overflow-auto p-4 space-y-4 text-sm">
              {createError && <p className="text-amber-700 text-sm">{createError}</p>}
              <p className="text-xs text-slate-600">
                Campos obrigatórios estão marcados com <span className="text-red-600">*</span>. O telefone é normalizado no servidor (DDI padrão configurável).
              </p>
              <label className="block space-y-1">
                <span className="font-medium text-slate-700">
                  Nome completo <span className="text-red-600">*</span>
                </span>
                <input
                  className="input w-full"
                  value={createName}
                  onChange={(e) => setCreateName(e.target.value)}
                  placeholder="Como aparece no pedido"
                  autoComplete="name"
                />
              </label>
              <label className="block space-y-1">
                <span className="font-medium text-slate-700">
                  Telefone <span className="text-red-600">*</span>
                </span>
                <input
                  className="input w-full"
                  value={createPhone}
                  onChange={(e) => setCreatePhone(e.target.value)}
                  placeholder="Ex.: 11999998888"
                  inputMode="tel"
                  autoComplete="tel"
                />
              </label>
              {stores.length > 0 && (
                <label className="block space-y-1">
                  <span className="font-medium text-slate-700">Loja de origem</span>
                  <select
                    className="input w-full"
                    value={createStoreId}
                    onChange={(e) => setCreateStoreId(e.target.value)}
                  >
                    <option value="">—</option>
                    {stores.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <label className="block space-y-1">
                <span className="font-medium text-slate-700">Data de nascimento</span>
                <input
                  type="date"
                  className="input w-full"
                  value={createBirthday}
                  onChange={(e) => setCreateBirthday(e.target.value)}
                />
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={createActive}
                  onChange={(e) => setCreateActive(e.target.checked)}
                  className="rounded border-slate-300"
                />
                <span className="font-medium text-slate-700">Cliente ativo</span>
              </label>
            </div>
            <div className="p-4 border-t border-slate-200 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowCreateModal(false)}
                className="px-4 py-2 rounded-lg bg-slate-100 text-slate-900 font-medium hover:bg-slate-200"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={() => submitCreate()}
                disabled={createSaving}
                className="px-4 py-2 rounded-lg bg-[#6320ee] text-white font-medium hover:brightness-95 disabled:opacity-60"
              >
                {createSaving ? "Salvando..." : "Salvar cliente"}
              </button>
            </div>
          </div>
        </div>
      )}

      {showModal && selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/90 backdrop-blur-sm px-4">
          <div
            role="dialog"
            aria-modal="true"
            className="w-full max-w-xl rounded-3xl bg-white border border-slate-200 shadow-2xl shadow-slate-200/80 p-6 space-y-4 text-slate-900"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-600">Editar cliente</p>
                <h2 className="text-2xl font-semibold">{selected.name}</h2>
                <p className="text-xs text-slate-600 mt-1">ID interno: {selected.id}</p>
              </div>
              <button
                onClick={() => {
                  setShowModal(false);
                  setSelected(null);
                }}
                className="text-sm px-3 py-1 rounded-full bg-slate-100 border border-slate-200 hover:bg-slate-200"
              >
                Fechar
              </button>
            </div>

            <div className="grid md:grid-cols-2 gap-3 text-sm">
              <label className="space-y-1 md:col-span-2">
                <span>
                  Nome <span className="text-red-600">*</span>
                </span>
                <input
                  className="input w-full"
                  value={editData.name}
                  disabled={!canEditCustomers}
                  onChange={(e) => setEditData({ ...editData, name: e.target.value })}
                />
              </label>
              <label className="space-y-1 md:col-span-2">
                <span>
                  Telefone <span className="text-red-600">*</span>
                </span>
                <input
                  className="input w-full"
                  value={editData.phone}
                  disabled={!canEditCustomers}
                  onChange={(e) => setEditData({ ...editData, phone: e.target.value })}
                  inputMode="tel"
                />
              </label>
              <label className="space-y-1 md:col-span-2">
                <span>Data de nascimento</span>
                <input
                  type="date"
                  className="input w-full"
                  value={editData.birthday}
                  disabled={!canEditCustomers}
                  onChange={(e) => setEditData({ ...editData, birthday: e.target.value })}
                />
              </label>
            </div>

            <div className="flex items-center justify-end gap-3">
              <button
                onClick={() => {
                  setShowModal(false);
                  setSelected(null);
                }}
                className="px-4 py-2 rounded-lg bg-slate-100 text-slate-900 text-sm font-semibold active:scale-95"
              >
                Cancelar
              </button>
              <button
                onClick={save}
                disabled={loading || !canEditCustomers}
                className="px-4 py-2 rounded-lg bg-[#6320ee] text-white text-sm font-semibold active:scale-95 disabled:opacity-60"
              >
                Salvar
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
