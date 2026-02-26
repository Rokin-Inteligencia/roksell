"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { adminFetch } from "@/lib/admin-api";
import { useAdminGuard } from "@/lib/use-admin-guard";
import { AdminSidebar } from "@/components/admin/AdminSidebar";
import { adminMenuWithHome } from "@/config/adminMenu";
import { usePathname } from "next/navigation";
import { ProfileBadge } from "@/components/admin/ProfileBadge";
import { useOrgName } from "@/lib/use-org-name";
import { Store, StoreInventoryItem } from "@/types";
import { useTenantModules } from "@/lib/use-tenant-modules";

export default function InventoryAdminPage() {
  const ready = useAdminGuard();
  const tenantName = useOrgName();
  const pathname = usePathname();
  const { hasModule, hasModuleAction, ready: modulesReady } = useTenantModules();
  const moduleAllowed = hasModule("inventory");
  const moduleBlocked = modulesReady && !moduleAllowed;
  const canEditInventory = hasModuleAction("inventory", "edit");

  const [stores, setStores] = useState<Store[]>([]);
  const [selectedStoreId, setSelectedStoreId] = useState<string>("");
  const [inventory, setInventory] = useState<StoreInventoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, number>>({});
  const [filter, setFilter] = useState("");

  const loadStores = useCallback(async () => {
    try {
      const list = await adminFetch<Store[]>("/admin/inventory/stores");
      setStores(list);
      if (!selectedStoreId && list.length > 0) {
        setSelectedStoreId(list[0].id);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao carregar lojas");
    }
  }, [selectedStoreId]);

  const loadInventory = useCallback(async (storeId: string) => {
    if (!storeId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await adminFetch<StoreInventoryItem[]>(`/admin/inventory?store_id=${storeId}`);
      setInventory(data);
      setDrafts({});
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao carregar estoque");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (ready && modulesReady && moduleAllowed) loadStores();
  }, [ready, modulesReady, moduleAllowed, loadStores]);

  useEffect(() => {
    if (ready && modulesReady && moduleAllowed && selectedStoreId) loadInventory(selectedStoreId);
  }, [selectedStoreId, ready, modulesReady, moduleAllowed, loadInventory]);

  const pendingUpdates = useMemo(() => {
    const inventoryMap = new Map(inventory.map((item) => [item.product_id, item.quantity]));
    return Object.entries(drafts)
      .map(([productId, quantity]) => ({
        productId,
        quantity,
        original: inventoryMap.get(productId),
      }))
      .filter((item) => typeof item.original === "number" && item.quantity !== item.original);
  }, [drafts, inventory]);

  async function saveAll() {
    if (!canEditInventory) return;
    if (!selectedStoreId) return;
    if (pendingUpdates.length === 0) {
      setError("Nenhuma alteração pendente.");
      return;
    }
    try {
      setLoading(true);
      setError(null);
      await Promise.all(
        pendingUpdates.map((item) =>
          adminFetch("/admin/inventory", {
            method: "POST",
            body: JSON.stringify({
              store_id: selectedStoreId,
              product_id: item.productId,
              quantity: Number(item.quantity),
            }),
          })
        )
      );
      await loadInventory(selectedStoreId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao salvar estoque");
    } finally {
      setLoading(false);
    }
  }

  const filteredInventory = useMemo(() => {
    const term = filter.toLowerCase();
    return inventory.filter((item) => item.product_name?.toLowerCase().includes(term));
  }, [inventory, filter]);

  if (!ready) return null;

  const sidebarItems = adminMenuWithHome;
  const currentStore = stores.find((s) => s.id === selectedStoreId);

  return (
    <main className="min-h-screen text-slate-900 bg-[#f5f3ff]">
      <div className="max-w-7xl w-full mx-auto px-3 sm:px-4 lg:px-6 py-8">
        <div className="grid gap-6 lg:grid-cols-[260px_minmax(0,1fr)] items-start">
          <AdminSidebar menu={sidebarItems} currentPath={pathname} collapsible orgName={tenantName} />

          <div className="space-y-6">
            <header className="flex flex-wrap items-center justify-between gap-3">
              <div className="text-slate-900 space-y-1">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-600">Admin - Estoque</p>
                <h1 className="text-3xl font-semibold">Estoque por loja</h1>
                <p className="text-sm text-slate-600">
                  Selecione uma loja e ajuste o saldo de cada produto. Cada venda desconta do estoque da loja escolhida no checkout.
                </p>
              </div>
              <ProfileBadge />
            </header>

            {moduleBlocked ? (
              <section className="rounded-2xl bg-white border border-slate-200 p-4 space-y-2">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Modulo inativo</p>
                <h2 className="text-lg font-semibold">Estoque indisponivel</h2>
                <p className="text-sm text-slate-600">
                  Este modulo nao esta habilitado para a sua empresa. Fale com o administrador para liberar o acesso.
                </p>
              </section>
            ) : (
              <>
                {error && <p className="text-sm text-red-500">{error}</p>}

                <section className="rounded-2xl bg-white border border-slate-200 p-3 sm:p-4 space-y-3">
                  <div className="grid sm:grid-cols-2 gap-3">
                    <label className="space-y-1 text-sm">
                      <span>Loja</span>
                      <select
                        className="input w-full"
                        value={selectedStoreId}
                        onChange={(e) => setSelectedStoreId(e.target.value)}
                      >
                        {stores.map((store) => (
                          <option key={store.id} value={store.id}>
                            {store.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="space-y-1 text-sm">
                      <span>Buscar produto</span>
                      <input
                        className="input w-full"
                        placeholder="Digite o nome..."
                        value={filter}
                        onChange={(e) => setFilter(e.target.value)}
                      />
                    </label>
                  </div>
                  {currentStore && (
                    <div className="text-xs text-slate-600">
                      {currentStore.is_delivery ? "Entrega habilitada" : "Apenas retirada"} |{" "}
                      {currentStore.city ? `${currentStore.city}/${currentStore.state ?? ""}` : "Cidade nao informada"}
                    </div>
                  )}
                </section>

                <section className="rounded-2xl bg-white border border-slate-200 p-3 sm:p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <h2 className="text-lg font-semibold">Produtos ({filteredInventory.length})</h2>
                    <div className="flex items-center gap-3">
                      {pendingUpdates.length > 0 && (
                        <span className="text-xs text-slate-600">{pendingUpdates.length} alteracoe(s)</span>
                      )}
                      <button
                        onClick={saveAll}
                        disabled={!canEditInventory || loading || pendingUpdates.length === 0}
                        className="px-3 py-1 rounded-lg bg-[#6320ee] text-white text-xs hover:brightness-95 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        Salvar
                      </button>
                      {loading && <span className="text-xs text-slate-600">Atualizando...</span>}
                    </div>
                  </div>
                  {filteredInventory.length === 0 ? (
                    <p className="text-sm text-slate-600">Nenhum produto ativo.</p>
                  ) : (
                    <>
                      <div className="space-y-3 sm:hidden">
                        {filteredInventory.map((item) => (
                          <div key={item.product_id} className="rounded-xl border border-slate-200 bg-slate-50 p-3 space-y-2">
                            <p className="text-sm font-semibold text-slate-900">{item.product_name || item.product_id}</p>
                            <label className="space-y-1 text-xs text-slate-600">
                              <span>Quantidade</span>
                              <input
                                type="number"
                                className="input w-full text-sm"
                                value={drafts[item.product_id] ?? item.quantity}
                                disabled={!canEditInventory}
                                onChange={(e) =>
                                  setDrafts((prev) => ({
                                    ...prev,
                                    [item.product_id]: Number(e.target.value),
                                  }))
                                }
                              />
                            </label>
                          </div>
                        ))}
                      </div>
                      <div className="hidden sm:block">
                        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-50">
                          <table className="w-full text-xs sm:text-sm min-w-[520px]">
                            <thead className="bg-slate-100 text-left">
                              <tr>
                                <th className="px-3 sm:px-4 py-2">Produto</th>
                                <th className="px-3 sm:px-4 py-2 w-32">Quantidade</th>
                              </tr>
                            </thead>
                            <tbody>
                              {filteredInventory.map((item, idx) => (
                                <tr key={item.product_id} className={idx % 2 === 0 ? "bg-transparent" : "bg-slate-50"}>
                                  <td className="px-3 sm:px-4 py-2">{item.product_name || item.product_id}</td>
                                  <td className="px-3 sm:px-4 py-2">
                                    <input
                                      type="number"
                                      className="input w-full"
                                      value={drafts[item.product_id] ?? item.quantity}
                                      disabled={!canEditInventory}
                                      onChange={(e) =>
                                        setDrafts((prev) => ({
                                          ...prev,
                                          [item.product_id]: Number(e.target.value),
                                        }))
                                      }
                                    />
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
    </main>
  );
}


