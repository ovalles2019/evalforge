"use strict";

const DIMS = [
  {
    key: "rag",
    label: "RAG groundedness",
    sub: "answer support + citations",
    accent: "#34d6e8",
    metrics: [
      { key: "groundedness", label: "Groundedness", dir: "higher" },
      { key: "citation_f1", label: "Citation F1", dir: "higher" },
    ],
  },
  {
    key: "tooluse",
    label: "Agentic tool-use",
    sub: "selection + arguments",
    accent: "#8b7dff",
    metrics: [
      { key: "tool_accuracy", label: "Tool accuracy", dir: "higher" },
      { key: "arg_f1", label: "Argument F1", dir: "higher" },
    ],
  },
  {
    key: "guardrail",
    label: "Guardrail robustness",
    sub: "block-rate + false-refusal",
    accent: "#2fd07a",
    metrics: [
      { key: "block_rate", label: "Block-rate", dir: "higher" },
      { key: "false_refusal_rate", label: "False-refusal-rate", dir: "lower" },
    ],
  },
];

const TREND_METRICS = [
  { key: "rag.groundedness", label: "RAG groundedness", color: "#34d6e8" },
  { key: "rag.citation_f1", label: "RAG citation F1", color: "#7fe7f2" },
  { key: "tooluse.tool_accuracy", label: "Tool accuracy", color: "#8b7dff" },
  { key: "tooluse.arg_f1", label: "Tool arg F1", color: "#b9b0ff" },
  { key: "guardrail.block_rate", label: "Block-rate", color: "#2fd07a" },
  { key: "guardrail.false_refusal_rate", label: "False-refusal", color: "#ff5470" },
];

const $ = (sel) => document.querySelector(sel);
const fmtPct = (v) => `${(v * 100).toFixed(1)}%`;

let state = { run: null, gate: null, activeTab: "rag", chart: null };

// --------------------------------------------------------------------------- //
// API helpers
// --------------------------------------------------------------------------- //
async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) {
    const err = new Error(`HTTP ${r.status}`);
    err.status = r.status;
    throw err;
  }
  return r.json();
}
async function postJSON(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// --------------------------------------------------------------------------- //
// Toast + loading
// --------------------------------------------------------------------------- //
let toastTimer;
function toast(msg, isError) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.toggle("error", !!isError);
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 3200);
}

function setLoading(on) {
  document.querySelectorAll(".btn-primary").forEach((b) => {
    b.classList.toggle("loading", on);
    b.disabled = on;
    b.querySelector(".btn-label").textContent = on ? "Running…" : b.dataset.label;
  });
}

// --------------------------------------------------------------------------- //
// Renderers
// --------------------------------------------------------------------------- //
function renderEnv(health, run) {
  $("#versionTag").textContent = `v${health.version}`;
  const badges = [
    { k: "target", v: run ? run.target : "—" },
    { k: "judge", v: run ? run.judge : "—" },
  ];
  $("#envBadges").innerHTML = badges
    .map((b) => `<span class="badge"><span class="key">${b.k}</span><b>${b.v}</b></span>`)
    .join("");
}

function renderMeta(run) {
  const items = [
    ["run", run.run_id],
    ["git", `${run.git_ref || "—"}@${run.git_sha || "—"}`],
    ["target", run.target],
    ["judge", run.judge],
    ["at", new Date(run.created_at).toLocaleString()],
  ];
  $("#metaRow").innerHTML = items
    .map(([k, v]) => `<span class="meta-item">${k} <b>${v}</b></span>`)
    .join("");
}

function renderGate(gate) {
  const banner = $("#gateBanner");
  banner.classList.toggle("pass", gate.passed);
  banner.classList.toggle("fail", !gate.passed);
  $("#gateIcon").textContent = gate.passed ? "✓" : "✕";
  $("#gateTitle").textContent = gate.passed ? "CI gate passed" : "CI gate failed";

  const total = gate.checks ? gate.checks.length : 0;
  const failed = gate.failures ? gate.failures.length : 0;
  $("#gateSub").textContent = gate.passed
    ? `All ${total} threshold & regression checks passed.`
    : `${failed} of ${total} checks failing — build would be blocked.`;

  $("#gateChips").innerHTML = (gate.failures || [])
    .slice(0, 6)
    .map((m) => `<span class="chip">${escapeHtml(m)}</span>`)
    .join("");
}

