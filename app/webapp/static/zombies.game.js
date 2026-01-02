// app/webapp/static/zombies.game.js  [ULTRA LUX vNext | Dual-Stick + iOS Fix + Start Fix]
// IMPORTANT: UI не меняем — только логика, клики, запуск.
// - Dual-stick: LEFT = move, RIGHT = aim + hold-to-shoot
// - FIRE button: auto-hide when right stick exists (kept for backward compat)
// - Fix: game loop always starts, canvas resizes, safe-area, iOS dead taps, prevent zoom
// - Fullscreen: tries Telegram.WebApp fullscreen APIs if available (no hard dependency)
// - CRITICAL FIX: do NOT kill global scrolling; lock scrolling ONLY while game is running.

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
  // Helpers
  // -------------------------
  const CORE = () => window.BCO_ZOMBIES_CORE || null;

  function isGameRunning() {
    const c = CORE();
    return !!(c && c.running);
  }

  function markScrollZones() {
    // We do NOT redesign UI. We only mark known modal bodies as scroll-allowed
    // so touchmove handler can pass them through on iOS.
    try {
      const nodes = Array.from(document.querySelectorAll(
        ".modal, .modal-body, .sheet, .sheet-body, .dialog, .dialog-body, [data-allow-scroll], .allow-scroll"
      ));
      for (const n of nodes) {
        if (!n || !n.classList) continue;
        if (!n.classList.contains("allow-scroll")) n.classList.add("allow-scroll");
        // allow vertical scrolling inside these containers
        try { n.style.touchAction = n.style.touchAction || "pan-y"; } catch {}
        try { n.style.webkitOverflowScrolling = "touch"; } catch {}
      }
    } catch {}
  }

  function isInsideScrollZone(ev) {
    try {
      const path = (ev && ev.composedPath && ev.composedPath()) || [];
      for (const n of path) {
        if (!n) continue;
        if (n.classList && (n.classList.contains("allow-scroll") || n.classList.contains("modal") || n.classList.contains("modal-body"))) {
          return true;
        }
        // any element with scrollable overflow should be allowed
        if (n instanceof HTMLElement) {
          const st = window.getComputedStyle(n);
          const oy = st && st.overflowY;
          if ((oy === "auto" || oy === "scroll") && (n.scrollHeight > n.clientHeight + 2)) return true;
        }
      }
    } catch {}
    return false;
  }

  // -------------------------
  // iOS / WebView touch hardening (NO dead taps)
  // CRITICAL: do NOT disable global scrolling when not playing.
  // -------------------------
  function applyIosHardening() {
    try {
      // Prevent long-press selection/callout (safe globally)
      document.body.style.userSelect = "none";
      document.body.style.webkitUserSelect = "none";
      document.body.style.webkitTouchCallout = "none";

      // IMPORTANT: DO NOT set touchAction:none on body/html globally.
      // Keep normal scrolling in app screens.
      try { document.body.style.touchAction = "manipulation"; } catch {}
      try { document.documentElement.style.touchAction = "manipulation"; } catch {}

      // Canvas + sticks must be crisp for pointer events
      if (canvas) {
        canvas.style.touchAction = "none";
        canvas.style.pointerEvents = "auto";
      }
      for (const el of [stickL, stickR, btnFire, btnStart]) {
        if (!el) continue;
        el.style.touchAction = "none";
        el.style.pointerEvents = "auto";
      }

      // Hard prevent pinch zoom gesture (global)
      const prevent = (e) => { try { e.preventDefault(); } catch {} };
      document.addEventListener("gesturestart", prevent, { passive: false });
      document.addEventListener("gesturechange", prevent, { passive: false });
      document.addEventListener("gestureend", prevent, { passive: false });

      // Only prevent scroll while GAME is actually running AND touch is outside scroll zones.
      document.addEventListener("touchmove", (e) => {
        if (!isGameRunning()) return;             // <-- KEY FIX
        if (isInsideScrollZone(e)) return;        // allow modals / scroll areas
        try { e.preventDefault(); } catch {}
      }, { passive: false });

      // Also guard wheel scrolling when in game (desktop)
      document.addEventListener("wheel", (e) => {
        if (!isGameRunning()) return;
        if (isInsideScrollZone(e)) return;
        try { e.preventDefault(); } catch {}
      }, { passive: false });

      markScrollZones();

      log("iOS hardening applied (safe)");
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

      // evolving APIs
      try { TG.requestFullscreen && TG.requestFullscreen(); } catch {}
      try { TG.setHeaderColor && TG.setHeaderColor("#000000"); } catch {}
      try { TG.setBackgroundColor && TG.setBackgroundColor("#000000"); } catch {}

      log("Telegram takeover requested");
    } catch (e) {
      warn("Telegram takeover error", e);
    }
  }

  // -------------------------
  // Canvas sizing (devicePixelRatio correct)
  // -------------------------
  function resizeCanvas() {
    if (!canvas) return null;

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
      const c = CORE();
      if (c && c.resize) c.resize(Math.floor(r2.width), Math.floor(r2.height));
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
      el.setPointerCapture && el.setPointerCapture(pid);
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

      const c = CORE();
      if (!c) return;

      if (kind === "move") {
        c.setMove && c.setMove(clx, cly);
      } else {
        c.setAim && c.setAim(clx, cly);
      }
    }

    function onUp(e) {
      if (!active) return;
      if (pid !== null && e.pointerId !== pid) return;

      active = false;
      pid = null;
      try { el.releasePointerCapture && el.releasePointerCapture(e.pointerId); } catch {}
      resetKnob();

      const c = CORE();
      if (c && kind === "move") c.setMove && c.setMove(0, 0);
      if (c && kind === "aim") c.setAim && c.setAim(0, 0);
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
    // If dual-stick exists -> FIRE is redundant. Hide it.
    if (stickR && btnFire) {
      btnFire.style.display = "none";
      btnFire.style.pointerEvents = "none";
      log("FIRE hidden (dual-stick detected)");
      return;
    }

    if (!btnFire) return;

    const down = (e) => {
      try { e.preventDefault(); } catch {}
      const c = CORE();
      if (c && c.setShooting) c.setShooting(true);
    };
    const up = (e) => {
      try { e.preventDefault(); } catch {}
      const c = CORE();
      if (c && c.setShooting) c.setShooting(false);
    };

    btnFire.addEventListener("pointerdown", down, { passive: false });
    btnFire.addEventListener("pointerup", up, { passive: false });
    btnFire.addEventListener("pointercancel", up, { passive: false });
    btnFire.addEventListener("pointerleave", up, { passive: false });
  }

  // -------------------------
  // Auto-shoot on RIGHT stick hold (Dual-stick)
  // -------------------------
  function setupDualStickShooting(aimStick) {
    if (!aimStick) return;

    function tick() {
      const c = CORE();
      if (c && c.setShooting) {
        const should = !!aimStick.active && (Math.hypot(aimStick.dx, aimStick.dy) > 0.08);
        c.setShooting(should);
      }
      requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  // -------------------------
  // Render hook (do not break your renderer)
  // -------------------------
  function drawFrame() {
    const c = CORE();
    if (!c || !c.getFrameData) return;

    const snap = c.getFrameData();

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
    if (_raf) return true;

    const c = CORE();
    if (!c || !c.updateFrame || !c.getFrameData) {
      health("Core not loaded");
      warn("BCO_ZOMBIES_CORE missing or incomplete");
      return false;
    }

    function frame(tms) {
      try {
        resizeCanvas();
        c.updateFrame(tms);
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
    return true;
  }

  function stopLoop() {
    if (_raf) {
      try { cancelAnimationFrame(_raf); } catch {}
      _raf = 0;
    }
    return true;
  }

  // -------------------------
  // Start game (calls CORE.start safely)
  // -------------------------
  function startGame(forceTakeover = false, modeOverride = null, optsOverride = null) {
    const c = CORE();
    if (!c || !c.start) {
      health("Core not ready");
      return false;
    }

    if (forceTakeover) requestTakeover();

    const r = resizeCanvas() || { cssW: window.innerWidth, cssH: window.innerHeight };

    const mode = (modeOverride != null)
      ? modeOverride
      : (window.BCO_ZOMBIES_MODE || window.__Z_MODE__ || c.meta?.mode || "arcade");

    const map = (optsOverride && optsOverride.map) ? optsOverride.map : (window.BCO_ZOMBIES_MAP || window.__Z_MAP__ || c.meta?.map || "Ashes");
    const character = (optsOverride && optsOverride.character) ? optsOverride.character : (window.BCO_ZOMBIES_CHARACTER || c.meta?.character || "male");
    const skin = (optsOverride && optsOverride.skin) ? optsOverride.skin : (window.BCO_ZOMBIES_SKIN || c.meta?.skin || "default");
    const weaponKey = (optsOverride && optsOverride.weaponKey) ? optsOverride.weaponKey : (c.meta?.weaponKey || "SMG");

    const opts = { map, character, skin, weaponKey };

    try {
      c.start(String(mode), Math.floor(r.cssW), Math.floor(r.cssH), opts);
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
  // API expected by zombies.init.js (contract compatibility)
  // -------------------------
  let _mode = "arcade";
  let _map = null;
  let _character = null;
  let _skin = null;
  let _weaponKey = null;

  function open() {
    // If you have overlay container, this is where you would show it.
    // We keep it safe: no UI changes. Return true for compatibility.
    markScrollZones();
    return true;
  }

  function close() {
    // No-op (no UI change). Compatibility.
    return true;
  }

  function start(mode = "arcade", opts = {}) {
    _mode = String(mode || "arcade");
    _map = opts.map ?? _map;
    _character = opts.character ?? _character;
    _skin = opts.skin ?? _skin;
    _weaponKey = opts.weaponKey ?? _weaponKey;

    return startGame(true, _mode, {
      map: _map,
      character: _character,
      skin: _skin,
      weaponKey: _weaponKey
    });
  }

  function stop(reason = "manual") {
    const c = CORE();
    if (c && c.stop) {
      try { c.stop(reason); } catch {}
    } else if (c) {
      try { c.running = false; } catch {}
    }
    stopLoop();
    health("stopped");
    return true;
  }

  function setMode(mode) { _mode = String(mode || "arcade"); return _mode; }
  function setMap(name) { _map = String(name || "Ashes"); return _map; }
  function setCharacter(character, skin) {
    _character = String(character || "male");
    if (skin != null) _skin = String(skin);
    return { character: _character, skin: _skin ?? "default" };
  }
  function setWeapon(key) {
    _weaponKey = String(key || "SMG");
    const c = CORE();
    if (c && c.setWeapon) try { c.setWeapon(_weaponKey); } catch {}
    return _weaponKey;
  }

  function buyPerk(id) {
    const c = CORE();
    if (c && c.buyPerk) return !!c.buyPerk(id);
    return false;
  }

  function reload() {
    const c = CORE();
    if (c && c.reload) return !!c.reload();
    return false;
  }

  function usePlate() {
    const c = CORE();
    if (c && c.usePlate) return !!c.usePlate();
    return false;
  }

  function sendResult(reason = "manual") {
    // If you already have bot sendData in app.js, you can hook it there.
    // Keep compatibility only:
    log("sendResult (compat)", reason);
    return true;
  }

  function getInput() {
    const c = CORE();
    return c ? { ...c.input } : null;
  }

  function setInput(obj) {
    const c = CORE();
    if (!c || !obj) return false;
    try {
      if ("moveX" in obj || "moveY" in obj) c.setMove(obj.moveX ?? c.input.moveX, obj.moveY ?? c.input.moveY);
      if ("aimX" in obj || "aimY" in obj) c.setAim(obj.aimX ?? c.input.aimX, obj.aimY ?? c.input.aimY);
      if ("shooting" in obj) c.setShooting(!!obj.shooting);
      return true;
    } catch { return false; }
  }

  // -------------------------
  // Init
  // -------------------------
  function init() {
    applyIosHardening();
    markScrollZones();

    const moveStick = makeStick(stickL, "move");
    const aimStick  = makeStick(stickR, "aim");

    if (aimStick) setupDualStickShooting(aimStick);
    setupFireBehavior();

    if (btnStart) {
      btnStart.addEventListener("pointerdown", (e) => {
        try { e.preventDefault(); } catch {}
        // contract: start game in current selected mode/options
        start(_mode || "arcade", {
          map: _map,
          character: _character,
          skin: _skin,
          weaponKey: _weaponKey
        });
      }, { passive: false });
    }

    if (canvas) {
      canvas.addEventListener("pointerdown", (e) => {
        const c = CORE();
        if (!c || c.running) return;
        try { e.preventDefault(); } catch {}
        start(_mode || "arcade", {
          map: _map,
          character: _character,
          skin: _skin,
          weaponKey: _weaponKey
        });
      }, { passive: false });
    }

    window.addEventListener("resize", () => {
      resizeCanvas();
      markScrollZones();
    });

    if (TG) {
      try { TG.ready && TG.ready(); } catch {}
      try { TG.expand && TG.expand(); } catch {}
    }

    // If core already running -> ensure loop
    try {
      const c = CORE();
      if (c && c.running) startLoop();
    } catch {}

    health("ready");
    log("init ok", { hasCanvas: !!canvas, hasL: !!stickL, hasR: !!stickR, hasFire: !!btnFire, hasStart: !!btnStart });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }

  // Expose full API expected by init.js
  window.BCO_ZOMBIES_GAME = {
    // overlay (compat)
    open,
    close,

    // run control (contract)
    start,
    stop,

    // settings (contract)
    setMode,
    setMap,
    setCharacter,
    setWeapon,

    // actions (contract)
    buyPerk,
    reload,
    usePlate,
    sendResult,

    // loop/tools
    startLoop,
    stopLoop,
    resizeCanvas,

    // io
    getInput,
    setInput,

    // raw (legacy)
    startGame
  };
})();
