// app/webapp/static/zombies.game.js  [ULTRA LUX vNext | NO-UI Runner + ZOOM Contract + iOS Fix]
// IMPORTANT:
// - UI НЕ меняем. Этот модуль НЕ трогает кнопки/оверлей/вкладки.
// - НЕТ автосоздания canvas, НЕТ автопривязки Start кнопок, НЕТ автозапуска.
// - Работает как "runner": setCanvas(canvas) + startLoop() (когда core уже start'нут UI-слоем).
// - ZOOM: passthrough API (+0.5 delta contract) + fallback renderer uses snap.camera.zoom.

(() => {
  "use strict";

  const log = (...a) => { try { console.log("[Z_GAME]", ...a); } catch {} };
  const warn = (...a) => { try { console.warn("[Z_GAME]", ...a); } catch {} };

  const TG = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;

  // -------------------------
  // Safe DOM helpers
  // -------------------------
  const $ = (sel) => document.querySelector(sel);
  const jsHealth = $("#jsHealth") || $(".jsHealth") || $("[data-js-health]");
  function health(msg) { try { if (jsHealth) jsHealth.textContent = String(msg || ""); } catch {} }

  // -------------------------
  // CORE / RENDER
  // -------------------------
  function CORE() { return window.BCO_ZOMBIES_CORE || null; }

  function getRenderer() {
    return window.BCO_ZOMBIES_RENDER || window.BCO_ZOMBIES_RENDERER || window.BCO_ZOMBIES_DRAW || null;
  }

  // -------------------------
  // STATE
  // -------------------------
  const STATE = {
    inGame: false,             // controlled by UI layer (app.js) usually
    lastSnapshot: null,
    snapshotSubs: new Set(),
    _raf: 0,
    _canvas: null,
    _ctx2d: null,
    _dpr: 1,
    _cssW: 0,
    _cssH: 0
  };

  // -------------------------
  // iOS / WebView hardening (NO UI changes, only safe guards)
  // - pinch/double-tap zoom prevention only when inGame=true
  // -------------------------
  function installGestureBlockers() {
    try {
      const prevent = (e) => {
        if (!STATE.inGame) return;
        try { e.preventDefault(); } catch {}
      };

      document.addEventListener("gesturestart", prevent, { passive: false });
      document.addEventListener("gesturechange", prevent, { passive: false });
      document.addEventListener("gestureend", prevent, { passive: false });

      // IMPORTANT: do not kill scroll in modals; allow scroll inside modal cards
      document.addEventListener("touchmove", (e) => {
        if (!STATE.inGame) return;
        const path = (e.composedPath && e.composedPath()) || [];
        for (const n of path) {
          if (!n) continue;
          const cls = n.classList;
          if (cls && (
            cls.contains("bco-z-card") ||
            cls.contains("bco-z-modal") ||
            cls.contains("modal") ||
            cls.contains("modal-body") ||
            cls.contains("allow-scroll")
          )) return;
        }
        try { e.preventDefault(); } catch {}
      }, { passive: false });

      log("gesture blockers installed");
    } catch (e) {
      warn("installGestureBlockers failed", e);
    }
  }

  // -------------------------
  // Canvas lifecycle
  // -------------------------
  function setCanvas(c) {
    if (!c || typeof c.getContext !== "function") {
      warn("setCanvas: invalid canvas");
      return false;
    }
    STATE._canvas = c;
    STATE._ctx2d = null;
    // Apply safe defaults (no visual UI changes; just ensure touch doesn't scroll/zoom on canvas)
    try { c.style.touchAction = "none"; } catch {}
    try { c.style.webkitUserSelect = "none"; } catch {}
    try { c.style.userSelect = "none"; } catch {}
    resizeCanvas(); // best effort
    return true;
  }

  function getCanvas() { return STATE._canvas || null; }

  // devicePixelRatio correct sizing, but DOES NOT create canvas
  function resizeCanvas() {
    const canvas = STATE._canvas;
    if (!canvas) return null;

    const dpr = Math.max(1, Math.min(3, (window.devicePixelRatio || 1)));
    const rect = canvas.getBoundingClientRect();

    const cssW = Math.max(1, rect.width || window.innerWidth || 1);
    const cssH = Math.max(1, rect.height || window.innerHeight || 1);

    const pxW = Math.max(1, Math.floor(cssW * dpr));
    const pxH = Math.max(1, Math.floor(cssH * dpr));

    if (canvas.width !== pxW) canvas.width = pxW;
    if (canvas.height !== pxH) canvas.height = pxH;

    STATE._dpr = dpr;
    STATE._cssW = cssW;
    STATE._cssH = cssH;

    // Inform core in CSS pixels (common contract)
    try {
      const c = CORE();
      if (c && typeof c.resize === "function") c.resize(Math.floor(cssW), Math.floor(cssH));
    } catch {}

    return { cssW, cssH, pxW, pxH, dpr };
  }

  // -------------------------
  // Render hook (supports BOTH styles)
  // - New: R.render(ctx, CORE, input, view)
  // - Old: R.draw(canvas, snap)
  // - Fallback: minimal draw() with snap.camera.zoom
  // -------------------------
  function drawFrame() {
    const core = CORE();
    if (!core || typeof core.getFrameData !== "function") return;

    const snap = core.getFrameData();
    STATE.lastSnapshot = snap;

    if (STATE.snapshotSubs.size) {
      for (const cb of STATE.snapshotSubs) {
        try { cb(snap); } catch {}
      }
    }

    const canvas = STATE._canvas;
    if (!canvas) return;

    const R = getRenderer();

    // Preferred renderer
    if (R && typeof R.render === "function") {
      try {
        const ctx = STATE._ctx2d || (STATE._ctx2d = canvas.getContext("2d"));
        const view = { w: canvas.width, h: canvas.height, cssW: STATE._cssW, cssH: STATE._cssH, dpr: STATE._dpr };
        const input = core.input || { aimX: 0, aimY: 0, moveX: 0, moveY: 0 };
        R.render(ctx, core, input, view);
        return;
      } catch (e) {
        // fall through
      }
    }

    // Legacy renderer
    if (R && typeof R.draw === "function") {
      try { R.draw(canvas, snap); return; } catch (e) { /* fallback */ }
    }

    // Minimal fallback + ✅ ZOOM from snapshot
    const ctx = STATE._ctx2d || (STATE._ctx2d = canvas.getContext("2d"));
    if (!ctx) return;

    const w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    const camX = snap.camera?.x || 0;
    const camY = snap.camera?.y || 0;

    // ✅ zoom from snapshot (contract from CORE)
    const zoom = Math.max(0.25, Math.min(4, Number(snap.camera?.zoom) || 1));
    const dpr = STATE._dpr || 1;

    const toX = (x) => (w / 2) + (x - camX) * dpr * zoom;
    const toY = (y) => (h / 2) + (y - camY) * dpr * zoom;

    // Player
    if (snap.player) {
      ctx.beginPath();
      ctx.arc(toX(snap.player.x || 0), toY(snap.player.y || 0), 14 * dpr * zoom, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(220,220,255,0.95)";
      ctx.fill();
    }

    // Zombies
    for (const z of (snap.zombies || [])) {
      ctx.beginPath();
      ctx.arc(toX(z.x || 0), toY(z.y || 0), (z.r || 16) * dpr * zoom, 0, Math.PI * 2);
      ctx.fillStyle = z.elite ? "rgba(255,210,120,0.95)" : "rgba(140,255,140,0.85)";
      ctx.fill();
    }

    // Bullets
    for (const b of (snap.bullets || [])) {
      ctx.beginPath();
      ctx.arc(toX(b.x || 0), toY(b.y || 0), 3 * dpr * zoom, 0, Math.PI * 2);
      ctx.fillStyle = b.crit ? "rgba(255,210,120,0.95)" : "rgba(240,240,255,0.9)";
      ctx.fill();
    }
  }

  // -------------------------
  // Loop (NO AUTOSTART)
  // -------------------------
  function startLoop() {
    if (STATE._raf) return true;

    const core = CORE();
    if (!core || typeof core.updateFrame !== "function" || typeof core.getFrameData !== "function") {
      health("Core not loaded");
      warn("BCO_ZOMBIES_CORE missing/incomplete");
      return false;
    }

    function frame(tms) {
      try {
        // Resize is cheap, but we throttle implicitly by RAF; ok for iOS.
        resizeCanvas();
        core.updateFrame(tms);
        drawFrame();
      } catch (e) {
        warn("frame error", e);
        health("frame error");
      }
      STATE._raf = requestAnimationFrame(frame);
    }

    STATE._raf = requestAnimationFrame(frame);
    health("loop ok");
    return true;
  }

  function stopLoop() {
    if (!STATE._raf) return true;
    try { cancelAnimationFrame(STATE._raf); } catch {}
    STATE._raf = 0;
    return true;
  }

  // -------------------------
  // In-game flag (UI layer should toggle this)
  // -------------------------
  function setInGame(on) {
    STATE.inGame = !!on;
    // TG chrome hide is handled by UI layer (app.js / BCO_TG). We do NOT touch UI here.
    return STATE.inGame;
  }

  function isInGame() { return !!STATE.inGame; }

  // -------------------------
  // Input passthrough helpers (optional; UI uses its own pump normally)
  // -------------------------
  function setInput(obj) {
    const core = CORE();
    if (!core || !obj) return false;
    try {
      if (typeof obj.moveX === "number" || typeof obj.moveY === "number") core.setMove?.(obj.moveX || 0, obj.moveY || 0);
      if (typeof obj.aimX === "number" || typeof obj.aimY === "number") core.setAim?.(obj.aimX || 0, obj.aimY || 0);
      if (typeof obj.shooting === "boolean") core.setShooting?.(obj.shooting);
      return true;
    } catch { return false; }
  }

  function getInput() {
    const core = CORE();
    if (!core) return null;
    try { return { ...(core.input || {}) }; } catch { return null; }
  }

  // -------------------------
  // Snapshot access
  // -------------------------
  function getSnapshot() {
    const core = CORE();
    return STATE.lastSnapshot || (core?.getFrameData?.() ?? null);
  }

  function onSnapshot(cb) {
    if (typeof cb !== "function") return false;
    STATE.snapshotSubs.add(cb);
    return true;
  }

  // -------------------------
  // Shop passthrough
  // -------------------------
  function buyPerk(id) { try { return !!CORE()?.buyPerk?.(id); } catch { return false; } }
  function reload() { try { return !!CORE()?.reload?.(); } catch { return false; } }
  function usePlate() { try { return !!CORE()?.usePlate?.(); } catch { return false; } }

  // -------------------------
  // ✅ ZOOM passthrough API (contract: +0.5 delta)
  // -------------------------
  function getZoom() { try { return CORE()?.getZoom?.() ?? 1; } catch { return 1; } }
  function setZoomLevel(z) { try { return CORE()?.setZoomLevel?.(z) ?? getZoom(); } catch { return getZoom(); } }
  function setZoomDelta(d) { try { return CORE()?.setZoomDelta?.(d) ?? getZoom(); } catch { return getZoom(); } }
  function zoomIn() { return setZoomDelta(+0.5); }
  function zoomOut() { return setZoomDelta(-0.5); }

  // -------------------------
  // Result send helper (optional; UI usually sends richer payload)
  // -------------------------
  function sendResult(reason = "manual") {
    try {
      const snap = getSnapshot();
      if (!snap) return false;

      const payload = {
        action: "game_result",
        game: "zombies",
        reason,
        mode: snap.meta?.mode || "unknown",
        map: snap.meta?.map || "unknown",
        wave: snap.hud?.wave || 1,
        kills: snap.hud?.kills || 0,
        coins: snap.hud?.coins || 0,
        duration: snap.hud?.timeMs || 0,
        relics: snap.hud?.relics || 0,
        wonderUnlocked: !!snap.hud?.wonderUnlocked,
        zoom: Number(snap.camera?.zoom) || 1
      };

      if (TG && TG.sendData) {
        TG.sendData(JSON.stringify(payload));
        return true;
      }
    } catch {}
    return false;
  }

  // -------------------------
  // Init (NO UI binding)
  // -------------------------
  function init() {
    installGestureBlockers();
    window.addEventListener("resize", () => { resizeCanvas(); }, { passive: true });

    // If core is already running and UI has already provided canvas+inGame, we can start loop later.
    // We DO NOT autostart loop here to avoid conflicts with app.js orchestration.
    health("ready");
    log("init ok (NO-UI runner)");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }

  // Export CONTRACT API (safe, no UI control)
  window.BCO_ZOMBIES_GAME = {
    // canvas
    setCanvas,
    getCanvas,
    resizeCanvas,

    // loop
    startLoop,
    stopLoop,

    // in-game flag (used by gesture blockers only)
    setInGame,
    isInGame,

    // snapshot / input
    getSnapshot,
    onSnapshot,
    getInput,
    setInput,

    // shop passthrough
    buyPerk,
    reload,
    usePlate,

    // result
    sendResult,

    // zoom API (contract +0.5 delta)
    getZoom,
    setZoomLevel,
    setZoomDelta,
    zoomIn,
    zoomOut
  };
})();
