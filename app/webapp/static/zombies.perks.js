/* =========================================================
   BLACK CROWN OPS — ZOMBIES PERKS [LUX + 3D-READY + COMPAT]
   File: app/webapp/static/zombies.perks.js

   Goals:
     ✅ Two-level API:
        A) Shop API (cost/canBuy/buy/apply/tick/label)
        B) Back-compat direct fn (Jug/Speed/Mag/Armor/Reload/Crit/Loot/Sprint/Tap/Quick/Dead)
     ✅ Works with your LUX zombies.core.js v1.2:
        - CORE.state.perks is flags (0/1) in core today
        - This file adds OPTIONAL leveling stored separately in run._perkLv
          (so we don't break core flags). Core flags are still set to 1 on first buy.
     ✅ NO UI changes; UI can call CORE.buyPerk("Jug") etc; world/init can wire.
     ✅ 3D-ready: no DOM/canvas; pure state mutation + small runtime cache.
     ✅ Elite feel: regen, DR scalar, small bonus logic, future hooks.

   Notes:
     - Your CORE already handles perks flags in _effectiveStats() and _weaponEffective().
     - This module adds extra depth (levels, regen, dmgMul, etc.) without breaking core.
     - If you want CORE to actually use dmgMul, we’ll patch CORE._damagePlayer in zombies.core.js next.
   ========================================================= */
