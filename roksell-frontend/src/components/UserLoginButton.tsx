"use client";
import { useEffect, useState } from "react";
import { clearAdminToken } from "@/lib/admin-auth";

type Props = {
  onLogin?: () => void;
  onLogout?: () => void;
};

export default function UserLoginButton({ onLogin, onLogout }: Props) {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [logged, setLogged] = useState(false);
  const [userInfo, setUserInfo] = useState<{ name?: string; email?: string; role?: string }>({});

  useEffect(() => {
    fetchMe();
  }, []);

  async function fetchMe() {
    try {
      const res = await fetch("/api/auth/me", { method: "GET", credentials: "include" });
      if (!res.ok) return;
      const data = await res.json();
      if (data) {
        setLogged(true);
        setUserInfo({ name: data.name, email: data.email, role: data.role });
      }
    } catch {
      /* ignore */
    }
  }

  async function login() {
    setError(null);
    setLoading(true);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
        credentials: "include",
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Falha no login");
      if (data?.access_token) {
        setLogged(true);
        setUserInfo({ name: data?.user?.name, email: data?.user?.email, role: data?.user?.role });
        onLogin?.();
        setOpen(false);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setLogged(false);
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    clearAdminToken();
    setLogged(false);
    setUserInfo({});
    onLogout?.();
    setOpen(false);
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="grid place-items-center p-2 rounded-full bg-neutral-200 hover:bg-neutral-300 active:scale-95 text-[#6320ee]"
        title={logged ? "Usuário conectado" : "Fazer login"}
      >
        <svg
          viewBox="0 0 24 24"
          aria-hidden="true"
          className="h-5 w-5"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M12 12a4 4 0 1 0-0.001-8.001A4 4 0 0 0 12 12Z" />
          <path d="M4 20c0-4.418 3.582-8 8-8s8 3.582 8 8" />
        </svg>
      </button>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm px-4">
          <div className="w-full max-w-md rounded-3xl bg-white border border-neutral-200 shadow-2xl p-6 space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.18em] text-neutral-500">Acesso</p>
                <h2 className="text-xl font-semibold">Conta</h2>
              </div>
              <button
                onClick={() => setOpen(false)}
                className="text-sm px-3 py-1 rounded-full bg-neutral-100 border border-neutral-200 hover:bg-neutral-200"
              >
                Fechar
              </button>
            </div>

            {!logged ? (
              <div className="space-y-2">
                <input
                  type="email"
                  className="input w-full text-sm"
                  placeholder="Email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
                <input
                  type="password"
                  className="input w-full text-sm"
                  placeholder="Senha"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                {error && <p className="text-xs text-red-600">{error}</p>}
                <button
                  onClick={login}
                  disabled={loading}
                  className="w-full px-3 py-2 rounded-lg bg-[#6320ee] text-white text-sm font-semibold active:scale-95 disabled:opacity-50"
                >
                  {loading ? "Entrando..." : "Entrar"}
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="rounded-xl bg-neutral-100 border border-neutral-200 p-3 text-sm space-y-1">
                  <div className="font-semibold">{userInfo.name || userInfo.email || "Usuário"}</div>
                  {userInfo.email && <div className="text-neutral-700">{userInfo.email}</div>}
                  {userInfo.role && (
                    <span className="inline-block text-[11px] px-2 py-1 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200">
                      Perfil: {userInfo.role}
                    </span>
                  )}
                </div>
                <button
                  onClick={logout}
                  className="w-full px-3 py-2 rounded-lg bg-neutral-200 text-neutral-900 text-sm font-semibold hover:bg-neutral-300"
                >
                  Sair
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
