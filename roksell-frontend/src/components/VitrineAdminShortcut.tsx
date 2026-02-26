"use client";
import { useEffect, useState } from "react";

type MeResponse = {
  role?: string | null;
};

const ALLOWED_ROLES = new Set(["owner", "manager", "operator", "admin", "seller", "vendedor"]);

export default function VitrineAdminShortcut() {
  const [allowed, setAllowed] = useState(false);

  useEffect(() => {
    const fetchMe = async () => {
      try {
        const res = await fetch("/api/auth/me", { method: "GET", credentials: "include" });
        if (!res.ok) return;
        const data: MeResponse = await res.json();
        const role = (data?.role || "").toLowerCase();
        if (ALLOWED_ROLES.has(role)) {
          setAllowed(true);
        }
      } catch {
        /* ignore */
      }
    };
    fetchMe();
  }, []);

  if (!allowed) return null;

  return (
    <a
      href="/portal"
      className="inline-flex items-center gap-2 rounded-full border border-neutral-200 bg-white px-3 py-1 text-xs font-semibold text-neutral-700 hover:bg-neutral-100"
      title="Ir para o portal"
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
        <path d="M3 12h7" />
        <path d="M10 5l7 7-7 7" />
        <path d="M17 12h4" />
      </svg>
      Portal
    </a>
  );
}
