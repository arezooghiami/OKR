// API client: runtime-configurable base URL, Bearer token, single-flight refresh.
// Token storage goes through the TokenStorage interface so a mobile shell can swap in secure storage.

export interface TokenStorage {
  get(): { access: string; refresh: string } | null;
  set(t: { access: string; refresh: string } | null): void;
}

export const webTokenStorage: TokenStorage = {
  get() {
    try {
      const raw = localStorage.getItem("okr.tokens");
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  },
  set(t) {
    try {
      if (t) localStorage.setItem("okr.tokens", JSON.stringify(t));
      else localStorage.removeItem("okr.tokens");
    } catch {
      /* storage unavailable: session lasts until reload */
    }
  },
};

declare global {
  interface Window {
    __OKR_CONFIG__?: { apiBase: string };
  }
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

let storage: TokenStorage = webTokenStorage;
let onUnauthorized: () => void = () => {};
export const configureClient = (opts: { storage?: TokenStorage; onUnauthorized?: () => void }) => {
  if (opts.storage) storage = opts.storage;
  if (opts.onUnauthorized) onUnauthorized = opts.onUnauthorized;
};

const base = () => window.__OKR_CONFIG__?.apiBase ?? "/api/v1";

let refreshing: Promise<boolean> | null = null;
function refresh(): Promise<boolean> {
  refreshing ??= (async () => {
    const t = storage.get();
    if (!t) return false;
    const r = await fetch(`${base()}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: t.refresh }),
    });
    if (!r.ok) {
      storage.set(null);
      return false;
    }
    const j = await r.json();
    storage.set({ access: j.access_token, refresh: j.refresh_token });
    return true;
  })().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

async function detail(r: Response): Promise<string> {
  try {
    const j = await r.json();
    return typeof j.detail === "string" ? j.detail : "درخواست ناموفق بود";
  } catch {
    return "درخواست ناموفق بود";
  }
}

export async function api<T>(path: string, opts: { method?: string; body?: unknown } = {}, retry = true): Promise<T> {
  const t = storage.get();
  let r: Response;
  try {
    r = await fetch(`${base()}${path}`, {
      method: opts.method ?? "GET",
      headers: { ...(opts.body !== undefined ? { "Content-Type": "application/json" } : {}), ...(t ? { Authorization: `Bearer ${t.access}` } : {}) },
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    });
  } catch {
    throw new ApiError(0, "ارتباط با سرور برقرار نشد");
  }
  if (r.status === 401 && retry && t && (await refresh())) return api<T>(path, opts, false);
  if (r.status === 401 && !path.startsWith("/auth/")) onUnauthorized();
  if (!r.ok) throw new ApiError(r.status, await detail(r));
  return r.status === 204 ? (undefined as T) : r.json();
}

export async function login(username: string, password: string): Promise<void> {
  const r = await api<{ access_token: string; refresh_token: string }>("/auth/login", { method: "POST", body: { username, password } });
  storage.set({ access: r.access_token, refresh: r.refresh_token });
}

export async function logout(): Promise<void> {
  const t = storage.get();
  storage.set(null);
  if (t) await api("/auth/logout", { method: "POST", body: { refresh_token: t.refresh } }).catch(() => {});
}

export const hasSession = () => storage.get() !== null;

/** Authenticated file download (Authorization header, never a cookie URL). A mobile shell can replace the save step. */
export async function download(path: string): Promise<void> {
  const send = () => {
    const t = storage.get();
    return fetch(`${base()}${path}`, { headers: t ? { Authorization: `Bearer ${t.access}` } : {} });
  };
  let r: Response;
  try {
    r = await send();
    if (r.status === 401 && (await refresh())) r = await send();
  } catch {
    throw new ApiError(0, "ارتباط با سرور برقرار نشد");
  }
  if (!r.ok) throw new ApiError(r.status, await detail(r));
  const cd = r.headers.get("Content-Disposition") ?? "";
  const m = cd.match(/filename\*=UTF-8''([^;]+)/);
  const name = m ? decodeURIComponent(m[1]) : "export.xlsx";
  const url = URL.createObjectURL(await r.blob());
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

/** Authenticated multipart upload (the browser sets the multipart boundary itself). */
export async function upload<T>(path: string, form: FormData, retry = true): Promise<T> {
  const t = storage.get();
  let r: Response;
  try {
    r = await fetch(`${base()}${path}`, { method: "POST", headers: t ? { Authorization: `Bearer ${t.access}` } : {}, body: form });
  } catch {
    throw new ApiError(0, "ارتباط با سرور برقرار نشد");
  }
  if (r.status === 401 && retry && t && (await refresh())) return upload<T>(path, form, false);
  if (r.status === 401) onUnauthorized();
  if (!r.ok) throw new ApiError(r.status, await detail(r));
  return r.json();
}
