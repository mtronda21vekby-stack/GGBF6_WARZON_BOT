/* =========================================================
   BLACK CROWN OPS — ZOMBIES INIT (Public API)  [LUX]
   File: app/webapp/static/zombies.init.js
   Exposes: window.BCO_ZOMBIES (single API)

   LUX upgrades:
     - Auto-installs BOSSES.install(CORE) if available (LUX bosses module)
     - Ensures PERKS hook is wired via CORE._buyPerk (if perks module exists)
     - Adds helpers: listMaps/listWeapons/getState/getMeta
     - Backward compatible with your existing calls
   ========================================================= */
(() => {
  "use strict";

  const GAME = () => window.BCO_ZOMBIES_GAME || null;
  const CORE = () => window.BCO_ZOMBIES_CORE || null;

  let _installed = false;

  function safe(fn, fallback) {
    try { return fn(); } catch { return fallback; }
  }

  function installOnce() {
    if (_installed) return true;
    _installed = true;

    const core = CORE();
    if (!core) return false;

    // 1) Install LUX bosses if present (adds projectiles/telegraphs + bullet hit hook)
    safe(() => {
      const BOSSES = window.BCO_ZOMBIES_BOSSES;
      if (BOSSES?.install && typeof BOSSES.install === "function") {
        BOSSES.install(core, () => window.BCO_ZOMBIES_MAPS?.get?.(core?.meta?.map));
      }
      return true;
    }, false);

    // 2) Wire perks module into CORE._buyPerk if not already wired
    safe(() => {
      const PERKS = window.BCO_ZOMBIES_PERKS;
      if (!PERKS) return false;

      const prev = core._buyPerk;
      core._buyPerk = function (CORE_ARG, perkId) {
        // Apply perk effect
        try {
          const fn = PERKS?.[String(perkId || "")];
          if (typeof fn === "function") fn(CORE_ARG);
        } catch {}

        // Keep previous hook if existed
        try { if (typeof prev === "function") prev(CORE_ARG, perkId); } catch {}
      };

      return true;
    }, false);

    return true;
  }

  function ensureInstalled() {
    installOnce();
    return true;
  }

  const API = {
    // core overlay
    open() {
      ensureInstalled();
      return GAME()?.open?.() ?? false;
    },

    close() {
      return GAME()?.close?.() ?? false;
    },

    // run control
    start(mode = "arcade", opts = {}) {
      // opts: { map, character, skin, weaponKey }
      ensureInstalled();
      return GAME()?.start?.(mode, opts) ?? false;
    },

    stop(reason = "manual") {
      return GAME()?.stop?.(reason) ?? false;
    },

    // runtime tweaks
    setMode(mode) {
      ensureInstalled();
      return GAME()?.setMode?.(mode) ?? "arcade";
    },

    setMap(name) {
      ensureInstalled();
      return GAME()?.setMap?.(name) ?? "Ashes";
    },

    setCharacter(character, skin) {
      ensureInstalled();
      return GAME()?.setCharacter?.(character, skin) ?? { character, skin };
    },

    setWeapon(key) {
      ensureInstalled();
      return GAME()?.setWeapon?.(key) ?? "SMG";
    },

    buyPerk(id) {
      ensureInstalled();
      return GAME()?.buyPerk?.(id) ?? false;
    },

    sendResult(reason) {
      return GAME()?.sendResult?.(reason) ?? false;
    },

    // helpers (lux)
    listMaps() {
      return safe(() => window.BCO_ZOMBIES_MAPS?.list?.() || ["Ashes"], ["Ashes"]);
    },

    listWeapons() {
      return safe(() => Object.keys(CORE()?.cfg?.weapons || { SMG: 1, AR: 1, SG: 1 }), ["SMG", "AR", "SG"]);
    },

    getState() {
      const c = CORE();
      return c?.state ? c.state : null;
    },

    getMeta() {
      const c = CORE();
      return c?.meta ? c.meta : null;
    }
  };

  // auto-install on load (safe)
  ensureInstalled();

  window.BCO_ZOMBIES = API;
  console.log("[Z_INIT] BCO_ZOMBIES exported (LUX)");
})();
