(() => {
  "use strict";

  const { nowMs, clamp } = window.BCO_UTILS;

  /**
   * PointerRouter: 100% reliable taps in iOS WebView.
   * - Captures pointer/touch at document level
   * - Generates "fast tap" (no 300ms delay)
   * - Prevents ghost clicks
   * - Allows scroll in modal containers (.bco-modal-scroll)
   * - Delegation: uses [data-action] / [data-route] attributes OR falls back to onclick
   */
  function createPointerRouter() {
    const cfg = window.BCO_CONFIG?.INPUT || {};
    const TAP_MAX_MOVE_PX = cfg.TAP_MAX_MOVE_PX ?? 12;
    const TAP_MAX_MS = cfg.TAP_MAX_MS ?? 450;
    const CAPTURE = cfg.CAPTURE ?? true;

    const handlers = new Map(); // action -> fn(payload, el, event)

    let active = null; // {id, t0, x0, y0, moved, target, canceled}

    function onAction(action, fn) {
      handlers.set(String(action), fn);
      return () => handlers.delete(String(action));
    }

    function _closestActionEl(el) {
      if (!el || !el.closest) return null;
      return el.closest("[data-action],[data-route],[data-z]");
    }

    function _extractPayload(el) {
      // No UI redesign: just read attributes if present
      const action = el.getAttribute("data-action") || null;
      const route = el.getAttribute("data-route") || null;
      const z = el.getAttribute("data-z") || null;

      const payload = { action, route, z };

      // Optional JSON payload
      const raw = el.getAttribute("data-payload");
      if (raw) {
        try {
          const obj = JSON.parse(raw);
          payload.payload = obj;
        } catch {
          payload.payload = raw;
        }
      }
      return payload;
    }

    function _invoke(el, ev) {
      const action = el.getAttribute("data-action");
      const route = el.getAttribute("data-route");
      const z = el.getAttribute("data-z");

      const payload = _extractPayload(el);

      // Priority: data-action -> data-route -> data-z
      const key = action || (route ? `route:${route}` : null) || (z ? `z:${z}` : null);

      if (key && handlers.has(key)) {
        handlers.get(key)(payload, el, ev);
        return true;
      }

      // Fallback: if element has onclick, let it run
      return false;
    }

    function _isInteractive(el) {
      if (!el) return false;
      const tag = (el.tagName || "").toLowerCase();
      if (tag === "button" || tag === "a" || tag === "input") return true;
      if (el.getAttribute && (el.getAttribute("role") === "button")) return true;
      if (el.closest && el.closest("button,a,[role='button']")) return true;
      return !!_closestActionEl(el);
    }

    function _withinScrollAllowed(target) {
      return !!(target && target.closest && target.closest(".bco-modal-scroll"));
    }

    function _onDown(ev) {
      const target = ev.target;
      if (_withinScrollAllowed(target)) return; // allow native scroll
      if (!_isInteractive(target)) return;

      active = {
        id: ev.pointerId || "touch",
        t0: nowMs(),
        x0: ev.clientX || (ev.touches && ev.touches[0] && ev.touches[0].clientX) || 0,
        y0: ev.clientY || (ev.touches && ev.touches[0] && ev.touches[0].clientY) || 0,
        moved: false,
        target: target,
        canceled: false,
      };
    }

    function _onMove(ev) {
      if (!active || active.canceled) return;
      const x = ev.clientX || (ev.touches && ev.touches[0] && ev.touches[0].clientX) || 0;
      const y = ev.clientY || (ev.touches && ev.touches[0] && ev.touches[0].clientY) || 0;
      const dx = x - active.x0;
      const dy = y - active.y0;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist > TAP_MAX_MOVE_PX) active.moved = true;
    }

    function _onUp(ev) {
      if (!active || active.canceled) return;

      const dt = nowMs() - active.t0;
      const okTime = dt <= TAP_MAX_MS;
      const okMove = !active.moved;

      const target = ev.target || active.target;
      const actionEl = _closestActionEl(target) || _closestActionEl(active.target);

      // If user is scrolling inside modal scroll, do nothing
      if (_withinScrollAllowed(target)) {
        active = null;
        return;
      }

      if (okTime && okMove && actionEl) {
        // stop ghost clicks
        if (ev.preventDefault) ev.preventDefault();
        if (ev.stopPropagation) ev.stopPropagation();

        _invoke(actionEl, ev);
      }

      active = null;
    }

    function _onCancel() {
      if (active) active.canceled = true;
      active = null;
    }

    function mount() {
      // Pointer events first
      document.addEventListener("pointerdown", _onDown, { capture: CAPTURE, passive: false });
      document.addEventListener("pointermove", _onMove, { capture: CAPTURE, passive: false });
      document.addEventListener("pointerup", _onUp, { capture: CAPTURE, passive: false });
      document.addEventListener("pointercancel", _onCancel, { capture: CAPTURE, passive: false });

      // Touch fallback (older iOS WebView cases)
      document.addEventListener("touchstart", _onDown, { capture: CAPTURE, passive: false });
      document.addEventListener("touchmove", _onMove, { capture: CAPTURE, passive: false });
      document.addEventListener("touchend", _onUp, { capture: CAPTURE, passive: false });
      document.addEventListener("touchcancel", _onCancel, { capture: CAPTURE, passive: false });

      // Kill ghost click after our fast tap
      document.addEventListener("click", (e) => {
        if (document.body.classList.contains("bco-game-takeover")) {
          // in takeover we prefer our router; block clicks unless inside modal scroll
          if (!_withinScrollAllowed(e.target)) {
            e.preventDefault();
            e.stopPropagation();
          }
        }
      }, { capture: true, passive: false });
    }

    return { mount, onAction };
  }

  window.BCO_POINTER_ROUTER = createPointerRouter();
})();
