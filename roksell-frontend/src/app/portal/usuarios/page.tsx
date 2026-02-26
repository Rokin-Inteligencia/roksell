"use client";
import { useAdminGuard } from "@/lib/use-admin-guard";
import { AdminSidebar } from "@/components/admin/AdminSidebar";
import { adminMenuWithHome } from "@/config/adminMenu";
import { usePathname } from "next/navigation";
import { ProfileBadge } from "@/components/admin/ProfileBadge";
import { useOrgName } from "@/lib/use-org-name";
import { clearAdminToken } from "@/lib/admin-auth";
import { UsersManagerPanel } from "@/components/admin/UsersManagerPanel";

export default function UsersAdminPage() {
  const ready = useAdminGuard();
  const tenantName = useOrgName();
  const pathname = usePathname();

  async function logout() {
    try {
      await fetch("/api/auth/logout", { method: "POST", credentials: "include" });
    } catch {
      /* ignore */
    } finally {
      clearAdminToken();
      window.location.href = "/portal/login";
    }
  }

  if (!ready) return null;

  const sidebarItems = adminMenuWithHome;

  return (
    <main className="min-h-screen text-slate-900 bg-[#f5f3ff]">
      <div className="max-w-7xl w-full mx-auto px-3 sm:px-4 lg:px-6 py-8">
        <div className="grid gap-6 lg:grid-cols-[260px_minmax(0,1fr)] items-start">
          <AdminSidebar
            menu={sidebarItems}
            currentPath={pathname}
            collapsible
            orgName={tenantName}
            footer={
              <button
                onClick={logout}
                className="block px-3 py-2 w-full text-left rounded-lg bg-[#6320ee] text-[#f8f0fb] font-semibold hover:brightness-95 transition"
              >
                Sair
              </button>
            }
          />

          <div className="space-y-6">
            <header className="flex flex-wrap items-center justify-between gap-3">
              <div className="text-slate-900 space-y-1">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-600">Admin - Usuarios</p>
                <h1 className="text-3xl font-semibold">Gestao de usuarios e lojas</h1>
                <p className="text-sm text-slate-600">
                  Crie administradores/operadores, associe-os a uma loja e respeite o limite de licencas.
                </p>
              </div>
              <ProfileBadge />
            </header>

            <UsersManagerPanel />
          </div>
        </div>
      </div>
    </main>
  );
}
