/* BLACK CROWN OPS v45 — CROWN SESSION HOME + WAR ROOM BRIEFING */
(() => {
  "use strict";
  if (window.__BCO_SESSION_HOME_V45_LOADED__) return;
  window.__BCO_SESSION_HOME_V45_LOADED__ = true;

  const $ = (q, root = document) => root.querySelector(q);
  const locale = () => String(document.documentElement.lang || "en").toLowerCase().startsWith("ru") ? "ru" : "en";
  const t = (ru, en) => locale() === "ru" ? ru : en;
  const safe = (value, fallback = "—") => { const text = String(value ?? "").trim(); return text || fallback; };
  const initData = () => { try { return String(window.Telegram?.WebApp?.initData || "").trim(); } catch (_) { return ""; } };

  function css() {
    if ($("#bcoSessionHomeCss")) return;
    const style = document.createElement("style");
    style.id = "bcoSessionHomeCss";
    style.textContent = `
      .bco-session-home{position:relative;overflow:hidden;margin:0 0 18px;padding:20px;border:1px solid rgba(240,203,119,.18);border-radius:22px;background:radial-gradient(circle at 82% 0%,rgba(216,177,91,.13),transparent 34%),linear-gradient(145deg,rgba(8,9,12,.985),rgba(20,22,27,.965));box-shadow:0 24px 70px rgba(0,0,0,.3)}
      .bco-sh-top{display:flex;align-items:flex-start;justify-content:space-between;gap:14px}.bco-sh-kicker{font-size:10px;letter-spacing:.18em;color:#d9bb79}.bco-sh-title{margin:6px 0 0;font-size:27px;line-height:1.04}.bco-sh-sub{margin:8px 0 0;max-width:520px;font-size:12px;line-height:1.5;opacity:.62}.bco-sh-account{padding:7px 9px;border:1px solid rgba(255,255,255,.09);border-radius:999px;font-size:9px;letter-spacing:.11em;opacity:.7;white-space:nowrap}
      .bco-sh-state{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;margin:18px 0}.bco-sh-cell{min-height:72px;padding:12px;border:1px solid rgba(255,255,255,.06);border-radius:14px;background:rgba(255,255,255,.027)}.bco-sh-cell span,.bco-sh-panel>span,.bco-sh-brief>span{display:block;margin-bottom:7px;font-size:8px;letter-spacing:.15em;opacity:.48}.bco-sh-cell strong{display:block;font-size:14px}.bco-sh-cell small{display:block;margin-top:4px;font-size:10px;opacity:.5}
      .bco-sh-meta{display:grid;grid-template-columns:1.15fr .85fr;gap:9px}.bco-sh-panel,.bco-sh-brief{padding:14px;border:1px solid rgba(255,255,255,.06);border-radius:15px;background:rgba(0,0,0,.12)}.bco-sh-panel p,.bco-sh-brief p{margin:0;font-size:12px;line-height:1.5;opacity:.78}.bco-sh-score{font-size:26px;font-weight:800}
      .bco-sh-mission{margin-top:10px;padding:15px;border:1px solid rgba(216,177,91,.16);border-radius:16px;background:linear-gradient(135deg,rgba(216,177,91,.07),rgba(255,255,255,.02))}.bco-sh-mission-head{display:flex;justify-content:space-between}.bco-sh-mission-head span{font-size:8px;letter-spacing:.16em;opacity:.52}.bco-sh-mission-head b{font-size:9px;color:#d9bb79}.bco-sh-mission h3{margin:8px 0 5px;font-size:17px}.bco-sh-mission p{margin:0;font-size:12px;line-height:1.5;opacity:.72}
      .bco-sh-briefing{display:none;margin-top:10px;gap:9px}.bco-sh-briefing.active{display:grid}.bco-sh-brief-grid{display:grid;grid-template-columns:1fr 1fr;gap:9px}.bco-sh-focus{margin:0;padding-left:17px;font-size:12px;line-height:1.55;opacity:.8}.bco-sh-intel{font-size:11px;line-height:1.5;opacity:.72}.bco-sh-source{margin-top:7px;font-size:9px;opacity:.42;word-break:break-word}.bco-sh-actions{display:grid;grid-template-columns:1fr auto;gap:9px;margin-top:13px}.bco-sh-primary,.bco-sh-secondary{min-height:44px;border-radius:13px;font-weight:800;letter-spacing:.045em}.bco-sh-primary{border:1px solid rgba(250,226,172,.28);background:linear-gradient(180deg,#f0d395,#cfaa60);color:#111216}.bco-sh-secondary{padding:0 14px;border:1px solid rgba(255,255,255,.09);background:rgba(255,255,255,.045);color:inherit}.bco-sh-status{margin-top:10px;font-size:9px;line-height:1.45;opacity:.42}
      @media(min-width:740px){.bco-sh-state{grid-template-columns:repeat(4,minmax(0,1fr))}.bco-session-home{padding:24px}.bco-sh-title{font-size:34px}}
    `;
    document.head.appendChild(style);
  }

  function set(id, value, fallback = "—") { const el = $(id); if (el) el.textContent = safe(value, fallback); }
  function shortId(value) { const text = safe(value, ""); return text ? `${text.slice(0, 6)}…${text.slice(-4)}` : "UNLINKED"; }
  function stateLabel(op) { return safe(op?.readiness || op?.session?.orchestrator_stage || "CALIBRATING").toUpperCase(); }

  function render(session) {
    if (!session) return false;
    const identity = session.identity || {}, profile = session.profile || {}, op = session.operator_twin || {}, mission = session.mission || session.next_mission || {}, meta = session.personal_meta || {}, entitlement = session.entitlement || {};
    const coverage = `${Number(meta.coverage || 0)}%`;
    set("#bcoShAccount", `CROWN ${shortId(identity.black_crown_user_id)}`); set("#bcoShState", stateLabel(op)); set("#bcoShGame", profile.game || "CALIBRATING"); set("#bcoShMode", [profile.mode, profile.input || profile.platform].filter(Boolean).join(" • ") || "—");
    set("#bcoShPremium", entitlement.premium ? "PREMIUM" : "STANDARD"); set("#bcoShPremiumSub", entitlement.state === "resolved" ? t("сервер подтверждён", "server verified") : t("проверка недоступна", "authority unavailable")); set("#bcoShCoverage", coverage); set("#bcoShKnown", coverage);
    set("#bcoShSummary", meta.summary || t("CROWN ещё собирает данные.", "CROWN is still collecting evidence.")); set("#bcoShMissionTitle", mission.title || "CALIBRATING"); set("#bcoShMissionObjective", mission.objective || t("Собираю evidence для измеримой цели.", "Collecting evidence for a measurable objective.")); set("#bcoShMissionStatus", safe(mission.status || op.session?.phase || "PRE_SESSION").toUpperCase());
    set("#bcoShStatus", identity.canonical ? t("Единый CROWN аккаунт подтверждён.", "Unified CROWN account verified.") : t("Canonical identity калибруется.", "Canonical identity is calibrating.")); return true;
  }

  function renderBriefing(data) {
    if (!data) return false;
    $("#bcoShBriefing")?.classList.add("active");
    const focus = Array.isArray(data.session_focus) ? data.session_focus : [];
    const focusRoot = $("#bcoShFocus"); if (focusRoot) focusRoot.innerHTML = focus.map((x) => `<li></li>`).join(""); if (focusRoot) Array.from(focusRoot.children).forEach((li, i) => li.textContent = safe(focus[i]));
    const intel = data.official_intel || {}; const facts = Array.isArray(intel.facts) ? intel.facts : [];
    set("#bcoShIntelState", `${safe(intel.confidence, "UNKNOWN")} • ${safe(intel.last_updated, "NO DATE")}`);
    set("#bcoShIntel", facts[1] || facts[0] || t("Свежие официальные данные недоступны — CROWN не будет притворяться, что мета подтверждена.", "Fresh official evidence unavailable — CROWN will not pretend the meta is verified."));
    set("#bcoShIntelSource", intel.source || t("Нет verified current source", "No verified current source"));
    const squad = data.squad_context || {}; set("#bcoShSquad", squad.status === "UNKNOWN" ? t("UNKNOWN — trusted squad source отсутствует", "UNKNOWN — no trusted squad source") : squad.status);
    set("#bcoShBriefMission", data.mission?.title || "CALIBRATING");
    set("#bcoShStatus", t("WAR ROOM briefing готов. Official intel и player evidence разделены по authority.", "WAR ROOM briefing ready. Official intel and player evidence remain authority-separated."));
    return true;
  }

  function openOperator() { try { window.Telegram?.WebApp?.HapticFeedback?.selectionChanged(); } catch (_) {} const button = $("#bcoOperatorNav"); if (button) button.click(); else $("#tab-operator-v25")?.scrollIntoView({behavior:"smooth"}); window.BCO_OPERATOR?.refresh?.(true); }

  async function prepareSession() {
    const btn = $("#bcoShPrepare"); if (btn) btn.disabled = true;
    set("#bcoShStatus", t("Проверяю Operator Twin, mission и официальные patch notes…", "Checking Operator Twin, mission and official patch notes…"));
    try {
      const init = initData(); if (!init) throw new Error("trusted_telegram_context_required");
      const response = await fetch("/webapp/api/crown-session/prepare", {method:"POST",headers:{"X-Telegram-Init-Data":init,accept:"application/json"},cache:"no-store",credentials:"same-origin"});
      const payload = await response.json().catch(() => null); if (!response.ok || !payload?.ok || !payload?.data) throw new Error(payload?.detail || `prepare_session_http_${response.status}`);
      renderBriefing(payload.data); await window.BCO_CROWN_SESSION?.refresh?.(true).then(render).catch(() => {});
      try { window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred?.("success"); } catch (_) {}
    } catch (error) { set("#bcoShStatus", safe(error?.message, t("PREPARE SESSION недоступна.", "PREPARE SESSION unavailable."))); try { window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred?.("error"); } catch (_) {} }
    finally { if (btn) btn.disabled = false; }
  }

  function mount() {
    const home = $("#tab-home"); if (!home || $("#bcoSessionHomeV45")) return false; css();
    const section = document.createElement("section"); section.id = "bcoSessionHomeV45"; section.className = "bco-session-home";
    section.innerHTML = `<div class="bco-sh-top"><div><div class="bco-sh-kicker">CROWN SESSION // LIVE PROFILE</div><h1 class="bco-sh-title">${t("С возвращением, оператор.", "Welcome back, Operator.")}</h1><p class="bco-sh-sub">${t("Один аккаунт. Один Operator Twin. Одна миссия.", "One account. One Operator Twin. One mission.")}</p></div><div class="bco-sh-account" id="bcoShAccount">CROWN —</div></div>
    <div class="bco-sh-state"><div class="bco-sh-cell"><span>CURRENT STATE</span><strong id="bcoShState">SYNCING</strong><small>operator readiness</small></div><div class="bco-sh-cell"><span>WORLD</span><strong id="bcoShGame">—</strong><small id="bcoShMode">—</small></div><div class="bco-sh-cell"><span>ACCESS</span><strong id="bcoShPremium">SYNCING</strong><small id="bcoShPremiumSub">server authority</small></div><div class="bco-sh-cell"><span>PERSONAL META</span><strong id="bcoShCoverage">0%</strong><small>evidence coverage</small></div></div>
    <div class="bco-sh-meta"><div class="bco-sh-panel"><span>CROWN READ</span><p id="bcoShSummary">Synchronizing…</p></div><div class="bco-sh-panel"><span>CONFIDENCE MODEL</span><div class="bco-sh-score"><span id="bcoShKnown">0%</span></div></div></div>
    <div class="bco-sh-mission"><div class="bco-sh-mission-head"><span>CURRENT MISSION</span><b id="bcoShMissionStatus">PRE_SESSION</b></div><h3 id="bcoShMissionTitle">CALIBRATING</h3><p id="bcoShMissionObjective"></p></div>
    <div class="bco-sh-briefing" id="bcoShBriefing"><div class="bco-sh-brief-grid"><div class="bco-sh-brief"><span>SESSION FOCUS</span><ul class="bco-sh-focus" id="bcoShFocus"></ul></div><div class="bco-sh-brief"><span>OFFICIAL INTEL</span><b id="bcoShIntelState">UNKNOWN</b><p class="bco-sh-intel" id="bcoShIntel"></p><div class="bco-sh-source" id="bcoShIntelSource"></div></div><div class="bco-sh-brief"><span>SQUAD CONTEXT</span><p id="bcoShSquad">UNKNOWN</p></div><div class="bco-sh-brief"><span>MISSION LOCK</span><p id="bcoShBriefMission">CALIBRATING</p></div></div></div>
    <div class="bco-sh-actions"><button class="bco-sh-primary" id="bcoShPrepare" type="button">PREPARE SESSION</button><button class="bco-sh-secondary" id="bcoShDossier" type="button">DOSSIER</button></div><div class="bco-sh-status" id="bcoShStatus">Waiting for trusted Telegram identity…</div>`;
    home.prepend(section); $("#bcoShPrepare")?.addEventListener("click", prepareSession); $("#bcoShDossier")?.addEventListener("click", openOperator);
    const existing = window.BCO_CROWN_SESSION?.getSnapshot?.(); if (existing) render(existing); window.addEventListener("bco:crown-session", (event) => render(event.detail)); window.BCO_CROWN_SESSION?.refresh?.(false).then(render).catch(() => {}); return true;
  }

  if (!mount()) { let tries = 0; const timer = window.setInterval(() => { tries += 1; if (mount() || tries > 30) window.clearInterval(timer); }, 200); }
  window.BCO_SESSION_HOME = { render, renderBriefing, prepareSession };
})();
