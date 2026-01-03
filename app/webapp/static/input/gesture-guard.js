(() => {
  "use strict";

  const { isIOS } = window.BCO_UTILS;

  function installGestureGuard(opts = {}) {
    const cfg = window.BCO_CONFIG?.FULLSCREEN || {};
    const preventPinch = opts.preventPinch ?? cfg.PREVENT_PINCH ?? true;
    const preventDoubleTapZoom = opts.preventDoubleTapZoom ?? cfg.PREVENT_DOUBLE_TAP_ZOOM ?? true;

    // CSS hardening (no visual redesign; purely interaction)
    const style = document.createElement("style");
    style.id = "bco-gesture-guard";
    style.textContent = `
      html, body { overscroll-behavior: none; }
      body { -webkit-user-select: none; user-select: none; -webkit-touch-callout: none; }
      .bco-game-takeover, .bco-game-takeover * { touch-action: none; }
      .bco-modal-scroll, .bco-modal-scroll * { touch-action: pan-y; }
    `;
    document.head.appendChild(style);

    // iOS: block pinch / gesture
    if (preventPinch) {
      document.addEventListener("gesturestart", (e) => e.preventDefault(), { passive: false });
      document.addEventListener("gesturechange", (e) => e.preventDefault(), { passive: false });
      document.addEventListener("gestureend", (e) => e.preventDefault(), { passive: false });
    }

    // Double-tap zoom prevention (iOS Safari/WebView)
    if (preventDoubleTapZoom && isIOS()) {
      let lastTouchEnd = 0;
      document.addEventListener("touchend", (e) => {
        const now = Date.now();
        if (now - lastTouchEnd <= 280) {
          e.preventDefault();
        }
        lastTouchEnd = now;
      }, { passive: false });
    }

    // Prevent iOS rubber-band in takeover
    document.addEventListener("touchmove", (e) => {
      const target = e.target;
      // allow scroll inside modal scroll containers
      if (target && target.closest && target.closest(".bco-modal-scroll")) return;
      // if game takeover active -> prevent
      if (document.body.classList.contains("bco-game-takeover")) {
        e.preventDefault();
      }
    }, { passive: false });
  }

  window.BCO_GESTURE_GUARD = { installGestureGuard };
})();
