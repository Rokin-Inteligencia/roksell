"use client";
import { useEffect, useMemo, useState } from "react";
import { api, fmtBRL } from "@/lib/api";
import { useParams, useSearchParams } from "next/navigation";

type PedidoItem = {
  produto_id: string;
  qtd: number;
  preco_unit_centavos: number;
  nome?: string;
};

type Endereco = {
  cep: string;
  logradouro: string;
  numero: string;
  complemento?: string | null;
  bairro?: string | null;
  cidade: string;
  uf: string;
  referencia?: string | null;
};

type Entrega = {
  status?: string | null;
  cep?: string | null;
  logradouro?: string | null;
  numero?: string | null;
  complemento?: string | null;
  bairro?: string | null;
  cidade?: string | null;
  uf?: string | null;
  referencia?: string | null;
} | null;

// Normalized shape for UI rendering (all optional + nullable)
type EnderecoDisplay = {
  nome?: string | null;
  cep?: string | null;
  logradouro?: string | null;
  numero?: string | null;
  complemento?: string | null;
  bairro?: string | null;
  cidade?: string | null;
  uf?: string | null;
  referencia?: string | null;
};

type StoreAddress = {
  id?: string;
  name?: string | null;
  postal_code?: string | null;
  street?: string | null;
  number?: string | null;
  complement?: string | null;
  district?: string | null;
  city?: string | null;
  state?: string | null;
  reference?: string | null;
} | null;

type PedidoDetalhe = {
  id: string;
  status: string;
  customer_name?: string | null;
  whatsapp_contact_phone?: string | null;
  whatsapp_order_message?: string | null;
  pix_key?: string | null;
  notes?: string | null;
  subtotal_centavos: number;
  frete_centavos?: number | null;
  frete?: { valor_centavos?: number | null } | null;
  total_centavos: number;
  itens: PedidoItem[];
  pagamento?: { metodo?: string | null; status?: string | null; troco_para?: number | null } | null;
  entrega?: Entrega;
  retirada?: boolean | null;
  endereco?: Endereco | null;
  store?: StoreAddress;
};

type ApiOrderItem = {
  product_id?: string;
  produto_id?: string;
  quantity?: number;
  qtd?: number;
  unit_price_cents?: number;
  preco_unit_centavos?: number;
  name?: string;
  nome?: string;
};

type ApiDelivery = {
  status?: string | null;
  postal_code?: string | null;
  cep?: string | null;
  street?: string | null;
  logradouro?: string | null;
  number?: string | null;
  numero?: string | null;
  complement?: string | null;
  bairro?: string | null;
  district?: string | null;
  city?: string | null;
  cidade?: string | null;
  state?: string | null;
  uf?: string | null;
  reference?: string | null;
  referencia?: string | null;
} | null;

type ApiOrderResponse = {
  id?: string;
  status?: string | { value: string };
  customer_name?: string | null;
  whatsapp_contact_phone?: string | null;
  whatsapp_order_message?: string | null;
  pix_key?: string | null;
  notes?: string | null;
  subtotal_cents?: number;
  subtotal_centavos?: number;
  shipping_cents?: number | null;
  frete_centavos?: number | null;
  frete?: { valor_centavos?: number | null } | null;
  total_cents?: number;
  total_centavos?: number;
  items?: ApiOrderItem[];
  itens?: ApiOrderItem[];
  delivery?: ApiDelivery;
  entrega?: ApiDelivery;
  payment?: {
    metodo?: string | null;
    method?: string | null;
    status?: string | null;
    troco_para?: number | null;
  } | null;
  pagamento?: {
    metodo?: string | null;
    method?: string | null;
    status?: string | null;
    troco_para?: number | null;
  } | null;
  pickup?: boolean | null;
  retirada?: boolean | null;
  endereco?: Endereco | null;
  store?: StoreAddress;
};

const metodoLabel = (m?: string | null) => {
  switch ((m || "").toLowerCase()) {
    case "pix": return "PIX";
    case "dinheiro": return "Dinheiro";
    case "cartao": case "cartão": return "Cartão";
    default: return m ?? "—";
  }
};

