// app/webapp/static/bco.engine.js
(() => {
  "use strict";

  window.BCO = window.BCO || {};
  const CFG = window.BCO.CONFIG || {};
  const ZOOM_BUMP = Number(CFG.ZOOM_BUMP || 0.5);

  function qs(id) { return document.getElementById(id); }
  function log(...a) { console.log("[BCO_ENGINE]", ...a); }

  const Engine = (() => {
    const st = {
      core: null,
      canvas: null,
      ctx: null,
      raf: 0,
      running: false,
      w: 0,
      h: 0
    };

    function detectCore() {
      st.core = window.BCO_ZOMBIES_CORE || null;
      return !!st.core;
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
        c.style.pointerEvents = "none"; // UI overlay handles input
        mount.appendChild(c);
      }

      st.canvas = c;
      st.ctx = c.getContext("2d", { alpha: true, desynchronized: true });
      return c;
    }

    function resize() {
      if (!st.canvas) return;
      const dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
      const w = Math.floor(window.innerWidth * dpr);
      const h = Math.floor(window.innerHeight * dpr);
      if (w === st.w && h === st.h) return;
      st.w = w; st.h = h;
      st.canvas.width = w;
      st.canvas.height = h;
      try { st.core?.resize?.(w, h); } catch {}
    }

    function render(frame) {
      const R = window.BCO_ZOMBIES_RENDER || window.BCO_ZOMBIES_RENDERER || null;
      if (R && typeof R.renderFrame === "function") {
        R.renderFrame(frame, st.ctx, st.canvas);
        return;
      }
      if (R && typeof R.render === "function") {
        R.render(frame, st.ctx, st.canvas);
        return;
      }

      // fallback minimal debug
      const ctx = st.ctx;
      ctx.clearRect(0, 0, st.canvas.width, st.canvas.height);
      ctx.save();
      ctx.globalAlpha = 0.9;
      ctx.fillStyle = "rgba(0,0,0,0.35)";
      ctx.fillRect(18, 18, 420, 140);
      ctx.fillStyle = "rgba(255,255,255,0.92)";
      ctx.font = "24px system-ui,-apple-system,Inter,Arial";
      ctx.fillText("ZOMBIES (render missing)", 28, 52);
      if (frame && frame.hud) {
        ctx.font = "18px system-ui,-apple-system,Inter,Arial";
        ctx.fillText(`wave ${frame.hud.wave} kills ${frame.hud.kills}`, 28, 82);
        ctx.fillText(`coins ${frame.hud.coins} relics ${frame.hud.relics}/${frame.hud.relicNeed}`, 28, 108);
        ctx.fillText(`zoom ${frame.camera?.zoom || "?"}`, 28, 134);
      }
      ctx.restore();
    }

    function loop() {
      if (!st.running) return;
      resize();

      const t = (performance && performance.now) ? performance.now() : Date.now();
      try { st.core?.updateFrame?.(t); } catch {}

      let frame = null;
      try { frame = st.core?.getFrameData?.() || null; } catch {}
      render(frame);

      st.raf = requestAnimationFrame(loop);
    }

    function start({ mode, map }) {
      if (!detectCore()) return false;
      ensureCanvas();
      resize();

      const m = String(mode || "arcade").toLowerCase().includes("rogue") ? "roguelike" : "arcade";
      const mp = map || "Ashes";

      st.core.start(m, st.w, st.h, { map: mp }, (performance && performance.now) ? performance.now() : Date.now());

      // contract zoom bump (+0.5 to current)
      if (typeof st.core.setZoomDelta === "function") st.core.setZoomDelta(ZOOM_BUMP);

      st.canvas.style.display = "block";
      st.running = true;
      loop();
      log("started", m, mp);
      return true;
    }

    function stop() {
      st.running = false;
      if (st.raf) cancelAnimationFrame(st.raf);
      st.raf = 0;
      try { st.core?.stop?.(); } catch {}
      if (st.canvas) st.canvas.style.display = "none";
      return true;
    }

    function getFrame() {
      try { return st.core?.getFrameData?.() || null; } catch { return null; }
    }

    return { start, stop, getFrame };
  })();

  window.BCO.engine = Engine;
})();
