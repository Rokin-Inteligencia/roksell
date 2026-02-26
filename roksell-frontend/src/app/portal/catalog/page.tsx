"use client";
import { useEffect, useMemo, useState } from "react";
import { adminFetch, adminUpload } from "@/lib/admin-api";
import { useAdminGuard } from "@/lib/use-admin-guard";
import { Additional, Category, Product } from "@/types";
import { ProfileBadge } from "@/components/admin/ProfileBadge";
import { AdminSidebar } from "@/components/admin/AdminSidebar";
import { adminMenuWithHome } from "@/config/adminMenu";
import { usePathname } from "next/navigation";
import { useOrgName } from "@/lib/use-org-name";
import { clearAdminToken } from "@/lib/admin-auth";
import { useTenantModules } from "@/lib/use-tenant-modules";

type ModalMode = "product" | "category" | "additional";
type AvailabilityStatus = "available" | "order" | "unavailable";

const PAGE_SIZE = 10;
const UNCATEGORIZED_ID = "uncategorized";
type CatalogResponse = {
  categories: Category[];
  products: Product[];
  additionals?: Additional[];
  selected_store_id?: string | null;
};
type StoreOption = {
  id: string;
  name: string;
  slug?: string;
};
type GroupOptionsResponse = {
  stores: StoreOption[];
};

