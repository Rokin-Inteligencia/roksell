"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { adminFetch } from "@/lib/admin-api";
import { viaCEP } from "@/lib/cep";
import { useAdminGuard } from "@/lib/use-admin-guard";
import { OperatingHoursDay } from "@/types";

type WizardStep = 1 | 2 | 3;

type OnboardingState = {
  needs_onboarding: boolean;
  store_id?: string | null;
  store_name?: string;
  person_type?: string;
  document?: string;
  contact_email?: string;
  contact_phone?: string;
  address?: {
    postal_code?: string;
    street?: string;
    number?: string;
    district?: string;
    city?: string;
    state?: string;
    complement?: string;
    reference?: string;
  };
  operating_hours?: OperatingHoursDay[];
};

type WizardForm = {
  store_name: string;
  person_type: "individual" | "company";
  document: string;
  contact_email: string;
  contact_phone: string;
  postal_code: string;
  street: string;
  number: string;
  district: string;
  city: string;
  state: string;
  complement: string;
  reference: string;
  operating_hours: OperatingHoursDay[];
};

const OPERATING_DAYS: Array<{ day: number; label: string }> = [
  { day: 0, label: "Segunda" },
  { day: 1, label: "Terca" },
  { day: 2, label: "Quarta" },
  { day: 3, label: "Quinta" },
  { day: 4, label: "Sexta" },
  { day: 5, label: "Sabado" },
  { day: 6, label: "Domingo" },
];

const DEFAULT_OPERATING_HOURS: OperatingHoursDay[] = OPERATING_DAYS.map((item) => ({
  day: item.day,
  enabled: item.day < 5,
  open: "08:00",
  close: "18:00",
}));

const FIELD_LABELS: Record<string, string> = {
  store_name: "Nome da loja",
  document: "CPF/CNPJ",
  contact_email: "Email",
  contact_phone: "Telefone",
  postal_code: "CEP",
  street: "Rua",
  number: "Numero",
  complement: "Complemento",
  district: "Bairro",
  city: "Cidade",
  state: "UF",
  reference: "Referencia",
  operating_hours: "Horario de funcionamento",
};

function onlyDigits(value: string): string {
  return value.replace(/\D+/g, "");
}

function formatCEP(value: string): string {
  const digits = onlyDigits(value).slice(0, 8);
  if (digits.length <= 5) return digits;
  return `${digits.slice(0, 5)}-${digits.slice(5)}`;
}

