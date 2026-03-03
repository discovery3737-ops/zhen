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
<<<<<<< HEAD
=======

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

// M2 配置 API
export async function getGlobalConfig() {
  const res = await request("/config/global");
  if (!res.ok) throw new Error("获取全局配置失败");
  return res.json();
}

export async function putGlobalConfig(data) {
  const res = await request("/config/global", { method: "PUT", body: JSON.stringify(data) });
  if (!res.ok) throw new Error("保存失败");
  return res.json();
}

export async function getDatasetsConfig() {
  const res = await request("/datasets/config");
  if (!res.ok) throw new Error("获取数据源配置失败");
  return res.json();
}

export async function putDatasetsConfig(items) {
  const res = await request("/datasets/config", { method: "PUT", body: JSON.stringify({ items }) });
  if (!res.ok) throw new Error("保存失败");
  return res.json();
}

export async function getScheduleDaily() {
  const res = await request("/schedule/daily");
  if (!res.ok) throw new Error("获取调度配置失败");
  return res.json();
}

export async function putScheduleDaily(data) {
  const res = await request("/schedule/daily", { method: "PUT", body: JSON.stringify(data) });
  if (!res.ok) throw new Error("保存失败");
  return res.json();
}

export async function getDelivery() {
  const res = await request("/delivery");
  if (!res.ok) throw new Error("获取发送配置失败");
  return res.json();
}

export async function putDelivery(data) {
  const res = await request("/delivery", { method: "PUT", body: JSON.stringify(data) });
  if (!res.ok) throw new Error("保存失败");
  return res.json();
}

export async function runDailyJob(dt) {
  const res = await request(`/jobs/daily/run?dt=${encodeURIComponent(dt)}`, { method: "POST" });
  if (!res.ok) throw new Error("触发任务失败");
  return res.json();
}
>>>>>>> edfd4a2 (M2: config in DB + web-configurable settings)
