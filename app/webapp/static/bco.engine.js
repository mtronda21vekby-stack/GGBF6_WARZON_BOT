/* app/webapp/static/bco.engine.js */
(() => {
  "use strict";

  const safe = (fn) => { try { return fn(); } catch (_) { return undefined; } };

  function pickZombies() {
    return window.BCO_ZOMBIES || window.BCO_ZOMBIES_CORE || window.BCO_Z || null;
  }

  const zombies = {
    setMode(mode) {
      const z = pickZombies();
      if (!z) return false;
      safe(() => z.setMode?.(mode));
      safe(() => z.mode?.(mode));
      return true;
    },
    enter({ map = "Ashes", mode = "arcade", onExit } = {}) {
      const z = pickZombies();
      if (!z) return false;
      const ok =
        safe(() => z.enter?.({ map, mode, onExit })) ??
        safe(() => z.open?.({ map, mode, onExit })) ??
        safe(() => z.start?.({ map, mode, onExit })) ??
        safe(() => z.start?.(mode));
      safe(() => z.onExit?.(onExit));
      safe(() => z.setOnExit?.(onExit));
      return ok !== false;
    }
  };

  window.BCO_ENGINE = { zombies };

  function loadModule(marker, path) {
    safe(() => {
      if (document.querySelector(`script[data-bco-module="${marker}"]`)) return;
      const script = document.createElement("script");
      script.dataset.bcoModule = marker;
      script.async = false;
      const build = window.__BCO_BUILD__ || Date.now();
      script.src = `${path}?build=${encodeURIComponent(build)}`;
      document.body.appendChild(script);
    });
  }

  loadModule("command-center", "/webapp/command-center.js");
  loadModule("quality-feedback", "/webapp/quality-feedback.js");
})();