function formatPhone(value: string): string {
  const digits = onlyDigits(value).slice(0, 11);
  if (digits.length <= 2) return digits;
  if (digits.length <= 6) return `(${digits.slice(0, 2)}) ${digits.slice(2)}`;
  if (digits.length <= 10) return `(${digits.slice(0, 2)}) ${digits.slice(2, 6)}-${digits.slice(6)}`;
  return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`;
}

function formatDocument(personType: "individual" | "company", value: string): string {
  const max = personType === "individual" ? 11 : 14;
  const digits = onlyDigits(value).slice(0, max);
  if (personType === "individual") {
    if (digits.length <= 3) return digits;
    if (digits.length <= 6) return `${digits.slice(0, 3)}.${digits.slice(3)}`;
    if (digits.length <= 9) return `${digits.slice(0, 3)}.${digits.slice(3, 6)}.${digits.slice(6)}`;
    return `${digits.slice(0, 3)}.${digits.slice(3, 6)}.${digits.slice(6, 9)}-${digits.slice(9)}`;
  }
  if (digits.length <= 2) return digits;
  if (digits.length <= 5) return `${digits.slice(0, 2)}.${digits.slice(2)}`;
  if (digits.length <= 8) return `${digits.slice(0, 2)}.${digits.slice(2, 5)}.${digits.slice(5)}`;
  if (digits.length <= 12) return `${digits.slice(0, 2)}.${digits.slice(2, 5)}.${digits.slice(5, 8)}/${digits.slice(8)}`;
  return `${digits.slice(0, 2)}.${digits.slice(2, 5)}.${digits.slice(5, 8)}/${digits.slice(8, 12)}-${digits.slice(12)}`;
}

function normalizeHours(input?: OperatingHoursDay[] | null): OperatingHoursDay[] {
  if (!input || input.length === 0) return DEFAULT_OPERATING_HOURS.map((item) => ({ ...item }));
  const byDay = new Map(input.map((item) => [item.day, item]));
  return OPERATING_DAYS.map((item) => ({
    day: item.day,
    enabled: byDay.get(item.day)?.enabled ?? false,
    open: byDay.get(item.day)?.open ?? "08:00",
    close: byDay.get(item.day)?.close ?? "18:00",
  }));
}

function initialFormFromState(data: OnboardingState): WizardForm {
  const personType = data.person_type === "individual" ? "individual" : "company";
  return {
    store_name: (data.store_name || "").trim(),
    person_type: personType,
    document: formatDocument(personType, data.document || ""),
    contact_email: (data.contact_email || "").trim(),
    contact_phone: formatPhone(data.contact_phone || ""),
    postal_code: formatCEP(data.address?.postal_code || ""),
    street: (data.address?.street || "").trim(),
    number: (data.address?.number || "").trim(),
    district: (data.address?.district || "").trim(),
    city: (data.address?.city || "").trim(),
    state: (data.address?.state || "").trim().toUpperCase(),
    complement: (data.address?.complement || "").trim(),
    reference: (data.address?.reference || "").trim(),
    operating_hours: normalizeHours(data.operating_hours),
  };
}

function RequiredLabel({ children }: { children: string }) {
  return (
    <span className="text-sm font-medium text-slate-800">
      {children} <span className="text-red-600">*</span>
    </span>
  );
}

export default function FirstAccessPage() {
  const ready = useAdminGuard({ skipOnboardingCheck: true });
  const router = useRouter();
  const [step, setStep] = useState<WizardStep>(1);
  const [storeId, setStoreId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [validationNotice, setValidationNotice] = useState<{ title: string; items: string[] } | null>(null);
  const [form, setForm] = useState<WizardForm>(initialFormFromState({ needs_onboarding: true }));

  useEffect(() => {
    if (!ready) return;
    let active = true;
    async function loadState() {
      try {
        setLoading(true);
        setError(null);
        const data = await adminFetch<OnboardingState>("/admin/onboarding/state");
        if (!active) return;
        if (!data.needs_onboarding) {
          router.replace("/portal");
          return;
        }
        setStoreId(data.store_id ?? null);
        setForm(initialFormFromState(data));
      } catch (e) {
        if (!active) return;
        setError(e instanceof Error ? e.message : "Falha ao carregar onboarding");
      } finally {
        if (active) setLoading(false);
      }
    }
    loadState();
    return () => {
      active = false;
    };
  }, [ready, router]);

  const progress = useMemo(
    () => [
      { id: 1 as const, title: "Dados da loja" },
      { id: 2 as const, title: "Endereco" },
      { id: 3 as const, title: "Funcionamento" },
    ],
    []
  );

  function inputClass(field: string): string {
    return `input w-full ${
      fieldErrors[field] ? "border-red-400 ring-1 ring-red-200 focus:border-red-500 focus:ring-red-200" : ""
    }`;
  }

  function setHour(day: number, patch: Partial<OperatingHoursDay>) {
    setForm((prev) => ({
      ...prev,
      operating_hours: prev.operating_hours.map((item) => (item.day === day ? { ...item, ...patch } : item)),
    }));
  }

  async function onCEPBlur() {
    const cepDigits = onlyDigits(form.postal_code);
    if (cepDigits.length !== 8) return;
    const result = await viaCEP(cepDigits);
    if (!result) return;
    setForm((prev) => ({
      ...prev,
      street: result.logradouro || prev.street,
      district: result.bairro || prev.district,
      city: result.cidade || prev.city,
      state: (result.uf || prev.state).toUpperCase(),
    }));
  }

  function validateStep(target: WizardStep): boolean {
    const nextErrors: Record<string, string> = {};

    if (target === 1) {
      const documentDigits = onlyDigits(form.document);
      if (!form.store_name.trim()) nextErrors.store_name = "Informe o nome da loja.";
      if (form.person_type === "individual" && documentDigits.length !== 11) {
        nextErrors.document = "CPF deve ter 11 digitos.";
      }
      if (form.person_type === "company" && documentDigits.length !== 14) {
        nextErrors.document = "CNPJ deve ter 14 digitos.";
      }
      if (!/\S+@\S+\.\S+/.test(form.contact_email.trim())) nextErrors.contact_email = "Email invalido.";
      if (onlyDigits(form.contact_phone).length < 10) nextErrors.contact_phone = "Telefone invalido.";
    }

    if (target === 2) {
      if (onlyDigits(form.postal_code).length !== 8) nextErrors.postal_code = "CEP invalido.";
      if (!form.street.trim()) nextErrors.street = "Informe a rua.";
      if (!form.number.trim()) nextErrors.number = "Informe o numero.";
      if (!form.district.trim()) nextErrors.district = "Informe o bairro.";
      if (!form.city.trim()) nextErrors.city = "Informe a cidade.";
      if (form.state.trim().length !== 2) nextErrors.state = "UF deve ter 2 caracteres.";
    }

    if (target === 3) {
      const enabled = form.operating_hours.filter((item) => item.enabled);
      if (enabled.length === 0) {
        nextErrors.operating_hours = "Selecione ao menos um dia com horario.";
      } else {
        const hasInvalidTime = enabled.some((item) => !item.open || !item.close || item.open >= item.close);
        if (hasInvalidTime) nextErrors.operating_hours = "Preencha corretamente os horarios de cada dia marcado.";
      }
    }

    setFieldErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      const items = Object.entries(nextErrors).map(
        ([field, message]) => `${FIELD_LABELS[field] ?? field}: ${message}`
      );
      setValidationNotice({
        title: "Revise os campos obrigatorios para continuar.",
        items,
      });
      return false;
    }
    setValidationNotice(null);
    return true;
  }

  async function submit() {
    if (!validateStep(3)) return;
    setSaving(true);
    setError(null);
    try {
      await adminFetch("/admin/onboarding/complete", {
        method: "POST",
        body: JSON.stringify({
          store_id: storeId,
          store_name: form.store_name.trim(),
          person_type: form.person_type,
          document: onlyDigits(form.document),
          contact_email: form.contact_email.trim(),
          contact_phone: onlyDigits(form.contact_phone),
          postal_code: onlyDigits(form.postal_code),
          street: form.street.trim(),
          number: form.number.trim(),
          district: form.district.trim(),
          city: form.city.trim(),
          state: form.state.trim().toUpperCase(),
          complement: form.complement.trim(),
          reference: form.reference.trim(),
          operating_hours: form.operating_hours,
        }),
      });
      router.replace("/portal");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao salvar onboarding");
    } finally {
      setSaving(false);
    }
  }

  if (!ready || loading) {
    return (
      <main className="min-h-screen flex items-center justify-center text-slate-700 bg-[#f5f3ff] px-4">
        <p className="text-sm">Carregando cadastro inicial...</p>
      </main>
    );
  }

  return (
    <main className="relative min-h-screen overflow-hidden bg-gradient-to-br from-[#f5f3ff] via-[#ede7ff] to-[#f8f7ff] text-slate-900">
      <div className="pointer-events-none absolute -top-28 -right-20 h-72 w-72 rounded-full bg-[#6320ee]/20 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-36 -left-20 h-80 w-80 rounded-full bg-[#8b5cf6]/20 blur-3xl" />

      <div className="relative mx-auto w-full max-w-7xl px-4 py-8 md:px-8 md:py-10 opacity-0 animate-[fade-up_0.65s_ease_forwards]">
        <header className="rounded-2xl border border-white/70 bg-white/80 p-6 shadow-sm backdrop-blur-md text-center md:p-8">
          <h1 className="text-3xl font-semibold">Vamos iniciar o cadastro da sua loja!</h1>
        </header>

        <section className="mt-5 rounded-2xl border border-slate-200 bg-slate-50/85 px-4 py-5 md:px-6">
          <div className="overflow-x-auto">
            <div className="flex min-w-[720px] items-center">
              {progress.map((item, index) => {
                const active = step === item.id;
                const done = step > item.id;
                return (
                  <Fragment key={item.id}>
                    <div className="flex items-center gap-3 shrink-0">
                      <div
                        className={`h-8 w-8 rounded-full border text-xs font-semibold flex items-center justify-center ${
                          done
                            ? "bg-emerald-500 text-white border-emerald-500"
                            : active
                              ? "bg-[#6320ee] text-white border-[#6320ee]"
                              : "bg-white text-slate-500 border-slate-300"
                        }`}
                      >
                        {item.id}
                      </div>
                      <span className={`text-base whitespace-nowrap ${active ? "text-slate-900 font-semibold" : "text-slate-500"}`}>
                        {item.title}
                      </span>
                    </div>
                    {index < progress.length - 1 && (
                      <div className={`mx-4 h-[2px] min-w-16 flex-1 ${step > item.id ? "bg-[#6320ee]" : "bg-slate-300"}`} />
                    )}
                  </Fragment>
                );
              })}
            </div>
          </div>
        </section>

        <section className="mt-5 rounded-2xl border border-slate-200 bg-white/90 p-6 shadow-sm backdrop-blur-md md:p-8">
          {error && <p className="mb-5 text-sm text-red-600">{error}</p>}
          {validationNotice && (
            <div className="mb-5 rounded-xl border border-amber-300 bg-amber-50 p-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold text-amber-900">{validationNotice.title}</p>
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-amber-900">
                    {validationNotice.items.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
                <button
                  type="button"
                  onClick={() => setValidationNotice(null)}
                  className="rounded-md border border-amber-400 px-2 py-1 text-xs font-medium text-amber-900 hover:bg-amber-100"
                >
                  Fechar
                </button>
              </div>
            </div>
          )}

          <div key={step} className="opacity-0 animate-[fade-up_0.45s_ease_forwards]">
          {step === 1 && (
            <section className="space-y-4">
              <div className="space-y-1">
                <label>
                  <RequiredLabel>Nome da loja</RequiredLabel>
                </label>
                <input
                  className={inputClass("store_name")}
                  value={form.store_name}
                  onChange={(e) => setForm((prev) => ({ ...prev, store_name: e.target.value }))}
                  placeholder="Ex.: Pizzaria Central"
                  required
                />
                {fieldErrors.store_name && <p className="text-xs text-red-600">{fieldErrors.store_name}</p>}
              </div>

              <div className="space-y-2">
                <p className="text-sm font-medium text-slate-800">
                  Modelo de negocio <span className="text-red-600">*</span>
                </p>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      setForm((prev) => ({
                        ...prev,
                        person_type: "individual",
                        document: formatDocument("individual", prev.document),
                      }))
                    }
                    className={`px-3 py-2 rounded-xl border text-sm font-medium ${
                      form.person_type === "individual"
                        ? "border-[#6320ee] bg-[#ede7ff] text-[#4a19b3]"
                        : "border-slate-200 bg-white text-slate-700"
                    }`}
                  >
                    Pessoa Fisica
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setForm((prev) => ({
                        ...prev,
                        person_type: "company",
                        document: formatDocument("company", prev.document),
                      }))
                    }
                    className={`px-3 py-2 rounded-xl border text-sm font-medium ${
                      form.person_type === "company"
                        ? "border-[#6320ee] bg-[#ede7ff] text-[#4a19b3]"
                        : "border-slate-200 bg-white text-slate-700"
                    }`}
                  >
                    Pessoa Juridica
                  </button>
                </div>
              </div>

              <div className="space-y-1">
                <label>
                  <RequiredLabel>{form.person_type === "individual" ? "CPF" : "CNPJ"}</RequiredLabel>
                </label>
                <input
                  className={inputClass("document")}
                  value={form.document}
                  onChange={(e) =>
                    setForm((prev) => ({
                      ...prev,
                      document: formatDocument(prev.person_type, e.target.value),
                    }))
                  }
                  placeholder={form.person_type === "individual" ? "000.000.000-00" : "00.000.000/0000-00"}
                  required
                />
                {fieldErrors.document && <p className="text-xs text-red-600">{fieldErrors.document}</p>}
              </div>

              <div className="grid md:grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label>
                    <RequiredLabel>Email</RequiredLabel>
                  </label>
                  <input
                    type="email"
                    className={inputClass("contact_email")}
                    value={form.contact_email}
                    onChange={(e) => setForm((prev) => ({ ...prev, contact_email: e.target.value }))}
                    required
                  />
                  {fieldErrors.contact_email && <p className="text-xs text-red-600">{fieldErrors.contact_email}</p>}
                </div>
                <div className="space-y-1">
                  <label>
                    <RequiredLabel>Telefone</RequiredLabel>
                  </label>
                  <input
                    className={inputClass("contact_phone")}
                    value={form.contact_phone}
                    onChange={(e) => setForm((prev) => ({ ...prev, contact_phone: formatPhone(e.target.value) }))}
                    required
                  />
                  {fieldErrors.contact_phone && <p className="text-xs text-red-600">{fieldErrors.contact_phone}</p>}
                </div>
              </div>
            </section>
          )}

          {step === 2 && (
            <section className="space-y-4">
              <div className="grid md:grid-cols-2 gap-4">
                <div className="space-y-1 md:col-span-2">
                  <label>
                    <RequiredLabel>CEP</RequiredLabel>
                  </label>
                  <input
                    className={inputClass("postal_code")}
                    value={form.postal_code}
                    onChange={(e) => setForm((prev) => ({ ...prev, postal_code: formatCEP(e.target.value) }))}
                    onBlur={onCEPBlur}
                    placeholder="00000-000"
                    required
                  />
                  {fieldErrors.postal_code && <p className="text-xs text-red-600">{fieldErrors.postal_code}</p>}
                </div>
                <div className="space-y-1 md:col-span-2">
                  <label>
                    <RequiredLabel>Rua</RequiredLabel>
                  </label>
                  <input
                    className={inputClass("street")}
                    value={form.street}
                    onChange={(e) => setForm((prev) => ({ ...prev, street: e.target.value }))}
                    required
                  />
                  {fieldErrors.street && <p className="text-xs text-red-600">{fieldErrors.street}</p>}
                </div>
                <div className="space-y-1">
                  <label>
                    <RequiredLabel>Numero</RequiredLabel>
                  </label>
                  <input
                    className={inputClass("number")}
                    value={form.number}
                    onChange={(e) => setForm((prev) => ({ ...prev, number: e.target.value }))}
                    required
                  />
                  {fieldErrors.number && <p className="text-xs text-red-600">{fieldErrors.number}</p>}
                </div>
                <div className="space-y-1">
                  <label>
                    <span className="text-sm font-medium text-slate-800">Complemento</span>
                  </label>
                  <input
                    className={inputClass("complement")}
                    value={form.complement}
                    onChange={(e) => setForm((prev) => ({ ...prev, complement: e.target.value }))}
                  />
                  {fieldErrors.complement && <p className="text-xs text-red-600">{fieldErrors.complement}</p>}
                </div>
                <div className="space-y-1 md:col-span-2">
                  <label>
                    <RequiredLabel>Bairro</RequiredLabel>
                  </label>
                  <input
                    className={inputClass("district")}
                    value={form.district}
                    onChange={(e) => setForm((prev) => ({ ...prev, district: e.target.value }))}
                    required
                  />
                  {fieldErrors.district && <p className="text-xs text-red-600">{fieldErrors.district}</p>}
                </div>
                <div className="space-y-1">
                  <label>
                    <RequiredLabel>Cidade</RequiredLabel>
                  </label>
                  <input
                    className={inputClass("city")}
                    value={form.city}
                    onChange={(e) => setForm((prev) => ({ ...prev, city: e.target.value }))}
                    required
                  />
                  {fieldErrors.city && <p className="text-xs text-red-600">{fieldErrors.city}</p>}
                </div>
                <div className="space-y-1">
                  <label>
                    <RequiredLabel>UF</RequiredLabel>
                  </label>
                  <input
                    className={inputClass("state")}
                    value={form.state}
                    onChange={(e) => setForm((prev) => ({ ...prev, state: e.target.value.toUpperCase() }))}
                    maxLength={2}
                    required
                  />
                  {fieldErrors.state && <p className="text-xs text-red-600">{fieldErrors.state}</p>}
                </div>
                <div className="space-y-1 md:col-span-2">
                  <label>
                    <span className="text-sm font-medium text-slate-800">Referencia</span>
                  </label>
                  <input
                    className={inputClass("reference")}
                    value={form.reference}
                    onChange={(e) => setForm((prev) => ({ ...prev, reference: e.target.value }))}
                  />
                  {fieldErrors.reference && <p className="text-xs text-red-600">{fieldErrors.reference}</p>}
                </div>
              </div>
            </section>
          )}

          {step === 3 && (
            <section className="space-y-4">
              <p className="text-sm text-slate-600">
                Horario de funcionamento <span className="text-red-600">*</span>. O calendario sera ajustado depois em Configuracoes da loja.
              </p>
              <div className="grid gap-3">
                {OPERATING_DAYS.map((day) => {
                  const item = form.operating_hours.find((entry) => entry.day === day.day);
                  return (
                    <div key={day.day} className="rounded-xl border border-slate-200 p-3 space-y-2 bg-white">
                      <label className="flex items-center gap-2 text-sm font-medium text-slate-800">
                        <input
                          type="checkbox"
                          checked={item?.enabled ?? false}
                          onChange={(e) => setHour(day.day, { enabled: e.target.checked })}
                        />
                        {day.label}
                      </label>
                      <div className="grid grid-cols-2 gap-2">
                        <input
                          type="time"
                          className="input"
                          value={item?.open || "08:00"}
                          disabled={!item?.enabled}
                          onChange={(e) => setHour(day.day, { open: e.target.value })}
                        />
                        <input
                          type="time"
                          className="input"
                          value={item?.close || "18:00"}
                          disabled={!item?.enabled}
                          onChange={(e) => setHour(day.day, { close: e.target.value })}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
              {fieldErrors.operating_hours && <p className="text-xs text-red-600">{fieldErrors.operating_hours}</p>}
            </section>
          )}
        </div>

          <footer className="flex items-center justify-between gap-3 pt-2">
          <button
            type="button"
            className="px-4 py-2 rounded-lg bg-slate-100 border border-slate-200 text-sm text-slate-700 disabled:opacity-50"
            disabled={step === 1 || saving}
            onClick={() => {
              setFieldErrors({});
              setValidationNotice(null);
              setStep((prev) => (prev === 1 ? 1 : ((prev - 1) as WizardStep)));
            }}
          >
            Voltar
          </button>
          {step < 3 ? (
            <button
              type="button"
              className="px-4 py-2 rounded-lg bg-[#6320ee] text-white text-sm font-semibold disabled:opacity-50"
              disabled={saving}
              onClick={() => {
                const current = step;
                if (!validateStep(current)) return;
                setStep((prev) => (prev === 3 ? 3 : ((prev + 1) as WizardStep)));
              }}
            >
              Continuar
            </button>
          ) : (
            <button
              type="button"
              className="px-4 py-2 rounded-lg bg-[#6320ee] text-white text-sm font-semibold disabled:opacity-50"
              disabled={saving}
              onClick={submit}
            >
              {saving ? "Salvando..." : "Concluir cadastro"}
            </button>
          )}
          </footer>
        </section>
      </div>
    </main>
  );
}
