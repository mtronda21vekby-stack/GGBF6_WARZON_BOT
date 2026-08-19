/* BLACK CROWN OPS v45 — CROWN SESSION HOME */
(() => {
  "use strict";
  if (window.__BCO_SESSION_HOME_V45_LOADED__) return;
  window.__BCO_SESSION_HOME_V45_LOADED__ = true;

  const $ = (q, root = document) => root.querySelector(q);
  const locale = () => String(document.documentElement.lang || "en").toLowerCase().startsWith("ru") ? "ru" : "en";
  const t = (ru, en) => locale() === "ru" ? ru : en;
  const safe = (value, fallback = "—") => {
    const text = String(value ?? "").trim();
    return text || fallback;
  };

  function css() {
    if ($("#bcoSessionHomeCss")) return;
    const style = document.createElement("style");
    style.id = "bcoSessionHomeCss";
    style.textContent = `
      .bco-session-home{position:relative;overflow:hidden;margin:0 0 18px;padding:20px;border:1px solid rgba(240,203,119,.18);border-radius:22px;background:radial-gradient(circle at 82% 0%,rgba(216,177,91,.13),transparent 34%),linear-gradient(145deg,rgba(8,9,12,.985),rgba(20,22,27,.965));box-shadow:0 24px 70px rgba(0,0,0,.3)}
      .bco-session-home:before{content:"";position:absolute;inset:0;pointer-events:none;background:linear-gradient(115deg,transparent 0 44%,rgba(255,255,255,.025) 50%,transparent 57%)}
      .bco-sh-top{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;position:relative}.bco-sh-kicker{font-size:10px;letter-spacing:.18em;color:#d9bb79;opacity:.9}.bco-sh-title{margin:6px 0 0;font-size:27px;line-height:1.04;letter-spacing:-.035em}.bco-sh-sub{margin:8px 0 0;max-width:520px;font-size:12px;line-height:1.5;opacity:.62}.bco-sh-account{flex:0 0 auto;padding:7px 9px;border:1px solid rgba(255,255,255,.09);border-radius:999px;font-size:9px;letter-spacing:.11em;opacity:.7}
      .bco-sh-state{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;margin:18px 0}.bco-sh-cell{min-height:72px;padding:12px;border:1px solid rgba(255,255,255,.06);border-radius:14px;background:rgba(255,255,255,.027)}.bco-sh-cell span{display:block;margin-bottom:7px;font-size:8px;letter-spacing:.15em;opacity:.48}.bco-sh-cell strong{display:block;font-size:14px;line-height:1.25}.bco-sh-cell small{display:block;margin-top:4px;font-size:10px;line-height:1.35;opacity:.5}
      .bco-sh-meta{display:grid;grid-template-columns:1.15fr .85fr;gap:9px}.bco-sh-panel{padding:14px;border:1px solid rgba(255,255,255,.06);border-radius:15px;background:rgba(0,0,0,.12)}.bco-sh-panel>span{display:block;font-size:8px;letter-spacing:.15em;opacity:.48;margin-bottom:7px}.bco-sh-panel p{margin:0;font-size:12px;line-height:1.5;opacity:.78}.bco-sh-score{font-size:26px;font-weight:800;letter-spacing:-.04em}.bco-sh-score small{font-size:10px;font-weight:600;opacity:.42;letter-spacing:.05em}
      .bco-sh-mission{margin-top:10px;padding:15px;border:1px solid rgba(216,177,91,.16);border-radius:16px;background:linear-gradient(135deg,rgba(216,177,91,.07),rgba(255,255,255,.02))}.bco-sh-mission-head{display:flex;justify-content:space-between;gap:10px;align-items:center}.bco-sh-mission-head span{font-size:8px;letter-spacing:.16em;opacity:.52}.bco-sh-mission-head b{font-size:9px;letter-spacing:.09em;color:#d9bb79}.bco-sh-mission h3{margin:8px 0 5px;font-size:17px}.bco-sh-mission p{margin:0;font-size:12px;line-height:1.5;opacity:.72}
      .bco-sh-actions{display:grid;grid-template-columns:1fr auto;gap:9px;margin-top:13px}.bco-sh-primary,.bco-sh-secondary{min-height:44px;border-radius:13px;font-weight:800;letter-spacing:.045em}.bco-sh-primary{border:1px solid rgba(250,226,172,.28);background:linear-gradient(180deg,#f0d395,#cfaa60);color:#111216}.bco-sh-secondary{padding:0 14px;border:1px solid rgba(255,255,255,.09);background:rgba(255,255,255,.045);color:inherit}.bco-sh-status{margin-top:10px;font-size:9px;line-height:1.45;opacity:.42}
      @media(min-width:740px){.bco-sh-state{grid-template-columns:repeat(4,minmax(0,1fr))}.bco-session-home{padding:24px}.bco-sh-title{font-size:34px}}
    `;
    document.head.appendChild(style);
  }

  function set(id, value, fallback = "—") {
    const el = $(id);
    if (el) el.textContent = safe(value, fallback);
  }

  function shortId(value) {
    const text = safe(value, "");
    return text ? `${text.slice(0, 6)}…${text.slice(-4)}` : t("НЕ СВЯЗАН", "UNLINKED");
  }

  function stateLabel(op) {
    if (!op || typeof op !== "object") return "CALIBRATING";
    return safe(op.readiness || op.session?.orchestrator_stage || "CALIBRATING").toUpperCase();
  }

  function render(session) {
    if (!session) return false;
    const identity = session.identity || {};
    const profile = session.profile || {};
    const op = session.operator_twin || {};
    const mission = session.mission || session.next_mission || {};
    const meta = session.personal_meta || {};
    const entitlement = session.entitlement || {};

    set("#bcoShAccount", `CROWN ${shortId(identity.black_crown_user_id)}`);
    set("#bcoShState", stateLabel(op));
    set("#bcoShGame", profile.game || t("КАЛИБРОВКА", "CALIBRATING"));
    set("#bcoShMode", [profile.mode, profile.input || profile.platform].filter(Boolean).join(" • ") || "—");
    set("#bcoShPremium", entitlement.premium ? "PREMIUM" : "STANDARD");
    set("#bcoShPremiumSub", entitlement.state === "resolved" ? t("сервер подтверждён", "server verified") : t("проверка недоступна", "authority unavailable"));
    set("#bcoShCoverage", `${Number(meta.coverage || 0)}%`);
    set("#bcoShSummary", meta.summary || t("CROWN ещё собирает данные, чтобы построить персональную модель.", "CROWN is still collecting evidence for your personal model."));
    set("#bcoShMissionTitle", mission.title || t("КАЛИБРОВКА", "CALIBRATING"));
    set("#bcoShMissionObjective", mission.objective || t("Собираю достаточно evidence для измеримой цели.", "Collecting enough evidence for a measurable objective."));
    set("#bcoShMissionStatus", safe(mission.status || op.session?.phase || "PRE_SESSION").toUpperCase());
    set("#bcoShStatus", identity.canonical
      ? t("Единый CROWN аккаунт подтверждён. Bot, Mini App и Website используют одну identity authority.", "Unified CROWN account verified. Bot, Mini App and Website share one identity authority.")
      : t("Telegram подтверждён, canonical identity ещё калибруется.", "Telegram verified; canonical identity is still calibrating."));
    return true;
  }

  function openOperator() {
    try { window.Telegram?.WebApp?.HapticFeedback?.selectionChanged(); } catch (_) {}
    const button = $("#bcoOperatorNav");
    if (button) button.click();
    else $("#tab-operator-v25")?.scrollIntoView({ behavior: "smooth", block: "start" });
    window.BCO_OPERATOR?.refresh?.(true);
  }

  async function prepareSession() {
    const btn = $("#bcoShPrepare");
    if (btn) btn.disabled = true;
    set("#bcoShStatus", t("Синхронизирую Operator Twin, Personal Meta и mission…", "Synchronizing Operator Twin, Personal Meta and mission…"));
    try {
      const session = await window.BCO_CROWN_SESSION?.refresh?.(true);
      render(session);
      try { window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred?.("success"); } catch (_) {}
      openOperator();
    } catch (error) {
      set("#bcoShStatus", safe(error?.message, t("CROWN SESSION недоступна.", "CROWN SESSION unavailable.")));
      try { window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred?.("error"); } catch (_) {}
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  function mount() {
    const home = $("#tab-home");
    if (!home || $("#bcoSessionHomeV45")) return false;
    css();
    const section = document.createElement("section");
    section.id = "bcoSessionHomeV45";
    section.className = "bco-session-home";
    section.innerHTML = `
      <div class="bco-sh-top">
        <div><div class="bco-sh-kicker">CROWN SESSION // LIVE PROFILE</div><h1 class="bco-sh-title">${t("С возвращением, оператор.", "Welcome back, Operator.")}</h1><p class="bco-sh-sub">${t("Один аккаунт. Один Operator Twin. Одна текущая миссия между Telegram, Mini App и BlackCrown.", "One account. One Operator Twin. One current mission across Telegram, Mini App and BlackCrown.")}</p></div>
        <div class="bco-sh-account" id="bcoShAccount">CROWN —</div>
      </div>
      <div class="bco-sh-state">
        <div class="bco-sh-cell"><span>${t("CURRENT STATE", "CURRENT STATE")}</span><strong id="bcoShState">SYNCING</strong><small>${t("operator readiness", "operator readiness")}</small></div>
        <div class="bco-sh-cell"><span>${t("WORLD", "WORLD")}</span><strong id="bcoShGame">—</strong><small id="bcoShMode">—</small></div>
        <div class="bco-sh-cell"><span>${t("ACCESS", "ACCESS")}</span><strong id="bcoShPremium">SYNCING</strong><small id="bcoShPremiumSub">server authority</small></div>
        <div class="bco-sh-cell"><span>${t("PERSONAL META", "PERSONAL META")}</span><strong id="bcoShCoverage">0%</strong><small>${t("evidence coverage", "evidence coverage")}</small></div>
      </div>
      <div class="bco-sh-meta">
        <div class="bco-sh-panel"><span>${t("CROWN READ", "CROWN READ")}</span><p id="bcoShSummary">${t("Синхронизация…", "Synchronizing…")}</p></div>
        <div class="bco-sh-panel"><span>${t("CONFIDENCE MODEL", "CONFIDENCE MODEL")}</span><div class="bco-sh-score"><span id="bcoShCoverage">0%</span> <small>KNOWN</small></div></div>
      </div>
      <div class="bco-sh-mission"><div class="bco-sh-mission-head"><span>${t("CURRENT MISSION", "CURRENT MISSION")}</span><b id="bcoShMissionStatus">PRE_SESSION</b></div><h3 id="bcoShMissionTitle">CALIBRATING</h3><p id="bcoShMissionObjective"></p></div>
      <div class="bco-sh-actions"><button class="bco-sh-primary" id="bcoShPrepare" type="button">${t("PREPARE SESSION", "PREPARE SESSION")}</button><button class="bco-sh-secondary" id="bcoShDossier" type="button">${t("ДОСЬЕ", "DOSSIER")}</button></div>
      <div class="bco-sh-status" id="bcoShStatus">${t("Ожидаю trusted Telegram identity…", "Waiting for trusted Telegram identity…")}</div>`;
    home.prepend(section);
    $("#bcoShPrepare")?.addEventListener("click", prepareSession);
    $("#bcoShDossier")?.addEventListener("click", openOperator);

    const existing = window.BCO_CROWN_SESSION?.getSnapshot?.();
    if (existing) render(existing);
    window.addEventListener("bco:crown-session", (event) => render(event.detail));
    window.BCO_CROWN_SESSION?.refresh?.(false).then(render).catch(() => {});
    return true;
  }

  if (!mount()) {
    let tries = 0;
    const timer = window.setInterval(() => {
      tries += 1;
      if (mount() || tries > 30) window.clearInterval(timer);
    }, 200);
  }

  window.BCO_SESSION_HOME = { render, prepareSession };
})();
