/* BLACK CROWN OPS — Premium Command Center v6 */
(() => {
  "use strict";

  const BUILD = window.__BCO_BUILD__ || "dev";
  const API = "/webapp/api/intelligence";
  const $ = (q) => document.querySelector(q);
  const safe = (fn) => { try { return fn(); } catch (_) { return undefined; } };

  let loaded = false;
  let loading = false;

  function injectCss() {
    if (document.querySelector('link[data-bco-command-center]')) return;
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.dataset.bcoCommandCenter = "1";
    link.href = `/webapp/command-center.css?build=${encodeURIComponent(BUILD)}`;
    document.head.appendChild(link);
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
          <div class="bco-cc-eyebrow">PLAYER INTELLIGENCE • SERVER VERIFIED</div>
          <div class="bco-cc-title">Premium Command Center</div>
          <div class="bco-cc-summary" id="ccSummary">Загружаю долгосрочный профиль игрока…</div>
          <div class="bco-cc-status" id="ccTrust"><i></i><span>Telegram identity required</span></div>
          <div class="bco-cc-actions">
            <button class="bco-cc-btn primary" id="ccRefresh" type="button">↻ Refresh intelligence</button>
            <button class="bco-cc-btn" id="ccCoach" type="button">🎯 Coach next focus</button>
          </div>
        </div>

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
        <div class="bco-cc-loader" id="ccLoader">Synchronizing server intelligence…</div>
      </div>`;

    if (foot) main.insertBefore(section, foot); else main.appendChild(section);

    const button = document.createElement("button");
    button.className = "nav-btn";
    button.dataset.tab = "intel";
    button.type = "button";
    button.setAttribute("aria-selected", "false");
    button.innerHTML = '<span class="nav-ico">◈</span><span class="nav-txt">Intel</span>';
    const settings = nav.querySelector('[data-tab="settings"]');
    if (settings) nav.insertBefore(button, settings); else nav.appendChild(button);
    nav.classList.add("bco-cc-six");

    $("#ccRefresh")?.addEventListener("click", () => refresh(true));
    $("#ccCoach")?.addEventListener("click", () => {
      const send = window.BCO_APP?.sendToBot;
      if (typeof send === "function") send({ type: "nav", target: "training" });
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
    if (!Array.isArray(items) || !items.length) return empty(root, "Нет подтверждённых повторяющихся ошибок. Нужны игровые отчёты/VOD.");
    root.innerHTML = "";
    items.slice(0, 8).forEach((item) => {
      const row = document.createElement("div");
      row.className = "bco-cc-item";
      const main = document.createElement("div"); main.className = "bco-cc-item-main";
      const title = document.createElement("div"); title.className = "bco-cc-item-title"; title.textContent = item.label || "Mistake";
      const meta = document.createElement("div"); meta.className = "bco-cc-item-meta"; meta.textContent = item.last_seen ? `last: ${fmtTime(item.last_seen)}` : "evidence-backed";
      main.append(title, meta);
      const count = document.createElement("div"); count.className = "bco-cc-count"; count.textContent = `×${Number(item.count || 0)}`;
      row.append(main, count); root.appendChild(row);
    });
  }

  function renderTraining(items) {
    const root = $("#ccTraining");
    if (!root) return;
    if (!Array.isArray(items) || !items.length) return empty(root, "Тренировочная история пока пустая.");
    root.innerHTML = "";
    items.slice(0, 8).forEach((item) => {
      const row = document.createElement("div"); row.className = "bco-cc-item";
      const main = document.createElement("div"); main.className = "bco-cc-item-main";
      const title = document.createElement("div"); title.className = "bco-cc-item-title"; title.textContent = String(item.focus || "hybrid").toUpperCase();
      const meta = document.createElement("div"); meta.className = "bco-cc-item-meta"; meta.textContent = [item.game, fmtTime(item.at)].filter(Boolean).join(" • ");
      main.append(title, meta); row.append(main); root.appendChild(row);
    });
  }

  function renderVod(items) {
    const root = $("#ccVod");
    if (!root) return;
    if (!Array.isArray(items) || !items.length) return empty(root, "VOD intelligence появится после первого видео-разбора.");
    root.innerHTML = "";
    items.slice(0, 5).forEach((item) => {
      const row = document.createElement("div"); row.className = "bco-cc-item";
      const main = document.createElement("div"); main.className = "bco-cc-item-main";
      const title = document.createElement("div"); title.className = "bco-cc-item-title"; title.textContent = [item.game || "VOD", fmtTime(item.at)].filter(Boolean).join(" • ");
      const summary = document.createElement("div"); summary.className = "bco-cc-vod-summary"; summary.textContent = item.summary || "Sampled-frame analysis stored.";
      const meta = document.createElement("div"); meta.className = "bco-cc-item-meta"; meta.textContent = (item.confirmed_mistakes || []).length ? `confirmed: ${(item.confirmed_mistakes || []).join(" · ")}` : "no high-confidence recurring mistake";
      main.append(title, summary, meta); row.append(main); root.appendChild(row);
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
      setText("#ccChartMetric", "waiting for match data"); setText("#ccChartRange", "—"); setText("#ccTrend", "—");
      return;
    }
    const values = rows.map((x) => Number(x.value));
    const min = Math.min(...values), max = Math.max(...values), span = Math.max(1e-9, max - min);
    const w = 300, h = 92, pad = 7;
    const points = values.map((v, i) => {
      const x = pad + (i * (w - pad * 2)) / Math.max(1, values.length - 1);
      const y = h - pad - ((v - min) / span) * (h - pad * 2);
      return [x.toFixed(2), y.toFixed(2)];
    });
    const line = points.map((p) => p.join(",")).join(" ");
    const area = `${pad},${h-pad} ${line} ${w-pad},${h-pad}`;
    root.innerHTML = `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-label="${metric} trend"><defs><linearGradient id="bcoCcGradient"><stop offset="0%" stop-color="#8b5cf6"/><stop offset="100%" stop-color="#22d3ee"/></linearGradient><linearGradient id="bcoCcArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#8b5cf6" stop-opacity=".20"/><stop offset="100%" stop-color="#22d3ee" stop-opacity="0"/></linearGradient></defs><polygon class="bco-cc-chart-area" points="${area}"/><polyline class="bco-cc-chart-line" points="${line}"/></svg>`;
    setText("#ccChartMetric", metric.replace("_pct", " %"));
    setText("#ccChartRange", `${values[0]} → ${values[values.length - 1]}`);
    const trend = trends?.[metric];
    const delta = Number(trend?.delta);
    const t = $("#ccTrend");
    if (t && Number.isFinite(delta)) {
      t.textContent = `${delta > 0 ? "+" : ""}${delta}`;
      t.className = `bco-cc-trend ${delta > 0 ? "up" : delta < 0 ? "down" : "flat"}`;
    } else if (t) { t.textContent = "collecting"; t.className = "bco-cc-trend flat"; }
  }

  function render(payload) {
    const p = payload?.player || {};
    const profile = p.profile || {}, activity = p.activity || {};
    setText("#ccSummary", p.summary || profile.last_session_summary, "BLACK CROWN ещё собирает доказательную историю игрока. Играй, отправляй результаты и VOD.");
    setText("#ccCoverage", `${Number(p.coverage || 0)}%`);
    setText("#ccMistakeCount", activity.recurring_mistakes ?? (p.top_mistakes || []).length);
    setText("#ccTrainingCount", activity.training_sessions ?? (p.training || []).length);
    setText("#ccProgressCount", activity.progression_events ?? (p.progression || []).length);
    setText("#ccBackend", `backend: ${activity.backend || "unknown"}`);
    setText("#ccGame", profile.game); setText("#ccInput", [profile.platform, profile.input].filter(Boolean).join(" / "));
    setText("#ccRank", profile.rank); setText("#ccKd", profile.kd); setText("#ccRole", profile.role || profile.bf6_class);
    setText("#ccGoal", profile.current_goal); setText("#ccFocus", profile.training_focus || profile.weekly_focus);
    setText("#ccVoice", [profile.voice, profile.difficulty, profile.tts_mode].filter(Boolean).join(" / "));
    renderScores(p.scores || {}); renderMistakes(p.top_mistakes || []); renderTraining(p.training || []); renderVod(p.vod_reviews || []); renderChart(p.metric_series || {}, p.trends || {});
    const trust = $("#ccTrust");
    if (trust) { trust.classList.remove("warn"); trust.querySelector("span").textContent = "Verified Telegram identity • server-authoritative data"; }
  }

  function renderError(message) {
    const trust = $("#ccTrust");
    if (trust) { trust.classList.add("warn"); trust.querySelector("span").textContent = message; }
    setText("#ccSummary", message);
  }

  async function refresh(force) {
    if (loading || (loaded && !force)) return;
    const initData = String(safe(() => window.Telegram?.WebApp?.initData) || "").trim();
    if (!initData) return renderError("Открой Mini App из Telegram, чтобы загрузить приватную Player Intelligence.");
    loading = true; $("#ccLoader")?.classList.add("show");
    const ctrl = new AbortController(); const timer = setTimeout(() => ctrl.abort(), 12000);
    try {
      const res = await fetch(API, { method: "GET", headers: { "X-Telegram-Init-Data": initData, "X-BCO-Version": "command-center-6.0" }, cache: "no-store", signal: ctrl.signal });
      const body = await res.json().catch(() => null);
      if (!res.ok || !body?.ok) throw new Error(res.status === 401 ? "Telegram identity verification failed" : "Command Center API unavailable");
      render(body); loaded = true;
    } catch (e) { renderError(e?.message || "Command Center temporarily unavailable"); }
    finally { clearTimeout(timer); loading = false; $("#ccLoader")?.classList.remove("show"); }
  }

  mount();
  window.BCO_COMMAND_CENTER = { refresh };
})();