export default function CatalogAdmin() {
  const ready = useAdminGuard();
  const tenantName = useOrgName();
  const pathname = usePathname();
  const { hasModule, hasModuleAction, ready: modulesReady } = useTenantModules();
  const moduleAllowed = hasModule("products");
  const moduleBlocked = modulesReady && !moduleAllowed;
  const canEditProducts = hasModuleAction("products", "edit");
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

  const [categories, setCategories] = useState<Category[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [additionals, setAdditionals] = useState<Additional[]>([]);
  const [stores, setStores] = useState<StoreOption[]>([]);
  const [selectedStoreId, setSelectedStoreId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [blockingDeleteMessage, setBlockingDeleteMessage] = useState<string | null>(null);
  const [quickSuccessMessage, setQuickSuccessMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [productSearch, setProductSearch] = useState("");
  const [categoryPage, setCategoryPage] = useState(1);
  const [productStatusFilter, setProductStatusFilter] = useState<"active" | "inactive" | "all">("active");
  const [productFilterOpen, setProductFilterOpen] = useState(false);
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());

  const [modalOpen, setModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<ModalMode>("product");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [modalData, setModalData] = useState({
    name: "",
    description: "",
    price_cents: 0,
    category_id: "",
    additionals_enabled: false,
    additional_ids: [] as string[],
    is_active: true,
    is_custom: false,
    availability_status: "available" as AvailabilityStatus,
    display_order: 0,
  });
  const [additionalLinkPromptOpen, setAdditionalLinkPromptOpen] = useState(false);
  const [additionalToLink, setAdditionalToLink] = useState<Additional | null>(null);
  const [selectedProductIdsForAdditional, setSelectedProductIdsForAdditional] = useState<string[]>([]);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [currentImageUrl, setCurrentImageUrl] = useState<string | null>(null);
  const [removeImage, setRemoveImage] = useState(false);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [videoPreview, setVideoPreview] = useState<string | null>(null);
  const [currentVideoUrl, setCurrentVideoUrl] = useState<string | null>(null);
  const [removeVideo, setRemoveVideo] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const options = await adminFetch<GroupOptionsResponse>("/admin/groups/options");
      const storeList = options.stores || [];
      setStores(storeList);
      const targetStoreId = selectedStoreId || storeList[0]?.id || "";
      const query = targetStoreId ? `?store_id=${encodeURIComponent(targetStoreId)}` : "";
      const catalog = await adminFetch<CatalogResponse>(`/admin/catalog${query}`);
      const resolvedStoreId = catalog.selected_store_id || targetStoreId;
      if (resolvedStoreId && resolvedStoreId !== selectedStoreId) {
        setSelectedStoreId(resolvedStoreId);
      }
      setCategories(catalog.categories);
      setProducts(catalog.products);
      setAdditionals(catalog.additionals ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao carregar catalogo");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (ready && modulesReady && moduleAllowed) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, modulesReady, moduleAllowed, selectedStoreId]);

  useEffect(() => {
    if (!quickSuccessMessage) return;
    const t = window.setTimeout(() => setQuickSuccessMessage(null), 1800);
    return () => window.clearTimeout(t);
  }, [quickSuccessMessage]);

  const filteredProducts = useMemo(() => {
    const q = productSearch.toLowerCase();
    return products.filter((p) => {
      const matchesName = (p.name ?? "Produto customizado").toLowerCase().includes(q);
      if (!matchesName) return false;
      if (productStatusFilter === "all") return true;
      if (productStatusFilter === "active") return p.is_active;
      return !p.is_active;
    });
  }, [products, productSearch, productStatusFilter]);

  useEffect(() => {
    const query = productSearch.trim();
    if (!query) return;
    const categoryIdsToExpand = new Set<string>();
    filteredProducts.forEach((product) => {
      categoryIdsToExpand.add(product.category_id || UNCATEGORIZED_ID);
    });
    setExpandedCategories((prev) => {
      const next = new Set(prev);
      categoryIdsToExpand.forEach((id) => next.add(id));
      if (next.size === prev.size) {
        let hasDiff = false;
        next.forEach((id) => {
          if (!prev.has(id)) hasDiff = true;
        });
        if (!hasDiff) return prev;
      }
      return next;
    });
  }, [productSearch, filteredProducts]);

  const productsByCategory = useMemo(() => {
    const map = new Map<string, Product[]>();
    filteredProducts.forEach((product) => {
      const key = product.category_id || UNCATEGORIZED_ID;
      if (!map.has(key)) map.set(key, []);
      map.get(key)?.push(product);
    });
    map.forEach((items) => {
      items.sort((a, b) => {
        const orderDiff = (a.display_order ?? 0) - (b.display_order ?? 0);
        if (orderDiff !== 0) return orderDiff;
        return (a.name ?? "").localeCompare(b.name ?? "");
      });
    });
    return map;
  }, [filteredProducts]);

  const sortedCategories = useMemo(
    () => categories.slice().sort((a, b) => (a.display_order ?? 0) - (b.display_order ?? 0)),
    [categories]
  );

  const hasProductFilter = productSearch.trim().length > 0 || productStatusFilter !== "all";

  function applyProductFilter(value: "active" | "inactive" | "all") {
    setProductStatusFilter(value);
    setProductFilterOpen(false);
  }

  function toggleCategoryExpand(id: string) {
    setExpandedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  const formatMoney = (cents: number) =>
    (cents / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  const parseApiErrorMessage = (message: string) => {
    const raw = (message || "").trim();
    if (!raw) return "Falha ao processar solicitacao.";
    if (raw.startsWith("{") && raw.endsWith("}")) {
      try {
        const parsed = JSON.parse(raw) as { detail?: unknown };
        if (typeof parsed.detail === "string" && parsed.detail.trim()) return parsed.detail.trim();
      } catch {
        return raw;
      }
    }
    return raw;
  };
  const resolveAvailabilityStatus = (product?: Product | null): AvailabilityStatus => {
    if (!product) return "available";
    return (product.availability_status ?? (product.block_sale ? "order" : "available")) as AvailabilityStatus;
  };
  const availabilityLabel = (status: AvailabilityStatus) => {
    if (status === "order") return "Encomenda";
    if (status === "unavailable") return "Indisponivel";
    return "";
  };

  const paginatedCategories = sortedCategories.slice(
    (categoryPage - 1) * PAGE_SIZE,
    categoryPage * PAGE_SIZE
  );
  const visibleCategories = hasProductFilter
    ? sortedCategories.filter((c) => (productsByCategory.get(c.id) ?? []).length > 0)
    : paginatedCategories;

  function openModal(mode: ModalMode, id?: string) {
    if (!canEditProducts) return;
    setModalMode(mode);
    setEditingId(id ?? null);
    if (mode === "product" && id) {
      const prod = products.find((p) => p.id === id);
      if (prod) {
        setModalData({
          name: prod.name ?? "",
          description: prod.description ?? "",
          price_cents: prod.price_cents,
          category_id: prod.category_id || "",
          additionals_enabled: !!prod.additionals_enabled,
          additional_ids: [...(prod.additional_ids ?? [])],
          is_active: prod.is_active ?? true,
          is_custom: prod.is_custom ?? false,
          availability_status: resolveAvailabilityStatus(prod),
          display_order: prod.display_order ?? 0,
        });
        setCurrentImageUrl(prod.image_url ?? null);
        setImagePreview(prod.image_url ?? null);
        setImageFile(null);
        setRemoveImage(false);
        setCurrentVideoUrl(prod.video_url ?? null);
        setVideoPreview(prod.video_url ?? null);
        setVideoFile(null);
        setRemoveVideo(false);
      }
    } else if (mode === "category" && id) {
      const cat = categories.find((c) => c.id === id);
      if (cat) {
        setModalData({
          name: cat.name,
          description: "",
          price_cents: 0,
          category_id: "",
          additionals_enabled: false,
          additional_ids: [],
          is_active: cat.is_active ?? true,
          is_custom: false,
          availability_status: "available",
          display_order: cat.display_order ?? 0,
        });
        setCurrentImageUrl(null);
        setImagePreview(null);
        setImageFile(null);
        setRemoveImage(false);
        setCurrentVideoUrl(null);
        setVideoPreview(null);
        setVideoFile(null);
        setRemoveVideo(false);
      }
    } else if (mode === "additional" && id) {
      const additional = additionals.find((a) => a.id === id);
      if (additional) {
        setModalData({
          name: additional.name,
          description: additional.description ?? "",
          price_cents: additional.price_cents,
          category_id: "",
          additionals_enabled: false,
          additional_ids: [],
          is_active: additional.is_active ?? true,
          is_custom: false,
          availability_status: "available",
          display_order: additional.display_order ?? 0,
        });
      }
      setCurrentImageUrl(null);
      setImagePreview(null);
      setImageFile(null);
      setRemoveImage(false);
      setCurrentVideoUrl(null);
      setVideoPreview(null);
      setVideoFile(null);
      setRemoveVideo(false);
    } else {
      setModalData({
        name: "",
        description: "",
        price_cents: 0,
        category_id: "",
        additionals_enabled: false,
        additional_ids: [],
        is_active: true,
        is_custom: false,
        availability_status: "available",
        display_order: 0,
      });
      setCurrentImageUrl(null);
      setImagePreview(null);
      setImageFile(null);
      setRemoveImage(false);
      setCurrentVideoUrl(null);
      setVideoPreview(null);
      setVideoFile(null);
      setRemoveVideo(false);
    }
    setModalOpen(true);
  }

  function closeModal() {
    setModalOpen(false);
    setEditingId(null);
    if (imagePreview?.startsWith("blob:")) {
      URL.revokeObjectURL(imagePreview);
    }
    if (videoPreview?.startsWith("blob:")) {
      URL.revokeObjectURL(videoPreview);
    }
    setImageFile(null);
    setImagePreview(null);
    setCurrentImageUrl(null);
    setRemoveImage(false);
    setVideoFile(null);
    setVideoPreview(null);
    setCurrentVideoUrl(null);
    setRemoveVideo(false);
  }

  async function saveModal() {
    if (!canEditProducts) return;
    try {
      setLoading(true);
      setError(null);
      const creatingAdditional = modalMode === "additional" && !editingId;
      let createdAdditional: Additional | null = null;
      if (modalMode === "product") {
        const payload = {
          store_id: selectedStoreId || null,
          name: modalData.is_custom ? null : modalData.name.trim(),
          description: modalData.description.trim(),
          price_cents: modalData.is_custom ? null : Number(modalData.price_cents),
          category_id: modalData.category_id || null,
          additionals_enabled: modalData.additionals_enabled,
          additional_ids: modalData.additional_ids,
          is_active: modalData.is_active,
          is_custom: modalData.is_custom,
          availability_status: modalData.availability_status,
        };
        let productId = editingId;
        if (editingId) {
          await adminFetch(`/admin/catalog/products/${editingId}`, { method: "PATCH", body: JSON.stringify(payload) });
        } else {
          const created = await adminFetch<Product>(`/admin/catalog/products`, {
            method: "POST",
            body: JSON.stringify(payload),
          });
          productId = created.id;
        }
        if (productId) {
          if (imageFile) {
            const form = new FormData();
            form.append("file", imageFile);
            await adminUpload(`/admin/catalog/products/${productId}/image`, form);
          } else if (removeImage) {
            await adminFetch(`/admin/catalog/products/${productId}`, {
              method: "PATCH",
              body: JSON.stringify({ image_url: null }),
            });
          }
          if (videoFile) {
            const form = new FormData();
            form.append("file", videoFile);
            await adminUpload(`/admin/catalog/products/${productId}/video`, form);
          } else if (removeVideo) {
            await adminFetch(`/admin/catalog/products/${productId}`, {
              method: "PATCH",
              body: JSON.stringify({ video_url: null }),
            });
          }
        }
      } else if (modalMode === "category") {
        const payload = {
          store_id: selectedStoreId || null,
          name: modalData.name.trim(),
          display_order: Number(modalData.display_order) || 0,
        };
        if (editingId) {
          await adminFetch(`/admin/catalog/categories/${editingId}`, { method: "PATCH", body: JSON.stringify(payload) });
        } else {
          await adminFetch(`/admin/catalog/categories`, { method: "POST", body: JSON.stringify(payload) });
        }
      } else {
        const payload = {
          store_id: selectedStoreId || null,
          name: modalData.name.trim(),
          description: modalData.description.trim() || null,
          price_cents: Number(modalData.price_cents) || 0,
          is_active: modalData.is_active,
          display_order: Number(modalData.display_order) || 0,
        };
        if (editingId) {
          await adminFetch(`/admin/catalog/additionals/${editingId}`, {
            method: "PATCH",
            body: JSON.stringify(payload),
          });
        } else {
          createdAdditional = await adminFetch<Additional>(`/admin/catalog/additionals`, {
            method: "POST",
            body: JSON.stringify(payload),
          });
        }
      }
      closeModal();
      await load();
      if (creatingAdditional && createdAdditional) {
        setAdditionalToLink(createdAdditional);
        setSelectedProductIdsForAdditional([]);
        setAdditionalLinkPromptOpen(true);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao salvar");
    } finally {
      setLoading(false);
    }
  }

  async function toggleProduct(p: Product) {
    if (!canEditProducts) return;
    try {
      setLoading(true);
      await adminFetch(`/admin/catalog/products/${p.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !p.is_active }),
      });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao atualizar status");
    } finally {
      setLoading(false);
    }
  }

  async function deleteProduct(product: Product) {
    if (!canEditProducts) return;
    if (!window.confirm(`Excluir o produto "${product.name ?? "Produto"}"?`)) return;
    try {
      setLoading(true);
      setError(null);
      setBlockingDeleteMessage(null);
      await adminFetch(`/admin/catalog/products/${product.id}`, { method: "DELETE" });
      setQuickSuccessMessage("Produto excluido com sucesso.");
      await load();
    } catch (e) {
      const message = parseApiErrorMessage(e instanceof Error ? e.message : "Falha ao excluir produto");
      setBlockingDeleteMessage(message);
    } finally {
      setLoading(false);
    }
  }

  async function toggleCategory(c: Category) {
    if (!canEditProducts) return;
    try {
      setLoading(true);
      await adminFetch(`/admin/catalog/categories/${c.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !c.is_active }),
      });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao atualizar status");
    } finally {
      setLoading(false);
    }
  }

  async function deleteCategory(category: Category) {
    if (!canEditProducts) return;
    if (!window.confirm(`Excluir a categoria "${category.name}"?`)) return;
    try {
      setLoading(true);
      setError(null);
      setBlockingDeleteMessage(null);
      await adminFetch(`/admin/catalog/categories/${category.id}`, { method: "DELETE" });
      await load();
    } catch (e) {
      const message = parseApiErrorMessage(e instanceof Error ? e.message : "Falha ao excluir categoria");
      setBlockingDeleteMessage(message);
    } finally {
      setLoading(false);
    }
  }

  async function toggleAdditional(additional: Additional) {
    if (!canEditProducts) return;
    try {
      setLoading(true);
      await adminFetch(`/admin/catalog/additionals/${additional.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !additional.is_active }),
      });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao atualizar adicional");
    } finally {
      setLoading(false);
    }
  }

  async function deleteAdditional(additional: Additional) {
    if (!canEditProducts) return;
    if (!window.confirm(`Excluir o adicional "${additional.name}"?`)) return;
    try {
      setLoading(true);
      setError(null);
      setBlockingDeleteMessage(null);
      await adminFetch(`/admin/catalog/additionals/${additional.id}`, { method: "DELETE" });
      await load();
    } catch (e) {
      const message = parseApiErrorMessage(e instanceof Error ? e.message : "Falha ao excluir adicional");
      setBlockingDeleteMessage(message);
    } finally {
      setLoading(false);
    }
  }

  const selectedStoreProducts = useMemo(
    () =>
      products.filter(
        (product) => product.is_active && (!selectedStoreId || product.store_id === selectedStoreId)
      ),
    [products, selectedStoreId]
  );

  function toggleProductForAdditionalLink(productId: string) {
    setSelectedProductIdsForAdditional((prev) => {
      if (prev.includes(productId)) return prev.filter((id) => id !== productId);
      return [...prev, productId];
    });
  }

  async function linkAdditionalToProducts() {
    if (!additionalToLink || selectedProductIdsForAdditional.length === 0) {
      setAdditionalLinkPromptOpen(false);
      setAdditionalToLink(null);
      return;
    }
    try {
      setLoading(true);
      for (const productId of selectedProductIdsForAdditional) {
        const product = products.find((item) => item.id === productId);
        if (!product) continue;
        const nextIds = Array.from(new Set([...(product.additional_ids ?? []), additionalToLink.id]));
        await adminFetch(`/admin/catalog/products/${productId}`, {
          method: "PATCH",
          body: JSON.stringify({
            additionals_enabled: true,
            additional_ids: nextIds,
          }),
        });
      }
      setAdditionalLinkPromptOpen(false);
      setAdditionalToLink(null);
      setSelectedProductIdsForAdditional([]);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao vincular adicional aos produtos");
    } finally {
      setLoading(false);
    }
  }

  if (!ready) return null;
  const uncategorizedProducts = productsByCategory.get(UNCATEGORIZED_ID) ?? [];
  const sidebarItems = adminMenuWithHome;

  return (
    <main className="min-h-screen bg-[#f5f3ff] text-slate-900">
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
              <div className="space-y-1 text-slate-900">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-600">Admin • Catálogo</p>
                <h1 className="text-3xl font-semibold">Produtos e categorias</h1>
                <p className="text-sm text-slate-600">Gerencie catálogo com buscas rápidas e ações em linha.</p>
              </div>
              <ProfileBadge />
            </header>
            {moduleBlocked ? (
              <section className="rounded-2xl bg-white border border-slate-200 p-4 space-y-2">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Modulo inativo</p>
                <h2 className="text-lg font-semibold">Produtos indisponivel</h2>
                <p className="text-sm text-slate-600">
                  Este modulo nao esta habilitado para a sua empresa. Fale com o administrador para liberar o acesso.
                </p>
              </section>
            ) : (
              <>

            {error && <p className="text-sm text-red-600">{error}</p>}
            {stores.length === 0 && (
              <p className="text-sm text-amber-700">Cadastre ao menos uma loja para gerenciar o catalogo.</p>
            )}

            <div className="flex flex-wrap items-end gap-3">
              <label className="space-y-1">
                <span className="text-xs uppercase tracking-[0.18em] text-slate-600">Loja</span>
                <select
                  className="input min-w-[220px]"
                  value={selectedStoreId}
                  onChange={(e) => setSelectedStoreId(e.target.value)}
                  disabled={stores.length <= 1}
                >
                  {stores.map((store) => (
                    <option key={store.id} value={store.id}>
                      {store.name}
                    </option>
                  ))}
                </select>
              </label>
              <button
                onClick={() => openModal("product")}
                disabled={!canEditProducts || !selectedStoreId}
                className="px-4 py-2 rounded-xl bg-white text-slate-900 font-semibold shadow-sm active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Novo produto
              </button>
              <button
                onClick={() => openModal("category")}
                disabled={!canEditProducts || !selectedStoreId}
                className="px-4 py-2 rounded-xl bg-[#6320ee] text-white font-semibold shadow-sm active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Nova categoria
              </button>
              <button
                onClick={() => openModal("additional")}
                disabled={!canEditProducts || !selectedStoreId}
                className="px-4 py-2 rounded-xl bg-slate-900 text-white font-semibold shadow-sm active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Novo adicional
              </button>
            </div>

            <section className="rounded-3xl bg-white text-slate-900 shadow-sm border border-slate-200 p-3 sm:p-5 space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="space-y-1">
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Catalogo</p>
                  <h2 className="text-lg font-semibold">Categorias e produtos</h2>
                  <p className="text-sm text-slate-600">
                    Expanda as categorias para visualizar os produtos relacionados.
                  </p>
                </div>
                <div className="flex flex-col sm:items-end gap-1 w-full sm:w-auto">
                  <div className="flex items-center gap-2 w-full sm:w-auto">
                    <div className="relative flex items-center">
                      <button
                        type="button"
                        onClick={() => setProductFilterOpen((open) => !open)}
                        className="h-10 w-10 rounded-xl border border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                        aria-label="Filtro de produtos"
                        aria-expanded={productFilterOpen}
                      >
                        <svg
                          className="h-4 w-4 mx-auto"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          aria-hidden="true"
                        >
                          <path d="M3 5h18" />
                          <path d="M6 12h12" />
                          <path d="M10 19h4" />
                        </svg>
                      </button>
                      {productFilterOpen && (
                        <div className="absolute left-0 sm:left-auto sm:right-0 mt-2 w-44 rounded-xl border border-slate-200 bg-white shadow-lg p-2 text-xs text-slate-700">
                          <button
                            type="button"
                            onClick={() => applyProductFilter("active")}
                            className={`w-full text-left px-3 py-2 rounded-lg hover:bg-slate-50 ${
                              productStatusFilter === "active" ? "bg-slate-100 font-semibold" : ""
                            }`}
                          >
                            Apenas ativos
                          </button>
                          <button
                            type="button"
                            onClick={() => applyProductFilter("inactive")}
                            className={`w-full text-left px-3 py-2 rounded-lg hover:bg-slate-50 ${
                              productStatusFilter === "inactive" ? "bg-slate-100 font-semibold" : ""
                            }`}
                          >
                            Apenas inativos
                          </button>
                          <button
                            type="button"
                            onClick={() => applyProductFilter("all")}
                            className={`w-full text-left px-3 py-2 rounded-lg hover:bg-slate-50 ${
                              productStatusFilter === "all" ? "bg-slate-100 font-semibold" : ""
                            }`}
                          >
                            Todos
                          </button>
                        </div>
                      )}
                    </div>
                    <input
                      className="input w-full sm:w-56"
                      placeholder="Buscar produto..."
                      value={productSearch}
                      onChange={(e) => {
                        setProductSearch(e.target.value);
                      }}
                    />
                  </div>
                  <span className="text-xs text-slate-600">Total: {filteredProducts.length} produtos</span>
                </div>
              </div>

              {visibleCategories.length === 0 && uncategorizedProducts.length === 0 ? (
                <p className="text-sm text-slate-600">Nenhum produto encontrado.</p>
              ) : (
                <div className="space-y-3">
                  {visibleCategories.map((c) => {
                    const categoryProducts = productsByCategory.get(c.id) ?? [];
                    const expanded = expandedCategories.has(c.id);
                    return (
                      <div key={c.id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4 space-y-3">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Categoria</p>
                            <p className="text-base font-semibold text-slate-900">{c.name}</p>
                            <p className="text-xs text-slate-500">
                              Ordem {c.display_order ?? 0} ? {categoryProducts.length} produtos
                            </p>
                          </div>
                          <div className="flex flex-wrap items-center gap-2">
                            <span
                              className={`px-2 py-1 rounded-full text-[10px] ${
                                c.is_active ? "bg-emerald-200 text-emerald-900" : "bg-amber-200 text-amber-900"
                              }`}
                            >
                              {c.is_active ? "Ativa" : "Inativa"}
                            </span>
                            <>
                              <button
                                onClick={() => openModal("category", c.id)}
                                disabled={!canEditProducts}
                                className="px-3 py-1 rounded-lg border border-slate-200 text-xs hover:bg-slate-100 disabled:opacity-50 disabled:cursor-not-allowed"
                              >
                                Editar
                              </button>
                              <button
                                onClick={() => toggleCategory(c)}
                                disabled={!canEditProducts}
                                className="px-3 py-1 rounded-lg bg-[#6320ee] text-white text-xs hover:brightness-95 disabled:opacity-50 disabled:cursor-not-allowed"
                              >
                                {c.is_active ? "Inativar" : "Ativar"}
                              </button>
                              <button
                                onClick={() => deleteCategory(c)}
                                disabled={!canEditProducts}
                                className="px-3 py-1 rounded-lg bg-red-50 text-red-700 border border-red-200 text-xs hover:bg-red-100 disabled:opacity-50 disabled:cursor-not-allowed"
                              >
                                Excluir
                              </button>
                            </>
                            <button
                              onClick={() => toggleCategoryExpand(c.id)}
                              className="px-3 py-1 rounded-lg border border-slate-200 text-xs hover:bg-slate-100"
                            >
                              {expanded ? "Fechar" : "Ver produtos"}
                            </button>
                          </div>
                        </div>
                        {expanded && (
                          <div className="space-y-2">
                            {categoryProducts.length === 0 ? (
                              <p className="text-xs text-slate-500">Sem produtos nessa categoria.</p>
                            ) : (
                              categoryProducts.map((p) => (
                                <div
                                  key={p.id}
                                  className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white px-3 py-2"
                                >
                                  <div className="h-12 w-12 rounded-lg overflow-hidden border border-slate-200 bg-slate-100 flex items-center justify-center">
                                    {p.image_url ? (
                                      // eslint-disable-next-line @next/next/no-img-element
                                      <img
                                        src={p.image_url}
                                        alt={p.name ?? "Produto"}
                                        className="h-full w-full object-cover"
                                      />
                                    ) : (
                                      <svg
                                        viewBox="0 0 24 24"
                                        className="h-5 w-5 text-slate-400"
                                        fill="none"
                                        stroke="currentColor"
                                        strokeWidth="1.5"
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        aria-hidden="true"
                                      >
                                        <path d="M4 7h16v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z" />
                                        <path d="M8 11l2.5 2.5L14 10l4 4" />
                                        <circle cx="9" cy="9" r="1.5" />
                                      </svg>
                                    )}
                                  </div>
                                  <div className="flex-1 min-w-[160px]">
                                    <p className="text-sm font-semibold text-slate-900">
                                      {p.name ?? "Produto customizado"}
                                    </p>
                                    <p className="text-xs text-slate-500">
                                      {formatMoney(p.price_cents)}
                                      {(() => {
                                        const label = availabilityLabel(resolveAvailabilityStatus(p));
                                        return label ? ` • ${label}` : "";
                                      })()}
                                    </p>
                                  </div>
                                  <span
                                    className={`px-2 py-1 rounded-full text-[10px] ${
                                      p.is_active ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"
                                    }`}
                                  >
                                    {p.is_active ? "Ativo" : "Inativo"}
                                  </span>
                                  <div className="flex flex-wrap gap-2">
                                    <button
                                      onClick={() => openModal("product", p.id)}
                                      disabled={!canEditProducts}
                                      className="px-3 py-1 rounded-lg border border-slate-200 text-xs hover:bg-slate-100 disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                      Editar
                                    </button>
                                    <button
                                      onClick={() => toggleProduct(p)}
                                      disabled={!canEditProducts}
                                      className="px-3 py-1 rounded-lg bg-[#6320ee] text-white text-xs hover:brightness-95 disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                      {p.is_active ? "Inativar" : "Ativar"}
                                    </button>
                                    <button
                                      onClick={() => deleteProduct(p)}
                                      disabled={!canEditProducts}
                                      className="px-3 py-1 rounded-lg bg-red-50 text-red-700 border border-red-200 text-xs hover:bg-red-100 disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                      Excluir
                                    </button>
                                  </div>
                                </div>
                              ))
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                  {uncategorizedProducts.length > 0 && (() => {
                    const expanded = expandedCategories.has(UNCATEGORIZED_ID);
                    return (
                      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 space-y-3">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Categoria</p>
                            <p className="text-base font-semibold text-slate-900">Sem categoria</p>
                            <p className="text-xs text-slate-500">{uncategorizedProducts.length} produtos</p>
                          </div>
                          <div className="flex flex-wrap items-center gap-2">
                            <button
                              onClick={() => toggleCategoryExpand(UNCATEGORIZED_ID)}
                              className="px-3 py-1 rounded-lg border border-slate-200 text-xs hover:bg-slate-100"
                            >
                              {expanded ? "Fechar" : "Ver produtos"}
                            </button>
                          </div>
                        </div>
                        {expanded && (
                          <div className="space-y-2">
                            {uncategorizedProducts.map((p) => (
                              <div
                                key={p.id}
                                className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white px-3 py-2"
                              >
                                <div className="h-12 w-12 rounded-lg overflow-hidden border border-slate-200 bg-slate-100 flex items-center justify-center">
                                  {p.image_url ? (
                                    // eslint-disable-next-line @next/next/no-img-element
                                    <img
                                      src={p.image_url}
                                      alt={p.name ?? "Produto"}
                                      className="h-full w-full object-cover"
                                    />
                                  ) : (
                                    <svg
                                      viewBox="0 0 24 24"
                                      className="h-5 w-5 text-slate-400"
                                      fill="none"
                                      stroke="currentColor"
                                      strokeWidth="1.5"
                                      strokeLinecap="round"
                                      strokeLinejoin="round"
                                      aria-hidden="true"
                                    >
                                      <path d="M4 7h16v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z" />
                                      <path d="M8 11l2.5 2.5L14 10l4 4" />
                                      <circle cx="9" cy="9" r="1.5" />
                                    </svg>
                                  )}
                                </div>
                                <div className="flex-1 min-w-[160px]">
                                  <p className="text-sm font-semibold text-slate-900">
                                    {p.name ?? "Produto customizado"}
                                  </p>
                                  <p className="text-xs text-slate-500">
                                    {formatMoney(p.price_cents)}
                                    {(() => {
                                      const label = availabilityLabel(resolveAvailabilityStatus(p));
                                      return label ? ` • ${label}` : "";
                                    })()}
                                  </p>
                                </div>
                                <span
                                  className={`px-2 py-1 rounded-full text-[10px] ${
                                    p.is_active ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"
                                  }`}
                                >
                                  {p.is_active ? "Ativo" : "Inativo"}
                                </span>
                                <div className="flex flex-wrap gap-2">
                                  <button
                                    onClick={() => openModal("product", p.id)}
                                    disabled={!canEditProducts}
                                    className="px-3 py-1 rounded-lg border border-slate-200 text-xs hover:bg-slate-100 disabled:opacity-50 disabled:cursor-not-allowed"
                                  >
                                    Editar
                                  </button>
                                  <button
                                    onClick={() => toggleProduct(p)}
                                    disabled={!canEditProducts}
                                    className="px-3 py-1 rounded-lg bg-[#6320ee] text-white text-xs hover:brightness-95 disabled:opacity-50 disabled:cursor-not-allowed"
                                  >
                                    {p.is_active ? "Inativar" : "Ativar"}
                                  </button>
                                  <button
                                    onClick={() => deleteProduct(p)}
                                    disabled={!canEditProducts}
                                    className="px-3 py-1 rounded-lg bg-red-50 text-red-700 border border-red-200 text-xs hover:bg-red-100 disabled:opacity-50 disabled:cursor-not-allowed"
                                  >
                                    Excluir
                                  </button>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })()}
                </div>
              )}

              {!hasProductFilter && categories.length > PAGE_SIZE && (
                <div className="flex items-center justify-between text-xs text-slate-600">
                  <button
                    className="px-3 py-1 rounded border border-slate-200 bg-slate-100 disabled:opacity-50"
                    onClick={() => setCategoryPage((p) => Math.max(1, p - 1))}
                    disabled={categoryPage === 1}
                  >
                    Anterior
                  </button>
                  <span>Pagina {categoryPage}</span>
                  <button
                    className="px-3 py-1 rounded border border-slate-200 bg-slate-100 disabled:opacity-50"
                    onClick={() =>
                      setCategoryPage((p) => (p * PAGE_SIZE < sortedCategories.length ? p + 1 : p))
                    }
                    disabled={categoryPage * PAGE_SIZE >= sortedCategories.length}
                  >
                    Proxima
                  </button>
                </div>
              )}
            </section>

            <section className="rounded-3xl bg-white text-slate-900 shadow-sm border border-slate-200 p-3 sm:p-5 space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="space-y-1">
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Catalogo</p>
                  <h2 className="text-lg font-semibold">Adicionais</h2>
                  <p className="text-sm text-slate-600">Cadastre e vincule adicionais para os produtos da loja.</p>
                </div>
                <span className="text-xs text-slate-600">{additionals.length} adicional(is)</span>
              </div>
              {additionals.length === 0 ? (
                <p className="text-sm text-slate-600">Nenhum adicional cadastrado para esta loja.</p>
              ) : (
                <div className="space-y-2">
                  {additionals.map((additional) => (
                    <div
                      key={additional.id}
                      className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2"
                    >
                      <div className="flex-1 min-w-[180px]">
                        <p className="text-sm font-semibold text-slate-900">{additional.name}</p>
                        <p className="text-xs text-slate-500">
                          {formatMoney(additional.price_cents)}
                          {additional.description ? ` - ${additional.description}` : ""}
                        </p>
                      </div>
                      <span
                        className={`px-2 py-1 rounded-full text-[10px] ${
                          additional.is_active ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"
                        }`}
                      >
                        {additional.is_active ? "Ativo" : "Inativo"}
                      </span>
                      <div className="flex flex-wrap gap-2">
                        <button
                          onClick={() => openModal("additional", additional.id)}
                          disabled={!canEditProducts}
                          className="px-3 py-1 rounded-lg border border-slate-200 text-xs hover:bg-slate-100 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          Editar
                        </button>
                        <button
                          onClick={() => toggleAdditional(additional)}
                          disabled={!canEditProducts}
                          className="px-3 py-1 rounded-lg bg-[#6320ee] text-white text-xs hover:brightness-95 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {additional.is_active ? "Inativar" : "Ativar"}
                        </button>
                        <button
                          onClick={() => deleteAdditional(additional)}
                          disabled={!canEditProducts}
                          className="px-3 py-1 rounded-lg bg-red-50 text-red-700 border border-red-200 text-xs hover:bg-red-100 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          Excluir
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
              </>
            )}

          </div>
        </div>
      </div>

      {quickSuccessMessage && (
        <div className="fixed top-4 right-4 z-40 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800 shadow-lg">
          <span className="font-semibold">✓</span> {quickSuccessMessage}
        </div>
      )}

      {blockingDeleteMessage && (
        <div className="fixed inset-0 z-50 bg-slate-900/45 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md rounded-2xl bg-white border border-slate-200 p-5 space-y-3 shadow-xl">
            <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Nao foi possivel excluir</p>
            <h3 className="text-lg font-semibold text-slate-900">Falha ao excluir registro</h3>
            <p className="text-sm text-slate-700">{blockingDeleteMessage}</p>
            <div className="flex items-center justify-end">
              <button
                type="button"
                onClick={() => setBlockingDeleteMessage(null)}
                className="px-4 py-2 rounded-lg bg-[#6320ee] text-white text-sm font-semibold hover:brightness-95"
              >
                Entendi
              </button>
            </div>
          </div>
        </div>
      )}

      {canEditProducts && modalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-200/80 backdrop-blur-sm flex items-center justify-center p-3 sm:p-4 overflow-y-auto">
          <div className="w-full max-w-xl rounded-3xl bg-white shadow-2xl text-[#211a1d] max-h-[calc(100dvh-1.5rem)] sm:max-h-[calc(100dvh-3rem)] flex flex-col">
            <div className="flex items-start justify-between px-5 pt-5 pb-3">
              <div>
                <p className="text-xs uppercase tracking-[0.18em] text-neutral-500">
                  {editingId ? "Editar" : "Novo"}{" "}
                  {modalMode === "product" ? "produto" : modalMode === "category" ? "categoria" : "adicional"}
                </p>
                <h3 className="text-xl font-semibold text-[#211a1d]">
                  {modalMode === "product" ? "Produto" : modalMode === "category" ? "Categoria" : "Adicional"}
                </h3>
              </div>
              <button onClick={closeModal} className="text-sm px-3 py-1 rounded-full bg-neutral-100 hover:bg-neutral-200">
                Fechar
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-5 pb-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                {modalMode === "product" ? (
                  <>
                    <label className="sm:col-span-2 space-y-1">
                      <span>Tipo de produto</span>
                      <select
                        className="input w-full"
                        value={modalData.is_custom ? "custom" : "regular"}
                        onChange={(e) =>
                          setModalData({ ...modalData, is_custom: e.target.value === "custom" })
                        }
                      >
                        <option value="regular">Produto</option>
                        <option value="custom">Produto customizado</option>
                      </select>
                    </label>
                    {!modalData.is_custom && (
                      <>
                        <label className="sm:col-span-2 space-y-1">
                          <span>Nome</span>
                          <input
                            className="input w-full"
                            value={modalData.name}
                            onChange={(e) => setModalData({ ...modalData, name: e.target.value })}
                          />
                        </label>
                        <label className="sm:col-span-2 space-y-1">
                          <span>Descricao</span>
                          <textarea
                            className="input w-full min-h-[96px]"
                            value={modalData.description}
                            onChange={(e) => setModalData({ ...modalData, description: e.target.value })}
                          />
                        </label>
                        <label className="sm:col-span-2 space-y-1">
                          <span>Foto do produto</span>
                          <input
                            type="file"
                            accept="image/jpeg,image/png,image/webp"
                            className="input w-full"
                            onChange={(e) => {
                              const file = e.target.files?.[0] ?? null;
                              if (imagePreview?.startsWith("blob:")) {
                                URL.revokeObjectURL(imagePreview);
                              }
                              setImageFile(file);
                              setRemoveImage(false);
                              if (file) {
                                setImagePreview(URL.createObjectURL(file));
                              } else {
                                setImagePreview(currentImageUrl);
                              }
                            }}
                          />
                          <span className="text-xs text-neutral-500">JPG, PNG ou WebP ate 5MB.</span>
                        </label>
                        {imagePreview && (
                          <div className="sm:col-span-2 flex items-center gap-3">
                            <div className="h-20 w-20 rounded-xl overflow-hidden border border-neutral-200">
                              {/* eslint-disable-next-line @next/next/no-img-element */}
                              <img src={imagePreview} alt="Foto do produto" className="h-full w-full object-cover" />
                            </div>
                            <button
                              type="button"
                              onClick={() => {
                                if (imagePreview.startsWith("blob:")) {
                                  URL.revokeObjectURL(imagePreview);
                                }
                                setImageFile(null);
                                setImagePreview(null);
                                setRemoveImage(true);
                              }}
                              className="px-3 py-2 rounded-lg border border-neutral-200 text-sm hover:bg-neutral-100"
                            >
                              Remover foto
                            </button>
                          </div>
                        )}
                        <label className="sm:col-span-2 space-y-1">
                          <span>Video do produto</span>
                          <input
                            type="file"
                            accept="video/mp4,video/webm"
                            className="input w-full"
                            onChange={(e) => {
                              const file = e.target.files?.[0] ?? null;
                              if (videoPreview?.startsWith("blob:")) {
                                URL.revokeObjectURL(videoPreview);
                              }
                              setVideoFile(file);
                              setRemoveVideo(false);
                              if (file) {
                                setVideoPreview(URL.createObjectURL(file));
                              } else {
                                setVideoPreview(currentVideoUrl);
                              }
                            }}
                          />
                          <span className="text-xs text-neutral-500">MP4 ou WebM ate 20MB.</span>
                        </label>
                        {videoPreview && (
                          <div className="sm:col-span-2 flex items-center gap-3">
                            <div className="h-20 w-32 rounded-xl overflow-hidden border border-neutral-200 bg-neutral-50">
                              <video src={videoPreview} className="h-full w-full object-cover" muted playsInline />
                            </div>
                            <button
                              type="button"
                              onClick={() => {
                                if (videoPreview.startsWith("blob:")) {
                                  URL.revokeObjectURL(videoPreview);
                                }
                                setVideoFile(null);
                                setVideoPreview(null);
                                setRemoveVideo(true);
                              }}
                              className="px-3 py-2 rounded-lg border border-neutral-200 text-sm hover:bg-neutral-100"
                            >
                              Remover video
                            </button>
                          </div>
                        )}
                        <label className="space-y-1">
                          <span>Preco (R$)</span>
                          <input
                            type="text"
                            className="input w-full"
                            inputMode="decimal"
                            value={
                              typeof modalData.price_cents === "number"
                                ? (modalData.price_cents / 100).toFixed(2)
                                : ""
                            }
                            onChange={(e) => {
                              const raw = e.target.value.replace(",", ".").replace(/[^0-9.]/g, "");
                              const parsed = Number.parseFloat(raw);
                              const cents = Number.isFinite(parsed) ? Math.round(parsed * 100) : 0;
                              setModalData({ ...modalData, price_cents: cents });
                            }}
                          />
                        </label>
                      </>
                    )}
                    <label className="space-y-1">
                      <span>Categoria</span>
                      <select
                        className="input w-full"
                        value={modalData.category_id}
                        onChange={(e) => setModalData({ ...modalData, category_id: e.target.value })}
                      >
                        <option value="">Sem categoria</option>
                        {categories.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="sm:col-span-2 space-y-2">
                      <span className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          className="h-4 w-4"
                          checked={modalData.additionals_enabled}
                          onChange={(e) =>
                            setModalData((prev) => ({
                              ...prev,
                              additionals_enabled: e.target.checked,
                            }))
                          }
                        />
                        <span>Produto com adicionais</span>
                      </span>
                    </label>
                    {modalData.additionals_enabled && (
                      <label className="sm:col-span-2 space-y-1">
                        <span>Adicionais permitidos</span>
                        <div className="max-h-40 overflow-y-auto rounded-xl border border-slate-200 bg-slate-50 p-2 space-y-1">
                          {additionals.length === 0 ? (
                            <p className="text-xs text-slate-500 px-1 py-2">
                              Nenhum adicional cadastrado para esta loja.
                            </p>
                          ) : (
                            additionals.map((additional) => (
                              <label
                                key={additional.id}
                                className="flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 hover:bg-white"
                              >
                                <span className="flex items-center gap-2">
                                  <input
                                    type="checkbox"
                                    checked={modalData.additional_ids.includes(additional.id)}
                                    onChange={(e) =>
                                      setModalData((prev) => {
                                        const selected = new Set(prev.additional_ids);
                                        if (e.target.checked) {
                                          selected.add(additional.id);
                                        } else {
                                          selected.delete(additional.id);
                                        }
                                        return {
                                          ...prev,
                                          additional_ids: Array.from(selected),
                                        };
                                      })
                                    }
                                  />
                                  <span className="text-xs text-slate-700">
                                    {additional.name}
                                    {!additional.is_active ? " (inativo)" : ""}
                                  </span>
                                </span>
                                <span className="text-xs text-slate-500">{formatMoney(additional.price_cents)}</span>
                              </label>
                            ))
                          )}
                        </div>
                      </label>
                    )}
                    <label className="flex items-center gap-2 mt-1">
                      <input
                        type="checkbox"
                        className="h-4 w-4"
                        checked={modalData.is_active}
                        onChange={(e) => setModalData({ ...modalData, is_active: e.target.checked })}
                      />
                      <span>Ativo</span>
                    </label>
                    <label className="sm:col-span-2 space-y-1">
                      <span>Status de venda</span>
                      <select
                        className="input w-full"
                        value={modalData.availability_status}
                        onChange={(e) =>
                          setModalData({
                            ...modalData,
                            availability_status: e.target.value as AvailabilityStatus,
                          })
                        }
                      >
                        <option value="available">Disponivel</option>
                        <option value="order">Encomenda (WhatsApp)</option>
                        <option value="unavailable">Indisponivel</option>
                      </select>
                    </label>
                  </>
                ) : modalMode === "category" ? (
                  <>
                    <label className="sm:col-span-2 space-y-1">
                      <span>Nome</span>
                      <input
                        className="input w-full"
                        value={modalData.name}
                        onChange={(e) => setModalData({ ...modalData, name: e.target.value })}
                      />
                    </label>
                    <label className="space-y-1">
                      <span>Ordem</span>
                      <input
                        type="number"
                        className="input w-full"
                        value={modalData.display_order}
                        onChange={(e) => setModalData({ ...modalData, display_order: Number(e.target.value) })}
                      />
                    </label>
                  </>
                ) : (
                  <>
                    <label className="sm:col-span-2 space-y-1">
                      <span>Nome</span>
                      <input
                        className="input w-full"
                        value={modalData.name}
                        onChange={(e) => setModalData({ ...modalData, name: e.target.value })}
                      />
                    </label>
                    <label className="sm:col-span-2 space-y-1">
                      <span>Descricao</span>
                      <textarea
                        className="input w-full min-h-[96px]"
                        value={modalData.description}
                        onChange={(e) => setModalData({ ...modalData, description: e.target.value })}
                      />
                    </label>
                    <label className="space-y-1">
                      <span>Preco (R$)</span>
                      <input
                        type="text"
                        className="input w-full"
                        inputMode="decimal"
                        value={(Number(modalData.price_cents || 0) / 100).toFixed(2)}
                        onChange={(e) => {
                          const raw = e.target.value.replace(",", ".").replace(/[^0-9.]/g, "");
                          const parsed = Number.parseFloat(raw);
                          const cents = Number.isFinite(parsed) ? Math.round(parsed * 100) : 0;
                          setModalData({ ...modalData, price_cents: cents });
                        }}
                      />
                    </label>
                    <label className="space-y-1">
                      <span>Ordem</span>
                      <input
                        type="number"
                        className="input w-full"
                        value={modalData.display_order}
                        onChange={(e) => setModalData({ ...modalData, display_order: Number(e.target.value) })}
                      />
                    </label>
                    <label className="sm:col-span-2 flex items-center gap-2 mt-1">
                      <input
                        type="checkbox"
                        className="h-4 w-4"
                        checked={modalData.is_active}
                        onChange={(e) => setModalData({ ...modalData, is_active: e.target.checked })}
                      />
                      <span>Ativo</span>
                    </label>
                  </>
                )}
              </div>
            </div>

            <div className="px-5 py-4 border-t border-neutral-200 space-y-3 bg-white rounded-b-3xl">
              {error ? <p className="text-sm text-red-600">{error}</p> : null}
              <div className="flex items-center justify-end gap-3">
              <button
                onClick={closeModal}
                className="px-4 py-2 rounded-lg bg-neutral-100 text-neutral-800 text-sm hover:bg-neutral-200"
              >
                Cancelar
              </button>
              <button
                onClick={saveModal}
                disabled={
                  loading ||
                  (modalMode === "category" && !modalData.name.trim()) ||
                  (modalMode === "additional" && !modalData.name.trim()) ||
                  (modalMode === "product" && !modalData.is_custom && !modalData.name.trim())
                }
                className="px-4 py-2 rounded-lg bg-white text-slate-900 text-sm font-semibold active:scale-95 disabled:opacity-50"
              >
                {editingId ? "Salvar" : "Criar"}
              </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {canEditProducts && additionalLinkPromptOpen && additionalToLink && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-3 sm:p-4">
          <div className="w-full max-w-lg rounded-3xl bg-white border border-slate-200 shadow-xl p-5 space-y-4">
            <div className="space-y-1">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Vincular adicional</p>
              <h3 className="text-xl font-semibold text-slate-900">{additionalToLink.name}</h3>
              <p className="text-sm text-slate-600">
                Deseja vincular este adicional a produtos ja cadastrados?
              </p>
            </div>
            <div className="max-h-64 overflow-y-auto rounded-xl border border-slate-200 bg-slate-50 p-2 space-y-1">
              {selectedStoreProducts.length === 0 ? (
                <p className="text-sm text-slate-600 px-2 py-2">Nenhum produto disponivel para vinculo nesta loja.</p>
              ) : (
                selectedStoreProducts.map((product) => (
                  <label
                    key={product.id}
                    className="flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 hover:bg-white"
                  >
                    <span className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={selectedProductIdsForAdditional.includes(product.id)}
                        onChange={() => toggleProductForAdditionalLink(product.id)}
                      />
                      <span className="text-sm text-slate-700">{product.name ?? "Produto customizado"}</span>
                    </span>
                    <span className="text-xs text-slate-500">{formatMoney(product.price_cents)}</span>
                  </label>
                ))
              )}
            </div>
            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setAdditionalLinkPromptOpen(false);
                  setAdditionalToLink(null);
                  setSelectedProductIdsForAdditional([]);
                }}
                className="px-4 py-2 rounded-lg bg-slate-100 text-slate-800 text-sm hover:bg-slate-200"
              >
                Agora nao
              </button>
              <button
                type="button"
                onClick={linkAdditionalToProducts}
                disabled={loading}
                className="px-4 py-2 rounded-lg bg-[#6320ee] text-white text-sm font-semibold disabled:opacity-50"
              >
                Vincular produtos
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}




