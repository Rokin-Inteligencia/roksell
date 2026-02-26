"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { adminFetch } from "@/lib/admin-api";
import { useAdminGuard } from "@/lib/use-admin-guard";
import { ProfileBadge } from "@/components/admin/ProfileBadge";
import { AdminSidebar } from "@/components/admin/AdminSidebar";
import { adminMenuWithHome } from "@/config/adminMenu";
import { usePathname } from "next/navigation";
import { useOrgName } from "@/lib/use-org-name";
import { clearAdminToken } from "@/lib/admin-auth";

type InboundMessage = {
  id: string;
  direction: "inbound" | "outbound";
  phone: string;
  message_type?: string | null;
  message_text?: string | null;
  media_url?: string | null;
  media_mime?: string | null;
  status?: string | null;
  provider_message_id?: string | null;
  created_at: string;
};

type Thread = {
  phone: string;
  customer_name?: string | null;
  last_message: string;
  last_received_at: string;
  total: number;
  unread_count: number;
};

type PushPublicKeyResponse = {
  enabled: boolean;
  public_key?: string | null;
};

function formatPhone(phone: string) {
  if (!phone) return "-";
  if (phone.startsWith("55") && phone.length >= 12) {
    const ddd = phone.slice(2, 4);
    const rest = phone.slice(4);
    return `+55 ${ddd} ${rest}`;
  }
  return phone;
}

