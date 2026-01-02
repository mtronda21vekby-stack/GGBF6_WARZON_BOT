/* =========================================================
   BLACK CROWN OPS — ZOMBIES INIT (Public API)
   File: app/webapp/static/zombies.init.js
   Exposes: window.BCO_ZOMBIES (single API)
   ========================================================= */
(() => {
  "use strict";

  const GAME = () => window.BCO_ZOMBIES_GAME || null;

  const API = {
    open() { return GAME()?.open?.() ?? false; },
    close() { return GAME()?.close?.() ?? false; },

    start(mode = "arcade", opts = {}) {
      // opts: { map, character, skin, weaponKey }
      return GAME()?.start?.(mode, opts) ?? false;
    },

    stop(reason = "manual") {
      return GAME()?.stop?.(reason) ?? false;
    },

    setMode(mode) { return GAME()?.setMode?.(mode) ?? "arcade"; },
    setMap(name) { return GAME()?.setMap?.(name) ?? "Ashes"; },

    setCharacter(character, skin) { return GAME()?.setCharacter?.(character, skin) ?? { character, skin }; },
    setWeapon(key) { return GAME()?.setWeapon?.(key) ?? "SMG"; },

    buyPerk(id) { return GAME()?.buyPerk?.(id) ?? false; },
    sendResult(reason) { return GAME()?.sendResult?.(reason) ?? false; }
  };

  window.BCO_ZOMBIES = API;
  console.log("[Z_INIT] BCO_ZOMBIES exported");
})();
