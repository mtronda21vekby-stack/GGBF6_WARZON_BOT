/* =========================================================
   BLACK CROWN OPS — ZOMBIES GAME (UI + RENDER + INPUT) [LUX FIX]
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

  // sticks refs
  let joyL = null;
  let joyR = null;
  let topHud = null;
  let shop = null;
  let shopBtns = {};
  let btnClose = null;

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
  // Orientation helpers (best-effort)
  // ---------------------------------------------------------
  async function tryLockLandscape() {
    try {
      const scr = window.screen;
      if (scr?.orientation?.lock) {
        await scr.orientation.lock("landscape");
        return true;
      }
    } catch {}
    return false;
  }

  function hideTelegramMainButton() {
    try { tg?.MainButton?.hide?.(); } catch {}
  }
  function showTelegramMainButton() {
    try { tg?.MainButton?.show?.(); } catch {}
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
    topHud = document.createElement("div");
    topHud.style.cssText = `
      position:absolute; left:0; right:0; top:0;
      height:68px; display:flex; align-items:center; justify-content:space-between;
      padding: calc(10px + env(safe-area-inset-top)) 12px 10px 12px;
      box-sizing:border-box;
      pointer-events:auto;
      backdrop-filter: blur(14px);
      background: linear-gradient(180deg, rgba(0,0,0,.55), rgba(0,0,0,0));
      border-bottom:1px solid rgba(255,255,255,.08);
    `;

    const left = document.createElement("div");
    left.style.cssText = `display:flex; gap:10px; align-items:center; min-width: 240px;`;

    const badge = document.createElement("div");
    badge.textContent = "🧟";
    badge.style.cssText = `
      width:38px; height:38px; border-radius:12px;
      display:flex; align-items:center; justify-content:center;
      background: rgba(255,255,255,.08);
      border:1px solid rgba(255,255,255,.12);
      flex: 0 0 auto;
    `;

    const title = document.createElement("div");
    title.style.cssText = `min-width: 0;`;
    title.innerHTML = `
      <div style="font:900 14px/1.1 Inter,system-ui; letter-spacing:.2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
        Zombies Survival
      </div>
      <div id="bco-z-sub" style="font:700 12px/1.1 Inter,system-ui; opacity:.72; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
        ARCADE • Ashes
      </div>
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
      max-width: 58vw;
      overflow: hidden;
      text-overflow: ellipsis;
    `;
    pill.textContent = `❤️ 100 • ☠️ 0 • 💰 0 • 🔫 SMG`;

    btnClose = document.createElement("button");
    btnClose.type = "button";
    btnClose.textContent = "✖";
    btnClose.style.cssText = `
      width:42px; height:42px; border-radius:14px;
      border:1px solid rgba(255,255,255,.14);
      background: rgba(255,255,255,.08);
      color: rgba(255,255,255,.92);
      font:900 16px/1 Inter,system-ui;
      touch-action: manipulation;
      flex: 0 0 auto;
    `;
    btnClose.addEventListener("click", () => API.close(), { passive: true });

    right.appendChild(pill);
    right.appendChild(btnClose);

    topHud.appendChild(left);
    topHud.appendChild(right);
    overlay.appendChild(topHud);

    // Bottom controls container
    const bottom = document.createElement("div");
    bottom.id = "bco-z-bottom";
    bottom.style.cssText = `
      position:absolute; left:0; right:0; bottom:0;
      height: 260px;
      padding:10px 12px calc(12px + env(safe-area-inset-bottom));
      box-sizing:border-box;
      pointer-events:none;
      background: linear-gradient(0deg, rgba(0,0,0,.62), rgba(0,0,0,0));
    `;
    overlay.appendChild(bottom);

    // Dual sticks (big, iOS-friendly)
    joyL = mkStick("left");
    joyR = mkStick("right");
    bottom.appendChild(joyL.base);
    bottom.appendChild(joyR.base);

    // Shop bar (roguelike)
    shop = document.createElement("div");
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

    const mkBtn = (id, txt, on) => {
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
        white-space: nowrap;
      `;
      b.addEventListener("click", on, { passive: true });
      shopBtns[id] = b;
      return b;
    };

    shop.appendChild(mkBtn("Jug",   "🧪 Jug",   () => API.buyPerk("Jug")));
    shop.appendChild(mkBtn("Speed", "⚡ Speed", () => API.buyPerk("Speed")));
    shop.appendChild(mkBtn("Mag",   "🔫 Ammo",  () => API.buyPerk("Mag")));

    function mkStick(side) {
      const base = document.createElement("div");
      base.className = "bco-z-stick";
      base.dataset.side = side;
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

      return { base, knob, id: null, side, maxR: 56 };
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

    // IMPORTANT: hide Telegram MainButton so it doesn't block controls
    hideTelegramMainButton();

    // show shop depending on mode
    syncShopUI();
  }

  function destroyOverlay() {
    if (!overlay) return;
    try { overlay.remove(); } catch {}
    overlay = null;
    canvas = null;
    ctx = null;
    joyL = null;
    joyR = null;
    topHud = null;
    shop = null;
    shopBtns = {};
    btnClose = null;
  }

  // ---------------------------------------------------------
  // Stick math
  // ---------------------------------------------------------
  function wireStick(stick, onMove) {
    const dead = 0.10;

    const rect = () => stick.base.getBoundingClientRect();

    function setKnob(nx, ny) {
      stick.knob.style.transform =
        `translate(calc(-50% + ${nx * stick.maxR}px), calc(-50% + ${ny * stick.maxR}px))`;
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
  // Shop UI sync (coins + costs + mode)
  // ---------------------------------------------------------
  function perkCost(id) {
    // CORE cfg is source of truth if present
    try {
      const c = CORE?.cfg?.perks?.[id]?.cost;
      if (Number.isFinite(c)) return c;
    } catch {}
    // fallback
    if (id === "Jug") return 12;
    if (id === "Speed") return 10;
    if (id === "Mag") return 8;
    return 999;
  }

  function syncShopUI() {
    if (!overlay || !shop) return;

    const isRogue = (String(CORE?.meta?.mode || "") === "roguelike");
    shop.style.opacity = isRogue ? "1" : "0";
    shop.style.pointerEvents = isRogue ? "auto" : "none";

    // update labels + enabled state
    const coins = Number(CORE?.state?.coins || 0);

    for (const id of ["Jug", "Speed", "Mag"]) {
      const b = shopBtns[id];
      if (!b) continue;

      const cost = perkCost(id);
      const owned = !!CORE?.state?.perks?.[id];
      const can = (!owned && coins >= cost && isRogue);

      const base =
        id === "Jug" ? "🧪 Jug" :
        id === "Speed" ? "⚡ Speed" :
        "🔫 Ammo";

      b.textContent = `${base} (${cost})${owned ? " ✓" : ""}`;
      b.disabled = !can;
      b.style.opacity = owned ? "0.55" : (can ? "1" : "0.55");
    }
  }

  // ---------------------------------------------------------
  // Resize (adaptive portrait/landscape)
  // ---------------------------------------------------------
  function resize() {
    if (!overlay || !canvas || !ctx) return;

    const r = overlay.getBoundingClientRect();
    const w = Math.max(1, r.width);
    const h = Math.max(1, r.height);

    dpr = Math.max(1, Math.min(3, window.devicePixelRatio || 1));
    canvas.width = Math.floor(w * dpr);
    canvas.height = Math.floor(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    CORE.resize(w, h);

    // adaptive sticks sizing
    const portrait = h > w;
    const stickSize = portrait ? 148 : 170;
    const knobSize  = portrait ? 58  : 66;
    const pad = portrait ? 10 : 12;

    if (joyL && joyR) {
      joyL.base.style.width = stickSize + "px";
      joyL.base.style.height = stickSize + "px";
      joyR.base.style.width = stickSize + "px";
      joyR.base.style.height = stickSize + "px";

      joyL.base.style.left = pad + "px";
      joyR.base.style.right = pad + "px";

      // raise sticks a bit in portrait (avoid bottom overlays)
      const bottomY = portrait ? 22 : 12;
      joyL.base.style.bottom = `calc(${bottomY}px + env(safe-area-inset-bottom))`;
      joyR.base.style.bottom = `calc(${bottomY}px + env(safe-area-inset-bottom))`;

      joyL.knob.style.width = knobSize + "px";
      joyL.knob.style.height = knobSize + "px";
      joyR.knob.style.width = knobSize + "px";
      joyR.knob.style.height = knobSize + "px";

      joyL.maxR = portrait ? 46 : 56;
      joyR.maxR = portrait ? 46 : 56;
    }

    if (shop) {
      shop.style.bottom = `calc(${portrait ? 10 : 12}px + env(safe-area-inset-bottom))`;
    }
  }

  window.addEventListener("resize", resize, { passive: true });
  window.addEventListener("orientationchange", () => {
    setTimeout(() => resize(), 80);
    setTimeout(() => resize(), 220);
  }, { passive: true });

  // ---------------------------------------------------------
  // Loop
  // ---------------------------------------------------------
  function loop(t) {
    raf = requestAnimationFrame(loop);

    if (!overlay || !ctx) return;

    if (CORE.running) CORE.updateFrame(t);

    const r = overlay.getBoundingClientRect();
    const view = { w: Math.max(1, r.width), h: Math.max(1, r.height) };
    RENDER.render(ctx, CORE, CORE.input, view);

    updateHud();
    syncShopUI();
    checkDeathAutoSend();
  }

  let _sentDeath = false;

  function checkDeathAutoSend() {
    if (!CORE.running) {
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
    if (hud) {
      const weap = CORE._weapon ? CORE._weapon().name : (CORE.meta.weaponKey || "SMG");
      hud.textContent = `❤️ ${hp|0}/${st.hpMax|0} • ☠️ ${CORE.state.kills|0} • 💰 ${CORE.state.coins|0} • 🔫 ${weap}`;
    }
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

      // best effort lock landscape
      tryLockLandscape();

      // critical: keep MainButton hidden
      hideTelegramMainButton();

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

      // restore MainButton (your app decides later if it needs it)
      showTelegramMainButton();

      return true;
    },

    start(mode = "arcade", opts = {}) {
      ensureOverlay();
      resize();
      _sentDeath = false;

      // critical: hide MainButton so it doesn't cover controls
      hideTelegramMainButton();

      // best effort lock landscape
      tryLockLandscape();

      CORE.start(mode, overlay.getBoundingClientRect().width, overlay.getBoundingClientRect().height, opts);

      // ensure shop state reflects mode immediately
      syncShopUI();

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
      syncShopUI();
      updateHud();
      return CORE.meta.mode;
    },

    setMap(mapName) {
      CORE.meta.map = String(mapName || "Ashes");
      updateHud();
      return CORE.meta.map;
    },

    setCharacter(character, skin) {
      if (character) CORE.meta.character = String(character);
      if (skin) CORE.meta.skin = String(skin);

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
      syncShopUI();
      updateHud();
      return ok;
    },

    sendResult(reason) {
      sendResult(reason || "manual");
      return true;
    }
  };

  window.BCO_ZOMBIES_GAME = API;
  console.log("[Z_GAME] ready (LUX FIX)");
})();
