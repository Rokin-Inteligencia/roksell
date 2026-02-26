export const dynamic = "force-dynamic";

import { api } from "@/lib/api";
import { notFound } from "next/navigation";
/*  */import { Catalog, CampaignBanner, OperatingHoursDay, Product, Store } from "@/types";
import ProductCard from "../../ProductCard";
import CartIcon from "../../CartIcon";
import UserLoginButton from "@/components/UserLoginButton";
import VitrineAdminShortcut from "@/components/VitrineAdminShortcut";
import { CampaignBannerPopup } from "./CampaignBannerPopup";
import { OperatingHoursBadge } from "./OperatingHoursBadge";
import type { CSSProperties } from "react";

type PageProps = {
  params: Promise<{ slug: string }>;
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

async function getCatalog(tenant: string, store?: string) {
  const query = store ? `?store=${encodeURIComponent(store)}` : "";
  return api<Catalog>(`/catalog${query}`, {
    headers: {
      "X-Tenant": tenant,
    },
    cache: "no-store",
  });
}

async function getStores(tenant: string) {
  return api<Store[]>("/stores", {
    headers: {
      "X-Tenant": tenant,
    },
    cache: "no-store",
  });
}

function normalizeStoreKey(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "");
}

function categoryIdOf(product: Product): string | null {
  return product.category_id ?? null;
}

