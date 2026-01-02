/* =========================================================
   BLACK CROWN OPS — ZOMBIES GAME (UI + RENDER + INPUT)
   File: app/webapp/static/zombies.game.js
   Requires:
     - zombies.core.js
     - zombies.render.js
     - zombies.assets.js (optional)
     - zombies.world.js (optional)
   Provides:
     - window.BCO_ZOMBIES_GAME
   ========================================================= */
(() => {
  "use strict";

  const CORE = window.BCO_ZOMBIES_CORE;
  const RENDER = window.BCO_ZOMBIES_RENDER;

  if (!CORE || !RENDER) {
    console.error("[Z_GAME] core/render missing");
    return;
  }

  const tg = window.Telegram?.WebApp || null;

  const mount = () => document.getElementById("zOverlayMount") || document.body;

  // ---------------------------------------------------------
  // UI State
  // ---------------------------------------------------------
  let overlay = null;
  let canvas = null;
  let ctx = null;
  let raf = 0;
  let dpr = 1;

  const input = {
    moveX: 0, moveY: 0,
    aimX: 1, aimY: 0
  };

  function haptic(type = "impact", style = "light") {
    try {
      if (!tg?.HapticFeedback) return;
      if (type === "impact") tg.HapticFeedback.impactOccurred(style);
      if (type === "notif") tg.HapticFeedback.notificationOccurred(style);
    } catch {}
  }

  function safeSendData(obj) {
    try {
      if (!tg?.sendData) return false;
      const s = JSON.stringify(obj);
      if (s.length > 15000) return false;
      tg.sendData(s);
      return true;
    } catch { return false; }
  }

  // ---------------------------------------------------------
  // Overlay build
  // ---------------------------------------------------------
  function ensureOverlay() {
    if (overlay) return;

    overlay = document.createElement("div");
    overlay.id = "bco-z-game";
    overlay.style.cssText = `
      position:fixed; inset:0; z-index:999999;
      background:
        radial-gradient(1200px 800px at 50% 35%, rgba(255,255,255,.06), rgba(0,0,0,.75)),
        linear-gradient(180deg, rgba(6,6,10,.90), rgba(0,0,0,.94));
      overflow:hidden;
      touch-action:none;
      -webkit-user-select:none; user-select:none;
    `;

    // Canvas
    canvas = document.createElement("canvas");
    canvas.id = "bco-z-canvas";
    canvas.style.cssText = `position:absolute; inset:0; width:100%; height:100%;`;
    overlay.appendChild(canvas);
    ctx = canvas.getContext("2d", { alpha: true });

    // Top HUD
    const top = document.createElement("div");
    top.style.cssText = `
      position:absolute; left:0; right:0; top:0;
      height:68px; display:flex; align-items:center; justify-content:space-between;
      padding:10px 12px; box-sizing:border-box;
      pointer-events:auto;
      backdrop-filter: blur(14px);
      background: linear-gradient(180deg, rgba(0,0,0,.45), rgba(0,0,0,0));
      border-bottom:1px solid rgba(255,255,255,.08);
    `;

    const left = document.createElement("div");
    left.style.cssText = `display:flex; gap:10px; align-items:center;`;

    const badge = document.createElement("div");
    badge.textContent = "🧟";
    badge.style.cssText = `
      width:38px; height:38px; border-radius:12px;
      display:flex; align-items:center; justify-content:center;
      background: rgba(255,255,255,.08);
      border:1px solid rgba(255,255,255,.12);
    `;

    const title = document.createElement("div");
    title.innerHTML = `
      <div style="font:900 14px/1.1 Inter,system-ui; letter-spacing:.2px;">Zombies Survival</div>
      <div id="bco-z-sub" style="font:700 12px/1.1 Inter,system-ui; opacity:.72;">ARCADE • Ashes</div>
    `;

    left.appendChild(badge);
    left.appendChild(title);

    const right = document.createElement("div");
    right.style.cssText = `display:flex; gap:10px; align-items:center;`;

    const pill = document.createElement("div");
    pill.id = "bco-z-hud";
    pill.style.cssText = `
      padding:10px 12px; border-radius:14px;
      font:800 12px/1 Inter,system-ui;
      background: rgba(255,255,255,.08);
      border:1px solid rgba(255,255,255,.12);
      color: rgba(255,255,255,.92);
      white-space: nowrap;
    `;
    pill.textContent = `❤️ 100 • ☠️ 0 • 💰 0 • 🔫 SMG`;

    const btnClose = document.createElement("button");
    btnClose.type = "button";
    btnClose.textContent = "✖";
    btnClose.style.cssText = `
      width:42px; height:42px; border-radius:14px;
      border:1px solid rgba(255,255,255,.14);
      background: rgba(255,255,255,.08);
      color: rgba(255,255,255,.92);
      font:900 16px/1 Inter,system-ui;
      touch-action: manipulation;
    `;
    btnClose.addEventListener("click", () => API.close(), { passive: true });

    right.appendChild(pill);
    right.appendChild(btnClose);

    top.appendChild(left);
    top.appendChild(right);
    overlay.appendChild(top);

    // Bottom controls
    const bottom = document.createElement("div");
    bottom.style.cssText = `
      position:absolute; left:0; right:0; bottom:0;
      height:220px;
      padding:10px 12px calc(10px + env(safe-area-inset-bottom));
      box-sizing:border-box;
      pointer-events:none;
      background: linear-gradient(0deg, rgba(0,0,0,.58), rgba(0,0,0,0));
    `;
    overlay.appendChild(bottom);

    // Dual sticks (big, iOS-friendly)
    const joyL = mkStick("left");
    const joyR = mkStick("right");

    bottom.appendChild(joyL.base);
    bottom.appendChild(joyR.base);

    // Shop bar (roguelike)
    const shop = document.createElement("div");
    shop.id = "bco-z-shop";
    shop.style.cssText = `
      position:absolute;
      left:50%; transform:translateX(-50%);
      bottom: calc(12px + env(safe-area-inset-bottom));
      display:flex; gap:10px;
      pointer-events:auto;
      opacity:0;
      transition: opacity .18s ease;
    `;
    bottom.appendChild(shop);

    const mkBtn = (txt, on) => {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = txt;
      b.style.cssText = `
        padding:12px 14px; border-radius:16px;
        border:1px solid rgba(255,255,255,.14);
        background: rgba(255,255,255,.08);
        color: rgba(255,255,255,.92);
        font:900 12px/1 Inter,system-ui;
        letter-spacing:.2px;
        touch-action: manipulation;
      `;
      b.addEventListener("click", on, { passive: true });
      return b;
    };

    shop.appendChild(mkBtn("🧪 Jug (12)", () => { if (CORE.buyPerk("Jug")) haptic("notif","success"); else haptic("notif","warning"); }));
    shop.appendChild(mkBtn("⚡ Speed (10)", () => { if (CORE.buyPerk("Speed")) haptic("notif","success"); else haptic("notif","warning"); }));
    shop.appendChild(mkBtn("🔫 Ammo (8)", () => { if (CORE.buyPerk("Mag")) haptic("notif","success"); else haptic("notif","warning"); }));

    function mkStick(side) {
      const base = document.createElement("div");
      base.style.cssText = `
        position:absolute;
        bottom: calc(12px + env(safe-area-inset-bottom));
        ${side === "left" ? "left" : "right"}: 12px;
        width: 170px; height: 170px;
        border-radius: 999px;
        background: rgba(255,255,255,.06);
        border: 1px solid rgba(255,255,255,.12);
        backdrop-filter: blur(10px);
        pointer-events:auto;
        touch-action:none;
      `;

      const knob = document.createElement("div");
      knob.style.cssText = `
        position:absolute; left:50%; top:50%;
        width: 66px; height: 66px;
        transform: translate(-50%,-50%);
        border-radius: 999px;
        background: rgba(255,255,255,.18);
        border: 1px solid rgba(255,255,255,.16);
        box-shadow: 0 16px 44px rgba(0,0,0,.45);
      `;
      base.appendChild(knob);

      return { base, knob, id: null, side };
    }

    // Prevent scroll/pinch
    overlay.addEventListener("touchmove", (e) => e.preventDefault(), { passive: false });
    overlay.addEventListener("gesturestart", (e) => e.preventDefault(), { passive: false });
    overlay.addEventListener("gesturechange", (e) => e.preventDefault(), { passive: false });

    // Attach
    mount().appendChild(overlay);

    // Resize + wire
    resize();
    wireStick(joyL, (x, y) => {
      input.moveX = x; input.moveY = y;
      CORE.setMove(x, y);
    });

    wireStick(joyR, (x, y) => {
      if (x || y) {
        input.aimX = x; input.aimY = y;
        CORE.setAim(x, y);
        CORE.setShooting(true);
      } else {
        CORE.setShooting(false);
      }
    });

    // Telegram buttons
    try { tg?.expand?.(); } catch {}
    try { tg?.BackButton?.show?.(); } catch {}
    try {
      tg?.BackButton?.onClick?.(() => {
        if (overlay) API.close();
      });
    } catch {}

    // show shop depending on mode
    shop.style.opacity = (CORE.meta.mode === "roguelike") ? "1" : "0";

    // local refs
    overlay._bco = { shop };
  }

  function destroyOverlay() {
    if (!overlay) return;
    try { overlay.remove(); } catch {}
    overlay = null;
    canvas = null;
    ctx = null;
  }

  // ---------------------------------------------------------
  // Stick math
  // ---------------------------------------------------------
  function wireStick(stick, onMove) {
    const dead = 0.10;
    const maxR = 56;

    const rect = () => stick.base.getBoundingClientRect();

    function setKnob(nx, ny) {
      stick.knob.style.transform =
        `translate(calc(-50% + ${nx * maxR}px), calc(-50% + ${ny * maxR}px))`;
    }

    function down(e) {
      e.preventDefault();
      stick.id = e.pointerId;
      stick.base.setPointerCapture?.(e.pointerId);
      move(e);
      haptic("impact", "light");
    }

    function move(e) {
      if (stick.id !== e.pointerId) return;

      const r = rect();
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;

      const dx = e.clientX - cx;
      const dy = e.clientY - cy;

      const L = Math.hypot(dx, dy) || 1;
      let nx = dx / Math.max(L, 1);
      let ny = dy / Math.max(L, 1);

      const mag = Math.min(1, L / (r.width * 0.42));
      let m = mag < dead ? 0 : (mag - dead) / (1 - dead);

      nx *= m;
      ny *= m;

      setKnob(nx, ny);
      onMove(nx, ny);
    }

    function up(e) {
      if (stick.id !== e.pointerId) return;
      stick.id = null;
      setKnob(0, 0);
      onMove(0, 0);
    }

    stick.base.addEventListener("pointerdown", down, { passive: false });
    stick.base.addEventListener("pointermove", move, { passive: false });
    stick.base.addEventListener("pointerup", up, { passive: false });
    stick.base.addEventListener("pointercancel", up, { passive: false });
  }

  // ---------------------------------------------------------
  // Resize
  // ---------------------------------------------------------
  function resize() {
    if (!canvas || !ctx) return;
    const r = overlay.getBoundingClientRect();
    dpr = Math.max(1, Math.min(3, window.devicePixelRatio || 1));
    canvas.width = Math.floor(r.width * dpr);
    canvas.height = Math.floor(r.height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    CORE.resize(r.width, r.height);
  }
  window.addEventListener("resize", resize, { passive: true });

  // ---------------------------------------------------------
  // Loop
  // ---------------------------------------------------------
  function loop(t) {
    raf = requestAnimationFrame(loop);

    if (!overlay || !ctx) return;

    if (CORE.running) CORE.updateFrame(t);

    const view = { w: overlay.getBoundingClientRect().width, h: overlay.getBoundingClientRect().height };
    RENDER.render(ctx, CORE, CORE.input, view);

    updateHud();
    checkDeathAutoSend();
  }

  let _sentDeath = false;

  function checkDeathAutoSend() {
    if (!CORE.running) {
      // if player hp 0 -> send result once
      if (!_sentDeath && CORE.state.player.hp <= 0) {
        _sentDeath = true;
        sendResult("dead");
        haptic("notif", "error");
      }
    }
  }

  function updateHud() {
    const sub = document.getElementById("bco-z-sub");
    const hud = document.getElementById("bco-z-hud");

    const st = CORE._effectiveStats ? CORE._effectiveStats() : { hpMax: 100 };
    const hp = Math.max(0, Math.min(CORE.state.player.hp, st.hpMax));

    if (sub) sub.textContent = `${CORE.meta.mode.toUpperCase()} • ${CORE.meta.map}`;
    if (hud) hud.textContent = `❤️ ${hp|0}/${st.hpMax|0} • ☠️ ${CORE.state.kills|0} • 💰 ${CORE.state.coins|0} • 🔫 ${CORE._weapon().name}`;

    const shop = overlay?._bco?.shop;
    if (shop) shop.style.opacity = (CORE.meta.mode === "roguelike") ? "1" : "0";
  }

  // ---------------------------------------------------------
  // Result payload
  // ---------------------------------------------------------
  function score() {
    const S = CORE.state;
    const base = (S.kills | 0) * 100;
    const waveBonus = Math.max(0, (S.wave - 1) | 0) * 250;
    const timeSec = Math.max(1, (S.timeMs / 1000));
    const pace = (S.kills / timeSec) * 100;
    const perks = (S.perks.Jug ? 150 : 0) + (S.perks.Speed ? 120 : 0) + (S.perks.Mag ? 80 : 0);
    return Math.round(base + waveBonus + pace + perks);
  }

  function sendResult(reason = "manual") {
    const S = CORE.state;

    const payload = {
      action: "game_result",
      game: "zombies",
      mode: CORE.meta.mode,
      reason,

      map: CORE.meta.map,
      wave: S.wave,
      kills: S.kills,
      coins: S.coins,
      duration_ms: Math.round(S.timeMs),
      score: score(),

      character: CORE.meta.character,
      skin: CORE.meta.skin,
      loadout: { weapon: CORE.meta.weaponKey },
      perks: { ...S.perks }
    };

    safeSendData(payload);
  }

  // ---------------------------------------------------------
  // Public API
  // ---------------------------------------------------------
  const API = {
    open() {
      ensureOverlay();
      resize();
      if (!raf) raf = requestAnimationFrame(loop);
      haptic("impact", "medium");
      return true;
    },

    close() {
      if (raf) cancelAnimationFrame(raf);
      raf = 0;
      CORE.stop();
      _sentDeath = false;

      try { tg?.BackButton?.hide?.(); } catch {}
      destroyOverlay();
      return true;
    },

    start(mode = "arcade", opts = {}) {
      ensureOverlay();
      resize();
      _sentDeath = false;

      CORE.start(mode, overlay.getBoundingClientRect().width, overlay.getBoundingClientRect().height, opts);

      if (!raf) raf = requestAnimationFrame(loop);

      haptic("notif", "success");
      return true;
    },

    stop(reason = "manual") {
      CORE.stop();
      sendResult(reason);
      haptic("notif", "warning");
      return true;
    },

    setMode(mode) {
      const m = String(mode || "").toLowerCase();
      CORE.meta.mode = (m.includes("rogue")) ? "roguelike" : "arcade";
      updateHud();
      return CORE.meta.mode;
    },

    setMap(mapName) {
      CORE.meta.map = String(mapName || "Ashes");
      // world module will load next tick
      updateHud();
      return CORE.meta.map;
    },

    setCharacter(character, skin) {
      if (character) CORE.meta.character = String(character);
      if (skin) CORE.meta.skin = String(skin);

      // assets module may support skins
      try {
        const A = window.BCO_ZOMBIES_ASSETS;
        if (A?.setPlayerSkin) A.setPlayerSkin(CORE.meta.skin);
      } catch {}

      return { character: CORE.meta.character, skin: CORE.meta.skin };
    },

    setWeapon(key) {
      return CORE.setWeapon(key);
    },

    buyPerk(id) {
      const ok = CORE.buyPerk(id);
      if (ok) haptic("notif", "success");
      else haptic("notif", "warning");
      return ok;
    },

    sendResult(reason) {
      sendResult(reason || "manual");
      return true;
    }
  };

  window.BCO_ZOMBIES_GAME = API;
  console.log("[Z_GAME] ready");
})();
