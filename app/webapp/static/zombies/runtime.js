// app/webapp/static/zombies/runtime.js
(() => {
  "use strict";

  // Contract:
  // - no UI redesign
  // - iOS clicks 100% (handled by bco.input.js + zombies/ui.js)
  // - fullscreen takeover hides TG chrome
  // - engine interface via window.BCO.engine (preferred) with compatibility fallback
  // - Arcade/Roguelike switch chooses mode; real differences live in CORE

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
    let pushToken = 0;

    const takeoverClass = FS.TAKEOVER_CLASS || "bco-game-takeover";
    const activeClass = FS.ACTIVE_CLASS || "bco-game-active";

    function lockScroll(on) {
      if (!(FS && FS.LOCK_BODY_SCROLL)) return;

      if (on) {
        savedY = window.scrollY || 0;

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

      // ALWAYS hide TG chrome for this app
      safe(() => wa.MainButton?.hide?.());
      safe(() => wa.BackButton?.hide?.());

      if (on) safe(() => wa.enableClosingConfirmation?.());
      else safe(() => wa.disableClosingConfirmation?.());

      safe(() => window.BCO_TG?.applyInsets?.());
    }

    function hideUI(on) {
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
      if (pushedState) return;
      pushedState = true;
      pushToken = Date.now();
      try {
        history.pushState({ bcoGame: true, token: pushToken }, "", location.href);
      } catch {}
    }

    function clearBackHandlerMarker() {
      if (!pushedState) return;
      pushedState = false;
      try {
        const st = history.state || {};
        if (st && st.bcoGame) {
          history.replaceState({ ...st, bcoGame: false }, "", location.href);
        }
      } catch {}
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
      clearBackHandlerMarker();

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

  // -------------------------
  // Engine compatibility layer
  // -------------------------
  function getEngine() {
    return window.BCO?.engine || window.BCO_ENGINE || window.BCO_ENGINE_ADAPTER || null;
  }

  function engineStart(engine, payload) {
    if (!engine) return false;

    const m = (payload.mode || "arcade");
    const mp = (payload.map || "Ashes");

    // 1) object signature start({mode,map})
    try {
      if (typeof engine.start === "function") {
        const r = engine.start({ mode: m, map: mp });
        if (typeof r === "boolean") return r;
        return true;
      }
    } catch {}

    // 2) adapter signature start(mode, opts)
    try {
      if (typeof engine.start === "function") {
        engine.start(m, { map: mp });
        return true;
      }
    } catch {}

    return false;
  }

  function engineStop(engine) {
    try { engine?.stop?.(); } catch {}
    return true;
  }

  function startGame() {
    const engine = getEngine();
    if (!engine) {
      console.warn("[Z_RUNTIME] engine missing");
      return false;
    }

    // ✅ вернуть mini app поведение: вход в fullscreen takeover
    Takeover.enter();

    const ok = engineStart(engine, {
      mode: (state.mode === "ROGUELIKE") ? "roguelike" : "arcade",
      map: state.map
    });

    // ✅ если старт не удался — ВОЗВРАЩАЕМ UI (не оставляем чёрный экран)
    if (!ok) {
      engineStop(engine);
      Takeover.exit();
      console.warn("[Z_RUNTIME] engine start failed -> rollback takeover");
      return false;
    }

    bus?.emit?.("zombies:started", { ...state });
    return true;
  }

  function stopGame() {
    const engine = getEngine();
    engineStop(engine);
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

    // Browser/back exits game ONLY if takeover is active.
    window.addEventListener("popstate", (e) => {
      if (Takeover.isActive()) {
        stopGame();
        return;
      }
      const st = e && e.state ? e.state : null;
      if (st && st.bcoGame) {
        try { history.replaceState({ ...st, bcoGame: false }, "", location.href); } catch {}
      }
    });

    document.addEventListener("visibilitychange", () => {
      if (!document.hidden && Takeover.isActive()) {
        safe(() => tg()?.MainButton?.hide?.());
        safe(() => tg()?.BackButton?.hide?.());
        safe(() => window.BCO_TG?.applyInsets?.());
      }
    });

    bus?.on?.("zombies:stop", () => {
      if (Takeover.isActive()) stopGame();
    });

    return true;
  }

  function init() {
    safe(() => window.BCO_GESTURE_GUARD?.installGestureGuard?.({
      takeoverClass: Takeover.takeoverClass,
      modalScrollSelector: ".bco-modal-scroll"
    }));

    setMode(state.mode);
    setMap(state.map);

    bind();
    return true;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }

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
