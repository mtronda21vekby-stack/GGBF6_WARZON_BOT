// app/webapp/static/zombies/runtime.js
(() => {
  "use strict";

  // Contract:
  // - no UI redesign
  // - iOS clicks 100% (handled by bco.input.js + zombies/ui.js)
  // - fullscreen takeover hides TG chrome (BUT NOT AUTO)
  // - engine interface via window.BCO.engine
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
  // Takeover controller (READY, but NOT auto-used)
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
        header && (header.style.display = "none");
        nav && (nav.style.display = "none");
        main && (main.style.display = "none");
        foot && (foot.style.display = "none");
      } else {
        header && (header.style.display = "");
        nav && (nav.style.display = "");
        main && (main.style.display = "");
        foot && (foot.style.display = "");
      }
    }

    function enter() {
      document.body.classList.add(takeoverClass, activeClass);
      lockScroll(true);
      hideTG(true);
      hideUI(true);
      if (!pushedState) {
        pushedState = true;
        try { history.pushState({ bcoGame: true }, "", location.href); } catch {}
      }
      bus?.emit?.("zombies:takeover", { on: true });
    }

    function exit() {
      document.body.classList.remove(takeoverClass, activeClass);
      hideUI(false);
      hideTG(false);
      lockScroll(false);
      pushedState = false;
      bus?.emit?.("zombies:takeover", { on: false });
    }

    function isActive() {
      return document.body.classList.contains(takeoverClass);
    }

    return { enter, exit, isActive, takeoverClass };
  })();

  // -------------------------
  // Runtime state
  // -------------------------
  const state = {
    mode: "ARCADE",
    map: "Ashes"
  };

  function setMode(m) {
    state.mode = String(m).toUpperCase().includes("ROGUE") ? "ROGUELIKE" : "ARCADE";

    qs("btnZModeArcade")?.classList.toggle("active", state.mode === "ARCADE");
    qs("btnZModeRogue")?.classList.toggle("active", state.mode === "ROGUELIKE");
    qs("btnZModeArcade2")?.classList.toggle("active", state.mode === "ARCADE");
    qs("btnZModeRogue2")?.classList.toggle("active", state.mode === "ROGUELIKE");

    bus?.emit?.("zombies:mode", { mode: state.mode });
  }

  function setMap(mp) {
    state.map = (String(mp) === "Astra") ? "Astra" : "Ashes";
    const seg = qs("segZMap");
    seg && Array.from(seg.querySelectorAll(".seg-btn"))
      .forEach(b => b.classList.toggle("active", b.getAttribute("data-value") === state.map));
    bus?.emit?.("zombies:map", { map: state.map });
  }

  function getEngine() {
    return window.BCO?.engine || window.BCO_ENGINE || null;
  }

  function startGame() {
    const engine = getEngine();
    if (!engine) {
      console.warn("[Z_RUNTIME] engine missing");
      return false;
    }

    // ❗ IMPORTANT:
    // ❌ NO Takeover.enter() here
    // Canvas/game starts INSIDE UI until overlay is ready

    const ok = engine.start({
      mode: state.mode === "ROGUELIKE" ? "roguelike" : "arcade",
      map: state.map
    });

    if (!ok) {
      console.warn("[Z_RUNTIME] engine start failed");
      return false;
    }

    bus?.emit?.("zombies:started", { ...state });
    return true;
  }

  function stopGame() {
    const engine = getEngine();
    safe(() => engine?.stop?.());
    if (Takeover.isActive()) Takeover.exit();
    bus?.emit?.("zombies:stopped", {});
    return true;
  }

  // -------------------------
  // Bind UI
  // -------------------------
  let bound = false;
  function bind() {
    if (bound) return;
    bound = true;

    qs("btnZEnterGame")?.addEventListener("click", startGame, { passive: true });
    qs("btnZQuickPlay")?.addEventListener("click", startGame, { passive: true });

    qs("btnZModeArcade")?.addEventListener("click", () => setMode("ARCADE"), { passive: true });
    qs("btnZModeRogue")?.addEventListener("click", () => setMode("ROGUELIKE"), { passive: true });
    qs("btnZModeArcade2")?.addEventListener("click", () => setMode("ARCADE"), { passive: true });
    qs("btnZModeRogue2")?.addEventListener("click", () => setMode("ROGUELIKE"), { passive: true });

    qs("segZMap")?.addEventListener("click", (e) => {
      const b = e.target.closest(".seg-btn");
      b && setMap(b.getAttribute("data-value"));
    }, { passive: true });

    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape") stopGame();
    });
  }

  function init() {
    setMode(state.mode);
    setMap(state.map);
    bind();
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
