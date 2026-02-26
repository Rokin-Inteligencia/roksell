"use client";

import { useEffect, useRef, useState } from "react";

type ProfileInfo = {
  name: string;
  role: string;
};

const ROLE_LABEL: Record<string, string> = {
  owner: "Administrador",
  manager: "Gerente",
  operator: "Operador",
};

export function ProfileBadge({
  name = "Usuario",
  photoUrl,
}: {
  name?: string;
  photoUrl?: string;
}) {
  const [open, setOpen] = useState(false);
  const [profile, setProfile] = useState<ProfileInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const wrapperRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let active = true;
    async function loadProfile() {
      if (loading || profile) return;
      setLoading(true);
      try {
        const res = await fetch("/api/auth/me", { credentials: "include" });
        if (!res.ok) return;
        const data = await res.json();
        if (!active) return;
        if (typeof data?.name === "string" && typeof data?.role === "string") {
          setProfile({ name: data.name, role: data.role });
        }
      } catch {
        /* ignore */
      } finally {
        if (active) setLoading(false);
      }
    }
    loadProfile();
    return () => {
      active = false;
    };
  }, [loading, profile]);

  useEffect(() => {
    if (!open) return;
    const onClick = (event: MouseEvent) => {
      const target = event.target as Node | null;
      if (target && wrapperRef.current?.contains(target)) return;
      setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("mousedown", onClick);
    };
  }, [open]);

  const displayName = profile?.name || name;
  const initial = displayName.trim().charAt(0).toUpperCase() || "U";
  const roleLabel = profile ? ROLE_LABEL[profile.role] || profile.role : "Usuario";

  return (
    <div ref={wrapperRef} className="relative hidden lg:block">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="h-12 w-12 rounded-full border-2 border-slate-200 shadow-lg shadow-slate-200/60 overflow-hidden bg-slate-100 flex items-center justify-center text-lg font-semibold text-slate-700"
        aria-expanded={open}
        aria-haspopup="dialog"
      >
        {photoUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={photoUrl} alt={displayName} className="h-full w-full object-cover" />
        ) : (
          initial
        )}
      </button>
      {open && (
        <div className="absolute right-0 mt-3 w-56 rounded-2xl border border-slate-200 bg-white p-4 text-left shadow-xl shadow-slate-200/60">
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">Perfil</div>
          <div className="mt-1 text-base font-semibold text-slate-900">{displayName}</div>
          <div className="text-sm text-slate-600">{roleLabel}</div>
        </div>
      )}
    </div>
  );
}
