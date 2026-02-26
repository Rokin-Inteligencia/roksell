"use client";

import { MouseEvent, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { createPortal } from "react-dom";
import { lockBodyScroll } from "@/lib/body-scroll-lock";
import { fmtBRL } from "@/lib/api";
import { EDIT_CART_LINE_EVENT, type EditCartLineDetail } from "@/lib/cart-events";
import { useCart, type CartItem } from "@/store/cart";

function BasketIcon({ className = "" }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M6.5 9h11l1.3 10.5a2 2 0 0 1-2 2.3H7.2a2 2 0 0 1-2-2.3L6.5 9Z" />
      <path d="M9 9V7a3 3 0 0 1 6 0v2" />
      <path d="M8 13h8" />
    </svg>
  );
}

export default function CartIcon() {
  const items = useCart((state) => state.items);
  const removeLine = useCart((state) => state.removeLine);
  const count = items.reduce((acc, item) => acc + (item.quantity || 0), 0);
  const totalCents = items.reduce((acc, item) => acc + item.price * item.quantity, 0);

  const [showFloating, setShowFloating] = useState(false);
  const [open, setOpen] = useState(false);
  const [visible, setVisible] = useState(false);
  const [portalTarget, setPortalTarget] = useState<HTMLElement | null>(null);
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();

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

  const storeParam = searchParams.get("store") || searchParams.get("store_id") || storeFromPath || "";
  const checkoutHref = useMemo(() => {
    const params = new URLSearchParams();
    if (tenant) params.set("tenant", tenant);
    if (storeParam) params.set("store", storeParam);
    const suffix = params.toString();
    return suffix ? `/checkout?${suffix}` : "/checkout";
  }, [tenant, storeParam]);

  useEffect(() => {
    setPortalTarget(document.body);
  }, []);

  useEffect(() => {
    const onScroll = () => setShowFloating(window.scrollY > 80);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!open) return;
    return lockBodyScroll();
  }, [open]);

  function openSummary(e?: MouseEvent) {
    e?.stopPropagation();
    setOpen(true);
    requestAnimationFrame(() => setVisible(true));
  }

  function closeSummary() {
    setVisible(false);
    setOpen(false);
  }

  function goCheckout() {
    closeSummary();
    router.push(checkoutHref);
  }

  function editCartItem(item: CartItem) {
    if (item.isCustom) return;
    window.dispatchEvent(
      new CustomEvent<EditCartLineDetail>(EDIT_CART_LINE_EVENT, {
        detail: { lineId: item.lineId, productId: item.productId },
      })
    );
    closeSummary();
  }

  return (
    <>
      <button
        type="button"
        onClick={openSummary}
        aria-label="Carrinho"
        className="relative inline-block text-accent"
      >
        <BasketIcon className="w-7 h-7" />
        {count > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[1.25rem] h-5 px-1 rounded-full bg-accent text-white text-xs grid place-items-center">
            {count}
          </span>
        )}
      </button>

      <button
        type="button"
        onClick={openSummary}
        aria-label="Carrinho"
        className={`fixed z-50 bottom-24 right-5 bg-white shadow-lg rounded-full border text-accent transition-all duration-200 ${
          showFloating ? "opacity-100 translate-y-0" : "opacity-0 pointer-events-none translate-y-2"
        }`}
      >
        <span className="relative block p-3">
          <BasketIcon className="w-6 h-6" />
          {count > 0 && (
            <span className="absolute -top-1 -right-1 min-w-[1.25rem] h-5 px-1 rounded-full bg-accent text-white text-xs grid place-items-center">
              {count}
            </span>
          )}
        </span>
      </button>

      {open &&
        portalTarget &&
        createPortal(
          <div
            className={`fixed inset-0 z-[90] flex items-center justify-center p-3 sm:p-4 transition-opacity duration-200 ${
              visible ? "bg-black/55 opacity-100" : "bg-black/0 opacity-0"
            }`}
            onClick={closeSummary}
          >
            <div
              className={`w-full max-w-lg max-h-[92vh] overflow-y-auto bg-white rounded-2xl shadow-2xl transition-all duration-200 ${
                visible ? "opacity-100 translate-y-0 scale-100" : "opacity-0 translate-y-2 scale-95"
              }`}
              onClick={(event) => event.stopPropagation()}
            >
              <div className="p-4 sm:p-5 space-y-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-neutral-500">Resumo do pedido</p>
                  <h3 className="text-xl font-semibold text-neutral-900">Confira antes de confirmar</h3>
                </div>

                {items.length === 0 ? (
                  <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-4 text-sm text-neutral-600">
                    Nenhum item no carrinho.
                  </div>
                ) : (
                  <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
                    {items.map((item) => (
                      <div key={item.lineId} className="w-full rounded-2xl border border-neutral-200 bg-neutral-50 p-3 flex gap-3">
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
                            onClick={() => editCartItem(item)}
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
                            <p className="text-sm font-semibold text-neutral-900">{item.name}</p>
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
                          <button
                            type="button"
                            onClick={() => removeLine(item.lineId)}
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
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                <button
                  type="button"
                  onClick={closeSummary}
                  className="w-full h-12 rounded-2xl bg-[#6320ee] text-white text-sm font-semibold hover:brightness-95 active:scale-[0.99]"
                >
                  Continue comprando
                </button>

                <div className="rounded-2xl border border-neutral-200 bg-white p-3 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-neutral-600">Valor total</span>
                    <span className="text-lg font-semibold text-neutral-900">{fmtBRL(totalCents / 100)}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={closeSummary}
                      className="h-11 rounded-xl bg-neutral-200 text-neutral-800 text-sm font-semibold hover:bg-neutral-300 active:scale-[0.99]"
                    >
                      Voltar
                    </button>
                    <button
                      type="button"
                      onClick={goCheckout}
                      disabled={items.length === 0}
                      className="h-11 rounded-xl bg-emerald-600 text-white text-sm font-semibold hover:bg-emerald-700 active:scale-[0.99] disabled:opacity-50"
                    >
                      Avancar
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>,
          portalTarget
        )}
    </>
  );
}
