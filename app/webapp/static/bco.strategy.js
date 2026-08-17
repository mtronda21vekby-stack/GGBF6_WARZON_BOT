/* BLACK CROWN OPS v33 — Adaptive Exploration Budget; Strategy Portfolio Calibration; Premium Strategy Outcome Loop; Premium Adaptive Strategy; recommendation, not player fact */
(() => {
  "use strict";
  if (window.__BCO_STRATEGY_V33_LOADED__) return;
  window.__BCO_STRATEGY_V33_LOADED__ = true;
  window.__BCO_STRATEGY_V32_LOADED__ = true;
  window.__BCO_STRATEGY_V31_LOADED__ = true;

  const API = "/webapp/api/operator-strategy";
  const $ = (q, root = document) => root.querySelector(q);
  const safe = (fn, fallback) => { try { const v = fn(); return v === undefined ? fallback : v; } catch (_) { return fallback; } };
  const initData = () => String(safe(() => window.Telegram?.WebApp?.initData, "") || "").trim();

  function mount() {
    const pane = $("#tab-operator-v25 .bco-op-shell");
    if (!pane || $("#bcoStrategyV33")) return;
    const card = document.createElement("section");
    card.id = "bcoStrategyV33";
    card.className = "bco-op-card";
    card.innerHTML = `<div class="bco-op-title"><span>ADAPTIVE STRATEGY</span><small>PREMIUM / EXPLORATION BUDGET</small></div><div id="bcoStrategyStatus" class="bco-op-review">Resolve strategy on demand.</div><div id="bcoStrategyBody"></div><button id="bcoStrategyRefresh" class="bco-op-btn" type="button">BUILD NEXT OBJECTIVE</button>`;
    const status = $("#bcoOpStatus", pane);
    if (status) pane.insertBefore(card, status); else pane.appendChild(card);
    $("#bcoStrategyRefresh")?.addEventListener("click", refresh);
  }

  function block(label, value) {
    const el = document.createElement("article"); el.className = "bco-op-dim neutral_observation";
    const title = document.createElement("strong"); title.textContent = label;
    const text = document.createElement("p"); text.textContent = String(value || "—");
    el.append(title, text); return el;
  }

  function effectivenessText(effectiveness) {
    const latest = effectiveness?.latest;
    if (!latest) return "NO FOLLOW-UP WINDOW YET";
    const verdict = String(latest.verdict || "insufficient_followup").replaceAll("_", " ").toUpperCase();
    const o = latest.outcomes || {};
    return `${verdict} • ${Number(latest.matched_cycles || 0)}/3 CYCLES • CLEAN ${Number(o.clean || 0)} / MIXED ${Number(o.mixed || 0)} / FAILED ${Number(o.failed || 0)}`;
  }

  function portfolioText(calibration) {
    const c = calibration || {};
    const sign = Number(c.priority_adjustment || 0) > 0 ? "+" : "";
    return `${String(c.state || "explore").toUpperCase()} • EVALUATED ${Number(c.evaluated_windows || 0)} • PRIORITY ${sign}${Number(c.priority_adjustment || 0)} • SCORE ${Number(c.selection_score || 0)} • EXPLORATION PRESERVED`;
  }

  function explorationText(exploration) {
    const e = exploration || {};
    const gap = e.score_gap === null || e.score_gap === undefined ? "N/A" : Number(e.score_gap);
    return `${String(e.reason || "top_signal").replaceAll("_", " ").toUpperCase()} • ROTATED ${e.rotated === true ? "YES" : "NO"} • REPEAT ${Number(e.repeat_streak || 0)}/${Number(e.repeat_limit || 2)} • SCORE GAP ${gap} • DETERMINISTIC • EVIDENCE-BACKED ONLY`;
  }

  function render(data) {
    const body = $("#bcoStrategyBody"); if (!body) return; body.innerHTML = "";
    body.append(
      block("FOCUS", String(data?.focus || "calibration").replaceAll("_", " ").toUpperCase()),
      block("OBJECTIVE", data?.objective),
      block("SUCCESS CONDITION", data?.success_condition),
      block("NEXT ADAPTATION", data?.next_adaptation),
      block("RATIONALE", data?.rationale),
      block("PORTFOLIO PRIOR", portfolioText(data?.portfolio_calibration)),
      block("EXPLORATION BUDGET", explorationText(data?.exploration_budget)),
      block("OUTCOME LOOP", effectivenessText(data?.effectiveness))
    );
    const meta = document.createElement("div"); meta.className = "bco-op-flow";
    meta.textContent = `${String(data?.strategy_class || "calibration").toUpperCase()} • CONF ${String(data?.confidence || "unknown").toUpperCase()} • STRATEGY ${String(data?.strategy_id || "untracked").toUpperCase()} • ASSOCIATION ≠ CAUSATION • RECOMMENDATION ≠ FACT • EFFECTIVENESS ≠ CAUSAL PROOF • PORTFOLIO PRIOR ≠ CAUSAL PROOF • EXPLORATION ≠ RANDOMNESS • ROTATION REQUIRES CLOSE EVIDENCE`;
    body.prepend(meta);
  }

  async function refresh() {
    const status = $("#bcoStrategyStatus"); const init = initData();
    if (!init) { if (status) status.textContent = "Open from Telegram to resolve server-authoritative Premium."; return; }
    if (status) status.textContent = "Building strategy from bounded evidence + portfolio prior + deterministic exploration budget…";
    try {
      const response = await fetch(API, { method: "GET", headers: { "X-Telegram-Init-Data": init }, cache: "no-store", credentials: "same-origin" });
      const payload = await response.json().catch(() => ({}));
      if (response.status === 403) { if (status) status.textContent = "ADAPTIVE STRATEGY LOCKED // bco_premium required."; const body = $("#bcoStrategyBody"); if (body) body.innerHTML = ""; return; }
      if (!response.ok || payload?.premium_authority !== "server_bco_premium") throw new Error(payload?.detail || `Strategy HTTP ${response.status}`);
      if (payload?.effectiveness_authority !== "explicit_outcome_association_only") throw new Error("Strategy outcome authority mismatch");
      if (payload?.portfolio_authority !== "associative_outcome_calibration_only") throw new Error("Strategy portfolio authority mismatch");
      if (payload?.exploration_authority !== "deterministic_evidence_backed_rotation_only") throw new Error("Exploration authority mismatch");
      if (status) status.textContent = "SERVER PREMIUM VERIFIED // EXPLORATION IS DETERMINISTIC, EVIDENCE-BACKED, NON-CAUSAL";
      render(payload.data || {});
    } catch (error) { if (status) status.textContent = error?.message || "Adaptive strategy unavailable."; }
  }

  let attempts = 0;
  const timer = window.setInterval(() => { attempts += 1; if ($("#tab-operator-v25 .bco-op-shell")) { window.clearInterval(timer); mount(); } else if (attempts > 30) window.clearInterval(timer); }, 150);
  window.BCO_ADAPTIVE_STRATEGY = { refresh };
})();
