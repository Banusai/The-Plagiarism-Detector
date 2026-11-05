const API_BASE = "http://127.0.0.1:8000";
const form = document.getElementById("login-form");
const errorBox = document.getElementById("login-error");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorBox.classList.add("hidden");
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  button.textContent = "Signing in…";

  try {
    const response = await fetch(`${API_BASE}/api/admin/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: document.getElementById("username").value,
        password: document.getElementById("password").value,
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Login failed.");
    sessionStorage.setItem("referenceAdminToken", data.access_token);
    window.location.href = "./admin.html";
  } catch (error) {
    errorBox.textContent = error.message;
    errorBox.classList.remove("hidden");
  } finally {
    button.disabled = false;
    button.textContent = "Sign in";
  }
});
