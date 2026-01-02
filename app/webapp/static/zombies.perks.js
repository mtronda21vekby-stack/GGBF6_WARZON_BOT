/* =========================================================
   app/webapp/static/zombies.perks.js
   ========================================================= */
(() => {
  "use strict";

  window.BCO_ZOMBIES_PERKS = {
    Jug(run) {
      run.maxHp += 50;
      run.hp += 50;
    },
    Speed(run) {
      run.reloadMul *= 0.8;
      run.rpmMul *= 1.15;
    },
    DoubleTap(run) {
      run.dmgMul *= 1.25;
    },
    Armor(run) {
      run.armorMax += 50;
      run.armor += 50;
    }
  };
})();
