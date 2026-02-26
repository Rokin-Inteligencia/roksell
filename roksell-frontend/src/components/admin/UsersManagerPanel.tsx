"use client";
import { useEffect, useMemo, useState } from "react";
import { adminFetch } from "@/lib/admin-api";

type UserRow = {
  id: string;
  name: string;
  email: string;
  role: string;
  is_active: boolean;
  max_active_sessions?: number;
  group_id?: string | null;
  default_store_id?: string | null;
};

type Licenses = {
  limit: number;
  used: number;
};

type GroupRow = {
  id: string;
  name: string;
  is_active: boolean;
  permissions: string[];
  store_ids: string[];
  users_count: number;
};

type GroupStoreOption = {
  id: string;
  name: string;
  slug?: string;
};

type GroupOptions = {
  modules: string[];
  stores: GroupStoreOption[];
  active_plan_name?: string | null;
  active_plan_id?: string | null;
};

const ROLE_LABEL: Record<string, string> = {
  owner: "Administrador",
  manager: "Gerente",
  operator: "Operador",
};

const MODULE_LABEL: Record<string, string> = {
  campaigns: "Campanhas",
  inventory: "Estoque",
  customers: "Clientes",
  products: "Produtos",
  insights: "Insights",
  messages: "Mensagens",
  stores: "Lojas",
  config: "Configuracoes",
};

type AccessLevel = "none" | "view" | "edit";
const ACCESS_LEVEL_MODULES = ["campaigns", "inventory", "customers", "products"] as const;
const ACCESS_LEVEL_OPTIONS: { value: AccessLevel; label: string }[] = [
  { value: "none", label: "Sem acesso" },
  { value: "view", label: "Somente visualizacao" },
  { value: "edit", label: "Visualizacao e edicao" },
];

function uniqueValues(values: string[]) {
  const out: string[] = [];
  values.forEach((value) => {
    if (value && !out.includes(value)) out.push(value);
  });
  return out;
}

function getModuleAccessLevel(permissions: string[], moduleKey: string): AccessLevel {
  const normalized = new Set(permissions.map((item) => item.trim().toLowerCase()));
  if (normalized.has(moduleKey) || normalized.has(`${moduleKey}:edit`)) return "edit";
  if (normalized.has(`${moduleKey}:view`)) return "view";
  return "none";
}

function setModuleAccessLevel(
  permissions: string[],
  moduleKey: string,
  level: AccessLevel,
): string[] {
  const blocked = new Set([moduleKey, `${moduleKey}:view`, `${moduleKey}:edit`]);
  const base = permissions.filter((item) => !blocked.has(item.trim().toLowerCase()));
  if (level === "view") return uniqueValues([...base, `${moduleKey}:view`]);
  if (level === "edit") return uniqueValues([...base, `${moduleKey}:edit`]);
  return uniqueValues(base);
}

