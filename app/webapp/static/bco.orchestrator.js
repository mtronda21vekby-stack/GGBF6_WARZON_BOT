/* BLACK CROWN OPS v36 — Mission Orchestrator overlay; additive over stable Operator Twin */
(() => {
  "use strict";
  if (window.__BCO_MISSION_ORCHESTRATOR_V36_LOADED__) return;
  window.__BCO_MISSION_ORCHESTRATOR_V36_LOADED__ = true;

  const $ = (q, root = document) => root.querySelector(q);
  let lastKey = "";

  function mount() {
    const card = $("#tab-operator-v25 .bco-op-mission");
    if (!card || $("#bcoMissionOrchestratorV36", card)) return false;
    const root = document.createElement("div");
    root.id = "bcoMissionOrchestratorV36";
    root.className = "bco-op-review";
    root.setAttribute("role", "status");
    root.textContent = "MISSION ORCHESTRATOR // synchronizing explicit-outcome stage…";
    const actions = $("#bcoOpMissionActions", card);
    if (actions) card.insertBefore(root, actions); else card.appendChild(root);
    return true;
  }

  function render() {
    mount();
    const root = $("#bcoMissionOrchestratorV36");
    if (!root) return;
    const data = window.BCO_OPERATOR?.getSnapshot?.() || {};
    const mission = data?.mission || {};
    const orch = mission?.orchestrator || data?.mission_orchestrator || {};
    if (orch?.enabled === false || data?.mission_orchestrator?.enabled === false) {
      root.textContent = "MISSION ORCHESTRATOR // rollback OFF — v35 mission behavior preserved";
      return;
    }
    const stage = String(mission?.training_stage || orch?.stage || "CALIBRATION").toUpperCase();
    const label = String(mission?.stage_label || orch?.stage_label || "BASELINE CAPTURE").toUpperCase();
    const gate = String(mission?.stage_success_condition || orch?.stage_success_condition || "explicit outcome gate");
    const next = String(orch?.next_stage_if_passed || stage).toUpperCase();
    const current = Number(orch?.current_evaluated_cycles || 0);
    const historical = Number(orch?.historical_evaluated_cycles || 0);
    const stale = Number(orch?.stale_explicit_cycles_excluded || 0);
    const recal = orch?.recalibration_required === true ? "REQUIRED" : "NO";
    const key = [stage, label, gate, next, current, historical, stale, recal].join("|");
    if (key === lastKey) return;
    lastKey = key;
    root.textContent = `MISSION ORCHESTRATOR // ${stage} · ${label} • GATE ${gate} • NEXT ${next} • CURRENT ${current} / HIST ${historical} • STALE EXCLUDED ${stale} • RECALIBRATION ${recal} • EXPLICIT OUTCOME ONLY • VOD CANNOT ADVANCE STAGE • STAGE ≠ PLAYER TRAIT • ONE BAD MATCH ≠ MAINTENANCE RESET`;
  }

  let attempts = 0;
  const boot = window.setInterval(() => {
    attempts += 1;
    if (window.BCO_OPERATOR && $("#tab-operator-v25 .bco-op-mission")) {
      window.clearInterval(boot);
      mount();
      render();
      window.setInterval(render, 600);
    } else if (attempts > 60) {
      window.clearInterval(boot);
    }
  }, 150);
})();
