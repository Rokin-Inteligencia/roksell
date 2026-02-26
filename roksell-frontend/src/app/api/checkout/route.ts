import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.API_URL ?? "http://127.0.0.1:8000";

export async function POST(req: NextRequest) {
  const body = await req.json();
  const tenant = req.nextUrl.searchParams.get("tenant");
  const response = await fetch(`${API_BASE}/checkout`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(tenant ? { "X-Tenant": tenant } : {}),
    },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const text = await response.text();
  return new NextResponse(text, {
    status: response.status,
    headers: { "Content-Type": response.headers.get("content-type") ?? "application/json" },
  });
}
