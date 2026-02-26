import { redirect } from "next/navigation";

type PedidoRedirectProps = {
  params: Promise<{ id: string }>;
  searchParams?: Promise<{
    tenant?: string;
    token?: string;
    store?: string;
    store_id?: string;
  }>;
};

export default async function PedidoRedirect({
  params,
  searchParams,
}: PedidoRedirectProps) {
  // Redireciona /pedidos/:id para /pedido/:id para manter compatibilidade de links.
  const resolvedParams = await params;
  const resolvedSearchParams = searchParams ? await searchParams : undefined;
  const tenant = resolvedSearchParams?.tenant;
  const token = resolvedSearchParams?.token;
  const store = resolvedSearchParams?.store;
  const storeId = resolvedSearchParams?.store_id;
  const qs = new URLSearchParams();
  if (tenant) qs.set("tenant", tenant);
  if (token) qs.set("token", token);
  if (store) qs.set("store", store);
  if (storeId) qs.set("store_id", storeId);
  const suffix = qs.toString();
  redirect(`/pedido/${resolvedParams.id}${suffix ? `?${suffix}` : ""}`);
}
