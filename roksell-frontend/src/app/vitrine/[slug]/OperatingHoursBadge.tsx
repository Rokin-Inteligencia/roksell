"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { OperatingHoursDay } from "@/types";

const DAYS = [
  { day: 0, label: "Segunda" },
  { day: 1, label: "Terca" },
  { day: 2, label: "Quarta" },
  { day: 3, label: "Quinta" },
  { day: 4, label: "Sexta" },
  { day: 5, label: "Sabado" },
  { day: 6, label: "Domingo" },
];

type OperatingHoursBadgeProps = {
  isOpen: boolean;
  hours: OperatingHoursDay[];
  deliveryMinutes?: number | null;
  deliveryEnabled?: boolean | null;
  allowPreorderWhenClosed?: boolean;
};

function formatRange(entry?: OperatingHoursDay) {
  if (!entry?.enabled || !entry.open || !entry.close) return "Fechado";
  return `${entry.open} - ${entry.close}`;
}

export function OperatingHoursBadge({
  isOpen,
  hours,
  deliveryMinutes,
  deliveryEnabled,
  allowPreorderWhenClosed,
}: OperatingHoursBadgeProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const statusLabel = isOpen ? "Aberto" : "Fechado";
  const statusTone = isOpen ? "bg-emerald-500/90 text-white" : "bg-rose-500/90 text-white";
  const hoursByDay = useMemo(() => new Map(hours.map((item) => [item.day, item])), [hours]);
  const showDelivery =
    isOpen &&
    (deliveryEnabled ?? true) &&
    typeof deliveryMinutes === "number" &&
    Number.isFinite(deliveryMinutes) &&
    deliveryMinutes > 0;

  useEffect(() => {
    if (!open) return;
    function handleClick(event: MouseEvent) {
      if (!rootRef.current) return;
      if (rootRef.current.contains(event.target as Node)) return;
      setOpen(false);
    }
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="relative inline-flex items-center gap-2">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-[10px] uppercase tracking-[0.28em] ${statusTone} hover:brightness-110`}
        aria-expanded={open}
        aria-controls="operating-hours-panel"
        title="Ver horario de funcionamento"
      >
        <span className="h-2 w-2 rounded-full bg-white/90" />
        {statusLabel}
      </button>
      {!isOpen && allowPreorderWhenClosed && (
        <span className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[10px] uppercase tracking-[0.2em] bg-amber-100 text-amber-800 border border-amber-300 shadow-sm">
          <svg
            className="h-3 w-3"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="9" />
            <path d="m8 12 2.5 2.5L16 9" />
          </svg>
          Encomenda
        </span>
      )}
      {showDelivery && (
        <span className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-[10px] uppercase tracking-[0.28em] bg-white/90 text-slate-700 border border-slate-200 shadow-sm">
          <svg
            className="h-3 w-3"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M3 7h11v8H3z" />
            <path d="M14 10h4l3 3v2h-7z" />
            <circle cx="7" cy="17" r="2" />
            <circle cx="17" cy="17" r="2" />
          </svg>
          {deliveryMinutes} min
        </span>
      )}

      {open && (
        <div
          id="operating-hours-panel"
          className="absolute left-1/2 top-full mt-2 -translate-x-1/2 z-50 w-[220px] max-w-[90vw] rounded-2xl border border-slate-200 bg-white/95 shadow-xl shadow-slate-200/70 px-3 py-2 text-[11px] text-slate-700 backdrop-blur"
        >
          <div className="flex items-center justify-end pb-2">
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="text-[11px] font-semibold text-slate-600 hover:text-slate-900"
            >
              Fechar
            </button>
          </div>
          <div className="space-y-1">
            {DAYS.map((dayItem) => {
              const entry = hoursByDay.get(dayItem.day);
              return (
                <div key={dayItem.day} className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-slate-700">{dayItem.label}</span>
                  <span className="text-slate-600">{formatRange(entry)}</span>
                </div>
              );
            })}
            {hours.length === 0 && <span className="text-slate-500">Horario nao configurado.</span>}
          </div>
        </div>
      )}
    </div>
  );
}
