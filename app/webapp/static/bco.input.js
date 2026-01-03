// app/webapp/static/bco.input.js
(() => {
  "use strict";

  // ==========================================================
  // BCO INPUT (SAFE MODE)
  // - iOS WebView tap reliability
  // - DOES NOT kill native click handlers
  // - Only prevents default when element has [data-action|data-route|data-z]
  // - Allows modal scrolling (.bco-modal-scroll)
  // - Backward compatible: window.BCO.input.mount()
  // ==========================================================

  window.BCO = window.BCO || {};

  const ROOT_CFG = window.BCO.CONFIG || window.BCO_CONFIG || {};
  const INP = ROOT_CFG.INPUT || {};
  const FS = ROOT_CFG.FULLSCREEN || {};

  const TAP_MAX_MOVE_PX = INP.TAP_MAX_MOVE_PX ?? 14;
  const TAP_MAX_MS = INP.TAP_MAX_MS ?? 520;
  const CAPTURE = INP.CAPTURE ?? true;

  const TAKEOVER_CLASS = FS.TAKEOVER_CLASS || "bco-game-takeover";
  const MODAL_SCROLL_SEL = ".bco-modal-scroll";

  function nowMs() {
    try {
      const U = window.BCO_UTILS;
      if (U && typeof U.nowMs === "function") return U.nowMs();
    } catch {}
    return Date.now();
  }

  function safe(fn) { try { return fn(); } catch (_) { return undefined; } }

  function withinModalScroll(target) {
    return !!(target && target.closest && target.closest(MODAL_SCROLL_SEL));
  }

  function closestActionEl(el) {
    if (!el || !el.closest) return null;
    return el.closest("[data-action],[data-route],[data-z]");
  }

  function isInteractive(target) {
    if (!target) return false;

    const tag = (target.tagName || "").toLowerCase();
    if (tag === "button" || tag === "a" || tag === "input" || tag === "textarea") return true;

    if (target.getAttribute && target.getAttribute("role") === "button") return true;
    if (target.closest && target.closest("button,a,[role='button']")) return true;

    // Elements with explicit routing attrs are interactive too
    if (closestActionEl(target)) return true;

    return false;
  }

  function extractPayload(el) {
    const action = el.getAttribute("data-action") || null;
    const route = el.getAttribute("data-route") || null;
    const z = el.getAttribute("data-z") || null;

    const payload = { action, route, z };

    const raw = el.getAttribute("data-payload");
    if (raw) {
      try { payload.payload = JSON.parse(raw); }
      catch { payload.payload = raw; }
    }
    return payload;
  }

  function makeKey(el) {
    const action = el.getAttribute("data-action");
    const route = el.getAttribute("data-route");
    const z = el.getAttribute("data-z");
    if (action) return String(action);
    if (route) return `route:${route}`;
    if (z) return `z:${z}`;
    return null;
  }

  function createPointerRouter() {
    const handlers = new Map(); // key -> fn(payload, el, ev)
    let active = null; // {t0,x0,y0,moved,target,canceled}

    function onAction(key, fn) {
      handlers.set(String(key), fn);
      return () => handlers.delete(String(key));
    }

    function invoke(el, ev) {
      const key = makeKey(el);
      if (key && handlers.has(key)) {
        const payload = extractPayload(el);
        handlers.get(key)(payload, el, ev);
        return true;
      }
      return false;
    }

    function onDown(ev) {
      const t = ev.target;

      // allow native scroll inside modal scroll containers
      if (withinModalScroll(t)) return;

      // only track taps on interactive stuff
      if (!isInteractive(t)) return;

      const pt = (ev.touches && ev.touches[0]) ? ev.touches[0] : ev;

      active = {
        t0: nowMs(),
        x0: pt.clientX || 0,
        y0: pt.clientY || 0,
        moved: false,
        target: t,
        canceled: false
      };
    }

    function onMove(ev) {
      if (!active || active.canceled) return;

      const pt = (ev.touches && ev.touches[0]) ? ev.touches[0] : ev;
      const x = pt.clientX || 0;
      const y = pt.clientY || 0;

      const dx = x - active.x0;
      const dy = y - active.y0;
      const dist = Math.sqrt(dx * dx + dy * dy);

      if (dist > TAP_MAX_MOVE_PX) active.moved = true;
    }

    function onUp(ev) {
      if (!active || active.canceled) return;

      const dt = nowMs() - active.t0;
      const okTap = (dt <= TAP_MAX_MS) && !active.moved;

      const t = ev.target || active.target;

      if (withinModalScroll(t)) { active = null; return; }
      if (!okTap) { active = null; return; }

      // IMPORTANT:
      // We only "FastTap-handle" elements that have [data-action|data-route|data-z].
      // For normal buttons (id-based handlers), we DO NOT preventDefault (native click must work).
      const actionEl = closestActionEl(t) || closestActionEl(active.target);
      if (!actionEl) {
        active = null;
        return;
      }

      safe(() => ev.preventDefault());
      safe(() => ev.stopPropagation());

      const handled = invoke(actionEl, ev);
      if (!handled) safe(() => actionEl.click());

      active = null;
    }

    function onCancel() {
      if (active) active.canceled = true;
      active = null;
    }

    function mount() {
      document.addEventListener("pointerdown", onDown, { capture: CAPTURE, passive: false });
      document.addEventListener("pointermove", onMove, { capture: CAPTURE, passive: false });
      document.addEventListener("pointerup", onUp, { capture: CAPTURE, passive: false });
      document.addEventListener("pointercancel", onCancel, { capture: CAPTURE, passive: false });

      // touch fallback
      document.addEventListener("touchstart", onDown, { capture: CAPTURE, passive: false });
      document.addEventListener("touchmove", onMove, { capture: CAPTURE, passive: false });
      document.addEventListener("touchend", onUp, { capture: CAPTURE, passive: false });
      document.addEventListener("touchcancel", onCancel, { capture: CAPTURE, passive: false });

      safe(() => console.log("[BCO_INPUT] mounted SAFE", { TAP_MAX_MOVE_PX, TAP_MAX_MS, CAPTURE, TAKEOVER_CLASS }));
      return true;
    }

    return { mount, onAction };
  }

  const router = createPointerRouter();

  window.BCO_POINTER_ROUTER = router;
  window.BCO.input = {
    mount: router.mount,
    onAction: router.onAction
  };
})();
