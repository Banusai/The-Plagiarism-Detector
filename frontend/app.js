const form = document.getElementById("plagiarism-form");
const healthBtn = document.getElementById("health-btn");
const resetBtn = document.getElementById("reset-btn");

const backendUrlLabel = document.getElementById("backend-url");
const requestState = document.getElementById("request-state");
const healthStatus = document.getElementById("health-status");
const errorBox = document.getElementById("error-box");
const emptyState = document.getElementById("empty-state");
const resultContent = document.getElementById("result-content");
const matchesBody = document.getElementById("matches-body");
const rawOutput = document.getElementById("raw-output");

const resultMessage = document.getElementById("result-message");
const resultLength = document.getElementById("result-length");
const resultChunks = document.getElementById("result-chunks");
const resultDetected = document.getElementById("result-detected");

const fileInput = document.getElementById("file");
const fileName = document.getElementById("file-name");

const BASE_URL = "http://127.0.0.1:8000";

function setThemeToggle() {
  const button = document.querySelector("[data-theme-toggle]");
  const root = document.documentElement;

  let theme =
    root.getAttribute("data-theme") ||
    (window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light");

  root.setAttribute("data-theme", theme);

  if (!button) return;

  button.addEventListener("click", () => {
    theme = theme === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", theme);
  });
}

function setState(label, tone = "neutral") {
  if (!requestState) return;
  requestState.textContent = label;
  requestState.className = `pill ${tone}`;
}

function clearMessages() {
  if (healthStatus) {
    healthStatus.textContent = "";
    healthStatus.className = "notice hidden health-inline";
  }

  if (errorBox) {
    errorBox.textContent = "";
    errorBox.className = "notice error hidden";
  }
}

function showError(message) {
  if (!errorBox) return;
  errorBox.textContent = message;
  errorBox.className = "notice error";
  errorBox.classList.remove("hidden");
  setState("Error", "error");
}

function formatScore(score) {
  if (typeof score !== "number" || Number.isNaN(score)) return "—";
  return `${(score * 100).toFixed(2)}%`;
}

function safeText(value) {
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}

function createCell(value) {
  const td = document.createElement("td");
  td.textContent = safeText(value);
  return td;
}

function renderResults(data) {
  if (emptyState) emptyState.classList.add("hidden");
  if (resultContent) resultContent.classList.remove("hidden");

  if (resultMessage) resultMessage.textContent = safeText(data.message);
  if (resultLength)
    resultLength.textContent = safeText(data.input_text_length ?? 0);
  if (resultChunks)
    resultChunks.textContent = safeText(data.total_chunks ?? 0);

  if (resultDetected) {
    resultDetected.textContent = data.plagiarism_detected
      ? "Detected"
      : "Not detected";
  }

  if (matchesBody) {
    matchesBody.innerHTML = "";
    const matches = Array.isArray(data.matches)
      ? data.matches
      : [];

    if (matches.length === 0) {
      const row = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = 4;
      td.textContent = "No matches returned.";
      row.appendChild(td);
      matchesBody.appendChild(row);
    } else {
matches.forEach((match) => {
  const row = document.createElement("tr");

  row.appendChild(
    createCell(
      match.document_id
    )
  );

  row.appendChild(
    createCell(
      formatScore(
        match.similarity_score
      )
    )
  );

  const highlightedCell =
    document.createElement("td");

  // Render document-derived evidence as text, never as executable HTML.
  highlightedCell.textContent =
    match.matched_text ||
    match.highlighted_match ||
    "—";

  row.appendChild(
    highlightedCell
  );

  row.appendChild(
    createCell(
      match.input_chunk
    )
  );

  matchesBody.appendChild(row);
});
    }
  }

  if (rawOutput) {
    rawOutput.textContent = JSON.stringify(data, null, 2);
  }

  setState(
    data.plagiarism_detected
      ? "Match found"
      : "Completed",
    data.plagiarism_detected
      ? "warning"
      : "success"
  );
}

async function checkHealth() {
  clearMessages();

  if (backendUrlLabel) {
    backendUrlLabel.textContent = BASE_URL;
  }

  setState("Checking health", "neutral");

  try {
    const response = await fetch(
      `${BASE_URL}/api/health`
    );

    if (!response.ok) {
      throw new Error(
        `Health check failed with status ${response.status}`
      );
    }

    await response.json();

    if (healthStatus) {
      healthStatus.classList.add("hidden");
    }

    setState("API healthy", "success");
  } catch (error) {
    showError(
      error.message.includes("Failed to fetch")
        ? "Could not reach backend."
        : error.message
    );
  }
}

async function submitForm(event) {
  event.preventDefault();
  clearMessages();

  if (backendUrlLabel) {
    backendUrlLabel.textContent = BASE_URL;
  }

  setState("Submitting", "neutral");

  const formData = new FormData();

  const text =
    document.getElementById("text")?.value.trim() || "";
  const selectedFile = fileInput?.files[0] || null;

  if (text) {
    formData.append("text", text);
  }

  if (selectedFile) {
    formData.append("file", selectedFile);
  }

  if (!text && !selectedFile) {
    showError("Please provide text or choose a file.");
    return;
  }

  try {
    const response = await fetch(`${BASE_URL}/api/plagiarism/check`, {
      method: "POST",
      body: formData,
    });

    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json")
      ? await response.json()
      : await response.text();

    if (!response.ok) {
      const message =
        typeof data === "string"
          ? data
          : data.detail || `Request failed (${response.status})`;
      throw new Error(message);
    }

    renderResults(data);
  } catch (error) {
    showError(
      error.message.includes("Failed to fetch")
        ? "Backend unavailable."
        : error.message
    );
  }
}


function resetUI() {
  clearMessages();

  if (form) form.reset();
  if (resultContent)
    resultContent.classList.add("hidden");
  if (emptyState)
    emptyState.classList.remove("hidden");
  if (matchesBody) matchesBody.innerHTML = "";
  if (rawOutput) rawOutput.textContent = "";
  if (fileName)
    fileName.textContent = "No file selected";
  if (resultMessage)
    resultMessage.textContent = "—";
  if (resultLength)
    resultLength.textContent = "0";
  if (resultChunks)
    resultChunks.textContent = "0";
  if (resultDetected)
    resultDetected.textContent = "—";

  setState("Idle", "neutral");
}

setThemeToggle();

if (fileInput && fileName) {
  fileInput.addEventListener("change", () => {
    fileName.textContent =
      fileInput.files.length
        ? fileInput.files[0].name
        : "No file selected";
  });
}

if (healthBtn) {
  healthBtn.addEventListener("click", checkHealth);
}

if (form) {
  form.addEventListener("submit", submitForm);
}

if (resetBtn) {
  resetBtn.addEventListener("click", () => {
    setTimeout(resetUI, 0);
  });
}