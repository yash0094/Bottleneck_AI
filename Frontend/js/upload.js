Api.requireAuth();
const user = Api.currentUser();
document.getElementById("userName").textContent = user ? `${user.name} (${user.role})` : "";

let selectedFile = null;
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const errorBox = document.getElementById("errorBox");

fileInput.addEventListener("change", (e) => setFile(e.target.files[0]));

["dragenter", "dragover"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.add("drag");
  })
);
["dragleave", "drop"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.remove("drag");
  })
);
dropzone.addEventListener("drop", (e) => {
  if (e.dataTransfer.files.length) setFile(e.dataTransfer.files[0]);
});

function setFile(file) {
  if (!file) return;
  selectedFile = file;
  document.getElementById("dropzoneText").textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(0)} KB)`;
  document.getElementById("uploadBtn").disabled = false;
}

async function handleUpload() {
  if (!selectedFile) return;
  showError(errorBox, "");
  const btn = document.getElementById("uploadBtn");
  btn.disabled = true;
  btn.textContent = "Uploading...";

  const formData = new FormData();
  formData.append("file", selectedFile);
  formData.append("name", document.getElementById("datasetName").value.trim());

  try {
    const data = await Api.postForm("/api/upload", formData);
    window.location.href = `report.html?dataset=${data.dataset.id}&run=1`;
  } catch (err) {
    showError(errorBox, err.message);
    btn.disabled = false;
    btn.textContent = "Upload & continue";
  }
}

async function handleSheetImport() {
  const url = document.getElementById("sheetUrl").value.trim();
  if (!url) return;
  showError(errorBox, "");
  const btn = document.getElementById("sheetBtn");
  btn.disabled = true;
  btn.textContent = "Importing...";

  try {
    const data = await Api.post("/api/sheets/import", {
      spreadsheetUrl: url,
      name: document.getElementById("datasetName").value.trim() || null,
    });
    window.location.href = `report.html?dataset=${data.dataset.id}&run=1`;
  } catch (err) {
    showError(errorBox, err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Import sheet";
  }
}

function logout() {
  Api.clearSession();
  window.location.href = "index.html";
}
