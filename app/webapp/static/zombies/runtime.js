// app/webapp/static/zombies/runtime.js
(() => {
  "use strict";

  // Contract:
  // - no UI redesign
  // - iOS clicks 100%
  // - fullscreen takeover hides TG chrome
  // - engine interface via window.BCO.engine (single source)
  // - Arcade/Roguelike mode switch (real differences live in CORE, runtime only selects)

  window.BCO = window.BCO || {};
  window.BCO.zombies = window.BCO.zombies || {};

  const CFG = window.BCO.CONFIG || window.BCO_CONFIG || {};
  const FS = CFG.FULLSCREEN || {};

  const bus = window.BCO.bus || window.BCO_BUS || window.BCO_EVENTBUS || null;

  function safe(fn) { try { return fn(); } catch (_) { return undefined; } }
  function qs(id) { return document.getElementById(id); }

  function tg() { return (window.Telegram && Telegram.WebApp) ? Telegram.WebApp : null; }

  // -------------------------
  // Takeover controller (elite & reversible)
  // -------------------------
  const Takeover = (() => {
    let savedY = 0;
    let pushedState = false;

    const takeoverClass = FS.TAKEOVER_CLASS || "bco-game-takeover";
    const activeClass = FS.ACTIVE_CLASS || "bco-game-active";

    function lockScroll(on) {
      if (!(FS && FS.LOCK_BODY_SCROLL)) return;

      if (on) {
        savedY = window.scrollY || 0;

        // fixed body lock (iOS safe)
        document.body.style.position = "fixed";
        document.body.style.top = `-${savedY}px`;
        document.body.style.left = "0";
        document.body.style.right = "0";
        document.body.style.width = "100%";
      } else {
        document.body.style.position = "";
        document.body.style.top = "";
        document.body.style.left = "";
        document.body.style.right = "";
        document.body.style.width = "";
        window.scrollTo(0, savedY);
      }
    }

    function hideTG(on) {
      const wa = tg();
      if (!wa) return;

      safe(() => wa.ready());
      safe(() => wa.expand());

      if (on) {
        safe(() => wa.MainButton?.hide?.());
        safe(() => wa.BackButton?.hide?.());
        safe(() => wa.enableClosingConfirmation?.());
      } else {
        // we still keep TG chrome minimal by default (as in your index.html)
        safe(() => wa.MainButton?.hide?.());
        safe(() => wa.BackButton?.hide?.());
        safe(() => wa.disableClosingConfirmation?.());
      }

      // apply insets if helper exists
      safe(() => window.BCO_TG?.applyInsets?.());
    }

    function hideUI(on) {
      // No redesign: just hide/show existing layout containers.
      const header = document.querySelector("header.app-header");
      const nav = document.querySelector("nav.bottom-nav");
      const main = document.querySelector("main.app-main");
      const foot = document.querySelector("footer.foot");

      if (on) {
        if (header) header.style.display = "none";
        if (nav) nav.style.display = "none";
        if (foot) foot.style.display = "none";
        if (main) main.style.display = "none";
      } else {
        if (header) header.style.display = "";
        if (nav) nav.style.display = "";
        if (foot) foot.style.display = "";
        if (main) main.style.display = "";
      }
    }

    function pushBackHandler() {
      // Elite iOS/Android: make “Back” exit game even if TG hides BackButton.
      if (pushedState) return;
      pushedState = true;
      try {
        history.pushState({ bcoGame: true }, "", location.href);
      } catch {}
    }

    function popBackHandler() {
      if (!pushedState) return;
      pushedState = false;
      // Pop happens automatically by user; nothing to undo.
    }

    function enter() {
      document.body.classList.add(takeoverClass);
      document.body.classList.add(activeClass);

      lockScroll(true);
      hideTG(true);
      hideUI(true);
      pushBackHandler();

      bus?.emit?.("zombies:takeover", { on: true });
    }

    function exit() {
      document.body.classList.remove(takeoverClass);
      document.body.classList.remove(activeClass);

      hideUI(false);
      hideTG(false);
      lockScroll(false);
      popBackHandler();

      bus?.emit?.("zombies:takeover", { on: false });
    }

    function isActive() {
      return document.body.classList.contains(takeoverClass);
    }

    return { enter, exit, isActive, takeoverClass };
  })();

  // -------------------------
  // Runtime launcher state
  // -------------------------
  const state = {
    mode: "ARCADE",   // ARCADE | ROGUELIKE
    map: "Ashes"      // Ashes | Astra
  };

  function setMode(m) {
    state.mode = (String(m).toUpperCase().includes("ROGUE")) ? "ROGUELIKE" : "ARCADE";

    // sync both mode button pairs (NO redesign)
    const a1 = qs("btnZModeArcade");
    const r1 = qs("btnZModeRogue");
    const a2 = qs("btnZModeArcade2");
    const r2 = qs("btnZModeRogue2");

    if (a1) a1.classList.toggle("active", state.mode === "ARCADE");
    if (r1) r1.classList.toggle("active", state.mode === "ROGUELIKE");
    if (a2) a2.classList.toggle("active", state.mode === "ARCADE");
    if (r2) r2.classList.toggle("active", state.mode === "ROGUELIKE");

    bus?.emit?.("zombies:mode", { mode: state.mode });
  }

  function setMap(mp) {
    state.map = (String(mp) === "Astra") ? "Astra" : "Ashes";

    const seg = qs("segZMap");
    if (seg) {
      const btns = Array.from(seg.querySelectorAll(".seg-btn"));
      for (const b of btns) b.classList.toggle("active", b.getAttribute("data-value") === state.map);
    }

    bus?.emit?.("zombies:map", { map: state.map });
  }

  function startGame() {
    const engine = window.BCO.engine || window.BCO_ENGINE || null;
    if (!engine || typeof engine.start !== "function") {
      console.warn("[Z_RUNTIME] engine missing");
      return false;
    }

    Takeover.enter();

    const ok = engine.start({
      mode: (state.mode === "ROGUELIKE") ? "roguelike" : "arcade",
      map: state.map
    });

    if (!ok) {
      Takeover.exit();
      console.warn("[Z_RUNTIME] engine start failed");
      return false;
    }

    bus?.emit?.("zombies:started", { ...state });
    return true;
  }

  function stopGame() {
    const engine = window.BCO.engine || window.BCO_ENGINE || null;
    safe(() => engine?.stop?.());
    Takeover.exit();
    bus?.emit?.("zombies:stopped", {});
    return true;
  }

  // -------------------------
  // Bind UI (NO redesign)
  // -------------------------
  let _bound = false;
  function bind() {
    if (_bound) return true;
    _bound = true;

    qs("btnZModeArcade")?.addEventListener("click", () => setMode("ARCADE"), { passive: true });
    qs("btnZModeRogue")?.addEventListener("click", () => setMode("ROGUELIKE"), { passive: true });
    qs("btnZModeArcade2")?.addEventListener("click", () => setMode("ARCADE"), { passive: true });
    qs("btnZModeRogue2")?.addEventListener("click", () => setMode("ROGUELIKE"), { passive: true });

    qs("btnZEnterGame")?.addEventListener("click", startGame, { passive: true });
    qs("btnZQuickPlay")?.addEventListener("click", startGame, { passive: true });

    const seg = qs("segZMap");
    if (seg) {
      seg.addEventListener("click", (e) => {
        const b = e.target && e.target.closest ? e.target.closest(".seg-btn") : null;
        if (!b) return;
        setMap(b.getAttribute("data-value"));
      }, { passive: true });
    }

    // ESC exits
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape") stopGame();
    });

    // Browser back exits (history pushState in takeover)
    window.addEventListener("popstate", () => {
      if (Takeover.isActive()) stopGame();
    });

    // If app becomes visible again during takeover, re-hide TG chrome
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden && Takeover.isActive()) {
        safe(() => tg()?.MainButton?.hide?.());
        safe(() => tg()?.BackButton?.hide?.());
        safe(() => window.BCO_TG?.applyInsets?.());
      }
    });

    return true;
  }

  function init() {
    // install gesture guard (if module exists) — safe call
    safe(() => window.BCO_GESTURE_GUARD?.installGestureGuard?.({
      takeoverClass: Takeover.takeoverClass,
      modalScrollSelector: ".bco-modal-scroll"
    }));

    // default state
    setMode(state.mode);
    setMap(state.map);

    bind();
    return true;
  }

  // Expose runtime API (stable)
  window.BCO.zombies.runtime = {
    init,
    bind,
    startGame,
    stopGame,
    setMode,
    setMap,
    getState: () => ({ ...state }),
    takeover: Takeover
  };
})();
