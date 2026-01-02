// app/webapp/static/zombies.js
(() => {
  "use strict";

  // =========================================================
  //  BLACK CROWN OPS — Zombies Survival (Fullscreen)
  //  Move: left joystick
  //  Aim: touch/drag on canvas (right side recommended)
  //  Shoot: hold Fire button (works while moving + aiming)
  // =========================================================

  const tg = window.Telegram?.WebApp || null;

  const CFG = {
    tickHz: 60,
    dtMax: 1 / 20,

    // world scale in "world units" (we use pixels as world units with camera)
    arenaRadius: 1400,

    // player
    player: {
      speed: 320,
      hpMax: 100,
      hitbox: 18,
      iFramesMs: 220
    },

    // bullets
    bullet: {
      speed: 980,
      lifeMs: 900,
      radius: 4,
      pierce: 0
    },

    // zombies
    zombie: {
      baseSpeed: 150,
      baseHp: 34,
      radius: 18,
      damage: 10,
      touchDpsMs: 350
    },

    // waves
    wave: {
      baseCount: 7,
      countGrowth: 2,
      hpGrowth: 1.08,
      speedGrowth: 1.03,
      spawnRingMin: 520,
      spawnRingMax: 880
    },

    // weapons
    weapons: {
      SMG: { name: "SMG", rpm: 820, dmg: 10, spread: 0.08, recoil: 0.06, bullets: 1 },
      AR:  { name: "AR",  rpm: 640, dmg: 14, spread: 0.05, recoil: 0.08, bullets: 1 },
      SG:  { name: "SG",  rpm: 120, dmg: 8,  spread: 0.22, recoil: 0.12, bullets: 6 }
    },

    // UI
    ui: {
      safePad: 12,
      joystick: { outer: 62, inner: 28, dead: 0.08 },
      fire: { r: 44 },
      hudH: 68
    }
  };

  // =========================================================
  // Utils
  // =========================================================
  const now = () => performance.now();
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const len2 = (x, y) => Math.sqrt(x * x + y * y) || 0;
  const norm = (x, y) => {
    const L = len2(x, y);
    if (!L) return { x: 0, y: 0, L: 0 };
    return { x: x / L, y: y / L, L };
  };
  const rand = (a, b) => a + Math.random() * (b - a);
  const fmt = (n) => (Number(n) || 0).toFixed(0);

  function haptic(type = "impact", style = "medium") {
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
    } catch {
      return false;
    }
  }

  // =========================================================
  // Assets bridge (optional)
  // =========================================================
  const ASSETS = () => window.BCO_ZOMBIES_ASSETS || null;

  // =========================================================
  // Perks bridge (optional) — SOURCE OF TRUTH
  // Expecting window.BCO_ZOMBIES_PERKS with optional methods:
  //   cost(perkId, run) -> number
  //   canBuy(perkId, run) -> boolean
  //   buy(perkId, run) -> boolean  (should mutate run, decrease coins itself OR return {spent:n})
  //   apply(perkId, run) -> void
  //   tick(run, dt, tms) -> void
  // =========================================================
  const PERKS = () => window.BCO_ZOMBIES_PERKS || null;

  // =========================================================
  // DOM / Overlay
  // =========================================================
  const mount = () => document.getElementById("zOverlayMount");

  let overlay = null;
  let canvas = null;
  let ctx = null;
  let dpr = 1;

  // UI elements
  let hudTop = null;
  let btnClose = null;
  let hudBottom = null;

  // joystick + fire
  let joy = null;
  let fireBtn = null;
  let shopBar = null;

  // sizing
  let W = 0;
  let H = 0;

  // shop buttons refs (for dynamic label update)
  const shopBtns = {};

  // =========================================================
  // Input state
  // =========================================================
  const input = {
    // joystick
    joyActive: false,
    joyId: null,
    joyBaseX: 0,
    joyBaseY: 0,
    joyX: 0,
    joyY: 0,
    moveX: 0,
    moveY: 0,

    // aim
    aimActive: false,
    aimId: null,
    aimX: 1,
    aimY: 0,

    // fire
    firing: false
  };

  // =========================================================
  // Game state
  // =========================================================
  let openFlag = false;
  let running = false;
  let rafId = 0;

  const game = {
    mode: "arcade", // "roguelike"
    startedAtMs: 0,
    timeMs: 0,

    wave: 1,
    kills: 0,
    coins: 0,

    perks: {
      Jug: 0,
      Speed: 0,
      Mag: 0
    },

    weaponKey: "SMG",

    // cosmetics
    character: "male",
    skin: "default",

    // player
    p: {
      x: 0,
      y: 0,
      vx: 0,
      vy: 0,
      hp: CFG.player.hpMax,
      lastHitAt: -99999
    },

    bullets: [],
    zombies: [],

    // shooting
    shootAcc: {
      lastShotAt: 0
    }
  };

  function weapon() {
    return CFG.weapons[game.weaponKey] || CFG.weapons.SMG;
  }

  function effectiveStats() {
    // NOTE: base fallback perks, but PERKS module can override via tick/apply
    const jug = game.perks.Jug ? 1.35 : 1.0;
    const speed = game.perks.Speed ? 1.18 : 1.0;
    const mag = game.perks.Mag ? 1.0 : 1.0; // placeholder hook
    return {
      hpMax: Math.round(CFG.player.hpMax * jug),
      speed: CFG.player.speed * speed,
      mag
    };
  }

  // =========================================================
  // Build overlay DOM
  // =========================================================
  function ensureOverlay() {
    if (overlay) return;

    const host = mount();
    if (!host) throw new Error("zOverlayMount not found");

    overlay = document.createElement("div");
    overlay.id = "bco-z-overlay";
    overlay.setAttribute("aria-hidden", "false");
    overlay.style.cssText = `
      position: fixed;
      inset: 0;
      z-index: 999999;
      background: radial-gradient(1200px 800px at 50% 35%, rgba(255,255,255,.06), rgba(0,0,0,.75)),
                  linear-gradient(180deg, rgba(6,6,10,.88), rgba(0,0,0,.92));
      overflow: hidden;
      touch-action: none;
      -webkit-user-select: none;
      user-select: none;
    `;

    // top hud
    hudTop = document.createElement("div");
    hudTop.style.cssText = `
      position: absolute;
      left: 0;
      right: 0;
      top: 0;
      height: ${CFG.ui.hudH}px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px 12px;
      box-sizing: border-box;
      pointer-events: auto;
      backdrop-filter: blur(14px);
      background: linear-gradient(180deg, rgba(0,0,0,.45), rgba(0,0,0,0));
      border-bottom: 1px solid rgba(255,255,255,.08);
    `;

    const left = document.createElement("div");
    left.style.cssText = `display:flex;gap:10px;align-items:center;`;

    const badge = document.createElement("div");
    badge.textContent = "🧟";
    badge.style.cssText = `
      width: 38px; height: 38px; border-radius: 12px;
      display:flex;align-items:center;justify-content:center;
      background: rgba(255,255,255,.08);
      border: 1px solid rgba(255,255,255,.12);
    `;

    const title = document.createElement("div");
    title.innerHTML = `
      <div style="font: 800 14px/1.1 Inter, system-ui; letter-spacing:.2px;">Zombies Survival</div>
      <div id="bco-z-sub" style="font: 600 12px/1.1 Inter, system-ui; opacity:.7;">ARCADE • Wave 1</div>
    `;

    left.appendChild(badge);
    left.appendChild(title);

    const right = document.createElement("div");
    right.style.cssText = `display:flex;gap:10px;align-items:center;`;

    const pill = document.createElement("div");
    pill.id = "bco-z-hud";
    pill.style.cssText = `
      padding: 10px 12px;
      border-radius: 14px;
      font: 700 12px/1 Inter, system-ui;
      background: rgba(255,255,255,.08);
      border: 1px solid rgba(255,255,255,.12);
      color: rgba(255,255,255,.92);
      white-space: nowrap;
    `;
    pill.textContent = `❤️ ${CFG.player.hpMax} • ☠️ 0 • 💰 0 • 🔫 ${weapon().name}`;

    btnClose = document.createElement("button");
    btnClose.type = "button";
    btnClose.textContent = "✖";
    btnClose.style.cssText = `
      width: 42px; height: 42px; border-radius: 14px;
      border: 1px solid rgba(255,255,255,.14);
      background: rgba(255,255,255,.08);
      color: rgba(255,255,255,.92);
      font: 800 16px/1 Inter, system-ui;
      cursor: pointer;
      touch-action: manipulation;
    `;
    btnClose.addEventListener("click", () => API.close(), { passive: true });

    right.appendChild(pill);
    right.appendChild(btnClose);

    hudTop.appendChild(left);
    hudTop.appendChild(right);

    // canvas
    canvas = document.createElement("canvas");
    canvas.id = "bco-z-canvas";
    canvas.style.cssText = `
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      touch-action: none;
      display:block;
    `;

    // bottom hud / controls
    hudBottom = document.createElement("div");
    hudBottom.style.cssText = `
      position: absolute;
      left: 0;
      right: 0;
      bottom: 0;
      height: 160px;
      padding: 10px 12px calc(10px + env(safe-area-inset-bottom));
      box-sizing: border-box;
      pointer-events: none;
      background: linear-gradient(0deg, rgba(0,0,0,.55), rgba(0,0,0,0));
    `;

    // joystick
    joy = document.createElement("div");
    joy.id = "bco-z-joy";
    joy.style.cssText = `
      position: absolute;
      left: ${CFG.ui.safePad}px;
      bottom: calc(${CFG.ui.safePad}px + env(safe-area-inset-bottom));
      width: ${CFG.ui.joystick.outer * 2}px;
      height: ${CFG.ui.joystick.outer * 2}px;
      border-radius: 999px;
      background: rgba(255,255,255,.06);
      border: 1px solid rgba(255,255,255,.10);
      backdrop-filter: blur(10px);
      pointer-events: auto;
      touch-action: none;
    `;

    const joyInner = document.createElement("div");
    joyInner.id = "bco-z-joy-inner";
    joyInner.style.cssText = `
      position:absolute;
      left: 50%; top: 50%;
      width: ${CFG.ui.joystick.inner * 2}px;
      height: ${CFG.ui.joystick.inner * 2}px;
      border-radius: 999px;
      transform: translate(-50%,-50%);
      background: rgba(255,255,255,.14);
      border: 1px solid rgba(255,255,255,.16);
      box-shadow: 0 12px 30px rgba(0,0,0,.35);
    `;

    joy.appendChild(joyInner);

    // fire button
    fireBtn = document.createElement("button");
    fireBtn.type = "button";
    fireBtn.textContent = "FIRE";
    fireBtn.style.cssText = `
      position: absolute;
      right: ${CFG.ui.safePad}px;
      bottom: calc(${CFG.ui.safePad}px + env(safe-area-inset-bottom));
      width: ${CFG.ui.fire.r * 2}px;
      height: ${CFG.ui.fire.r * 2}px;
      border-radius: 999px;
      border: 1px solid rgba(255,255,255,.18);
      background: radial-gradient(circle at 35% 30%, rgba(255,255,255,.18), rgba(255,255,255,.06));
      color: rgba(255,255,255,.92);
      font: 900 13px/1 Inter, system-ui;
      letter-spacing:.6px;
      pointer-events: auto;
      touch-action: none;
      box-shadow: 0 18px 40px rgba(0,0,0,.45);
    `;

    // shop bar (roguelike)
    shopBar = document.createElement("div");
    shopBar.id = "bco-z-shop";
    shopBar.style.cssText = `
      position: absolute;
      left: 50%;
      transform: translateX(-50%);
      bottom: calc(14px + env(safe-area-inset-bottom));
      display: flex;
      gap: 10px;
      pointer-events: auto;
      touch-action: none;
      opacity: .0;
      transition: opacity .18s ease;
    `;

    function mkShopBtn(perkId, labelBase, onClick) {
      const b = document.createElement("button");
      b.type = "button";
      b.dataset.perkId = perkId;
      b.textContent = labelBase;
      b.style.cssText = `
        padding: 10px 12px;
        border-radius: 14px;
        border: 1px solid rgba(255,255,255,.14);
        background: rgba(255,255,255,.08);
        color: rgba(255,255,255,.92);
        font: 800 12px/1 Inter, system-ui;
        letter-spacing: .2px;
        touch-action: manipulation;
      `;
      b.addEventListener("click", onClick, { passive: true });
      shopBtns[perkId] = b;
      return b;
    }

    shopBar.appendChild(mkShopBtn("Jug",   "🧪 Jug",   () => API.buyPerk("Jug")));
    shopBar.appendChild(mkShopBtn("Speed", "⚡ Speed", () => API.buyPerk("Speed")));
    shopBar.appendChild(mkShopBtn("Mag",   "🔫 Ammo",  () => API.buyPerk("Mag")));

    hudBottom.appendChild(joy);
    hudBottom.appendChild(fireBtn);
    hudBottom.appendChild(shopBar);

    overlay.appendChild(canvas);
    overlay.appendChild(hudTop);
    overlay.appendChild(hudBottom);
    host.appendChild(overlay);

    ctx = canvas.getContext("2d", { alpha: true });

    // Prevent scroll / pinch
    overlay.addEventListener("touchmove", (e) => e.preventDefault(), { passive: false });
    overlay.addEventListener("gesturestart", (e) => e.preventDefault(), { passive: false });
    overlay.addEventListener("gesturechange", (e) => e.preventDefault(), { passive: false });

    // Wire input handlers
    wireControls(joyInner);

    // shop labels sync on mount
    syncShopLabels();
  }

  function destroyOverlay() {
    if (!overlay) return;
    try { overlay.remove(); } catch {}
    overlay = null;
    canvas = null;
    ctx = null;
    hudTop = null;
    hudBottom = null;
    btnClose = null;
    joy = null;
    fireBtn = null;
    shopBar = null;
  }

  // =========================================================
  // Sizing / DPR
  // =========================================================
  function resize() {
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    W = Math.max(1, rect.width);
    H = Math.max(1, rect.height);
    dpr = Math.max(1, Math.min(3, window.devicePixelRatio || 1));

    canvas.width = Math.floor(W * dpr);
    canvas.height = Math.floor(H * dpr);

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  // =========================================================
  // Controls wiring (pointer first, fallback touch)
  // =========================================================
  function setJoyVisual(nx, ny) {
    const inner = document.getElementById("bco-z-joy-inner");
    if (!inner) return;
    const r = CFG.ui.joystick.outer - CFG.ui.joystick.inner - 6;
    inner.style.transform = `translate(calc(-50% + ${nx * r}px), calc(-50% + ${ny * r}px))`;
  }

  function joyReset() {
    input.joyActive = false;
    input.joyId = null;
    input.moveX = 0;
    input.moveY = 0;
    setJoyVisual(0, 0);
  }

  function aimSetFromScreen(px, py) {
    const cam = camera();
    const sx = (game.p.x - cam.x) + W / 2;
    const sy = (game.p.y - cam.y) + H / 2;

    const dx = px - sx;
    const dy = py - sy;
    const n = norm(dx, dy);
    if (n.L > 3) {
      input.aimX = n.x;
      input.aimY = n.y;
    }
  }

  function wireControls() {
    if (!canvas) return;

    // FIRE button: hold to shoot
    if (fireBtn) {
      const down = (e) => {
        e.preventDefault?.();
        input.firing = true;
        haptic("impact", "light");
      };
      const up = (e) => {
        e.preventDefault?.();
        input.firing = false;
      };

      if (window.PointerEvent) {
        fireBtn.addEventListener("pointerdown", down, { passive: false });
        fireBtn.addEventListener("pointerup", up, { passive: false });
        fireBtn.addEventListener("pointercancel", up, { passive: false });
        fireBtn.addEventListener("pointerleave", up, { passive: false });
      } else {
        fireBtn.addEventListener("touchstart", down, { passive: false });
        fireBtn.addEventListener("touchend", up, { passive: false });
        fireBtn.addEventListener("touchcancel", up, { passive: false });
      }
    }

    // Joystick
    const joyRect = () => joy.getBoundingClientRect();

    const joyDown = (id, x, y) => {
      input.joyActive = true;
      input.joyId = id;
      const r = joyRect();
      input.joyBaseX = r.left + r.width / 2;
      input.joyBaseY = r.top + r.height / 2;

      const dx = x - input.joyBaseX;
      const dy = y - input.joyBaseY;

      const outer = CFG.ui.joystick.outer;
      const n = norm(dx, dy);
      const mag = clamp(n.L / outer, 0, 1);

      const dead = CFG.ui.joystick.dead;
      const m = mag < dead ? 0 : (mag - dead) / (1 - dead);

      input.moveX = n.x * m;
      input.moveY = n.y * m;
      setJoyVisual(input.moveX, input.moveY);
    };

    const joyMove = (id, x, y) => {
      if (!input.joyActive || input.joyId !== id) return;
      const dx = x - input.joyBaseX;
      const dy = y - input.joyBaseY;

      const outer = CFG.ui.joystick.outer;
      const n = norm(dx, dy);
      const mag = clamp(n.L / outer, 0, 1);

      const dead = CFG.ui.joystick.dead;
      const m = mag < dead ? 0 : (mag - dead) / (1 - dead);

      input.moveX = n.x * m;
      input.moveY = n.y * m;
      setJoyVisual(input.moveX, input.moveY);
    };

    const joyUp = (id) => {
      if (!input.joyActive || input.joyId !== id) return;
      joyReset();
    };

    // Aim
    const aimDown = (id, x, y) => {
      input.aimActive = true;
      input.aimId = id;
      aimSetFromScreen(x, y);
    };

    const aimMove = (id, x, y) => {
      if (!input.aimActive || input.aimId !== id) return;
      aimSetFromScreen(x, y);
    };

    const aimUp = (id) => {
      if (!input.aimActive || input.aimId !== id) return;
      input.aimActive = false;
      input.aimId = null;
    };

    if (window.PointerEvent) {
      joy.addEventListener("pointerdown", (e) => {
        e.preventDefault();
        joy.setPointerCapture?.(e.pointerId);
        joyDown(e.pointerId, e.clientX, e.clientY);
      }, { passive: false });

      joy.addEventListener("pointermove", (e) => {
        if (!input.joyActive) return;
        e.preventDefault();
        joyMove(e.pointerId, e.clientX, e.clientY);
      }, { passive: false });

      joy.addEventListener("pointerup", (e) => { e.preventDefault(); joyUp(e.pointerId); }, { passive: false });
      joy.addEventListener("pointercancel", (e) => { e.preventDefault(); joyUp(e.pointerId); }, { passive: false });

      canvas.addEventListener("pointerdown", (e) => {
        e.preventDefault();
        canvas.setPointerCapture?.(e.pointerId);
        aimDown(e.pointerId, e.clientX, e.clientY);
      }, { passive: false });

      canvas.addEventListener("pointermove", (e) => {
        if (!input.aimActive) return;
        e.preventDefault();
        aimMove(e.pointerId, e.clientX, e.clientY);
      }, { passive: false });

      canvas.addEventListener("pointerup", (e) => { e.preventDefault(); aimUp(e.pointerId); }, { passive: false });
      canvas.addEventListener("pointercancel", (e) => { e.preventDefault(); aimUp(e.pointerId); }, { passive: false });
    } else {
      joy.addEventListener("touchstart", (e) => {
        e.preventDefault();
        const t = e.changedTouches[0];
        if (!t) return;
        joyDown(t.identifier, t.clientX, t.clientY);
      }, { passive: false });

      joy.addEventListener("touchmove", (e) => {
        e.preventDefault();
        for (const t of e.changedTouches) joyMove(t.identifier, t.clientX, t.clientY);
      }, { passive: false });

      joy.addEventListener("touchend", (e) => {
        e.preventDefault();
        for (const t of e.changedTouches) joyUp(t.identifier);
      }, { passive: false });

      joy.addEventListener("touchcancel", (e) => {
        e.preventDefault();
        for (const t of e.changedTouches) joyUp(t.identifier);
      }, { passive: false });

      canvas.addEventListener("touchstart", (e) => {
        e.preventDefault();
        const t = e.changedTouches[0];
        if (!t) return;
        aimDown(t.identifier, t.clientX, t.clientY);
      }, { passive: false });

      canvas.addEventListener("touchmove", (e) => {
        e.preventDefault();
        for (const t of e.changedTouches) aimMove(t.identifier, t.clientX, t.clientY);
      }, { passive: false });

      canvas.addEventListener("touchend", (e) => {
        e.preventDefault();
        for (const t of e.changedTouches) aimUp(t.identifier);
      }, { passive: false });

      canvas.addEventListener("touchcancel", (e) => {
        e.preventDefault();
        for (const t of e.changedTouches) aimUp(t.identifier);
      }, { passive: false });
    }

    window.addEventListener("resize", () => resize(), { passive: true });
  }

  // =========================================================
  // Camera
  // =========================================================
  function camera() {
    return { x: game.p.x, y: game.p.y };
  }

  // =========================================================
  // World hooks (compat for zombies.world.js)
  // =========================================================
  // These are intentionally on API, so world.js can wrap them:
  //   const _tick = core._tickWorld; core._tickWorld = (run,dt,t)=>{...; if(_tick) _tick(...) }
  //   const _buy  = core._buyPerk;  core._buyPerk  = (run,perk)=>{...; if(_buy) _buy(...) }
  function tickWorld(run, dt, tms) {
    // default noop (world.js can wrap)
  }
  function buyWorldPerk(run, perkId) {
    // default noop (world.js can wrap)
  }

  // =========================================================
  // Game control
  // =========================================================
  function resetRun() {
    const st = effectiveStats();

    game.startedAtMs = now();
    game.timeMs = 0;
    game.wave = 1;
    game.kills = 0;
    game.coins = 0;

    game.perks = { Jug: 0, Speed: 0, Mag: 0 };
    game.weaponKey = "SMG";

    game.p.x = 0;
    game.p.y = 0;
    game.p.vx = 0;
    game.p.vy = 0;
    game.p.hp = st.hpMax;
    game.p.lastHitAt = -99999;

    game.bullets = [];
    game.zombies = [];

    game.shootAcc.lastShotAt = 0;

    input.aimX = 1;
    input.aimY = 0;

    spawnWave(game.wave);

    syncShopLabels();
    updateHud();
  }

  function spawnWave(w) {
    const count = CFG.wave.baseCount + (w - 1) * CFG.wave.countGrowth;
    const hpMul = Math.pow(CFG.wave.hpGrowth, (w - 1));
    const spMul = Math.pow(CFG.wave.speedGrowth, (w - 1));

    for (let i = 0; i < count; i++) {
      const ang = rand(0, Math.PI * 2);
      const r = rand(CFG.wave.spawnRingMin, CFG.wave.spawnRingMax);
      const x = game.p.x + Math.cos(ang) * r;
      const y = game.p.y + Math.sin(ang) * r;

      game.zombies.push({
        x, y,
        vx: 0, vy: 0,
        hp: CFG.zombie.baseHp * hpMul,
        sp: CFG.zombie.baseSpeed * spMul,
        nextTouchAt: 0
      });
    }
  }

  function openOverlay() {
    ensureOverlay();
    resize();

    openFlag = true;
    overlay.style.display = "block";
    overlay.style.opacity = "1";

    try { tg?.BackButton?.show?.(); } catch {}
    try { tg?.MainButton?.hide?.(); } catch {}
    try { tg?.expand?.(); } catch {}

    if (shopBar) shopBar.style.opacity = (game.mode === "roguelike") ? "1" : "0";

    haptic("impact", "medium");
  }

  function closeOverlay() {
    openFlag = false;
    running = false;
    if (rafId) cancelAnimationFrame(rafId);
    rafId = 0;

    joyReset();
    input.aimActive = false;
    input.aimId = null;
    input.firing = false;

    try { tg?.BackButton?.hide?.(); } catch {}
    try { tg?.MainButton?.show?.(); } catch {}

    destroyOverlay();
  }

  function startRun() {
    if (!openFlag) openOverlay();

    resetRun();
    running = true;

    loop(now());
    haptic("notif", "success");
  }

  function stopRun(reason = "manual") {
    running = false;
    if (rafId) cancelAnimationFrame(rafId);
    rafId = 0;

    updateHud();
    haptic("notif", reason === "dead" ? "error" : "warning");
  }

  // =========================================================
  // Combat
  // =========================================================
  function canShoot(tms) {
    const w = weapon();
    const intervalMs = (60_000 / w.rpm);
    return (tms - game.shootAcc.lastShotAt) >= intervalMs;
  }

  function shoot(tms) {
    if (!canShoot(tms)) return;
    const w = weapon();
    game.shootAcc.lastShotAt = tms;

    const sp = CFG.bullet.speed;

    const ax = input.aimX;
    const ay = input.aimY;

    const spread = w.spread;
    const bullets = w.bullets;

    for (let i = 0; i < bullets; i++) {
      const a = Math.atan2(ay, ax) + rand(-spread, spread);
      const dx = Math.cos(a);
      const dy = Math.sin(a);

      game.bullets.push({
        x: game.p.x + dx * 18,
        y: game.p.y + dy * 18,
        vx: dx * sp,
        vy: dy * sp,
        born: tms,
        life: CFG.bullet.lifeMs,
        dmg: w.dmg,
        pierce: CFG.bullet.pierce
      });
    }
  }

  function hitPlayer(tms) {
    const st = effectiveStats();
    const ifr = CFG.player.iFramesMs;
    if (tms - game.p.lastHitAt < ifr) return;

    game.p.lastHitAt = tms;
    game.p.hp = Math.max(0, game.p.hp - CFG.zombie.damage);
    haptic("impact", "light");

    if (game.p.hp <= 0) {
      stopRun("dead");
      sendResult("dead");
    }
  }

  // =========================================================
  // Physics / Update
  // =========================================================
  function update(dt, tms) {
    game.timeMs = tms - game.startedAtMs;

    // allow world modules to inject (maps/collisions/bosses)
    try { API._tickWorld(game, dt, tms); } catch {}

    // perks tick (regen etc) from module (if provided)
    try {
      const P = PERKS();
      if (P?.tick) P.tick(game, dt, tms);
    } catch {}

    // movement
    const st = effectiveStats();
    const mx = input.moveX;
    const my = input.moveY;

    const speed = st.speed;
    game.p.vx = mx * speed;
    game.p.vy = my * speed;
    game.p.x += game.p.vx * dt;
    game.p.y += game.p.vy * dt;

    // keep player in arena
    const pr = len2(game.p.x, game.p.y);
    if (pr > CFG.arenaRadius) {
      const n = norm(game.p.x, game.p.y);
      game.p.x = n.x * CFG.arenaRadius;
      game.p.y = n.y * CFG.arenaRadius;
    }

    // shooting
    if (input.firing && running) shoot(tms);

    // bullets
    for (let i = game.bullets.length - 1; i >= 0; i--) {
      const b = game.bullets[i];
      b.x += b.vx * dt;
      b.y += b.vy * dt;

      if ((tms - b.born) > b.life) {
        game.bullets.splice(i, 1);
        continue;
      }

      if (len2(b.x, b.y) > CFG.arenaRadius + 220) {
        game.bullets.splice(i, 1);
        continue;
      }
    }

    // zombies
    for (let i = game.zombies.length - 1; i >= 0; i--) {
      const z = game.zombies[i];

      const dx = game.p.x - z.x;
      const dy = game.p.y - z.y;
      const n = norm(dx, dy);

      z.vx = n.x * z.sp;
      z.vy = n.y * z.sp;

      z.x += z.vx * dt;
      z.y += z.vy * dt;

      const dist = len2(dx, dy);
      if (dist < (CFG.zombie.radius + CFG.player.hitbox)) {
        if (tms >= z.nextTouchAt) {
          z.nextTouchAt = tms + CFG.zombie.touchDpsMs;
          hitPlayer(tms);
        }
      }
    }

    // collisions: bullets vs zombies
    for (let bi = game.bullets.length - 1; bi >= 0; bi--) {
      const b = game.bullets[bi];
      let consumed = false;

      for (let zi = game.zombies.length - 1; zi >= 0; zi--) {
        const z = game.zombies[zi];
        const dx = z.x - b.x;
        const dy = z.y - b.y;
        const dist = len2(dx, dy);

        if (dist < (CFG.zombie.radius + CFG.bullet.radius)) {
          z.hp -= b.dmg;
          haptic("impact", "light");

          if (z.hp <= 0) {
            game.zombies.splice(zi, 1);
            game.kills += 1;
            game.coins += (game.mode === "roguelike") ? 2 : 1;
          }

          if (b.pierce > 0) {
            b.pierce -= 1;
          } else {
            consumed = true;
          }
          break;
        }
      }

      if (consumed) game.bullets.splice(bi, 1);
    }

    // next wave
    if (game.zombies.length === 0 && running) {
      game.wave += 1;
      spawnWave(game.wave);
      haptic("notif", "success");
    }

    updateHud();
  }

  // =========================================================
  // Render helpers
  // =========================================================
  function drawArena(cam) {
    ctx.save();
    ctx.translate(W / 2, H / 2);
    ctx.translate(-game.p.x + cam.x, -game.p.y + cam.y);

    ctx.globalAlpha = 0.22;
    ctx.lineWidth = 1;

    const step = 80;
    const minX = cam.x - W / 2 - 200;
    const maxX = cam.x + W / 2 + 200;
    const minY = cam.y - H / 2 - 200;
    const maxY = cam.y + H / 2 + 200;

    ctx.strokeStyle = "rgba(255,255,255,.10)";
    for (let x = Math.floor(minX / step) * step; x < maxX; x += step) {
      ctx.beginPath();
      ctx.moveTo(x, minY);
      ctx.lineTo(x, maxY);
      ctx.stroke();
    }
    for (let y = Math.floor(minY / step) * step; y < maxY; y += step) {
      ctx.beginPath();
      ctx.moveTo(minX, y);
      ctx.lineTo(maxX, y);
      ctx.stroke();
    }

    ctx.globalAlpha = 0.65;
    ctx.lineWidth = 3;
    ctx.strokeStyle = "rgba(255,255,255,.12)";
    ctx.beginPath();
    ctx.arc(0, 0, CFG.arenaRadius, 0, Math.PI * 2);
    ctx.stroke();

    ctx.restore();
  }

  function drawFallbackPlayer(x, y) {
    ctx.save();
    ctx.translate(x, y);
    ctx.fillStyle = "rgba(255,255,255,.92)";
    ctx.beginPath();
    ctx.arc(0, 0, 18, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = "rgba(255,255,255,.22)";
    ctx.beginPath();
    ctx.arc(6, -6, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  function drawFallbackZombie(x, y) {
    ctx.save();
    ctx.translate(x, y);
    ctx.fillStyle = "rgba(180,255,180,.82)";
    ctx.beginPath();
    ctx.arc(0, 0, 18, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = "rgba(0,0,0,.32)";
    ctx.beginPath();
    ctx.arc(-6, -4, 3, 0, Math.PI * 2);
    ctx.arc(6, -4, 3, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  function drawSprite(kind, x, y, dirX, dirY) {
    const A = ASSETS();
    if (!A || !A.SPRITES) {
      if (kind === "player") drawFallbackPlayer(x, y);
      else drawFallbackZombie(x, y);
      return;
    }

    const spr = (kind === "player")
      ? (A.SPRITES.player || A.SPRITES.player_idle || null)
      : (A.SPRITES.zombie || A.SPRITES.zombie_walk || null);

    if (!spr || !A.drawSprite) {
      if (kind === "player") drawFallbackPlayer(x, y);
      else drawFallbackZombie(x, y);
      return;
    }

    try {
      const a = Math.atan2(dirY, dirX);
      A.drawSprite(ctx, spr, x, y, { rot: a });
    } catch {
      if (kind === "player") drawFallbackPlayer(x, y);
      else drawFallbackZombie(x, y);
    }
  }

  function drawAimReticle(cam) {
    const sx = (game.p.x - cam.x) + W / 2;
    const sy = (game.p.y - cam.y) + H / 2;

    const ax = input.aimX;
    const ay = input.aimY;

    const r1 = 36;
    const r2 = 62;

    ctx.save();
    ctx.translate(sx, sy);

    ctx.globalAlpha = 0.45;
    ctx.strokeStyle = "rgba(255,255,255,.75)";
    ctx.lineWidth = 2;

    ctx.beginPath();
    ctx.moveTo(ax * r1, ay * r1);
    ctx.lineTo(ax * r2, ay * r2);
    ctx.stroke();

    ctx.globalAlpha = 0.22;
    ctx.beginPath();
    ctx.arc(ax * r2, ay * r2, 8, 0, Math.PI * 2);
    ctx.stroke();

    ctx.restore();
  }

  function render() {
    if (!ctx) return;

    ctx.clearRect(0, 0, W, H);

    const cam = camera();

    ctx.save();
    ctx.fillStyle = "rgba(0,0,0,.18)";
    ctx.fillRect(0, 0, W, H);
    ctx.restore();

    drawArena(cam);

    ctx.save();
    ctx.translate(W / 2, H / 2);
    ctx.translate(-cam.x, -cam.y);

    ctx.globalAlpha = 0.9;
    ctx.fillStyle = "rgba(255,255,255,.9)";
    for (const b of game.bullets) {
      ctx.beginPath();
      ctx.arc(b.x, b.y, CFG.bullet.radius, 0, Math.PI * 2);
      ctx.fill();
    }

    for (const z of game.zombies) {
      drawSprite("zombie", z.x, z.y, z.vx, z.vy);
    }

    drawSprite("player", game.p.x, game.p.y, input.aimX, input.aimY);

    ctx.restore();

    drawAimReticle(cam);
  }

  // =========================================================
  // HUD updates + shop label sync
  // =========================================================
  function perkCost(name) {
    const P = PERKS();
    try {
      if (P?.cost) {
        const c = Number(P.cost(name, game));
        if (Number.isFinite(c)) return c;
      }
    } catch {}
    if (name === "Jug") return 12;
    if (name === "Speed") return 10;
    if (name === "Mag") return 8;
    return 999;
  }

  function syncShopLabels() {
    const P = PERKS();
    const defs = {
      Jug:   { base: "🧪 Jug",   emoji: "🧪" },
      Speed: { base: "⚡ Speed", emoji: "⚡" },
      Mag:   { base: "🔫 Ammo",  emoji: "🔫" }
    };

    for (const k of Object.keys(defs)) {
      const b = shopBtns[k];
      if (!b) continue;

      const cost = perkCost(k);
      const owned = !!game.perks?.[k];

      // optional: let module provide label
      let label = `${defs[k].base} (${cost})`;
      try {
        if (P?.label) {
          const s = P.label(k, game);
          if (s) label = String(s);
        }
      } catch {}

      if (owned) label = `${label} ✓`;

      b.textContent = label;

      // disable button if owned (lux UX)
      b.disabled = owned;
      b.style.opacity = owned ? "0.55" : "1";
    }
  }

  function updateHud() {
    const sub = document.getElementById("bco-z-sub");
    const hud = document.getElementById("bco-z-hud");

    const st = effectiveStats();
    const hp = clamp(game.p.hp, 0, st.hpMax);

    if (sub) sub.textContent = `${game.mode.toUpperCase()} • Wave ${game.wave}`;

    if (hud) {
      hud.textContent =
        `❤️ ${fmt(hp)}/${fmt(st.hpMax)} • ☠️ ${fmt(game.kills)} • 💰 ${fmt(game.coins)} • 🔫 ${weapon().name}`;
    }

    if (shopBar) shopBar.style.opacity = (game.mode === "roguelike") ? "1" : "0";

    // keep shop labels live (prices/owned)
    syncShopLabels();
  }

  // =========================================================
  // Loop
  // =========================================================
  let lastT = 0;

  function loop(t) {
    if (!openFlag) return;
    rafId = requestAnimationFrame(loop);

    if (!running) {
      render();
      return;
    }

    if (!lastT) lastT = t;
    let dt = (t - lastT) / 1000;
    lastT = t;

    dt = Math.min(CFG.dtMax, Math.max(0, dt));

    update(dt, t);
    render();
  }

  // =========================================================
  // Shop / perks (now routed through module if present)
  // =========================================================
  function buyPerk(name) {
    if (game.mode !== "roguelike") { haptic("notif", "warning"); return false; }
    if (game.perks?.[name]) { haptic("impact", "light"); return false; }

    // allow world module to react first (maps/perk systems)
    try { API._buyPerk(game, name); } catch {}

    const P = PERKS();

    // If module provides buy() — it owns the logic
    if (P?.buy) {
      try {
        const ok = !!P.buy(name, game);
        if (ok) {
          haptic("notif", "success");
          updateHud();
          return true;
        }
        haptic("notif", "warning");
        return false;
      } catch {
        haptic("notif", "warning");
        return false;
      }
    }

    // Else fallback local buy (your previous behavior)
    const c = perkCost(name);
    if (game.coins < c) { haptic("notif", "warning"); return false; }

    game.coins -= c;
    game.perks[name] = 1;

    // apply max hp immediately
    const st = effectiveStats();
    game.p.hp = Math.min(game.p.hp + 18, st.hpMax);

    // If module has apply(), call it (soft integration)
    try { if (P?.apply) P.apply(name, game); } catch {}

    haptic("notif", "success");
    updateHud();
    return true;
  }

  // =========================================================
  // Results -> bot
  // =========================================================
  function score() {
    const base = game.kills * 100;
    const waveBonus = (game.wave - 1) * 250;
    const timeSec = Math.max(1, game.timeMs / 1000);
    const pace = (game.kills / timeSec) * 100;
    const perks = (game.perks.Jug ? 150 : 0) + (game.perks.Speed ? 120 : 0) + (game.perks.Mag ? 80 : 0);
    return Math.round(base + waveBonus + pace + perks);
  }

  function sendResult(reason = "manual") {
    const payload = {
      action: "game_result",
      game: "zombies",
      mode: game.mode,
      reason,

      wave: game.wave,
      kills: game.kills,
      coins: game.coins,
      duration_ms: Math.round(game.timeMs),
      score: score(),

      character: game.character,
      skin: game.skin,
      loadout: { weapon: game.weaponKey },
      perks: { ...game.perks }
    };

    safeSendData(payload);
  }

  // =========================================================
  // Public API
  // =========================================================
  const API = {
    // world hooks (for zombies.world.js wrapping)
    _tickWorld: tickWorld,
    _buyPerk: buyWorldPerk,

    open() {
      if (!openFlag) openOverlay();
      return true;
    },
    close() {
      closeOverlay();
      return true;
    },
    start() {
      startRun();
      return true;
    },
    stop() {
      stopRun("manual");
      return true;
    },
    isOpen() {
      return !!openFlag;
    },
    setMode(mode) {
      const m = (String(mode || "")).toLowerCase();
      game.mode = (m === "roguelike" || m === "rogue") ? "roguelike" : "arcade";
      if (shopBar) shopBar.style.opacity = (game.mode === "roguelike") ? "1" : "0";
      syncShopLabels();
      updateHud();
      return game.mode;
    },
    setCharacter(character, skin) {
      if (character) game.character = String(character);
      if (skin) game.skin = String(skin);

      const A = ASSETS();
      try {
        if (A?.setPlayerSkin) A.setPlayerSkin(game.skin);
      } catch {}
      return { character: game.character, skin: game.skin };
    },
    setWeapon(key) {
      if (CFG.weapons[key]) game.weaponKey = key;
      updateHud();
      return game.weaponKey;
    },
    buyPerk(name) {
      return buyPerk(name);
    },
    sendResult(reason) {
      sendResult(reason || "manual");
      return true;
    }
  };

  // Telegram Back button close overlay
  try {
    tg?.BackButton?.onClick?.(() => {
      if (openFlag) API.close();
    });
  } catch {}

  // Export
  window.BCO_ZOMBIES = API;
})();