function prettyName(slug: string) {
  return slug
    .split("-")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function buildWhatsappLink(value?: string | null): string | null {
  if (!value) return null;
  const digits = value.replace(/\D/g, "");
  if (!digits) return null;
  return `https://wa.me/${digits}`;
}

const DEFAULT_STORE_TIMEZONE = "America/Sao_Paulo";

function resolveStoreTimezone(value?: string | null): string {
  return (value || "").trim() || DEFAULT_STORE_TIMEZONE;
}

function nowPartsInTimezone(timeZone: string): { isoDate: string; weekday: number; minutes: number } {
  const now = new Date();
  try {
    const dateParts = new Intl.DateTimeFormat("en-CA", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).formatToParts(now);
    const year = dateParts.find((part) => part.type === "year")?.value ?? "1970";
    const month = dateParts.find((part) => part.type === "month")?.value ?? "01";
    const day = dateParts.find((part) => part.type === "day")?.value ?? "01";

    const weekdayLabel = new Intl.DateTimeFormat("en-US", { timeZone, weekday: "short" }).format(now);
    const weekdayMap: Record<string, number> = {
      Mon: 0,
      Tue: 1,
      Wed: 2,
      Thu: 3,
      Fri: 4,
      Sat: 5,
      Sun: 6,
    };
    const weekday = weekdayMap[weekdayLabel] ?? 0;

    const timeParts = new Intl.DateTimeFormat("en-GB", {
      timeZone,
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).formatToParts(now);
    const hour = Number(timeParts.find((part) => part.type === "hour")?.value ?? "0");
    const minute = Number(timeParts.find((part) => part.type === "minute")?.value ?? "0");
    const minutes = hour * 60 + minute;
    return { isoDate: `${year}-${month}-${day}`, weekday, minutes };
  } catch {
    const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
    return {
      isoDate: local.toISOString().slice(0, 10),
      weekday: (now.getDay() + 6) % 7,
      minutes: now.getHours() * 60 + now.getMinutes(),
    };
  }
}

function isOpenNow(hours: OperatingHoursDay[], timeZone: string): boolean {
  if (!hours || hours.length === 0) return true;
  const now = nowPartsInTimezone(timeZone);
  const weekday = now.weekday;
  const entry = hours.find((item) => item.day === weekday);
  if (!entry || !entry.enabled || !entry.open || !entry.close) return false;
  const [openHour, openMinute] = entry.open.split(":").map((value) => Number(value));
  const [closeHour, closeMinute] = entry.close.split(":").map((value) => Number(value));
  if (!Number.isFinite(openHour) || !Number.isFinite(closeHour)) return false;
  const openMinutes = openHour * 60 + (openMinute || 0);
  const closeMinutes = closeHour * 60 + (closeMinute || 0);
  return openMinutes <= now.minutes && now.minutes < closeMinutes;
}

function getSearchParam(
  searchParams: Record<string, string | string[] | undefined> | undefined,
  key: string
): string {
  if (!searchParams) return "";
  const value = searchParams[key];
  if (Array.isArray(value)) return value[0] ?? "";
  return value ?? "";
}

type BannerCardProps = {
  banner: CampaignBanner;
  variant?: "top" | "between";
};

function BannerCard({ banner, variant = "top" }: BannerCardProps) {
  if (!banner.banner_image_url) return null;
  const bannerLabel = banner.name?.trim() || "Campanha";
  const heightClass = variant === "between" ? "h-36 sm:h-44 lg:h-60" : "h-40 sm:h-48 lg:h-72";
  const content = (
    <div className="group relative overflow-hidden rounded-3xl border border-white/70 bg-white/85 shadow-xl shadow-[#6320ee]/10">
      <img
        src={banner.banner_image_url}
        alt={bannerLabel}
        className={`w-full ${heightClass} object-cover`}
        loading="lazy"
      />
      <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/10 to-transparent opacity-90" />
      <div className="absolute bottom-3 left-4 right-4 text-white space-y-1">
        <p className="text-[10px] uppercase tracking-[0.3em] text-white/70">Campanha</p>
        <p className="text-sm sm:text-base font-semibold">{bannerLabel}</p>
      </div>
    </div>
  );
  if (!banner.banner_link_url) return content;
  return (
    <a
      href={banner.banner_link_url}
      target="_blank"
      rel="noreferrer"
      aria-label={`Abrir ${bannerLabel}`}
      className="block"
    >
      {content}
    </a>
  );
}

export default async function VitrinePage({ params, searchParams }: PageProps) {
  const { slug } = await params;
  const resolvedSearchParams = searchParams ? await searchParams : undefined;
  const tenant = slug;
  if (!tenant) {
    notFound();
  }
  const stores = await getStores(tenant);
  const storeParam =
    getSearchParam(resolvedSearchParams, "store") ||
    getSearchParam(resolvedSearchParams, "store_id");
  if (!storeParam) {
    notFound();
  }
  const data = await getCatalog(tenant, storeParam || undefined);
  const selectedStore =
    stores.find((store) => store.id === data.selected_store_id) ||
    stores.find((store) => store.slug === data.selected_store_slug) ||
    stores.find((store) => store.id === storeParam) ||
    stores.find((store) => store.slug === storeParam) ||
    stores.find((store) => normalizeStoreKey(store.name) === normalizeStoreKey(storeParam)) ||
    null;
  if (!selectedStore) {
    notFound();
  }
  const closedDates = (selectedStore?.closed_dates || []).filter(Boolean);
  const operatingHours = (selectedStore?.operating_hours || []).filter(Boolean) as OperatingHoursDay[];
  const storeTimezone = resolveStoreTimezone(selectedStore?.timezone);
  const todayIso = nowPartsInTimezone(storeTimezone).isoDate;
  const isAllowedToday = closedDates.length === 0 || closedDates.includes(todayIso);
  const isOpenTodayByHours = isOpenNow(operatingHours, storeTimezone);

  const sections = data.categories.map((category) => ({
    category,
    products: data.products.filter((product) => categoryIdOf(product) === category.id),
  }));

  const uncategorized = data.products.filter(
    (product) => !data.categories.some((category) => category.id === categoryIdOf(product))
  );
  const visibleSections = sections.filter(({ products }) => products.length > 0);
  const banners = data.campaign_banners ?? [];
  const topBanners = banners.filter((banner) => banner.banner_position !== "between" && banner.banner_image_url);
  const betweenBanners = banners.filter((banner) => banner.banner_position === "between" && banner.banner_image_url);
  const extraBetweenBanners = betweenBanners.slice(visibleSections.length);
  const coverImageUrl = data.cover_image_url ?? null;
  const isOpen = isAllowedToday && isOpenTodayByHours;
  const slaMinutes = data.sla_minutes ?? null;
  const deliveryEnabled = data.delivery_enabled ?? null;
  const contactUrl =
    buildWhatsappLink(data.whatsapp_contact_phone) ?? process.env.NEXT_PUBLIC_CONTACT_URL ?? null;
  const themeStyle = {
    "--rokin-primary": "#6320ee",
    "--rokin-accent": "#c4b5ff",
    "--rokin-soft": "#ede7ff",
  } as CSSProperties;

  return (
    <main
      className="min-h-screen bg-[radial-gradient(circle_at_top,#f6f2ff_0%,#f7f4ff_40%,#fcfbff_100%)] text-slate-900 font-sans"
      style={themeStyle}
    >
      <div className="relative">
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute -top-40 right-[-15%] h-[420px] w-[420px] rounded-full bg-[#6320ee]/15 blur-3xl" />
          <div className="absolute -bottom-40 left-[-10%] h-[380px] w-[380px] rounded-full bg-[#c4b5ff]/20 blur-3xl" />
        </div>

        <div className="relative max-w-6xl mx-auto w-full px-4 sm:px-6 lg:px-8 pb-10">
          {coverImageUrl && (
            <section className="relative -mx-4 sm:-mx-6 lg:-mx-8 h-40 sm:h-56 lg:h-64 overflow-hidden">
              <img
                src={coverImageUrl}
                alt={`Capa da vitrine ${prettyName(tenant)}`}
                className="absolute inset-0 w-full h-full object-cover"
                loading="lazy"
              />
              <div className="absolute inset-0 bg-gradient-to-b from-black/45 via-black/20 to-transparent" />
            </section>
          )}

          <header
            className={`sticky top-0 z-20 -mx-4 sm:-mx-6 lg:-mx-8 ${
              coverImageUrl ? "-mt-8 sm:-mt-12 lg:-mt-16" : "mt-6"
            } px-4 sm:px-6 lg:px-8 pt-4 pb-3`}
          >
            <div className="relative rounded-3xl bg-white/85 backdrop-blur border border-white/70 shadow-xl shadow-[#6320ee]/10 px-4 sm:px-6 py-3">
              <div className="flex items-center justify-between gap-3">
                <div className="shrink-0 flex items-center gap-2 z-10">
                  <UserLoginButton />
                  <VitrineAdminShortcut />
                </div>
                <div className="shrink-0 z-10">
                  <CartIcon />
                </div>
              </div>
              <h1 className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 max-w-[62vw] truncate text-xl sm:text-2xl md:text-3xl font-semibold tracking-[0.08em] text-slate-900 text-center">
                {prettyName(tenant)}
              </h1>
              <div className="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-1/2">
                <OperatingHoursBadge
                  isOpen={isOpen}
                  hours={operatingHours}
                  deliveryMinutes={slaMinutes}
                  deliveryEnabled={deliveryEnabled}
                  allowPreorderWhenClosed={selectedStore.allow_preorder_when_closed !== false}
                />
              </div>
            </div>
          </header>

          <div className={`space-y-8 ${coverImageUrl ? "mt-12 sm:mt-20 lg:mt-24" : "mt-6"}`}>
            <CampaignBannerPopup banners={banners} tenant={tenant} />

            {topBanners.length > 0 && (
              <section className="space-y-3">
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
                  {topBanners.map((banner) => (
                    <BannerCard key={banner.id} banner={banner} variant="top" />
                  ))}
                </div>
              </section>
            )}

            {visibleSections.length > 1 && (
              <nav className="flex items-center gap-2 overflow-x-auto pb-1">
                {visibleSections.map(({ category }) => (
                  <a
                    key={category.id}
                    href={`#cat-${category.id}`}
                    className="px-3 py-1 rounded-full border border-[#6320ee]/20 bg-white/70 text-xs text-slate-700 whitespace-nowrap hover:border-[#6320ee]/50"
                  >
                    {category.name}
                  </a>
                ))}
                {uncategorized.length > 0 && (
                  <a
                    href="#cat-outros"
                    className="px-3 py-1 rounded-full border border-[#6320ee]/20 bg-white/70 text-xs text-slate-700 whitespace-nowrap hover:border-[#6320ee]/50"
                  >
                    Outros
                  </a>
                )}
              </nav>
            )}

            <div className="space-y-10">
              {visibleSections.map(({ category, products }, index) => (
                <div key={category.id} className="space-y-6">
                  <section
                    id={`cat-${category.id}`}
                    className="scroll-mt-28 sm:scroll-mt-32 lg:scroll-mt-36 rounded-[28px] bg-white/85 backdrop-blur border border-white/70 shadow-xl shadow-[#6320ee]/10 p-4 sm:p-6 space-y-4"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <h2 className="text-lg sm:text-xl font-semibold text-slate-900">{category.name}</h2>
                      <span className="text-[10px] uppercase tracking-[0.3em] text-[var(--rokin-primary)] bg-[var(--rokin-soft)] px-3 py-1 rounded-full">
                        {products.length} itens
                      </span>
                    </div>
                    <ul className="grid gap-3 sm:gap-4 sm:grid-cols-2 lg:grid-cols-3">
                      {products
                        .sort((a, b) => (a.display_order ?? 0) - (b.display_order ?? 0))
                        .map((product) => (
                          <ProductCard
                            key={product.id}
                            product={product}
                            additionals={data.additionals}
                            contactUrl={contactUrl}
                          />
                        ))}
                    </ul>
                  </section>
                  {betweenBanners[index] && <BannerCard banner={betweenBanners[index]} variant="between" />}
                </div>
              ))}

              {extraBetweenBanners.length > 0 && (
                <div className="grid gap-3 sm:grid-cols-2">
                  {extraBetweenBanners.map((banner) => (
                    <BannerCard key={banner.id} banner={banner} variant="between" />
                  ))}
                </div>
              )}

              {uncategorized.length > 0 && (
                <section
                  id="cat-outros"
                  className="scroll-mt-28 sm:scroll-mt-32 lg:scroll-mt-36 rounded-[28px] bg-white/85 backdrop-blur border border-white/70 shadow-xl shadow-[#6320ee]/10 p-4 sm:p-6 space-y-4"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <h2 className="text-lg sm:text-xl font-semibold text-slate-900">Outros</h2>
                    <span className="text-[10px] uppercase tracking-[0.3em] text-[var(--rokin-primary)] bg-[var(--rokin-soft)] px-3 py-1 rounded-full">
                      {uncategorized.length} itens
                    </span>
                  </div>
                  <ul className="grid gap-3 sm:gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {uncategorized.map((product) => (
                      <ProductCard
                        key={product.id}
                        product={product}
                        additionals={data.additionals}
                        contactUrl={contactUrl}
                      />
                    ))}
                  </ul>
                </section>
              )}
            </div>
          </div>
        </div>

        {contactUrl && (
          <a
            href={contactUrl}
            target="_blank"
            rel="noreferrer"
            aria-label="Falar no WhatsApp"
            className="fixed bottom-5 right-5 z-40 inline-flex items-center justify-center rounded-full bg-[#25d366] p-3 text-white shadow-xl shadow-[#25d366]/30 transition hover:brightness-95 active:scale-95"
          >
            <svg
              viewBox="0 0 24 24"
              aria-hidden="true"
              className="h-6 w-6"
              fill="currentColor"
            >
              <path d="M20.52 3.48A11.87 11.87 0 0 0 12.04 0C5.44 0 .08 5.36.08 11.96c0 2.1.55 4.16 1.6 5.98L0 24l6.24-1.64a11.89 11.89 0 0 0 5.8 1.48h.01c6.6 0 11.96-5.36 11.96-11.96 0-3.19-1.24-6.18-3.49-8.4Zm-8.48 18.35h-.01a9.9 9.9 0 0 1-5.03-1.38l-.36-.22-3.7.97.99-3.6-.24-.37a9.96 9.96 0 0 1-1.53-5.27c0-5.51 4.48-9.99 9.99-9.99 2.67 0 5.17 1.04 7.05 2.93a9.9 9.9 0 0 1 2.92 7.05c0 5.51-4.48 9.99-9.99 9.99Zm5.48-7.49c-.3-.15-1.8-.89-2.07-.99-.28-.1-.49-.15-.69.15-.2.3-.79.99-.97 1.2-.18.2-.36.22-.66.07-.3-.15-1.28-.47-2.43-1.5-.89-.8-1.5-1.8-1.68-2.1-.18-.3-.02-.46.14-.6.14-.14.3-.36.45-.54.15-.18.2-.3.3-.5.1-.2.05-.37-.03-.52-.07-.15-.69-1.67-.94-2.29-.25-.6-.5-.52-.69-.53h-.59c-.2 0-.52.08-.79.37-.27.3-1.04 1.01-1.04 2.47 0 1.45 1.06 2.86 1.2 3.06.15.2 2.09 3.2 5.08 4.48.71.3 1.26.48 1.69.61.71.22 1.35.19 1.85.12.57-.08 1.8-.73 2.05-1.44.25-.71.25-1.31.17-1.44-.08-.12-.28-.2-.58-.35Z" />
            </svg>
          </a>
        )}
      </div>
    </main>
  );
}
