"use client";

import { useEffect, useState } from "react";
import type { CampaignBanner } from "@/types";

type CampaignBannerPopupProps = {
  banners: CampaignBanner[];
  tenant: string;
};

export function CampaignBannerPopup({ banners, tenant }: CampaignBannerPopupProps) {
  const [activeBanner, setActiveBanner] = useState<CampaignBanner | null>(null);

  useEffect(() => {
    if (!banners.length) return;
    const popupBanners = banners.filter((banner) => banner.banner_popup && banner.banner_image_url);
    if (!popupBanners.length) return;

    for (const banner of popupBanners) {
      const key = `vitrine-banner-popup-${tenant}-${banner.id}`;
      if (!localStorage.getItem(key)) {
        setActiveBanner(banner);
        return;
      }
    }
  }, [banners, tenant]);

  if (!activeBanner?.banner_image_url) return null;

  const bannerLabel = activeBanner.name?.trim() || "Campanha";
  const storageKey = `vitrine-banner-popup-${tenant}-${activeBanner.id}`;

  function closePopup() {
    localStorage.setItem(storageKey, "1");
    setActiveBanner(null);
  }

  function handleBannerClick() {
    localStorage.setItem(storageKey, "1");
    setActiveBanner(null);
  }

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
        onClick={closePopup}
        className="absolute top-3 right-3 rounded-full bg-white/90 px-3 py-1 text-xs font-semibold text-slate-900 shadow"
      >
        Fechar
      </button>
    </div>
  );

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/55 px-4 py-6">
      {activeBanner.banner_link_url ? (
        <a
          href={activeBanner.banner_link_url}
          target="_blank"
          rel="noreferrer"
          aria-label={`Abrir ${bannerLabel}`}
          className="block w-full max-w-lg"
          onClick={handleBannerClick}
        >
          {bannerContent}
        </a>
      ) : (
        <div className="w-full max-w-lg">{bannerContent}</div>
      )}
    </div>
  );
}
