/* =========================================================
   BLACK CROWN OPS — ZOMBIES GAME (UI + RENDER + INPUT)
   File: app/webapp/static/zombies.game.js
   Требует:
     - zombies.core.js
     - zombies.assets.js
   ========================================================= */

(() => {
  "use strict";

  if (!window.BCO_ZOMBIES_CORE) {
    console.error("[Z_GAME] core missing");
    return;
  }

  const CORE = window.BCO_ZOMBIES_CORE;
  const ASSETS = () => window.BCO_ZOMBIES_ASSETS || null;
  const tg = window.Telegram?.WebApp || null;

  // =========================================================
  // DOM
  // =========================================================
  const mount = document.getElementById("zOverlayMount") || document.body;

  const overlay = document.createElement("div");
  overlay.id = "bco-z-game";
  overlay.style.cssText = `
    position:fixed; inset:0; z-index:999999;
    background:#05070c; overflow:hidden;
    touch-action:none; user-select:none;
  `;

  const canvas = document.createElement("canvas");
  canvas.style.cssText = `position:absolute; inset:0; width:100%; height:100%;`;
  overlay.appendChild(canvas);
  mount.appendChild(overlay);

  const ctx = canvas.getContext("2d", { alpha: true });

  // =========================================================
  // HUD
  // =========================================================
  const hud = document.createElement("div");
  hud.style.cssText = `
    position:absolute; left:12px; top:12px;
    padding:10px 14px; border-radius:14px;
    background:rgba(0,0,0,.45);
    color:#fff; font:700 13px system-ui;
    backdrop-filter:blur(10px);
  `;
  overlay.appendChild(hud);

  // =========================================================
  // CONTROLS (dual stick)
  // =========================================================
  const joyL = mkStick(16, "left");
  const joyR = mkStick(16, "right");

  function mkStick(pad, side) {
    const s = document.createElement("div");
    s.style.cssText = `
      position:absolute;
      bottom:${pad + 12}px;
      ${side === "left" ? "left" : "right"}:${pad}px;
      width:140px; height:140px;
      border-radius:50%;
      background:rgba(255,255,255,.05);
      border:1px solid rgba(255,255,255,.12);
      touch-action:none;
    `;
    const inner = document.createElement("div");
    inner.style.cssText = `
      position:absolute; left:50%; top:50%;
      width:56px; height:56px;
      transform:translate(-50%,-50%);
      border-radius:50%;
      background:rgba(255,255,255,.18);
    `;
    s.appendChild(inner);
    overlay.appendChild(s);
    return { base: s, knob: inner, id: null };
  }

  // =========================================================
  // RESIZE
  // =========================================================
  function resize() {
    const dpr = Math.min(3, window.devicePixelRatio || 1);
    const r = overlay.getBoundingClientRect();
    canvas.width = Math.floor(r.width * dpr);
    canvas.height = Math.floor(r.height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  window.addEventListener("resize", resize);
  resize();

  // =========================================================
  // INPUT
  // =========================================================
  const input = {
    moveX: 0, moveY: 0,
    aimX: 1, aimY: 0
  };

  function stickHandlers(stick, onMove) {
    const rect = () => stick.base.getBoundingClientRect();

    function down(e) {
      e.preventDefault();
      stick.id = e.pointerId;
      stick.base.setPointerCapture(e.pointerId);
      move(e);
    }
    function move(e) {
      if (stick.id !== e.pointerId) return;
      const r = rect();
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;
      const dx = e.clientX - cx;
      const dy = e.clientY - cy;
      const len = Math.hypot(dx, dy) || 1;
      const nx = dx / Math.max(len, 40);
      const ny = dy / Math.max(len, 40);
      stick.knob.style.transform =
        `translate(calc(-50% + ${nx * 42}px), calc(-50% + ${ny * 42}px))`;
      onMove(nx, ny);
    }
    function up(e) {
      if (stick.id !== e.pointerId) return;
      stick.id = null;
      stick.knob.style.transform = "translate(-50%,-50%)";
      onMove(0, 0);
    }

    stick.base.addEventListener("pointerdown", down, { passive: false });
    stick.base.addEventListener("pointermove", move, { passive: false });
    stick.base.addEventListener("pointerup", up, { passive: false });
    stick.base.addEventListener("pointercancel", up, { passive: false });
  }

  stickHandlers(joyL, (x, y) => {
    input.moveX = x;
    input.moveY = y;
    CORE.setMove(x, y);
  });

  stickHandlers(joyR, (x, y) => {
    if (x || y) {
      input.aimX = x;
      input.aimY = y;
      CORE.setAim(x, y);
      CORE.setShooting(true);
    } else {
      CORE.setShooting(false);
    }
  });

  // =========================================================
  // START GAME
  // =========================================================
  CORE.start("arcade", canvas.width, canvas.height);

  // =========================================================
  // LOOP
  // =========================================================
  function loop(t) {
    requestAnimationFrame(loop);
    CORE.updateFrame(t);
    render();
  }
  requestAnimationFrame(loop);

  // =========================================================
  // RENDER
  // =========================================================
  function render() {
    const S = CORE.state;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // arena
    ctx.save();
    ctx.translate(canvas.width / 2, canvas.height / 2);
    ctx.strokeStyle = "rgba(255,255,255,.12)";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(0, 0, Math.min(canvas.width, canvas.height) * 0.45, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();

    // bullets
    ctx.fillStyle = "#fff";
    for (const b of S.bullets) {
      ctx.beginPath();
      ctx.arc(b.x, b.y, 3, 0, Math.PI * 2);
      ctx.fill();
    }

    // zombies
    for (const z of S.zombies) {
      const A = ASSETS();
      if (A?.drawZombie) {
        A.drawZombie(ctx, z.x, z.y, { zombie: "basic" });
      } else {
        ctx.fillStyle = "#6f6";
        ctx.beginPath();
        ctx.arc(z.x, z.y, 16, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // player
    const A = ASSETS();
    if (A?.drawPlayer) {
      A.drawPlayer(ctx, S.player.x, S.player.y, input.aimX, input.aimY, {
        player: "male"
      });
    } else {
      ctx.fillStyle = "#4af";
      ctx.beginPath();
      ctx.arc(S.player.x, S.player.y, 14, 0, Math.PI * 2);
      ctx.fill();
    }

    // HUD
    hud.textContent =
      `❤️ ${Math.max(0, S.player.hp | 0)}  ☠️ ${S.kills}  💰 ${S.coins}  🌊 ${S.wave}`;
  }

  // =========================================================
  // TELEGRAM
  // =========================================================
  try {
    tg?.expand?.();
    tg?.BackButton?.show?.();
    tg?.BackButton?.onClick?.(() => overlay.remove());
  } catch {}

  console.log("[Z_GAME] ready");
})();
