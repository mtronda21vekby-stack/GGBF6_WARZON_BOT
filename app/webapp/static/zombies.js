// app/webapp/static/zombies.js
(() => {
  "use strict";

  // =========================================================
  // BLACK CROWN OPS — Zombies Survival (UI + Render wrapper)
  // Engine: window.BCO_ZOMBIES_CORE (required)
  // Optional: window.BCO_ZOMBIES_ASSETS, window.BCO_ZOMBIES_PERKS
  //
  // ✅ Dual-stick:
  //   - LEFT joystick = movement
  //   - RIGHT aim joystick = FIRE button drag (direction) + hold = shooting
  //   - You can move + aim + shoot одновременно
  // =========================================================

  const tg = window.Telegram?.WebApp || null;
  const CORE = () => window.BCO_ZOMBIES_CORE || null;
  const ASSETS = () => window.BCO_ZOMBIES_ASSETS || null;
  const PERKS = () => window.BCO_ZOMBIES_PERKS || null;

  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const len = (x, y) => Math.hypot(x, y) || 0;
  const norm = (x, y) => {
    const L = len(x, y);
    if (!L) return { x: 0, y: 0, L: 0 };
    return { x: x / L, y: y / L, L };
  };

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
  // Overlay mount
  // =========================================================
  const mount = () => document.getElementById("zOverlayMount");

  let overlay = null;
  let canvas = null;
  let ctx = null;
  let dpr = 1;
  let W = 0;
  let H = 0;

  let hudTop = null;
  let hudBottom = null;
  let btnClose = null;

  let joy = null;
  let joyInner = null;

  let fireBtn = null;
  let fireInner = null;
  let shopBar = null;

  const shopBtns = {};

  // ui config (lux touch zones)
  const UI = {
    safePad: 12,
    hudH: 68,
    bottomH: 170,
    joystick: { outer: 66, inner: 28, dead: 0.08 },
    fire: { outer: 54, inner: 24, dead: 0.05 }
  };

  // =========================================================
  // Input (Dual-stick)
  // =========================================================
  const input = {
    // left movement stick
    joyActive: false,
    joyId: null,
    joyBaseX: 0,
    joyBaseY: 0,
    moveX: 0,
    moveY: 0,

    // right aim stick (on FIRE)
    aimActive: false,
    aimId: null,
    aimBaseX: 0,
    aimBaseY: 0,
    aimX: 1,
    aimY: 0,

    // shooting
    firing: false
  };

  function setJoyVisual(nx, ny) {
    if (!joyInner) return;
    const r = UI.joystick.outer - UI.joystick.inner - 6;
    joyInner.style.transform = `translate(calc(-50% + ${nx * r}px), calc(-50% + ${ny * r}px))`;
  }

  function setFireVisual(nx, ny) {
    if (!fireInner) return;
    const r = UI.fire.outer - UI.fire.inner - 8;
    fireInner.style.transform = `translate(calc(-50% + ${nx * r}px), calc(-50% + ${ny * r}px))`;
  }

  function joyReset() {
    input.joyActive = false;
    input.joyId = null;
    input.moveX = 0;
    input.moveY = 0;
    setJoyVisual(0, 0);
    const C = CORE();
    if (C) C.setMove(0, 0);
  }

  function aimReset() {
    input.aimActive = false;
    input.aimId = null;
    input.aimX = 1;
    input.aimY = 0;
    setFireVisual(0, 0);
    const C = CORE();
    if (C) C.setAim(1, 0);
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
      background: radial-gradient(1200px 800px at 50% 35%, rgba(255,255,255,.06), rgba(0,0,0,.78)),
                  linear-gradient(180deg, rgba(6,6,10,.90), rgba(0,0,0,.94));
      overflow: hidden;
      touch-action: none;
      -webkit-user-select: none;
      user-select: none;
    `;

    // top hud
    hudTop = document.createElement("div");
    hudTop.style.cssText = `
      position: absolute;
      left: 0; right: 0; top: 0;
      height: ${UI.hudH}px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px 12px;
      box-sizing: border-box;
      pointer-events: auto;
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      background: linear-gradient(180deg, rgba(0,0,0,.52), rgba(0,0,0,0));
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
      <div style="font: 900 14px/1.1 Inter, system-ui; letter-spacing:.2px;">Zombies Survival</div>
      <div id="bco-z-sub" style="font: 700 12px/1.1 Inter, system-ui; opacity:.72;">ARCADE • Wave 1</div>
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
      font: 800 12px/1 Inter, system-ui;
      background: rgba(255,255,255,.08);
      border: 1px solid rgba(255,255,255,.12);
      color: rgba(255,255,255,.92);
      white-space: nowrap;
    `;
    pill.textContent = `❤️ 100 • ☠️ 0 • 💰 0 • 🔫 SMG`;

    btnClose = document.createElement("button");
    btnClose.type = "button";
    btnClose.textContent = "✖";
    btnClose.style.cssText = `
      width: 42px; height: 42px; border-radius: 14px;
      border: 1px solid rgba(255,255,255,.14);
      background: rgba(255,255,255,.08);
      color: rgba(255,255,255,.92);
      font: 900 16px/1 Inter, system-ui;
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
      display: block;
    `;

    // bottom controls
    hudBottom = document.createElement("div");
    hudBottom.style.cssText = `
      position: absolute;
      left: 0; right: 0; bottom: 0;
      height: ${UI.bottomH}px;
      padding: 10px 12px calc(10px + env(safe-area-inset-bottom));
      box-sizing: border-box;
      pointer-events: none;
      background: linear-gradient(0deg, rgba(0,0,0,.58), rgba(0,0,0,0));
    `;

    // left joystick
    joy = document.createElement("div");
    joy.id = "bco-z-joy";
    joy.style.cssText = `
      position: absolute;
      left: ${UI.safePad}px;
      bottom: calc(${UI.safePad}px + env(safe-area-inset-bottom));
      width: ${UI.joystick.outer * 2}px;
      height: ${UI.joystick.outer * 2}px;
      border-radius: 999px;
      background: rgba(255,255,255,.06);
      border: 1px solid rgba(255,255,255,.10);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      pointer-events: auto;
      touch-action: none;
    `;

    joyInner = document.createElement("div");
    joyInner.id = "bco-z-joy-inner";
    joyInner.style.cssText = `
      position:absolute;
      left: 50%; top: 50%;
      width: ${UI.joystick.inner * 2}px;
      height: ${UI.joystick.inner * 2}px;
      border-radius: 999px;
      transform: translate(-50%,-50%);
      background: rgba(255,255,255,.14);
      border: 1px solid rgba(255,255,255,.16);
      box-shadow: 0 12px 30px rgba(0,0,0,.35);
      pointer-events: none;
    `;
    joy.appendChild(joyInner);

    // right FIRE (aim stick)
    fireBtn = document.createElement("div");
    fireBtn.id = "bco-z-fire";
    fireBtn.style.cssText = `
      position: absolute;
      right: ${UI.safePad}px;
      bottom: calc(${UI.safePad}px + env(safe-area-inset-bottom));
      width: ${UI.fire.outer * 2}px;
      height: ${UI.fire.outer * 2}px;
      border-radius: 999px;
      border: 1px solid rgba(255,255,255,.18);
      background: radial-gradient(circle at 35% 30%, rgba(255,255,255,.18), rgba(255,255,255,.06));
      box-shadow: 0 18px 40px rgba(0,0,0,.45);
      pointer-events: auto;
      touch-action: none;
      display:flex;
      align-items:center;
      justify-content:center;
      color: rgba(255,255,255,.92);
      font: 950 13px/1 Inter, system-ui;
      letter-spacing: .6px;
    `;
    fireBtn.textContent = "FIRE";

    fireInner = document.createElement("div");
    fireInner.id = "bco-z-fire-inner";
    fireInner.style.cssText = `
      position:absolute;
      left: 50%; top: 50%;
      width: ${UI.fire.inner * 2}px;
      height: ${UI.fire.inner * 2}px;
      border-radius: 999px;
      transform: translate(-50%,-50%);
      background: linear-gradient(135deg, rgba(139,92,246,.35), rgba(34,211,238,.18));
      border: 1px solid rgba(255,255,255,.18);
      box-shadow: 0 14px 35px rgba(0,0,0,.35);
      pointer-events: none;
      opacity: .95;
    `;
    fireBtn.appendChild(fireInner);

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
      opacity: 0;
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
        font: 900 12px/1 Inter, system-ui;
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

    wireControls();

    resize();
    syncShopLabels();
    updateHud();
  }

  function destroyOverlay() {
    if (!overlay) return;
    try { overlay.remove(); } catch {}

    overlay = null;
    canvas = null;
    ctx = null;
    dpr = 1;
    W = 0;
    H = 0;

    hudTop = null;
    hudBottom = null;
    btnClose = null;

    joy = null;
    joyInner = null;
    fireBtn = null;
    fireInner = null;
    shopBar = null;
  }

  // =========================================================
  // DPR sizing
  // =========================================================
  function resize() {
    if (!canvas || !ctx) return;
    const rect = canvas.getBoundingClientRect();
    W = Math.max(1, rect.width);
    H = Math.max(1, rect.height);
    dpr = Math.max(1, Math.min(3, window.devicePixelRatio || 1));

    canvas.width = Math.floor(W * dpr);
    canvas.height = Math.floor(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const C = CORE();
    if (C) C.resize(W, H);
  }

  // =========================================================
  // Controls: pointer first, touch fallback
  // =========================================================
  function wireControls() {
    if (!canvas || !joy || !fireBtn) return;

    const joyRect = () => joy.getBoundingClientRect();
    const fireRect = () => fireBtn.getBoundingClientRect();

    const joyDown = (id, x, y) => {
      input.joyActive = true;
      input.joyId = id;
      const r = joyRect();
      input.joyBaseX = r.left + r.width / 2;
      input.joyBaseY = r.top + r.height / 2;
      joyMove(id, x, y);
    };

    const joyMove = (id, x, y) => {
      if (!input.joyActive || input.joyId !== id) return;

      const dx = x - input.joyBaseX;
      const dy = y - input.joyBaseY;

      const outer = UI.joystick.outer;
      const n = norm(dx, dy);
      const mag = clamp(n.L / outer, 0, 1);

      const dead = UI.joystick.dead;
      const m = mag < dead ? 0 : (mag - dead) / (1 - dead);

      input.moveX = n.x * m;
      input.moveY = n.y * m;

      setJoyVisual(input.moveX, input.moveY);

      const C = CORE();
      if (C) C.setMove(input.moveX, input.moveY);
    };

    const joyUp = (id) => {
      if (!input.joyActive || input.joyId !== id) return;
      joyReset();
    };

    const aimDown = (id, x, y) => {
      input.aimActive = true;
      input.aimId = id;

      // anchor at FIRE center (right stick)
      const r = fireRect();
      input.aimBaseX = r.left + r.width / 2;
      input.aimBaseY = r.top + r.height / 2;

      input.firing = true;
      aimMove(id, x, y);
      const C = CORE();
      if (C) C.setShooting(true);

      haptic("impact", "light");
    };

    const aimMove = (id, x, y) => {
      if (!input.aimActive || input.aimId !== id) return;

      const dx = x - input.aimBaseX;
      const dy = y - input.aimBaseY;

      const outer = UI.fire.outer;
      const n = norm(dx, dy);
      const mag = clamp(n.L / outer, 0, 1);

      const dead = UI.fire.dead;
      const m = mag < dead ? 0 : (mag - dead) / (1 - dead);

      // stick visual
      setFireVisual(n.x * m, n.y * m);

      // aim vector (direction)
      if (n.L > 2) {
        input.aimX = n.x;
        input.aimY = n.y;
        const C = CORE();
        if (C) C.setAim(input.aimX, input.aimY);
      }
    };

    const aimUp = (id) => {
      if (!input.aimActive || input.aimId !== id) return;
      input.aimActive = false;
      input.aimId = null;
      input.firing = false;
      setFireVisual(0, 0);

      const C = CORE();
      if (C) C.setShooting(false);
    };

    // pointer
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

      fireBtn.addEventListener("pointerdown", (e) => {
        e.preventDefault();
        fireBtn.setPointerCapture?.(e.pointerId);
        aimDown(e.pointerId, e.clientX, e.clientY);
      }, { passive: false });

      fireBtn.addEventListener("pointermove", (e) => {
        if (!input.aimActive) return;
        e.preventDefault();
        aimMove(e.pointerId, e.clientX, e.clientY);
      }, { passive: false });

      fireBtn.addEventListener("pointerup", (e) => { e.preventDefault(); aimUp(e.pointerId); }, { passive: false });
      fireBtn.addEventListener("pointercancel", (e) => { e.preventDefault(); aimUp(e.pointerId); }, { passive: false });
      fireBtn.addEventListener("pointerleave", (e) => { e.preventDefault(); aimUp(e.pointerId); }, { passive: false });
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

      fireBtn.addEventListener("touchstart", (e) => {
        e.preventDefault();
        const t = e.changedTouches[0];
        if (!t) return;
        aimDown(t.identifier, t.clientX, t.clientY);
      }, { passive: false });

      fireBtn.addEventListener("touchmove", (e) => {
        e.preventDefault();
        for (const t of e.changedTouches) aimMove(t.identifier, t.clientX, t.clientY);
      }, { passive: false });

      fireBtn.addEventListener("touchend", (e) => {
        e.preventDefault();
        for (const t of e.changedTouches) aimUp(t.identifier);
      }, { passive: false });

      fireBtn.addEventListener("touchcancel", (e) => {
        e.preventDefault();
        for (const t of e.changedTouches) aimUp(t.identifier);
      }, { passive: false });
    }

    window.addEventListener("resize", () => resize(), { passive: true });
  }

  // =========================================================
  // Render
  // =========================================================
  function drawFallbackPlayer(x, y, dirX, dirY) {
    ctx.save();
    ctx.translate(x, y);

    ctx.globalAlpha = 0.95;
    ctx.fillStyle = "rgba(255,255,255,.92)";
    ctx.beginPath();
    ctx.arc(0, 0, 18, 0, Math.PI * 2);
    ctx.fill();

    // face dir
    const n = norm(dirX, dirY);
    ctx.globalAlpha = 0.28;
    ctx.fillStyle = "rgba(34,211,238,.9)";
    ctx.beginPath();
    ctx.arc(n.x * 9, n.y * 9, 4.5, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
  }

  function drawFallbackZombie(x, y) {
    ctx.save();
    ctx.translate(x, y);

    ctx.globalAlpha = 0.95;
    ctx.fillStyle = "rgba(34,197,94,.85)";
    ctx.beginPath();
    ctx.arc(0, 0, 17, 0, Math.PI * 2);
    ctx.fill();

    ctx.globalAlpha = 0.28;
    ctx.fillStyle = "rgba(0,0,0,.55)";
    ctx.beginPath();
    ctx.arc(-6, -4, 3, 0, Math.PI * 2);
    ctx.arc(6, -4, 3, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
  }

  function drawSprite(kind, x, y, dirX, dirY) {
    const A = ASSETS();
    if (!A || !A.SPRITES || !A.drawSprite) {
      if (kind === "player") drawFallbackPlayer(x, y, dirX, dirY);
      else drawFallbackZombie(x, y);
      return;
    }

    const spr = (kind === "player")
      ? (A.SPRITES.player || A.SPRITES.player_idle || null)
      : (A.SPRITES.zombie || A.SPRITES.zombie_walk || null);

    if (!spr) {
      if (kind === "player") drawFallbackPlayer(x, y, dirX, dirY);
      else drawFallbackZombie(x, y);
      return;
    }

    try {
      const a = Math.atan2(dirY, dirX);
      A.drawSprite(ctx, spr, x, y, { rot: a });
    } catch {
      if (kind === "player") drawFallbackPlayer(x, y, dirX, dirY);
      else drawFallbackZombie(x, y);
    }
  }

  function drawAimReticle(camX, camY, px, py, ax, ay) {
    const sx = (px - camX) + W / 2;
    const sy = (py - camY) + H / 2;

    const r1 = 34;
    const r2 = 64;

    ctx.save();
    ctx.translate(sx, sy);

    ctx.globalAlpha = 0.46;
    ctx.strokeStyle = "rgba(255,255,255,.78)";
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
    const C = CORE();
    if (!ctx || !C) return;

    const S = C.state;
    const cfg = C.cfg;

    ctx.clearRect(0, 0, W, H);

    // subtle bg
    ctx.save();
    ctx.fillStyle = "rgba(0,0,0,.18)";
    ctx.fillRect(0, 0, W, H);
    ctx.restore();

    const camX = S.camX;
    const camY = S.camY;

    // grid + arena
    ctx.save();
    ctx.translate(W / 2, H / 2);
    ctx.translate(-camX, -camY);

    // grid
    ctx.globalAlpha = 0.20;
    ctx.strokeStyle = "rgba(255,255,255,.10)";
    ctx.lineWidth = 1;
    const step = 80;
    const minX = camX - W / 2 - 200;
    const maxX = camX + W / 2 + 200;
    const minY = camY - H / 2 - 200;
    const maxY = camY + H / 2 + 200;

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
    ctx.arc(0, 0, cfg.arenaRadius, 0, Math.PI * 2);
    ctx.stroke();

    // bullets
    ctx.globalAlpha = 0.92;
    ctx.fillStyle = "rgba(255,255,255,.92)";
    for (const b of S.bullets) {
      ctx.beginPath();
      ctx.arc(b.x, b.y, (b.r || cfg.bullet.radius), 0, Math.PI * 2);
      ctx.fill();
    }

    // zombies
    for (const z of S.zombies) {
      drawSprite("zombie", z.x, z.y, z.vx, z.vy);
    }

    // player
    drawSprite("player", S.player.x, S.player.y, C.input.aimX, C.input.aimY);

    ctx.restore();

    drawAimReticle(camX, camY, S.player.x, S.player.y, C.input.aimX, C.input.aimY);
  }

  // =========================================================
  // HUD + shop labels
  // =========================================================
  function perkCost(id) {
    const C = CORE();
    const P = PERKS();
    if (!C) return 999;

    try {
      if (P?.cost) {
        const c = Number(P.cost(id, C));
        if (Number.isFinite(c)) return c;
      }
    } catch {}

    const p = C.cfg?.perks?.[id];
    return p ? (Number(p.cost) || 999) : 999;
  }

  function syncShopLabels() {
    const C = CORE();
    if (!C) return;

    const P = PERKS();
    const defs = {
      Jug:   { base: "🧪 Jug" },
      Speed: { base: "⚡ Speed" },
      Mag:   { base: "🔫 Ammo" }
    };

    for (const k of Object.keys(defs)) {
      const b = shopBtns[k];
      if (!b) continue;

      const cost = perkCost(k);
      const owned = !!C.state?.perks?.[k];

      let label = `${defs[k].base} (${cost})`;
      try {
        if (P?.label) {
          const s = P.label(k, C);
          if (s) label = String(s);
        }
      } catch {}

      if (owned) label = `${label} ✓`;

      b.textContent = label;
      b.disabled = owned;
      b.style.opacity = owned ? "0.55" : "1";
    }
  }

  function updateHud() {
    const C = CORE();
    if (!C) return;

    const sub = document.getElementById("bco-z-sub");
    const hud = document.getElementById("bco-z-hud");

    const st = C._effectiveStats();
    const hp = clamp(C.state.player.hp, 0, st.hpMax);
    const w = C._weapon();

    if (sub) sub.textContent = `${C.meta.mode.toUpperCase()} • Wave ${C.state.wave}`;
    if (hud) {
      hud.textContent =
        `❤️ ${Math.round(hp)}/${Math.round(st.hpMax)} • ☠️ ${C.state.kills} • 💰 ${C.state.coins} • 🔫 ${w.name}`;
    }

    if (shopBar) shopBar.style.opacity = (C.meta.mode === "roguelike") ? "1" : "0";
    syncShopLabels();
  }

  // =========================================================
  // Loop
  // =========================================================
  let rafId = 0;

  function loop(tms) {
    const C = CORE();
    if (!overlay || !C) return;

    rafId = requestAnimationFrame(loop);

    if (!C.running) {
      render();
      updateHud();
      return;
    }

    C.updateFrame(tms);

    // auto-dead
    if (!C.running && C.state.player.hp <= 0) {
      haptic("notif", "error");
      API.sendResult("dead");
    }

    render();
    updateHud();
  }

  // =========================================================
  // Open/Close + start/stop
  // =========================================================
  let openFlag = false;

  function openOverlay() {
    ensureOverlay();
    resize();

    openFlag = true;
    overlay.style.display = "block";
    overlay.style.opacity = "1";

    try { tg?.BackButton?.show?.(); } catch {}
    try { tg?.MainButton?.hide?.(); } catch {}
    try { tg?.expand?.(); } catch {}
    haptic("impact", "medium");

    if (!rafId) rafId = requestAnimationFrame(loop);
  }

  function closeOverlay() {
    openFlag = false;

    const C = CORE();
    if (C) C.stop();

    if (rafId) cancelAnimationFrame(rafId);
    rafId = 0;

    joyReset();
    aimReset();
    input.firing = false;

    try { tg?.BackButton?.hide?.(); } catch {}
    try { tg?.MainButton?.show?.(); } catch {}

    destroyOverlay();
  }

  function startRun() {
    const C = CORE();
    if (!C) throw new Error("BCO_ZOMBIES_CORE missing");

    if (!openFlag) openOverlay();

    C.start(C.meta.mode, W, H, {
      map: C.meta.map,
      character: C.meta.character,
      skin: C.meta.skin,
      weaponKey: C.meta.weaponKey
    });

    // sync aim + shooting
    C.setAim(input.aimX, input.aimY);
    C.setMove(input.moveX, input.moveY);
    C.setShooting(!!input.firing);

    haptic("notif", "success");
    updateHud();

    return true;
  }

  function stopRun(reason = "manual") {
    const C = CORE();
    if (C) C.stop();
    input.firing = false;
    if (C) C.setShooting(false);
    haptic("notif", reason === "dead" ? "error" : "warning");
    updateHud();
    return true;
  }

  // =========================================================
  // Results -> bot
  // =========================================================
  function score(C) {
    const S = C.state;
    const base = S.kills * 100;
    const waveBonus = (S.wave - 1) * 250;
    const timeSec = Math.max(1, S.timeMs / 1000);
    const pace = (S.kills / timeSec) * 100;
    const perks = (S.perks.Jug ? 150 : 0) + (S.perks.Speed ? 120 : 0) + (S.perks.Mag ? 80 : 0);
    return Math.round(base + waveBonus + pace + perks);
  }

  function sendResult(reason = "manual") {
    const C = CORE();
    if (!C) return false;

    const payload = {
      action: "game_result",
      game: "zombies",
      mode: C.meta.mode,
      reason,

      wave: C.state.wave,
      kills: C.state.kills,
      coins: C.state.coins,
      duration_ms: Math.round(C.state.timeMs),
      score: score(C),

      character: C.meta.character,
      skin: C.meta.skin,
      loadout: { weapon: C.meta.weaponKey },
      perks: { ...C.state.perks }
    };

    return safeSendData(payload);
  }

  // =========================================================
  // Shop / perks (module-first, fallback to CORE)
  // =========================================================
  function buyPerk(id) {
    const C = CORE();
    if (!C) return false;

    if (C.meta.mode !== "roguelike") { haptic("notif", "warning"); return false; }
    if (C.state?.perks?.[id]) { haptic("impact", "light"); return false; }

    // world hook first
    if (typeof C._buyPerk === "function") {
      try { C._buyPerk(C, id); } catch {}
    }

    const P = PERKS();
    if (P?.buy) {
      try {
        const ok = !!P.buy(id, C);
        haptic("notif", ok ? "success" : "warning");
        updateHud();
        return ok;
      } catch {
        haptic("notif", "warning");
        return false;
      }
    }

    const ok = !!C.buyPerk(id);
    haptic("notif", ok ? "success" : "warning");
    updateHud();
    return ok;
  }

  // =========================================================
  // Public API
  // =========================================================
  const API = {
    open() { if (!openFlag) openOverlay(); return true; },
    close() { closeOverlay(); return true; },
    start() { return startRun(); },
    stop() { return stopRun("manual"); },
    isOpen() { return !!openFlag; },

    setMode(mode) {
      const C = CORE();
      if (!C) return "arcade";
      const m = String(mode || "").toLowerCase();
      C.meta.mode = (m === "roguelike" || m === "rogue") ? "roguelike" : "arcade";
      if (shopBar) shopBar.style.opacity = (C.meta.mode === "roguelike") ? "1" : "0";
      updateHud();
      return C.meta.mode;
    },

    setMap(map) {
      const C = CORE();
      if (!C) return null;
      C.meta.map = String(map || "Ashes");
      return C.meta.map;
    },

    setCharacter(character, skin) {
      const C = CORE();
      if (!C) return { character: "male", skin: "default" };

      if (character) C.meta.character = String(character);
      if (skin) C.meta.skin = String(skin);

      const A = ASSETS();
      try { if (A?.setPlayerSkin) A.setPlayerSkin(C.meta.skin); } catch {}

      return { character: C.meta.character, skin: C.meta.skin };
    },

    setWeapon(key) {
      const C = CORE();
      if (!C) return null;
      C.setWeapon(key);
      updateHud();
      return C.meta.weaponKey;
    },

    buyPerk(id) { return buyPerk(id); },

    sendResult(reason) { return !!sendResult(reason || "manual"); },

    // hooks for world.js to wrap (pass-through to CORE)
    get core() { return CORE(); }
  };

  // Telegram Back button close overlay
  try {
    tg?.BackButton?.onClick?.(() => {
      if (openFlag) API.close();
    });
  } catch {}

  window.BCO_ZOMBIES = API;
  console.log("[Z] loaded");
})();
