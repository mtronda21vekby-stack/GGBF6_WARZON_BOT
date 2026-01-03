// app/webapp/static/zombies/ui.js
(() => {
  "use strict";

  window.BCO = window.BCO || {};
  const bus = window.BCO.bus;

  // We do NOT redesign UI. We only mark scrollable dialog containers for iOS.
  function markModalScroll() {
    const nodes = Array.from(document.querySelectorAll(
      ".modal, .modal-content, [role='dialog'], [data-modal], [data-popup]"
    ));
    for (const el of nodes) {
      const cs = window.getComputedStyle(el);
      const oy = cs.overflowY;
      if (oy === "auto" || oy === "scroll") {
        el.classList.add("bco-modal-scroll");
        el.style.webkitOverflowScrolling = "touch";
      }
    }
  }

  // During takeover we prevent touchmove globally except .bco-modal-scroll
  function installTakeoverTouchGuard() {
    document.addEventListener("touchmove", (e) => {
      const takeover = document.body.classList.contains("bco-game-takeover");
      if (!takeover) return;
      const t = e.target;
      if (t && t.closest && t.closest(".bco-modal-scroll")) return;
      e.preventDefault();
    }, { passive: false, capture: true });
  }

  function loopMark() {
    let n = 0;
    const tick = () => {
      n++;
      if (n < 180) markModalScroll(); // first ~3 seconds worth of frames
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  installTakeoverTouchGuard();
  loopMark();

  bus?.on?.("zombies:takeover", () => markModalScroll());
})();
