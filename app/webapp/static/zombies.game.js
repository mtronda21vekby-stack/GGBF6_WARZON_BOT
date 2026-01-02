// app/webapp/static/zombies.game.js  [ULTRA LUX vNext | Dual-Stick + iOS Fix + Start Fix]
// IMPORTANT: UI не меняем — только логика, клики, запуск.
// FIXES:
// - Scrolling in menu/tab screens works (no global kill).
// - Scroll inside modals works.
// - Game always starts (canvas guaranteed + start buttons wired).
// - Dual-stick: LEFT=move, RIGHT=aim + hold-to-shoot.
// - FIRE legacy button: auto-hide when right stick exists.
// - iOS dead taps: pointer events + proper capture.
// - Prevent pinch/zoom ONLY while in game takeover.
// - Fullscreen takeover best-effort via Telegram WebApp API.

(() => {
  "use strict";

  const log = (...a) => { try { console.log("[Z_GAME]", ...a); } catch {} };
  const warn = (...a) => { try { console.warn("[Z_GAME]", ...a); } catch {} };

  const TG = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;

  // -------------------------
  // Safe DOM helpers
  // -------------------------
  const $ = (sel) => document.querySelector(sel);

  function pickEl(selectors) {
    for (const s of selectors) {
      const el = $(s);
      if (el) return el;
    }
    return null;
  }

  // -------------------------
  // Mounts / Overlay
  // -------------------------
  const overlayMount = pickEl(["#zOverlayMount", "[data-z-overlay-mount]"]);

  function ensureCanvas() {
    // Try existing canvas
    let c = pickEl([
      "#zombiesCanvas",
      "#zCanvas",
      "canvas#zombies",
      "canvas#game",
      "canvas"
    ]);

    // If none — create inside #zOverlayMount (this is REQUIRED for your current index.html)
    if (!c) {
      if (!overlayMount) {
        warn("No canvas and no #zOverlayMount. Cannot create game surface.");
        return null;
      }
      c = document.createElement("canvas");
      c.id = "zombiesCanvas";

      // Inline styles ONLY for guaranteed fullscreen surface (logic-level safety)
      c.style.position = "fixed";
      c.style.left = "0";
      c.style.top = "0";
      c.style.width = "100vw";
      c.style.height = "100vh";
      c.style.zIndex = "9999";
      c.style.display = "block";
      c.style.pointerEvents = "auto";
      c.style.touchAction = "none";
      c.style.background = "transparent";

      overlayMount.appendChild(c);
      log("Canvas created in #zOverlayMount");
    }

    return c;
  }

  // Canvas ref (lazy-safe)
  let canvas = null;

  // Left/right joystick containers (optional; may be provided by other modules/HTML)
  const stickL = pickEl([
    "#joyL", "#stickLeft", ".joy.left", ".joystick.left", ".joy-left", ".stick-left",
    "[data-joy='left']"
  ]);

  const stickR = pickEl([
    "#joyR", "#stickRight", ".joy.right", ".joystick.right", ".joy-right", ".stick-right",
    "[data-joy='right']"
  ]);

  // Legacy FIRE button (optional)
  const btnFire = pickEl([
    "#btnFire", "#fire", ".btn-fire", ".fire",
    "button[data-action='fire']",
    ".z-fire"
  ]);

  // Start fullscreen (old id optional)
  const btnStart = pickEl([
    "#btnStartFullscreen",
    "button[data-action='start_fullscreen']",
    ".btn-start-fullscreen",
    "#startFullscreen",
    ".start-fullscreen"
  ]);

  // YOUR REAL buttons from index.html (must work)
  const btnZEnterGame = pickEl(["#btnZEnterGame"]);
  const btnPlayZombies = pickEl(["#btnPlayZombies"]);
  const btnZQuickPlay = pickEl(["#btnZQuickPlay"]);

  const jsHealth = pickEl(["#jsHealth", ".jsHealth", "[data-js-health]"]);
  function health(msg) { try { if (jsHealth) jsHealth.textContent = String(msg || ""); } catch {} }

  // -------------------------
  // STATE
  // -------------------------
  const STATE = {
    inGame: false,
    mode: "arcade",
    map: "Ashes",
    character: "male",
    skin: "default",
    weaponKey: "SMG",
    lastSnapshot: null,
    snapshotSubs: new Set(),
    _raf: 0,
    _aimStick: null
  };

  function CORE() { return window.BCO_ZOMBIES_CORE || null; }

  // -------------------------
  // iOS / WebView hardening
  // IMPORTANT: DO NOT KILL SCROLL globally.
  // We apply strict "no scroll / no pinch" ONLY during game takeover.
  // -------------------------
  function setHardening(on) {
    try {
      const root = document.documentElement;
      const body = document.body;
      if (!root || !body) return;

      if (on) {
        body.classList.add("bco-game-active");

        body.style.userSelect = "none";
        body.style.webkitUserSelect = "none";
        body.style.webkitTouchCallout = "none";

        root.style.overscrollBehavior = "none";
        body.style.overscrollBehavior = "none";

        root.style.touchAction = "none";
        body.style.touchAction = "none";

        if (canvas) { canvas.style.touchAction = "none"; canvas.style.pointerEvents = "auto"; }
        for (const el of [stickL, stickR, btnFire, btnStart, btnZEnterGame, btnPlayZombies, btnZQuickPlay]) {
          if (!el) continue;
          el.style.touchAction = "none";
          el.style.pointerEvents = "auto";
        }

        // If you have TG helper from index.html
        try { window.BCO_TG && window.BCO_TG.hideChrome && window.BCO_TG.hideChrome(); } catch {}
      } else {
        body.classList.remove("bco-game-active");

        body.style.userSelect = "";
        body.style.webkitUserSelect = "";
        body.style.webkitTouchCallout = "";

        root.style.overscrollBehavior = "";
        body.style.overscrollBehavior = "";

        root.style.touchAction = "";
        body.style.touchAction = "";

        if (canvas) { canvas.style.touchAction = ""; canvas.style.pointerEvents = ""; }
        for (const el of [stickL, stickR, btnFire, btnStart, btnZEnterGame, btnPlayZombies, btnZQuickPlay]) {
          if (!el) continue;
          el.style.touchAction = "";
          el.style.pointerEvents = "";
        }

        try { window.BCO_TG && window.BCO_TG.showChrome && window.BCO_TG.showChrome(); } catch {}
      }
    } catch (e) {
      warn("setHardening failed", e);
    }
  }

  // prevent pinch zoom ONLY in game
  function installGestureBlockers() {
    try {
      const prevent = (e) => {
        if (!STATE.inGame) return;
        try { e.preventDefault(); } catch {}
      };
      document.addEventListener("gesturestart", prevent, { passive: false });
      document.addEventListener("gesturechange", prevent, { passive: false });
      document.addEventListener("gestureend", prevent, { passive: false });

      // allow scroll in modals ALWAYS; block only during game and only outside modals
      document.addEventListener("touchmove", (e) => {
        if (!STATE.inGame) return; // menu scroll works
        const path = (e.composedPath && e.composedPath()) || [];
        for (const n of path) {
          if (!n) continue;
          const cls = n.classList;
          if (cls && (cls.contains("modal") || cls.contains("modal-body") || cls.contains("allow-scroll"))) return;
        }
        e.preventDefault();
      }, { passive: false });

      log("gesture blockers installed");
    } catch (e) {
      warn("installGestureBlockers failed", e);
    }
  }

  // -------------------------
  // Telegram fullscreen take-over (best effort)
  // -------------------------
  function requestTakeover() {
    try {
      if (!TG) return;
      try { TG.ready && TG.ready(); } catch {}
      try { TG.expand && TG.expand(); } catch {}
      try { TG.MainButton && TG.MainButton.hide && TG.MainButton.hide(); } catch {}
      try { TG.BackButton && TG.BackButton.hide && TG.BackButton.hide(); } catch {}
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

    // stretch if not sized
    if (!rect.width || !rect.height) {
      canvas.style.width = "100vw";
      canvas.style.height = "100vh";
    }

    const r2 = canvas.getBoundingClientRect();
    const w = Math.max(1, Math.floor(r2.width * dpr));
    const h = Math.max(1, Math.floor(r2.height * dpr));

    if (canvas.width !== w) canvas.width = w;
    if (canvas.height !== h) canvas.height = h;

    // notify CORE about logical size in CSS px
    try {
      const c = CORE();
      if (c && c.resize) c.resize(Math.floor(r2.width), Math.floor(r2.height));
    } catch {}

    return { cssW: r2.width, cssH: r2.height, pxW: w, pxH: h, dpr };
  }

  // -------------------------
  // Dual-stick joystick (pointer-driven)
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

    function pushToCore(nx, ny) {
      const c = CORE();
      if (!c) return;
      if (kind === "move") c.setMove && c.setMove(nx, ny);
      else c.setAim && c.setAim(nx, ny);
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
      pushToCore(clx, cly);
    }

    function onUp(e) {
      if (!active) return;
      if (pid !== null && e.pointerId !== pid) return;

      active = false;
      pid = null;
      try { el.releasePointerCapture && el.releasePointerCapture(e.pointerId); } catch {}
      resetKnob();
      pushToCore(0, 0);
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
  // FIRE legacy behavior
  // -------------------------
  function setupFireBehavior() {
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
  // Auto-shoot on RIGHT stick hold
  // -------------------------
  function setupDualStickShooting(aimStick) {
    if (!aimStick) return;
    STATE._aimStick = aimStick;

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
  // Render hook (supports BOTH styles)
  // - New: BCO_ZOMBIES_RENDER.render(ctx, CORE, input, view)
  // - Old: BCO_ZOMBIES_RENDER.draw(canvas, snap)
  // -------------------------
  function drawFrame() {
    const c = CORE();
    if (!c || !c.getFrameData) return;

    const snap = c.getFrameData();
    STATE.lastSnapshot = snap;

    if (STATE.snapshotSubs.size) {
      for (const cb of STATE.snapshotSubs) {
        try { cb(snap); } catch {}
      }
    }

    if (!canvas) return;

    const R = window.BCO_ZOMBIES_RENDER || window.BCO_ZOMBIES_RENDERER || window.BCO_ZOMBIES_DRAW;

    // Preferred: render(ctx, CORE, input, view)
    if (R && typeof R.render === "function") {
      try {
        const ctx = canvas.getContext("2d");
        const view = { w: canvas.width, h: canvas.height };
        const input = c.input || { aimX: 0, aimY: 0 };
        R.render(ctx, c, input, view);
        return;
      } catch (e) {
        // fall through
      }
    }

    // Legacy: draw(canvas, snap)
    if (R && typeof R.draw === "function") {
      try { R.draw(canvas, snap); return; } catch (e) { /* fallback */ }
    }

    // minimal fallback
    const ctx = canvas.getContext("2d");
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
  // Loop (guaranteed start)
  // -------------------------
  function startLoop() {
    if (STATE._raf) return true;

    const c = CORE();
    if (!c || !c.updateFrame || !c.getFrameData) {
      health("Core not loaded");
      warn("BCO_ZOMBIES_CORE missing/incomplete");
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
      STATE._raf = requestAnimationFrame(frame);
    }

    STATE._raf = requestAnimationFrame(frame);
    health("loop ok");
    log("loop started");
    return true;
  }

  function stopLoop() {
    if (!STATE._raf) return true;
    try { cancelAnimationFrame(STATE._raf); } catch {}
    STATE._raf = 0;
    return true;
  }

  // -------------------------
  // GAME lifecycle (contract for zombies.init.js)
  // -------------------------
  function open() { return true; }
  function close() { return true; }

  function setMode(mode) { STATE.mode = String(mode || "arcade"); return STATE.mode; }
  function setMap(map) { STATE.map = String(map || "Ashes"); return STATE.map; }

  function setCharacter(character, skin) {
    STATE.character = String(character || "male");
    STATE.skin = String(skin || "default");
    return { character: STATE.character, skin: STATE.skin };
  }

  function setWeapon(key) {
    STATE.weaponKey = String(key || "SMG");
    try { CORE()?.setWeapon?.(STATE.weaponKey); } catch {}
    return STATE.weaponKey;
  }

  function start(mode = "arcade", opts = {}) {
    const c = CORE();
    if (!c || !c.start) {
      health("Core not ready");
      return false;
    }

    // Ensure canvas exists BEFORE hardening/takeover
    canvas = ensureCanvas();
    if (!canvas) {
      health("No canvas");
      return false;
    }

    // apply opts -> local state
    if (opts && typeof opts === "object") {
      if (opts.map) STATE.map = String(opts.map);
      if (opts.character) STATE.character = String(opts.character);
      if (opts.skin) STATE.skin = String(opts.skin);
      if (opts.weaponKey) STATE.weaponKey = String(opts.weaponKey);
    }
    STATE.mode = String(mode || STATE.mode || "arcade");

    // enter game mode (hardening ON)
    STATE.inGame = true;
    setHardening(true);

    // takeover
    requestTakeover();

    // ensure canvas sized
    const r = resizeCanvas() || { cssW: window.innerWidth, cssH: window.innerHeight };

    try {
      c.start(STATE.mode, Math.floor(r.cssW), Math.floor(r.cssH), {
        map: STATE.map,
        character: STATE.character,
        skin: STATE.skin,
        weaponKey: STATE.weaponKey
      });

      startLoop();
      health("running");
      return true;
    } catch (e) {
      warn("CORE.start failed", e);
      health("start failed");
      return false;
    }
  }

  function stop(reason = "manual") {
    const c = CORE();
    try { c?.stop?.(reason); } catch {}

    STATE.inGame = false;
    setHardening(false);

    stopLoop();

    // optional: hide canvas (do not destroy)
    try {
      if (canvas) {
        // keep it in DOM for next start; just stop drawing.
      }
    } catch {}

    health("stopped");
    return true;
  }

  // Shop passthrough (contract)
  function buyPerk(id) { try { return !!CORE()?.buyPerk?.(id); } catch { return false; } }
  function reload() { try { return !!CORE()?.reload?.(); } catch { return false; } }
  function usePlate() { try { return !!CORE()?.usePlate?.(); } catch { return false; } }

  function getSnapshot() { return STATE.lastSnapshot || (CORE()?.getFrameData?.() ?? null); }
  function onSnapshot(cb) {
    if (typeof cb !== "function") return false;
    STATE.snapshotSubs.add(cb);
    return true;
  }

  function getInput() {
    const c = CORE();
    if (!c) return null;
    return { ...c.input };
  }

  function setInput(obj) {
    const c = CORE();
    if (!c || !obj) return false;
    try {
      if (typeof obj.moveX === "number" || typeof obj.moveY === "number") c.setMove?.(obj.moveX || 0, obj.moveY || 0);
      if (typeof obj.aimX === "number" || typeof obj.aimY === "number") c.setAim?.(obj.aimX || 0, obj.aimY || 0);
      if (typeof obj.shooting === "boolean") c.setShooting?.(obj.shooting);
      return true;
    } catch { return false; }
  }

  function sendResult(reason = "manual") {
    try {
      const snap = getSnapshot();
      if (!snap) return false;

      const payload = {
        action: "game_result",
        game: "zombies",
        reason,
        mode: snap.meta?.mode || STATE.mode,
        map: snap.meta?.map || STATE.map,
        wave: snap.hud?.wave || 1,
        kills: snap.hud?.kills || 0,
        coins: snap.hud?.coins || 0,
        duration: snap.hud?.timeMs || 0,
        relics: snap.hud?.relics || 0,
        wonderUnlocked: !!snap.hud?.wonderUnlocked
      };

      if (TG && TG.sendData) {
        TG.sendData(JSON.stringify(payload));
        return true;
      }
    } catch {}
    return false;
  }

  // -------------------------
  // Wire start buttons (YOUR UI)
  // -------------------------
  function wireStartButton(el) {
    if (!el) return;
    el.addEventListener("pointerdown", (e) => {
      try { e.preventDefault(); } catch {}
      start(STATE.mode || "arcade", {
        map: STATE.map,
        character: STATE.character,
        skin: STATE.skin,
        weaponKey: STATE.weaponKey
      });
    }, { passive: false });
  }

  // -------------------------
  // Init
  // -------------------------
  function init() {
    installGestureBlockers();

    // Prepare canvas lazily (do not force takeover)
    canvas = ensureCanvas();

    // sticks (if present)
    const moveStick = makeStick(stickL, "move");
    const aimStick  = makeStick(stickR, "aim");
    if (aimStick) setupDualStickShooting(aimStick);
    setupFireBehavior();

    // start buttons
    wireStartButton(btnStart);
    wireStartButton(btnZEnterGame);
    wireStartButton(btnPlayZombies);
    wireStartButton(btnZQuickPlay);

    // tap canvas to start (only when not running)
    if (canvas) {
      canvas.addEventListener("pointerdown", (e) => {
        const c = CORE();
        if (!c || c.running) return;
        try { e.preventDefault(); } catch {}
        start(STATE.mode || "arcade", {
          map: STATE.map,
          character: STATE.character,
          skin: STATE.skin,
          weaponKey: STATE.weaponKey
        });
      }, { passive: false });
    }

    window.addEventListener("resize", () => { resizeCanvas(); });

    if (TG) {
      try { TG.ready && TG.ready(); } catch {}
      try { TG.expand && TG.expand(); } catch {}
    }

    try { if (CORE()?.running) startLoop(); } catch {}

    // start in menu mode -> hardening OFF so scroll works
    STATE.inGame = false;
    setHardening(false);

    health("ready");
    log("init ok", {
      hasMount: !!overlayMount,
      hasCanvas: !!canvas,
      hasL: !!stickL,
      hasR: !!stickR,
      hasFire: !!btnFire,
      hasStartOld: !!btnStart,
      hasStartUI: !!btnZEnterGame || !!btnPlayZombies || !!btnZQuickPlay
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }

  // Export CONTRACT API (this is what zombies.init.js expects)
  window.BCO_ZOMBIES_GAME = {
    open,
    close,
    start,
    stop,
    setMode,
    setMap,
    setCharacter,
    setWeapon,
    buyPerk,
    reload,
    usePlate,
    sendResult,
    getSnapshot,
    onSnapshot,
    getInput,
    setInput,
    resizeCanvas,
    startLoop
  };
})();
