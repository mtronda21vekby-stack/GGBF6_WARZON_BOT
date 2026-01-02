/* =========================================================
   BLACK CROWN OPS — ZOMBIES RENDER + INPUT (FULLSCREEN)
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

  // =========================================================
  // DOM
  // =========================================================
  const mount = document.getElementById("zOverlayMount");
  let overlay, canvas, ctx, W = 0, H = 0, dpr = 1;

  // controls
  let joy, joyInner, fire;

  // =========================================================
  // BUILD OVERLAY
  // =========================================================
  function build() {
    if (overlay) return;

    overlay = document.createElement("div");
    overlay.style.cssText = `
      position:fixed; inset:0; z-index:999999;
      background: radial-gradient(1200px 800px at 50% 40%, rgba(255,255,255,.06), rgba(0,0,0,.85));
      touch-action:none;
    `;

    canvas = document.createElement("canvas");
    canvas.style.cssText = `position:absolute; inset:0; width:100%; height:100%;`;
    overlay.appendChild(canvas);

    // joystick
    joy = document.createElement("div");
    joy.style.cssText = `
      position:absolute; left:16px; bottom:16px;
      width:120px; height:120px; border-radius:50%;
      background:rgba(255,255,255,.06);
      border:1px solid rgba(255,255,255,.12);
      touch-action:none;
    `;

    joyInner = document.createElement("div");
    joyInner.style.cssText = `
      position:absolute; left:50%; top:50%;
      width:56px; height:56px; border-radius:50%;
      transform:translate(-50%,-50%);
      background:rgba(255,255,255,.18);
    `;
    joy.appendChild(joyInner);

    // fire = AIM JOYSTICK
    fire = document.createElement("div");
    fire.style.cssText = `
      position:absolute; right:16px; bottom:16px;
      width:120px; height:120px; border-radius:50%;
      background:rgba(255,80,80,.10);
      border:1px solid rgba(255,120,120,.25);
      touch-action:none;
    `;

    overlay.appendChild(joy);
    overlay.appendChild(fire);
    mount.appendChild(overlay);

    ctx = canvas.getContext("2d", { alpha: true });
    resize();
    wireInput();
    loop(performance.now());
  }

  function resize() {
    const r = canvas.getBoundingClientRect();
    W = r.width; H = r.height;
    dpr = Math.min(3, window.devicePixelRatio || 1);
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  // =========================================================
  // INPUT (DUAL STICK)
  // =========================================================
  function wireInput() {
    const joyRect = () => joy.getBoundingClientRect();
    const fireRect = () => fire.getBoundingClientRect();

    function stick(rect, cb) {
      return (e) => {
        e.preventDefault();
        const r = rect();
        const cx = r.left + r.width / 2;
        const cy = r.top + r.height / 2;
        const dx = e.clientX - cx;
        const dy = e.clientY - cy;
        const l = Math.hypot(dx, dy) || 1;
        const nx = dx / Math.min(l, r.width / 2);
        const ny = dy / Math.min(l, r.height / 2);
        cb(nx, ny);
      };
    }

    joy.addEventListener("pointerdown", stick(joyRect, (x, y) => {
      CORE.setMove(x, y);
      joyInner.style.transform = `translate(calc(-50% + ${x * 30}px), calc(-50% + ${y * 30}px))`;
    }));

    joy.addEventListener("pointermove", stick(joyRect, (x, y) => {
      CORE.setMove(x, y);
      joyInner.style.transform = `translate(calc(-50% + ${x * 30}px), calc(-50% + ${y * 30}px))`;
    }));

    joy.addEventListener("pointerup", () => {
      CORE.setMove(0, 0);
      joyInner.style.transform = "translate(-50%,-50%)";
    });

    fire.addEventListener("pointerdown", stick(fireRect, (x, y) => {
      CORE.setAim(x, y);
      CORE.setShooting(true);
    }));

    fire.addEventListener("pointermove", stick(fireRect, (x, y) => {
      CORE.setAim(x, y);
    }));

    fire.addEventListener("pointerup", () => {
      CORE.setShooting(false);
    });

    window.addEventListener("resize", resize);
  }

  // =========================================================
  // RENDER
  // =========================================================
  function draw() {
    const s = CORE.state;
    ctx.clearRect(0, 0, W, H);

    ctx.save();
    ctx.translate(W / 2, H / 2);

    // bullets
    ctx.fillStyle = "#fff";
    for (const b of s.bullets) {
      ctx.beginPath();
      ctx.arc(b.x, b.y, 4, 0, Math.PI * 2);
      ctx.fill();
    }

    // zombies
    for (const z of s.zombies) {
      const A = ASSETS();
      if (A?.drawZombie) A.drawZombie(ctx, z.x, z.y);
      else {
        ctx.fillStyle = "#3f3";
        ctx.beginPath();
        ctx.arc(z.x, z.y, 18, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // player
    const p = s.player;
    const A = ASSETS();
    if (A?.drawPlayer) A.drawPlayer(ctx, p.x, p.y, s.input.aimX, s.input.aimY);
    else {
      ctx.fillStyle = "#fff";
      ctx.beginPath();
      ctx.arc(p.x, p.y, 18, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.restore();
  }

  // =========================================================
  // LOOP
  // =========================================================
  function loop(t) {
    requestAnimationFrame(loop);
    CORE.updateFrame(t);
    draw();
  }

  // =========================================================
  // AUTO START
  // =========================================================
  build();
  CORE.start();

  console.log("[Z_RENDER] loaded");
})();
