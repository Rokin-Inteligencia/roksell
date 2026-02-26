import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.API_URL ?? "http://127.0.0.1:8000";

function isSecureRequest(req: NextRequest): boolean {
  const forwarded = req.headers.get("x-forwarded-proto");
  if (forwarded) return forwarded.split(",")[0].trim() === "https";
  return req.nextUrl.protocol === "https:";
}

export async function POST(req: NextRequest) {
  const body = await req.json();
  const secure = isSecureRequest(req);
  const response = await fetch(`${API_BASE.replace(/\/$/, "")}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
    cache: "no-store",
    credentials: "include",
  });
  const text = await response.text();

  const headers = new Headers({ "Content-Type": response.headers.get("content-type") ?? "application/json" });
  const res = new NextResponse(text, { status: response.status, headers });

  // Para ambientes dev (domínios diferentes), reescrevemos o cookie no host atual
  try {
    const data = JSON.parse(text);
    const token = data?.access_token;
    const tenantSlug = data?.tenant_slug;
    const expiresInSecondsRaw = Number(data?.expires_in_seconds);
    const expiresInSeconds =
      Number.isFinite(expiresInSecondsRaw) && expiresInSecondsRaw > 0
        ? Math.floor(expiresInSecondsRaw)
        : 60 * 60 * 24;
    if (token) {
      res.cookies.set("admin_token", token, {
        httpOnly: true,
        sameSite: "lax",
        secure,
        path: "/",
        maxAge: expiresInSeconds,
      });
    }
    if (tenantSlug) {
      res.cookies.set("tenant_slug", tenantSlug, {
        httpOnly: false,
        sameSite: "lax",
        secure,
        path: "/",
        maxAge: expiresInSeconds,
      });
    }
  } catch {
    /* ignore parse errors */
  }

  return res;
}
