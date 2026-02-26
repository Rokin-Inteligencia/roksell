import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.API_URL ?? "http://127.0.0.1:8000";

async function handle(req: NextRequest) {
  const token = req.cookies.get("admin_token")?.value;
  if (!token) {
    return NextResponse.json({ detail: "Missing credentials" }, { status: 401 });
  }

  const tenant = req.cookies.get("tenant_slug")?.value ?? process.env.NEXT_PUBLIC_TENANT_SLUG;
  const base = API_BASE.replace(/\/$/, "");
  const upstreamPath = req.nextUrl.pathname.replace(/^\/api\/admin/, "");
  const url = `${base}${upstreamPath}${req.nextUrl.search}`;

  const headers = new Headers();
  headers.set("Authorization", `Bearer ${token}`);
  if (tenant) headers.set("X-Tenant", tenant);

  const contentType = req.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);

  const method = req.method.toUpperCase();
  const init: RequestInit = { method, headers };
  if (!["GET", "HEAD"].includes(method)) {
    const body = await req.arrayBuffer();
    if (body.byteLength > 0) init.body = body;
  }

  const upstream = await fetch(url, init);
  const responseHeaders = new Headers();
  const upstreamContentType = upstream.headers.get("content-type");
  if (upstreamContentType) {
    responseHeaders.set("Content-Type", upstreamContentType);
  }

  const noBodyStatus = upstream.status === 204 || upstream.status === 205 || upstream.status === 304;
  const noBodyMethod = method === "HEAD";
  if (noBodyStatus || noBodyMethod) {
    return new NextResponse(null, { status: upstream.status, headers: responseHeaders });
  }

  const raw = await upstream.text();
  return new NextResponse(raw, { status: upstream.status, headers: responseHeaders });
}

export const GET = handle;
export const POST = handle;
export const PATCH = handle;
export const PUT = handle;
export const DELETE = handle;
