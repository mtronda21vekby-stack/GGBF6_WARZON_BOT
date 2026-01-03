// app/webapp/static/bco.input.js
// ULTRA: pointer-router + tap synthesis + gesture-guard for iOS WebView
(() => {
  "use strict";

  const CFG = window.BCO_CFG || {};
  const ZC = (CFG.ZOMBIES || {});
  const TAP_MAX_MOVE_PX = ZC.TAP_MAX_MOVE_PX || 12;
  const TAP_MAX_MS = ZC.TAP_MAX_MS || 520;

  const log = (...a) => { try { console.log("[BCO_INPUT]", ...a); } catch {} };

  function isScrollableEl(el) {
    if (!el) return false;
    const cls = el.classList;
    if (cls && (
      cls.contains("bco-z-card") ||
      cls.contains("bco-z-modal") ||
      cls.contains("modal") ||
      cls.contains("modal-body") ||
      cls.contains("allow-scroll") ||
      cls.contains("chat-log")
    )) return true;

    const st = window.getComputedStyle(el);
    const oy = st ? st.overflowY : "";
    return (oy === "auto" || oy === "scroll");
  }

  function composedPath(e) {
    try { return (e.composedPath && e.composedPath()) || []; } catch { return []; }
  }

  function hasScrollableInPath(e) {
    const p = composedPath(e);
    for (const n of p) {
      if (n && n.nodeType === 1 && isScrollableEl(n)) return true;
    }
    return false;
  }

  // GestureGuard: blocks pinch/zoom; blocks page-scroll ONLY when game takeover is active
  const GestureGuard = {
    _installed: false,
    _isGame: () => !!window.BCO_Z_RUNTIME?.isInGame?.(),

    install() {
      if (this._installed) return true;
      this._installed = true;

      const prevent = (e) => { try { e.preventDefault(); } catch {} };

      // iOS pinch gestures
      window.addEventListener("gesturestart", (e) => { if (this._isGame()) prevent(e); }, { passive: false });
      window.addEventListener("gesturechange", (e) => { if (this._isGame()) prevent(e); }, { passive: false });
      window.addEventListener("gestureend", (e) => { if (this._isGame()) prevent(e); }, { passive: false });

      // multi-touch scroll/zoom
      window.addEventListener("touchstart", (e) => {
        if (!this._isGame()) return;
        if (e.touches && e.touches.length > 1) prevent(e);
      }, { passive: false });

      // stop background scrolling, but DO NOT kill modal scroll
      window.addEventListener("touchmove", (e) => {
        if (!this._isGame()) return;
        if (hasScrollableInPath(e)) return;
        prevent(e);
      }, { passive: false });

      // ctrl+wheel zoom
      window.addEventListener("wheel", (e) => {
        if (!this._isGame()) return;
        if (e.ctrlKey) prevent(e);
      }, { passive: false });

      log("GestureGuard installed");
      return true;
    }
  };

  // TapSynth: fixes “tap doesn’t click” in iOS WebView by synthesizing click on short pointer sequences.
  const TapSynth = {
    _installed: false,
    _targets: null,

    install({ root = document, selector = "button, a, [role='button'], .btn, .chip, .seg-btn, .nav-btn" } = {}) {
      if (this._installed) return true;
      this._installed = true;
      this._targets = { root, selector };

      let down = null;

      function findTarget(e) {
        const t = e.target;
        if (!t || !t.closest) return null;
        return t.closest(selector);
      }

      root.addEventListener("pointerdown", (e) => {
        const tgt = findTarget(e);
        if (!tgt) return;
        // don't steal native scroll gestures
        if (hasScrollableInPath(e)) return;

        down = {
          id: e.pointerId,
          t: performance.now(),
          x: e.clientX,
          y: e.clientY,
          target: tgt
        };

        // Make sure we receive up/cancel even if finger slides
        try { tgt.setPointerCapture && tgt.setPointerCapture(e.pointerId); } catch {}

      }, { passive: true, capture: true });

      root.addEventListener("pointerup", (e) => {
        if (!down) return;
        if (e.pointerId !== down.id) return;

        const dt = performance.now() - down.t;
        const dx = e.clientX - down.x;
        const dy = e.clientY - down.y;

        const moved = Math.hypot(dx, dy);
        const okTap = (dt <= TAP_MAX_MS && moved <= TAP_MAX_MOVE_PX);

        const tgt = down.target;
        down = null;

        if (!okTap) return;
        if (!tgt || tgt.disabled) return;

        // iOS: sometimes pointerup doesn't trigger click — synthesize
        // But avoid double: only if event wasn't already default-handled.
        try {
          // focus + click
          tgt.focus && tgt.focus({ preventScroll: true });
        } catch {}

        try {
          // if element is inside label or has special, click still ok
          tgt.click();
        } catch {}
      }, { passive: true, capture: true });

      root.addEventListener("pointercancel", () => { down = null; }, { passive: true, capture: true });

      log("TapSynth installed", selector);
      return true;
    }
  };

  // PointerRouter: normalized pointers for dual-stick etc.
  const PointerRouter = {
    _installed: false,
    _handlers: new Set(),

    install() {
      if (this._installed) return true;
      this._installed = true;

      const on = (fn) => { if (typeof fn === "function") this._handlers.add(fn); return () => this._handlers.delete(fn); };

      const emit = (type, e) => {
        const payload = {
          type,
          pointerId: e.pointerId,
          x: e.clientX,
          y: e.clientY,
          t: performance.now(),
          target: e.target
        };
        for (const fn of this._handlers) { try { fn(payload); } catch {} }
      };

      // capture so we see it even if tg webview eats bubbling
      window.addEventListener("pointerdown", (e) => emit("down", e), { passive: true, capture: true });
      window.addEventListener("pointermove", (e) => emit("move", e), { passive: true, capture: true });
      window.addEventListener("pointerup",   (e) => emit("up", e),   { passive: true, capture: true });
      window.addEventListener("pointercancel",(e) => emit("cancel", e), { passive: true, capture: true });

      log("PointerRouter installed");
      return { on };
    }
  };

  window.BCO_INPUT = { GestureGuard, TapSynth, PointerRouter };
  console.log("[BCO_INPUT] loaded");
})();
