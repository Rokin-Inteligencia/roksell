import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.API_URL ?? "http://127.0.0.1:8000";

function isSecureRequest(req: NextRequest): boolean {
  const forwarded = req.headers.get("x-forwarded-proto");
  if (forwarded) return forwarded.split(",")[0].trim() === "https";
  return req.nextUrl.protocol === "https:";
}

export async function POST(req: NextRequest) {
  const secure = isSecureRequest(req);
  const token = req.cookies.get("admin_token")?.value;
  const requestHeaders = new Headers();
  if (token) requestHeaders.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_BASE.replace(/\/$/, "")}/auth/logout`, {
    method: "POST",
    headers: requestHeaders,
    cache: "no-store",
    credentials: "include",
  });
  const text = await response.text();
  const headers = new Headers({ "Content-Type": response.headers.get("content-type") ?? "application/json" });
  const res = new NextResponse(text, { status: response.status, headers });
  // Clear cookies on the current host too.
  res.cookies.set("admin_token", "", { path: "/", maxAge: 0, httpOnly: true, secure, sameSite: "lax" });
  res.cookies.set("tenant_slug", "", { path: "/", maxAge: 0, secure, sameSite: "lax" });
  return res;
}
