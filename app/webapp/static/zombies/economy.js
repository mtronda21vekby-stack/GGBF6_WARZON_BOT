(() => {
  "use strict";

  const { clamp } = window.BCO_UTILS;

  /**
   * Economy module:
   * - Arcade: simple coins/score
   * - Roguelike: coins + relic quest + rarity rolls + shop hooks
   */
  function createEconomy() {
    const cfg = window.BCO_CONFIG?.ZOMBIES || {};
    const ARC = cfg.ARCADE || {};
    const ROG = cfg.ROGUELIKE || {};

    const state = {
      mode: "ARCADE",
      coins: 0,
      relics: 0,
      relicsGoal: 5,
      lastDropAt: 0,
      runLevel: 1,
      runXP: 0,
      rarityTable: ROG.RARITY || { common: 0.62, rare: 0.25, epic: 0.10, legendary: 0.03 },
      stats: {
        kills: 0,
        waves: 0,
        score: 0,
        durationMs: 0,
      },
    };

    function setMode(mode) {
      state.mode = (mode === "ROGUELIKE") ? "ROGUELIKE" : "ARCADE";
      resetRun();
    }

    function resetRun() {
      state.coins = 0;
      state.relics = 0;
      state.runLevel = 1;
      state.runXP = 0;
      state.stats.kills = 0;
      state.stats.waves = 0;
      state.stats.score = 0;
      state.stats.durationMs = 0;
    }

    function _rand() { return Math.random(); }

    function onKill() {
      state.stats.kills += 1;

      if (state.mode === "ROGUELIKE") {
        state.coins += (ROG.COINS_PER_KILL ?? 1);
        state.stats.score += 10;
        // relic chance
        const chance = clamp(ROG.RELIC_DROP_CHANCE ?? 0.04, 0, 1);
        if (_rand() < chance) {
          state.relics = clamp(state.relics + 1, 0, state.relicsGoal);
          return { drop: "relic" };
        }
        return { drop: "coin" };
      }

      // ARCADE
      state.coins += (ARC.COINS_PER_KILL ?? 1);
      state.stats.score += 8;
      const chanceA = clamp(ARC.RELIC_DROP_CHANCE ?? 0.02, 0, 1);
      if (_rand() < chanceA) {
        state.relics = clamp(state.relics + 1, 0, state.relicsGoal);
        return { drop: "relic" };
      }
      return { drop: "coin" };
    }

    function onWaveComplete() {
      state.stats.waves += 1;

      if (state.mode === "ROGUELIKE") {
        state.coins += (ROG.COINS_PER_WAVE ?? 8);
        state.stats.score += 50;
        gainXP(20 + state.stats.waves * 2);
      } else {
        state.stats.score += 35;
      }
    }

    function gainXP(xp) {
      if (state.mode !== "ROGUELIKE") return;
      state.runXP += Math.max(0, xp | 0);
      // simple leveling curve
      while (state.runXP >= xpToNext(state.runLevel)) {
        state.runXP -= xpToNext(state.runLevel);
        state.runLevel += 1;
      }
    }

    function xpToNext(level) {
      return 60 + (level * 20);
    }

    function rollRarity() {
      const t = state.rarityTable;
      const r = _rand();
      let acc = 0;
      for (const k of ["common", "rare", "epic", "legendary"]) {
        acc += t[k] || 0;
        if (r <= acc) return k;
      }
      return "common";
    }

    function canWonderWeapon() {
      return state.relics >= state.relicsGoal;
    }

    function spendCoins(n) {
      n = Math.max(0, n | 0);
      if (state.coins < n) return false;
      state.coins -= n;
      return true;
    }

    function snapshot() {
      return JSON.parse(JSON.stringify(state));
    }

    return {
      state,
      setMode,
      resetRun,
      onKill,
      onWaveComplete,
      gainXP,
      rollRarity,
      canWonderWeapon,
      spendCoins,
      snapshot,
    };
  }

  window.BCO_ZOMBIES_ECON = createEconomy();
})();
