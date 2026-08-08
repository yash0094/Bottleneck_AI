Api.requireAuth();
const user = Api.currentUser();
document.getElementById("userName").textContent = user ? `${user.name} (${user.role})` : "";

const params = new URLSearchParams(window.location.search);
const datasetId = params.get("dataset");
const shouldRunFirst = params.get("run") === "1";

if (!datasetId) {
  document.getElementById("content").innerHTML = `<div class="card"><p>No dataset specified.</p></div>`;
} else {
  init();
}

async function init() {
  setStatus("Loading...");
  try {
    if (shouldRunFirst) {
      await runAnalysis(true);
    } else {
      const { result } = await Api.get(`/api/analysis/${datasetId}/latest`);
      render(result);
      setStatus("");
    }
  } catch (err) {
    // No analysis yet — run one automatically.
    try {
      await runAnalysis(true);
    } catch (e2) {
      setStatus("");
      document.getElementById("content").innerHTML = `<div class="card"><p>${escapeHtml(e2.message)}</p></div>`;
    }
  }
}

async function runAnalysis(silent) {
  if (!silent) setStatus("Running analysis...");
  document.getElementById("runBtn").disabled = true;
  try {
    const { result } = await Api.post(`/api/analysis/${datasetId}/run`, {});
    render(result);
    setStatus("");
  } finally {
    document.getElementById("runBtn").disabled = false;
  }
}

function setStatus(text) {
  document.getElementById("statusLine").textContent = text;
}

function render(result) {
  document.getElementById("datasetTitle").textContent = "Bottleneck Report";

  const stats = [
    ["ITEMS", result.totalItems],
    ["STAGES", result.totalStages],
    ["BOTTLENECKS", result.bottleneckStages.length],
    ["STUCK ITEMS", result.stuckItemCount],
  ];

  const statsHtml = `
    <div class="card">
      <h2>Executive Summary</h2>
      <p>${escapeHtml(result.summaryText)}</p>
      <div class="grid-4">
        ${stats.map(([label, num]) => `<div class="stat-box"><div class="num">${num}</div><div class="label">${label}</div></div>`).join("")}
      </div>
    </div>`;

  const stagesHtml = `
    <div class="card">
      <h2>Stage-by-Stage Breakdown</h2>
      ${result.stageReports
        .map((s, i) => {
          const badgeClass = s.isBottleneck ? "danger" : "ok";
          const badgeText = s.isBottleneck ? "BOTTLENECK" : "Healthy";
          return `
        <div class="stage-card">
          <div class="head">
            <strong>${i + 1}. ${escapeHtml(s.stage)}</strong>
            <span class="badge ${badgeClass}">${badgeText}</span>
          </div>
          <div class="stats-line">
            Avg: ${fmtSeconds(s.mean)} &middot; Median: ${fmtSeconds(s.median)} &middot;
            Std Dev: ${fmtSeconds(s.stddev)} &middot; Items: ${s.count} &middot;
            Outliers: ${s.outlierCount} &middot; Z-score: ${s.zScore.toFixed(2)}
          </div>
          <div class="cause"><strong>Cause:</strong> ${escapeHtml(s.cause)} — ${escapeHtml(s.explanation)}</div>
          <div class="rec"><strong>Recommendation:</strong> ${escapeHtml(s.recommendation)}</div>
        </div>`;
        })
        .join("")}
    </div>`;

  const stuckHtml = result.stuckItems.length
    ? `
    <div class="card">
      <h2>Stuck Items (Top Outliers)</h2>
      <p class="muted">Items whose stage duration exceeded the statistical outlier ceiling (Q3 + 1.5×IQR) for that stage.</p>
      <table class="stuck-table">
        <thead><tr><th>Item ID</th><th>Stage</th><th>Duration</th><th>Expected Max</th><th>Exceeded By</th></tr></thead>
        <tbody>
          ${result.stuckItems
            .slice(0, 30)
            .map(
              (it) => `<tr>
              <td>${escapeHtml(it.item_id)}</td>
              <td>${escapeHtml(it.stage)}</td>
              <td>${fmtSeconds(it.duration_seconds)}</td>
              <td>${fmtSeconds(it.expected_ceiling_seconds)}</td>
              <td>${fmtSeconds(it.exceeded_by_seconds)}</td>
            </tr>`
            )
            .join("")}
        </tbody>
      </table>
    </div>`
    : "";

  document.getElementById("content").innerHTML = statsHtml + stagesHtml + stuckHtml;
}

async function downloadPdf() {
  const btn = document.getElementById("pdfBtn");
  btn.disabled = true;
  btn.textContent = "Preparing...";
  try {
    const res = await Api.get(`/api/report/${datasetId}/pdf`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "FlowLens_Report.pdf";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (err) {
    alert(err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Download PDF";
  }
}

function logout() {
  Api.clearSession();
  window.location.href = "index.html";
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}
