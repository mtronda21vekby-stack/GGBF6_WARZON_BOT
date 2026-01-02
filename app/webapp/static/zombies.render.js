/* =========================================================
   BLACK CROWN OPS — ZOMBIES RENDERER + INPUT (FULLSCREEN)
   File: app/webapp/static/zombies.render.js
   ========================================================= */

(() => {
  "use strict";

  if (!window.BCO_ZOMBIES_CORE) {
    console.error("[Z_RENDER] core missing");
    return;
  }

  const CORE = window.BCO_ZOMBIES_CORE;
  const ASSETS = () => window.BCO_ZOMBIES_ASSETS || null;
  const tg = window.Telegram?.WebApp || null;

  // =========================================================
  // DOM / OVERLAY
  // =========================================================
  const mount = document.getElementById("zOverlayMount");
  if (!mount) {
    console.error("[Z_RENDER] zOverlayMount missing");
    return;
  }

  const overlay = document.createElement("div");
  overlay.id = "bco-z-overlay";
  overlay.style.cssText = `
    position:fixed; inset:0; z-index:999999;
    background:#05070c;
    touch-action:none;
  `;

  const canvas = document.createElement("canvas");
  canvas.style.cssText = `
    position:absolute; inset:0;
    width:100%; height:100%;
    touch-action:none;
  `;

  overlay.appendChild(canvas);
  mount.appendChild(overlay);

  const ctx = canvas.getContext("2d");
  let W = 0, H = 0, DPR = 1;

  function resize() {
    DPR = Math.min(3, window.devicePixelRatio || 1);
    W = window.innerWidth;
    H = window.innerHeight;
    canvas.width = Math.floor(W * DPR);
    canvas.height = Math.floor(H * DPR);
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  }
  window.addEventListener("resize", resize);
  resize();

  // =========================================================
  // INPUT (DUAL STICK)
  // =========================================================
  const input = {
    joy: { active:false, id:null, bx:0, by:0, x:0, y:0 },
    aim: { active:false, id:null },
    firing:false
  };

  function joyValue(x, y) {
    const dx = x - input.joy.bx;
    const dy = y - input.joy.by;
    const d = Math.hypot(dx, dy);
    if (!d) return {x:0,y:0};
    const r = Math.min(1, d / 60);
    return { x:(dx/d)*r, y:(dy/d)*r };
  }

  function aimFrom(px, py) {
    const st = CORE.state;
    const sx = W/2 + st.player.x * -1;
    const sy = H/2 + st.player.y * -1;
    CORE.setAim(px - sx, py - sy);
  }

  canvas.addEventListener("pointerdown", e => {
    e.preventDefault();
    if (e.clientX < W * 0.45) {
      input.joy.active = true;
      input.joy.id = e.pointerId;
      input.joy.bx = e.clientX;
      input.joy.by = e.clientY;
    } else {
      input.aim.active = true;
      input.aim.id = e.pointerId;
      input.firing = true;
      aimFrom(e.clientX, e.clientY);
      CORE.setShooting(true);
    }
  }, { passive:false });

  canvas.addEventListener("pointermove", e => {
    if (input.joy.active && e.pointerId === input.joy.id) {
      const v = joyValue(e.clientX, e.clientY);
      CORE.setMove(v.x, v.y);
    }
    if (input.aim.active && e.pointerId === input.aim.id) {
      aimFrom(e.clientX, e.clientY);
    }
  }, { passive:false });

  canvas.addEventListener("pointerup", e => {
    if (e.pointerId === input.joy.id) {
      input.joy.active = false;
      CORE.setMove(0,0);
    }
    if (e.pointerId === input.aim.id) {
      input.aim.active = false;
      input.firing = false;
      CORE.setShooting(false);
    }
  }, { passive:false });

  canvas.addEventListener("pointercancel", () => {
    input.joy.active = false;
    input.aim.active = false;
    input.firing = false;
    CORE.setMove(0,0);
    CORE.setShooting(false);
  });

  // =========================================================
  // RENDER
  // =========================================================
  function drawArena() {
    ctx.strokeStyle = "rgba(255,255,255,.08)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(W/2, H/2, 420, 0, Math.PI*2);
    ctx.stroke();
  }

  function render() {
    const st = CORE.state;
    ctx.clearRect(0,0,W,H);

    drawArena();

    ctx.save();
    ctx.translate(W/2 - st.player.x, H/2 - st.player.y);

    // bullets
    ctx.fillStyle = "#fff";
    for (const b of st.bullets) {
      ctx.beginPath();
      ctx.arc(b.x, b.y, 3, 0, Math.PI*2);
      ctx.fill();
    }

    // zombies
    for (const z of st.zombies) {
      const A = ASSETS();
      if (A?.drawZombie) A.drawZombie(ctx, z.x, z.y, {});
      else {
        ctx.fillStyle="#3f3";
        ctx.beginPath(); ctx.arc(z.x,z.y,18,0,Math.PI*2); ctx.fill();
      }
    }

    // player
    const A = ASSETS();
    if (A?.drawPlayer) {
      A.drawPlayer(ctx, st.player.x, st.player.y, st.input?.aimX||1, st.input?.aimY||0, {});
    } else {
      ctx.fillStyle="#4af";
      ctx.beginPath(); ctx.arc(st.player.x, st.player.y, 18, 0, Math.PI*2); ctx.fill();
    }

    ctx.restore();
  }

  // =========================================================
  // LOOP
  // =========================================================
  let raf = 0;
  function loop(t) {
    CORE.updateFrame(t);
    render();
    raf = requestAnimationFrame(loop);
  }

  // =========================================================
  // PUBLIC API
  // =========================================================
  window.BCO_ZOMBIES_RENDER = {
    start() {
      CORE.start();
      loop(performance.now());
      try { tg?.expand?.(); } catch {}
    },
    stop() {
      cancelAnimationFrame(raf);
      overlay.remove();
    }
  };

  console.log("[Z_RENDER] loaded");
})();
