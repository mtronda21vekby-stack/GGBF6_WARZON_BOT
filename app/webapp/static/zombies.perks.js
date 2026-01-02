/* =========================================================
   BLACK CROWN OPS — ZOMBIES PERKS
   File: app/webapp/static/zombies.perks.js
   Provides: window.BCO_ZOMBIES_PERKS[perkId](CORE)
   ========================================================= */
(() => {
  "use strict";

  const PERKS = {
    Jug(CORE) {
      // Core already increases hpMax via effectiveStats;
      // Here we just top-up hp on buy for premium feel.
      try {
        const st = CORE._effectiveStats();
        CORE.state.player.hp = Math.min(CORE.state.player.hp + 30, st.hpMax);
      } catch {}
    },
    Speed(CORE) {
      // Core speed is derived from perks; nothing else needed.
    },
    Mag(CORE) {
      // Optional: add slight bullet pierce as "Ammo perk"
      try {
        CORE.cfg.bullet.pierce = 1;
      } catch {}
    }
  };

  window.BCO_ZOMBIES_PERKS = PERKS;
  console.log("[Z_PERKS] loaded");
})();
