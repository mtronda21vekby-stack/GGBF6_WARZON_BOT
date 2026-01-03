// app/webapp/static/input/gesture-guard.js
(() => {
  "use strict";

  // Contract: NO UI redesign. Only interaction hardening.
  // Goal: iOS WebView stable clicks + no pinch/zoom + allow modal scrolling.

  const U = window.BCO_UTILS || {};
  const isIOS = (typeof U.isIOS === "function") ? U.isIOS : () => {
    const p = (navigator.platform || "").toLowerCase();
    const ua = (navigator.userAgent || "").toLowerCase();
    return /iphone|ipad|ipod/.test(ua) || (p.includes("mac") && "ontouchend" in document);
  };

  function safe(fn) { try { return fn(); } catch (_) { return undefined; } }

  function installGestureGuard(opts = {}) {
    const CFG = window.BCO_CONFIG || window.BCO?.CONFIG || {};
    const FS = CFG.FULLSCREEN || {};

    const preventPinch = opts.preventPinch ?? FS.PREVENT_PINCH ?? true;
    const preventDoubleTapZoom = opts.preventDoubleTapZoom ?? FS.PREVENT_DOUBLE_TAP_ZOOM ?? true;

    const takeoverClass = opts.takeoverClass ?? FS.TAKEOVER_CLASS ?? "bco-game-takeover";
    const modalScrollSel = opts.modalScrollSelector ?? ".bco-modal-scroll";

    // --- CSS hardening (NO visual change; only behavior) ---
    // IMPORTANT: do NOT set `touch-action:none` on "*", because it can kill click synthesis on iOS.
    // We scope it to takeover root and canvas only, and allow modal scroll areas.
    const id = "bco-gesture-guard";
    const old = document.getElementById(id);
    if (old) old.remove();

    const style = document.createElement("style");
    style.id = id;
    style.textContent = `
      html, body { overscroll-behavior: none; }
      body { -webkit-user-select:none; user-select:none; -webkit-touch-callout:none; }
      /* allow regular taps by default */
      body { touch-action: manipulation; }

      /* takeover: block page scrolling/gestures on the game surface */
      body.${takeoverClass} { touch-action: none; }

      /* allow vertical scroll inside modals */
      ${modalScrollSel}, ${modalScrollSel} * { touch-action: pan-y !important; -webkit-overflow-scrolling: touch; }

      /* if you have an overlay root, keep it tappable */
      #zOverlayMount { pointer-events: auto; }
      /* canvas itself is visual-only (input handled by overlay/joysticks), keep it non-blocking */
      #bcoZCanvas { pointer-events: none; }
    `;
    document.head.appendChild(style);

    // --- Pinch / gesture block (iOS) ---
    if (preventPinch) {
      document.addEventListener("gesturestart", (e) => e.preventDefault(), { passive: false });
      document.addEventListener("gesturechange", (e) => e.preventDefault(), { passive: false });
      document.addEventListener("gestureend", (e) => e.preventDefault(), { passive: false });
    }

    // --- Double-tap zoom block (iOS WebView) ---
    if (preventDoubleTapZoom && isIOS()) {
      let lastTouchEnd = 0;
      document.addEventListener("touchend", (e) => {
        const now = Date.now();
        if (now - lastTouchEnd <= 280) {
          // IMPORTANT: only block if NOT inside a scroll modal
          const t = e.target;
          if (t && t.closest && t.closest(modalScrollSel)) return;
          e.preventDefault();
        }
        lastTouchEnd = now;
      }, { passive: false });
    }

    // --- Prevent iOS rubber-band while takeover, BUT allow modal scroll ---
    document.addEventListener("touchmove", (e) => {
      if (!document.body.classList.contains(takeoverClass)) return;

      const t = e.target;
      if (t && t.closest && t.closest(modalScrollSel)) return; // allow modal scroll

      // Allow single-finger move if some module wants it? NO: takeover should own it.
      e.preventDefault();
    }, { passive: false });

    // --- Prevent multi-touch zoom anywhere during takeover (extra safety) ---
    document.addEventListener("touchstart", (e) => {
      if (!document.body.classList.contains(takeoverClass)) return;
      if (e.touches && e.touches.length > 1) e.preventDefault();
    }, { passive: false });

    safe(() => console.log("[BCO_GESTURE_GUARD] installed", { takeoverClass }));
    return true;
  }

  window.BCO_GESTURE_GUARD = { installGestureGuard };
})();
