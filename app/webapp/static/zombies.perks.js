/* =========================================================
   BLACK CROWN OPS — ZOMBIES PERKS SYSTEM (Core module)
   File: app/webapp/static/zombies.perks.js
   Drop-in: attaches to window.BCO_ZOMBIES safely
   ========================================================= */
(() => {
  "use strict";

  const core = window.BCO_ZOMBIES;
  if (!core) {
    console.warn("[BCO_Z_PERKS] core not loaded (window.BCO_ZOMBIES missing)");
    return;
  }

  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

  // -----------------------------
  // ✅ Run helpers (safe apply)
  // -----------------------------
  function ensureRunShape(run) {
    if (!run || typeof run !== "object") return null;

    // base fields used by perks (do NOT overwrite if already exists)
    if (typeof run.maxHp !== "number") run.maxHp = 100;
    if (typeof run.hp !== "number") run.hp = run.maxHp;

    if (typeof run.armorMax !== "number") run.armorMax = 150;
    if (typeof run.armor !== "number") run.armor = 0;

    if (typeof run.platesMax !== "number") run.platesMax = 3;
    if (typeof run.plates !== "number") run.plates = 0;
    if (typeof run.plateValue !== "number") run.plateValue = 50;

    if (typeof run.dmgMul !== "number") run.dmgMul = 1;
    if (typeof run.rpmMul !== "number") run.rpmMul = 1;
    if (typeof run.moveMul !== "number") run.moveMul = 1;
    if (typeof run.reloadMul !== "number") run.reloadMul = 1;
    if (typeof run.magMul !== "number") run.magMul = 1;
    if (typeof run.pierceBonus !== "number") run.pierceBonus = 0;
    if (typeof run.critChance !== "number") run.critChance = 0.10;
    if (typeof run.coinMul !== "number") run.coinMul = 1;

    if (!Array.isArray(run.perks)) run.perks = [];

    // optional sync if exists
    if (typeof run._syncPlates === "function") {
      run._syncPlates();
    } else {
      // minimal plate sync
      const p = Math.ceil((run.armor || 0) / run.plateValue);
      run.plates = clamp(p, 0, run.platesMax);
      run.armor = clamp(run.armor, 0, run.armorMax);
    }

    return run;
  }

  // -----------------------------
  // ✅ Perk definitions
  // -----------------------------
  const LIST = [
    {
      id: "Jug",
      name: "🧪 Jug",
      desc: "+Max HP (+40) и heal",
      baseCost: 18,
      apply(run) {
        run.maxHp += 40;
        run.hp = Math.min(run.maxHp, run.hp + 30);
      }
    },
    {
      id: "Speed",
      name: "⚡ Speed Cola",
      desc: "Reload быстрее, RPM выше",
      baseCost: 16,
      apply(run) {
        run.reloadMul *= 0.82;
        run.rpmMul *= 1.10;
      }
    },
    {
      id: "StaminUp",
      name: "🏃 Stamin-Up",
      desc: "Move speed +16%",
      baseCost: 14,
      apply(run) {
        run.moveMul *= 1.16;
      }
    },
    {
      id: "DoubleTap",
      name: "🔥 Double Tap",
      desc: "Damage +16%",
      baseCost: 18,
      apply(run) {
        run.dmgMul *= 1.16;
      }
    },
    {
      id: "Deadshot",
      name: "🎯 Deadshot",
      desc: "Crit шанс +8% (cap 35%)",
      baseCost: 16,
      apply(run) {
        run.critChance = Math.min(0.35, run.critChance + 0.08);
      }
    },
    {
      id: "Mag",
      name: "📦 Mag+",
      desc: "Magazine size +18%",
      baseCost: 15,
      apply(run) {
        run.magMul *= 1.18;
      }
    },
    {
      id: "Armor",
      name: "🛡 Armor+",
      desc: "+Armor (пластины/броня)",
      baseCost: 14,
      apply(run) {
        run.armor = clamp(run.armor + 35, 0, run.armorMax);
        if (typeof run._syncPlates === "function") run._syncPlates();
      }
    },
    {
      id: "Pierce",
      name: "🗡 Pierce",
      desc: "Пули пробивают +1",
      baseCost: 20,
      apply(run) {
        run.pierceBonus += 1;
      }
    },
    {
      id: "Lucky",
      name: "🍀 Lucky",
      desc: "Coins per kill +15%",
      baseCost: 15,
      apply(run) {
        run.coinMul *= 1.15;
      }
    },
    {
      id: "QuickRevive",
      name: "💉 Quick Revive",
      desc: "Слабый regen (arcade/rogue)",
      baseCost: 17,
      apply(run) {
        // помечаем флагом — логика regen может жить в game tick
        run.quickRevive = true;
      }
    }
  ];

  const BY_ID = Object.create(null);
  for (const p of LIST) BY_ID[p.id] = p;

  // -----------------------------
  // ✅ Cost scaling (roguelike shop)
  // -----------------------------
  function cost(perkId, run) {
    const p = BY_ID[perkId];
    if (!p) return 9999;

    const wave = Math.max(1, Math.floor(run?.wave || 1));
    const owned = (run?.perks || []).length;

    // элитно, но честно: растёт с волной и количеством купленного
    const scaled =
      p.baseCost +
      Math.floor(wave * 0.55) +
      Math.floor(owned * 1.25);

    return clamp(scaled, p.baseCost, 60);
  }

  // -----------------------------
  // ✅ Buy / apply API
  // -----------------------------
  function has(run, perkId) {
    return Array.isArray(run?.perks) && run.perks.includes(perkId);
  }

  function buy(run, perkId, opts = {}) {
    run = ensureRunShape(run);
    if (!run) return { ok: false, error: "no_run" };

    const p = BY_ID[perkId];
    if (!p) return { ok: false, error: "bad_perk" };

    if (has(run, perkId)) return { ok: false, error: "owned" };

    const mode = String(run.mode || "");
    const rogOnly = (opts.roguelikeOnly !== false); // default true
    if (rogOnly && mode && mode !== "roguelike") {
      return { ok: false, error: "roguelike_only" };
    }

    const c = cost(perkId, run);
    const coins = Math.floor(run.coins || 0);
    if (coins < c) return { ok: false, error: "no_coins", need: c };

    run.coins = coins - c;
    run.perks.push(perkId);

    try { p.apply?.(run); } catch {}
    if (typeof run._syncPlates === "function") run._syncPlates();

    return { ok: true, perk: perkId, cost: c };
  }

  function applyAll(run) {
    run = ensureRunShape(run);
    if (!run) return run;

    // сброс базовых мультипликаторов НЕ делаем тут (чтоб не ломать ран),
    // applyAll нужен для восстановления после load/save — если надо, зови resetThenApply
    for (const id of (run.perks || [])) {
      const p = BY_ID[id];
      if (!p) continue;
      try { p.apply?.(run); } catch {}
    }
    if (typeof run._syncPlates === "function") run._syncPlates();
    return run;
  }

  function resetThenApply(run) {
    run = ensureRunShape(run);
    if (!run) return run;

    // reset perk-driven stats only
    run.dmgMul = 1;
    run.rpmMul = 1;
    run.moveMul = 1;
    run.reloadMul = 1;
    run.magMul = 1;
    run.pierceBonus = 0;
    run.critChance = 0.10;
    run.coinMul = 1;
    run.quickRevive = false;

    // keep hp/armor as is (game may control it), but keep bounds
    run.hp = clamp(run.hp, 0, run.maxHp);
    run.armor = clamp(run.armor, 0, run.armorMax);
    if (typeof run._syncPlates === "function") run._syncPlates();

    return applyAll(run);
  }

  // -----------------------------
  // ✅ Optional: regen hook (if game calls it)
  // -----------------------------
  function tick(run, dt) {
    if (!run?.running) return;
    if (!run.quickRevive) return;
    if (run.hp <= 0) return;

    // мягкий regen, не имба
    const rate = (run.mode === "roguelike") ? 0.8 : 1.4; // hp/sec
    run.hp = Math.min(run.maxHp, run.hp + rate * dt);
  }

  // -----------------------------
  // ✅ Attach to core (non-breaking)
  // -----------------------------
  core.PERKS = {
    LIST,
    BY_ID,
    cost,
    has,
    buy,
    applyAll,
    resetThenApply,
    tick
  };

  // compat alias (если где-то уже ждёшь core.perks)
  core.perks = core.PERKS;

  console.log("[BCO_Z_PERKS] loaded:", LIST.length);
})();
