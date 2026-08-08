Api.requireAuth();

const user = Api.currentUser();
document.getElementById("userName").textContent = user ? `${user.name} (${user.role})` : "";
document.getElementById("welcomeName").textContent = user ? user.name.split(" ")[0] : "";
document.getElementById("zThreshold").value = user ? user.z_threshold : 1.0;

async function loadDatasets() {
  const listEl = document.getElementById("datasetsList");
  try {
    const { datasets } = await Api.get("/api/datasets");
    if (!datasets.length) {
      listEl.innerHTML = `<div class="empty-state">No datasets yet — upload your first CSV or Excel file to get started.</div>`;
      return;
    }
    listEl.innerHTML = datasets
      .map(
        (d) => `
      <div class="dataset-row">
        <div>
          <div class="name">${escapeHtml(d.name)}</div>
          <div class="meta">${d.row_count} rows &middot; ${d.source} &middot; ${new Date(d.created_at).toLocaleDateString()}${d.owner_name ? ` &middot; ${escapeHtml(d.owner_name)}` : ""}</div>
        </div>
        <div class="actions">
          <a href="report.html?dataset=${d.id}"><button class="secondary">View report</button></a>
          <button class="secondary" onclick="deleteDataset('${d.id}')">Delete</button>
        </div>
      </div>`
      )
      .join("");
  } catch (err) {
    listEl.innerHTML = `<div class="empty-state">Could not load datasets: ${escapeHtml(err.message)}</div>`;
  }
}

async function deleteDataset(id) {
  if (!confirm("Delete this dataset? This cannot be undone.")) return;
  try {
    await Api.del(`/api/datasets/${id}`);
    loadDatasets();
  } catch (err) {
    alert(err.message);
  }
}

async function saveThreshold() {
  const value = parseFloat(document.getElementById("zThreshold").value);
  try {
    const { user: updated } = await Api.patch("/api/auth/settings", { z_threshold: value });
    Api.setSession(Api.token(), updated);
    alert("Sensitivity saved.");
  } catch (err) {
    alert(err.message);
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

loadDatasets();
