"use client";
import { useCart } from "@/store/cart";
import { Product } from "@/types";
import { useState } from "react";

export default function AddBtn({
  product,
  onCustomClick,
  contactUrl,
}: {
  product: Product;
  onCustomClick?: () => void;
  contactUrl?: string | null;
}) {
  const add = useCart((s) => s.add);
  const [ok, setOk] = useState(false);
  const resolvedContactUrl = contactUrl ?? process.env.NEXT_PUBLIC_CONTACT_URL;
  const availability =
    product.availability_status ?? (product.block_sale ? "order" : "available");
  const isOrder = availability === "order";
  const isUnavailable = availability === "unavailable";

  function onClick() {
    if (isOrder || isUnavailable) {
      return;
    }
    if (product.is_custom) {
      onCustomClick?.();
      return;
    }
    add({ productId: product.id, name: product.name, price: product.price_cents });
    setOk(true);
    window.setTimeout(() => setOk(false), 900);
  }

  if (isOrder) {
    if (!resolvedContactUrl) {
      return (
        <button
          className="px-3 py-2 rounded-lg text-sm font-medium bg-neutral-200 text-neutral-500 cursor-not-allowed"
          disabled
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
        className="px-3 py-2 rounded-lg text-sm font-medium bg-emerald-500 text-white hover:brightness-95 active:scale-95 transition-transform"
      >
        Encomendar
      </a>
    );
  }
  if (isUnavailable) {
    return (
      <button
        className="px-3 py-2 rounded-lg text-sm font-medium bg-neutral-200 text-neutral-500 cursor-not-allowed"
        disabled
      >
        Indisponivel
      </button>
    );
  }

  return (
    <button
      onClick={onClick}
      className={`relative px-3 py-2 rounded-lg text-sm font-medium text-neutral-900 active:scale-95 transition-colors transition-transform duration-200 ${
        ok ? "bg-[#8c8ca1] scale-105" : "bg-[#A0A0B2] hover:bg-[#8c8ca1]"
      }`}
      aria-live="polite"
    >
      <span
        className={`block transition-all duration-200 ${
          ok ? "opacity-0 -translate-y-1" : "opacity-100 translate-y-0"
        }`}
      >
        {product.is_custom ? "Personalizar" : "Adicionar"}
      </span>
      <span
        className={`pointer-events-none absolute inset-0 grid place-items-center transition-all duration-200 ${
          ok ? "opacity-100 translate-y-0" : "opacity-0 translate-y-1"
        }`}
        aria-hidden
      >
        OK
      </span>
    </button>
  );
}
