// If already logged in, skip straight to the dashboard.
if (Api.token()) {
  window.location.href = "dashboard.html";
}

function switchTab(tab) {
  const isLogin = tab === "login";
  document.getElementById("tabLogin").classList.toggle("active", isLogin);
  document.getElementById("tabSignup").classList.toggle("active", !isLogin);
  document.getElementById("loginForm").style.display = isLogin ? "block" : "none";
  document.getElementById("signupForm").style.display = isLogin ? "none" : "block";
  showError(document.getElementById("errorBox"), "");
}

async function handleLogin() {
  const errorBox = document.getElementById("errorBox");
  const btn = document.getElementById("loginBtn");
  const email = document.getElementById("loginEmail").value.trim();
  const password = document.getElementById("loginPassword").value;

  showError(errorBox, "");
  btn.disabled = true;
  btn.textContent = "Logging in...";
  try {
    const data = await Api.post("/api/auth/login", { email, password });
    Api.setSession(data.token, data.user);
    window.location.href = "dashboard.html";
  } catch (err) {
    showError(errorBox, err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Log in";
  }
}

async function handleSignup() {
  const errorBox = document.getElementById("errorBox");
  const btn = document.getElementById("signupBtn");
  const name = document.getElementById("signupName").value.trim();
  const email = document.getElementById("signupEmail").value.trim();
  const password = document.getElementById("signupPassword").value;

  showError(errorBox, "");
  btn.disabled = true;
  btn.textContent = "Creating account...";
  try {
    const data = await Api.post("/api/auth/register", { name, email, password });
    Api.setSession(data.token, data.user);
    window.location.href = "dashboard.html";
  } catch (err) {
    showError(errorBox, err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Create account";
  }
}
