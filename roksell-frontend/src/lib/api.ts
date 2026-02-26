// src/lib/api.ts
function isServer() {
  return typeof window === 'undefined';
}

// Base do backend (SSR usa API_URL; browser usa NEXT_PUBLIC_API_URL)
function getBase() {
  const base =
    (isServer() ? process.env.API_URL : process.env.NEXT_PUBLIC_API_URL)
    ?? 'http://127.0.0.1:8000';
  return base.endsWith('/') ? base : base + '/';
}

/** Chamada simples à API. `path` pode ser "/checkout", "checkout", etc. */
export async function api<T = unknown>(path: string, init?: RequestInit): Promise<T> {
  // Garante que a URL final fique correta
  const url = new URL(path.replace(/^\//, ''), getBase()).toString();

  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`API ${res.status} ${res.statusText} - ${url}\n${text}`);
  }

  const ct = res.headers.get('content-type') || '';
  if (ct.includes('application/json')) return res.json() as Promise<T>;
  return (await res.text()) as unknown as T;
}

/** Formata em BRL assumindo valor em **reais** (ex: 9.9 => R$ 9,90) */
export function fmtBRL(value: number): string {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value);
}
