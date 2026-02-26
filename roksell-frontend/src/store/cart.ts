import { create } from "zustand";

export type CartCustomDetails = {
  name?: string;
  description?: string;
  weight?: string;
};

export type CartAdditional = {
  id: string;
  name: string;
  description?: string;
  price_cents: number;
};

export type CartItem = {
  lineId: string;
  productId: string;
  name: string;
  price: number;
  quantity: number;
  imageUrl?: string;
  isCustom?: boolean;
  custom?: CartCustomDetails;
  additionals?: CartAdditional[];
  itemNotes?: string;
};

type AddToCartPayload = {
  productId: string;
  name: string;
  price: number;
  quantity?: number;
  imageUrl?: string;
  isCustom?: boolean;
  custom?: CartCustomDetails;
  additionals?: CartAdditional[];
  itemNotes?: string;
};

type CartState = {
  items: CartItem[];
  add: (payload: AddToCartPayload) => void;
  inc: (id: string) => void;
  dec: (id: string) => void;
  removeLine: (id: string) => void;
  clear: () => void;
  subtotal: () => number;
};

function normalizeLineId(payload: AddToCartPayload): string {
  if (payload.isCustom) {
    return crypto.randomUUID();
  }
  const additionalIds = (payload.additionals ?? [])
    .map((item) => item.id)
    .sort()
    .join(",");
  const itemNotes = (payload.itemNotes || "").trim().toLowerCase();
  return `${payload.productId}::${additionalIds}::${itemNotes}`;
}

export const useCart = create<CartState>((set, get) => ({
  items: [],
  add: (payload) =>
    set((state) => {
      const quantity = Math.max(1, Math.floor(payload.quantity ?? 1));
      const lineId = normalizeLineId(payload);
      const itemNotes = (payload.itemNotes || "").trim() || undefined;
      if (payload.isCustom) {
        return {
          items: [
            ...state.items,
            {
              ...payload,
              lineId,
              quantity,
              itemNotes,
            },
          ],
        };
      }
      const existing = state.items.find((item) => item.lineId === lineId && !item.isCustom);
      if (existing) {
        return {
          items: state.items.map((item) =>
            item.lineId === lineId ? { ...item, quantity: item.quantity + quantity } : item
          ),
        };
      }
      return {
        items: [
          ...state.items,
          {
            ...payload,
            lineId,
            quantity,
            itemNotes,
          },
        ],
      };
    }),
  inc: (id) =>
    set((state) => ({
      items: state.items.map((item) => (item.lineId === id ? { ...item, quantity: item.quantity + 1 } : item)),
    })),
  dec: (id) =>
    set((state) => ({
      items: state.items.flatMap((item) =>
        item.lineId === id ? (item.quantity > 1 ? [{ ...item, quantity: item.quantity - 1 }] : []) : [item]
      ),
    })),
  removeLine: (id) =>
    set((state) => ({
      items: state.items.filter((item) => item.lineId !== id),
    })),
  clear: () => set({ items: [] }),
  subtotal: () => get().items.reduce((acc, item) => acc + item.price * item.quantity, 0),
}));
