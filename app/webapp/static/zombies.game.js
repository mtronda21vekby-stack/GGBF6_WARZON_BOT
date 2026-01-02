// app/webapp/static/zombies.game.js  [ULTRA LUX vNext | Dual-Stick + iOS Fix + Start Fix]
// IMPORTANT: UI не меняем — только логика, клики, запуск.
// FIXES:
// - Scrolling in menu/tab screens works (no global kill).
// - Scroll inside modals works.
// - Game always starts (API contract aligned with zombies.init.js).
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

  // Main game canvas (must exist on Game tab screen)
  const canvas = pickEl([
    "#zombiesCanvas",
    "#zCanvas",
    "canvas#zombies",
    "canvas#game",
    "canvas"
  ]);

  // Left/right joystick containers (UI already has circles)
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

  // Start fullscreen (optional)
  const btnStart = pickEl([
    "#btnStartFullscreen",
    "button[data-action='start_fullscreen']",
    ".btn-start-fullscreen",
    "#startFullscreen",
    ".start-fullscreen"
  ]);

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
    _raf: 0
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

        // prevent selection / callout
        body.style.userSelect = "none";
        body.style.webkitUserSelect = "none";
        body.style.webkitTouchCallout = "none";

        // stop overscroll bounce
        root.style.overscrollBehavior = "none";
        body.style.overscrollBehavior = "none";

        // IMPORTANT: lock gestures only in game
        root.style.touchAction = "none";
        body.style.touchAction = "none";

        // ensure main controls receive pointer events
        if (canvas) { canvas.style.touchAction = "none"; canvas.style.pointerEvents = "auto"; }
        for (const el of [stickL, stickR, btnFire, btnStart]) {
          if (!el) continue;
          el.style.touchAction = "none";
          el.style.pointerEvents = "auto";
        }
      } else {
        body.classList.remove("bco-game-active");

        // restore to allow scroll everywhere
        body.style.userSelect = "";
        body.style.webkitUserSelect = "";
        body.style.webkitTouchCallout = "";

        root.style.overscrollBehavior = "";
        body.style.overscrollBehavior = "";

        root.style.touchAction = "";
        body.style.touchAction = "";

        if (canvas) { canvas.style.touchAction = ""; canvas.style.pointerEvents = ""; }
        for (const el of [stickL, stickR, btnFire, btnStart]) {
          if (!el) continue;
          el.style.touchAction = "";
          el.style.pointerEvents = "";
        }
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
        if (!STATE.inGame) return; // <- menu scroll works
        const path = (e.composedPath && e.composedPath()) || [];
        for (const n of path) {
          if (!n) continue;
          const cls = n.classList;
          if (cls && (cls.contains("modal") || cls.contains("modal-body") || cls.contains("allow-scroll"))) {
            return; // allow modal scrolling even in game
          }
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

      // evolving API - safe calls
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

    // notify CORE about logical size in CSS px
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

      // center
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
    // If dual-stick exists -> FIRE redundant. Hide it.
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
    STATE.lastSnapshot = snap;

    // notify subscribers
    if (STATE.snapshotSubs.size) {
      for (const cb of STATE.snapshotSubs) {
        try { cb(snap); } catch {}
      }
    }

    const R = window.BCO_ZOMBIES_RENDER || window.BCO_ZOMBIES_RENDERER || window.BCO_ZOMBIES_DRAW;
    if (R && typeof R.draw === "function") {
      try { R.draw(canvas, snap); return; } catch (e) { /* fallback */ }
    }

    // minimal fallback
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
  function open() {
    // If you already have overlay open/close logic elsewhere – keep it there.
    // Here: just mark state; do not change UI layout.
    return true;
  }

  function close() {
    return true;
  }

  function setMode(mode) {
    STATE.mode = String(mode || "arcade");
    return STATE.mode;
  }

  function setMap(map) {
    STATE.map = String(map || "Ashes");
    return STATE.map;
  }

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

    // best effort takeover
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

    // exit game mode (hardening OFF -> scroll returns)
    STATE.inGame = false;
    setHardening(false);

    stopLoop();
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
    // If you already have app.js sendData -> use it there.
    // Here we just provide a hook.
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

      // telegram sendData if available
      if (TG && TG.sendData) {
        TG.sendData(JSON.stringify(payload));
        return true;
      }
    } catch {}
    return false;
  }

  // -------------------------
  // Init
  // -------------------------
  function init() {
    installGestureBlockers();

    // sticks
    const moveStick = makeStick(stickL, "move");
    const aimStick  = makeStick(stickR, "aim");

    if (aimStick) setupDualStickShooting(aimStick);
    setupFireBehavior();

    // start button (optional)
    if (btnStart) {
      btnStart.addEventListener("pointerdown", (e) => {
        try { e.preventDefault(); } catch {}
        start(STATE.mode || "arcade", { map: STATE.map, character: STATE.character, skin: STATE.skin, weaponKey: STATE.weaponKey });
      }, { passive: false });
    }

    // tap canvas to start (only when not running)
    if (canvas) {
      canvas.addEventListener("pointerdown", (e) => {
        const c = CORE();
        if (!c || c.running) return;
        try { e.preventDefault(); } catch {}
        start(STATE.mode || "arcade", { map: STATE.map, character: STATE.character, skin: STATE.skin, weaponKey: STATE.weaponKey });
      }, { passive: false });
    }

    // resize
    window.addEventListener("resize", () => { resizeCanvas(); });

    // Telegram ready/expand (does not takeover)
    if (TG) {
      try { TG.ready && TG.ready(); } catch {}
      try { TG.expand && TG.expand(); } catch {}
    }

    // ensure loop if core already running
    try { if (CORE()?.running) startLoop(); } catch {}

    // start in menu mode -> hardening OFF so scroll works
    STATE.inGame = false;
    setHardening(false);

    health("ready");
    log("init ok", { hasCanvas: !!canvas, hasL: !!stickL, hasR: !!stickR, hasFire: !!btnFire, hasStart: !!btnStart });
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
