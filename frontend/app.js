const API_BASE = (() => {
  const el = document.currentScript;
  return el && el.dataset.apiBase ? el.dataset.apiBase : "http://localhost:8000";
})();
const CSRF_HEADER = "X-DeploySmith";
const $ = (id) => document.getElementById(id);

function logEvent(text, kind = "") {
  const events = $("events");
  const div = document.createElement("div");
  div.className = "line" + (kind ? " " + kind : "");
  div.textContent = text;
  events.appendChild(div);
  events.scrollTop = events.scrollHeight;
}

function setStatus(text, kind) {
  const el = $("api-status");
  el.textContent = text;
  el.style.color = kind === "ok" ? "#166534" : kind === "err" ? "#991b1b" : "#4b5563";
}

async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/api/health`);
    if (res.ok) {
      setStatus("API reachable - " + (await res.json()).status, "ok");
    } else {
      setStatus("API returned " + res.status, "err");
    }
  } catch (e) {
    setStatus("API unreachable: " + e.message, "err");
  }
}

async function loadApps() {
  try {
    const res = await fetch(`${API_BASE}/api/apps`);
    const apps = await res.json();
    const list = $("apps-list");
    list.innerHTML = "";
    if (!apps || apps.length === 0) {
      list.innerHTML = "<div>No apps yet.</div>";
      return;
    }
    for (const app of apps) {
      const item = document.createElement("div");
      item.className = "app-item";
      item.innerHTML = `
        <strong>${escapeHtml(app.name || "app")}</strong>
        <span class="small-btn">engine: ${app.engine_enabled ? "on" : "off"}</span>
        <div style="margin-top:4px;font-size:0.8rem;color:#4b5563;">${escapeHtml(String(app.repo_url || "-"))}</div>
      `;
      list.appendChild(item);
    }
  } catch (e) {
    $("apps-list").innerHTML = "<div class='err'>Failed to load apps: " + escapeHtml(e.message) + "</div>";
  }
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

async function startDeployment(repoUrl) {
  const result = $("deploy-result");
  result.className = "hidden";
  result.textContent = "";

  try {
    const res = await fetch(`${API_BASE}/api/deployments`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        [CSRF_HEADER]: "1",
      },
      body: JSON.stringify({ repo_url: repoUrl }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Deployment failed (" + res.status + ")");
    }

    const data = await res.json();
    result.className = "ok";
    result.textContent = `Deployment started: id=${data.id} repo=${escapeHtml(data.repo_url)}`;
    logEvent(`Run ${data.id} started for ${escapeHtml(data.repo_url)}`);
    streamEvents(data.id);
  } catch (e) {
    result.className = "err";
    result.textContent = e.message;
  }
}

async function streamEvents(runId) {
  logEvent(`Opening event stream for run ${runId}&hellip;`);
  try {
    const res = await fetch(`${API_BASE}/api/deployments/${runId}/events`);
    if (!res.ok || !res.body) {
      throw new Error("Could not open event stream (" + (res.status || "no body") + ")");
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const payload = JSON.parse(line.slice(6));
            const kind = payload.status || payload.log ? "" : "";
            logEvent(`[${payload.status || "log"}] ${payload.log || JSON.stringify(payload)}`, kind);
          } catch (_) {
            logEvent(line.slice(6));
          }
        } else if (line === "event: done") {
          logEvent("Stream complete.", "done");
          return;
        } else if (line === "event: error") {
          logEvent("Stream error.", "error");
          return;
        }
      }
    }
  } catch (e) {
    logEvent("Stream error: " + escapeHtml(e.message), "error");
  }
}

$("btn-health").addEventListener("click", checkHealth);
$("btn-apps").addEventListener("click", loadApps);

$("deploy-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const url = $("repo-url").value.trim();
  if (!url) return;
  startDeployment(url);
});

checkHealth();
loadApps();
