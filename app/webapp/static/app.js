// app/webapp/static/app.js
// BCO App Entry (uses YOUR existing modules) vNEXT-ENTRY-1
(() => {
  "use strict";

  const log = (...a) => console.log("[BCO_APP]", ...a);
  const warn = (...a) => console.warn("[BCO_APP]", ...a);
  const err = (...a) => console.error("[BCO_APP]", ...a);

  function safe(fn) { try { return fn(); } catch (e) { return undefined; } }

  function q(id) { return document.getElementById(id); }

  function setHealth(msg) {
    const el = q("jsHealth");
    if (el) el.textContent = msg;
  }

  // --- Detect your modules (supports BOTH naming styles you already have) ---
  function detect() {
    // input
    const input =
      window.BCO_INPUT ||
      window.BCO?.input ||
      window.BCOInput ||
      window.BCO?.INPUT ||
      null;

    // engine adapter
    const engine =
      window.BCO_ENGINE ||
      window.BCO?.engine ||
      window.BCOEngine ||
      window.BCO?.ENGINE ||
      null;

    // zombies runtime/ui/economy
    const zRuntime =
      window.BCO_ZOMBIES_RUNTIME ||
      window.BCO?.zombies?.runtime ||
      window.ZombiesRuntime ||
      null;

    const zUI =
      window.BCO_ZOMBIES_UI ||
      window.BCO?.zombies?.ui ||
      window.ZombiesUI ||
      null;

    const zEcon =
      window.BCO_ZOMBIES_ECONOMY ||
      window.BCO?.zombies?.economy ||
      window.ZombiesEconomy ||
      null;

    // bus/store (optional)
    const bus = window.BCO_EVENTBUS || window.BCO?.bus || window.EventBus || null;
    const store = window.BCO_STORE || window.BCO?.store || window.Store || null;

    // core is already your existing BCO_ZOMBIES_CORE
    const core = window.BCO_ZOMBIES_CORE || null;

    return { input, engine, zRuntime, zUI, zEcon, bus, store, core };
  }

  // --- iOS click/scroll hardening (NO UI change, only behavior) ---
  function installIOSHardening() {
    // Prevent double-tap zoom / gesture zoom (you already have in index.html, but we keep redundancy safe)
    const prevent = (e) => { try { e.preventDefault(); } catch {} };

    window.addEventListener("gesturestart", prevent, { passive: false });
    window.addEventListener("gesturechange", prevent, { passive: false });
    window.addEventListener("gestureend", prevent, { passive: false });

    // Kill “ghost click” while in takeover mode (class toggled by your runtime)
    document.addEventListener("click", (e) => {
      const takeover =
        document.body.classList.contains("bco-game-takeover") ||
        document.body.classList.contains("bco-game-active") ||
        document.body.classList.contains("takeover") ||
        false;
      if (!takeover) return;

      // allow clicks inside any scrollable modal zone you already use
      const t = e.target;
      const allow = t && t.closest && t.closest(".bco-modal-scroll, .modal, [role='dialog']");
      if (allow) return;

      e.preventDefault();
      e.stopPropagation();
    }, { capture: true, passive: false });

    // In takeover: block touchmove unless inside scroll containers
    document.addEventListener("touchmove", (e) => {
      const takeover =
        document.body.classList.contains("bco-game-takeover") ||
        document.body.classList.contains("bco-game-active") ||
        document.body.classList.contains("takeover") ||
        false;
      if (!takeover) return;

      const t = e.target;
      const allow = t && t.closest && t.closest(".bco-modal-scroll, .modal, [role='dialog']");
      if (allow) return;

      e.preventDefault();
    }, { passive: false, capture: true });
  }

  // --- Bind existing DOM buttons to your runtime (NO UI change) ---
  function bindLauncher(mods) {
    const rt = mods.zRuntime;

    const btnEnter = q("btnZEnterGame");
    const btnQuick = q("btnZQuickPlay");
    const btnModeA1 = q("btnZModeArcade");
    const btnModeR1 = q("btnZModeRogue");
    const btnModeA2 = q("btnZModeArcade2");
    const btnModeR2 = q("btnZModeRogue2");

    const segMap = q("segZMap");

    function setMode(m) {
      // try all common APIs
      if (rt?.setMode) return rt.setMode(m);
      if (rt?.setGameMode) return rt.setGameMode(m);
      if (window.BCO_ZOMBIES?.setMode) return window.BCO_ZOMBIES.setMode(m);
      // fallback to core start option handled later
    }

    function setMap(mp) {
      if (rt?.setMap) return rt.setMap(mp);
      if (rt?.setGameMap) return rt.setGameMap(mp);
      if (window.BCO_ZOMBIES?.setMap) return window.BCO_ZOMBIES.setMap(mp);
    }

    function startGame() {
      // prefer runtime start
      if (rt?.startGame) return rt.startGame();
      if (rt?.start) return rt.start();
      if (window.BCO_ZOMBIES?.startGame) return window.BCO_ZOMBIES.startGame();

      // last resort: direct engine start if you built it that way
      if (mods.engine?.start) {
        // Read current UI selections
        const mode = (btnModeR2 && btnModeR2.classList.contains("active")) ? "roguelike" : "arcade";
        let map = "Ashes";
        if (segMap) {
          const b = segMap.querySelector(".seg-btn.active");
          if (b) map = b.getAttribute("data-value") || "Ashes";
        }
        return mods.engine.start({ mode, map });
      }

      warn("No runtime/engine start found");
    }

    btnEnter?.addEventListener("click", startGame, { passive: true });
    btnQuick?.addEventListener("click", startGame, { passive: true });

    btnModeA1?.addEventListener("click", () => setMode("ARCADE"), { passive: true });
    btnModeR1?.addEventListener("click", () => setMode("ROGUELIKE"), { passive: true });
    btnModeA2?.addEventListener("click", () => setMode("ARCADE"), { passive: true });
    btnModeR2?.addEventListener("click", () => setMode("ROGUELIKE"), { passive: true });

    if (segMap) {
      segMap.addEventListener("click", (e) => {
        const b = e.target && e.target.closest ? e.target.closest(".seg-btn") : null;
        if (!b) return;
        setMap(b.getAttribute("data-value"));
      }, { passive: true });
    }
  }

  function start() {
    setHealth("js: app start…");

    // keep TG chrome hidden during game (you already do in index.html; we keep safe)
    safe(() => window.BCO_TG?.hideChrome?.());

    installIOSHardening();

    const mods = detect();

    // 1) mount input layer (this is the BIG iOS fix)
    if (mods.input?.mount) safe(() => mods.input.mount());
    else if (mods.input?.init) safe(() => mods.input.init());
    else warn("Input module not found (mount/init)");

    // 2) init zombies UI/econ/runtime if they have init/bind
    if (mods.zUI?.init) safe(() => mods.zUI.init());
    if (mods.zUI?.bind) safe(() => mods.zUI.bind());

    if (mods.zEcon?.init) safe(() => mods.zEcon.init());
    if (mods.zEcon?.bind) safe(() => mods.zEcon.bind());

    if (mods.zRuntime?.init) safe(() => mods.zRuntime.init());
    if (mods.zRuntime?.bind) safe(() => mods.zRuntime.bind());

    // 3) bind your existing launcher buttons to runtime
    bindLauncher(mods);

    // 4) mark loaded
    window.__BCO_JS_OK__ = true;
    setHealth("js: OK (app.js entry)");
    log("Started. Detected:", {
      input: !!mods.input,
      engine: !!mods.engine,
      runtime: !!mods.zRuntime,
      ui: !!mods.zUI,
      economy: !!mods.zEcon,
      core: !!mods.core
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
