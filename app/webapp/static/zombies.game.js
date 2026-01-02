/* =========================================================
   BLACK CROWN OPS — ZOMBIES GAME (UI + RENDER + INPUT)  [LUX]
   File: app/webapp/static/zombies.game.js
   Requires:
     - zombies.core.js
     - zombies.render.js
     - zombies.assets.js (optional)
     - zombies.world.js (optional)
   Provides:
     - window.BCO_ZOMBIES_GAME

   LUX upgrades:
     - iOS-friendly landscape: dynamic safe-area + viewport tracking
     - Dual-stick always works (Pointer Events)
     - Roguelike HUD shows: HP + ARMOR + PLATES + COINS + KILLS + WAVE + AMMO
     - Action buttons: Reload + Plate + Shop (buy perks) + Upgrade + Reroll
     - Shop fully usable (pointer-events, not blocked by overlay)
     - No code cuts; backwards compatible with old CORE (will soft-disable missing features)
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

  function cssSafe() {
    // robust safe-area fallback for older webviews
    const top = `max(env(safe-area-inset-top), 0px)`;
    const bot = `max(env(safe-area-inset-bottom), 0px)`;
    const left = `max(env(safe-area-inset-left), 0px)`;
    const right = `max(env(safe-area-inset-right), 0px)`;
    return { top, bot, left, right };
  }

  // ---------------------------------------------------------
  // Overlay build
  // ---------------------------------------------------------
  function ensureOverlay() {
    if (overlay) return;

    const safe = cssSafe();

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
      padding-top:${safe.top};
      padding-bottom:${safe.bot};
      padding-left:${safe.left};
      padding-right:${safe.right};
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
      background: linear-gradient(180deg, rgba(0,0,0,.55), rgba(0,0,0,0));
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
      <div id="bco-z-sub" style="font:800 12px/1.1 Inter,system-ui; opacity:.72;">ARCADE • Ashes</div>
    `;

    left.appendChild(badge);
    left.appendChild(title);

    const right = document.createElement("div");
    right.style.cssText = `display:flex; gap:10px; align-items:center;`;

    const pill = document.createElement("div");
    pill.id = "bco-z-hud";
    pill.style.cssText = `
      padding:10px 12px; border-radius:14px;
      font:900 12px/1 Inter,system-ui;
      background: rgba(255,255,255,.08);
      border:1px solid rgba(255,255,255,.12);
      color: rgba(255,255,255,.92);
      white-space: nowrap;
      max-width: 78vw;
      overflow:hidden;
      text-overflow: ellipsis;
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

    // Bottom controls layer
    const bottom = document.createElement("div");
    bottom.style.cssText = `
      position:absolute; left:0; right:0; bottom:0;
      height:240px;
      padding:10px 12px calc(10px + env(safe-area-inset-bottom));
      box-sizing:border-box;
      pointer-events:none;
      background: linear-gradient(0deg, rgba(0,0,0,.62), rgba(0,0,0,0));
    `;
    overlay.appendChild(bottom);

    // Dual sticks (big, iOS-friendly)
    const joyL = mkStick("left");
    const joyR = mkStick("right");
    bottom.appendChild(joyL.base);
    bottom.appendChild(joyR.base);

    // Right-side action stack (Reload/Plate)
    const action = document.createElement("div");
    action.id = "bco-z-actions";
    action.style.cssText = `
      position:absolute;
      right: 200px;
      bottom: calc(14px + env(safe-area-inset-bottom));
      display:flex;
      flex-direction:column;
      gap:10px;
      pointer-events:auto;
      z-index:2;
    `;
    bottom.appendChild(action);

    const btnReload = mkBtn("🔄 Reload", () => {
      if (typeof CORE.reload === "function") {
        const ok = CORE.reload();
        haptic("impact", ok ? "medium" : "light");
      } else {
        haptic("notif", "warning");
      }
    }, { w: 112 });

    const btnPlate = mkBtn("🛡 Plate", () => {
      if (typeof CORE.usePlate === "function") {
        const ok = CORE.usePlate();
        haptic("impact", ok ? "medium" : "light");
      } else {
        haptic("notif", "warning");
      }
    }, { w: 112 });

    action.appendChild(btnReload);
    action.appendChild(btnPlate);

    // Shop bar (roguelike)
    const shop = document.createElement("div");
    shop.id = "bco-z-shop";
    shop.style.cssText = `
      position:absolute;
      left:50%; transform:translateX(-50%);
      bottom: calc(14px + env(safe-area-inset-bottom));
      display:flex; gap:10px;
      pointer-events:auto;
      opacity:0;
      transition: opacity .18s ease, transform .18s ease;
      z-index:3;
    `;
    bottom.appendChild(shop);

    // Upgrade/Reroll row (roguelike)
    const upgrades = document.createElement("div");
    upgrades.id = "bco-z-upgrades";
    upgrades.style.cssText = `
      position:absolute;
      left:50%; transform:translateX(-50%);
      bottom: calc(74px + env(safe-area-inset-bottom));
      display:flex; gap:10px;
      pointer-events:auto;
      opacity:0;
      transition: opacity .18s ease, transform .18s ease;
      z-index:3;
    `;
    bottom.appendChild(upgrades);

    const btnUpg = mkBtn("⬆️ Upgrade", () => {
      // soft-compat: if CORE has weapon upgrade mechanics, call it; else buy Mag as placeholder
      let ok = false;
      try {
        if (CORE?.state?.weapon && typeof CORE?.state?.weapon?.upgrade === "number") {
          // cheap upgrade cost curve (UI-side helper), CORE can ignore if it wants
          const S = CORE.state;
          const w = S.weapon;
          const cost = 8 + (w.upgrade | 0) * 6;
          if (CORE.meta.mode !== "roguelike") ok = false;
          else if ((S.coins | 0) >= cost) {
            S.coins -= cost;
            w.upgrade = Math.min(9, (w.upgrade | 0) + 1);
            // rebuild effective maxima if core supports mkWeapon; many cores do internally
            if (typeof CORE.setWeapon === "function") CORE.setWeapon(CORE.meta.weaponKey);
            ok = true;
          }
        }
      } catch {}
      if (ok) haptic("notif", "success");
      else haptic("notif", "warning");
    }, { w: 126 });

    const btnReroll = mkBtn("🎲 Reroll", () => {
      // UI-only reroll: gives random weapon via setWeapon if available
      let ok = false;
      try {
        if (CORE.meta.mode === "roguelike" && CORE?.cfg?.weapons && typeof CORE.setWeapon === "function") {
          const keys = Object.keys(CORE.cfg.weapons);
          if (keys.length) {
            const key = keys[(Math.random() * keys.length) | 0];
            const cost = 6;
            if ((CORE.state.coins | 0) >= cost) {
              CORE.state.coins -= cost;
              CORE.setWeapon(key);
              ok = true;
            }
          }
        }
      } catch {}
      if (ok) haptic("notif", "success");
      else haptic("notif", "warning");
    }, { w: 126 });

    upgrades.appendChild(btnUpg);
    upgrades.appendChild(btnReroll);

    // Shop buttons (perks)
    shop.appendChild(mkBtn("🧪 Jug (12)", () => { if (CORE.buyPerk("Jug")) haptic("notif","success"); else haptic("notif","warning"); }, { w: 120 }));
    shop.appendChild(mkBtn("⚡ Speed (10)", () => { if (CORE.buyPerk("Speed")) haptic("notif","success"); else haptic("notif","warning"); }, { w: 124 }));
    shop.appendChild(mkBtn("📦 Mag (8)", () => { if (CORE.buyPerk("Mag")) haptic("notif","success"); else haptic("notif","warning"); }, { w: 110 }));
    shop.appendChild(mkBtn("🛡 Armor (14)", () => { if (CORE.buyPerk("Armor")) haptic("notif","success"); else haptic("notif","warning"); }, { w: 128 }));

    function mkBtn(txt, on, opt = {}) {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = txt;
      const w = opt.w ? `${opt.w}px` : "auto";
      b.style.cssText = `
        min-width:${w};
        padding:12px 14px; border-radius:16px;
        border:1px solid rgba(255,255,255,.14);
        background: rgba(255,255,255,.08);
        color: rgba(255,255,255,.92);
        font:900 12px/1 Inter,system-ui;
        letter-spacing:.2px;
        touch-action: manipulation;
        -webkit-tap-highlight-color: transparent;
      `;
      b.addEventListener("click", (e) => {
        e.preventDefault();
        try { on?.(e); } catch {}
      }, { passive: false });
      return b;
    }

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
        -webkit-tap-highlight-color: transparent;
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

    // Sticks
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
    setRogueUI(CORE.meta.mode === "roguelike");

    // local refs
    overlay._bco = { shop, upgrades, action, joyL, joyR };
  }

  function setRogueUI(isRogue) {
    if (!overlay?._bco) return;
    const { shop, upgrades } = overlay._bco;

    const on = isRogue ? "1" : "0";
    shop.style.opacity = on;
    upgrades.style.opacity = on;

    // tiny lift when visible
    shop.style.transform = `translateX(-50%) translateY(${isRogue ? "0px" : "10px"})`;
    upgrades.style.transform = `translateX(-50%) translateY(${isRogue ? "0px" : "10px"})`;
  }

  function destroyOverlay() {
    if (!overlay) return;
    try { overlay.remove(); } catch {}
    overlay = null;
    canvas = null;
    ctx = null;
  }

  // ---------------------------------------------------------
  // Stick math (premium: stable, deadzone)
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
      try { stick.base.setPointerCapture?.(e.pointerId); } catch {}
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
  // Resize (fix landscape / rotation)
  // ---------------------------------------------------------
  function resize() {
    if (!overlay || !canvas || !ctx) return;

    const r = overlay.getBoundingClientRect();
    dpr = Math.max(1, Math.min(3, window.devicePixelRatio || 1));

    canvas.width = Math.floor(r.width * dpr);
    canvas.height = Math.floor(r.height * dpr);

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    CORE.resize(r.width, r.height);
  }

  function scheduleResize() {
    // iOS sometimes reports stale sizes; do a quick two-step
    resize();
    setTimeout(resize, 50);
    setTimeout(resize, 180);
  }

  window.addEventListener("resize", scheduleResize, { passive: true });
  window.addEventListener("orientationchange", scheduleResize, { passive: true });
  try {
    window.visualViewport?.addEventListener?.("resize", scheduleResize, { passive: true });
    window.visualViewport?.addEventListener?.("scroll", scheduleResize, { passive: true });
  } catch {}

  // ---------------------------------------------------------
  // Loop
  // ---------------------------------------------------------
  function loop(t) {
    raf = requestAnimationFrame(loop);
    if (!overlay || !ctx) return;

    if (CORE.running) CORE.updateFrame(t);

    const r = overlay.getBoundingClientRect();
    const view = { w: r.width, h: r.height };

    // render
    RENDER.render(ctx, CORE, CORE.input, view);

    updateHud();
    checkDeathAutoSend();
  }

  let _sentDeath = false;

  function checkDeathAutoSend() {
    if (!CORE.running) {
      if (!_sentDeath && CORE?.state?.player?.hp <= 0) {
        _sentDeath = true;
        sendResult("dead");
        haptic("notif", "error");
      }
    }
  }

  function updateHud() {
    const sub = document.getElementById("bco-z-sub");
    const hud = document.getElementById("bco-z-hud");

    const S = CORE.state;
    const st = (typeof CORE._effectiveStats === "function") ? CORE._effectiveStats() : { hpMax: 100, armorMax: 0, platesMax: 0 };

    const hp = Math.max(0, Math.min(S.player.hp, st.hpMax || 100));
    const armor = Math.max(0, Math.min(S.player.armor || 0, st.armorMax || 0));
    const plates = Math.max(0, Math.min(S.player.plates || 0, st.platesMax || 0));

    const W = (typeof CORE._weaponEffective === "function")
      ? CORE._weaponEffective()
      : (S.weapon ? S.weapon : (CORE._weapon ? CORE._weapon() : { name: "SMG" }));

    const mag = (S.weapon && typeof S.weapon.mag === "number") ? (S.weapon.mag | 0) : null;
    const magMax = (typeof W.magMax === "number") ? (W.magMax | 0) : null;
    const reserve = (S.weapon && typeof S.weapon.reserve === "number") ? (S.weapon.reserve | 0) : null;

    if (sub) sub.textContent = `${String(CORE.meta.mode || "arcade").toUpperCase()} • ${String(CORE.meta.map || "Ashes")}`;

    // build HUD string with armor/ammo if exists
    let s = `❤️ ${hp|0}/${(st.hpMax|0) || 100}`;
    if ((st.armorMax|0) > 0 || armor > 0) s += ` • 🛡 ${armor|0}/${(st.armorMax|0) || 0}`;
    if ((st.platesMax|0) > 0 || plates > 0) s += ` • 🧩 ${plates|0}`;
    s += ` • ☠️ ${(S.kills|0)} • 🌊 ${(S.wave|0)} • 💰 ${(S.coins|0)} • 🔫 ${W.name || "SMG"}`;
    if (mag !== null && magMax !== null) {
      s += ` • ${mag}/${magMax}`;
      if (reserve !== null) s += ` (${reserve})`;
    }
    if (hud) hud.textContent = s;

    // roguelike UI toggles
    setRogueUI(CORE.meta.mode === "roguelike");

    // button hint state (plate/reload)
    try {
      const a = overlay?._bco?.action;
      if (a) {
        const btns = a.querySelectorAll("button");
        if (btns?.length >= 2) {
          // reload
          const canReload = (typeof CORE.reload === "function") && (S.weapon && (S.weapon.mag|0) < ((W.magMax|0) || 999)) && ((S.weapon.reserve|0) > 0) && !(S.reload?.active);
          btns[0].style.opacity = canReload ? "1" : "0.55";

          // plate
          const canPlate = (typeof CORE.usePlate === "function") && (CORE.meta.mode === "roguelike") && ((plates|0) > 0) && ((armor|0) < ((st.armorMax|0) || 0)) && !(S.player?.plating?.active);
          btns[1].style.opacity = canPlate ? "1" : "0.55";
        }
      }
    } catch {}
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

    const perks = S.perks || {};
    const perkScore =
      (perks.Jug ? 150 : 0) +
      (perks.Speed ? 120 : 0) +
      (perks.Mag ? 80 : 0) +
      (perks.Armor ? 140 : 0) +
      (perks.Reload ? 110 : 0) +
      (perks.Crit ? 130 : 0) +
      (perks.Loot ? 120 : 0) +
      (perks.Sprint ? 90 : 0);

    const armorBonus = Math.min(180, Math.max(0, (S.player.armor | 0)));
    const lvl = Math.max(1, (S.level | 0));
    const lvlBonus = Math.min(800, (lvl - 1) * 40);

    return Math.round(base + waveBonus + pace + perkScore + armorBonus + lvlBonus);
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
      perks: { ...(S.perks || {}) },

      // LUX extras (safe)
      hp: S.player?.hp ?? null,
      armor: S.player?.armor ?? null,
      plates: S.player?.plates ?? null,
      xp: S.xp ?? null,
      level: S.level ?? null,
      ammo: (S.weapon && typeof S.weapon.mag === "number") ? { mag: S.weapon.mag, reserve: S.weapon.reserve } : null
    };

    safeSendData(payload);
  }

  // ---------------------------------------------------------
  // Public API
  // ---------------------------------------------------------
  const API = {
    open() {
      ensureOverlay();
      scheduleResize();
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
      scheduleResize();
      _sentDeath = false;

      const r = overlay.getBoundingClientRect();
      CORE.start(mode, r.width, r.height, opts);

      if (!raf) raf = requestAnimationFrame(loop);

      // ensure UI toggles
      setRogueUI(CORE.meta.mode === "roguelike");

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
      setRogueUI(CORE.meta.mode === "roguelike");
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

    reload() {
      if (typeof CORE.reload !== "function") return false;
      const ok = CORE.reload();
      if (ok) haptic("impact", "medium");
      else haptic("impact", "light");
      return ok;
    },

    usePlate() {
      if (typeof CORE.usePlate !== "function") return false;
      const ok = CORE.usePlate();
      if (ok) haptic("impact", "medium");
      else haptic("impact", "light");
      return ok;
    },

    sendResult(reason) {
      sendResult(reason || "manual");
      return true;
    }
  };

  window.BCO_ZOMBIES_GAME = API;
  console.log("[Z_GAME] ready (LUX)");
})();
