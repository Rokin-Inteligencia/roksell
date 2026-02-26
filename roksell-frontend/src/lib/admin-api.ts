function buildProxyUrl(path: string): string {
  const cleaned = path.replace(/^\//, "");
  return `/api/admin/${cleaned}`;
}

function extractDetailMessage(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (!Array.isArray(detail) || detail.length === 0) return null;
  const first = detail[0];
  if (typeof first === "string") return first;
  if (!first || typeof first !== "object") return null;
  const msg = "msg" in first && typeof first.msg === "string" ? first.msg : null;
  const locRaw = "loc" in first ? first.loc : null;
  const loc = Array.isArray(locRaw)
    ? locRaw
        .filter((item): item is string | number => typeof item === "string" || typeof item === "number")
        .join(".")
    : null;
  if (!msg) return null;
  return loc ? `${loc}: ${msg}` : msg;
}

function parseErrorBody(raw: string): string | null {
  if (!raw.trim()) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed === "string" && parsed.trim()) return parsed;
    if (!parsed || typeof parsed !== "object") return null;
    const parsedObj = parsed as { detail?: unknown; message?: unknown; error?: unknown };
    const detailMsg = extractDetailMessage(parsedObj.detail);
    if (detailMsg) return detailMsg;
    if (typeof parsedObj.message === "string" && parsedObj.message.trim()) return parsedObj.message;
    if (typeof parsedObj.error === "string" && parsedObj.error.trim()) return parsedObj.error;
  } catch {
    return null;
  }
  return null;
}

async function readErrorMessage(res: Response): Promise<string> {
  const raw = await res.text().catch(() => "");
  const parsed = parseErrorBody(raw);
  if (parsed) return parsed;
  if (raw.trim()) return raw;
  return `Request failed (${res.status})`;
}

async function parseAdminResponse<T>(res: Response): Promise<T> {
  if (res.status === 204 || res.status === 205) {
    return undefined as T;
  }
  const raw = await res.text().catch(() => "");
  if (!raw.trim()) {
    return undefined as T;
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    try {
      return JSON.parse(raw) as T;
    } catch {
      // Fallback when backend sets JSON content-type but body is not valid JSON.
      return raw as T;
    }
  }
  return raw as T;
}

export async function adminFetch<T = unknown>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  const url = buildProxyUrl(path);
  const res = await fetch(url, {
    ...init,
    headers,
    cache: "no-store",
    credentials: "include",
  });
  if (!res.ok) {
    throw new Error(await readErrorMessage(res));
  }
  return parseAdminResponse<T>(res);
}

export async function adminUpload<T = unknown>(path: string, form: FormData, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string> | undefined),
  };
  const url = buildProxyUrl(path);
  const res = await fetch(url, {
    method: init?.method ?? "POST",
    ...init,
    headers,
    body: form,
    cache: "no-store",
    credentials: "include",
  });
  if (!res.ok) {
    throw new Error(await readErrorMessage(res));
  }
  return parseAdminResponse<T>(res);
}
