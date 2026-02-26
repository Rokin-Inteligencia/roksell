import Link from "next/link";
import { ReactNode, useEffect, useState } from "react";
import { adminFetch } from "@/lib/admin-api";
import { getTenantSlug } from "@/lib/portal-auth";
import { AdminMenuItem } from "@/config/adminMenu";
import { useTenantModules } from "@/lib/use-tenant-modules";

type SidebarLink = AdminMenuItem & {
  badge?: string;
  badgeTone?: "whatsapp";
  variant?: "default" | "primary";
  copyHref?: string;
};

type AdminSidebarProps = {
  menu: SidebarLink[];
  footer?: ReactNode;
  collapsible?: boolean;
  orgName?: string;
  currentPath?: string;
};

type StoreCopyOption = {
  id: string;
  name: string;
  slug?: string | null;
};

export function AdminSidebar({ menu, footer, collapsible, orgName, currentPath }: AdminSidebarProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [displayName, setDisplayName] = useState(orgName);
  const [isMobile, setIsMobile] = useState(false);
  const [hasUserToggled, setHasUserToggled] = useState(false);
  const [tenantSlug, setTenantSlug] = useState(() => getTenantSlug());
  const [whatsappUnread, setWhatsappUnread] = useState<number | null>(null);
  const [copyPickerOpen, setCopyPickerOpen] = useState(false);
  const [copyStoreOptions, setCopyStoreOptions] = useState<StoreCopyOption[]>([]);
  const [copyStoreLoading, setCopyStoreLoading] = useState(false);
  const [copyStoreError, setCopyStoreError] = useState<string | null>(null);
  const [copyBaseHref, setCopyBaseHref] = useState<string | null>(null);
  const [copiedStoreId, setCopiedStoreId] = useState<string | null>(null);
  const [vitrineExpanded, setVitrineExpanded] = useState(false);
  const [vitrineStores, setVitrineStores] = useState<StoreCopyOption[]>([]);
  const [vitrineStoresLoading, setVitrineStoresLoading] = useState(false);
  const [vitrineStoresError, setVitrineStoresError] = useState<string | null>(null);
  const { hasModule } = useTenantModules();

  useEffect(() => {
    if (orgName) {
      setDisplayName(orgName);
    }
    let cancelled = false;
    adminFetch<{ name: string; slug: string }>("/admin/tenant")
      .then((res) => {
        if (!cancelled) {
          setDisplayName(res.name || res.slug);
          if (res.slug) setTenantSlug(res.slug);
        }
      })
      .catch(() => {
        if (!cancelled) setDisplayName(undefined);
      });
    return () => {
      cancelled = true;
    };
  }, [orgName]);

  useEffect(() => {
    const media = window.matchMedia("(max-width: 1023px)");
    const onChange = () => setIsMobile(media.matches);
    onChange();
    if (typeof media.addEventListener === "function") {
      media.addEventListener("change", onChange);
    } else {
      media.addListener(onChange);
    }
    return () => {
      if (typeof media.addEventListener === "function") {
        media.removeEventListener("change", onChange);
      } else {
        media.removeListener(onChange);
      }
    };
  }, []);

  useEffect(() => {
    if (!collapsible && !isMobile) {
      setCollapsed(false);
      setHasUserToggled(false);
      return;
    }
    if (!hasUserToggled) {
      setCollapsed(isMobile);
    }
  }, [collapsible, hasUserToggled, isMobile]);

  const hasMessagesMenu = menu.some(
    (item) =>
      item.href === "/portal/mensagens" &&
      item.enabled &&
      (!item.moduleKey || hasModule(item.moduleKey))
  );

  const allowCollapse = collapsible || isMobile;
  const showMenuLabel = !collapsed || isMobile;
  const cardOffsetClasses = collapsed ? "lg:w-[64px]" : "lg:translate-x-[-8px]";
  const cardBaseClasses =
    "rounded-3xl bg-white border border-slate-200 shadow-xl shadow-slate-200/60 text-slate-900";
  const cardResponsiveClasses = ["w-full", cardOffsetClasses].join(" ");
  const cardClasses = [
    cardBaseClasses,
    "p-3 lg:p-4 space-y-4",
    cardResponsiveClasses,
  ].join(" ");
  const companyCardClasses = [
    "mb-3",
    "hidden lg:block",
    cardBaseClasses,
    "p-3 lg:p-4",
    cardResponsiveClasses,
  ].join(" ");
  const vitrineBaseUrl = (process.env.NEXT_PUBLIC_VITRINE_BASE_URL || "https://www.rokin.com.br").replace(/\/$/, "");
  const resolvedMenu = menu.map<SidebarLink>((item) => {
    const isMessages = item.href === "/portal/mensagens";
    const messageBadge =
      item.href === "/portal/mensagens" && whatsappUnread && whatsappUnread > 0
        ? String(whatsappUnread)
        : item.badge;
    const badgeTone = isMessages && whatsappUnread && whatsappUnread > 0 ? "whatsapp" : item.badgeTone;
    let href = item.href;
    const moduleEnabled = item.moduleKey ? hasModule(item.moduleKey) : true;
    const isEnabled = item.enabled && moduleEnabled;
    let copyHref = isEnabled && item.copyable ? href : undefined;
    if (item.href.includes("{tenant}")) {
      if (tenantSlug) {
        href = item.href.replace("{tenant}", tenantSlug);
        copyHref = isEnabled && item.copyable ? href : undefined;
      } else {
        copyHref = undefined;
      }
    }
    if (copyHref) {
      copyHref = copyHref.startsWith("http") ? copyHref : `${vitrineBaseUrl}${copyHref}`;
    }
    return { ...item, href, copyHref, enabled: isEnabled, badge: messageBadge, badgeTone };
  });
  const visibleMenu = resolvedMenu.filter((item) => item.enabled);

  useEffect(() => {
    if (!hasMessagesMenu) return;
    let cancelled = false;
    const loadUnread = async () => {
      try {
        const res = await adminFetch<{ count: number }>("/admin/whatsapp/unread");
        if (!cancelled) setWhatsappUnread(res.count);
      } catch {
        if (!cancelled) setWhatsappUnread(null);
      }
    };
    loadUnread();
    const timer = setInterval(loadUnread, 20000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [hasMessagesMenu]);

  function buildStoreVitrineHref(baseHref: string, store: StoreCopyOption): string {
    const normalizedBase = baseHref.replace(/\/$/, "");
    const suffix = (store.slug || "").trim() || store.id;
    return `${normalizedBase}/${encodeURIComponent(suffix)}`;
  }

  async function loadVitrineStores(): Promise<{ stores: StoreCopyOption[]; failed: boolean }> {
    setVitrineStoresLoading(true);
    setVitrineStoresError(null);
    try {
      const options = await adminFetch<{ stores?: StoreCopyOption[] }>("/admin/groups/options");
      const stores = options.stores ?? [];
      setVitrineStores(stores);
      return { stores, failed: false };
    } catch {
      setVitrineStoresError("Falha ao carregar lojas.");
      return { stores: [], failed: true };
    } finally {
      setVitrineStoresLoading(false);
    }
  }

  async function openCopyStorePicker(baseHref: string) {
    setCopyBaseHref(baseHref);
    setCopyStoreLoading(true);
    setCopyStoreError(null);
    setCopiedStoreId(null);
    try {
      let stores = vitrineStores;
      let failed = false;
      if (stores.length === 0) {
        const loaded = await loadVitrineStores();
        stores = loaded.stores;
        failed = loaded.failed;
      }
      if (failed) {
        setCopyStoreError("Falha ao carregar lojas para copia.");
        setCopyPickerOpen(true);
        return;
      }
      setCopyStoreOptions(stores);
      if (stores.length === 0) {
        setCopyStoreError("Nenhuma loja disponivel para copiar.");
        setCopyPickerOpen(true);
        return;
      }
      setCopyPickerOpen(true);
    } catch {
      setCopyStoreError("Falha ao carregar lojas para copia.");
      setCopyPickerOpen(true);
    } finally {
      setCopyStoreLoading(false);
    }
  }

  function handleMenuCopy(copyHref: string, href: string): boolean {
    const isVitrinePath = href.startsWith("/vitrine/");
    if (!isVitrinePath) {
      copyToClipboard(copyHref);
      return true;
    }
    void openCopyStorePicker(copyHref);
    return false;
  }

  function copyStoreLink(store: StoreCopyOption) {
    if (!copyBaseHref) return;
    copyToClipboard(buildStoreVitrineHref(copyBaseHref, store));
    setCopiedStoreId(store.id);
    window.setTimeout(() => setCopiedStoreId(null), 1200);
  }

  function handleVitrineToggle(): boolean {
    const next = !vitrineExpanded;
    setVitrineExpanded(next);
    if (next && vitrineStores.length === 0 && !vitrineStoresLoading) {
      void loadVitrineStores();
    }
    return false;
  }

  return (
    <>
      <aside className="w-full self-start lg:sticky lg:top-6">
        {displayName && (
          <div className={companyCardClasses}>
            <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Empresa</div>
            <div className="text-base lg:text-lg font-semibold break-words">{displayName}</div>
          </div>
        )}
        <div className={cardClasses}>
          <div className="flex items-center justify-between">
            {showMenuLabel && <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Menu</div>}
            {allowCollapse && (
              <button
                onClick={() => {
                  setCollapsed((v) => !v);
                  setHasUserToggled(true);
                }}
                className="h-8 w-8 rounded-full bg-slate-100 border border-slate-200 hover:bg-slate-200 flex items-center justify-center"
                aria-label={collapsed ? "Abrir menu" : "Fechar menu"}
              >
                <span className="sr-only">{collapsed ? "Abrir menu" : "Fechar menu"}</span>
                <span className="flex flex-col gap-1">
                  <span className="block h-0.5 w-4 bg-slate-600" />
                  <span className="block h-0.5 w-4 bg-slate-600" />
                  <span className="block h-0.5 w-4 bg-slate-600" />
                </span>
              </button>
            )}
          </div>

          {!collapsed && (
            <>
              <nav className="space-y-2">
                {visibleMenu.map((item, index) => (
                  <div
                    key={item.label}
                    className="opacity-0 animate-[fade-up_0.5s_ease_forwards]"
                    style={{ animationDelay: `${index * 70}ms` }}
                  >
                    <SidebarItem
                      {...item}
                      activePath={currentPath}
                      onCopyRequest={handleMenuCopy}
                      onNavigateRequest={item.href.startsWith("/vitrine/") ? handleVitrineToggle : undefined}
                      expandable={item.href.startsWith("/vitrine/")}
                      expanded={item.href.startsWith("/vitrine/") ? vitrineExpanded : undefined}
                    />
                    {item.href.startsWith("/vitrine/") && vitrineExpanded && (
                      <div className="ml-3 mt-2 pl-3 border-l border-slate-200 space-y-1">
                        {vitrineStoresLoading && (
                          <p className="text-xs text-slate-500 px-2 py-1">Carregando lojas...</p>
                        )}
                        {!vitrineStoresLoading && vitrineStoresError && (
                          <p className="text-xs text-red-600 px-2 py-1">{vitrineStoresError}</p>
                        )}
                        {!vitrineStoresLoading && !vitrineStoresError && vitrineStores.length === 0 && (
                          <p className="text-xs text-slate-500 px-2 py-1">Nenhuma loja disponivel.</p>
                        )}
                        {!vitrineStoresLoading &&
                          !vitrineStoresError &&
                          vitrineStores.map((store) => {
                            const storeHref = buildStoreVitrineHref(item.href, store);
                            const active = currentPath ? currentPath.startsWith(storeHref) : false;
                            return (
                              <Link
                                key={store.id}
                                href={storeHref}
                                className={`flex items-center justify-between rounded-lg border px-3 py-2 text-sm transition ${
                                  active
                                    ? "border-[#6320ee]/40 bg-[#6320ee] text-white"
                                    : "border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100"
                                }`}
                              >
                                <span className="font-medium truncate">{store.name}</span>
                              </Link>
                            );
                          })}
                      </div>
                    )}
                  </div>
                ))}
              </nav>

              {footer && (
                <div className="pt-2 border-t border-slate-200 text-xs text-slate-500 space-y-1">{footer}</div>
              )}
            </>
          )}
        </div>
      </aside>

      {copyPickerOpen && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-900/80 backdrop-blur-sm px-4">
          <div className="w-full max-w-md rounded-3xl bg-white border border-slate-200 shadow-2xl p-6 space-y-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-600">Vitrine</p>
                <h2 className="text-xl font-semibold text-slate-900">Copiar link da loja</h2>
              </div>
              <button
                onClick={() => setCopyPickerOpen(false)}
                className="text-sm px-3 py-1 rounded-full bg-slate-100 border border-slate-200 hover:bg-slate-200"
              >
                Fechar
              </button>
            </div>

            {copyStoreLoading && <p className="text-sm text-slate-600">Carregando lojas...</p>}
            {copyStoreError && <p className="text-sm text-red-600">{copyStoreError}</p>}

            {!copyStoreLoading && !copyStoreError && (
              <div className="space-y-2 max-h-72 overflow-y-auto">
                {copyStoreOptions.map((store) => (
                  <button
                    key={store.id}
                    type="button"
                    onClick={() => copyStoreLink(store)}
                    className="w-full text-left rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 hover:bg-slate-100"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-semibold text-sm text-slate-900">{store.name}</span>
                      <span
                        className={`text-[10px] px-2 py-1 rounded-full border ${
                          copiedStoreId === store.id
                            ? "bg-emerald-500 border-emerald-500 text-white"
                            : "bg-white border-slate-300 text-slate-600"
                        }`}
                      >
                        {copiedStoreId === store.id ? "Copiado" : "Copiar"}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}

function copyToClipboard(text: string) {
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(text).catch(() => {});
    return;
  }
  if (typeof document === "undefined") return;
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "true");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  try {
    document.execCommand("copy");
  } catch {
    /* ignore */
  }
  document.body.removeChild(textarea);
}

function SidebarItem({
  label,
  href,
  enabled,
  badge,
  badgeTone,
  showStatus,
  variant = "default",
  activePath,
  copyHref,
  onCopyRequest,
  onNavigateRequest,
  expandable,
  expanded,
}: SidebarLink & {
  activePath?: string;
  onCopyRequest?: (copyHref: string, href: string) => boolean;
  onNavigateRequest?: (href: string) => boolean;
  expandable?: boolean;
  expanded?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const statusLabel = badge ?? (showStatus ? (enabled ? "Ativo" : "Inativo") : null);
  const hasStatusLabel = Boolean(statusLabel);
  if (!enabled) {
    return (
      <div className="flex items-center justify-between rounded-xl bg-slate-100 border border-slate-200 px-3 py-2 text-slate-500 opacity-80">
        <span>{label}</span>
        {hasStatusLabel ? (
          <span className="text-[10px] px-2 py-1 rounded-full bg-amber-100 border border-amber-200 text-amber-700">
            {statusLabel}
          </span>
        ) : (
          <span className="text-[10px] px-2 py-1 rounded-full bg-slate-200 border border-slate-300 text-slate-600">
            Em breve
          </span>
        )}
      </div>
    );
  }

  const isActive = activePath ? activePath.startsWith(href) : false;

  const variantClasses = (() => {
    if (isActive) return "bg-[#6320ee] text-white border-[#6320ee]/40";
    return variant === "primary" ? "bg-[#6320ee] text-white" : "bg-[#ede7ff] text-[#1f1b2e]";
  })();

  const badgeClasses = (() => {
    if (badgeTone === "whatsapp") {
      return "bg-[#25D366] border border-[#25D366] text-white";
    }
    return variant === "primary"
      ? "bg-black/10 border border-black/15 text-white"
      : "bg-white border border-slate-200 text-[#1f1b2e]";
  })();
  const shouldShowMeta = Boolean(copyHref || statusLabel || expandable);

  return (
    <Link
      href={href}
      className={`flex items-center justify-between rounded-xl border border-slate-200 px-3 py-2 hover:brightness-95 transition ${variantClasses}`}
      onClick={(event) => {
        if (!onNavigateRequest) return;
        const allowNavigate = onNavigateRequest(href);
        if (!allowNavigate) {
          event.preventDefault();
          event.stopPropagation();
        }
      }}
    >
      <span className="font-semibold">{label}</span>
      {shouldShowMeta && (
        <span className="flex items-center gap-2">
          {copyHref && (
            <button
              type="button"
              title={copied ? "Copiado" : "Copiar URL da vitrine"}
              aria-label={copied ? "Copiado" : "Copiar URL da vitrine"}
              className={`h-6 w-6 rounded-full border text-slate-700 transition ${
                copied
                  ? "border-emerald-200 bg-emerald-500 text-white"
                  : "border-slate-200 bg-white/70 hover:bg-white"
              }`}
              onClick={(event) => {
                event.preventDefault();
                event.stopPropagation();
                const copiedNow = onCopyRequest ? onCopyRequest(copyHref, href) : true;
                if (!onCopyRequest || copiedNow) {
                  if (!onCopyRequest) {
                    copyToClipboard(copyHref);
                  }
                  setCopied(true);
                  window.setTimeout(() => setCopied(false), 1200);
                }
              }}
            >
              <span className="sr-only">{copied ? "Copiado" : "Copiar URL"}</span>
              {copied ? (
                <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 mx-auto" aria-hidden="true">
                  <path
                    d="M5 12l4 4 10-10"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              ) : (
                <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 mx-auto" aria-hidden="true">
                  <path
                    d="M9 9a2 2 0 0 1 2-2h7a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-7a2 2 0 0 1-2-2V9zm-5 6V6a2 2 0 0 1 2-2h7"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.6"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              )}
            </button>
          )}
          {statusLabel && (
            <span
              className={`text-[10px] ${
                badgeTone === "whatsapp" ? "h-5 min-w-[20px] px-1 rounded-full leading-5 text-center" : "px-2 py-1 rounded-full"
              } ${badgeClasses}`}
            >
              {statusLabel}
            </span>
          )}
          {expandable && (
            <span
              className={`inline-flex h-5 w-5 items-center justify-center rounded-full border border-slate-200 bg-white/70 text-slate-600 transition ${
                expanded ? "rotate-180" : ""
              }`}
              aria-hidden="true"
            >
              <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.8">
                <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
          )}
        </span>
      )}
    </Link>
  );
}
