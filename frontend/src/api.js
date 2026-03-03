const API_BASE = "/api";

async function request(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  return res;
}

export async function getHealth() {
  const res = await request("/health");
  const json = await res.json();
  return { ok: res.ok, data: json };
}

export async function getRuns(page = 1, pageSize = 20) {
  const res = await request(`/runs?page=${page}&page_size=${pageSize}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.message || "获取 Runs 失败");
  }
  return res.json();
}

export async function getRun(runId) {
  const res = await request(`/runs/${runId}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.message || "获取 Run 失败");
  }
  return res.json();
}

export async function downloadReport(dt) {
  const url = `${API_BASE}/reports/daily/download?dt=${encodeURIComponent(dt)}`;
  const res = await fetch(url);
  if (!res.ok) {
    const json = await res.json().catch(() => ({}));
    throw new Error(json.message || "Report not found");
  }
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition");
  let filename = `daily_report_${dt}.xlsx`;
  if (disposition) {
    const m = disposition.match(/filename[^;=\n]*=([^;\n]*)/);
    if (m) filename = m[1].trim().replace(/^["']|["']$/g, "");
  }
  const a = document.createElement("a");
  const blobUrl = URL.createObjectURL(blob);
  a.href = blobUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(blobUrl), 100);
}

// M1 授权中心 API
export async function authSessionStart() {
  const res = await request("/auth/session/start", { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.message || "创建会话失败");
  }
  return res.json();
}

export async function authSessionFinish(sessionId, token) {
  const res = await request("/auth/session/finish", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, token: token || null }),
  });
  return res.json();
}

export async function authCredentialStatus() {
  const res = await request("/auth/credential/status");
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.message || "获取凭证状态失败");
  }
  return res.json();
}