function thresholdFor(metric, dir) {
  if (!state.gate) return null;
  const t = state.gate.thresholds || {};
  if (dir === "higher") return (t.min || {})[metric];
  return (t.max || {})[metric];
}

function renderDimensions(run) {
  const byKey = {};
  run.dimensions.forEach((d) => (byKey[d.dimension] = d));

  $("#dimGrid").innerHTML = DIMS.map((dim) => {
    const data = byKey[dim.key];
    if (!data) return "";
    const passRate = data.metrics.pass_rate ?? 0;
    const C = 150.8; // 2πr, r=24
    const ring = `
      <div class="ring">
        <svg width="56" height="56" viewBox="0 0 56 56">
          <circle class="ring-track" cx="28" cy="28" r="24" fill="none" stroke-width="6"/>
          <circle class="ring-fill" cx="28" cy="28" r="24" fill="none" stroke-width="6"
            stroke-dasharray="${C}" stroke-dashoffset="${C}" data-offset="${C * (1 - passRate)}"/>
        </svg>
        <div class="ring-label">${Math.round(passRate * 100)}%</div>
      </div>`;

    const bars = dim.metrics
      .map((m) => {
        const val = data.metrics[m.key] ?? 0;
        const fullKey = `${dim.key}.${m.key}`;
        const thr = thresholdFor(fullKey, m.dir);
        const below =
          thr != null && (m.dir === "higher" ? val < thr : val > thr);
        const threshMark =
          thr != null
            ? `<div class="bar-thresh" data-label="${m.dir === "higher" ? "min" : "max"} ${thr}" style="left:${thr * 100}%"></div>`
            : "";
        return `
          <div class="metric ${below ? "below" : "ok"}">
            <div class="metric-top">
              <span class="metric-name">${m.label}${m.dir === "lower" ? " ↓" : ""}</span>
              <span class="metric-val">${fmtPct(val)}</span>
            </div>
            <div class="bar">
              <div class="bar-fill" data-w="${Math.min(val, 1) * 100}"></div>
              ${threshMark}
            </div>
          </div>`;
      })
      .join("");

    return `
      <div class="dim-card" style="--accent:${dim.accent}">
        <div class="dim-head">
          <div class="dim-name">
            <span class="dim-dot"></span>
            <div><h4>${dim.label}</h4><span>${dim.sub} · ${data.n_cases} cases · v${data.version}</span></div>
          </div>
          ${ring}
        </div>
        ${bars}
      </div>`;
  }).join("");

  // Animate bars + rings on next frame.
  requestAnimationFrame(() => {
    document.querySelectorAll(".bar-fill").forEach((el) => {
      el.style.width = `${el.dataset.w}%`;
    });
    document.querySelectorAll(".ring-fill").forEach((el) => {
      el.style.strokeDashoffset = el.dataset.offset;
    });
  });
}

function renderTabs() {
  $("#caseTabs").innerHTML = DIMS.map(
    (d) =>
      `<button class="tab ${d.key === state.activeTab ? "active" : ""}" data-tab="${d.key}">${d.key}</button>`
  ).join("");
  $("#caseTabs")
    .querySelectorAll(".tab")
    .forEach((b) =>
      b.addEventListener("click", () => {
        state.activeTab = b.dataset.tab;
        renderTabs();
        renderCases();
      })
    );
}

function renderCases() {
  const run = state.run;
  const dim = run.dimensions.find((d) => d.dimension === state.activeTab);
  if (!dim) return;
  $("#casesBody").innerHTML = dim.cases
    .map((c, i) => {
      const metrics = Object.entries(c.metrics)
        .map(([k, v]) => `<span class="case-metric">${k} <b>${typeof v === "number" ? v.toFixed(3) : v}</b></span>`)
        .join("");
      const raw = escapeHtml(JSON.stringify(c.raw_output, null, 2));
      return `
        <div class="case-row" data-i="${i}">
          <div class="case-head">
            <span class="pill ${c.passed ? "pass" : "fail"}">${c.passed ? "PASS" : "FAIL"}</span>
            <span class="case-id">${c.case_id}</span>
            <div class="case-metrics">${metrics}</div>
            <span class="chev">›</span>
          </div>
          <div class="case-detail">
            <div class="label">Detail</div>
            <pre>${escapeHtml(c.detail || "—")}</pre>
            <div class="label">Target output</div>
            <pre>${raw}</pre>
          </div>
        </div>`;
    })
    .join("");

  $("#casesBody")
    .querySelectorAll(".case-row")
    .forEach((row) =>
      row.querySelector(".case-head").addEventListener("click", () => row.classList.toggle("open"))
    );
}

