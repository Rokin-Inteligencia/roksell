import { NextRequest, NextResponse } from "next/server";

type ApiError = { detail?: string; message?: string };

function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (typeof err === "string") return err;
  try {
    return JSON.stringify(err);
  } catch {
    return "Unknown error";
  }
}

export async function GET(req: NextRequest) {
  const apiBase = process.env.API_URL;
  const tenant = req.nextUrl.searchParams.get("tenant") || process.env.NEXT_PUBLIC_TENANT_SLUG;
  if (!apiBase) {
    return NextResponse.json<ApiError>({ detail: "API_URL not defined" }, { status: 500 });
  }
  try {
    const url = `${apiBase.replace(/\/$/, "")}/stores`;
    const upstream = await fetch(url, {
      headers: {
        ...(tenant ? { "X-Tenant": tenant } : {}),
      },
      cache: "no-store",
    });
    const raw = await upstream.text();
    return new NextResponse(raw, {
      status: upstream.status,
      headers: {
        "Content-Type": upstream.headers.get("content-type") ?? "application/json",
      },
    });
  } catch (e) {
    return NextResponse.json<ApiError>({ detail: errorMessage(e) }, { status: 500 });
  }
}