(() => {
  "use strict";

  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const now = () => (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now();

  // ---------------------------------------------------------
  // Perk definitions (elite curve, scalable)
  // ---------------------------------------------------------
  const DEF = {
    Jug:    { name: "Jugger",     emoji: "🧪", maxLv: 3, baseCost: 12, costMul: 1.55, desc: "HP max +, damage resist (L2+)" },
    Speed:  { name: "Stamin-Up",  emoji: "⚡", maxLv: 3, baseCost: 10, costMul: 1.55, desc: "Move speed +, iFrames + (L2+)" },
    Mag:    { name: "Ammo",       emoji: "📦", maxLv: 3, baseCost: 8,  costMul: 1.55, desc: "Mag/reserve +, pierce +" },
    Armor:  { name: "Plates",     emoji: "🛡", maxLv: 3, baseCost: 14, costMul: 1.55, desc: "Armor max +, plating faster" },
    Reload: { name: "Fast Hands", emoji: "🔄", maxLv: 3, baseCost: 11, costMul: 1.55, desc: "Reload faster" },
    Crit:   { name: "Deadshot",   emoji: "🎯", maxLv: 3, baseCost: 13, costMul: 1.60, desc: "Crit chance/dmg +" },
    Loot:   { name: "Scavenger",  emoji: "💰", maxLv: 3, baseCost: 12, costMul: 1.55, desc: "Better drops + magnet" },
    Sprint: { name: "Marathon",   emoji: "🏃", maxLv: 3, baseCost: 10, costMul: 1.55, desc: "Less move penalty" },

    // extra/future perks (safe to exist even if UI doesn't show them)
    Tap:    { name: "Double Tap", emoji: "💥", maxLv: 3, baseCost: 14, costMul: 1.60, desc: "Fire rate +, spread -" },
    Quick:  { name: "Quick Rev",  emoji: "💉", maxLv: 3, baseCost: 11, costMul: 1.55, desc: "HP regen over time" },
    Dead:   { name: "Deadshot+",  emoji: "🧿", maxLv: 3, baseCost: 15, costMul: 1.62, desc: "Aim assist + (future) + crit" }
  };

  // ---------------------------------------------------------
  // Helpers to read/write across "run" shapes
  // run can be CORE or an overlay state object
  // ---------------------------------------------------------
  function getPerksFlags(run) {
    // CORE: run.state.perks ; overlay: run.perks
    if (!run) return null;
    if (run.state?.perks && typeof run.state.perks === "object") return run.state.perks;
    if (run.perks && typeof run.perks === "object") return run.perks;
    return null;
  }

  function getCoins(run) {
    if (!run) return 0;
    if (Number.isFinite(run.state?.coins)) return run.state.coins | 0;
    if (Number.isFinite(run.coins)) return run.coins | 0;
    return 0;
  }

  function setCoins(run, v) {
    const val = v | 0;
    if (!run) return;
    if (Number.isFinite(run.state?.coins)) run.state.coins = val;
    else if (Number.isFinite(run.coins)) run.coins = val;
  }

  function getMode(run) {
    const m = String(run?.mode || run?.meta?.mode || "").toLowerCase();
    return m.includes("rogue") ? "roguelike" : "arcade";
  }

  function getPlayer(run) {
    return run?.state?.player || run?.player || run?.p || null;
  }

  function getCfg(run) {
    return run?.cfg || run?.state?.cfg || null;
  }

  // ---------------------------------------------------------
  // Level storage (DO NOT break core flags)
  // - Core uses state.perks.{Jug:0/1,...}
  // - We keep levels in run._perkLv (per-run) and mirror "owned" into flags.
  // ---------------------------------------------------------
  function getLvStore(run) {
    if (!run) return null;
    run._perkLv = run._perkLv || {};
    return run._perkLv;
  }

  function lvlOf(perkId, run) {
    const d = DEF[perkId];
    if (!d) return 0;

    const store = getLvStore(run);
    const lv = store ? (store[perkId] | 0) : 0;
    return clamp(lv, 0, d.maxLv | 0);
  }

  function setLvl(perkId, run, lv) {
    const d = DEF[perkId];
    if (!d) return;
    const store = getLvStore(run);
    if (!store) return;
    store[perkId] = clamp(lv | 0, 0, d.maxLv | 0);
  }

  function ensureOwnedFlag(perkId, run) {
    const flags = getPerksFlags(run);
    if (!flags) return;
    // keep compatibility with core: flags are 0/1 (owned)
    flags[perkId] = 1;
  }

  // ---------------------------------------------------------
  // Shop API
  // ---------------------------------------------------------
  function cost(perkId, run) {
    const d = DEF[perkId];
    if (!d) return 999;

    const lv = lvlOf(perkId, run);
    if (lv >= d.maxLv) return 999;

    // Elite curve: base * mul^lv
    const raw = d.baseCost * Math.pow(d.costMul, lv);
    return Math.max(1, Math.round(raw));
  }

  function canBuy(perkId, run) {
    const d = DEF[perkId];
    if (!d) return false;
    if (getMode(run) !== "roguelike") return false;

    const lv = lvlOf(perkId, run);
    if (lv >= d.maxLv) return false;

    return (getCoins(run) | 0) >= (cost(perkId, run) | 0);
  }

  function label(perkId, run) {
    const d = DEF[perkId];
    if (!d) return String(perkId || "");
    const lv = lvlOf(perkId, run);
    const c = cost(perkId, run);
    const price = (lv >= d.maxLv) ? "MAX" : String(c);
    return `${d.emoji} ${perkId} L${lv}/${d.maxLv} (${price})`;
  }

  // ---------------------------------------------------------
  // Apply effects (instant). Passive effects in tick().
  // This is SAFE even if CORE already boosts via flags.
  // ---------------------------------------------------------
  function apply(perkId, run) {
    const p = getPlayer(run);
    if (!p) return;

    const lv = lvlOf(perkId, run); // current after setLvl in buy()
    const cfg = getCfg(run);

    // Premium instant feedback on buy:
    if (perkId === "Jug") {
      const heal = 18 + lv * 7;
      // prefer CORE effectiveStats hpMax if exists
      const maxHp = safeHpMax(run, p);
      p.hp = Math.min((p.hp | 0) + heal, maxHp);
    }

    if (perkId === "Quick") {
      const heal = 12 + lv * 5;
      const maxHp = safeHpMax(run, p);
      p.hp = Math.min((p.hp | 0) + heal, maxHp);
    }

    // Soft config nudges (won't break if cfg missing)
    if (perkId === "Mag") {
      // do NOT mutate base weapon templates aggressively; instead set helper scalars
      run._perkMagMul = (lv === 1) ? 1.08 : (lv === 2) ? 1.14 : 1.20;
      run._perkPierceBonus = (lv === 1) ? 0 : (lv === 2) ? 1 : 2;
      // if core has cfg.bullet, set minimum pierce baseline (core also has weapon pierce)
      try {
        if (cfg?.bullet) cfg.bullet.pierce = Math.max(cfg.bullet.pierce || 0, 1);
      } catch {}
    }

    if (perkId === "Tap") {
      run._perkRpmMul = (lv === 1) ? 1.06 : (lv === 2) ? 1.12 : 1.18;
      run._perkSpreadMul = (lv === 1) ? 0.92 : (lv === 2) ? 0.86 : 0.80;
    }

    if (perkId === "Reload") {
      run._perkReloadMul = (lv === 1) ? 0.92 : (lv === 2) ? 0.86 : 0.80;
    }

    if (perkId === "Crit" || perkId === "Dead" ) {
      run._perkCritBonus = (lv === 1) ? 0.03 : (lv === 2) ? 0.06 : 0.09;
      run._perkCritMul = (lv === 1) ? 1.10 : (lv === 2) ? 1.18 : 1.28;
    }

    if (perkId === "Armor") {
      run._perkArmorMul = (lv === 1) ? 1.06 : (lv === 2) ? 1.12 : 1.18;
      run._perkPlateSpeedMul = (lv === 1) ? 0.92 : (lv === 2) ? 0.86 : 0.80;
    }

    if (perkId === "Loot") {
      run._perkLootBonus = (lv === 1) ? 0.15 : (lv === 2) ? 0.30 : 0.45;
      run._perkMagnetMul = (lv === 1) ? 1.08 : (lv === 2) ? 1.18 : 1.30;
    }

    if (perkId === "Sprint") {
      run._perkMovePenaltyMul = (lv === 1) ? 0.92 : (lv === 2) ? 0.84 : 0.76;
    }

    if (perkId === "Speed") {
      // iFrames helper for future core patch
      run._perkIFramesMul = (lv === 1) ? 1.02 : (lv === 2) ? 1.08 : 1.14;
    }
  }

  function tick(run, dt, tms) {
    const p = getPlayer(run);
    if (!p) return;

    const time = (Number(tms) || now());
    const rt = (run._perkRT = run._perkRT || { lastRegenAt: 0 });

    // Quick Revive regen
    const quickLv = lvlOf("Quick", run);
    if (quickLv > 0) {
      const regenPerSec = (quickLv === 1) ? 1.2 : (quickLv === 2) ? 2.0 : 3.0;
      if ((time - rt.lastRegenAt) > 90) {
        rt.lastRegenAt = time;
        const maxHp = safeHpMax(run, p);
        const cur = (p.hp || 0);
        if (cur > 0 && cur < maxHp) {
          // dt is fixed in core (60hz); keep regen stable anyway
          const add = regenPerSec * 0.10;
          p.hp = Math.min(maxHp, cur + add);
        }
      }
    }

    // Jug DR scalar (core patch will read run._dmgMul if we wire it)
    const jugLv = lvlOf("Jug", run);
    run._dmgMul = (jugLv === 0) ? 1.0 : (jugLv === 1) ? 0.92 : (jugLv === 2) ? 0.86 : 0.80;

    // Loot magnet scalar (core can read this later)
    const lootLv = lvlOf("Loot", run);
    run._magnetMul = (lootLv === 0) ? 1.0 : (lootLv === 1) ? 1.08 : (lootLv === 2) ? 1.18 : 1.30;
  }

  function buy(perkId, run) {
    if (!DEF[perkId]) return false;
    if (!canBuy(perkId, run)) return false;

    const c = cost(perkId, run) | 0;
    const coins = getCoins(run) | 0;
    if (coins < c) return false;

    setCoins(run, coins - c);

    const lv = lvlOf(perkId, run);
    setLvl(perkId, run, lv + 1);

    // Maintain core-compatible "owned" flag from first buy
    ensureOwnedFlag(perkId, run);

    // Apply immediate
    try { apply(perkId, run); } catch {}

    return true;
  }

  // ---------------------------------------------------------
  // Back-compat direct functions (called as PERKS.Jug(CORE))
  // These MUST NOT break core.
  // ---------------------------------------------------------
  function Jug(CORE) {
    // Mark owned + set lv to at least 1 + instant heal
    try {
      ensureOwnedFlag("Jug", CORE);
      if (lvlOf("Jug", CORE) <= 0) setLvl("Jug", CORE, 1);
      apply("Jug", CORE);
      // default DR scalar
      CORE._dmgMul = 0.92;
    } catch {}
  }

  function Speed(CORE) {
    try {
      ensureOwnedFlag("Speed", CORE);
      if (lvlOf("Speed", CORE) <= 0) setLvl("Speed", CORE, 1);
      apply("Speed", CORE);
    } catch {}
  }

  function Mag(CORE) {
    try {
      ensureOwnedFlag("Mag", CORE);
      if (lvlOf("Mag", CORE) <= 0) setLvl("Mag", CORE, 1);
      apply("Mag", CORE);
    } catch {}
  }

  function Armor(CORE) {
    try {
      ensureOwnedFlag("Armor", CORE);
      if (lvlOf("Armor", CORE) <= 0) setLvl("Armor", CORE, 1);
      apply("Armor", CORE);
    } catch {}
  }

  function Reload(CORE) {
    try {
      ensureOwnedFlag("Reload", CORE);
      if (lvlOf("Reload", CORE) <= 0) setLvl("Reload", CORE, 1);
      apply("Reload", CORE);
    } catch {}
  }

  function Crit(CORE) {
    try {
      ensureOwnedFlag("Crit", CORE);
      if (lvlOf("Crit", CORE) <= 0) setLvl("Crit", CORE, 1);
      apply("Crit", CORE);
    } catch {}
  }

  function Loot(CORE) {
    try {
      ensureOwnedFlag("Loot", CORE);
      if (lvlOf("Loot", CORE) <= 0) setLvl("Loot", CORE, 1);
      apply("Loot", CORE);
    } catch {}
  }

  function Sprint(CORE) {
    try {
      ensureOwnedFlag("Sprint", CORE);
      if (lvlOf("Sprint", CORE) <= 0) setLvl("Sprint", CORE, 1);
      apply("Sprint", CORE);
    } catch {}
  }

  function Tap(CORE) {
    try {
      ensureOwnedFlag("Tap", CORE);
      if (lvlOf("Tap", CORE) <= 0) setLvl("Tap", CORE, 1);
      apply("Tap", CORE);
    } catch {}
  }

  function Quick(CORE) {
    try {
      ensureOwnedFlag("Quick", CORE);
      if (lvlOf("Quick", CORE) <= 0) setLvl("Quick", CORE, 1);
      apply("Quick", CORE);
    } catch {}
  }

  function Dead(CORE) {
    try {
      ensureOwnedFlag("Dead", CORE);
      if (lvlOf("Dead", CORE) <= 0) setLvl("Dead", CORE, 1);
      apply("Dead", CORE);
    } catch {}
  }

  // ---------------------------------------------------------
  // Small helpers
  // ---------------------------------------------------------
  function safeHpMax(run, p) {
    // Prefer CORE._effectiveStats().hpMax
    try {
      if (typeof run?._effectiveStats === "function") {
        const st = run._effectiveStats();
        if (st && Number.isFinite(st.hpMax)) return st.hpMax | 0;
      }
    } catch {}
    // fallback to player.hpMax if present
    const hpMax = (p && Number.isFinite(p.hpMax)) ? (p.hpMax | 0) : 100;
    return Math.max(1, hpMax);
  }

  // ---------------------------------------------------------
  // Export
  // ---------------------------------------------------------
  window.BCO_ZOMBIES_PERKS = {
    // Shop API
    cost,
    canBuy,
    buy,
    apply,
    tick,
    label,

    // Back-compat direct fns
    Jug,
    Speed,
    Mag,
    Armor,
    Reload,
    Crit,
    Loot,
    Sprint,
    Tap,
    Quick,
    Dead,

    // defs + helpers (optional)
    defs: DEF,
    lvlOf: (id, run) => lvlOf(String(id || ""), run),
    setLvl: (id, run, lv) => setLvl(String(id || ""), run, lv),
    _version: "LUX_PERKS_v2_3D_READY"
  };

  console.log("[Z_PERKS] loaded (LUX + 3D-ready + compat)");
})();
