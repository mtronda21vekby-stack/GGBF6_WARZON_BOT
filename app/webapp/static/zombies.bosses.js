// =========================================================
// ZOMBIES BOSSES
// =========================================================
(() => {
  function spawnBoss(run, type = "brute") {
    const base = {
      brute: {
        hp: 1200,
        r: 34,
        spd: 45,
        dmg: 22,
        color: "rgba(34,197,94,.9)"
      },
      elite: {
        hp: 2200,
        r: 42,
        spd: 52,
        dmg: 28,
        color: "rgba(139,92,246,.95)"
      }
    }[type];

    const z = {
      boss: true,
      type,
      x: Math.random() * run.w,
      y: -60,
      r: base.r,
      hp: base.hp,
      maxHp: base.hp,
      spd: base.spd,
      dmg: base.dmg,
      color: base.color
    };

    run.zombies.push(z);
  }

  function bossLogic(run) {
    if (run.wave > 0 && run.wave % 5 === 0 && !run._bossSpawned) {
      spawnBoss(run, run.wave >= 15 ? "elite" : "brute");
      run._bossSpawned = true;
    }
    if (run.wave % 5 !== 0) run._bossSpawned = false;
  }

  window.BCO_ZOMBIES_BOSSES = {
    spawnBoss,
    bossLogic
  };
})();