export function UsersManagerPanel() {
  const [usersError, setUsersError] = useState<string | null>(null);
  const [usersLoading, setUsersLoading] = useState(false);
  const [userFormError, setUserFormError] = useState<string | null>(null);

  const [users, setUsers] = useState<UserRow[]>([]);
  const [licenses, setLicenses] = useState<Licenses | null>(null);

  const [groups, setGroups] = useState<GroupRow[]>([]);
  const [groupOptions, setGroupOptions] = useState<GroupOptions>({ modules: [], stores: [] });

  const [showUserForm, setShowUserForm] = useState(false);
  const [editingUser, setEditingUser] = useState<UserRow | null>(null);
  const [startingFirstAccessTest, setStartingFirstAccessTest] = useState(false);
  const [userForm, setUserForm] = useState({
    name: "",
    email: "",
    role: "operator",
    password: "",
    is_active: true,
    max_active_sessions: 3,
    group_id: "",
    default_store_id: "",
  });

  const [showGroupForm, setShowGroupForm] = useState(false);
  const [editingGroup, setEditingGroup] = useState<GroupRow | null>(null);
  const [groupForm, setGroupForm] = useState({
    name: "",
    is_active: true,
    permissions: [] as string[],
    store_ids: [] as string[],
  });

  const canCreate = licenses ? licenses.used < licenses.limit : true;
  const scopedModules = ACCESS_LEVEL_MODULES.filter((moduleKey) =>
    groupOptions.modules.includes(moduleKey)
  );
  const checkboxModules = groupOptions.modules.filter(
    (moduleKey) => !scopedModules.includes(moduleKey as (typeof ACCESS_LEVEL_MODULES)[number])
  );

  const groupById = useMemo(() => {
    const map = new Map<string, GroupRow>();
    groups.forEach((group) => map.set(group.id, group));
    return map;
  }, [groups]);

  const storeById = useMemo(() => {
    const map = new Map<string, GroupStoreOption>();
    groupOptions.stores.forEach((store) => map.set(store.id, store));
    return map;
  }, [groupOptions.stores]);

  const availableStoresForUser = useMemo(() => {
    const selectedGroup = groupById.get(userForm.group_id);
    if (!selectedGroup) return groupOptions.stores;
    if (!selectedGroup.store_ids || selectedGroup.store_ids.length === 0) return groupOptions.stores;
    return groupOptions.stores.filter((store) => selectedGroup.store_ids.includes(store.id));
  }, [groupById, groupOptions.stores, userForm.group_id]);

  function normalizeGroupStores(input: string[]) {
    const values = uniqueValues(input);
    if (values.length > 0) return values;
    if (groupOptions.stores.length === 1) return [groupOptions.stores[0].id];
    return values;
  }

  function normalizeGroupPermissions(input: string[]) {
    const allowed = new Set(groupOptions.modules);
    const normalized: string[] = [];
    uniqueValues(input).forEach((raw) => {
      const value = raw.trim().toLowerCase();
      if (!value) return;
      const [moduleKey, action] = value.split(":", 2);
      if (!moduleKey || !allowed.has(moduleKey)) return;
      if (action && action !== "view" && action !== "edit") return;
      normalized.push(action ? `${moduleKey}:${action}` : moduleKey);
    });
    return uniqueValues(normalized);
  }

  async function loadUsers() {
    setUsersLoading(true);
    setUsersError(null);
    try {
      const [list, lic, groupList, options] = await Promise.all([
        adminFetch<UserRow[]>("/admin/users"),
        adminFetch<Licenses>("/admin/users/limits"),
        adminFetch<GroupRow[]>("/admin/groups"),
        adminFetch<GroupOptions>("/admin/groups/options"),
      ]);
      setUsers(list);
      setLicenses(lic);
      setGroups(groupList);
      setGroupOptions(options);

      if (!userForm.group_id && groupList.length > 0) {
        const firstGroupId = groupList[0].id;
        setUserForm((prev) => ({
          ...prev,
          group_id: firstGroupId,
        }));
      }
    } catch (e) {
      setUsersError(e instanceof Error ? e.message : "Falha ao carregar usuarios");
    } finally {
      setUsersLoading(false);
    }
  }

  function openCreateUser() {
    const firstGroupId = groups[0]?.id ?? "";
    const firstStoreId = groups[0]?.store_ids?.[0] ?? groupOptions.stores[0]?.id ?? "";
    setEditingUser(null);
    setUserForm({
      name: "",
      email: "",
      role: "operator",
      password: "",
      is_active: true,
      max_active_sessions: 3,
      group_id: firstGroupId,
      default_store_id: firstStoreId,
    });
    setUserFormError(null);
    setShowUserForm(true);
  }

  function openEditUser(user: UserRow) {
    setEditingUser(user);
    setUserForm({
      name: user.name,
      email: user.email,
      role: user.role,
      password: "",
      is_active: user.is_active,
      max_active_sessions: user.max_active_sessions ?? 3,
      group_id: user.group_id || groups[0]?.id || "",
      default_store_id: user.default_store_id || "",
    });
    setUserFormError(null);
    setShowUserForm(true);
  }

  function openCreateGroup() {
    setEditingGroup(null);
    setGroupForm({
      name: "",
      is_active: true,
      permissions: normalizeGroupPermissions(groupOptions.modules),
      store_ids: normalizeGroupStores(groupOptions.stores.map((store) => store.id)),
    });
    setShowGroupForm(true);
  }

  function openEditGroup(group: GroupRow) {
    setEditingGroup(group);
    setGroupForm({
      name: group.name,
      is_active: group.is_active,
      permissions: normalizeGroupPermissions(group.permissions),
      store_ids: normalizeGroupStores(group.store_ids),
    });
    setShowGroupForm(true);
  }

  async function saveGroup() {
    const payload = {
      name: groupForm.name.trim(),
      permissions: normalizeGroupPermissions(groupForm.permissions),
      store_ids: normalizeGroupStores(groupForm.store_ids),
      is_active: groupForm.is_active,
    };
    if (!payload.name) {
      setUsersError("Informe o nome do grupo.");
      return;
    }

    try {
      setUsersLoading(true);
      setUsersError(null);
      if (editingGroup) {
        await adminFetch(`/admin/groups/${editingGroup.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
      } else {
        await adminFetch("/admin/groups", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }
      setShowGroupForm(false);
      setEditingGroup(null);
      await loadUsers();
    } catch (e) {
      setUsersError(e instanceof Error ? e.message : "Falha ao salvar grupo");
    } finally {
      setUsersLoading(false);
    }
  }

  async function deleteGroup(group: GroupRow) {
    if (!window.confirm(`Excluir o grupo ${group.name}?`)) return;
    try {
      setUsersLoading(true);
      setUsersError(null);
      await adminFetch(`/admin/groups/${group.id}`, { method: "DELETE" });
      await loadUsers();
    } catch (e) {
      setUsersError(e instanceof Error ? e.message : "Falha ao excluir grupo");
    } finally {
      setUsersLoading(false);
    }
  }

  async function saveUser() {
    const trimmedName = userForm.name.trim();
    const trimmedEmail = userForm.email.trim();
    const trimmedPassword = userForm.password.trim();

    if (!trimmedName) {
      setUserFormError("Informe o nome do usuario.");
      return;
    }
    if (!trimmedEmail) {
      setUserFormError("Informe o email do usuario.");
      return;
    }
    if (!userForm.group_id) {
      setUserFormError("Selecione um grupo para o usuario.");
      return;
    }
    if (!editingUser && trimmedPassword.length < 6) {
      setUserFormError("A senha deve ter no minimo 6 caracteres.");
      return;
    }
    if (editingUser && trimmedPassword.length > 0 && trimmedPassword.length < 6) {
      setUserFormError("A nova senha deve ter no minimo 6 caracteres.");
      return;
    }
    if (!Number.isInteger(userForm.max_active_sessions) || userForm.max_active_sessions < 1 || userForm.max_active_sessions > 20) {
      setUserFormError("Limite de sessoes deve ser entre 1 e 20.");
      return;
    }

    try {
      setUsersLoading(true);
      setUsersError(null);
      setUserFormError(null);
      if (editingUser) {
        const payload: Record<string, unknown> = {
          name: trimmedName,
          email: trimmedEmail,
          role: userForm.role,
          is_active: userForm.is_active,
          max_active_sessions: userForm.max_active_sessions,
          group_id: userForm.group_id,
          default_store_id: userForm.default_store_id || null,
        };
        if (trimmedPassword) payload.password = trimmedPassword;
        await adminFetch(`/admin/users/${editingUser.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
      } else {
        await adminFetch("/admin/users", {
          method: "POST",
          body: JSON.stringify({
            name: trimmedName,
            email: trimmedEmail,
            password: trimmedPassword,
            role: userForm.role,
            max_active_sessions: userForm.max_active_sessions,
            group_id: userForm.group_id,
            default_store_id: userForm.default_store_id || null,
          }),
        });
      }
      setShowUserForm(false);
      setEditingUser(null);
      setUserFormError(null);
      await loadUsers();
    } catch (e) {
      setUserFormError(e instanceof Error ? e.message : "Falha ao salvar usuario");
    } finally {
      setUsersLoading(false);
    }
  }

  async function toggleUser(user: UserRow) {
    try {
      setUsersLoading(true);
      await adminFetch(`/admin/users/${user.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !user.is_active }),
      });
      await loadUsers();
    } catch (e) {
      setUsersError(e instanceof Error ? e.message : "Falha ao atualizar status");
    } finally {
      setUsersLoading(false);
    }
  }

  async function startFirstAccessTest() {
    try {
      setStartingFirstAccessTest(true);
      setUserFormError(null);
      await adminFetch("/admin/onboarding/test-enable", { method: "POST" });
      window.location.href = "/portal/primeiro-acesso";
    } catch (e) {
      setUserFormError(e instanceof Error ? e.message : "Falha ao iniciar teste de primeiro acesso");
    } finally {
      setStartingFirstAccessTest(false);
    }
  }

  function toggleGroupStore(storeId: string) {
    setGroupForm((prev) => {
      const has = prev.store_ids.includes(storeId);
      return {
        ...prev,
        store_ids: has ? prev.store_ids.filter((item) => item !== storeId) : [...prev.store_ids, storeId],
      };
    });
  }

  function toggleGroupPermission(moduleKey: string) {
    setGroupForm((prev) => {
      const has = prev.permissions.includes(moduleKey);
      return {
        ...prev,
        permissions: has
          ? prev.permissions.filter((item) => item !== moduleKey)
          : [...prev.permissions, moduleKey],
      };
    });
  }

  useEffect(() => {
    loadUsers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <>
      {usersError && <p className="text-sm text-red-500">{usersError}</p>}

      <section className="rounded-2xl bg-white border border-slate-200 p-3 sm:p-4 flex flex-wrap gap-4 items-center justify-between">
        <div className="space-y-1">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-600">Licencas</p>
          <h3 className="text-xl font-semibold">{licenses ? `${licenses.used}/${licenses.limit}` : "..."}</h3>
          <p className="text-xs text-slate-600">
            Plano ativo: {groupOptions.active_plan_name ?? "Nao identificado"}
          </p>
        </div>
        <div className="flex gap-2 items-center">
          <button
            onClick={openCreateUser}
            disabled={!canCreate || usersLoading || groups.length === 0}
            className="w-full sm:w-auto px-4 py-2 rounded-lg bg-[#6320ee] text-white text-sm font-semibold active:scale-95 disabled:opacity-50"
          >
            {canCreate ? "Adicionar usuario" : "Limite atingido"}
          </button>
          <button
            onClick={openCreateGroup}
            disabled={usersLoading}
            className="w-full sm:w-auto px-4 py-2 rounded-lg bg-white border border-slate-200 text-slate-800 text-sm font-semibold active:scale-95"
          >
            Novo grupo
          </button>
        </div>
      </section>

      <section className="rounded-2xl bg-white border border-slate-200 p-3 sm:p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Grupos de permissao</h2>
          {usersLoading && <span className="text-xs text-slate-600">Atualizando...</span>}
        </div>

        {groups.length === 0 ? (
          <p className="text-sm text-slate-600">Nenhum grupo cadastrado.</p>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-50">
            <table className="w-full text-xs sm:text-sm min-w-[760px]">
              <thead className="bg-slate-100 text-left">
                <tr>
                  <th className="px-3 sm:px-4 py-2">Grupo</th>
                  <th className="px-3 sm:px-4 py-2">Permissoes</th>
                  <th className="px-3 sm:px-4 py-2">Lojas</th>
                  <th className="px-3 sm:px-4 py-2">Usuarios</th>
                  <th className="px-3 sm:px-4 py-2">Status</th>
                  <th className="px-3 sm:px-4 py-2 text-right">Acoes</th>
                </tr>
              </thead>
              <tbody>
                {groups.map((group, idx) => (
                  <tr key={group.id} className={idx % 2 === 0 ? "bg-transparent" : "bg-slate-50"}>
                    <td className="px-3 sm:px-4 py-2 font-medium">{group.name}</td>
                    <td className="px-3 sm:px-4 py-2">{group.permissions.length}</td>
                    <td className="px-3 sm:px-4 py-2">{group.store_ids.length || groupOptions.stores.length}</td>
                    <td className="px-3 sm:px-4 py-2">{group.users_count}</td>
                    <td className="px-3 sm:px-4 py-2">
                      <span
                        className={`px-2 py-1 rounded-full text-xs ${
                          group.is_active ? "bg-emerald-200 text-emerald-800" : "bg-amber-200 text-amber-800"
                        }`}
                      >
                        {group.is_active ? "Ativo" : "Inativo"}
                      </span>
                    </td>
                    <td className="px-3 sm:px-4 py-2 text-right">
                      <div className="flex gap-2 justify-end">
                        <button
                          onClick={() => openEditGroup(group)}
                          className="px-3 py-1 rounded-lg bg-[#6320ee] text-white text-xs hover:brightness-95"
                        >
                          Editar
                        </button>
                        <button
                          onClick={() => deleteGroup(group)}
                          className="px-3 py-1 rounded-lg bg-slate-100 border border-slate-200 text-xs"
                        >
                          Excluir
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="rounded-2xl bg-white border border-slate-200 p-3 sm:p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Usuarios</h2>
          {usersLoading && <span className="text-xs text-slate-600">Atualizando...</span>}
        </div>

        {users.length === 0 ? (
          <p className="text-sm text-slate-600">Nenhum usuario.</p>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-50">
            <table className="w-full text-xs sm:text-sm min-w-[920px]">
              <thead className="bg-slate-100 text-left">
                <tr>
                  <th className="px-3 sm:px-4 py-2">Nome</th>
                  <th className="px-3 sm:px-4 py-2">Email</th>
                  <th className="px-3 sm:px-4 py-2">Perfil</th>
                  <th className="px-3 sm:px-4 py-2">Grupo</th>
                  <th className="px-3 sm:px-4 py-2">Loja padrao</th>
                  <th className="px-3 sm:px-4 py-2">Sessoes</th>
                  <th className="px-3 sm:px-4 py-2">Status</th>
                  <th className="px-3 sm:px-4 py-2 text-right">Acoes</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user, idx) => {
                  const group = user.group_id ? groupById.get(user.group_id) : null;
                  const store = user.default_store_id ? storeById.get(user.default_store_id) : null;
                  return (
                    <tr key={user.id} className={idx % 2 === 0 ? "bg-transparent" : "bg-slate-50"}>
                      <td className="px-3 sm:px-4 py-2">{user.name}</td>
                      <td className="px-3 sm:px-4 py-2">{user.email}</td>
                      <td className="px-3 sm:px-4 py-2">{ROLE_LABEL[user.role] ?? user.role}</td>
                      <td className="px-3 sm:px-4 py-2">{group?.name ?? "-"}</td>
                      <td className="px-3 sm:px-4 py-2">{store?.name ?? "-"}</td>
                      <td className="px-3 sm:px-4 py-2">{user.max_active_sessions ?? 3}</td>
                      <td className="px-3 sm:px-4 py-2">
                        <span
                          className={`px-2 py-1 rounded-full text-xs ${
                            user.is_active ? "bg-emerald-200 text-emerald-800" : "bg-amber-200 text-amber-800"
                          }`}
                        >
                          {user.is_active ? "Ativo" : "Inativo"}
                        </span>
                      </td>
                      <td className="px-3 sm:px-4 py-2 text-right">
                        <div className="flex gap-2 justify-end">
                          <button
                            onClick={() => openEditUser(user)}
                            className="px-3 py-1 rounded-lg bg-[#6320ee] text-white text-xs hover:brightness-95"
                          >
                            Editar
                          </button>
                          <button
                            onClick={() => toggleUser(user)}
                            className="px-3 py-1 rounded-lg bg-slate-100 border border-slate-200 text-xs"
                          >
                            {user.is_active ? "Inativar" : "Ativar"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {showGroupForm && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-900/90 backdrop-blur-sm px-4">
          <div
            role="dialog"
            aria-modal="true"
            className="w-full max-w-3xl rounded-3xl bg-white border border-slate-200 shadow-2xl shadow-slate-200/80 p-6 space-y-4 text-slate-900"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-600">
                  {editingGroup ? "Editar" : "Criar"} grupo
                </p>
                <h2 className="text-2xl font-semibold">{editingGroup ? editingGroup.name : "Novo grupo"}</h2>
              </div>
              <button
                onClick={() => {
                  setShowGroupForm(false);
                  setEditingGroup(null);
                }}
                className="text-sm px-3 py-1 rounded-full bg-slate-100 border border-slate-200 hover:bg-slate-200"
              >
                Fechar
              </button>
            </div>

            <div className="grid md:grid-cols-2 gap-4 text-sm">
              <label className="space-y-1 md:col-span-2">
                <span>Nome do grupo</span>
                <input
                  className="input w-full"
                  value={groupForm.name}
                  onChange={(e) => setGroupForm({ ...groupForm, name: e.target.value })}
                />
              </label>

              <div className="space-y-2">
                <span className="font-semibold">Permissoes por modulo</span>
                <div className="max-h-48 overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-3 space-y-2">
                  {groupOptions.modules.length === 0 ? (
                    <p className="text-xs text-slate-500">Nenhum modulo ativo no plano.</p>
                  ) : (
                    <>
                      {scopedModules.map((moduleKey) => (
                        <label key={moduleKey} className="flex items-center justify-between gap-2 text-xs">
                          <span>{MODULE_LABEL[moduleKey] ?? moduleKey}</span>
                          <select
                            className="input h-8 w-44 text-xs"
                            value={getModuleAccessLevel(groupForm.permissions, moduleKey)}
                            onChange={(e) =>
                              setGroupForm((prev) => ({
                                ...prev,
                                permissions: setModuleAccessLevel(
                                  prev.permissions,
                                  moduleKey,
                                  e.target.value as AccessLevel
                                ),
                              }))
                            }
                          >
                            {ACCESS_LEVEL_OPTIONS.map((option) => (
                              <option key={`${moduleKey}-${option.value}`} value={option.value}>
                                {option.label}
                              </option>
                            ))}
                          </select>
                        </label>
                      ))}
                      {checkboxModules.map((moduleKey) => (
                        <label key={moduleKey} className="flex items-center gap-2 text-xs">
                          <input
                            type="checkbox"
                            checked={groupForm.permissions.includes(moduleKey)}
                            onChange={() => toggleGroupPermission(moduleKey)}
                          />
                          <span>{MODULE_LABEL[moduleKey] ?? moduleKey}</span>
                        </label>
                      ))}
                    </>
                  )}
                </div>
              </div>

              <div className="space-y-2">
                <span className="font-semibold">Lojas do grupo</span>
                <div className="max-h-48 overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-3 space-y-2">
                  {groupOptions.stores.length === 0 ? (
                    <p className="text-xs text-slate-500">Nenhuma loja cadastrada.</p>
                  ) : (
                    groupOptions.stores.map((store) => (
                      <label key={store.id} className="flex items-center gap-2 text-xs">
                        <input
                          type="checkbox"
                          checked={groupForm.store_ids.includes(store.id)}
                          onChange={() => toggleGroupStore(store.id)}
                        />
                        <span>{store.name}</span>
                      </label>
                    ))
                  )}
                </div>
              </div>

              <label className="flex items-center gap-2 text-sm md:col-span-2">
                <input
                  type="checkbox"
                  checked={groupForm.is_active}
                  onChange={(e) => setGroupForm({ ...groupForm, is_active: e.target.checked })}
                />
                <span>Grupo ativo</span>
              </label>
            </div>

            <div className="flex items-center justify-end gap-3">
              <button
                onClick={() => {
                  setShowGroupForm(false);
                  setEditingGroup(null);
                }}
                className="px-4 py-2 rounded-lg bg-slate-100 text-slate-900 text-sm font-semibold active:scale-95"
              >
                Cancelar
              </button>
              <button
                onClick={saveGroup}
                disabled={usersLoading || !groupForm.name.trim()}
                className="px-4 py-2 rounded-lg bg-[#6320ee] text-white text-sm font-semibold active:scale-95 disabled:opacity-60"
              >
                Salvar grupo
              </button>
            </div>
          </div>
        </div>
      )}

      {showUserForm && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-900/90 backdrop-blur-sm px-4">
          <div
            role="dialog"
            aria-modal="true"
            className="w-full max-w-xl rounded-3xl bg-white border border-slate-200 shadow-2xl shadow-slate-200/80 p-6 space-y-4 text-slate-900"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-600">
                  {editingUser ? "Editar" : "Criar"} usuario
                </p>
                <h2 className="text-2xl font-semibold">{editingUser ? editingUser.name : "Novo usuario"}</h2>
              </div>
              <button
                onClick={() => {
                  setShowUserForm(false);
                  setEditingUser(null);
                  setUserFormError(null);
                }}
                className="text-sm px-3 py-1 rounded-full bg-slate-100 border border-slate-200 hover:bg-slate-200"
              >
                Fechar
              </button>
            </div>

            {userFormError && <p className="text-sm text-red-500">{userFormError}</p>}

            <div className="grid md:grid-cols-2 gap-3 text-sm">
              <label className="space-y-1">
                <span>Nome</span>
                <input
                  className="input w-full"
                  value={userForm.name}
                  onChange={(e) => setUserForm({ ...userForm, name: e.target.value })}
                />
              </label>
              <label className="space-y-1">
                <span>Email</span>
                <input
                  className="input w-full"
                  value={userForm.email}
                  onChange={(e) => setUserForm({ ...userForm, email: e.target.value })}
                />
              </label>
              <label className="space-y-1">
                <span>Perfil</span>
                <select
                  className="input w-full"
                  value={userForm.role}
                  onChange={(e) => setUserForm({ ...userForm, role: e.target.value })}
                >
                  <option value="owner">Administrador</option>
                  <option value="manager">Gerente</option>
                  <option value="operator">Operador</option>
                </select>
              </label>
              <label className="space-y-1">
                <span>{editingUser ? "Nova senha (opcional)" : "Senha"}</span>
                <input
                  type="password"
                  className="input w-full"
                  value={userForm.password}
                  onChange={(e) => setUserForm({ ...userForm, password: e.target.value })}
                  placeholder={editingUser ? "Deixe em branco para manter" : undefined}
                />
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
                    setUserForm({
                      ...userForm,
                      max_active_sessions: Number(e.target.value),
                    })
                  }
                />
              </label>

              <label className="space-y-1 md:col-span-2">
                <span>Grupo de permissoes</span>
                <select
                  className="input w-full"
                  value={userForm.group_id}
                  onChange={(e) => {
                    const groupId = e.target.value;
                    const group = groupById.get(groupId);
                    const allowedStores = !group?.store_ids?.length
                      ? groupOptions.stores
                      : groupOptions.stores.filter((store) => group.store_ids.includes(store.id));
                    setUserForm((prev) => ({
                      ...prev,
                      group_id: groupId,
                      default_store_id: allowedStores.some((store) => store.id === prev.default_store_id)
                        ? prev.default_store_id
                        : (allowedStores[0]?.id ?? ""),
                    }));
                  }}
                >
                  <option value="">Selecione um grupo</option>
                  {groups.map((group) => (
                    <option key={group.id} value={group.id}>
                      {group.name}
                    </option>
                  ))}
                </select>
              </label>

              <label className="space-y-1 md:col-span-2">
                <span>Loja padrao</span>
                <select
                  className="input w-full"
                  value={userForm.default_store_id}
                  onChange={(e) => setUserForm({ ...userForm, default_store_id: e.target.value })}
                >
                  <option value="">Sem loja</option>
                  {availableStoresForUser.map((store) => (
                    <option key={store.id} value={store.id}>
                      {store.name}
                    </option>
                  ))}
                </select>
              </label>

              {editingUser && (
                <label className="flex items-center gap-2 text-sm mt-2 md:col-span-2">
                  <input
                    type="checkbox"
                    className="h-4 w-4"
                    checked={userForm.is_active}
                    onChange={(e) => setUserForm({ ...userForm, is_active: e.target.checked })}
                  />
                  <span>Ativo</span>
                </label>
              )}
            </div>

            <div className="flex items-center justify-end gap-3">
              <button
                onClick={startFirstAccessTest}
                disabled={usersLoading || startingFirstAccessTest}
                className="px-4 py-2 rounded-lg bg-white border border-slate-200 text-slate-900 text-sm font-semibold active:scale-95 disabled:opacity-60"
              >
                {startingFirstAccessTest ? "Abrindo..." : "Testar primeiro acesso"}
              </button>
              <button
                onClick={() => {
                  setShowUserForm(false);
                  setEditingUser(null);
                  setUserFormError(null);
                }}
                className="px-4 py-2 rounded-lg bg-slate-100 text-slate-900 text-sm font-semibold active:scale-95"
              >
                Cancelar
              </button>
              <button
                onClick={saveUser}
                disabled={usersLoading || startingFirstAccessTest || !userForm.group_id || (!editingUser && !userForm.password)}
                className="px-4 py-2 rounded-lg bg-[#6320ee] text-white text-sm font-semibold active:scale-95 disabled:opacity-60"
              >
                Salvar
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
