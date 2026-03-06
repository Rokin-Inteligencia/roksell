"use client";

import { useState, useEffect, useCallback } from "react";
import type { CampaignBanner } from "@/types";

const ROTATE_INTERVAL_MS = 6000;

type BannerCarouselProps = {
  banners: CampaignBanner[];
  variant?: "top" | "between";
};

function BannerCardInner({ banner, variant }: { banner: CampaignBanner; variant: "top" | "between" }) {
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

export function BannerCarousel({ banners, variant = "top" }: BannerCarouselProps) {
  const [index, setIndex] = useState(0);

  const next = useCallback(() => {
    setIndex((i) => (i + 1) % banners.length);
  }, [banners.length]);

  useEffect(() => {
    if (banners.length <= 1) return;
    const id = setInterval(next, ROTATE_INTERVAL_MS);
    return () => clearInterval(id);
  }, [banners.length, next]);

  if (!banners.length) return null;
  if (banners.length === 1) {
    return <BannerCardInner banner={banners[0]} variant={variant} />;
  }

  return (
    <div className="relative">
      <div className="overflow-hidden rounded-3xl">
        {banners.map((banner, i) => (
          <div
            key={banner.id}
            className={`transition-opacity duration-500 ${
              i === index ? "opacity-100 block" : "opacity-0 hidden"
            }`}
            aria-hidden={i !== index}
          >
            <BannerCardInner banner={banner} variant={variant} />
          </div>
        ))}
      </div>
      <div className="flex justify-center gap-1.5 mt-2" aria-label="Slides do carrossel">
        {banners.map((banner, i) => (
          <button
            key={banner.id}
            type="button"
            onClick={() => setIndex(i)}
            className={`h-2 rounded-full transition-all ${
              i === index ? "w-6 bg-[#6320ee]" : "w-2 bg-slate-300 hover:bg-slate-400"
            }`}
            aria-label={`Ir para banner ${i + 1}`}
            aria-current={i === index ? "true" : undefined}
          />
        ))}
      </div>
    </div>
  );
}
