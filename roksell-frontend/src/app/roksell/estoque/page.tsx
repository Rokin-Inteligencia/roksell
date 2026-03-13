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

type StatusFilter = "active" | "inactive" | "all";

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
  const [filter, setFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("active");
  const [filterOpen, setFilterOpen] = useState(false);

  const [moveModalOpen, setMoveModalOpen] = useState(false);
  const [moveItem, setMoveItem] = useState<StoreInventoryItem | null>(null);
  const [moveOperation, setMoveOperation] = useState<"add" | "subtract">("add");
  const [moveQuantity, setMoveQuantity] = useState<number>(1);
  const [moveSubmitting, setMoveSubmitting] = useState(false);

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
      const params = new URLSearchParams({ store_id: storeId, status: statusFilter });
      const data = await adminFetch<StoreInventoryItem[]>(`/admin/inventory?${params.toString()}`);
      setInventory(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao carregar estoque");
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    if (ready && modulesReady && moduleAllowed) loadStores();
  }, [ready, modulesReady, moduleAllowed, loadStores]);

  useEffect(() => {
    if (ready && modulesReady && moduleAllowed && selectedStoreId) loadInventory(selectedStoreId);
  }, [selectedStoreId, ready, modulesReady, moduleAllowed, statusFilter, loadInventory]);

  const filteredInventory = useMemo(() => {
    const term = filter.toLowerCase().trim();
    if (!term) return inventory;
    return inventory.filter(
      (item) =>
        item.product_name?.toLowerCase().includes(term) ||
        (item.product_code && item.product_code.toLowerCase().includes(term))
    );
  }, [inventory, filter]);

  function openMoveModal(item: StoreInventoryItem) {
    setMoveItem(item);
    setMoveOperation("add");
    setMoveQuantity(1);
    setMoveModalOpen(true);
  }

  async function submitMove() {
    if (!canEditInventory || !selectedStoreId || !moveItem) return;
    if (moveQuantity < 1) {
      setError("Informe uma quantidade válida.");
      return;
    }
    if (moveOperation === "subtract" && moveQuantity > moveItem.quantity) {
      setError("Quantidade a subtrair não pode ser maior que o estoque atual.");
      return;
    }
    setMoveSubmitting(true);
    setError(null);
    try {
      await adminFetch("/admin/inventory/move", {
        method: "POST",
        body: JSON.stringify({
          store_id: selectedStoreId,
          product_id: moveItem.product_id,
          operation: moveOperation,
          quantity: moveQuantity,
        }),
      });
      setMoveModalOpen(false);
      setMoveItem(null);
      await loadInventory(selectedStoreId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao registrar movimentação");
    } finally {
      setMoveSubmitting(false);
    }
  }

  if (!ready) return null;

  const sidebarItems = adminMenuWithHome;

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
                  Selecione uma loja e realize movimentações de entrada ou saída. Cada venda desconta do estoque da loja escolhida no checkout.
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
                    <div className="space-y-1 text-sm flex flex-col">
                      <span>Buscar</span>
                      <div className="flex items-center gap-2">
                        <input
                          className="input flex-1"
                          placeholder="Nome ou código do produto..."
                          value={filter}
                          onChange={(e) => setFilter(e.target.value)}
                        />
                        <div className="relative">
                          <button
                            type="button"
                            onClick={() => setFilterOpen((o) => !o)}
                            className="p-2 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-100"
                            aria-label="Filtro por status"
                            aria-expanded={filterOpen}
                          >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
                            </svg>
                          </button>
                          {filterOpen && (
                            <div className="absolute right-0 top-full mt-1 z-10 rounded-xl border border-slate-200 bg-white p-3 shadow-lg min-w-[160px] space-y-2">
                              <p className="text-xs font-medium text-slate-600">Status do produto</p>
                              <button
                                type="button"
                                onClick={() => { setStatusFilter("active"); setFilterOpen(false); }}
                                className={`block w-full text-left px-3 py-2 rounded-lg text-sm ${statusFilter === "active" ? "bg-[#6320ee] text-white" : "hover:bg-slate-50 text-slate-700"}`}
                              >
                                Ativos
                              </button>
                              <button
                                type="button"
                                onClick={() => { setStatusFilter("all"); setFilterOpen(false); }}
                                className={`block w-full text-left px-3 py-2 rounded-lg text-sm ${statusFilter === "all" ? "bg-[#6320ee] text-white" : "hover:bg-slate-50 text-slate-700"}`}
                              >
                                Todos
                              </button>
                              <button
                                type="button"
                                onClick={() => { setStatusFilter("inactive"); setFilterOpen(false); }}
                                className={`block w-full text-left px-3 py-2 rounded-lg text-sm ${statusFilter === "inactive" ? "bg-[#6320ee] text-white" : "hover:bg-slate-50 text-slate-700"}`}
                              >
                                Inativos
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </section>

                <section className="rounded-2xl bg-white border border-slate-200 p-3 sm:p-4 space-y-3">
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div>
                      <h2 className="text-lg font-semibold">Produtos</h2>
                      <p className="text-sm text-slate-600 italic">
                        {filteredInventory.length} produto{filteredInventory.length !== 1 ? "s" : ""}
                      </p>
                    </div>
                    {loading && <span className="text-xs text-slate-600">Atualizando...</span>}
                  </div>
                  {filteredInventory.length === 0 ? (
                    <p className="text-sm text-slate-600">Nenhum produto encontrado.</p>
                  ) : (
                    <>
                      <div className="space-y-3 sm:hidden">
                        {filteredInventory.map((item) => (
                          <div key={item.product_id} className="rounded-xl border border-slate-200 bg-slate-50 p-3 space-y-2">
                            <div className="flex items-center gap-3">
                              {item.product_image_url ? (
                                <div className="w-12 h-12 rounded-lg overflow-hidden bg-slate-200 shrink-0">
                                  {/* eslint-disable-next-line @next/next/no-img-element */}
                                  <img
                                    src={item.product_image_url}
                                    alt=""
                                    className="w-full h-full object-cover"
                                  />
                                </div>
                              ) : (
                                <div className="w-12 h-12 rounded-lg bg-slate-200 shrink-0 flex items-center justify-center text-slate-400 text-xs">
                                  —
                                </div>
                              )}
                              <div className="min-w-0 flex-1">
                                <p className="text-xs text-slate-500">{item.product_code ?? "—"}</p>
                                <p className="text-sm font-semibold text-slate-900 truncate">{item.product_name || item.product_id}</p>
                              </div>
                            </div>
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-sm text-slate-600">
                                {item.quantity} {item.unit_of_measure || "un"}
                              </span>
                              {canEditInventory && (
                                <button
                                  type="button"
                                  onClick={() => openMoveModal(item)}
                                  className="p-2 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-100"
                                  aria-label="Movimentar estoque"
                                  title="Movimentar estoque"
                                >
                                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
                                  </svg>
                                </button>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                      <div className="hidden sm:block">
                        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-50">
                          <table className="w-full text-xs sm:text-sm min-w-[520px]">
                            <thead className="bg-slate-100 text-left">
                              <tr>
                                <th className="px-3 sm:px-4 py-2 w-[72px]">Foto</th>
                                <th className="px-3 sm:px-4 py-2 w-20">Código</th>
                                <th className="px-3 sm:px-4 py-2">Produto</th>
                                <th className="px-3 sm:px-4 py-2 w-40">Estoque</th>
                              </tr>
                            </thead>
                            <tbody>
                              {filteredInventory.map((item, idx) => (
                                <tr key={item.product_id} className={idx % 2 === 0 ? "bg-transparent" : "bg-slate-50"}>
                                  <td className="px-3 sm:px-4 py-2">
                                    {item.product_image_url ? (
                                      <div className="w-12 h-12 rounded-lg overflow-hidden bg-slate-200">
                                        {/* eslint-disable-next-line @next/next/no-img-element */}
                                        <img
                                          src={item.product_image_url}
                                          alt=""
                                          className="w-full h-full object-cover"
                                        />
                                      </div>
                                    ) : (
                                      <div className="w-12 h-12 rounded-lg bg-slate-200 flex items-center justify-center text-slate-400 text-xs">
                                        —
                                      </div>
                                    )}
                                  </td>
                                  <td className="px-3 sm:px-4 py-2 font-mono text-slate-700">{item.product_code ?? "—"}</td>
                                  <td className="px-3 sm:px-4 py-2">{item.product_name || item.product_id}</td>
                                  <td className="px-3 sm:px-4 py-2">
                                    <div className="flex items-center gap-2">
                                      <span className="text-slate-700">
                                        {item.quantity} {item.unit_of_measure || "un"}
                                      </span>
                                      {canEditInventory && (
                                        <button
                                          type="button"
                                          onClick={() => openMoveModal(item)}
                                          className="p-2 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-100"
                                          aria-label="Movimentar estoque"
                                          title="Movimentar estoque"
                                        >
                                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
                                          </svg>
                                        </button>
                                      )}
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
              </>
            )}
          </div>
        </div>
      </div>

      {moveModalOpen && moveItem && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center px-4">
          <section className="w-full max-w-sm rounded-2xl bg-white border border-slate-200 p-5 shadow-xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-slate-900">Movimentação de estoque</h3>
              <button
                type="button"
                onClick={() => { setMoveModalOpen(false); setMoveItem(null); }}
                className="p-1 rounded-lg text-slate-500 hover:bg-slate-100"
                aria-label="Fechar"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"> <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /> </svg>
              </button>
            </div>
            <p className="text-sm text-slate-600">
              {moveItem.product_name || moveItem.product_id} — Estoque atual: {moveItem.quantity} {moveItem.unit_of_measure || "un"}
            </p>
            <div className="space-y-2">
              <label className="block text-sm font-medium text-slate-700">Tipo de operação</label>
              <select
                className="input w-full"
                value={moveOperation}
                onChange={(e) => setMoveOperation(e.target.value as "add" | "subtract")}
              >
                <option value="add">Adição (entrada)</option>
                <option value="subtract">Subtração (saída)</option>
              </select>
            </div>
            <div className="space-y-2">
              <label className="block text-sm font-medium text-slate-700">Quantidade</label>
              <input
                type="number"
                min={1}
                max={moveOperation === "subtract" ? moveItem.quantity : undefined}
                className="input w-full"
                value={moveQuantity}
                onChange={(e) => setMoveQuantity(Math.max(0, parseInt(e.target.value, 10) || 0))}
              />
            </div>
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => { setMoveModalOpen(false); setMoveItem(null); }}
                className="px-3 py-2 rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={submitMove}
                disabled={moveSubmitting || moveQuantity < 1 || (moveOperation === "subtract" && moveQuantity > moveItem.quantity)}
                className="px-3 py-2 rounded-lg bg-[#6320ee] text-white font-medium hover:brightness-95 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {moveSubmitting ? "Salvando..." : "Confirmar"}
              </button>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}
