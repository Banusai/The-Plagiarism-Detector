const API_BASE = "http://127.0.0.1:8000";
const token = sessionStorage.getItem("referenceAdminToken");
const form = document.getElementById("upload-form");
const fileInput = document.getElementById("reference-files");
const selectedFiles = document.getElementById("selected-files");
const uploadMessage = document.getElementById("upload-message");
const listError = document.getElementById("list-error");
const documentsBody = document.getElementById("documents-body");

if (!token) window.location.replace("./admin-login.html");

function authHeaders(extra = {}) {
  return { ...extra, Authorization: `Bearer ${token}` };
}

function escapeText(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
}

function showMessage(element, message, isError = false) {
  element.textContent = message;
  element.className = `notice ${isError ? "error" : "success"}`;
}

async function handleUnauthorized(response) {
  if (response.status === 401) {
    sessionStorage.removeItem("referenceAdminToken");
    window.location.replace("./admin-login.html");
    return true;
  }
  return false;
}

async function loadDocuments() {
  listError.classList.add("hidden");
  try {
    const response = await fetch(`${API_BASE}/api/references`, {
      headers: authHeaders(),
    });
    if (await handleUnauthorized(response)) return;
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Could not load references.");

    const docs = data.documents || [];
    document.getElementById("document-count").textContent = docs.length;
    document.getElementById("chunk-count").textContent =
      docs.reduce((total, doc) => total + Number(doc.chunks_added || 0), 0);

    documentsBody.replaceChildren();
    if (!docs.length) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 4;
      cell.textContent = "No administrator-uploaded reference documents yet.";
      row.appendChild(cell);
      documentsBody.appendChild(row);
      return;
    }

    docs.forEach((doc) => {
      const row = document.createElement("tr");
      [doc.filename, doc.format, doc.status, new Date(doc.created_at).toLocaleString()]
        .forEach((value) => {
          const cell = document.createElement("td");
          cell.textContent = value || "—";
          row.appendChild(cell);
        });
      documentsBody.appendChild(row);
    });
  } catch (error) {
    showMessage(listError, error.message, true);
  }
}

fileInput.addEventListener("change", () => {
  const files = Array.from(fileInput.files || []);
  selectedFiles.textContent = files.length
    ? `${files.length} file(s): ${files.map((file) => file.name).join(", ")}`
    : "No files selected.";
  if (files.length > 5) showMessage(uploadMessage, "Select no more than 5 files per batch.", true);
  else uploadMessage.classList.add("hidden");
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  uploadMessage.classList.add("hidden");
  const files = Array.from(fileInput.files || []);
  if (files.length < 1 || files.length > 5) {
    showMessage(uploadMessage, "Select between 1 and 5 files per upload.", true);
    return;
  }
  if (files.some((file) => file.size > 5 * 1024 * 1024)) {
    showMessage(uploadMessage, "Each file must be 5 MB or smaller.", true);
    return;
  }

  const payload = new FormData();
  files.forEach((file) => payload.append("files", file));
  const button = document.getElementById("upload-btn");
  button.disabled = true;
  button.textContent = "Processing and indexing…";

  try {
    const response = await fetch(`${API_BASE}/api/references/upload`, {
      method: "POST",
      headers: authHeaders(),
      body: payload,
    });
    if (await handleUnauthorized(response)) return;
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Upload failed.");
    showMessage(
      uploadMessage,
      `${data.message} Added ${data.index.new_chunks} chunks to the search index.`
    );
    form.reset();
    selectedFiles.textContent = "No files selected.";
    await loadDocuments();
  } catch (error) {
    showMessage(uploadMessage, error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = "Upload and index";
  }
});

document.getElementById("refresh-btn").addEventListener("click", loadDocuments);
document.getElementById("logout-btn").addEventListener("click", () => {
  sessionStorage.removeItem("referenceAdminToken");
  window.location.replace("./admin-login.html");
});

loadDocuments();
