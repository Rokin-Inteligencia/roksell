"use client";

import { useEffect, useState } from "react";
import { useSuperAdminGuard } from "@/lib/use-super-admin-guard";
import { adminFetch } from "@/lib/admin-api";
import Link from "next/link";

const MODULE_LABELS: Record<string, string> = {
  inventory: "Estoque",
  stores: "Cadastro de lojas",
  campaigns: "Campanhas",
  insights: "Insights",
  messages: "Mensagens",
};

type PlanSummary = {
  id: string;
  name: string;
  description?: string | null;
  is_active: boolean;
  modules: string[];
};

type PlanForm = {
  name: string;
  description: string;
  is_active: boolean;
  modules: Record<string, boolean>;
};

const DEFAULT_FORM: PlanForm = {
  name: "",
  description: "",
  is_active: true,
  modules: Object.keys(MODULE_LABELS).reduce((acc, key) => {
    acc[key] = false;
    return acc;
  }, {} as Record<string, boolean>),
};

export default function AdminPlansPage() {
  const ready = useSuperAdminGuard();
  const [plans, setPlans] = useState<PlanSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<PlanSummary | null>(null);
  const [form, setForm] = useState<PlanForm>(DEFAULT_FORM);
  const [modalOpen, setModalOpen] = useState(false);

  useEffect(() => {
    if (ready) loadPlans();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);

  async function loadPlans() {
    setLoading(true);
    setError(null);
    try {
      const data = await adminFetch<PlanSummary[]>("/admin/central/plans");
      setPlans(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar planos");
    } finally {
      setLoading(false);
    }
  }

  function openCreate() {
    setSelectedPlan(null);
    setForm(DEFAULT_FORM);
    setModalOpen(true);
  }

  function openEdit(plan: PlanSummary) {
    const modulesState = Object.keys(MODULE_LABELS).reduce((acc, key) => {
      acc[key] = plan.modules?.includes(key) ?? false;
      return acc;
    }, {} as Record<string, boolean>);
    setSelectedPlan(plan);
    setForm({
      name: plan.name ?? "",
      description: plan.description ?? "",
      is_active: plan.is_active ?? true,
      modules: modulesState,
    });
    setModalOpen(true);
  }

  function closeModal() {
    setModalOpen(false);
    setSelectedPlan(null);
    setForm(DEFAULT_FORM);
  }

  async function savePlan() {
    const name = form.name.trim();
    if (!name) {
      setError("Nome do plano e obrigatorio.");
      return;
    }
    const moduleKeys = Object.entries(form.modules)
      .filter(([, enabled]) => enabled)
      .map(([key]) => key);

    const payload = {
      name,
      description: form.description.trim() || null,
      is_active: form.is_active,
      module_keys: moduleKeys,
    };

    try {
      setLoading(true);
      setError(null);
      if (selectedPlan) {
        await adminFetch(`/admin/central/plans/${selectedPlan.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
      } else {
        await adminFetch("/admin/central/plans", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }
      setStatusMessage("Plano salvo com sucesso.");
      await loadPlans();
      closeModal();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar plano");
    } finally {
      setLoading(false);
    }
  }

  if (!ready) return null;

  return (
    <main className="min-h-screen bg-[#f5f3ff] text-slate-900">
      <div className="max-w-5xl w-full mx-auto px-6 py-10 space-y-8">
        <header className="space-y-2">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.26em] text-slate-500">Admin central</p>
              <h1 className="text-3xl font-semibold">Planos</h1>
              <p className="text-sm text-slate-600">Defina os modulos incluidos em cada plano.</p>
            </div>
            <Link
              href="/admin"
              className="px-4 py-2 rounded-lg border border-slate-200 bg-white text-sm font-semibold hover:bg-slate-100"
            >
              Voltar para empresas
            </Link>
          </div>
        </header>

        {statusMessage && <p className="text-sm text-emerald-700">{statusMessage}</p>}
        {error && <p className="text-sm text-red-600">{error}</p>}

        <section className="rounded-3xl bg-white border border-slate-200 shadow-sm shadow-slate-200/60 p-6 space-y-4">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-xl font-semibold">Planos cadastrados</h2>
            <button
              onClick={openCreate}
              className="px-4 py-2 rounded-lg bg-[#6320ee] text-white font-semibold"
            >
              Novo plano
            </button>
          </div>

          {plans.length === 0 ? (
            <p className="text-sm text-slate-600">Nenhum plano cadastrado.</p>
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {plans.map((plan) => (
                <div key={plan.id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4 space-y-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Plano</p>
                      <p className="text-lg font-semibold">{plan.name}</p>
                      {plan.description && <p className="text-xs text-slate-600">{plan.description}</p>}
                    </div>
                    <span
                      className={`text-[10px] px-2 py-1 rounded-full border ${
                        plan.is_active
                          ? "bg-emerald-200 border-emerald-300 text-emerald-900"
                          : "bg-red-200 border-red-300 text-red-900"
                      }`}
                    >
                      {plan.is_active ? "Ativo" : "Inativo"}
                    </span>
                  </div>
                  <div className="text-xs text-slate-600">
                    Modulos:{" "}
                    {plan.modules?.length
                      ? plan.modules.map((key) => MODULE_LABELS[key] || key).join(", ")
                      : "Nenhum modulo"}
                  </div>
                  <div className="flex items-center justify-end">
                    <button
                      onClick={() => openEdit(plan)}
                      className="px-3 py-1 rounded-lg bg-[#6320ee] text-white text-xs"
                    >
                      Editar
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/90 backdrop-blur-sm px-4">
          <div className="w-full max-w-2xl rounded-3xl bg-white border border-slate-200 shadow-2xl shadow-slate-200/80 p-6 space-y-5 text-slate-900">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Plano</p>
                <h2 className="text-2xl font-semibold">{selectedPlan ? "Editar plano" : "Novo plano"}</h2>
              </div>
              <button
                onClick={closeModal}
                className="text-sm px-3 py-1 rounded-full bg-slate-100 border border-slate-200 hover:bg-slate-200"
              >
                Fechar
              </button>
            </div>

            <div className="grid md:grid-cols-2 gap-4 text-sm">
              <label className="space-y-1">
                <span>Nome</span>
                <input
                  className="input w-full"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
              </label>
              <label className="space-y-1">
                <span>Status</span>
                <select
                  className="input w-full"
                  value={form.is_active ? "true" : "false"}
                  onChange={(e) => setForm({ ...form, is_active: e.target.value === "true" })}
                >
                  <option value="true">Ativo</option>
                  <option value="false">Inativo</option>
                </select>
              </label>
              <label className="space-y-1 md:col-span-2">
                <span>Descricao</span>
                <input
                  className="input w-full"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                />
              </label>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 space-y-3">
              <div>
                <h3 className="text-lg font-semibold">Modulos do plano</h3>
                <p className="text-xs text-slate-500">Selecione quais modulos estarao disponiveis.</p>
              </div>
              <div className="grid md:grid-cols-2 gap-3 text-sm">
                {Object.entries(MODULE_LABELS).map(([key, label]) => (
                  <label
                    key={key}
                    className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3"
                  >
                    <span>{label}</span>
                    <input
                      type="checkbox"
                      className="accent-[#6320ee]"
                      checked={form.modules[key]}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          modules: { ...form.modules, [key]: e.target.checked },
                        })
                      }
                    />
                  </label>
                ))}
              </div>
            </div>

            <div className="flex items-center justify-end gap-3">
              <button
                onClick={closeModal}
                className="px-4 py-2 rounded-lg bg-slate-100 text-slate-900 text-sm font-semibold"
              >
                Cancelar
              </button>
              <button
                onClick={savePlan}
                disabled={loading}
                className="px-4 py-2 rounded-lg bg-[#6320ee] text-white text-sm font-semibold disabled:opacity-60"
              >
                {loading ? "Salvando..." : "Salvar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
