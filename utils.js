// ── API helpers ────────────────────────────────────────────────────────────────
const API = "/api";

async function apiFetch(path, options = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Toast ──────────────────────────────────────────────────────────────────────
function showToast(msg, type = "success") {
  let el = document.getElementById("toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "toast";
    el.className = "toast";
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.className = `toast ${type}`;
  requestAnimationFrame(() => {
    el.classList.add("show");
    clearTimeout(el._t);
    el._t = setTimeout(() => el.classList.remove("show"), 3000);
  });
}

// ── Nav active link ────────────────────────────────────────────────────────────
document.querySelectorAll(".nav-links a").forEach((a) => {
  if (a.href === location.href) a.classList.add("active");
});
