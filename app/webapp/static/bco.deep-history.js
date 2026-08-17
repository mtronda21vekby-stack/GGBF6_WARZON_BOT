/* BLACK CROWN OPS v29 — Premium Deep History; server-authoritative entitlement only */
(() => {
  "use strict";
  if (window.__BCO_DEEP_HISTORY_V29_LOADED__) return;
  window.__BCO_DEEP_HISTORY_V29_LOADED__ = true;

  const API = "/webapp/api/operator-deep-history";
  const $ = (q, root = document) => root.querySelector(q);
  const safe = (fn, fallback) => { try { const v = fn(); return v === undefined ? fallback : v; } catch (_) { return fallback; } };

  function initData() {
    return String(safe(() => window.Telegram?.WebApp?.initData, "") || "").trim();
  }

  function mount() {
    const pane = $("#tab-operator-v25 .bco-op-shell");
    if (!pane || $("#bcoDeepHistoryV29")) return;
    const card = document.createElement("section");
    card.id = "bcoDeepHistoryV29";
    card.className = "bco-op-card";
    card.innerHTML = `
      <div class="bco-op-title"><span>PREMIUM DEEP HISTORY</span><small>SERVER ENTITLEMENT</small></div>
      <div id="bcoDeepHistoryStatus" class="bco-op-review">Checking server-authoritative bco_premium…</div>
      <div id="bcoDeepHistoryBody"></div>
      <button id="bcoDeepHistoryRefresh" class="bco-op-btn" type="button">REFRESH HISTORY</button>`;
    const status = $("#bcoOpStatus", pane);
    if (status) pane.insertBefore(card, status); else pane.appendChild(card);
    $("#bcoDeepHistoryRefresh")?.addEventListener("click", refresh);
    refresh();
  }

  function render(data) {
    const body = $("#bcoDeepHistoryBody");
    if (!body) return;
    const horizon = data?.horizon || {};
    const evidence = data?.evidence || {};
    const comparisons = Array.isArray(data?.focus_comparisons) ? data.focus_comparisons : [];
    body.innerHTML = "";

    const summary = document.createElement("div");
    summary.className = "bco-op-flow";
    summary.textContent = `HORIZON ${Number(horizon.observed_cycles || 0)}/${Number(horizon.max_cycles || 36)} CYCLES • VOD ${Number(evidence.vod_correlated_cycles || 0)} • CONTRADICTIONS ${Number(evidence.contradictions || 0)}`;
    body.appendChild(summary);

    comparisons.slice(0, 6).forEach((item) => {
      const row = document.createElement("article");
      row.className = "bco-op-dim neutral_observation";
      const focus = String(item.focus || "unknown").replaceAll("_", " ").toUpperCase();
      const direction = String(item.direction || "unknown").toUpperCase();
      row.innerHTML = `<div><strong></strong><small></small></div><div class="bco-op-dim-meta"></div><p></p>`;
      row.querySelector("strong").textContent = focus;
      row.querySelector("small").textContent = direction;
      row.querySelector(".bco-op-dim-meta").textContent = `${Number(item.cycles || 0)} CYCLES • CONF ${String(item.confidence || "unknown").toUpperCase()} • CONTRADICTIONS ${Number(item.contradictions || 0)}`;
      row.querySelector("p").textContent = "Association only — never a causal claim.";
      body.appendChild(row);
    });
  }

  async function refresh() {
    const status = $("#bcoDeepHistoryStatus");
    const init = initData();
    if (!init) {
      if (status) status.textContent = "Open from Telegram to resolve server entitlement.";
      return;
    }
    if (status) status.textContent = "Resolving bco_premium on server…";
    try {
      const response = await fetch(API, {
        method: "GET",
        headers: { "X-Telegram-Init-Data": init },
        cache: "no-store",
        credentials: "same-origin",
      });
      const payload = await response.json().catch(() => ({}));
      if (response.status === 403) {
        if (status) status.textContent = "PREMIUM DEEP HISTORY LOCKED // bco_premium required. Account linking alone does not unlock it.";
        const body = $("#bcoDeepHistoryBody"); if (body) body.innerHTML = "";
        return;
      }
      if (!response.ok || !payload?.ok || payload?.premium_authority !== "server_bco_premium") {
        throw new Error(payload?.detail || `Deep History HTTP ${response.status}`);
      }
      if (status) status.textContent = "PREMIUM ACTIVE // authority: server bco_premium // ASSOCIATION ≠ CAUSATION";
      render(payload.data || {});
    } catch (error) {
      if (status) status.textContent = error?.message || "Premium authority unavailable.";
    }
  }

  let attempts = 0;
  const timer = window.setInterval(() => {
    attempts += 1;
    if ($("#tab-operator-v25 .bco-op-shell")) {
      window.clearInterval(timer);
      mount();
    } else if (attempts > 30) {
      window.clearInterval(timer);
    }
  }, 150);

  window.BCO_DEEP_HISTORY = { refresh };
})();