const statusPagamentoLabel = (s?: string | null) => {
  switch ((s || "").toUpperCase()) {
    case "PENDENTE": return "Pendente";
    case "PAGO": return "Pago";
    case "FALHOU": return "Falhou";
    default: return s ?? "—";
  }
};

const statusPedidoLabel = (s?: string | null) => {
  const value = (s || "").toLowerCase();
  switch (value) {
    case "received": return "Recebido";
    case "confirmed": return "Confirmado";
    case "preparing": return "Preparando";
    case "ready": return "Pronto";
    case "on_route": return "Saiu para entrega";
    case "delivered": return "Entregue";
    case "completed": return "Concluido";
    case "canceled":
    case "cancelado": return "Cancelado";
    case "pending": return "Pendente";
    default:
      if (!value) return "—";
      return value.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  }
};

function buildWhatsappMessage(
  template: string | null | undefined,
  orderId: string,
  customerName?: string | null,
): string {
  const base = (template || "").trim();
  const fallback = `Ola, gostaria de acompanhar o status do pedido ${orderId}.`;
  const message = base || fallback;
  return message
    .replaceAll("{order_id}", orderId)
    .replaceAll("{order_short_id}", orderId.slice(0, 8))
    .replaceAll("{customer_name}", customerName ?? "");
}

function buildWhatsappLink(phone?: string | null, message?: string | null): string | null {
  if (!phone) return null;
  const digits = phone.replace(/\D/g, "");
  if (!digits) return null;
  const textValue = (message || "").trim();
  const suffix = textValue ? `?text=${encodeURIComponent(textValue)}` : "";
  return `https://wa.me/${digits}${suffix}`;
}

