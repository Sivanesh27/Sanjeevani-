let csrf = "";
export const setCsrf = (t) => { csrf = t || ""; };

export class ApiError extends Error {
  constructor(status, detail) { super(typeof detail === "string" ? detail : "Request failed"); this.status = status; this.detail = detail; }
}

function message(detail) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => `${(d.loc || []).filter((x) => x !== "body").join(" › ")}: ${d.msg}`).join("; ");
  return "Something went wrong. Please try again.";
}

async function request(method, path, body) {
  const headers = {};
  const isForm = typeof FormData !== "undefined" && body instanceof FormData;
  if (body && !isForm) headers["Content-Type"] = "application/json";
  if (method !== "GET") headers["X-CSRF-Token"] = csrf;
  let res;
  try {
    res = await fetch(`/api${path}`, { method, headers, credentials: "include", body: body ? (isForm ? body : JSON.stringify(body)) : undefined });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Check your connection and try again.");
  }
  let data = null;
  try { data = await res.json(); } catch { /* empty body */ }
  if (!res.ok) {
    const detail = data?.detail ?? "Request failed";
    if (res.status === 401 && !path.startsWith("/auth/login") && !path.startsWith("/auth/face") && path !== "/auth/me") window.dispatchEvent(new Event("sj:unauthorized"));
    const e = new ApiError(res.status, detail); e.message = message(detail); e.code = typeof detail === "string" ? detail : null; throw e;
  }
  return data;
}

export const api = {
  get: (p) => request("GET", p),
  post: (p, b) => request("POST", p, b ?? {}),
  put: (p, b) => request("PUT", p, b ?? {}),
  patch: (p, b) => request("PATCH", p, b ?? {}),
  del: (p, b) => request("DELETE", p, b),
  upload: (p, file) => { const f = new FormData(); f.append("file", file); return request("POST", p, f); },
};
