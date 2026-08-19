/* BLACK CROWN OPS v49 — unified ecosystem shell */
(() => {
  "use strict";
  if (window.__BCO_ECOSYSTEM_SHELL_V49_LOADED__) return;
  window.__BCO_ECOSYSTEM_SHELL_V49_LOADED__ = true;

  const $ = (q, root = document) => root.querySelector(q);
  const $$ = (q, root = document) => Array.from(root.querySelectorAll(q));
  const safe = (value, fallback = "—") => { const text = String(value ?? "").trim(); return text || fallback; };
  const tap = (id) => { const el = document.getElementById(id); if (el) { el.click(); return true; } return false; };
  const haptic = () => { try { window.Telegram?.WebApp?.HapticFeedback?.selectionChanged?.(); } catch (_) {} };

  const modules = [
    {id:"ai_brief", icon:"✦", title:"CROWN", sub:"AI Combat Brief", route:"crown"},
    {id:"training", icon:"◎", title:"TRAINING", sub:"Personal protocol", route:"crown"},
    {id:"world", icon:"◈", title:"WORLD", sub:"Game & input context", route:"world"},
    {id:"vod", icon:"▣", title:"VOD LAB", sub:"Engagement Intelligence", route:"vod"},
    {id:"zombies", icon:"⬡", title:"ZOMBIES", sub:"HQ & survival", route:"zombies"},
    {id:"operator", icon:"◇", title:"OPERATOR", sub:"Twin & missions", route:"operator"},
    {id:"premium", icon:"◆", title:"PREMIUM", sub:"Entitlements", route:"premium"},
    {id:"system", icon:"⚙", title:"SYSTEM", sub:"Voice, core & profile", route:"system"},
  ];

  let current = "home";
  let lastSession = null;

  function addCss() {
    if ($("#bcoEcosystemV49Css")) return;
    const style = document.createElement("style");
    style.id = "bcoEcosystemV49Css";
    style.textContent = `
      :root{--b49-bg:#07080a;--b49-panel:#101216;--b49-panel2:#15181d;--b49-line:rgba(255,255,255,.075);--b49-text:#f4f2ed;--b49-muted:#858991;--b49-gold:#d9b86f;--b49-gold2:#f1d697;--b49-ok:#9cc9aa}
      body.bco49{background:var(--b49-bg)!important;color:var(--b49-text)!important;padding-bottom:92px!important}
      body.bco49 .bg{opacity:.34}.bco49 .app-header,.bco49 .hero,.bco49>.bottom-nav,.bco49 .foot{display:none!important}
      .bco49 .app-main{padding-top:0!important}.bco49 .wrap{width:min(100%,760px)!important;padding-left:14px!important;padding-right:14px!important}
      .b49-head{position:sticky;top:0;z-index:80;margin:0 -14px 14px;padding:calc(var(--tg-top,0px) + 10px) 16px 10px;background:linear-gradient(180deg,rgba(7,8,10,.98),rgba(7,8,10,.91) 75%,rgba(7,8,10,0));backdrop-filter:blur(18px)}
      .b49-head__row{display:flex;align-items:center;justify-content:space-between;gap:12px}.b49-brand{display:flex;align-items:center;gap:10px}.b49-crown{display:grid;place-items:center;width:35px;height:35px;border:1px solid rgba(217,184,111,.25);border-radius:11px;background:rgba(217,184,111,.07);font-size:17px;color:var(--b49-gold2)}
      .b49-name{font-size:13px;font-weight:800;letter-spacing:.09em}.b49-sub{margin-top:2px;font-size:9px;letter-spacing:.12em;color:var(--b49-muted)}.b49-access{display:flex;align-items:center;gap:6px;padding:7px 9px;border:1px solid var(--b49-line);border-radius:999px;background:rgba(255,255,255,.025);font-size:9px;letter-spacing:.08em}.b49-dot{width:6px;height:6px;border-radius:50%;background:var(--b49-ok)}
      .b49-context{display:flex;gap:6px;margin-top:10px;overflow:hidden}.b49-chip{min-width:0;padding:6px 8px;border:1px solid var(--b49-line);border-radius:9px;background:rgba(255,255,255,.02);font-size:9px;color:#b8bbc1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .b49-launchpad{margin:4px 0 14px}.b49-label{margin:0 2px 8px;font-size:9px;letter-spacing:.16em;color:#777b83}.b49-modules{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px}.b49-module{min-height:69px;padding:10px 8px;border:1px solid var(--b49-line);border-radius:13px;background:linear-gradient(180deg,rgba(22,24,29,.88),rgba(13,15,18,.92));color:inherit;text-align:left}.b49-module:active{transform:scale(.985)}.b49-module__icon{font-size:15px;color:var(--b49-gold)}.b49-module b{display:block;margin-top:7px;font-size:9px;letter-spacing:.06em}.b49-module small{display:block;margin-top:3px;font-size:8px;line-height:1.25;color:#747982}
      .bco49 .card,.bco49 .cardlite,.bco49 .chat-shell{border:1px solid var(--b49-line)!important;border-radius:16px!important;background:var(--b49-panel)!important;box-shadow:none!important}.bco49 .card{padding:15px!important}.bco49 .card-title{font-size:12px!important;letter-spacing:.02em!important}.bco49 .hint{color:#8a8e96!important;font-size:11px!important}.bco49 .btn{border-radius:11px!important;min-height:42px!important}.bco49 .btn.primary{background:linear-gradient(180deg,#e2c27d,#c7a45d)!important;color:#111!important;border-color:rgba(255,230,180,.25)!important}
      .bco49 #tab-home>.card,.bco49 #tab-home>.chat-shell{display:none!important}.bco49 #tab-home{display:block!important}.bco49 #tab-home:not(.active){display:none!important}.bco49 #bcoSessionHomeV45{margin-top:0!important;border-radius:18px!important}.bco49 #bcoAfterActionV46{border-radius:14px!important}
      .b49-view{display:none}.b49-view.active{display:grid;gap:10px}.b49-section{padding:15px;border:1px solid var(--b49-line);border-radius:16px;background:var(--b49-panel)}.b49-section h2{margin:0;font-size:18px}.b49-section p{margin:6px 0 0;color:var(--b49-muted);font-size:11px;line-height:1.5}.b49-section__head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}.b49-kicker{font-size:8px;letter-spacing:.16em;color:var(--b49-gold)}
      .b49-actions{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}.b49-action{min-height:48px;padding:10px 12px;border:1px solid var(--b49-line);border-radius:12px;background:var(--b49-panel2);color:inherit;text-align:left}.b49-action b{display:block;font-size:11px}.b49-action small{display:block;margin-top:3px;color:var(--b49-muted);font-size:9px}.b49-action.primary{border-color:rgba(217,184,111,.22);background:rgba(217,184,111,.075)}
      .b49-account{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}.b49-stat{padding:11px;border:1px solid var(--b49-line);border-radius:12px;background:rgba(255,255,255,.02)}.b49-stat span{display:block;font-size:8px;letter-spacing:.13em;color:var(--b49-muted)}.b49-stat b{display:block;margin-top:6px;font-size:12px;word-break:break-all}
      .b49-moregrid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.b49-more{min-height:112px;padding:13px;border:1px solid var(--b49-line);border-radius:15px;background:var(--b49-panel);color:inherit;text-align:left}.b49-more .ico{font-size:19px;color:var(--b49-gold)}.b49-more b{display:block;margin-top:13px;font-size:12px}.b49-more small{display:block;margin-top:5px;color:var(--b49-muted);font-size:10px;line-height:1.35}
      .b49-bottom{position:fixed;left:10px;right:10px;bottom:calc(var(--tg-bottom,0px) + 8px);z-index:120;display:grid;grid-template-columns:repeat(5,1fr);max-width:730px;margin:auto;padding:6px;border:1px solid rgba(255,255,255,.09);border-radius:18px;background:rgba(12,13,16,.94);backdrop-filter:blur(20px)}.b49-nav{min-height:51px;border:0;border-radius:13px;background:transparent;color:#777c84}.b49-nav span{display:block;font-size:16px;line-height:1}.b49-nav b{display:block;margin-top:5px;font-size:8px;letter-spacing:.04em}.b49-nav.active{background:rgba(217,184,111,.09);color:var(--b49-gold2)}
      .b49-legacy{display:none!important}.b49-panel-head{display:flex;align-items:center;gap:10px;margin-bottom:10px}.b49-back{width:36px;height:36px;border:1px solid var(--b49-line);border-radius:10px;background:var(--b49-panel2);color:inherit}.b49-panel-head h2{margin:0;font-size:17px}.b49-panel-head small{color:var(--b49-muted)}
      @media(max-width:430px){.b49-modules{grid-template-columns:repeat(4,minmax(0,1fr));gap:5px}.b49-module{min-height:64px;padding:9px 6px}.b49-module small{display:none}.b49-actions{grid-template-columns:1fr}.b49-moregrid{grid-template-columns:1fr 1fr}}
    `;
    document.head.appendChild(style);
  }

  function legacyTab(name) {
    const button = $(`.bottom-nav .nav-btn[data-tab="${name}"]`);
    if (button) button.click();
  }

  function hideAllCustom() { $$(".b49-view").forEach(x => x.classList.remove("active")); }

  function showCustom(id) {
    $$(".tabpane").forEach(x => x.classList.remove("active"));
    hideAllCustom();
    const el = $(id); if (el) el.classList.add("active");
  }

  function route(name) {
    current = name;
    haptic();
    $$(".b49-nav").forEach(x => x.classList.toggle("active", x.dataset.route === name));
    if (name === "home") { hideAllCustom(); legacyTab("home"); }
    else if (name === "crown") showCustom("#b49Crown");
    else if (name === "vod") { hideAllCustom(); legacyTab("vod"); }
    else if (name === "operator") {
      hideAllCustom();
      const op = $("#tab-operator-v25");
      if (op) { $$(".tabpane").forEach(x => x.classList.remove("active")); op.classList.add("active"); window.BCO_OPERATOR?.refresh?.(true); }
      else { legacyTab("home"); $("#bcoSessionHomeV45")?.scrollIntoView({behavior:"smooth"}); }
    } else if (name === "more") showCustom("#b49More");
    window.scrollTo({top:0,behavior:"smooth"});
  }

  function openModule(routeName) {
    if (["home","crown","vod","operator","more"].includes(routeName)) return route(routeName);
    if (routeName === "training") return route("crown");
    if (routeName === "world" || routeName === "system") { hideAllCustom(); legacyTab("settings"); return; }
    if (routeName === "zombies") { hideAllCustom(); legacyTab("game"); return; }
    if (routeName === "premium") { route("more"); $("#b49Premium")?.scrollIntoView({behavior:"smooth",block:"center"}); return; }
  }

  function moveLegacy() {
    const crown = $("#b49CrownBody");
    const chat = $("#tab-home .chat-shell");
    if (crown && chat) { chat.classList.remove("b49-legacy"); crown.appendChild(chat); }
    const coach = $("#tab-coach");
    if (crown && coach) {
      Array.from(coach.children).forEach(child => crown.appendChild(child));
      coach.classList.add("b49-legacy");
    }
  }

  function buildShell() {
    if ($("#bcoEcosystemV49")) return;
    addCss(); document.body.classList.add("bco49");
    const main = $("main.app-main"); if (!main) return;

    const head = document.createElement("div");
    head.id = "bcoEcosystemV49"; head.className = "b49-head";
    head.innerHTML = `<div class="b49-head__row"><div class="b49-brand"><div class="b49-crown">♛</div><div><div class="b49-name">BLACK CROWN</div><div class="b49-sub">COMPETITIVE INTELLIGENCE</div></div></div><div class="b49-access"><i class="b49-dot"></i><span id="b49Access">SYNCING</span></div></div><div class="b49-context"><div class="b49-chip" id="b49World">WORLD —</div><div class="b49-chip" id="b49Core">CORE —</div><div class="b49-chip" id="b49Identity">CROWN —</div></div>`;
    main.prepend(head);

    const launch = document.createElement("section"); launch.className = "b49-launchpad";
    launch.innerHTML = `<div class="b49-label">ECOSYSTEM</div><div class="b49-modules">${modules.map(m => `<button class="b49-module" type="button" data-module="${m.route}"><span class="b49-module__icon">${m.icon}</span><b>${m.title}</b><small>${m.sub}</small></button>`).join("")}</div>`;
    head.after(launch);

    const crown = document.createElement("section"); crown.id="b49Crown"; crown.className="b49-view";
    crown.innerHTML = `<div class="b49-section"><div class="b49-section__head"><div><div class="b49-kicker">CROWN // LIVE</div><h2>Combat Intelligence</h2><p>Один AI-контекст с Telegram-ботом: тот же Operator, world, brain mode и память.</p></div><button class="b49-action primary" id="b49BotConsole" type="button"><b>BOT CONSOLE</b><small>open Telegram controls</small></button></div></div><div id="b49CrownBody" class="b49-view active"></div>`;
    main.appendChild(crown);

    const more = document.createElement("section"); more.id="b49More"; more.className="b49-view";
    more.innerHTML = `<div class="b49-section"><div class="b49-kicker">ONE BLACK CROWN ACCOUNT</div><h2>Ecosystem Control</h2><p>Website, Telegram Bot и Mini App работают через одну canonical identity. Настройки отправляются в общий player profile.</p><div class="b49-account"><div class="b49-stat"><span>CROWN ID</span><b id="b49AccountId">SYNCING</b></div><div class="b49-stat"><span>ENTITLEMENT</span><b id="b49Entitlement">SYNCING</b></div></div></div><div class="b49-moregrid"><button class="b49-more" data-open="world"><span class="ico">◈</span><b>WORLD</b><small>Warzone / BO7 / BF6, platform and input.</small></button><button class="b49-more" data-open="zombies"><span class="ico">⬡</span><b>ZOMBIES</b><small>Game launcher, strategy, perks and HQ.</small></button><button class="b49-more" id="b49Premium" data-open="premium"><span class="ico">◆</span><b>PREMIUM</b><small id="b49PremiumText">Server entitlement and premium intelligence.</small></button><button class="b49-more" data-open="system"><span class="ico">⚙</span><b>SYSTEM</b><small>Voice behavior, brain mode and synchronized profile.</small></button></div><div class="b49-section"><div class="b49-kicker">SYNC</div><h2>Profile Authority</h2><p>После изменения World / Input / Voice профиль отправляется в Telegram backend и используется AI, VOD и missions.</p><div class="b49-actions"><button class="b49-action primary" id="b49Sync" type="button"><b>SYNC PROFILE</b><small>push current controls to backend</small></button><button class="b49-action" id="b49OpenBot" type="button"><b>TELEGRAM CONSOLE</b><small>same ecosystem modules</small></button></div></div>`;
    main.appendChild(more);

    const nav = document.createElement("nav"); nav.className="b49-bottom"; nav.setAttribute("aria-label","BLACK CROWN navigation");
    nav.innerHTML = [["home","⌂","HOME"],["crown","✦","CROWN"],["vod","▣","VOD"],["operator","◇","OPERATOR"],["more","⋯","MORE"]].map(([r,i,t]) => `<button class="b49-nav${r==="home"?" active":""}" data-route="${r}" type="button"><span>${i}</span><b>${t}</b></button>`).join("");
    document.body.appendChild(nav);

    $$(".b49-module").forEach(btn => btn.addEventListener("click", () => openModule(btn.dataset.module)));
    $$(".b49-nav").forEach(btn => btn.addEventListener("click", () => route(btn.dataset.route)));
    $$("[data-open]").forEach(btn => btn.addEventListener("click", () => openModule(btn.dataset.open)));
    $("#b49Sync")?.addEventListener("click", () => { if (!tap("btnApplyProfile")) tap("btnSync"); });
    $("#b49OpenBot")?.addEventListener("click", () => tap("btnOpenBot"));
    $("#b49BotConsole")?.addEventListener("click", () => tap("btnOpenBot"));
    moveLegacy(); route("home");
  }

  function renderSession(session) {
    if (!session) return; lastSession = session;
    const profile = session.profile || {}, identity = session.identity || {}, entitlement = session.entitlement || {};
    const id = safe(identity.black_crown_user_id, "UNLINKED");
    $("#b49World") && ($("#b49World").textContent = `${safe(profile.game,"WORLD")} • ${safe(profile.input,profile.platform||"—")}`);
    $("#b49Core") && ($("#b49Core").textContent = `${safe(profile.difficulty,"NORMAL")} • ${safe(profile.voice,"TEAMMATE")}`);
    $("#b49Identity") && ($("#b49Identity").textContent = id === "UNLINKED" ? "CROWN UNLINKED" : `CROWN ${id.slice(0,6)}…${id.slice(-4)}`);
    $("#b49AccountId") && ($("#b49AccountId").textContent = id);
    const premium = entitlement.premium === true;
    $("#b49Access") && ($("#b49Access").textContent = premium ? "PREMIUM" : (identity.canonical ? "ONLINE" : "CALIBRATING"));
    $("#b49Entitlement") && ($("#b49Entitlement").textContent = premium ? "PREMIUM ACTIVE" : "STANDARD");
    $("#b49PremiumText") && ($("#b49PremiumText").textContent = premium ? "Premium intelligence is active on this canonical account." : "Upgrade applies to the same canonical account across surfaces.");
  }

  function mount() {
    buildShell();
    const existing = window.BCO_CROWN_SESSION?.getSnapshot?.(); if (existing) renderSession(existing);
    window.addEventListener("bco:crown-session", e => renderSession(e.detail));
    window.BCO_CROWN_SESSION?.refresh?.(false).then(renderSession).catch(() => {});
    window.BCO_ECOSYSTEM = {route, openModule, renderSession, getSession:()=>lastSession};
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount, {once:true}); else mount();
})();
