// app/webapp/static/bco.engine.js
(() => {
  "use strict";

  // Single Engine (elite):
  // - Uses BCO_ZOMBIES_CORE (your v1.4.2 3D-ready core)
  // - Uses renderer plugin if present: window.BCO_ZOMBIES_RENDER / window.BCO_ZOMBIES_RENDERER
  // - Fullscreen canvas on #zOverlayMount (NO UI redesign)
  // - Contract: zoom bump = +0.5 to current (CFG.ZOOM_BUMP default 0.5)

  window.BCO = window.BCO || {};
  const CFG = window.BCO.CONFIG || window.BCO_CONFIG || {};
  const ZOOM_BUMP = Number(CFG.ZOOM_BUMP || 0.5);

  function qs(id) { return document.getElementById(id); }
  function safe(fn) { try { return fn(); } catch (_) { return undefined; } }
  function log(...a) { console.log("[BCO_ENGINE]", ...a); }

  const Engine = (() => {
    const st = {
      core: null,
      canvas: null,
      ctx: null,
      raf: 0,
      running: false,
      w: 0,
      h: 0,
      lastTS: 0
    };

    function detectCore() {
      st.core = window.BCO_ZOMBIES_CORE || null;
      return !!st.core;
    }

    function detectRenderer() {
      return window.BCO_ZOMBIES_RENDER || window.BCO_ZOMBIES_RENDERER || null;
    }

    function ensureCanvas() {
      const mount = qs("zOverlayMount");
      if (!mount) return null;

      let c = mount.querySelector("#bcoZCanvas");
      if (!c) {
        c = document.createElement("canvas");
        c.id = "bcoZCanvas";
        c.style.position = "fixed";
        c.style.left = "0";
        c.style.top = "0";
        c.style.width = "100vw";
        c.style.height = "100vh";
        c.style.zIndex = "9999";
        c.style.display = "none";
        c.style.background = "transparent";
        c.style.pointerEvents = "none"; // input handled by your overlay/joysticks modules
        mount.appendChild(c);
      }

      st.canvas = c;
      st.ctx = c.getContext("2d", { alpha: true, desynchronized: true });
      return c;
    }

    function resize() {
      if (!st.canvas || !st.core) return;

      const dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
      const w = Math.floor(window.innerWidth * dpr);
      const h = Math.floor(window.innerHeight * dpr);
      if (w === st.w && h === st.h) return;

      st.w = w; st.h = h;
      st.canvas.width = w;
      st.canvas.height = h;

      safe(() => st.core.resize?.(w, h));
    }

    function renderFallback(frame) {
      const ctx = st.ctx;
      const c = st.canvas;
      if (!ctx || !c) return;

      ctx.clearRect(0, 0, c.width, c.height);
      ctx.save();
      ctx.globalAlpha = 0.9;

      ctx.fillStyle = "rgba(0,0,0,0.35)";
      ctx.fillRect(18, 18, 440, 160);

      ctx.fillStyle = "rgba(255,255,255,0.92)";
      ctx.font = "24px system-ui,-apple-system,Inter,Arial";
      ctx.fillText("ZOMBIES (renderer missing)", 28, 52);

      if (frame && frame.hud) {
        ctx.font = "18px system-ui,-apple-system,Inter,Arial";
        ctx.fillText(`wave ${frame.hud.wave} kills ${frame.hud.kills}`, 28, 82);
        ctx.fillText(`coins ${frame.hud.coins} lvl ${frame.hud.level}`, 28, 108);
        ctx.fillText(`relics ${frame.hud.relics}/${frame.hud.relicNeed}`, 28, 134);
        ctx.fillText(`zoom ${frame.camera?.zoom ?? "?"}`, 28, 160);
      }

      ctx.restore();
    }

    function render(frame) {
      const R = detectRenderer();
      if (R && typeof R.renderFrame === "function") {
        return safe(() => R.renderFrame(frame, st.ctx, st.canvas));
      }
      if (R && typeof R.render === "function") {
        return safe(() => R.render(frame, st.ctx, st.canvas));
      }
      renderFallback(frame);
      return null;
    }

    function loop(ts) {
      if (!st.running) return;

      resize();

      const t = (typeof ts === "number") ? ts : ((performance && performance.now) ? performance.now() : Date.now());
      st.lastTS = t;

      safe(() => st.core.updateFrame?.(t));
      const frame = safe(() => st.core.getFrameData?.()) || null;

      render(frame);

      st.raf = requestAnimationFrame(loop);
    }

    // Public: start({mode,map})
    function start({ mode, map } = {}) {
      if (!detectCore()) return false;
      ensureCanvas();
      resize();

      const m = String(mode || "arcade").toLowerCase().includes("rogue") ? "roguelike" : "arcade";
      const mp = (String(map || "Ashes") === "Astra") ? "Astra" : "Ashes";

      const tms = (performance && performance.now) ? performance.now() : Date.now();

      // IMPORTANT: core.start signature: start(mode, w, h, opts, tms)
      safe(() => st.core.start(m, st.w, st.h, { map: mp }, tms));

      // Contract: zoom bump +0.5 to CURRENT (not absolute)
      if (typeof st.core.setZoomDelta === "function") {
        safe(() => st.core.setZoomDelta(ZOOM_BUMP));
      }

      st.canvas.style.display = "block";
      st.running = true;

      // stable resize hooks
      window.addEventListener("resize", resize, { passive: true });
      window.addEventListener("orientationchange", () => setTimeout(resize, 50), { passive: true });

      st.raf = requestAnimationFrame(loop);

      log("started", { mode: m, map: mp, zoomBump: ZOOM_BUMP });
      return true;
    }

    function stop() {
      st.running = false;

      if (st.raf) cancelAnimationFrame(st.raf);
      st.raf = 0;

      safe(() => st.core?.stop?.());

      if (st.canvas) st.canvas.style.display = "none";

      window.removeEventListener("resize", resize);

      log("stopped");
      return true;
    }

    function getFrame() {
      return safe(() => st.core?.getFrameData?.()) || null;
    }

    function getZoom() {
      if (!st.core) st.core = window.BCO_ZOMBIES_CORE || null;
      if (!st.core) return null;
      if (typeof st.core.getZoom === "function") return safe(() => st.core.getZoom());
      return st.core.state?.zoom ?? null;
    }

    function setZoomDelta(d) {
      if (!st.core) st.core = window.BCO_ZOMBIES_CORE || null;
      if (!st.core) return null;
      if (typeof st.core.setZoomDelta === "function") return safe(() => st.core.setZoomDelta(d));
      // fallback
      const cur = Number(st.core.state?.zoom || 1.0);
      st.core.state.zoom = cur + Number(d || 0);
      return st.core.state.zoom;
    }

    // Optional input bridge (if your input layer uses it later)
    function setInput({ moveX, moveY, aimX, aimY, shooting } = {}) {
      if (!st.core) st.core = window.BCO_ZOMBIES_CORE || null;
      if (!st.core) return false;

      if (moveX != null || moveY != null) safe(() => st.core.setMove?.(moveX || 0, moveY || 0));
      if (aimX != null || aimY != null) safe(() => st.core.setAim?.(aimX || 0, aimY || 0));
      if (shooting != null) safe(() => st.core.setShooting?.(!!shooting));
      return true;
    }

    return { start, stop, getFrame, getZoom, setZoomDelta, setInput };
  })();

  // Single source of truth:
  window.BCO.engine = Engine;
  // Compatibility alias:
  window.BCO_ENGINE = Engine;
})();
