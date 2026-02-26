"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { clearAdminToken, getTenantSlug } from "@/lib/portal-auth";

const SUPER_ADMIN_SLUG = process.env.NEXT_PUBLIC_SUPER_ADMIN_SLUG || "rokin";

export default function AdminLogin() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionActive, setSessionActive] = useState(false);

  useEffect(() => {
    async function checkSession() {
      try {
        const res = await fetch("/api/auth/me", { credentials: "include" });
        if (!res.ok) return;
        const tenantSlug = getTenantSlug();
        if (tenantSlug !== SUPER_ADMIN_SLUG) return;
        setSessionActive(true);
        router.replace("/admin");
      } catch {
        /* ignore */
      }
    }
    checkSession();
  }, [router]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
        credentials: "include",
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Falha no login");
      const tenantSlug = data?.tenant_slug;
      if (tenantSlug && tenantSlug !== SUPER_ADMIN_SLUG) {
        clearAdminToken();
        throw new Error("Usuario nao autorizado para admin central.");
      }
      if (data?.access_token) {
        setSessionActive(true);
        router.push("/admin");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro desconhecido");
      clearAdminToken();
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-[#f6f4ff] via-[#f3f1ff] to-[#eef2ff] text-slate-900">
      <div className="max-w-5xl w-full mx-auto px-6 py-12 space-y-10">
        <div className="flex justify-center">
          <Link href="/" className="text-3xl font-semibold tracking-wide text-[#6320ee]">
            Roksell
          </Link>
        </div>
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Rokin Admin</p>
            <h1 className="text-3xl font-semibold">Painel Central</h1>
            <p className="text-sm text-slate-600">Acesso exclusivo para o time Rokin.</p>
          </div>
        </header>

        <section className="rounded-3xl bg-white border border-slate-200 shadow-xl shadow-slate-200/60 p-6 space-y-5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-slate-900">Login admin</h2>
            </div>
            {sessionActive && (
              <span className="px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs border border-emerald-200">
                Sessao ativa
              </span>
            )}
          </div>

          <form className="space-y-4" onSubmit={onSubmit}>
            <label className="block space-y-1 text-sm">
              <span className="text-slate-700">Email</span>
              <input
                type="email"
                className="input w-full bg-white border border-slate-200 text-slate-900 placeholder:text-slate-400"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-slate-700">Senha</span>
              <input
                type="password"
                className="input w-full bg-white border border-slate-200 text-slate-900 placeholder:text-slate-400"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </label>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <div className="flex items-center gap-3">
              <button
                type="submit"
                disabled={loading}
                className="px-4 py-2 rounded-lg bg-[#6320ee] text-white font-semibold active:scale-95 disabled:opacity-50"
              >
                {loading ? "Entrando..." : "Entrar"}
              </button>
              {sessionActive && (
                <button
                  type="button"
                  onClick={() => {
                    clearAdminToken();
                    setSessionActive(false);
                  }}
                  className="px-3 py-2 rounded-lg bg-slate-100 border border-slate-200 text-sm text-slate-700 hover:bg-slate-200"
                >
                  Sair
                </button>
              )}
            </div>
          </form>
        </section>
      </div>
    </main>
  );
}