export default function PedidoStatus() {
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const id = typeof params.id === "string" ? params.id : Array.isArray(params.id) ? params.id[0] : "";
  const tenant = searchParams.get("tenant") || "";
  const token = searchParams.get("token") || "";
  const storeFromQuery = (searchParams.get("store") || searchParams.get("store_id") || "").trim();
  const [data, setData] = useState<PedidoDetalhe | null>(null);
  const [loading, setLoading] = useState(true);
  const [pixCopied, setPixCopied] = useState(false);
  const [addressCopied, setAddressCopied] = useState(false);

  useEffect(() => {
    if (!id) return;
    let t: ReturnType<typeof setTimeout>;
    const fetcher = async () => {
      try {
        const qs = new URLSearchParams();
        if (token) qs.set("token", token);
        const path = `/orders/${id}${qs.toString() ? `?${qs.toString()}` : ""}`;
        const r = await api<ApiOrderResponse>(path, {
          headers: tenant ? { "X-Tenant": tenant } : undefined,
        });
        const itens = (r.items || r.itens || []).map((it: ApiOrderItem) => ({
          produto_id: it.product_id ?? it.produto_id ?? "",
          qtd: it.quantity ?? it.qtd ?? 0,
          preco_unit_centavos: it.unit_price_cents ?? it.preco_unit_centavos ?? 0,
          nome: it.name ?? it.nome,
        }));
        const entrega: Entrega =
          r.delivery
            ? {
                status: r.delivery.status ?? null,
                cep: r.delivery.postal_code ?? r.delivery.cep ?? null,
                logradouro: r.delivery.street ?? r.delivery.logradouro ?? null,
                numero: r.delivery.number ?? r.delivery.numero ?? null,
                complemento: r.delivery.complement ?? null,
                bairro: r.delivery.district ?? r.delivery.bairro ?? null,
                cidade: r.delivery.city ?? r.delivery.cidade ?? null,
                uf: r.delivery.state ?? r.delivery.uf ?? null,
                referencia: r.delivery.reference ?? r.delivery.referencia ?? null,
              }
            : r.entrega ?? null;

        const endereco: Endereco | null = r.endereco
          ? {
              cep: r.endereco.cep ?? "",
              logradouro: r.endereco.logradouro ?? "",
              numero: r.endereco.numero ?? "",
              complemento: r.endereco.complemento ?? null,
              bairro: r.endereco.bairro ?? null,
              cidade: r.endereco.cidade ?? "",
              uf: r.endereco.uf ?? "",
              referencia: r.endereco.referencia ?? null,
            }
          : null;
        const store: StoreAddress = r.store
          ? {
              id: r.store.id,
              name: r.store.name ?? null,
              postal_code: r.store.postal_code ?? null,
              street: r.store.street ?? null,
              number: r.store.number ?? null,
              complement: r.store.complement ?? null,
              district: r.store.district ?? null,
              city: r.store.city ?? null,
              state: r.store.state ?? null,
              reference: r.store.reference ?? null,
            }
          : null;

        const payment = r.payment ?? r.pagamento ?? null;
        const normalizedPayment = payment
          ? {
              metodo: payment.metodo ?? payment.method ?? null,
              status: payment.status ?? null,
              troco_para: payment.troco_para ?? null,
            }
          : null;

        setData({
          id: r.id ?? id,
          status: typeof r.status === "string" ? r.status : r.status?.value ?? "",
          customer_name: r.customer_name ?? null,
          whatsapp_contact_phone: r.whatsapp_contact_phone ?? null,
          whatsapp_order_message: r.whatsapp_order_message ?? null,
          pix_key: r.pix_key ?? null,
          notes: r.notes ?? null,
          subtotal_centavos: r.subtotal_cents ?? r.subtotal_centavos ?? 0,
          frete_centavos: r.shipping_cents ?? r.frete_centavos ?? null,
          frete: r.frete ?? null,
          total_centavos: r.total_cents ?? r.total_centavos ?? 0,
          itens,
          pagamento: normalizedPayment,
          entrega,
          retirada: r.pickup ?? r.retirada ?? null,
          endereco,
          store,
        });
        setLoading(false);
      } finally {
        t = setTimeout(fetcher, 30000);
      }
    };
    fetcher();
    return () => clearTimeout(t);
  }, [id, tenant]);

  const freteCents = useMemo(() => {
    if (!data) return 0;
    const f = data.frete?.valor_centavos ?? data.frete_centavos ?? 0;
    return typeof f === "number" ? f : 0;
  }, [data]);

  const isRetirada = useMemo(() => {
    if (!data) return false;
    if (typeof data.retirada === "boolean") return data.retirada;
    const hasEntregaCampos = !!(
      (data.entrega && (
        (data.entrega.logradouro && data.entrega.numero) ||
        data.entrega.cidade || data.entrega.uf || data.entrega.cep
      ))
    );
    const hasEnderecoLegacy = !!(data.endereco);
    return !(hasEntregaCampos || hasEnderecoLegacy);
  }, [data]);

  const entregaEndereco = useMemo((): EnderecoDisplay | null => {
    if (!data) return null;
    if (data.entrega) {
      return {
        cep: data.entrega.cep ?? null,
        logradouro: data.entrega.logradouro ?? null,
        numero: data.entrega.numero ?? null,
        complemento: data.entrega.complemento ?? null,
        bairro: data.entrega.bairro ?? null,
        cidade: data.entrega.cidade ?? null,
        uf: data.entrega.uf ?? null,
        referencia: data.entrega.referencia ?? null,
      };
    }
    if (data.endereco) {
      return {
        cep: data.endereco.cep ?? null,
        logradouro: data.endereco.logradouro ?? null,
        numero: data.endereco.numero ?? null,
        complemento: data.endereco.complemento ?? null,
        bairro: data.endereco.bairro ?? null,
        cidade: data.endereco.cidade ?? null,
        uf: data.endereco.uf ?? null,
        referencia: data.endereco.referencia ?? null,
      };
    }
    return null;
  }, [data]);

  const retiradaEndereco = useMemo((): EnderecoDisplay | null => {
    if (!data?.store) return null;
    return {
      nome: data.store.name ?? null,
      cep: data.store.postal_code ?? null,
      logradouro: data.store.street ?? null,
      numero: data.store.number ?? null,
      complemento: data.store.complement ?? null,
      bairro: data.store.district ?? null,
      cidade: data.store.city ?? null,
      uf: data.store.state ?? null,
      referencia: data.store.reference ?? null,
    };
  }, [data]);

  const formatEnderecoText = (e: EnderecoDisplay | null, includeName = true) => {
    if (!e) return "";
    const logradouro = e.logradouro ?? "";
    const numero = e.numero ?? "";
    const complemento = e.complemento ?? "";
    const bairro = e.bairro ?? "";
    const cidade = e.cidade ?? "";
    const uf = e.uf ?? "";
    const cep = e.cep ?? "";
    const referencia = e.referencia ?? "";

    const l1 = [logradouro, numero].filter(Boolean).join(", ") + (complemento ? `, ${complemento}` : "");
    const l2Main = [bairro].filter(Boolean).join("");
    const l2Tail = [cidade, uf].filter(Boolean).join("/");
    const l2 = [l2Main, l2Tail].filter(Boolean).join(" — ");
    const l3 = (cep ? `CEP: ${cep}` : "") + (referencia ? `${cep ? "  •  " : ""}Referência: ${referencia}` : "");

    const lines = [(includeName ? e.nome : null) ?? "", l1, l2, l3].filter(Boolean);
    return lines.join("\n");
  };

  const whatsappMessage = useMemo(() => {
    if (!data) return "";
    return buildWhatsappMessage(data.whatsapp_order_message, data.id, data.customer_name);
  }, [data]);

  const whatsappLink = useMemo(() => {
    if (!data) return null;
    return buildWhatsappLink(data.whatsapp_contact_phone, whatsappMessage);
  }, [data, whatsappMessage]);

  const vitrineStoreRef = storeFromQuery || data?.store?.id || "";
  const vitrineLink = tenant
    ? vitrineStoreRef
      ? `/vitrine/${tenant}/${encodeURIComponent(vitrineStoreRef)}`
      : `/vitrine/${tenant}`
    : "/";

  const renderEntrega = (e: EnderecoDisplay | null) => {
    if (!e) return null;
    const logradouro = e.logradouro ?? "";
    const numero = e.numero ?? "";
    const complemento = e.complemento ?? "";
    const bairro = e.bairro ?? "";
    const cidade = e.cidade ?? "";
    const uf = e.uf ?? "";
    const cep = e.cep ?? "";
    const referencia = e.referencia ?? "";

    const l1 = [logradouro, numero].filter(Boolean).join(", ") + (complemento ? `, ${complemento}` : "");
    const l2Main = [bairro].filter(Boolean).join("");
    const l2Tail = [cidade, uf].filter(Boolean).join("/");
    const l2 = [l2Main, l2Tail].filter(Boolean).join(" — ");
    const l3 = (cep ? `CEP: ${cep}` : "") + (referencia ? `${cep ? "  •  " : ""}Referência: ${referencia}` : "");

    return (
      <div className="text-sm text-neutral-600 space-y-0.5">
        {e.nome && <div className="font-semibold text-neutral-800">{e.nome}</div>}
        {l1 && <div>{l1}</div>}
        {(l2Main || l2Tail) && <div>{l2}</div>}
        {l3 && <div>{l3}</div>}
      </div>
    );
  };

  const pixKey = data?.pix_key?.trim() || "";
  const handleCopyPix = async () => {
    if (!pixKey) return;
    try {
      await navigator.clipboard?.writeText(pixKey);
      setPixCopied(true);
      setTimeout(() => setPixCopied(false), 2000);
    } catch {
      /* ignore */
    }
  };

  const enderecoParaExibir = isRetirada ? retiradaEndereco : entregaEndereco;
  const enderecoTexto = useMemo(
    () => formatEnderecoText(enderecoParaExibir, false),
    [enderecoParaExibir],
  );
  const mapsUrl = useMemo(() => {
    if (!enderecoTexto) return "";
    const query = enderecoTexto.replace(/\n/g, ", ");
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`;
  }, [enderecoTexto]);
  const handleCopyEndereco = async () => {
    if (!enderecoTexto) return;
    try {
      await navigator.clipboard?.writeText(enderecoTexto);
      setAddressCopied(true);
      setTimeout(() => setAddressCopied(false), 2000);
    } catch {
      /* ignore */
    }
  };

  const statusBadge = (status: string) => {
    const s = status.toLowerCase();
    if (["delivered", "completed"].includes(s)) return "bg-emerald-100 text-emerald-800 border-emerald-200";
    if (["canceled", "cancelado"].includes(s)) return "bg-red-100 text-red-700 border-red-200";
    if (["preparing", "ready", "on_route"].includes(s)) return "bg-amber-100 text-amber-800 border-amber-200";
    return "bg-neutral-100 text-neutral-800 border-neutral-200";
  };

  const skeleton = (
    <div className="animate-pulse space-y-4">
      <div className="h-10 bg-white/60 rounded-xl"></div>
      <div className="h-32 bg-white/60 rounded-2xl"></div>
      <div className="h-48 bg-white/60 rounded-2xl"></div>
    </div>
  );

  if (!data) {
    return (
      <main className="min-h-screen bg-gradient-to-b from-white to-[#f5f0ff]">
        <div className="max-w-4xl mx-auto px-4 py-8">{loading ? skeleton : null}</div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gradient-to-b from-white to-[#f5f0ff]">
      <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
        <header className="flex items-center justify-between">
          <div>
            <p className="text-sm text-neutral-500">Pedido</p>
            <h1 className="text-3xl font-semibold text-[#211a1d]">#{id.slice(0, 8)}</h1>
            <div className={`mt-2 inline-flex items-center gap-2 px-3 py-1 rounded-full border text-sm ${statusBadge(data.status)}`}>
              <span className="h-2 w-2 rounded-full bg-current opacity-70"></span>
              <span>{statusPedidoLabel(data.status)}</span>
            </div>
            <div className="mt-3">
              <a
                href={vitrineLink}
                className="inline-flex items-center gap-2 rounded-full border border-neutral-200 bg-white px-3 py-1 text-xs font-semibold text-neutral-700 hover:bg-neutral-100"
              >
                <svg
                  viewBox="0 0 24 24"
                  className="h-4 w-4"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M15 18l-6-6 6-6" />
                </svg>
                Voltar a vitrine
              </a>
            </div>
          </div>
          <div className="text-right text-sm text-neutral-600">
            <div>Subtotal: <b className="text-[#211a1d]">{fmtBRL(data.subtotal_centavos / 100)}</b></div>
            <div>Frete: <b className="text-[#211a1d]">{fmtBRL((freteCents || 0) / 100)}</b></div>
            <div className="text-lg font-semibold text-[#211a1d]">Total: {fmtBRL(data.total_centavos / 100)}</div>
          </div>
        </header>

        {whatsappLink && (
          <section className="rounded-3xl bg-white shadow-sm border border-neutral-200/60 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-[0.16em] text-neutral-500">WhatsApp</p>
                <h2 className="text-lg font-semibold text-[#211a1d]">Receber atualizacoes</h2>
                <p className="text-sm text-neutral-600">
                  Quero acompanhar o meu pedido no WhatsApp.
                </p>
              </div>
              <div className="w-full sm:w-auto flex justify-center">
                <a
                  href={whatsappLink}
                  target="_blank"
                  rel="noreferrer"
                  className="px-4 py-2 rounded-full bg-[#25D366] text-white text-sm font-semibold hover:brightness-105"
                >
                  Acompanhar pedido
                </a>
              </div>
            </div>
          </section>
        )}

        <section className="rounded-3xl bg-white shadow-sm border border-neutral-200/60 p-4 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.16em] text-neutral-500">Itens</p>
              <h2 className="text-lg font-semibold text-[#211a1d]">Resumo</h2>
            </div>
            <span className="text-xs text-neutral-500">{data.itens.length} item(s)</span>
          </div>
          <div className="divide-y divide-neutral-100">
            {data.itens.map((i) => {
              const nome = i.nome || `Produto ${i.produto_id}`;
              const totalItem = (i.preco_unit_centavos || 0) * (i.qtd || 0);
              return (
                <div key={`${i.produto_id}`} className="py-3 flex items-center justify-between">
                  <div>
                    <div className="font-semibold text-[#211a1d]">{nome}</div>
                    <div className="text-sm text-neutral-600">
                      {i.qtd}x <span className="ml-1">{fmtBRL((i.preco_unit_centavos || 0) / 100)}</span>
                    </div>
                  </div>
                  <div className="text-sm font-semibold text-[#211a1d]">{fmtBRL(totalItem / 100)}</div>
                </div>
              );
            })}
          </div>
        </section>

        <section className="grid md:grid-cols-2 gap-3">
          <div className="rounded-3xl bg-white shadow-sm border border-neutral-200/60 p-4 space-y-2">
            <p className="text-xs uppercase tracking-[0.16em] text-neutral-500">Pagamento</p>
            <div className="text-sm text-neutral-700 text-center">
              {metodoLabel(data.pagamento?.metodo)} · {statusPagamentoLabel(data.pagamento?.status)}
            </div>
            {data.pagamento?.metodo?.toLowerCase() === "pix" && pixKey && (
              <div className="mt-2 space-y-2 text-sm text-center">
                <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-emerald-900">
                  <div className="text-xs uppercase tracking-[0.16em] text-emerald-700">Chave PIX</div>
                  <div className="mt-1 break-all font-semibold">{pixKey}</div>
                </div>
                <button
                  type="button"
                  onClick={handleCopyPix}
                  className={`mx-auto inline-flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold transition ${
                    pixCopied
                      ? "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200 opacity-80"
                      : "bg-emerald-600 text-white hover:brightness-105"
                  }`}
                >
                  <span
                    className={`inline-flex h-4 w-4 items-center justify-center rounded-full border transition ${
                      pixCopied
                        ? "border-emerald-300 bg-emerald-200 text-emerald-800"
                        : "border-white/70 text-white"
                    }`}
                  >
                    <svg
                      viewBox="0 0 24 24"
                      className={`h-3 w-3 transition ${
                        pixCopied ? "opacity-100" : "opacity-70"
                      }`}
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      aria-hidden="true"
                    >
                      {pixCopied ? <path d="M20 6L9 17l-5-5" /> : <path d="M16 4H8a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2z" />}
                    </svg>
                  </span>
                  {pixCopied ? "Chave copiada" : "Copiar chave PIX"}
                </button>
              </div>
            )}
          </div>
          <div className="rounded-3xl bg-white shadow-sm border border-neutral-200/60 p-4 space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs uppercase tracking-[0.16em] text-neutral-500">
                {isRetirada ? "Retirada" : "Entrega"}
              </p>
              {enderecoTexto && (
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={handleCopyEndereco}
                    className={`inline-flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold transition ${
                      addressCopied
                        ? "bg-neutral-100 text-neutral-700 ring-1 ring-neutral-200 opacity-80"
                        : "bg-neutral-900 text-white hover:brightness-105"
                    }`}
                  >
                    <span
                      className={`inline-flex h-4 w-4 items-center justify-center rounded-full border transition ${
                        addressCopied
                          ? "border-neutral-300 bg-neutral-200 text-neutral-700"
                          : "border-white/70 text-white"
                      }`}
                    >
                      <svg
                        viewBox="0 0 24 24"
                        className={`h-3 w-3 transition ${
                          addressCopied ? "opacity-100" : "opacity-70"
                        }`}
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        aria-hidden="true"
                      >
                        {addressCopied ? (
                          <path d="M20 6L9 17l-5-5" />
                        ) : (
                          <path d="M16 4H8a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2z" />
                        )}
                      </svg>
                    </span>
                    {addressCopied ? "Endereco copiado" : "Copiar endereco"}
                  </button>
                  {mapsUrl && (
                    <a
                      href={mapsUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold bg-neutral-100 text-neutral-700 border border-neutral-200 hover:bg-neutral-200"
                    >
                      Abrir no Maps
                    </a>
                  )}
                </div>
              )}
            </div>
            {isRetirada && retiradaEndereco?.nome && (
              <div className="text-sm font-semibold text-neutral-800">
                Retirada na {retiradaEndereco.nome}
              </div>
            )}
            {enderecoParaExibir ? (
              renderEntrega(enderecoParaExibir)
            ) : (
              <div className="text-sm text-neutral-700">Endereco nao informado.</div>
            )}
          </div>
        </section>

        {data.notes && data.notes.trim() && (
          <section className="rounded-3xl bg-white shadow-sm border border-neutral-200/60 p-4 space-y-2">
            <p className="text-xs uppercase tracking-[0.16em] text-neutral-500">Observacoes</p>
            <p className="text-sm text-neutral-700 whitespace-pre-wrap">{data.notes}</p>
          </section>
        )}

      </div>
    </main>
  );
}
