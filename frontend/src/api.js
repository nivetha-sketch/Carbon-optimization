const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

export async function getMeta() {
  const res = await fetch(`${API_BASE}/dashboard/meta`);
  if (!res.ok) throw new Error("Failed to load dashboard metadata");
  return res.json();
}

export async function getAnalytics(payload) {
  const res = await fetch(`${API_BASE}/dashboard/analytics`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to load analytics");
  return res.json();
}

export async function getExplainability(payload) {
  const res = await fetch(`${API_BASE}/dashboard/explain`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to load explainability");
  return res.json();
}

export async function runPipeline(step) {
  const res = await fetch(`${API_BASE}/pipeline/run/${step}`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to run pipeline");
  return res.json();
}

export async function runPipelineAll(mode = "demo") {
  const res = await fetch(`${API_BASE}/pipeline/run/all?mode=${encodeURIComponent(mode)}`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to run pipeline");
  return res.json();
}

export async function uploadWorkloadCsv(file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/pipeline/upload-workload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    let detail = "Failed to upload workload CSV";
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {
      // ignore json parse error
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function getAlertRules() {
  const res = await fetch(`${API_BASE}/alerts/rules`);
  if (!res.ok) throw new Error("Failed to load alert rules");
  return res.json();
}

export async function saveAlertRules(rules) {
  const res = await fetch(`${API_BASE}/alerts/rules`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rules }),
  });
  if (!res.ok) throw new Error("Failed to save alert rules");
  return res.json();
}

export async function evaluateAlerts() {
  const res = await fetch(`${API_BASE}/alerts/evaluate`);
  if (!res.ok) throw new Error("Failed to evaluate alerts");
  return res.json();
}
