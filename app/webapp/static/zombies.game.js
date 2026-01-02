// app/webapp/static/zombies.game.js  [ULTRA LUX vNext | Dual-Stick + iOS Fix + Start Fix]
// IMPORTANT: UI не меняем — только логика, клики, запуск.
// - Dual-stick: LEFT = move, RIGHT = aim + hold-to-shoot
// - FIRE button: auto-hide when right stick exists (kept for backward compat)
// - Fix: game loop always starts, canvas resizes, safe-area, iOS dead taps, prevent zoom
// - Fullscreen: tries Telegram.WebApp fullscreen APIs if available (no hard dependency)

(() => {
  "use strict";

  const log = (...a) => { try { console.log("[Z_GAME]", ...a); } catch {} };
  const warn = (...a) => { try { console.warn("[Z_GAME]", ...a); } catch {} };

  const TG = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;

  // -------------------------
  // Safe DOM helpers (robust selectors)
  // -------------------------
  const $ = (sel) => document.querySelector(sel);

  function pickEl(selectors) {
    for (const s of selectors) {
      const el = $(s);
      if (el) return el;
    }
    return null;
  }

  // Canvas (main game surface)
  const canvas = pickEl([
    "#zombiesCanvas",
    "#zCanvas",
    "canvas#zombies",
    "canvas#game",
    "canvas"
  ]);

  // Left/right sticks containers (your UI already has 2 circles)
  const stickL = pickEl([
    "#joyL", "#stickLeft", ".joy.left", ".joystick.left", ".joy-left", ".stick-left",
    "[data-joy='left']"
  ]);

  const stickR = pickEl([
    "#joyR", "#stickRight", ".joy.right", ".joystick.right", ".joy-right", ".stick-right",
    "[data-joy='right']"
  ]);

  // FIRE button (we will hide if right stick exists)
  const btnFire = pickEl([
    "#btnFire", "#fire", ".btn-fire", ".fire",
    "button[data-action='fire']",
    ".z-fire"
  ]);

  // Start Fullscreen button (if exists)
  const btnStart = pickEl([
    "#btnStartFullscreen",
    "button[data-action='start_fullscreen']",
    ".btn-start-fullscreen",
    "#startFullscreen",
    ".start-fullscreen"
  ]);

  // Optional: debug/health label
  const jsHealth = pickEl(["#jsHealth", ".jsHealth", "[data-js-health]"]);

  function health(msg) {
    if (!jsHealth) return;
    try { jsHealth.textContent = String(msg || ""); } catch {}
  }

  // -------------------------
  // iOS / WebView touch hardening (NO dead taps)
  // -------------------------
  function applyIosHardening() {
    try {
      // prevent bounce/scroll while playing
      document.documentElement.style.overscrollBehavior = "none";
      document.body.style.overscrollBehavior = "none";

      // prevent long-press menu / selection
      document.body.style.userSelect = "none";
      document.body.style.webkitUserSelect = "none";
      document.body.style.webkitTouchCallout = "none";

      // prevent double-tap zoom + unify pointer behavior
      document.body.style.touchAction = "none";
      document.documentElement.style.touchAction = "none";

      // if canvas exists, ensure it receives pointer events
      if (canvas) {
        canvas.style.touchAction = "none";
        canvas.style.pointerEvents = "auto";
        // block iOS context menu / long press
        canvas.addEventListener("contextmenu", (e) => { try { e.preventDefault(); } catch {} }, { passive: false });
      }

      // sticks and buttons must be clickable
      for (const el of [stickL, stickR, btnFire, btnStart]) {
        if (!el) continue;
        el.style.touchAction = "none";
        el.style.pointerEvents = "auto";
        el.addEventListener("contextmenu", (e) => { try { e.preventDefault(); } catch {} }, { passive: false });
      }

      // hard prevent pinch zoom gesture
      const prevent = (e) => { try { e.preventDefault(); } catch {} };
      document.addEventListener("gesturestart", prevent, { passive: false });
      document.addEventListener("gesturechange", prevent, { passive: false });
      document.addEventListener("gestureend", prevent, { passive: false });

      // prevent scroll on touchmove during play (allow inside modals / scrollable sheets)
      document.addEventListener("touchmove", (e) => {
        const path = (e.composedPath && e.composedPath()) || [];
        for (const n of path) {
          if (!n || !n.classList) continue;
          // allow scroll in anything modal-like or explicitly scrollable
          if (
            n.classList.contains("modal") ||
            n.classList.contains("modal-body") ||
            n.classList.contains("allow-scroll") ||
            n.classList.contains("sheet") ||
            n.classList.contains("sheet-body") ||
            n.classList.contains("scroll") ||
            n.classList.contains("scroll-y") ||
            n.hasAttribute("data-allow-scroll")
          ) {
            return;
          }
        }
        e.preventDefault();
      }, { passive: false });

      log("iOS hardening applied");
    } catch (e) {
      warn("iOS hardening failed", e);
    }
  }

  // -------------------------
  // Telegram fullscreen take-over (best effort)
  // -------------------------
  function requestTakeover() {
    try {
      if (!TG) return;

      try { TG.expand(); } catch {}
      try { TG.MainButton && TG.MainButton.hide && TG.MainButton.hide(); } catch {}
      try { TG.BackButton && TG.BackButton.hide && TG.BackButton.hide(); } catch {}

      // evolving API, safe try-calls
      try { TG.requestFullscreen && TG.requestFullscreen(); } catch {}
      try { TG.setHeaderColor && TG.setHeaderColor("#000000"); } catch {}
      try { TG.setBackgroundColor && TG.setBackgroundColor("#000000"); } catch {}

      log("Telegram takeover requested");
    } catch (e) {
      warn("Telegram takeover error", e);
    }
  }

  // While game is running, Telegram buttons can reappear (orientation etc). Hard-hide periodically.
  let _tgHideTimer = 0;
  function startTelegramHideLoop() {
    if (!TG || _tgHideTimer) return;
    _tgHideTimer = window.setInterval(() => {
      const CORE = window.BCO_ZOMBIES_CORE;
      if (!CORE || !CORE.running) return;
      try { TG.MainButton && TG.MainButton.hide && TG.MainButton.hide(); } catch {}
      try { TG.BackButton && TG.BackButton.hide && TG.BackButton.hide(); } catch {}
      try { TG.expand && TG.expand(); } catch {}
    }, 350);
  }

  // -------------------------
  // Canvas sizing (devicePixelRatio correct)
  // -------------------------
  function resizeCanvas() {
    if (!canvas) return;

    const dpr = Math.max(1, Math.min(3, (window.devicePixelRatio || 1)));
    const rect = canvas.getBoundingClientRect();

    // If canvas has no explicit size yet, stretch to parent
    if (!rect.width || !rect.height) {
      const p = canvas.parentElement || document.body;
      const pr = p.getBoundingClientRect();
      canvas.style.width = (pr.width || window.innerWidth) + "px";
      canvas.style.height = (pr.height || window.innerHeight) + "px";
    }

    const r2 = canvas.getBoundingClientRect();
    const w = Math.max(1, Math.floor(r2.width * dpr));
    const h = Math.max(1, Math.floor(r2.height * dpr));

    if (canvas.width !== w) canvas.width = w;
    if (canvas.height !== h) canvas.height = h;

    // Notify CORE about logical size in CSS pixels (not DPR)
    try {
      const CORE = window.BCO_ZOMBIES_CORE;
      if (CORE && CORE.resize) CORE.resize(Math.floor(r2.width), Math.floor(r2.height));
    } catch {}

    return { cssW: r2.width, cssH: r2.height, pxW: w, pxH: h, dpr };
  }

  // -------------------------
  // Dual-stick virtual joystick (pointer-driven, multi-touch safe)
  // -------------------------
  function makeStick(el, kind /* "move" | "aim" */) {
    if (!el) return null;

    const knob = el.querySelector(".knob") || el.querySelector(".inner") || el.firstElementChild || null;

    let active = false;
    let pid = null;
    let cx = 0, cy = 0;
    let dx = 0, dy = 0;
    let radius = 1;

    function recalc() {
      const r = el.getBoundingClientRect();
      cx = r.left + r.width / 2;
      cy = r.top + r.height / 2;
      radius = Math.max(24, Math.min(r.width, r.height) * 0.38);
    }

    function setKnob(nx, ny) {
      dx = nx; dy = ny;
      if (!knob) return;
      const kx = nx * radius;
      const ky = ny * radius;
      knob.style.transform = `translate(${kx}px, ${ky}px)`;
    }

    function resetKnob() {
      dx = 0; dy = 0;
      if (knob) knob.style.transform = "translate(0px, 0px)";
    }

    function onDown(e) {
      try { e.preventDefault(); } catch {}
      recalc();
      active = true;
      pid = e.pointerId;
      try { el.setPointerCapture && el.setPointerCapture(pid); } catch {}
      onMove(e);
    }

    function onMove(e) {
      if (!active) return;
      if (pid !== null && e.pointerId !== pid) return;

      const vx = (e.clientX - cx);
      const vy = (e.clientY - cy);
      const L = Math.hypot(vx, vy) || 0;

      const nx = L > 0 ? (vx / Math.max(L, radius)) : 0;
      const ny = L > 0 ? (vy / Math.max(L, radius)) : 0;

      const clx = Math.max(-1, Math.min(1, nx));
      const cly = Math.max(-1, Math.min(1, ny));
      setKnob(clx, cly);

      const CORE = window.BCO_ZOMBIES_CORE;
      if (!CORE) return;

      if (kind === "move") {
        CORE.setMove && CORE.setMove(clx, cly);
      } else {
        CORE.setAim && CORE.setAim(clx, cly);
        // ULTRA: for aim stick, shooting state should follow pointer immediately (no rAF lag)
        CORE.setShooting && CORE.setShooting(Math.hypot(clx, cly) > 0.08);
      }
    }

    function onUp(e) {
      if (!active) return;
      if (pid !== null && e.pointerId !== pid) return;

      active = false;
      pid = null;
      try { el.releasePointerCapture && el.releasePointerCapture(e.pointerId); } catch {}
      resetKnob();

      const CORE = window.BCO_ZOMBIES_CORE;
      if (CORE && kind === "move") CORE.setMove && CORE.setMove(0, 0);
      if (CORE && kind === "aim") {
        // setAim(0,0) is fine even if core keeps last aim; we MUST stop shooting now
        CORE.setAim && CORE.setAim(0, 0);
        CORE.setShooting && CORE.setShooting(false);
      }
    }

    el.addEventListener("pointerdown", onDown, { passive: false });
    window.addEventListener("pointermove", onMove, { passive: false });
    window.addEventListener("pointerup", onUp, { passive: false });
    window.addEventListener("pointercancel", onUp, { passive: false });

    setTimeout(recalc, 0);
    window.addEventListener("resize", recalc);

    return {
      get active() { return active; },
      get dx() { return dx; },
      get dy() { return dy; },
      recalc
    };
  }

  // -------------------------
  // FIRE behavior (legacy)
  // -------------------------
  function setupFireBehavior() {
    if (stickR && btnFire) {
      btnFire.style.display = "none";
      btnFire.style.pointerEvents = "none";
      log("FIRE hidden (dual-stick detected)");
      return;
    }

    if (!btnFire) return;

    const CORE = () => window.BCO_ZOMBIES_CORE;

    const down = (e) => {
      try { e.preventDefault(); } catch {}
      const C = CORE();
      if (C && C.setShooting) C.setShooting(true);
    };
    const up = (e) => {
      try { e.preventDefault(); } catch {}
      const C = CORE();
      if (C && C.setShooting) C.setShooting(false);
    };

    btnFire.addEventListener("pointerdown", down, { passive: false });
    btnFire.addEventListener("pointerup", up, { passive: false });
    btnFire.addEventListener("pointercancel", up, { passive: false });
    btnFire.addEventListener("pointerleave", up, { passive: false });
  }

  // -------------------------
  // Render hook (do not break your renderer)
  // -------------------------
  function drawFrame() {
    const CORE = window.BCO_ZOMBIES_CORE;
    if (!CORE || !CORE.getFrameData) return;

    const snap = CORE.getFrameData();

    const R = window.BCO_ZOMBIES_RENDER || window.BCO_ZOMBIES_RENDERER || window.BCO_ZOMBIES_DRAW;
    if (R && typeof R.draw === "function") {
      try { R.draw(canvas, snap); return; } catch (e) { /* fallback below */ }
    }

    const ctx = canvas ? canvas.getContext("2d") : null;
    if (!ctx) return;

    const dpr = Math.max(1, Math.min(3, (window.devicePixelRatio || 1)));
    const w = canvas.width, h = canvas.height;

    ctx.clearRect(0, 0, w, h);

    const camX = snap.camera?.x || 0;
    const camY = snap.camera?.y || 0;

    const toX = (x) => (w / 2) + (x - camX) * dpr;
    const toY = (y) => (h / 2) + (y - camY) * dpr;

    ctx.beginPath();
    ctx.arc(toX(snap.player.x), toY(snap.player.y), 14 * dpr, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(220,220,255,0.95)";
    ctx.fill();

    for (const z of (snap.zombies || [])) {
      ctx.beginPath();
      ctx.arc(toX(z.x), toY(z.y), (z.r || 16) * dpr, 0, Math.PI * 2);
      ctx.fillStyle = z.elite ? "rgba(255,210,120,0.95)" : "rgba(140,255,140,0.85)";
      ctx.fill();
    }

    for (const b of (snap.bullets || [])) {
      ctx.beginPath();
      ctx.arc(toX(b.x), toY(b.y), 3 * dpr, 0, Math.PI * 2);
      ctx.fillStyle = b.crit ? "rgba(255,210,120,0.95)" : "rgba(240,240,255,0.9)";
      ctx.fill();
    }
  }

  // -------------------------
  // Main loop (guaranteed start)
  // -------------------------
  let _raf = 0;
  function startLoop() {
    if (_raf) return;
    const CORE = window.BCO_ZOMBIES_CORE;

    if (!CORE || !CORE.updateFrame || !CORE.getFrameData) {
      health("Core not loaded");
      warn("BCO_ZOMBIES_CORE missing or incomplete");
      return;
    }

    startTelegramHideLoop();

    function frame(tms) {
      try {
        resizeCanvas();
        CORE.updateFrame(tms);
        drawFrame();
      } catch (e) {
        warn("frame error", e);
        health("frame error");
      }
      _raf = requestAnimationFrame(frame);
    }

    _raf = requestAnimationFrame(frame);
    health("loop ok");
    log("loop started");
  }

  // -------------------------
  // Start game (calls CORE.start safely)
  // -------------------------
  function startGame(forceTakeover = false) {
    const CORE = window.BCO_ZOMBIES_CORE;
    if (!CORE || !CORE.start) {
      health("Core not ready");
      return false;
    }

    if (forceTakeover) requestTakeover();

    const r = resizeCanvas() || { cssW: window.innerWidth, cssH: window.innerHeight };

    const mode = (window.BCO_ZOMBIES_MODE || window.__Z_MODE__ || CORE.meta?.mode || "arcade");
    const map = (window.BCO_ZOMBIES_MAP || window.__Z_MAP__ || CORE.meta?.map || "Ashes");
    const character = (window.BCO_ZOMBIES_CHARACTER || CORE.meta?.character || "male");
    const skin = (window.BCO_ZOMBIES_SKIN || CORE.meta?.skin || "default");

    const modeStr = String(mode);
    const opts = { map, character, skin };

    try {
      CORE.start(modeStr, Math.floor(r.cssW), Math.floor(r.cssH), opts);
      startLoop();
      health("running");
      return true;
    } catch (e) {
      warn("CORE.start failed", e);
      health("start failed");
      return false;
    }
  }

  // -------------------------
  // Init
  // -------------------------
  function init() {
    applyIosHardening();

    const moveStick = makeStick(stickL, "move");
    const aimStick  = makeStick(stickR, "aim");

    // FIRE legacy behavior (and auto-hide on dual-stick)
    setupFireBehavior();

    if (btnStart) {
      btnStart.addEventListener("pointerdown", (e) => {
        try { e.preventDefault(); } catch {}
        startGame(true);
      }, { passive: false });
    }

    // Tap canvas to start if not running
    if (canvas) {
      canvas.addEventListener("pointerdown", (e) => {
        const CORE = window.BCO_ZOMBIES_CORE;
        if (!CORE || CORE.running) return;
        try { e.preventDefault(); } catch {}
        startGame(false);
      }, { passive: false });
    }

    window.addEventListener("resize", () => { resizeCanvas(); });

    if (TG) {
      try { TG.ready && TG.ready(); } catch {}
      try { TG.expand && TG.expand(); } catch {}
      // don’t force takeover here (only on start), but keep loop available
      startTelegramHideLoop();
    }

    try {
      const CORE = window.BCO_ZOMBIES_CORE;
      if (CORE && CORE.running) startLoop();
    } catch {}

    health("ready");
    log("init ok", { hasCanvas: !!canvas, hasL: !!stickL, hasR: !!stickR, hasFire: !!btnFire, hasStart: !!btnStart, hasMove: !!moveStick, hasAim: !!aimStick });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }

  window.BCO_ZOMBIES_GAME = {
    startGame,
    startLoop,
    resizeCanvas
  };
})();
