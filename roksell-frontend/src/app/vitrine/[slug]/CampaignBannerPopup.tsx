"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import type { CampaignBanner } from "@/types";

type CampaignBannerPopupProps = {
  banners: CampaignBanner[];
  tenant: string;
};

function storageKey(tenant: string, bannerId: string) {
  return `vitrine-banner-popup-${tenant}-${bannerId}`;
}

export function CampaignBannerPopup({ banners, tenant }: CampaignBannerPopupProps) {
  const [queue, setQueue] = useState<CampaignBanner[]>([]);
  const [droplet, setDroplet] = useState(false);
  const nextTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!banners.length) return;
    const popupBanners = banners.filter((b) => b.banner_popup && b.banner_image_url);
    if (!popupBanners.length) return;
    const unseen: CampaignBanner[] = [];
    for (const banner of popupBanners) {
      if (!localStorage.getItem(storageKey(tenant, banner.id))) {
        unseen.push(banner);
      }
    }
    if (unseen.length > 0) {
      setQueue(unseen);
      setDroplet(true);
    }
    return () => {
      if (nextTimeoutRef.current) clearTimeout(nextTimeoutRef.current);
    };
  }, [banners, tenant]);

  const activeBanner = queue[0] ?? null;

  const closeCurrent = useCallback(() => {
    if (!activeBanner) return;
    localStorage.setItem(storageKey(tenant, activeBanner.id), "1");
    if (queue.length <= 1) {
      setQueue([]);
      setDroplet(false);
    } else {
      setDroplet(false);
      if (nextTimeoutRef.current) clearTimeout(nextTimeoutRef.current);
      nextTimeoutRef.current = setTimeout(() => {
        nextTimeoutRef.current = null;
        setQueue((q) => q.slice(1));
        setDroplet(true);
      }, 220);
    }
  }, [tenant, activeBanner, queue.length]);

  if (!activeBanner?.banner_image_url) return null;

  const bannerLabel = activeBanner.name?.trim() || "Campanha";

  const bannerContent = (
    <div className="relative overflow-hidden rounded-3xl border border-white/70 bg-white shadow-2xl">
      <img
        src={activeBanner.banner_image_url}
        alt={bannerLabel}
        className="w-full h-60 sm:h-72 object-cover"
      />
      <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/20 to-transparent" />
      <div className="absolute bottom-4 left-4 right-4 text-white">
        <p className="text-[10px] uppercase tracking-[0.3em] text-white/70">Campanha</p>
        <p className="text-base font-semibold">{bannerLabel}</p>
      </div>
      <button
        type="button"
        onClick={closeCurrent}
        className="absolute top-3 right-3 rounded-full bg-white/90 px-3 py-1 text-xs font-semibold text-slate-900 shadow"
      >
        Fechar
      </button>
    </div>
  );

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/55 px-4 py-6">
      <div
        key={activeBanner.id}
        className={`w-full max-w-lg transition-all duration-300 ease-out ${
          droplet
            ? "animate-banner-droplet opacity-100"
            : "opacity-0 translate-y-[-24px] scale-95"
        }`}
      >
        {activeBanner.banner_link_url ? (
          <a
            href={activeBanner.banner_link_url}
            target="_blank"
            rel="noreferrer"
            aria-label={`Abrir ${bannerLabel}`}
            className="block"
            onClick={() => closeCurrent()}
          >
            {bannerContent}
          </a>
        ) : (
          bannerContent
        )}
      </div>
    </div>
  );
}
