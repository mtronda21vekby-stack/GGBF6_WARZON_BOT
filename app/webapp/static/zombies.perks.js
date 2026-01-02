// =========================================================
// ZOMBIES PERKS SYSTEM
// =========================================================
(() => {
  const PERKS = [
    {
      id: "Jug",
      name: "🧪 Juggernog",
      cost: 18,
      apply(run) {
        run.maxHp += 40;
        run.hp = Math.min(run.hp + 40, run.maxHp);
      }
    },
    {
      id: "Speed",
      name: "⚡ Speed Cola",
      cost: 16,
      apply(run) {
        run.reloadMul *= 0.8;
        run.rpmMul *= 1.12;
      }
    },
    {
      id: "DoubleTap",
      name: "🔥 Double Tap",
      cost: 18,
      apply(run) {
        run.dmgMul *= 1.18;
      }
    },
    {
      id: "Deadshot",
      name: "🎯 Deadshot",
      cost: 16,
      apply(run) {
        run.critChance = Math.min(0.35, run.critChance + 0.1);
      }
    }
  ];

  function buyPerk(run, id) {
    if (run.perks.includes(id)) return false;
    const perk = PERKS.find(p => p.id === id);
    if (!perk || run.coins < perk.cost) return false;

    run.coins -= perk.cost;
    run.perks.push(id);
    perk.apply(run);
    return true;
  }

  window.BCO_ZOMBIES_PERKS = {
    PERKS,
    buyPerk
  };
})();
