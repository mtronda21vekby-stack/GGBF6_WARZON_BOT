/* BLACK CROWN OPS — Adaptive Mission Command Center v19 */
(() => {
  "use strict";

  const BUILD = window.__BCO_BUILD__ || "dev";
  const API = "/webapp/api/intelligence";
  const MISSION_ACCEPT_API = "/webapp/api/mission/accept";
  const MISSION_COMPLETE_API = "/webapp/api/mission/complete";
  const CLIENT_VERSION = "adaptive-mission-control-19.0.0";
  const $ = (q, root = document) => root.querySelector(q);
  const safe = (fn, fallback) => {
    try {
      const value = fn();
      return value === undefined ? fallback : value;
    } catch (_) {
      return fallback;
    }
  };

  let loaded = false;
  let loading = false;
  let missionBusy = false;
  let latestMissionControl = null;

  function injectCss() {
    if (document.querySelector('link[data-bco-command-center]')) return;
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.dataset.bcoCommandCenter = "1";
    link.href = `/webapp/command-center.css?build=${encodeURIComponent(BUILD)}`;
    document.head.appendChild(link);
  }

  function haptic(kind = "light") {
    safe(() => {
      const api = window.Telegram?.WebApp?.HapticFeedback;
      if (!api) return;
      if (["success", "warning", "error"].includes(kind)) api.notificationOccurred(kind);
      else if (kind === "selection") api.selectionChanged();
      else api.impactOccurred(kind);
    });
  }

  function field(label, id) {
    return `<div class="bco-cc-field"><small>${label}</small><strong id="${id}">—</strong></div>`;
  }

  function mount() {
    injectCss();
    const main = $(".app-main");
    const foot = $(".foot");
    const nav = $(".bottom-nav");
    if (!main || !nav || $("#tab-intel")) return;

    const section = document.createElement("section");
    section.className = "grid tabpane";
    section.id = "tab-intel";
    section.innerHTML = `
      <div class="bco-cc-shell">
        <div class="bco-cc-hero">
          <div class="bco-cc-hero-grid" aria-hidden="true"></div>
          <div class="bco-cc-eyebrow">BLACK CROWN OPS • ADAPTIVE PLAYER INTELLIGENCE</div>
          <div class="bco-cc-title">Mission Command Center</div>
          <div class="bco-cc-summary" id="ccSummary">Синхронизирую долгосрочную память, игровые сигналы и активный протокол…</div>
          <div class="bco-cc-status" id="ccTrust"><i></i><span>Telegram identity required</span></div>
          <div class="bco-cc-actions">
            <button class="bco-cc-btn primary" id="ccRefresh" type="button">↻ Recalculate intelligence</button>
            <button class="bco-cc-btn" id="ccCoach" type="button">🧠 Open AI briefing</button>
          </div>
        </div>

        <article class="bco-mission-card" id="ccMissionCard" aria-live="polite">
          <div class="bco-mission-scan" aria-hidden="true"></div>
          <div class="bco-mission-head">
            <div>
              <div class="bco-mission-kicker">ACTIVE ADAPTIVE PROTOCOL // V19</div>
              <div class="bco-mission-state-line">
                <span class="bco-mission-state" id="ccMissionMode">CALIBRATE</span>
                <span class="bco-mission-status" id="ccMissionStatus">CANDIDATE</span>
              </div>
            </div>
            <div class="bco-mission-id" id="ccMissionId">—</div>
          </div>

          <div class="bco-mission-overview">
            <div class="bco-readiness-gauge" id="ccReadinessGauge" style="--readiness:0">
              <div class="bco-readiness-core">
                <strong id="ccReadiness">0</strong>
                <small>READINESS</small>
              </div>
            </div>
            <div class="bco-mission-telemetry">
              <div><small>MOMENTUM</small><strong id="ccMomentum">0</strong><i><b id="ccMomentumBar"></b></i></div>
              <div><small>CONFIDENCE</small><strong id="ccConfidence">0</strong><i><b id="ccConfidenceBar"></b></i></div>
              <div><small>RISK</small><strong id="ccRisk">0</strong><i><b id="ccRiskBar"></b></i></div>
              <div><small>DATA COVERAGE</small><strong id="ccMissionCoverage">0</strong><i><b id="ccCoverageBar"></b></i></div>
            </div>
          </div>

          <div class="bco-mission-focus-row">
            <span id="ccMissionFocus">POSITIONING</span>
            <span id="ccMissionDuration">16 MIN</span>
            <span id="ccMissionRiskLevel">RISK MODERATE</span>
          </div>
          <h2 class="bco-mission-title" id="ccMissionTitle">CALIBRATION PROTOCOL</h2>
          <p class="bco-mission-objective" id="ccMissionObjective">Собираю доказательства для первой миссии.</p>
          <div class="bco-mission-why"><small>WHY THIS MISSION</small><p id="ccMissionWhy">—</p></div>

          <div class="bco-mission-protocol" id="ccMissionProtocol"></div>

          <div class="bco-mission-directives">
            <div><small>MATCH RULE</small><p id="ccMissionRule">—</p></div>
            <div><small>SUCCESS METRIC</small><p id="ccMissionMetric">—</p></div>
          </div>

          <div class="bco-mission-evidence">
            <small>EVIDENCE CHANNEL</small>
            <div id="ccMissionEvidence"></div>
          </div>

          <div class="bco-mission-actions" id="ccMissionActions">
            <button class="bco-cc-btn primary" id="ccMissionAccept" type="button">✓ Accept mission</button>
            <button class="bco-cc-btn" id="ccMissionBrief" type="button">🧠 Brief with AI</button>
          </div>
          <div class="bco-mission-outcomes" id="ccMissionOutcomes" hidden>
            <button class="bco-outcome clean" data-outcome="clean" type="button">CLEAN</button>
            <button class="bco-outcome mixed" data-outcome="mixed" type="button">MIXED</button>
            <button class="bco-outcome failed" data-outcome="failed" type="button">FAILED</button>
          </div>
          <div class="bco-mission-history" id="ccMissionHistory">accepted 0 • completed 0</div>
        </article>

        <div class="bco-cc-kpis">
          <div class="bco-cc-kpi"><div class="bco-cc-kpi-label">Data coverage</div><div class="bco-cc-kpi-value" id="ccCoverage">—</div></div>
          <div class="bco-cc-kpi"><div class="bco-cc-kpi-label">Recurring mistakes</div><div class="bco-cc-kpi-value" id="ccMistakeCount">—</div></div>
          <div class="bco-cc-kpi"><div class="bco-cc-kpi-label">Training sessions</div><div class="bco-cc-kpi-value" id="ccTrainingCount">—</div></div>
          <div class="bco-cc-kpi"><div class="bco-cc-kpi-label">Progress signals</div><div class="bco-cc-kpi-value" id="ccProgressCount">—</div></div>
        </div>

        <div class="bco-cc-card">
          <div class="bco-cc-card-title"><span>👤 Player profile</span><span class="bco-cc-card-sub" id="ccBackend">backend: —</span></div>
          <div class="bco-cc-profile">
            ${field("Game", "ccGame")}${field("Input", "ccInput")}${field("Rank", "ccRank")}${field("K/D", "ccKd")}
            ${field("Role", "ccRole")}${field("Goal", "ccGoal")}${field("Training focus", "ccFocus")}${field("Voice", "ccVoice")}
          </div>
        </div>

        <div class="bco-cc-grid two">
          <div class="bco-cc-card">
            <div class="bco-cc-card-title"><span>🧠 Skill matrix</span><span class="bco-cc-card-sub">evidence only</span></div>
            <div class="bco-cc-scores" id="ccScores"></div>
          </div>
          <div class="bco-cc-card">
            <div class="bco-cc-card-title"><span>📈 Progress signal</span><span class="bco-cc-trend flat" id="ccTrend">—</span></div>
            <div class="bco-cc-chart" id="ccChart"></div>
            <div class="bco-cc-chart-meta"><span id="ccChartMetric">waiting for match data</span><span id="ccChartRange">—</span></div>
          </div>
        </div>

        <div class="bco-cc-grid two">
          <div class="bco-cc-card">
            <div class="bco-cc-card-title"><span>⚠️ Recurring mistakes</span><span class="bco-cc-card-sub">frequency</span></div>
            <div class="bco-cc-list" id="ccMistakes"></div>
          </div>
          <div class="bco-cc-card">
            <div class="bco-cc-card-title"><span>🎯 Training history</span><span class="bco-cc-card-sub">latest</span></div>
            <div class="bco-cc-list" id="ccTraining"></div>
          </div>
        </div>

        <div class="bco-cc-card">
          <div class="bco-cc-card-title"><span>🎬 VOD intelligence</span><span class="bco-cc-card-sub">sampled-frame evidence</span></div>
          <div class="bco-cc-list" id="ccVod"></div>
        </div>
        <div class="bco-cc-loader" id="ccLoader"><i></i><span>Synchronizing server intelligence…</span></div>
      </div>`;

    if (foot) main.insertBefore(section, foot);
    else main.appendChild(section);

    const button = document.createElement("button");
    button.className = "nav-btn";
    button.dataset.tab = "intel";
    button.type = "button";
    button.setAttribute("aria-selected", "false");
    button.innerHTML = '<span class="nav-ico">◈</span><span class="nav-txt">Mission</span>';
    const settings = nav.querySelector('[data-tab="settings"]');
    if (settings) nav.insertBefore(button, settings);
    else nav.appendChild(button);
    nav.classList.add("bco-cc-six");

    $("#ccRefresh")?.addEventListener("click", () => refresh(true));
    $("#ccCoach")?.addEventListener("click", missionBrief);
    $("#ccMissionAccept")?.addEventListener("click", () => missionAction("accept"));
    $("#ccMissionBrief")?.addEventListener("click", missionBrief);
    $("#ccMissionOutcomes")?.addEventListener("click", (event) => {
      const outcome = event.target.closest?.("[data-outcome]")?.dataset.outcome;
      if (outcome) missionAction("complete", outcome);
    });
    button.addEventListener("click", () => refresh(false));
  }

  function setText(id, value, fallback = "—") {
    const el = $(id);
    if (el) el.textContent = (value === null || value === undefined || value === "") ? fallback : String(value);
  }

  function fmtTime(value) {
    const raw = String(value || "");
    if (!raw) return "";
    const d = new Date(raw);
    if (Number.isNaN(d.getTime())) return raw.slice(0, 16);
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" }) + " " + d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  function empty(container, text) {
    container.innerHTML = "";
    const el = document.createElement("div");
    el.className = "bco-cc-empty";
    el.textContent = text;
    container.appendChild(el);
  }

  function clampPercent(value) {
    const number = Number(value);
    return Number.isFinite(number) ? Math.max(0, Math.min(100, Math.round(number))) : 0;
  }

  function setMeter(valueId, barId, value) {
    const n = clampPercent(value);
    setText(valueId, n);
    const bar = $(barId);
    if (bar) bar.style.width = `${n}%`;
  }

  function renderMission(control) {
    latestMissionControl = control && typeof control === "object" ? control : null;
    const state = control?.state || {};
    const mission = control?.mission || {};
    const history = control?.history || {};
    const enabled = control?.enabled !== false;
    const status = String(mission.status || "candidate").toLowerCase();
    const readiness = clampPercent(state.readiness);

    const card = $("#ccMissionCard");
    card?.classList.toggle("is-active", status === "active");
    card?.classList.toggle("is-disabled", !enabled);
    card?.setAttribute("data-mode", String(state.mode || "CALIBRATE").toLowerCase());
    card?.setAttribute("data-risk", String(state.risk_level || "MODERATE").toLowerCase());

    setText("#ccMissionMode", state.mode || "CALIBRATE");
    setText("#ccMissionStatus", enabled ? status.toUpperCase() : "READ ONLY");
    setText("#ccMissionId", mission.id ? `ID ${String(mission.id).slice(-8).toUpperCase()}` : "ID —");
    setText("#ccReadiness", readiness);
    const gauge = $("#ccReadinessGauge");
    if (gauge) gauge.style.setProperty("--readiness", readiness);

    setMeter("#ccMomentum", "#ccMomentumBar", state.momentum);
    setMeter("#ccConfidence", "#ccConfidenceBar", state.confidence_pct);
    setMeter("#ccRisk", "#ccRiskBar", state.risk);
    setMeter("#ccMissionCoverage", "#ccCoverageBar", state.coverage);

    setText("#ccMissionFocus", String(mission.focus || state.dominant_focus || "positioning").toUpperCase());
    setText("#ccMissionDuration", `${Number(mission.duration_min || 0)} MIN`);
    setText("#ccMissionRiskLevel", `RISK ${String(state.risk_level || "MODERATE").toUpperCase()}`);
    setText("#ccMissionTitle", mission.title || "CALIBRATION PROTOCOL");
    setText("#ccMissionObjective", mission.objective || "Собрать первый надёжный игровой сигнал.");
    setText("#ccMissionWhy", mission.why || "Недостаточно данных для причинного выбора.");
    setText("#ccMissionRule", mission.match_rule || "Одна задача на матч; не менять критерий в середине попытки.");
    setText("#ccMissionMetric", mission.success_metric || "После матча отправить измеримый результат.");
    setText("#ccMissionHistory", `accepted ${Number(history.accepted || 0)} • completed ${Number(history.completed || 0)}${history.last_outcome ? ` • last ${String(history.last_outcome).toUpperCase()}` : ""}`);

    const protocolRoot = $("#ccMissionProtocol");
    if (protocolRoot) {
      protocolRoot.innerHTML = "";
      const protocol = Array.isArray(mission.protocol) ? mission.protocol : [];
      if (!protocol.length) {
        empty(protocolRoot, "Protocol is calibrating.");
      } else {
        protocol.slice(0, 3).forEach((step, index) => {
          const row = document.createElement("div");
          row.className = "bco-protocol-step";
          const indexEl = document.createElement("span");
          indexEl.textContent = String(index + 1).padStart(2, "0");
          const content = document.createElement("div");
          const head = document.createElement("strong");
          head.textContent = `${String(step.phase || "PHASE").toUpperCase()} · ${Number(step.minutes || 0)} MIN`;
          const copy = document.createElement("p");
          copy.textContent = String(step.action || "");
          content.append(head, copy);
          row.append(indexEl, content);
          protocolRoot.appendChild(row);
        });
      }
    }

    const evidenceRoot = $("#ccMissionEvidence");
    if (evidenceRoot) {
      evidenceRoot.innerHTML = "";
      const evidence = Array.isArray(mission.evidence) ? mission.evidence : [];
      if (!evidence.length) {
        const chip = document.createElement("span");
        chip.className = "bco-evidence-chip calibrating";
        chip.textContent = "CALIBRATING";
        evidenceRoot.appendChild(chip);
      } else {
        evidence.slice(0, 6).forEach((item) => {
          const chip = document.createElement("span");
          chip.className = "bco-evidence-chip";
          chip.textContent = `${String(item.label || "signal").slice(0, 80)}${item.weight !== undefined ? ` · W${item.weight}` : ""}`;
          evidenceRoot.appendChild(chip);
        });
      }
    }

    const accept = $("#ccMissionAccept");
    const outcomes = $("#ccMissionOutcomes");
    if (accept) {
      accept.hidden = status === "active" || !enabled;
      accept.disabled = missionBusy || !mission.id || !enabled;
      accept.textContent = missionBusy ? "Synchronizing…" : "✓ Accept mission";
    }
    if (outcomes) {
      outcomes.hidden = status !== "active" || !enabled;
      outcomes.querySelectorAll("button").forEach((button) => { button.disabled = missionBusy; });
    }
  }

  function renderScores(scores) {
    const root = $("#ccScores");
    if (!root) return;
    root.innerHTML = "";
    for (const name of ["aim", "movement", "positioning", "decision", "comms"]) {
      const value = scores?.[name];
      const numeric = Number(value);
      const known = Number.isFinite(numeric);
      const row = document.createElement("div");
      row.className = "bco-cc-score-row";
      row.innerHTML = `<div class="bco-cc-score-name"></div><div class="bco-cc-bar"><i></i></div><div class="bco-cc-score-value"></div>`;
      row.children[0].textContent = name;
      row.querySelector("i").style.width = known ? `${Math.max(0, Math.min(100, numeric))}%` : "0%";
      row.children[2].textContent = known ? String(numeric) : "—";
      root.appendChild(row);
    }
  }

  function renderMistakes(items) {
    const root = $("#ccMistakes");
    if (!root) return;
    if (!Array.isArray(items) || !items.length) return empty(root, "Нет подтверждённых повторяющихся ошибок. Нужны игровые отчёты или VOD.");
    root.innerHTML = "";
    items.slice(0, 8).forEach((item) => {
      const row = document.createElement("div");
      row.className = "bco-cc-item";
      const main = document.createElement("div");
      main.className = "bco-cc-item-main";
      const title = document.createElement("div");
      title.className = "bco-cc-item-title";
      title.textContent = item.label || "Mistake";
      const meta = document.createElement("div");
      meta.className = "bco-cc-item-meta";
      meta.textContent = item.last_seen ? `last: ${fmtTime(item.last_seen)}` : "evidence-backed";
      main.append(title, meta);
      const count = document.createElement("div");
      count.className = "bco-cc-count";
      count.textContent = `×${Number(item.count || 0)}`;
      row.append(main, count);
      root.appendChild(row);
    });
  }

  function renderTraining(items) {
    const root = $("#ccTraining");
    if (!root) return;
    if (!Array.isArray(items) || !items.length) return empty(root, "Тренировочная история пока пустая.");
    root.innerHTML = "";
    items.slice(0, 8).forEach((item) => {
      const row = document.createElement("div");
      row.className = "bco-cc-item";
      const main = document.createElement("div");
      main.className = "bco-cc-item-main";
      const title = document.createElement("div");
      title.className = "bco-cc-item-title";
      title.textContent = String(item.focus || "hybrid").toUpperCase();
      const meta = document.createElement("div");
      meta.className = "bco-cc-item-meta";
      meta.textContent = [item.game, fmtTime(item.at)].filter(Boolean).join(" • ");
      main.append(title, meta);
      row.append(main);
      root.appendChild(row);
    });
  }

  function renderVod(items) {
    const root = $("#ccVod");
    if (!root) return;
    if (!Array.isArray(items) || !items.length) return empty(root, "VOD intelligence появится после первого видео-разбора.");
    root.innerHTML = "";
    items.slice(0, 5).forEach((item) => {
      const row = document.createElement("div");
      row.className = "bco-cc-item";
      const main = document.createElement("div");
      main.className = "bco-cc-item-main";
      const title = document.createElement("div");
      title.className = "bco-cc-item-title";
      title.textContent = [item.game || "VOD", fmtTime(item.at)].filter(Boolean).join(" • ");
      const summary = document.createElement("div");
      summary.className = "bco-cc-vod-summary";
      summary.textContent = item.summary || "Sampled-frame analysis stored.";
      const meta = document.createElement("div");
      meta.className = "bco-cc-item-meta";
      meta.textContent = (item.confirmed_mistakes || []).length ? `confirmed: ${(item.confirmed_mistakes || []).join(" · ")}` : "no high-confidence recurring mistake";
      main.append(title, summary, meta);
      row.append(main);
      root.appendChild(row);
    });
  }

  function chooseSeries(series) {
    const order = ["accuracy_pct", "kills", "placement", "score", "wave"];
    for (const key of order) {
      const rows = Array.isArray(series?.[key]) ? series[key].filter((x) => Number.isFinite(Number(x.value))) : [];
      if (rows.length >= 2) return [key, rows];
    }
    return [null, []];
  }

  function renderChart(series, trends) {
    const root = $("#ccChart");
    if (!root) return;
    const [metric, rows] = chooseSeries(series);
    if (!metric) {
      empty(root, "Нужно минимум 2 match/progression отчёта для графика.");
      setText("#ccChartMetric", "waiting for match data");
      setText("#ccChartRange", "—");
      setText("#ccTrend", "—");
      return;
    }
    const values = rows.map((x) => Number(x.value));
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = Math.max(1e-9, max - min);
    const w = 300;
    const h = 92;
    const pad = 7;
    const points = values.map((v, i) => {
      const x = pad + (i * (w - pad * 2)) / Math.max(1, values.length - 1);
      const y = h - pad - ((v - min) / span) * (h - pad * 2);
      return [x.toFixed(2), y.toFixed(2)];
    });
    const line = points.map((p) => p.join(",")).join(" ");
    const area = `${pad},${h - pad} ${line} ${w - pad},${h - pad}`;
    root.innerHTML = `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-label="${metric} trend"><defs><linearGradient id="bcoCcGradient"><stop offset="0%" stop-color="#22d3ee"/><stop offset="100%" stop-color="#a5f3fc"/></linearGradient><linearGradient id="bcoCcArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#22d3ee" stop-opacity=".22"/><stop offset="100%" stop-color="#22d3ee" stop-opacity="0"/></linearGradient></defs><polygon class="bco-cc-chart-area" points="${area}"/><polyline class="bco-cc-chart-line" points="${line}"/></svg>`;
    setText("#ccChartMetric", metric.replace("_pct", " %"));
    setText("#ccChartRange", `${values[0]} → ${values[values.length - 1]}`);
    const trend = trends?.[metric];
    const delta = Number(trend?.delta);
    const t = $("#ccTrend");
    if (t && Number.isFinite(delta)) {
      t.textContent = `${delta > 0 ? "+" : ""}${delta}`;
      t.className = `bco-cc-trend ${delta > 0 ? "up" : delta < 0 ? "down" : "flat"}`;
    } else if (t) {
      t.textContent = "collecting";
      t.className = "bco-cc-trend flat";
    }
  }

  function render(payload) {
    const p = payload?.player || {};
    const profile = p.profile || {};
    const activity = p.activity || {};
    setText("#ccSummary", p.summary || profile.last_session_summary, "BLACK CROWN собирает доказательную историю игрока. Играй, отправляй результаты и VOD.");
    setText("#ccCoverage", `${Number(p.coverage || 0)}%`);
    setText("#ccMistakeCount", activity.recurring_mistakes ?? (p.top_mistakes || []).length);
    setText("#ccTrainingCount", activity.training_sessions ?? (p.training || []).length);
    setText("#ccProgressCount", activity.progression_events ?? (p.progression || []).length);
    setText("#ccBackend", `backend: ${activity.backend || "unknown"}`);
    setText("#ccGame", profile.game);
    setText("#ccInput", [profile.platform, profile.input].filter(Boolean).join(" / "));
    setText("#ccRank", profile.rank);
    setText("#ccKd", profile.kd);
    setText("#ccRole", profile.role || profile.bf6_class);
    setText("#ccGoal", profile.current_goal);
    setText("#ccFocus", profile.training_focus || profile.weekly_focus);
    setText("#ccVoice", [profile.voice, profile.difficulty, profile.tts_mode].filter(Boolean).join(" / "));
    renderMission(payload?.mission_control || null);
    renderScores(p.scores || {});
    renderMistakes(p.top_mistakes || []);
    renderTraining(p.training || []);
    renderVod(p.vod_reviews || []);
    renderChart(p.metric_series || {}, p.trends || {});
    const trust = $("#ccTrust");
    if (trust) {
      trust.classList.remove("warn");
      trust.querySelector("span").textContent = "Verified Telegram identity • server-authoritative mission state";
    }
  }

  function renderError(message) {
    const trust = $("#ccTrust");
    if (trust) {
      trust.classList.add("warn");
      trust.querySelector("span").textContent = message;
    }
    setText("#ccSummary", message);
  }

  function initData() {
    return String(safe(() => window.Telegram?.WebApp?.initData, "") || "").trim();
  }

  async function requestJson(url, options = {}) {
    const data = initData();
    if (!data) throw new Error("Открой Mini App из Telegram, чтобы использовать приватную Player Intelligence.");
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 14000);
    try {
      const response = await fetch(url, {
        method: options.method || "GET",
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          "X-Telegram-Init-Data": data,
          "X-BCO-Version": CLIENT_VERSION,
          ...(options.headers || {}),
        },
        body: options.body ? JSON.stringify(options.body) : undefined,
        cache: "no-store",
        signal: controller.signal,
      });
      const body = await response.json().catch(() => null);
      if (!response.ok || !body) {
        const error = new Error(body?.error || body?.detail || `HTTP ${response.status}`);
        error.payload = body;
        throw error;
      }
      return body;
    } finally {
      clearTimeout(timer);
    }
  }

  async function refresh(force) {
    if (loading || (loaded && !force)) return;
    loading = true;
    $("#ccLoader")?.classList.add("show");
    try {
      const body = await requestJson(API);
      if (!body?.ok) throw new Error("Command Center API unavailable");
      render(body);
      loaded = true;
      haptic("success");
    } catch (error) {
      renderError(error?.message || "Command Center temporarily unavailable");
      haptic("error");
    } finally {
      loading = false;
      $("#ccLoader")?.classList.remove("show");
    }
  }

  function setMissionBusy(active) {
    missionBusy = !!active;
    $("#ccMissionCard")?.classList.toggle("is-busy", missionBusy);
    renderMission(latestMissionControl);
  }

  async function missionAction(action, outcome = "reported") {
    if (missionBusy) return;
    const mission = latestMissionControl?.mission || {};
    const missionId = String(mission.id || "");
    if (!missionId) return;
    setMissionBusy(true);
    haptic("medium");
    try {
      const endpoint = action === "accept" ? MISSION_ACCEPT_API : MISSION_COMPLETE_API;
      const body = action === "accept"
        ? { mission_id: missionId }
        : { mission_id: missionId, outcome, metrics: {} };
      const response = await requestJson(endpoint, { method: "POST", body });
      latestMissionControl = response?.mission_control || latestMissionControl;
      renderMission(latestMissionControl);
      loaded = false;
      haptic("success");
      setTimeout(() => refresh(true), 180);
    } catch (error) {
      if (error?.payload?.mission_control) {
        latestMissionControl = error.payload.mission_control;
        renderMission(latestMissionControl);
      }
      renderError(`Mission action: ${error?.message || "temporarily unavailable"}`);
      haptic("error");
    } finally {
      setMissionBusy(false);
    }
  }

  function missionBrief() {
    const mission = latestMissionControl?.mission || {};
    const state = latestMissionControl?.state || {};
    const prompt = [
      "Разбери мою активную миссию BLACK CROWN OPS.",
      `Mission: ${mission.title || "calibration"}`,
      `Focus: ${mission.focus || state.dominant_focus || "unknown"}`,
      `Objective: ${mission.objective || "—"}`,
      `Match rule: ${mission.match_rule || "—"}`,
      `Success metric: ${mission.success_metric || "—"}`,
      "Дай: главный риск, правильное выполнение по шагам и что фиксировать после матча.",
    ].join("\n");

    const home = $('.nav-btn[data-tab="home"]');
    home?.click();
    setTimeout(() => {
      const input = $("#chatInputLive") || $("#chatInput");
      if (input) {
        input.value = prompt;
        input.focus();
        input.dispatchEvent(new Event("input", { bubbles: true }));
      } else {
        safe(() => window.BCO_APP?.sendToBot?.({ type: "one_line", text: prompt, profile: true }));
      }
    }, 140);
    haptic("selection");
  }

  mount();
  window.BCO_COMMAND_CENTER = {
    refresh,
    missionAction,
    missionBrief,
    version: "19.0.0",
  };
})();
