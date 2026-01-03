// app/webapp/static/bco.input.js
(() => {
  "use strict";

  // ==========================================================
  // BCO INPUT (ELITE, SINGLE SOURCE)
  // - 100% iOS WebView tap reliability
  // - FastTap routing via [data-action]/[data-route]/[data-z]
  // - Allows modal scrolling (.bco-modal-scroll)
  // - Ghost-click killer ONLY for true ghosts (post FastTap)
  // - Backward compatible: window.BCO.input.mount()
  // - Extensible: window.BCO_POINTER_ROUTER.onAction(key, fn)
  // ==========================================================

  window.BCO = window.BCO || {};

  const ROOT_CFG = window.BCO.CONFIG || window.BCO_CONFIG || {};
  const INP = ROOT_CFG.INPUT || {};
  const FS = ROOT_CFG.FULLSCREEN || {};

  const TAP_MAX_MOVE_PX = INP.TAP_MAX_MOVE_PX ?? 12;
  const TAP_MAX_MS = INP.TAP_MAX_MS ?? 450;
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

    // Anything with action attributes should be considered interactive
    if (closestActionEl(target)) return true;

    const tag = (target.tagName || "").toLowerCase();
    if (tag === "button" || tag === "a" || tag === "input" || tag === "textarea") return true;

    // Role=button or inside a button
    if (target.getAttribute && target.getAttribute("role") === "button") return true;
    if (target.closest && target.closest("button,a,[role='button']")) return true;

    return false;
  }

  function extractPayload(el) {
    const action = el.getAttribute("data-action") || null;
    const route = el.getAttribute("data-route") || null;
    const z = el.getAttribute("data-z") || null;

    const payload = { action, route, z };

    const raw = el.getAttribute("data-payload");
    if (raw) {
      try {
        payload.payload = JSON.parse(raw);
      } catch {
        payload.payload = raw;
      }
    }
    return payload;
  }

  function makeKey(el) {
    const action = el.getAttribute("data-action");
    const route = el.getAttribute("data-route");
    const z = el.getAttribute("data-z");

    // Priority: action -> route -> z
    if (action) return String(action);
    if (route) return `route:${route}`;
    if (z) return `z:${z}`;
    return null;
  }

  // -------------------------
  // FastTap Pointer Router
  // -------------------------
  function createPointerRouter() {
    const handlers = new Map(); // key -> fn(payload, el, ev)

    // Ghost click tracking (ONLY block clicks that are ghosts)
    let lastFastTapAt = 0;
    let lastFastTapX = 0;
    let lastFastTapY = 0;
    const GHOST_WINDOW_MS = INP.GHOST_WINDOW_MS ?? 700;
    const GHOST_RADIUS_PX = INP.GHOST_RADIUS_PX ?? 36;

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

      // Allow native scroll inside modal scroll containers
      if (withinModalScroll(t)) return;

      // Only track taps on interactive stuff
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

      // If user ended inside a scroll modal, we do nothing (native scroll wins)
      if (withinModalScroll(t)) {
        active = null;
        return;
      }

      if (!okTap) {
        active = null;
        return;
      }

      // Find action element (prefer current target; fallback to initial)
      const actionEl = closestActionEl(t) || closestActionEl(active.target);

      // If no action element, we let native click happen (important!)
      if (!actionEl) {
        active = null;
        return;
      }

      // We handled it as FastTap -> prevent native click chain
      safe(() => ev.preventDefault());
      safe(() => ev.stopPropagation());

      // Mark fast tap for ghost click filter
      const pt = (ev.changedTouches && ev.changedTouches[0]) ? ev.changedTouches[0] : ev;
      lastFastTapAt = nowMs();
      lastFastTapX = pt.clientX || active.x0 || 0;
      lastFastTapY = pt.clientY || active.y0 || 0;

      // Invoke handler if registered; otherwise allow fallback onclick by manual click
      const handled = invoke(actionEl, ev);

      if (!handled) {
        // Fallback: trigger element's native click if no handler registered
        // (keeps old inline onclick working)
        safe(() => actionEl.click());
      }

      active = null;
    }

    function onCancel() {
      if (active) active.canceled = true;
      active = null;
    }

    function isGhostClick(e) {
      const t = nowMs();
      if (!lastFastTapAt) return false;
      if ((t - lastFastTapAt) > GHOST_WINDOW_MS) return false;

      const x = e.clientX || 0;
      const y = e.clientY || 0;
      const dx = x - lastFastTapX;
      const dy = y - lastFastTapY;
      const dist = Math.sqrt(dx * dx + dy * dy);

      return dist <= GHOST_RADIUS_PX;
    }

    function mount() {
      // Pointer events (primary)
      document.addEventListener("pointerdown", onDown, { capture: CAPTURE, passive: false });
      document.addEventListener("pointermove", onMove, { capture: CAPTURE, passive: false });
      document.addEventListener("pointerup", onUp, { capture: CAPTURE, passive: false });
      document.addEventListener("pointercancel", onCancel, { capture: CAPTURE, passive: false });

      // Touch fallback (some iOS WebViews still weird)
      document.addEventListener("touchstart", onDown, { capture: CAPTURE, passive: false });
      document.addEventListener("touchmove", onMove, { capture: CAPTURE, passive: false });
      document.addEventListener("touchend", onUp, { capture: CAPTURE, passive: false });
      document.addEventListener("touchcancel", onCancel, { capture: CAPTURE, passive: false });

      // Ghost click killer — NOT global “kill all clicks”.
      // Only block clicks that are very likely ghost clicks right after a FastTap.
      document.addEventListener("click", (e) => {
        // always allow clicks inside modal scroll
        if (withinModalScroll(e.target)) return;

        // In takeover we still allow genuine mouse clicks; we only block ghosts.
        const takeover = document.body.classList.contains(TAKEOVER_CLASS);
        if (!takeover) {
          // outside takeover: only block true ghost
          if (!isGhostClick(e)) return;
        } else {
          // takeover: also only block true ghost (DO NOT nuke real clicks)
          if (!isGhostClick(e)) return;
        }

        e.preventDefault();
        e.stopPropagation();
      }, { capture: true, passive: false });

      safe(() => console.log("[BCO_INPUT] mounted", { TAP_MAX_MOVE_PX, TAP_MAX_MS, CAPTURE }));
      return true;
    }

    return { mount, onAction };
  }

  // Create single router instance
  const router = createPointerRouter();

  // Public API (backward compatible)
  window.BCO_POINTER_ROUTER = router;
  window.BCO.input = {
    mount: router.mount,
    onAction: router.onAction
  };
})();
