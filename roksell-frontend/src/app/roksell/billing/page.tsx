"use client";
import { useEffect, useState } from "react";
import { adminFetch } from "@/lib/admin-api";
import { useAdminGuard } from "@/lib/use-admin-guard";
import { ProfileBadge } from "@/components/admin/ProfileBadge";

type Plan = {
  id: string;
  name: string;
  price_cents: number;
  currency: string;
  interval: string;
  description?: string | null;
  modules: string[];
};

type Subscription = {
  id: string;
  plan_id: string;
  status: string;
  started_at: string;
  current_period_end?: string | null;
  modules: string[];
};

export default function BillingAdmin() {
  const ready = useAdminGuard();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState<string>("");

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [p, sub] = await Promise.all([
        adminFetch<Plan[]>("/admin/billing/plans"),
        adminFetch<Subscription>("/admin/billing/subscription"),
      ]);
      setPlans(p);
      setSubscription(sub);
      setSelectedPlan(sub.plan_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao carregar assinatura");
    } finally {
      setLoading(false);
    }
  }

  async function changePlan() {
    if (!selectedPlan) return;
    try {
      setLoading(true);
      await adminFetch("/admin/billing/subscription", {
        method: "POST",
        body: JSON.stringify({ plan_id: selectedPlan }),
      });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao trocar plano");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (ready) load();
  }, [ready]);

  if (!ready) return null;

  return (
    <main className="min-h-screen text-slate-900 px-6 py-8 bg-[#f5f3ff]">
      <div className="max-w-5xl w-full mx-auto px-3 sm:px-4 space-y-6">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Admin · Billing</p>
            <h1 className="text-3xl font-semibold">Assinatura e módulos</h1>
            <p className="text-sm text-slate-600">Controle de planos focado em desktop.</p>
          </div>
          <ProfileBadge />
        </header>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <section className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-2xl bg-white text-slate-900 shadow p-3 sm:p-5 space-y-3 border border-slate-200">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold">Plano atual</h2>
              <span className="text-xs px-3 py-1 rounded-full bg-slate-100 text-slate-700">
                {subscription?.status ?? "N/A"}
              </span>
            </div>
            {subscription ? (
              <div className="text-sm space-y-1">
                <div>Plano ID: {subscription.plan_id}</div>
                <div>Módulos: {subscription.modules.join(", ") || "Nenhum"}</div>
                <div>Início: {new Date(subscription.started_at).toLocaleString("pt-BR")}</div>
              </div>
            ) : (
              <p className="text-sm text-slate-600">Nenhuma assinatura encontrada.</p>
            )}
          </div>

          <div className="rounded-2xl bg-white text-slate-900 shadow p-3 sm:p-5 space-y-3 border border-slate-200">
            <h2 className="font-semibold">Aplicar plano</h2>
            <div className="space-y-2 max-h-72 overflow-auto pr-1">
              {plans.map((plan) => (
                <label key={plan.id} className="block rounded-xl border border-slate-100 p-3 space-y-1">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <input
                        type="radio"
                        name="plan"
                        className="accent-[#6320ee]"
                        checked={selectedPlan === plan.id}
                        onChange={() => setSelectedPlan(plan.id)}
                      />
                      <span className="font-semibold">{plan.name}</span>
                    </div>
                    <div className="text-sm text-slate-700">
                      {(plan.price_cents / 100).toLocaleString("pt-BR", {
                        style: "currency",
                        currency: plan.currency || "BRL",
                      })}{" "}
                      / {plan.interval}
                    </div>
                  </div>
                  <div className="text-xs text-slate-500">{plan.description}</div>
                  <div className="text-xs text-slate-500">Módulos: {plan.modules.join(", ") || "-"}</div>
                </label>
              ))}
            </div>
            <button
              onClick={changePlan}
              disabled={!selectedPlan || loading}
              className="px-3 py-2 rounded-lg bg-[#6320ee] text-white text-sm font-semibold active:scale-95 disabled:opacity-60"
            >
              Aplicar plano
            </button>
          </div>
        </section>
      </div>
    </main>
  );
}

