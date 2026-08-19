/* BLACK CROWN OPS v45 — CROWN SESSION driven WAR ROOM */
(() => {
  "use strict";
  if (window.__BCO_WAR_ROOM_V44_LOADED__) return;
  window.__BCO_WAR_ROOM_V44_LOADED__ = true;

  const $ = (q, root = document) => root.querySelector(q);
  const locale = () => String(document.documentElement.lang || "en").toLowerCase().startsWith("ru") ? "ru" : "en";
  const t = (ru, en) => locale() === "ru" ? ru : en;
  const safe = (value, fallback = "—") => {
    const text = String(value ?? "").trim();
    return text || fallback;
  };

  function css() {
    if ($("#bcoWarRoomCss")) return;
    const style = document.createElement("style");
    style.id = "bcoWarRoomCss";
    style.textContent = `
      .bco-war-room{margin:0 0 18px;padding:18px;border:1px solid rgba(255,255,255,.09);border-radius:18px;background:linear-gradient(145deg,rgba(12,14,17,.97),rgba(24,27,31,.94));box-shadow:0 18px 50px rgba(0,0,0,.18)}
      .bco-war-room__top{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.bco-war-room__kicker{font-size:11px;letter-spacing:.15em;opacity:.62}.bco-war-room h2{margin:5px 0 0;font-size:22px;letter-spacing:-.02em}.bco-war-room__state{font-size:11px;letter-spacing:.08em;padding:7px 9px;border:1px solid rgba(255,255,255,.1);border-radius:999px;white-space:nowrap}
      .bco-war-room__identity{display:flex;gap:8px;flex-wrap:wrap;margin:13px 0 0}.bco-war-room__badge{font-size:9px;letter-spacing:.1em;padding:6px 8px;border:1px solid rgba(255,255,255,.08);border-radius:999px;background:rgba(255,255,255,.025)}.bco-war-room__badge.active{border-color:rgba(106,202,255,.24);color:#9fdcff}.bco-war-room__badge.premium{border-color:rgba(235,200,112,.3);color:#eed28e}
      .bco-war-room__grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;margin:16px 0}.bco-war-room__cell{padding:11px 12px;background:rgba(255,255,255,.035);border:1px solid rgba(255,255,255,.055);border-radius:12px}.bco-war-room__cell span{display:block;font-size:9px;letter-spacing:.13em;opacity:.5;margin-bottom:5px}.bco-war-room__cell strong{display:block;font-size:13px;line-height:1.25}
      .bco-war-room__meta{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin:0 0 14px}.bco-war-room__meta article{padding:10px 12px;border-radius:12px;background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.05)}.bco-war-room__meta small{display:block;font-size:9px;letter-spacing:.12em;opacity:.48;margin-bottom:5px}.bco-war-room__meta strong{font-size:13px}.bco-war-room__meta p{font-size:11px;line-height:1.35;opacity:.66;margin:5px 0 0}
      .bco-war-room__mission{padding-top:13px;border-top:1px solid rgba(255,255,255,.07)}.bco-war-room__mission small{font-size:9px;letter-spacing:.13em;opacity:.52}.bco-war-room__mission h3{margin:6px 0 5px;font-size:16px}.bco-war-room__mission p{margin:0;line-height:1.45;opacity:.78;font-size:13px}.bco-war-room__truth{margin-top:12px;font-size:10px;line-height:1.4;opacity:.48}.bco-war-room__open{margin-top:14px;width:100%;padding:11px 13px;border:0;border-radius:11px;background:rgba(255,255,255,.94);color:#0c0d0f;font-weight:700;letter-spacing:.04em}.bco-war-room__open:active{transform:translateY(1px)}
      @media (min-width:740px){.bco-war-room__grid{grid-template-columns:repeat(4,minmax(0,1fr))}}
    `;
    document.head.appendChild(style);
  }

  function set(id, value, fallback = "—") {
    const el = $(id);
    if (el) el.textContent = safe(value, fallback);
  }

  function shortId(value) {
    const text = String(value || "").trim();
    return text ? `${text.slice(0, 8)}…${text.slice(-4)}` : "UNRESOLVED";
  }

  function crownSession() {
    return window.BCO_CROWN_SESSION?.getSnapshot?.() || null;
  }

  function operatorData() {
    const session = crownSession();
    if (session?.operator_twin) return session.operator_twin;
    return window.BCO_OPERATOR?.getSnapshot?.() || null;
  }

  function render() {
    const crown = crownSession();
    const data = operatorData();
    if (!data && !crown) return false;

    const op = data?.operator || {};
    const mission = crown?.mission || data?.mission || {};
    const session = data?.session || {};
    const identity = crown?.identity || {};
    const meta = crown?.personal_meta || {};
    const entitlement = crown?.entitlement || {};
    const profile = crown?.profile || {};

    set("#bcoWarRoomState", session.phase || "PRE_SESSION");
    set("#bcoWarRoomReadiness", op.readiness || "CALIBRATING");
    set("#bcoWarRoomRisk", op.risk || "UNKNOWN");
    set("#bcoWarRoomConfidence", op.confidence || "UNKNOWN");
    set("#bcoWarRoomMomentum", op.session_momentum || "UNKNOWN");
    set("#bcoWarRoomMission", mission.title || t("КАЛИБРОВКА", "CALIBRATING"));
    set("#bcoWarRoomObjective", mission.objective || t("Собираю достаточно данных для измеримой цели.", "Collecting enough evidence for a measurable objective."));
    set("#bcoWarRoomAccount", shortId(identity.black_crown_user_id));
    set("#bcoWarRoomGame", profile.game || "—");
    set("#bcoWarRoomCoverage", `${Number(meta.coverage || 0)}%`);
    set("#bcoWarRoomMetaSummary", meta.summary || t("Недостаточно подтверждённых данных.", "Not enough verified evidence yet."));

    const accountBadge = $("#bcoWarRoomIdentityBadge");
    if (accountBadge) {
      accountBadge.textContent = identity.canonical ? "CROWN ID // ACTIVE" : "CROWN ID // CALIBRATING";
      accountBadge.classList.toggle("active", identity.canonical === true);
    }
    const premiumBadge = $("#bcoWarRoomPremiumBadge");
    if (premiumBadge) {
      premiumBadge.textContent = entitlement.premium ? "PREMIUM // ACTIVE" : "PREMIUM // STANDARD";
      premiumBadge.classList.toggle("premium", entitlement.premium === true);
    }
    return true;
  }

  async function refresh() {
    try { await window.BCO_CROWN_SESSION?.refresh?.(true); } catch (_) {}
    try { await window.BCO_OPERATOR?.refresh?.(true); } catch (_) {}
    render();
  }

  function mount() {
    const operator = $("#tab-operator-v25");
    if (!operator || $("#bcoWarRoomV44")) return false;
    css();
    const card = document.createElement("section");
    card.id = "bcoWarRoomV44";
    card.className = "bco-war-room";
    card.innerHTML = `
      <div class="bco-war-room__top"><div><div class="bco-war-room__kicker">BLACK CROWN // CROWN SESSION</div><h2>${t("Командный центр", "War Room")}</h2></div><div class="bco-war-room__state" id="bcoWarRoomState">PRE_SESSION</div></div>
      <div class="bco-war-room__identity"><span class="bco-war-room__badge" id="bcoWarRoomIdentityBadge">CROWN ID // SYNC</span><span class="bco-war-room__badge" id="bcoWarRoomPremiumBadge">PREMIUM // SYNC</span></div>
      <div class="bco-war-room__grid">
        <div class="bco-war-room__cell"><span>${t("ГОТОВНОСТЬ", "READINESS")}</span><strong id="bcoWarRoomReadiness">CALIBRATING</strong></div>
        <div class="bco-war-room__cell"><span>${t("РИСК", "RISK")}</span><strong id="bcoWarRoomRisk">UNKNOWN</strong></div>
        <div class="bco-war-room__cell"><span>${t("УВЕРЕННОСТЬ", "CONFIDENCE")}</span><strong id="bcoWarRoomConfidence">UNKNOWN</strong></div>
        <div class="bco-war-room__cell"><span>${t("ТЕМП", "MOMENTUM")}</span><strong id="bcoWarRoomMomentum">UNKNOWN</strong></div>
      </div>
      <div class="bco-war-room__meta">
        <article><small>CROWN ACCOUNT</small><strong id="bcoWarRoomAccount">SYNC</strong><p id="bcoWarRoomGame">—</p></article>
        <article><small>PERSONAL META // COVERAGE</small><strong id="bcoWarRoomCoverage">0%</strong><p id="bcoWarRoomMetaSummary"></p></article>
      </div>
      <div class="bco-war-room__mission"><small>${t("ТЕКУЩАЯ МИССИЯ", "CURRENT MISSION")}</small><h3 id="bcoWarRoomMission">CALIBRATING</h3><p id="bcoWarRoomObjective"></p></div>
      <div class="bco-war-room__truth">${t("Один серверный CROWN SESSION для Telegram, Mini App и сайта. Нет скрытого рейтинга. Неизвестное остаётся неизвестным.", "One server-owned CROWN SESSION across Telegram, Mini App and website. No hidden score. Unknown remains unknown.")}</div>
      <button class="bco-war-room__open" id="bcoWarRoomOpenOperator" type="button">${t("ОТКРЫТЬ ПОЛНОЕ ДОСЬЕ", "OPEN FULL DOSSIER")}</button>`;
    operator.prepend(card);
    $("#bcoWarRoomOpenOperator")?.addEventListener("click", () => {
      try { window.Telegram?.WebApp?.HapticFeedback?.selectionChanged(); } catch (_) {}
      operator.scrollIntoView({behavior:"smooth",block:"start"});
    });
    window.addEventListener("bco:crown-session", render);
    refresh();
    let tries = 0;
    const timer = window.setInterval(() => {
      tries += 1;
      if (render() || tries > 24) window.clearInterval(timer);
    }, 250);
    return true;
  }

  if (!mount()) {
    let tries = 0;
    const timer = window.setInterval(() => {
      tries += 1;
      if (mount() || tries > 30) window.clearInterval(timer);
    }, 200);
  }

  window.BCO_WAR_ROOM = { render, refresh };
})();