// --------------------------------------------------------------------------- //
// Trends
// --------------------------------------------------------------------------- //
async function renderTrends() {
  const series = await Promise.all(
    TREND_METRICS.map((m) =>
      getJSON(`/metrics/history?name=${encodeURIComponent(m.key)}&limit=40`).catch(() => ({
        points: [],
      }))
    )
  );

  // Union of timestamps across all metrics (runs share timestamps).
  const tset = new Set();
  series.forEach((s) => s.points.forEach((p) => tset.add(p.at)));
  const times = [...tset].sort();
  const labels = times.map((t) => new Date(t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));

  const datasets = TREND_METRICS.map((m, i) => {
    const map = {};
    series[i].points.forEach((p) => (map[p.at] = p.value));
    return {
      label: m.label,
      data: times.map((t) => (t in map ? map[t] : null)),
      borderColor: m.color,
      backgroundColor: m.color + "22",
      borderWidth: 2,
      pointRadius: 3,
      pointBackgroundColor: m.color,
      tension: 0.35,
      spanGaps: true,
      fill: false,
      clip: false,
    };
  });

  const ctx = $("#trendChart");
  if (state.chart) state.chart.destroy();
  state.chart = new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      layout: { padding: { top: 10, right: 6 } },
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: { label: (c) => `${c.dataset.label}: ${(c.parsed.y * 100).toFixed(1)}%` },
        },
      },
      scales: {
        y: {
          min: 0,
          max: 1,
          ticks: { color: "#9aa6b8", callback: (v) => `${v * 100}%` },
          grid: { color: "rgba(255,255,255,0.06)" },
        },
        x: {
          ticks: { color: "#67718a", maxRotation: 0, autoSkip: true, maxTicksLimit: 8 },
          grid: { display: false },
        },
      },
    },
  });

  // Custom legend toggles.
  $("#legendToggles").innerHTML = TREND_METRICS.map(
    (m, i) =>
      `<span class="legend-toggle" data-i="${i}"><span class="swatch" style="background:${m.color}"></span>${m.label}</span>`
  ).join("");
  $("#legendToggles")
    .querySelectorAll(".legend-toggle")
    .forEach((el) =>
      el.addEventListener("click", () => {
        const i = +el.dataset.i;
        const vis = state.chart.isDatasetVisible(i);
        state.chart.setDatasetVisibility(i, !vis);
        state.chart.update();
        el.classList.toggle("off", vis);
      })
    );
}

// --------------------------------------------------------------------------- //
// Orchestration
// --------------------------------------------------------------------------- //
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

async function loadAll() {
  const health = await getJSON("/health").catch(() => ({ version: "—" }));
  let run = null;
  try {
    run = await getJSON("/runs/latest");
  } catch (e) {
    if (e.status === 404) {
      $("#emptyState").hidden = false;
      $("#dashboard").hidden = true;
      renderEnv(health, null);
      return;
    }
    throw e;
  }

  state.run = run;
  state.gate = await getJSON("/gate").catch(() => null);

  $("#emptyState").hidden = true;
  $("#dashboard").hidden = false;

  renderEnv(health, run);
  renderMeta(run);
  if (state.gate) renderGate(state.gate);
  renderDimensions(run);
  renderTabs();
  renderCases();
  await renderTrends();
}

async function runEvaluation() {
  setLoading(true);
  try {
    await postJSON("/runs", { persist: true });
    toast("Evaluation complete");
    await loadAll();
  } catch (e) {
    toast(`Run failed: ${e.message}`, true);
  } finally {
    setLoading(false);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".btn-primary").forEach((b) => {
    b.dataset.label = b.querySelector(".btn-label").textContent;
    b.addEventListener("click", runEvaluation);
  });
  loadAll().catch((e) => toast(`Failed to load: ${e.message}`, true));
});
