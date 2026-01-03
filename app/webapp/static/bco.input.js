// app/webapp/static/bco.input.js
(() => {
  "use strict";

  window.BCO = window.BCO || {};
  const CFG = window.BCO.CONFIG || {};
  const IC = CFG.INPUT || { TAP_MAX_MOVE_PX: 12, TAP_MAX_MS: 450, CAPTURE: true };

  function withinModalScroll(target) {
    return !!(target && target.closest && target.closest(".bco-modal-scroll"));
  }

  function isInteractive(target) {
    if (!target) return false;
    const tag = (target.tagName || "").toLowerCase();
    if (tag === "button" || tag === "a" || tag === "input" || tag === "textarea") return true;
    return !!(target.closest && target.closest("button,a,[role='button']"));
  }

  let active = null;

  function onDown(ev) {
    const t = ev.target;
    if (!isInteractive(t)) return;
    if (withinModalScroll(t)) return;

    const pt = ev.touches && ev.touches[0] ? ev.touches[0] : ev;
    active = {
      t0: Date.now(),
      x0: pt.clientX || 0,
      y0: pt.clientY || 0,
      moved: false,
      canceled: false
    };
  }

  function onMove(ev) {
    if (!active || active.canceled) return;
    const pt = ev.touches && ev.touches[0] ? ev.touches[0] : ev;
    const dx = (pt.clientX || 0) - active.x0;
    const dy = (pt.clientY || 0) - active.y0;
    const d = Math.hypot(dx, dy);
    if (d > (IC.TAP_MAX_MOVE_PX || 12)) active.moved = true;
  }

  function onUp(ev) {
    if (!active || active.canceled) return;
    const dt = Date.now() - active.t0;
    const okTap = (dt <= (IC.TAP_MAX_MS || 450)) && !active.moved;

    // During takeover: kill ghost clicks except modal scroll areas
    const takeover = document.body.classList.contains((CFG.FULLSCREEN && CFG.FULLSCREEN.TAKEOVER_CLASS) || "bco-game-takeover");
    const t = ev.target;

    if (takeover && okTap && !withinModalScroll(t)) {
      try { ev.preventDefault(); } catch {}
      try { ev.stopPropagation(); } catch {}
    }

    active = null;
  }

  function onCancel() { active = null; }

  function mount() {
    const cap = !!IC.CAPTURE;

    document.addEventListener("pointerdown", onDown, { capture: cap, passive: false });
    document.addEventListener("pointermove", onMove, { capture: cap, passive: false });
    document.addEventListener("pointerup", onUp, { capture: cap, passive: false });
    document.addEventListener("pointercancel", onCancel, { capture: cap, passive: false });

    document.addEventListener("touchstart", onDown, { capture: cap, passive: false });
    document.addEventListener("touchmove", onMove, { capture: cap, passive: false });
    document.addEventListener("touchend", onUp, { capture: cap, passive: false });
    document.addEventListener("touchcancel", onCancel, { capture: cap, passive: false });

    // ghost click killer only in takeover
    document.addEventListener("click", (e) => {
      const takeover = document.body.classList.contains((CFG.FULLSCREEN && CFG.FULLSCREEN.TAKEOVER_CLASS) || "bco-game-takeover");
      if (!takeover) return;
      if (withinModalScroll(e.target)) return;
      e.preventDefault();
      e.stopPropagation();
    }, { capture: true, passive: false });
  }

  window.BCO.input = { mount };
})();
