/* =========================================================
   app/webapp/static/zombies.bosses.js
   ========================================================= */
(() => {
  "use strict";

  const BOSSES = {
    brute: {
      hp: 600,
      r: 28,
      speed: 55,
      dmg: 18
    },
    tank: {
      hp: 1400,
      r: 36,
      speed: 38,
      dmg: 28
    }
  };

  window.BCO_ZOMBIES_BOSSES = {
    create(type, x, y) {
      const b = BOSSES[type];
      if (!b) return null;
      return {
        type,
        x,
        y,
        r: b.r,
        hp: b.hp,
        maxHp: b.hp,
        spd: b.speed,
        dmg: b.dmg,
        boss: true
      };
    }
  };
})();
