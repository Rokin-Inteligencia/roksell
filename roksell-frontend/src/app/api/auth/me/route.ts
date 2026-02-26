import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.API_URL ?? "http://127.0.0.1:8000";

export async function GET(req: NextRequest) {
  const tenant = req.cookies.get("tenant_slug")?.value ?? process.env.NEXT_PUBLIC_TENANT_SLUG;
  const token = req.cookies.get("admin_token")?.value;
  if (!token) {
    return NextResponse.json({ detail: "Missing credentials" }, { status: 401 });
  }
  try {
    const response = await fetch(`${API_BASE.replace(/\/$/, "")}/auth/me`, {
      method: "GET",
      headers: {
        ...(tenant ? { "X-Tenant": tenant } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      cache: "no-store",
      credentials: "include",
      signal: AbortSignal.timeout(8000),
    });
    const text = await response.text();
    const headers = new Headers({ "Content-Type": response.headers.get("content-type") ?? "application/json" });
    const setCookie = response.headers.get("set-cookie");
    if (setCookie) headers.append("Set-Cookie", setCookie);
    return new NextResponse(text, {
      status: response.status,
      headers,
    });
  } catch {
    return NextResponse.json({ detail: "Auth service unavailable" }, { status: 503 });
  }
}
