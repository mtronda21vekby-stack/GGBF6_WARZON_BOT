/* BLACK CROWN OPS v31 — Premium Strategy Outcome Loop; association, not causation */
(() => {
  "use strict";
  if (window.__BCO_STRATEGY_V31_LOADED__) return;
  window.__BCO_STRATEGY_V31_LOADED__ = true;

  const API = "/webapp/api/operator-strategy";
  const $ = (q, root = document) => root.querySelector(q);
  const safe = (fn, fallback) => { try { const v = fn(); return v === undefined ? fallback : v; } catch (_) { return fallback; } };

  function initData() {
    return String(safe(() => window.Telegram?.WebApp?.initData, "") || "").trim();
  }

  function mount() {
    const pane = $("#tab-operator-v25 .bco-op-shell");
    if (!pane || $("#bcoStrategyV31")) return;
    const card = document.createElement("section");
    card.id = "bcoStrategyV31";
    card.className = "bco-op-card";
    card.innerHTML = `
      <div class="bco-op-title"><span>ADAPTIVE STRATEGY</span><small>PREMIUM / OUTCOME LOOP</small></div>
      <div id="bcoStrategyStatus" class="bco-op-review">Resolve strategy on demand.</div>
      <div id="bcoStrategyBody"></div>
      <button id="bcoStrategyRefresh" class="bco-op-btn" type="button">BUILD NEXT OBJECTIVE</button>`;
    const status = $("#bcoOpStatus", pane);
    if (status) pane.insertBefore(card, status); else pane.appendChild(card);
    $("#bcoStrategyRefresh")?.addEventListener("click", refresh);
  }

  function block(label, value) {
    const el = document.createElement("article");
    el.className = "bco-op-dim neutral_observation";
    const title = document.createElement("strong");
    title.textContent = label;
    const text = document.createElement("p");
    text.textContent = String(value || "—");
    el.append(title, text);
    return el;
  }

  function effectivenessText(effectiveness) {
    const latest = effectiveness?.latest;
    if (!latest) return "NO FOLLOW-UP WINDOW YET";
    const verdict = String(latest.verdict || "insufficient_followup").replaceAll("_", " ").toUpperCase();
    const outcomes = latest.outcomes || {};
    return `${verdict} • ${Number(latest.matched_cycles || 0)}/3 CYCLES • CLEAN ${Number(outcomes.clean || 0)} / MIXED ${Number(outcomes.mixed || 0)} / FAILED ${Number(outcomes.failed || 0)}`;
  }

  function render(data) {
    const body = $("#bcoStrategyBody");
    if (!body) return;
    body.innerHTML = "";
    body.append(
      block("FOCUS", String(data?.focus || "calibration").replaceAll("_", " ").toUpperCase()),
      block("OBJECTIVE", data?.objective),
      block("SUCCESS CONDITION", data?.success_condition),
      block("NEXT ADAPTATION", data?.next_adaptation),
      block("RATIONALE", data?.rationale),
      block("OUTCOME LOOP", effectivenessText(data?.effectiveness))
    );
    const meta = document.createElement("div");
    meta.className = "bco-op-flow";
    meta.textContent = `${String(data?.strategy_class || "calibration").toUpperCase()} • CONF ${String(data?.confidence || "unknown").toUpperCase()} • STRATEGY ${String(data?.strategy_id || "untracked").toUpperCase()} • ASSOCIATION ≠ CAUSATION • EFFECTIVENESS ≠ CAUSAL PROOF`;
    body.prepend(meta);
  }

  async function refresh() {
    const status = $("#bcoStrategyStatus");
    const init = initData();
    if (!init) {
      if (status) status.textContent = "Open from Telegram to resolve server-authoritative Premium.";
      return;
    }
    if (status) status.textContent = "Building strategy and evaluating explicit follow-up outcomes…";
    try {
      const response = await fetch(API, {
        method: "GET",
        headers: { "X-Telegram-Init-Data": init },
        cache: "no-store",
        credentials: "same-origin",
      });
      const payload = await response.json().catch(() => ({}));
      if (response.status === 403) {
        if (status) status.textContent = "ADAPTIVE STRATEGY LOCKED // bco_premium required.";
        const body = $("#bcoStrategyBody"); if (body) body.innerHTML = "";
        return;
      }
      if (!response.ok || payload?.premium_authority !== "server_bco_premium") {
        throw new Error(payload?.detail || `Strategy HTTP ${response.status}`);
      }
      if (payload?.effectiveness_authority !== "explicit_outcome_association_only") {
        throw new Error("Strategy outcome authority mismatch");
      }
      if (status) status.textContent = "SERVER PREMIUM VERIFIED // OUTCOME EFFECTIVENESS IS ASSOCIATIVE, NOT CAUSAL";
      render(payload.data || {});
    } catch (error) {
      if (status) status.textContent = error?.message || "Adaptive strategy unavailable.";
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

  window.BCO_ADAPTIVE_STRATEGY = { refresh };
})();
