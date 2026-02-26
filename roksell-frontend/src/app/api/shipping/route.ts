import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

type ShippingItem = { product_id: string; quantity: number };
type ShippingAddress = {
  street: string;
  number: string;
  district: string;
  city: string;
  state: string;
  postal_code: string;
  complement?: string;
};
type ShippingGeo = { lat: number; lon: number };
type ShippingRequest = {
  postal_code: string;
  pickup?: boolean;
  items: ShippingItem[];
  address?: ShippingAddress;
  geo?: ShippingGeo;
  store_id?: string;
};
type ShippingError = { detail?: string; message?: string; [k: string]: unknown };

function isJsonContent(contentType: string | null): boolean {
  return !!contentType && contentType.toLowerCase().includes("application/json");
}
function errorMessageFromUnknown(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (typeof err === "string") return err;
  try {
    return JSON.stringify(err);
  } catch {
    return "Unknown error";
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = (await req.json()) as ShippingRequest;

    const payload: ShippingRequest = {
      postal_code: body.postal_code,
      pickup: typeof body.pickup === "boolean" ? body.pickup : false,
      items: body.items,
      address: body.address,
      geo: body.geo,
      store_id: body.store_id,
    };

    const apiBase = process.env.API_URL;
    const tenant = req.nextUrl.searchParams.get("tenant") || process.env.NEXT_PUBLIC_TENANT_SLUG;
    if (!apiBase) {
      return NextResponse.json<ShippingError>(
        { detail: "API_URL not defined" },
        { status: 500 },
      );
    }

    const url = `${apiBase.replace(/\/$/, "")}/shipping/quote`;
    const rid = req.headers.get("x-request-id") ?? `shipping-${Date.now()}`;

    const upstream = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Request-Id": rid,
        ...(tenant ? { "X-Tenant": tenant } : {}),
      },
      body: JSON.stringify(payload),
    });

    const contentType = upstream.headers.get("content-type");
    const raw = await upstream.text();

    return new NextResponse(raw, {
      status: upstream.status,
      headers: {
        "Content-Type": isJsonContent(contentType)
          ? "application/json"
          : "text/plain",
      },
    });
  } catch (e: unknown) {
    console.error("[PROXY/SHIPPING:ERR]", e);
    return NextResponse.json<ShippingError>(
      { detail: errorMessageFromUnknown(e) },
      { status: 500 },
    );
  }
}