function formatDateTime(value?: string | null) {
  if (!value) return "-";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function base64UrlToArrayBuffer(value: string): ArrayBuffer {
  const padding = "=".repeat((4 - (value.length % 4)) % 4);
  const normalized = (value + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(normalized);
  const output = new Uint8Array(raw.length);
  for (let index = 0; index < raw.length; index += 1) {
    output[index] = raw.charCodeAt(index);
  }
  return output.buffer as ArrayBuffer;
}

export default function MensagensPage() {
  const ready = useAdminGuard();
  const tenantName = useOrgName();
  const pathname = usePathname();
  const [preferredPhone, setPreferredPhone] = useState("");
  const [threads, setThreads] = useState<Thread[]>([]);
  const [messages, setMessages] = useState<InboundMessage[]>([]);
  const [selectedPhone, setSelectedPhone] = useState<string>("");
  const [expandedImageUrl, setExpandedImageUrl] = useState<string | null>(null);
  const selectedPhoneRef = useRef("");
  const messagesContainerRef = useRef<HTMLDivElement | null>(null);
  const shouldScrollToBottomRef = useRef(false);
  const [pushSupported, setPushSupported] = useState(false);
  const [pushEnabled, setPushEnabled] = useState(false);
  const [pushBusy, setPushBusy] = useState(false);
  const [pushMessage, setPushMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  async function loadThreads() {
    setError(null);
    try {
      const nextThreads = await adminFetch<Thread[]>("/admin/whatsapp/threads?limit=200");
      setThreads(nextThreads);
      const currentSelected = selectedPhoneRef.current;
      const preferredExists = preferredPhone && nextThreads.some((item) => item.phone === preferredPhone);
      if (preferredExists && currentSelected !== preferredPhone) {
        setSelectedPhone(preferredPhone);
      } else if (currentSelected && !nextThreads.some((t) => t.phone === currentSelected)) {
        setSelectedPhone("");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao carregar mensagens");
    }
  }

  async function loadMessages(phone: string) {
    if (!phone) return;
    setLoading(true);
    setError(null);
    try {
      const qs = new URLSearchParams({ phone, limit: "200" });
      const res = await adminFetch<InboundMessage[]>(`/admin/whatsapp/conversation?${qs.toString()}`);
      setMessages(res);
      const readParams = new URLSearchParams({ phone });
      adminFetch(`/admin/whatsapp/read?${readParams.toString()}`, { method: "POST" }).catch(() => {});
      setThreads((current) =>
        current.map((thread) =>
          thread.phone === phone ? { ...thread, unread_count: 0 } : thread
        )
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao carregar conversa");
    } finally {
      setLoading(false);
    }
  }

  async function getPushRegistration(): Promise<ServiceWorkerRegistration> {
    return navigator.serviceWorker.register("/whatsapp-push-sw.js", { scope: "/portal/" });
  }

  async function subscribePushNotifications() {
    if (!pushSupported || pushBusy) return;
    setPushBusy(true);
    setPushMessage(null);
    try {
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        setPushEnabled(false);
        setPushMessage("Permissao de notificacao negada no navegador.");
        return;
      }
      const config = await adminFetch<PushPublicKeyResponse>("/admin/whatsapp/push/public-key");
      if (!config.enabled || !config.public_key) {
        setPushMessage("Push nao configurado no servidor (WEB_PUSH_PUBLIC_KEY/PRIVATE_KEY).");
        return;
      }
      const registration = await getPushRegistration();
      const applicationServerKey = base64UrlToArrayBuffer(config.public_key);
      const current = await registration.pushManager.getSubscription();
      const subscription =
        current ??
        (await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey,
        }));
      const payload = subscription.toJSON();
      if (!payload.endpoint || !payload.keys?.p256dh || !payload.keys?.auth) {
        throw new Error("Subscription invalida");
      }
      await adminFetch("/admin/whatsapp/push/subscribe", {
        method: "POST",
        body: JSON.stringify({
          endpoint: payload.endpoint,
          expirationTime: payload.expirationTime,
          keys: {
            p256dh: payload.keys.p256dh,
            auth: payload.keys.auth,
          },
          user_agent: navigator.userAgent,
        }),
      });
      setPushEnabled(true);
      setPushMessage("Notificacoes push ativadas.");
    } catch (e) {
      setPushEnabled(false);
      setPushMessage(e instanceof Error ? e.message : "Falha ao ativar notificacoes push.");
    } finally {
      setPushBusy(false);
    }
  }

  async function unsubscribePushNotifications() {
    if (!pushSupported || pushBusy) return;
    setPushBusy(true);
    setPushMessage(null);
    try {
      const registration = await getPushRegistration();
      const subscription = await registration.pushManager.getSubscription();
      if (subscription) {
        const endpoint = subscription.endpoint;
        await subscription.unsubscribe();
        await adminFetch("/admin/whatsapp/push/unsubscribe", {
          method: "POST",
          body: JSON.stringify({ endpoint }),
        });
      }
      setPushEnabled(false);
      setPushMessage("Notificacoes push desativadas.");
    } catch (e) {
      setPushMessage(e instanceof Error ? e.message : "Falha ao desativar notificacoes push.");
    } finally {
      setPushBusy(false);
    }
  }

  async function initPushState() {
    if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) {
      setPushSupported(false);
      return;
    }
    setPushSupported(true);
    try {
      const registration = await getPushRegistration();
      const subscription = await registration.pushManager.getSubscription();
      const enabled = Notification.permission === "granted" && !!subscription;
      setPushEnabled(enabled);
      if (!enabled || !subscription) return;
      const payload = subscription.toJSON();
      if (!payload.endpoint || !payload.keys?.p256dh || !payload.keys?.auth) return;
      await adminFetch("/admin/whatsapp/push/subscribe", {
        method: "POST",
        body: JSON.stringify({
          endpoint: payload.endpoint,
          expirationTime: payload.expirationTime,
          keys: {
            p256dh: payload.keys.p256dh,
            auth: payload.keys.auth,
          },
          user_agent: navigator.userAgent,
        }),
      });
    } catch {
      setPushEnabled(false);
    }
  }

  function scrollConversationToBottom() {
    const container = messagesContainerRef.current;
    if (!container) return;
    container.scrollTop = container.scrollHeight;
  }

  useEffect(() => {
    if (!ready) return;
    loadThreads();
    initPushState();
    const timer = setInterval(loadThreads, 20000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);

  useEffect(() => {
    selectedPhoneRef.current = selectedPhone;
  }, [selectedPhone]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const phone = new URLSearchParams(window.location.search).get("phone");
    setPreferredPhone((phone || "").trim());
  }, []);

  useEffect(() => {
    if (!selectedPhone) return;
    shouldScrollToBottomRef.current = true;
  }, [selectedPhone]);

  useEffect(() => {
    if (!ready || !selectedPhone) return;
    loadMessages(selectedPhone);
    const timer = setInterval(() => loadMessages(selectedPhone), 15000);
    return () => clearInterval(timer);
  }, [ready, selectedPhone]);

  useEffect(() => {
    if (!messages.length) return;
    if (!shouldScrollToBottomRef.current) return;
    scrollConversationToBottom();
    shouldScrollToBottomRef.current = false;
  }, [messages]);

  const selectedThread = useMemo(
    () => threads.find((thread) => thread.phone === selectedPhone) || null,
    [threads, selectedPhone],
  );
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const chatOpen = !!selectedPhone;

  async function sendMessage() {
    if (!selectedPhone || !draft.trim()) return;
    setSending(true);
    try {
      await adminFetch("/admin/whatsapp/send", {
        method: "POST",
        body: JSON.stringify({ phone: selectedPhone, text: draft.trim() }),
      });
      setDraft("");
      shouldScrollToBottomRef.current = true;
      await loadMessages(selectedPhone);
      await loadThreads();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao enviar mensagem");
    } finally {
      setSending(false);
    }
  }

  if (!ready) return null;

  return (
    <>
    <main className="min-h-screen text-slate-900 bg-[#f5f3ff] overflow-x-hidden">
      <div className="max-w-7xl w-full mx-auto px-3 sm:px-4 lg:px-6 py-8">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[260px_minmax(0,1fr)] items-start min-w-0">
          <AdminSidebar
            menu={adminMenuWithHome}
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

          <div className="space-y-6 min-w-0">
            <header className="flex flex-wrap items-center justify-between gap-3">
              <div className="text-slate-900 space-y-1">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-600">Admin - Mensagens</p>
                <h1 className="text-3xl font-semibold">Central de WhatsApp</h1>
                <p className="text-sm text-slate-600">
                  Veja mensagens recebidas e enviadas no seu numero e acompanhe cada cliente.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {pushSupported && (
                  <button
                    type="button"
                    onClick={pushEnabled ? unsubscribePushNotifications : subscribePushNotifications}
                    disabled={pushBusy}
                    className="px-3 py-2 rounded-lg border border-slate-200 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                  >
                    {pushBusy
                      ? "Processando..."
                      : pushEnabled
                        ? "Desativar notificacoes push"
                        : "Ativar notificacoes push"}
                  </button>
                )}
                <ProfileBadge />
              </div>
            </header>

            {error && <p className="text-sm text-red-500">{error}</p>}
            {pushMessage && <p className="text-sm text-slate-600">{pushMessage}</p>}
            {!pushSupported && (
              <p className="text-sm text-slate-500">
                Este navegador nao suporta notificacoes push em segundo plano.
              </p>
            )}

            <section className="grid grid-cols-1 gap-4 lg:grid-cols-[280px_minmax(0,1fr)] min-w-0">
              <div
                className={`rounded-2xl bg-white border border-slate-200 p-3 space-y-3 min-w-0 ${
                  chatOpen ? "hidden lg:block" : ""
                }`}
              >
                <div className="flex items-center justify-between">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Conversas</p>
                  <span className="text-xs text-slate-500">{threads.length}</span>
                </div>
                <div className="space-y-2 max-h-[70vh] lg:max-h-[520px] overflow-auto pr-1">
                  {threads.length === 0 && (
                    <p className="text-sm text-slate-500">Nenhuma mensagem recebida.</p>
                  )}
                  {threads.map((thread) => {
                    const isActive = thread.phone === selectedPhone;
                    const hasUnread = thread.unread_count > 0;
                    return (
                      <button
                        key={thread.phone}
                        type="button"
                        onClick={() => {
                          shouldScrollToBottomRef.current = true;
                          setSelectedPhone(thread.phone);
                        }}
                        className={`w-full text-left rounded-xl border px-3 py-2 transition overflow-hidden ${
                          isActive
                            ? "border-[#25D366] bg-[#e8fff1]"
                            : hasUnread
                              ? "border-[#25D366]/50 bg-[#f1fff6] hover:bg-[#e9ffef]"
                              : "border-slate-200 bg-slate-50 hover:bg-slate-100"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div className={`font-semibold text-sm min-w-0 truncate ${hasUnread ? "text-slate-900" : ""}`}>
                            {formatPhone(thread.phone)}
                            {thread.customer_name ? ` | ${thread.customer_name}` : ""}
                          </div>
                          <span className={`text-[10px] shrink-0 ${hasUnread ? "text-[#178f45]" : "text-slate-500"}`}>
                            {formatDateTime(thread.last_received_at)}
                          </span>
                        </div>
                        <div className="mt-1 flex items-center justify-between gap-2">
                          <div className={`text-xs min-w-0 flex-1 truncate ${hasUnread ? "text-slate-800 font-medium" : "text-slate-600"}`}>
                            {thread.last_message}
                          </div>
                          {hasUnread && (
                            <span className="min-w-5 h-5 px-1 rounded-full bg-[#25D366] text-white text-[10px] font-bold inline-flex items-center justify-center">
                              {thread.unread_count > 99 ? "99+" : thread.unread_count}
                            </span>
                          )}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div
                className={`rounded-2xl bg-white border border-slate-200 p-4 flex flex-col h-[72vh] lg:h-[560px] ${
                  chatOpen ? "flex" : "hidden lg:flex"
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Mensagens</p>
                    <h2 className="text-lg font-semibold">
                      {selectedThread
                        ? `${formatPhone(selectedThread.phone)}${
                            selectedThread.customer_name ? ` | ${selectedThread.customer_name}` : ""
                          }`
                        : "Selecione uma conversa"}
                    </h2>
                  </div>
                  <div className="flex items-center gap-2">
                    {chatOpen && (
                      <button
                        type="button"
                        onClick={() => setSelectedPhone("")}
                        className="lg:hidden px-2 py-1 rounded-lg border border-slate-200 bg-slate-50 text-xs font-semibold text-slate-700"
                      >
                        Voltar
                      </button>
                    )}
                    {loading && <span className="text-xs text-slate-500">Atualizando...</span>}
                  </div>
                </div>
                <div className="mt-2 flex-1 overflow-hidden">
                  <div ref={messagesContainerRef} className="space-y-3 h-full overflow-auto pl-1 pr-4 sm:pl-2 sm:pr-5 pb-3">
                  {!selectedPhone && (
                    <p className="text-sm text-slate-500">Escolha um cliente para ver as mensagens.</p>
                  )}
                  {selectedPhone && messages.length === 0 && (
                    <p className="text-sm text-slate-500">Nenhuma mensagem nesta conversa.</p>
                  )}
                  {messages.map((msg) => {
                    const outbound = msg.direction === "outbound";
                    const mediaAvailable = !!msg.media_url && msg.message_type && msg.message_type !== "text";
                    const isImage = mediaAvailable && msg.message_type === "image";
                    const isAudio = mediaAvailable && msg.message_type === "audio";
                    return (
                      <div key={msg.id} className={`flex px-1 ${outbound ? "justify-end" : "justify-start"}`}>
                        <div
                          className={`max-w-[calc(100%-0.5rem)] sm:max-w-[80%] rounded-xl border p-3 break-words [overflow-wrap:anywhere] whitespace-pre-wrap ${
                            outbound
                              ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                              : "border-slate-200 bg-slate-50 text-slate-700"
                          }`}
                        >
                          <div className="flex items-center justify-between text-xs text-slate-500">
                            <span>{outbound ? "Voce" : formatPhone(msg.phone)}</span>
                            <span className="font-semibold text-slate-600">{formatDateTime(msg.created_at)}</span>
                          </div>
                          <div className="mt-1 text-sm">
                            {isImage && (
                              <button
                                type="button"
                                onClick={() => setExpandedImageUrl(msg.media_url || null)}
                                className="block"
                                aria-label="Abrir imagem"
                              >
                                <img
                                  src={msg.media_url || ""}
                                  alt="Imagem recebida"
                                  className="max-h-64 rounded-lg border border-slate-200 bg-white"
                                  loading="lazy"
                                />
                              </button>
                            )}
                            {isAudio && (
                              <audio
                                controls
                                src={msg.media_url || ""}
                                className="w-full mt-1"
                              />
                            )}
                            {mediaAvailable && !isImage && !isAudio && (
                              <a
                                href={msg.media_url || "#"}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 hover:border-slate-300"
                              >
                                {msg.message_type ? `Arquivo: ${msg.message_type}` : "Arquivo recebido"}
                              </a>
                            )}
                            {msg.message_text && (
                              <div className={mediaAvailable ? "mt-2" : ""}>{msg.message_text}</div>
                            )}
                            {!msg.message_text && !mediaAvailable && (
                              <div>
                                {msg.message_type === "image"
                                  ? "Imagem recebida (nao disponivel)."
                                  : msg.message_type || (outbound ? "Mensagem enviada." : "Mensagem recebida.")}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                  </div>
                </div>
                <div className="mt-3 border-t border-slate-200 pt-3">
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={draft}
                      onChange={(e) => setDraft(e.target.value)}
                      placeholder="Escreva uma mensagem..."
                      className="input w-full text-base md:text-sm"
                      disabled={!selectedPhone || sending}
                    />
                    <button
                      type="button"
                      onClick={sendMessage}
                      disabled={!selectedPhone || sending || !draft.trim()}
                      className="px-4 py-2 rounded-lg bg-[#25D366] text-white text-sm font-semibold hover:brightness-105 disabled:opacity-60"
                    >
                      {sending ? "Enviando..." : "Enviar"}
                    </button>
                  </div>
                </div>
              </div>
            </section>
          </div>
        </div>
      </div>
    </main>
    {expandedImageUrl && (
      <div
        className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4"
        onClick={() => setExpandedImageUrl(null)}
        role="presentation"
      >
        <div
          className="max-w-5xl w-full max-h-[90vh] flex items-center justify-center"
          onClick={(e) => e.stopPropagation()}
          role="presentation"
        >
          <img
            src={expandedImageUrl}
            alt="Imagem ampliada"
            className="max-h-[90vh] max-w-full rounded-xl border border-white/20 bg-white"
          />
        </div>
      </div>
    )}
    </>
  );
}
