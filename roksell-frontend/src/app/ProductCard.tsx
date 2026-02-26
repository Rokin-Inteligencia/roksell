"use client";

import { MouseEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { createPortal } from "react-dom";
import { Additional, Product } from "@/types";
import { lockBodyScroll } from "@/lib/body-scroll-lock";
import { fmtBRL } from "@/lib/api";
import { EDIT_CART_LINE_EVENT, type EditCartLineDetail } from "@/lib/cart-events";
import { useCart, type CartItem } from "@/store/cart";

type ModalStep = "config" | "summary";

export default function ProductCard({
  product,
  additionals,
  contactUrl,
}: {
  product: Product;
  additionals?: Additional[];
  contactUrl?: string | null;
}) {
  const [open, setOpen] = useState(false);
  const [visible, setVisible] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const [step, setStep] = useState<ModalStep>("config");
  const [selectedAdditionalIds, setSelectedAdditionalIds] = useState<string[]>([]);
  const [itemNotes, setItemNotes] = useState("");
  const [quantity, setQuantity] = useState(1);
  const [editingLineId, setEditingLineId] = useState<string | null>(null);
  const [draftVisible, setDraftVisible] = useState(true);
  const trackRef = useRef<HTMLDivElement | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [portalTarget, setPortalTarget] = useState<HTMLElement | null>(null);

  const add = useCart((state) => state.add);
  const removeLine = useCart((state) => state.removeLine);
  const cartItems = useCart((state) => state.items);
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const [customOpen, setCustomOpen] = useState(false);
  const [customVisible, setCustomVisible] = useState(false);
  const [customName, setCustomName] = useState("");
  const [customDescription, setCustomDescription] = useState("");
  const [customWeight, setCustomWeight] = useState("");
  const [customPrice, setCustomPrice] = useState("");
  const [customError, setCustomError] = useState<string | null>(null);

  const resolvedContactUrl = contactUrl ?? process.env.NEXT_PUBLIC_CONTACT_URL;
  const availability = product.availability_status ?? (product.block_sale ? "order" : "available");
  const isOrder = availability === "order";
  const isUnavailable = availability === "unavailable";

  const tenant = useMemo(() => {
    if (!pathname) return "";
    const parts = pathname.split("/").filter(Boolean);
    if (parts[0] === "vitrine" && parts[1]) return parts[1];
    return "";
  }, [pathname]);
  const storeFromPath = useMemo(() => {
    if (!pathname) return "";
    const parts = pathname.split("/").filter(Boolean);
    if (parts[0] === "vitrine" && parts[2]) return parts[2];
    return "";
  }, [pathname]);
  const storeFromQuery = (searchParams.get("store") || searchParams.get("store_id") || "").trim();
  const storeRef = storeFromQuery || storeFromPath;
  const checkoutHref = useMemo(() => {
    const params = new URLSearchParams();
    if (tenant) params.set("tenant", tenant);
    if (storeRef) params.set("store", storeRef);
    const suffix = params.toString();
    return suffix ? `/checkout?${suffix}` : "/checkout";
  }, [tenant, storeRef]);

  const productName = product.name ?? "Produto customizado";
  const mediaItems = [
    ...(product.video_url ? [{ type: "video" as const, url: product.video_url }] : []),
    ...(product.image_url ? [{ type: "image" as const, url: product.image_url }] : []),
  ];

  const availableAdditionals = useMemo(() => {
    if (!product.additionals_enabled) return [];
    const allowedIds = new Set(product.additional_ids ?? []);
    return (additionals ?? [])
      .filter((item) => item.is_active && allowedIds.has(item.id))
      .sort((a, b) => (a.display_order ?? 0) - (b.display_order ?? 0));
  }, [additionals, product.additionals_enabled, product.additional_ids]);

  const additionalById = useMemo(
    () => new Map(availableAdditionals.map((item) => [item.id, item])),
    [availableAdditionals]
  );

  const selectedAdditionals = useMemo(
    () =>
      selectedAdditionalIds
        .map((id) => additionalById.get(id))
        .filter((item): item is Additional => Boolean(item)),
    [selectedAdditionalIds, additionalById]
  );

  const additionalCents = useMemo(
    () => selectedAdditionals.reduce((sum, item) => sum + (item.price_cents || 0), 0),
    [selectedAdditionals]
  );
  const unitPriceCents = (product.price_cents || 0) + additionalCents;
  const itemSubtotalCents = unitPriceCents * quantity;
  const existingOrderItems = useMemo(
    () => (editingLineId ? cartItems.filter((item) => item.lineId !== editingLineId) : cartItems),
    [cartItems, editingLineId]
  );
  const previewOrderItems = useMemo(
    () => [
      ...existingOrderItems,
      ...(draftVisible
        ? [
            {
              lineId: "__preview__",
              productId: product.id,
              name: productName,
              price: unitPriceCents,
              quantity,
              imageUrl: product.image_url ?? undefined,
              additionals: selectedAdditionals.map((item) => ({
                id: item.id,
                name: item.name,
                description: item.description ?? undefined,
                price_cents: item.price_cents,
              })),
              itemNotes: itemNotes.trim() || undefined,
            },
          ]
        : []),
    ],
    [
      existingOrderItems,
      draftVisible,
      product.id,
      productName,
      product.image_url,
      unitPriceCents,
      quantity,
      selectedAdditionals,
      itemNotes,
    ]
  );
  const previewOrderTotalCents = useMemo(
    () => previewOrderItems.reduce((sum, item) => sum + item.price * item.quantity, 0),
    [previewOrderItems]
  );

  useEffect(() => {
    setPortalTarget(document.body);
  }, []);

  useEffect(() => {
    if (!open && !customOpen) return;
    return lockBodyScroll();
  }, [open, customOpen]);

  useEffect(() => {
    if (!open) return;
    setActiveIndex(0);
    const track = trackRef.current;
    if (!track) return;
    track.scrollLeft = 0;
  }, [open, product.id]);

  useEffect(() => {
    if (!open) return;
    const video = videoRef.current;
    if (!video) return;
    const play = async () => {
      try {
        await video.play();
      } catch {
        /* autoplay can be blocked */
      }
    };
    play();
  }, [open, product.id]);

  useEffect(() => {
    setSelectedAdditionalIds((prev) => prev.filter((id) => additionalById.has(id)));
  }, [additionalById]);

  const stop = (e: MouseEvent) => e.stopPropagation();

  function resetFlowState() {
    setStep("config");
    setQuantity(1);
    setSelectedAdditionalIds([]);
    setItemNotes("");
    setEditingLineId(null);
    setDraftVisible(true);
  }

  function openDetails() {
    if (product.is_custom) {
      openCustom();
      return;
    }
    resetFlowState();
    setOpen(true);
    requestAnimationFrame(() => setVisible(true));
  }

  function closeDetails() {
    setVisible(false);
    setEditingLineId(null);
    setDraftVisible(true);
    setOpen(false);
  }

  function toggleAdditional(id: string) {
    setSelectedAdditionalIds((prev) => {
      if (prev.includes(id)) return prev.filter((item) => item !== id);
      return [...prev, id];
    });
  }

  const loadLineForEdit = useCallback(
    (line: CartItem) => {
      setStep("config");
      setEditingLineId(line.lineId);
      setDraftVisible(true);
      setQuantity(Math.max(1, line.quantity || 1));
      setItemNotes(line.itemNotes ?? "");
      setSelectedAdditionalIds((line.additionals ?? []).map((item) => item.id));
      if (!open) {
        setOpen(true);
        requestAnimationFrame(() => setVisible(true));
      }
    },
    [open]
  );

  useEffect(() => {
    function onEditLine(event: Event) {
      const customEvent = event as CustomEvent<EditCartLineDetail>;
      const detail = customEvent.detail;
      if (!detail || detail.productId !== product.id) return;
      const line = cartItems.find((item) => item.lineId === detail.lineId);
      if (!line || line.isCustom) return;
      loadLineForEdit(line);
    }
    window.addEventListener(EDIT_CART_LINE_EVENT, onEditLine);
    return () => window.removeEventListener(EDIT_CART_LINE_EVENT, onEditLine);
  }, [cartItems, loadLineForEdit, product.id]);

  function editLine(line: CartItem) {
    if (line.lineId === "__preview__") {
      setDraftVisible(true);
      setStep("config");
      return;
    }
    if (line.isCustom) return;
    if (line.productId !== product.id) {
      window.dispatchEvent(
        new CustomEvent<EditCartLineDetail>(EDIT_CART_LINE_EVENT, {
          detail: { lineId: line.lineId, productId: line.productId },
        })
      );
      closeDetails();
      return;
    }
    loadLineForEdit(line);
  }

  function addConfiguredItemToCart() {
    if (!draftVisible) return;
    if (editingLineId) {
      const lineToReplace = cartItems.find((item) => item.lineId === editingLineId && item.productId === product.id);
      if (lineToReplace) {
        removeLine(editingLineId);
      }
    }
    add({
      productId: product.id,
      name: productName,
      price: unitPriceCents,
      quantity,
      imageUrl: product.image_url ?? undefined,
      additionals: selectedAdditionals.map((item) => ({
        id: item.id,
        name: item.name,
        description: item.description ?? undefined,
        price_cents: item.price_cents,
      })),
      itemNotes: itemNotes.trim() || undefined,
    });
    setEditingLineId(null);
  }

  function removeLineFromSummary(line: CartItem) {
    if (line.lineId === "__preview__") {
      if (editingLineId) {
        removeLine(editingLineId);
        setEditingLineId(null);
      }
      setDraftVisible(false);
      return;
    }
    removeLine(line.lineId);
  }

  function continueShopping() {
    addConfiguredItemToCart();
    closeDetails();
  }

  function continueToCheckout() {
    addConfiguredItemToCart();
    closeDetails();
    router.push(checkoutHref);
  }

  function onCardClick() {
    openDetails();
  }

  function onAddClick(e: MouseEvent) {
    e.stopPropagation();
    if (isUnavailable) return;
    if (isOrder) {
      if (resolvedContactUrl) {
        window.open(resolvedContactUrl, "_blank", "noopener,noreferrer");
      }
      return;
    }
    openDetails();
  }

  const openCustom = () => {
    if (open) {
      setVisible(false);
      setOpen(false);
    }
    setCustomError(null);
    setCustomName("");
    setCustomDescription("");
    setCustomWeight("");
    setCustomPrice("");
    setCustomOpen(true);
    requestAnimationFrame(() => setCustomVisible(true));
  };

  const closeCustom = () => {
    setCustomVisible(false);
    setCustomOpen(false);
  };

  function parsePriceToCents(value: string) {
    const normalized = value.replace(/\./g, "").replace(",", ".");
    const parsed = Number(normalized);
    if (Number.isNaN(parsed)) return 0;
    return Math.round(parsed * 100);
  }

  function addCustomToCart() {
    const priceCents = parsePriceToCents(customPrice.trim());
    if (!customName.trim() || priceCents <= 0) {
      setCustomError("Informe nome e preco validos.");
      return;
    }
    add({
      productId: product.id,
      name: customName.trim(),
      price: priceCents,
      imageUrl: product.image_url ?? undefined,
      isCustom: true,
      custom: {
        name: customName.trim(),
        description: customDescription.trim() || undefined,
        weight: customWeight.trim() || undefined,
      },
    });
    setCustomError(null);
    setCustomName("");
    setCustomDescription("");
    setCustomWeight("");
    setCustomPrice("");
    closeCustom();
  }

  function renderActionButton() {
    if (isOrder) {
      if (!resolvedContactUrl) {
        return (
          <button
            type="button"
            disabled
            className="px-3 py-2 rounded-xl text-sm font-medium bg-neutral-200 text-neutral-500 cursor-not-allowed"
          >
            Encomendar
          </button>
        );
      }
      return (
        <a
          href={resolvedContactUrl}
          target="_blank"
          rel="noreferrer"
          onClick={stop}
          className="px-3 py-2 rounded-xl text-sm font-medium bg-emerald-500 text-white hover:brightness-95 active:scale-95 transition-transform"
        >
          Encomendar
        </a>
      );
    }
    if (isUnavailable) {
      return (
        <button
          type="button"
          disabled
          className="px-3 py-2 rounded-xl text-sm font-medium bg-neutral-200 text-neutral-500 cursor-not-allowed"
        >
          Indisponivel
        </button>
      );
    }
    return (
      <button
        type="button"
        onClick={onAddClick}
        className="px-3 py-2 rounded-xl text-sm font-medium text-white bg-[#6320ee] hover:brightness-95 active:scale-95 transition"
      >
        {product.is_custom ? "Personalizar" : "Adicionar"}
      </button>
    );
  }

  return (
    <>
      <div
        className="rounded-xl bg-white/95 border border-neutral-200 shadow-sm flex items-stretch cursor-pointer overflow-hidden active:scale-[0.99] transition-transform duration-150 hover:-translate-y-0.5 hover:shadow-md"
        onClick={onCardClick}
      >
        {product.image_url ? (
          <>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={product.image_url}
              alt={productName}
              className="w-28 h-28 object-cover flex-shrink-0 bg-neutral-100"
              loading="lazy"
            />
          </>
        ) : (
          <div className="w-28 h-28 bg-neutral-100 flex-shrink-0 grid place-items-center text-neutral-400 text-xs">
            Sem foto
          </div>
        )}
        <div className="flex-1 min-w-0 p-3 flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="font-semibold text-base truncate text-neutral-900">{productName}</div>
            <div className="mt-1 text-base text-neutral-700">
              {product.is_custom ? "Sob encomenda" : fmtBRL((product.price_cents || 0) / 100)}
            </div>
          </div>
          <div onClick={stop}>{renderActionButton()}</div>
        </div>
      </div>

      {open &&
        portalTarget &&
        createPortal(
          <div
            className={`fixed inset-0 z-[80] flex items-center justify-center p-3 sm:p-4 transition-opacity duration-200 ${
              visible ? "bg-black/55 opacity-100" : "bg-black/0 opacity-0"
            }`}
            onClick={closeDetails}
          >
            <div
              className={`w-full max-w-lg max-h-[92vh] overflow-y-auto bg-white rounded-2xl shadow-2xl transition-all duration-200 ${
                visible ? "opacity-100 translate-y-0 scale-100" : "opacity-0 translate-y-2 scale-95"
              }`}
              onClick={stop}
            >
              {mediaItems.length > 0 && (
                <div
                  className={`overflow-hidden transition-all duration-300 ease-in-out ${
                    step === "config" ? "max-h-[22rem] opacity-100" : "max-h-0 opacity-0"
                  }`}
                >
                  <div
                    className={`w-full h-64 sm:h-72 bg-neutral-100 relative transition-transform duration-300 ease-in-out ${
                      step === "config" ? "translate-y-0" : "-translate-y-2"
                    }`}
                  >
                    <div
                      ref={trackRef}
                      className="flex h-full overflow-x-auto snap-x snap-mandatory scroll-smooth"
                      style={{ scrollbarWidth: "none", msOverflowStyle: "none" }}
                      onScroll={() => {
                        const track = trackRef.current;
                        if (!track) return;
                        const nextIndex = Math.round(track.scrollLeft / track.clientWidth);
                        if (nextIndex !== activeIndex) setActiveIndex(nextIndex);
                      }}
                    >
                      {mediaItems.map((item, idx) => (
                        <div key={`${item.type}-${idx}`} className="min-w-full h-64 sm:h-72 snap-center">
                          {item.type === "video" ? (
                            <video
                              ref={idx === 0 ? videoRef : undefined}
                              src={item.url}
                              className="w-full h-64 sm:h-72 object-cover bg-neutral-100"
                              controls
                              preload="auto"
                              muted
                              playsInline
                              autoPlay
                              loop
                            />
                          ) : (
                            <>
                              {/* eslint-disable-next-line @next/next/no-img-element */}
                              <img
                                src={item.url}
                                alt={productName}
                                className="w-full h-64 sm:h-72 object-cover bg-neutral-100"
                              />
                            </>
                          )}
                        </div>
                      ))}
                    </div>
                    {mediaItems.length > 1 && (
                      <div className="absolute bottom-3 left-1/2 -translate-x-1/2 flex items-center gap-2">
                        {mediaItems.map((_, idx) => (
                          <span
                            key={`dot-${idx}`}
                            className={`h-2 w-2 rounded-full ${idx === activeIndex ? "bg-white" : "bg-white/50"}`}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {step === "config" ? (
                <div className="p-4 sm:p-5 space-y-4">
                  <div className="space-y-2">
                    <p className="text-xs uppercase tracking-[0.18em] text-neutral-500">Detalhes do produto</p>
                    <h3 className="text-xl font-semibold text-neutral-900">{productName}</h3>
                    {product.description && (
                      <p className="text-sm text-neutral-600 whitespace-pre-wrap">{product.description}</p>
                    )}
                    <p className="text-sm font-semibold text-neutral-800">
                      Valor: {fmtBRL((product.price_cents || 0) / 100)}
                    </p>
                  </div>

                  {availableAdditionals.length > 0 && (
                    <section className="rounded-2xl border border-violet-200 bg-violet-50/60 p-3 space-y-2">
                      <p className="text-sm font-semibold text-violet-900">Adicionais</p>
                      <div className="space-y-2">
                        {availableAdditionals.map((additional) => {
                          const checked = selectedAdditionalIds.includes(additional.id);
                          return (
                            <label
                              key={additional.id}
                              className={`flex items-start gap-3 rounded-xl border px-3 py-2 cursor-pointer transition ${
                                checked
                                  ? "border-violet-400 bg-white"
                                  : "border-violet-100 bg-white/70 hover:border-violet-300"
                              }`}
                            >
                              <input
                                type="checkbox"
                                checked={checked}
                                onChange={() => toggleAdditional(additional.id)}
                                className="mt-1 h-4 w-4 rounded border-neutral-300 text-[#6320ee] focus:ring-[#6320ee]"
                              />
                              <span className="min-w-0 flex-1">
                                <span className="block text-sm font-medium text-neutral-900">{additional.name}</span>
                                {additional.description && (
                                  <span className="block text-xs text-neutral-500">{additional.description}</span>
                                )}
                              </span>
                              <span className="text-sm font-semibold text-neutral-800">
                                {fmtBRL((additional.price_cents || 0) / 100)}
                              </span>
                            </label>
                          );
                        })}
                      </div>
                    </section>
                  )}

                  {!isUnavailable && (
                    <label className="block space-y-1">
                      <textarea
                        value={itemNotes}
                        onChange={(e) => setItemNotes(e.target.value)}
                        className="input w-full min-h-[92px]"
                        placeholder="Alguma observacao?"
                        aria-label="Alguma observacao?"
                      />
                    </label>
                  )}

                  <div className="rounded-xl border border-neutral-200 bg-neutral-50 px-3 py-2 flex items-center justify-between">
                    <span className="text-sm text-neutral-600">Subtotal do item</span>
                    <span className="text-base font-semibold text-neutral-900">{fmtBRL(itemSubtotalCents / 100)}</span>
                  </div>

                  <div className="grid grid-cols-[1fr_auto_1fr] gap-2 items-center">
                    <button
                      type="button"
                      onClick={closeDetails}
                      className="h-11 rounded-xl bg-rose-600 text-white text-sm font-semibold hover:bg-rose-700 active:scale-[0.99]"
                    >
                      Voltar
                    </button>
                    <div className="h-11 rounded-xl border border-neutral-200 bg-white flex items-center overflow-hidden">
                      <button
                        type="button"
                        onClick={() => setQuantity((prev) => Math.max(1, prev - 1))}
                        className="h-full w-10 text-lg text-neutral-700 hover:bg-neutral-100"
                      >
                        -
                      </button>
                      <span className="h-full min-w-10 px-2 grid place-items-center text-sm font-semibold">{quantity}</span>
                      <button
                        type="button"
                        onClick={() => setQuantity((prev) => prev + 1)}
                        className="h-full w-10 text-lg text-neutral-700 hover:bg-neutral-100"
                      >
                        +
                      </button>
                    </div>
                    {isUnavailable ? (
                      <button
                        type="button"
                        disabled
                        className="h-11 rounded-xl bg-neutral-200 text-neutral-500 text-sm font-semibold cursor-not-allowed"
                      >
                        Indisponivel
                      </button>
                    ) : isOrder ? (
                      resolvedContactUrl ? (
                        <a
                          href={resolvedContactUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="h-11 rounded-xl bg-emerald-600 text-white text-sm font-semibold hover:bg-emerald-700 active:scale-[0.99] grid place-items-center"
                        >
                          Encomendar
                        </a>
                      ) : (
                        <button
                          type="button"
                          disabled
                          className="h-11 rounded-xl bg-neutral-200 text-neutral-500 text-sm font-semibold cursor-not-allowed"
                        >
                          Encomendar
                        </button>
                      )
                    ) : (
                      <button
                        type="button"
                        onClick={() => setStep("summary")}
                        className="h-11 rounded-xl bg-emerald-600 text-white text-sm font-semibold hover:bg-emerald-700 active:scale-[0.99]"
                      >
                        Avancar
                      </button>
                    )}
                  </div>
                </div>
              ) : (
                <div className="p-4 sm:p-5 space-y-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-neutral-500">Resumo do pedido</p>
                    <h3 className="text-xl font-semibold text-neutral-900">Confira antes de confirmar</h3>
                  </div>

                  <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
                    {previewOrderItems.map((item) => (
                      <div
                        key={item.lineId}
                        className="w-full rounded-2xl border border-neutral-200 bg-neutral-50 p-3 flex gap-3"
                      >
                        {item.imageUrl ? (
                          <>
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img
                              src={item.imageUrl}
                              alt={item.name}
                              className="w-16 h-16 rounded-lg object-cover bg-neutral-200 flex-shrink-0"
                            />
                          </>
                        ) : (
                          <div className="w-16 h-16 rounded-lg bg-neutral-200 grid place-items-center text-[10px] text-neutral-500 flex-shrink-0">
                            Sem foto
                          </div>
                        )}
                        {!item.isCustom ? (
                          <button
                            type="button"
                            onClick={() => {
                              setDraftVisible(true);
                              editLine(item);
                            }}
                            className="min-w-0 flex-1 text-left space-y-1 rounded-xl px-1 py-0.5 hover:bg-violet-50"
                          >
                            <p className="text-sm font-semibold text-neutral-900">{item.name}</p>
                            {item.additionals && item.additionals.length > 0 && (
                              <p className="text-xs text-neutral-600">
                                Adicionais: {item.additionals.map((additional) => additional.name).join(", ")}
                              </p>
                            )}
                            {item.itemNotes && <p className="text-xs text-neutral-600">Obs: {item.itemNotes}</p>}
                            <p className="text-xs text-neutral-500">Quantidade: {item.quantity}</p>
                            <p className="text-[11px] font-medium text-violet-700">Toque para editar</p>
                          </button>
                        ) : (
                          <div className="min-w-0 flex-1 space-y-1 px-1 py-0.5">
                            <p className="text-sm font-semibold text-neutral-900">
                              {item.name}
                              {item.lineId === "__preview__" && (
                                <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded-full bg-[#ede7ff] text-[#4a19b3]">
                                  Novo
                                </span>
                              )}
                            </p>
                            {item.additionals && item.additionals.length > 0 && (
                              <p className="text-xs text-neutral-600">
                                Adicionais: {item.additionals.map((additional) => additional.name).join(", ")}
                              </p>
                            )}
                            {item.itemNotes && <p className="text-xs text-neutral-600">Obs: {item.itemNotes}</p>}
                            <p className="text-xs text-neutral-500">Quantidade: {item.quantity}</p>
                          </div>
                        )}
                        <div className="flex flex-col items-end justify-between gap-2">
                          <div className="text-sm font-semibold text-neutral-900">
                            {fmtBRL((item.price * item.quantity) / 100)}
                          </div>
                          {item.lineId !== "__preview__" && (
                            <button
                              type="button"
                              onClick={() => removeLineFromSummary(item)}
                              className="h-8 w-8 rounded-lg border border-rose-200 text-rose-600 hover:bg-rose-50 grid place-items-center"
                              aria-label={`Excluir ${item.name}`}
                              title="Excluir item"
                            >
                              <svg
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="1.8"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                className="h-4 w-4"
                                aria-hidden
                              >
                                <path d="M3 6h18" />
                                <path d="M8 6V4h8v2" />
                                <path d="M19 6l-1 14H6L5 6" />
                                <path d="M10 11v6" />
                                <path d="M14 11v6" />
                              </svg>
                            </button>
                          )}
                          {item.lineId === "__preview__" && (
                            <button
                              type="button"
                              onClick={() => removeLineFromSummary(item)}
                              className="h-8 w-8 rounded-lg border border-rose-200 text-rose-600 hover:bg-rose-50 grid place-items-center"
                              aria-label={`Excluir ${item.name}`}
                              title="Excluir item"
                            >
                              <svg
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="1.8"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                className="h-4 w-4"
                                aria-hidden
                              >
                                <path d="M3 6h18" />
                                <path d="M8 6V4h8v2" />
                                <path d="M19 6l-1 14H6L5 6" />
                                <path d="M10 11v6" />
                                <path d="M14 11v6" />
                              </svg>
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>

                  <button
                    type="button"
                    onClick={continueShopping}
                    className="w-full h-12 rounded-2xl bg-[#6320ee] text-white text-sm font-semibold hover:brightness-95 active:scale-[0.99]"
                  >
                    Continue comprando
                  </button>

                  <div className="rounded-2xl border border-neutral-200 bg-white p-3 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-neutral-600">Valor total</span>
                      <span className="text-lg font-semibold text-neutral-900">
                        {fmtBRL(previewOrderTotalCents / 100)}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <button
                        type="button"
                        onClick={() => setStep("config")}
                        className="h-11 rounded-xl bg-neutral-200 text-neutral-800 text-sm font-semibold hover:bg-neutral-300 active:scale-[0.99]"
                      >
                        Voltar
                      </button>
                      <button
                        type="button"
                        onClick={continueToCheckout}
                        className="h-11 rounded-xl bg-emerald-600 text-white text-sm font-semibold hover:bg-emerald-700 active:scale-[0.99]"
                      >
                        Avancar
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>,
          portalTarget
        )}

      {customOpen &&
        portalTarget &&
        createPortal(
          <div
            className={`fixed inset-0 z-[90] flex items-center justify-center p-4 transition-opacity duration-200 ${
              customVisible ? "bg-black/50 opacity-100" : "bg-black/0 opacity-0"
            }`}
            onClick={closeCustom}
          >
            <div
              className={`w-full max-w-md bg-white rounded-xl shadow-lg overflow-hidden transition-all duration-200 ${
                customVisible ? "opacity-100 translate-y-0 scale-100" : "opacity-0 translate-y-2 scale-95"
              }`}
              onClick={stop}
            >
              <div className="p-4 space-y-3">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-neutral-500">Produto customizado</p>
                    <h3 className="text-xl font-semibold text-neutral-900">{productName}</h3>
                  </div>
                  <button
                    onClick={closeCustom}
                    className="text-sm px-3 py-1 rounded-full bg-neutral-100 hover:bg-neutral-200"
                  >
                    Fechar
                  </button>
                </div>
                <label className="block space-y-1 text-sm">
                  <span>Nome</span>
                  <input
                    className="input w-full"
                    value={customName}
                    onChange={(e) => setCustomName(e.target.value)}
                    placeholder="Ex.: Bolo de chocolate"
                  />
                </label>
                <label className="block space-y-1 text-sm">
                  <span>Descricao</span>
                  <textarea
                    className="input w-full min-h-[80px]"
                    value={customDescription}
                    onChange={(e) => setCustomDescription(e.target.value)}
                    placeholder="Detalhes, sabores, recheio..."
                  />
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <label className="block space-y-1 text-sm">
                    <span>Peso</span>
                    <input
                      className="input w-full"
                      value={customWeight}
                      onChange={(e) => setCustomWeight(e.target.value)}
                      placeholder="Ex.: 2kg"
                    />
                  </label>
                  <label className="block space-y-1 text-sm">
                    <span>Preco</span>
                    <input
                      className="input w-full"
                      value={customPrice}
                      onChange={(e) => setCustomPrice(e.target.value)}
                      placeholder="Ex.: 120,00"
                    />
                  </label>
                </div>
                {customError && <p className="text-sm text-red-600">{customError}</p>}
                <div className="flex gap-2 pt-2">
                  <button
                    onClick={closeCustom}
                    className="px-3 py-2 rounded-lg bg-neutral-200 hover:bg-neutral-300 active:scale-95"
                  >
                    Cancelar
                  </button>
                  <button
                    onClick={addCustomToCart}
                    className="px-3 py-2 rounded-lg bg-[#A0A0B2] text-neutral-900 font-medium hover:bg-[#8c8ca1]"
                  >
                    Adicionar
                  </button>
                </div>
              </div>
            </div>
          </div>,
          portalTarget
        )}
    </>
  );
}
