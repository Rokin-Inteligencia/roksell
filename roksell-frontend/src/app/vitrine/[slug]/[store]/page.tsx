export const dynamic = "force-dynamic";

import VitrinePage from "../page";

type PageProps = {
  params: Promise<{ slug: string; store: string }>;
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function VitrineByStorePage({ params, searchParams }: PageProps) {
  const resolvedParams = await params;
  const resolvedSearchParams = (searchParams ? await searchParams : {}) || {};
  return VitrinePage({
    params: Promise.resolve({ slug: resolvedParams.slug }),
    searchParams: Promise.resolve({
      ...resolvedSearchParams,
      store: resolvedParams.store,
    }),
  });
}
