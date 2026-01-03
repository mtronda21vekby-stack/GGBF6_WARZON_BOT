// app/webapp/static/app.js
// BCO App Entry (uses YOUR existing modules) vNEXT-ENTRY-RESTORE-1
(() => {
  "use strict";

  const log = (...a) => console.log("[BCO_APP]", ...a);
  const warn = (...a) => console.warn("[BCO_APP]", ...a);

  function safe(fn) { try { return fn(); } catch (e) { return undefined; } }
  function q(id) { return document.getElementById(id); }

  function setHealth(msg) {
    const el = q("jsHealth");
    if (el) el.textContent = msg;
  }

  function detect() {
    const input =
      window.BCO_INPUT ||
      window.BCO?.input ||
      window.BCOInput ||
      window.BCO?.INPUT ||
      null;

    const engine =
      window.BCO_ENGINE ||
      window.BCO?.engine ||
      window.BCOEngine ||
      window.BCO?.ENGINE ||
      null;

    const zRuntime =
      window.BCO_ZOMBIES_RUNTIME ||
      window.BCO?.zombies?.runtime ||
      window.ZombiesRuntime ||
      window.BCO?.zombies?.runtime ||
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

    const bus = window.BCO_EVENTBUS || window.BCO?.bus || window.EventBus || null;
    const store = window.BCO_STORE || window.BCO?.store || window.Store || null;

    const core = window.BCO_ZOMBIES_CORE || null;

    return { input, engine, zRuntime, zUI, zEcon, bus, store, core };
  }

  // ✅ ONLY safe anti-zoom redundancy (NO click killer)
  function installIOSHardeningSafe() {
    const prevent = (e) => { try { e.preventDefault(); } catch {} };
    window.addEventListener("gesturestart", prevent, { passive: false });
    window.addEventListener("gesturechange", prevent, { passive: false });
    window.addEventListener("gestureend", prevent, { passive: false });
  }

  function start() {
    setHealth("js: app start…");

    // Keep TG chrome managed by BCO_TG (index.html already initializes it)
    safe(() => window.BCO_TG?.hideChrome?.());

    installIOSHardeningSafe();

    const mods = detect();

    // 1) mount input layer (main iOS tap fix)
    if (mods.input?.mount) safe(() => mods.input.mount());
    else if (mods.input?.init) safe(() => mods.input.init());
    else warn("Input module not found (mount/init)");

    // 2) init modules if present
    if (mods.zUI?.init) safe(() => mods.zUI.init());
    if (mods.zUI?.bind) safe(() => mods.zUI.bind());

    if (mods.zEcon?.init) safe(() => mods.zEcon.init());
    if (mods.zEcon?.bind) safe(() => mods.zEcon.bind());

    if (mods.zRuntime?.init) safe(() => mods.zRuntime.init());
    if (mods.zRuntime?.bind) safe(() => mods.zRuntime.bind());

    window.__BCO_JS_OK__ = true;
    setHealth("js: OK (app.js restored)");
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
