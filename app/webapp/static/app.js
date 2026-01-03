// app/webapp/static/app.js
// BCO Mini App Bootstrap Loader (Elite) v3.1.0
// Goal: ensure your new modular architecture is loaded in correct order
// WITHOUT changing UI and WITHOUT requiring index.html edits.

(() => {
  "use strict";

  const BUILD = (window.__BCO_BUILD__ && window.__BCO_BUILD__ !== "__BUILD__")
    ? window.__BCO_BUILD__
    : String(Date.now());

  function qs(id) { return document.getElementById(id); }
  function setHealth(msg) {
    const el = qs("jsHealth");
    if (el) el.textContent = msg;
  }

  function log(...a) { console.log("[BCO_BOOT]", ...a); }
  function warn(...a) { console.warn("[BCO_BOOT]", ...a); }
  function err(...a) { console.error("[BCO_BOOT]", ...a); }

  function loadScript(src, optional = false) {
    return new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.async = false;
      s.src = src + (src.includes("?") ? "&" : "?") + "build=" + encodeURIComponent(BUILD);
      s.onload = () => resolve(true);
      s.onerror = () => optional ? resolve(false) : reject(new Error("Failed to load: " + src));
      document.body.appendChild(s);
    });
  }

  async function boot() {
    try {
      setHealth("js: bootstrap…");

      // 0) Telegram minimal ready (safe)
      try {
        if (window.Telegram && Telegram.WebApp) {
          Telegram.WebApp.ready();
          Telegram.WebApp.expand();
          try { Telegram.WebApp.MainButton?.hide?.(); } catch {}
          try { Telegram.WebApp.BackButton?.hide?.(); } catch {}
        }
      } catch {}

      // 1) Your modular BCO layer (order matters)
      await loadScript("/webapp/bco.config.js");
      await loadScript("/webapp/bco.store.js");
      await loadScript("/webapp/bco.eventbus.js");
      await loadScript("/webapp/bco.input.js");
      await loadScript("/webapp/bco.engine.js");

      // 2) Zombies modules (runtime/ui/economy)
      await loadScript("/webapp/zombies/runtime.js");
      await loadScript("/webapp/zombies/ui.js");
      await loadScript("/webapp/zombies/economy.js");

      // 3) Bind app to your DOM (buttons/tabs) — in runtime (no UI changes)
      if (window.BCO_APP && typeof window.BCO_APP.start === "function") {
        window.BCO_APP.start();
      } else {
        warn("BCO_APP.start not found — check runtime exports");
      }

      window.__BCO_JS_OK__ = true;
      setHealth("js: OK (bootstrap v3.1.0)");
      log("Boot OK");
    } catch (e) {
      err("BOOT ERROR", e);
      setHealth("js: BOOT ERROR (console)");
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();
