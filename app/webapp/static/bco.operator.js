/* BLACK CROWN OPS v25 — Operator Twin / Adaptive Mission Intelligence; v27 mission evidence fusion */
(() => {
  "use strict";
  if (window.__BCO_OPERATOR_V25_LOADED__) return;
  window.__BCO_OPERATOR_V25_LOADED__ = true;

  const BUILD = String(window.__BCO_BUILD__ || "dev");
  const API = "/webapp/api/operator-intelligence";
  const ACCEPT = "/webapp/api/operator-mission/accept";
  const COMPLETE = "/webapp/api/operator-mission/complete";
  const $ = (q, root = document) => root.querySelector(q);
  const $$ = (q, root = document) => Array.from(root.querySelectorAll(q));
  const safe = (fn, fallback) => { try { const v = fn(); return v === undefined ? fallback : v; } catch (_) { return fallback; } };
  let latest = null;
  let busy = false;

  function initData() {
    return String(safe(() => window.Telegram?.WebApp?.initData, "") || "").trim();
  }

  function haptic(kind = "selection") {
    safe(() => {
      const h = window.Telegram?.WebApp?.HapticFeedback;
      if (!h) return;
      if (["success", "warning", "error"].includes(kind)) h.notificationOccurred(kind);
      else h.selectionChanged();
    });
  }

  function injectCss() {
    if ($('link[data-bco-operator="v25"]')) return;
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.dataset.bcoOperator = "v25";
    link.href = `/webapp/bco.operator.css?build=${encodeURIComponent(BUILD)}`;
    document.head.appendChild(link);
  }

  function switchToOperator() {
    $$(".tabpane").forEach((pane) => pane.classList.remove("active"));
    $$(".nav-btn").forEach((btn) => btn.setAttribute("aria-selected", "false"));
    $("#tab-operator-v25")?.classList.add("active");
    $("#bcoOperatorNav")?.setAttribute("aria-selected", "true");
    refresh(false);
  }

  function mount() {
    injectCss();
    const main = $(".app-main");
    const nav = $(".bottom-nav");
    const foot = $(".foot");
    if (!main || !nav || $("#tab-operator-v25")) return;

    const section = document.createElement("section");
    section.id = "tab-operator-v25";
    section.className = "grid tabpane bco-op-pane";
    section.innerHTML = `
      <div class="bco-op-shell">
        <header class="bco-op-hero">
          <div class="bco-op-kicker">OPERATOR TWIN // SERVER-AUTHORITATIVE</div>
          <h2>Adaptive Mission Intelligence</h2>
          <p id="bcoOpTruth">No hidden score. Unknown remains unknown.</p>
          <button class="bco-op-btn" id="bcoOpRefresh" type="button">REFRESH DOSSIER</button>
        </header>
        <div class="bco-op-state">
          <div><span>READINESS</span><strong id="bcoOpReadiness">—</strong></div>
          <div><span>RISK</span><strong id="bcoOpRisk">—</strong></div>
          <div><span>CONFIDENCE</span><strong id="bcoOpConfidence">—</strong></div>
          <div><span>MOMENTUM</span><strong id="bcoOpMomentum">—</strong></div>
        </div>
        <section class="bco-op-card">
          <div class="bco-op-title"><span>OPERATOR SIGNAL MATRIX</span><small>evidence-calibrated</small></div>
          <div id="bcoOpDimensions" class="bco-op-dimensions"></div>
        </section>
        <section class="bco-op-card bco-op-mission">
          <div class="bco-op-title"><span>CURRENT MISSION</span><small id="bcoOpPhase">PRE_SESSION</small></div>
          <h3 id="bcoOpMissionTitle">Synchronizing…</h3>
          <p id="bcoOpMissionObjective"></p>
          <div class="bco-op-metrics" id="bcoOpMetrics"></div>
          <div class="bco-op-success" id="bcoOpSuccess"></div>
          <div class="bco-op-basis" id="bcoOpBasis"></div>
          <div id="bcoOpMissionActions" class="bco-op-actions"></div>
          <div id="bcoOpReport" class="bco-op-report" hidden>
            <label>Clean executions<input id="bcoOpCleanCount" type="number" min="0" max="100" inputmode="numeric" placeholder="optional"></label>
            <label>Death cause<input id="bcoOpDeathCause" maxlength="240" placeholder="optional evidence"></label>
          </div>
        </section>
        <section class="bco-op-card">
          <div class="bco-op-title"><span>SESSION LIFECYCLE</span><small>persistent</small></div>
          <div class="bco-op-flow"><i>PRE-SESSION</i><b>→</b><i>LIVE OBJECTIVE</i><b>→</b><i>POST-SESSION REVIEW</i><b>→</b><i>MEMORY UPDATE</i><b>→</b><i>NEXT MISSION</i></div>
          <div id="bcoOpEvidence" class="bco-op-review"></div>
          <div id="bcoOpReview" class="bco-op-review"></div>
        </section>
        <div id="bcoOpStatus" class="bco-op-status">Telegram identity required.</div>
      </div>`;
    if (foot) main.insertBefore(section, foot); else main.appendChild(section);

    const button = document.createElement("button");
    button.id = "bcoOperatorNav";
    button.className = "nav-btn";
    button.type = "button";
    button.dataset.tab = "operator-v25";
    button.setAttribute("aria-selected", "false");
    button.innerHTML = '<span class="nav-ico">◫</span><span class="nav-txt">Operator</span>';
    const settings = nav.querySelector('[data-tab="settings"]');
    if (settings) nav.insertBefore(button, settings); else nav.appendChild(button);
    button.addEventListener("click", switchToOperator);
    $("#bcoOpRefresh")?.addEventListener("click", () => refresh(true));
  }

  function text(id, value, fallback = "—") {
    const el = $(id);
    if (el) el.textContent = (value === null || value === undefined || value === "") ? fallback : String(value);
  }

  function renderDimensions(dimensions) {
    const root = $("#bcoOpDimensions");
    if (!root) return;
    root.innerHTML = "";
    const order = ["aim","movement","positioning","rotations","decision","aggression","survivability","comms","discipline","consistency","tilt_susceptibility"];
    order.forEach((name) => {
      const d = dimensions?.[name] || {};
      const row = document.createElement("article");
      row.className = `bco-op-dim ${String(d.assessment || "unknown")}`;
      const label = name.replaceAll("_", " ").toUpperCase();
      const claim = String(d.claim_class || "unknown").replaceAll("_", " ").toUpperCase();
      const evidence = Number(d.evidence_count || 0);
      const trend = String(d.trend || "unknown").toUpperCase();
      row.innerHTML = `<div><strong></strong><small></small></div><div class="bco-op-dim-meta"></div><p></p>`;
      row.querySelector("strong").textContent = label;
      row.querySelector("small").textContent = claim;
      row.querySelector(".bco-op-dim-meta").textContent = `CONF ${String(d.confidence || "unknown").toUpperCase()} • EVIDENCE ${evidence} • TREND ${trend}`;
      row.querySelector("p").textContent = d.uncertainty || "No sufficient evidence.";
      root.appendChild(row);
    });
  }

  function missionMetrics(mission) {
    return Array.isArray(mission?.metrics) ? mission.metrics.map((x) => String(x).replaceAll("_", " ").toUpperCase()) : [];
  }

  function actionButton(label, kind, handler) {
    const btn = document.createElement("button");
    btn.className = `bco-op-btn ${kind || ""}`;
    btn.type = "button";
    btn.textContent = label;
    btn.addEventListener("click", handler);
    return btn;
  }

  function renderMission(data) {
    const mission = data?.mission || {};
    const session = data?.session || {};
    text("#bcoOpPhase", session.phase || "PRE_SESSION");
    text("#bcoOpMissionTitle", mission.title, "NO ACTIVE MISSION");
    text("#bcoOpMissionObjective", mission.objective, "Collecting evidence.");
    text("#bcoOpSuccess", mission.success_condition ? `SUCCESS CONDITION // ${mission.success_condition}` : "SUCCESS CONDITION // collecting evidence");
    text("#bcoOpBasis", mission.basis ? `BASIS // ${mission.basis}` : "BASIS // unknown remains unknown");
    const metrics = $("#bcoOpMetrics");
    if (metrics) metrics.innerHTML = missionMetrics(mission).map((x) => `<span>${x}</span>`).join("");

    const actions = $("#bcoOpMissionActions");
    const report = $("#bcoOpReport");
    if (!actions) return;
    actions.innerHTML = "";
    if (report) report.hidden = mission.status !== "active";
    if (mission.status === "candidate" && mission.id) {
      actions.appendChild(actionButton("ACCEPT MISSION", "primary", () => acceptMission(mission.id)));
    } else if (mission.status === "active" && mission.id) {
      actions.append(
        actionButton("CLEAN", "success", () => completeMission(mission.id, "clean")),
        actionButton("MIXED", "primary", () => completeMission(mission.id, "mixed")),
        actionButton("FAILED", "danger", () => completeMission(mission.id, "failed")),
      );
    }

    const missionEvidence = session.mission_evidence;
    const evidenceEl = $("#bcoOpEvidence");
    if (evidenceEl) {
      evidenceEl.textContent = missionEvidence
        ? `MISSION EVIDENCE // ${String(missionEvidence.classification || "unknown").replaceAll("_", " ").toUpperCase()} • ${Number(missionEvidence.clips || 0)} CLIPS • ${Number(missionEvidence.evidence_count || 0)} SIGNALS • SAMPLED-FRAME ONLY / NO AUTO-COMPLETE`
        : "MISSION EVIDENCE // no correlated VOD evidence yet.";
    }

    const review = session.last_review;
    const reviewEl = $("#bcoOpReview");
    if (reviewEl) {
      reviewEl.textContent = review ? `LAST REVIEW // ${String(review.outcome || "reported").toUpperCase()} • ${String(review.focus || "unknown").replaceAll("_", " ").toUpperCase()}` : "No completed mission review yet.";
    }
  }

  function render(data) {
    latest = data;
    const op = data?.operator || {};
    text("#bcoOpReadiness", op.readiness);
    text("#bcoOpRisk", op.risk);
    text("#bcoOpConfidence", op.confidence);
    text("#bcoOpMomentum", op.session_momentum);
    const truth = op.truth_model || {};
    text("#bcoOpTruth", `Truth model: ${Number(truth.verified_facts || 0)} verified facts • ${Number(truth.high_confidence_patterns || 0)} high-confidence patterns • ${Number(truth.unknown_dimensions || 0)} unknown dimensions. No hidden score.`);
    renderDimensions(op.dimensions || {});
    renderMission(data);
    text("#bcoOpStatus", data.enabled === false ? "Operator Intelligence rollback flag is OFF." : "Verified Telegram identity • server-authoritative Operator Twin");
  }

  async function request(path, body) {
    const init = initData();
    if (!init) throw new Error("Open Command Center from Telegram to use private Operator Intelligence.");
    const response = await fetch(path, {
      method: body ? "POST" : "GET",
      headers: { "X-Telegram-Init-Data": init, ...(body ? { "Content-Type": "application/json" } : {}) },
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store",
    });
    const payload = await response.json().catch(() => null);
    if (!response.ok || !payload?.ok) throw new Error(payload?.detail || `Operator API HTTP ${response.status}`);
    return payload.data;
  }

  async function refresh(force) {
    if (busy || (!force && latest)) return;
    busy = true;
    text("#bcoOpStatus", "Synchronizing Operator Twin…");
    try {
      render(await request(API));
    } catch (error) {
      text("#bcoOpStatus", error?.message || "Operator Intelligence unavailable.");
    } finally {
      busy = false;
    }
  }

  async function acceptMission(missionId) {
    if (busy) return;
    busy = true;
    try {
      const data = await request(ACCEPT, { mission_id: missionId });
      render(data); haptic("success");
    } catch (error) {
      text("#bcoOpStatus", error?.message || "Mission acceptance failed."); haptic("error");
    } finally { busy = false; }
  }

  async function completeMission(missionId, outcome) {
    if (busy) return;
    busy = true;
    const cleanRaw = String($("#bcoOpCleanCount")?.value || "").trim();
    const clean = cleanRaw === "" ? null : Number(cleanRaw);
    const deathCause = String($("#bcoOpDeathCause")?.value || "").trim();
    const metrics = {};
    if (clean !== null && Number.isFinite(clean) && clean >= 0) metrics.clean_executions = clean;
    if (deathCause) metrics.death_cause = deathCause;
    try {
      const data = await request(COMPLETE, { mission_id: missionId, outcome, metrics });
      render(data); haptic(outcome === "failed" ? "warning" : "success");
    } catch (error) {
      text("#bcoOpStatus", error?.message || "Mission completion failed."); haptic("error");
    } finally { busy = false; }
  }

  mount();
  window.BCO_OPERATOR = { refresh, getSnapshot: () => latest };
})();
