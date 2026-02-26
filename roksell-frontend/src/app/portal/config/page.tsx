"use client";

import { useEffect } from "react";

export default function ConfigRedirectPage() {
  useEffect(() => {
    window.location.replace("/portal/lojas");
  }, []);

  return (
    <main className="min-h-screen flex items-center justify-center px-4 text-slate-700">
      <p className="text-sm">Redirecionando para Lojas...</p>
    </main>
  );
}
