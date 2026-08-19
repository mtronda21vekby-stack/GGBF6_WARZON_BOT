/* BLACK CROWN OPS v45 — unified trusted CROWN SESSION bootstrap */
(() => {
  "use strict";
  if (window.__BCO_CROWN_SESSION_V45_LOADED__) return;
  window.__BCO_CROWN_SESSION_V45_LOADED__ = true;

  const API = "/webapp/api/crown-session";
  let latest = null;
  let pending = null;
  let lastError = "";

  function initData() {
    try { return String(window.Telegram?.WebApp?.initData || "").trim(); }
    catch (_) { return ""; }
  }

  async function fetchSession() {
    const init = initData();
    if (!init) throw new Error("trusted_telegram_context_required");
    const response = await fetch(API, {
      method: "GET",
      headers: { "X-Telegram-Init-Data": init, accept: "application/json" },
      cache: "no-store",
      credentials: "same-origin",
    });
    const payload = await response.json().catch(() => null);
    if (!response.ok || !payload?.ok || !payload?.data) {
      throw new Error(payload?.detail || `crown_session_http_${response.status}`);
    }
    latest = payload.data;
    lastError = "";
    try { window.dispatchEvent(new CustomEvent("bco:crown-session", { detail: latest })); } catch (_) {}
    return latest;
  }

  function refresh(force = false) {
    if (!force && latest) return Promise.resolve(latest);
    if (pending) return pending;
    pending = fetchSession()
      .catch((error) => {
        lastError = String(error?.message || "crown_session_unavailable");
        throw error;
      })
      .finally(() => { pending = null; });
    return pending;
  }

  function operatorSnapshot() {
    const data = latest?.operator_twin;
    return data && typeof data === "object" ? data : null;
  }

  window.BCO_CROWN_SESSION = {
    refresh,
    getSnapshot: () => latest,
    getOperatorSnapshot: operatorSnapshot,
    getError: () => lastError,
  };

  // Bootstrap immediately when opened inside Telegram. Failure is non-fatal:
  // legacy Mini App surfaces remain usable and may retry explicitly.
  refresh(false).catch((error) => console.warn("[BCO v45] CROWN SESSION bootstrap unavailable", error));
})();
