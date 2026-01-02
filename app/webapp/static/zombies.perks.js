/* =========================================================
   BLACK CROWN OPS — ZOMBIES PERKS [LUX + COMPAT]
   File: app/webapp/static/zombies.perks.js

   Provides: window.BCO_ZOMBIES_PERKS with BOTH APIs:
   A) "Shop API" (used by zombies.js overlay):
      - cost(perkId, run) -> number
      - canBuy(perkId, run) -> boolean
      - buy(perkId, run) -> boolean
      - apply(perkId, run) -> void
      - tick(run, dt, tms) -> void
      - label(perkId, run) -> string

   B) Back-compat "direct perk fn" (your current style):
      - Jug(CORE), Speed(CORE), Mag(CORE)
      (works with zombies.core.js if you call it on buy)
   ========================================================= */
(() => {
  "use strict";

  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

  // ---------------------------------------------------------
  // Perk definitions (scalable, elite-feel)
  // ---------------------------------------------------------
  const DEF = {
    Jug: {
      name: "Jugger",
      emoji: "🧪",
      maxLv: 3,
      baseCost: 12,
      costMul: 1.55,
      desc: "HP max +, damage resist (L2+)"
    },
    Speed: {
      name: "Stamin-Up",
      emoji: "⚡",
      maxLv: 3,
      baseCost: 10,
      costMul: 1.55,
      desc: "Move speed +, iFrames + (L2+)"
    },
    Mag: {
      name: "Ammo",
      emoji: "🔫",
      maxLv: 3,
      baseCost: 8,
      costMul: 1.55,
      desc: "Pierce +, spread -, reload feel (future)"
    },

    // Extras (future UI can expose)
    Tap: {
      name: "Double Tap",
      emoji: "💥",
      maxLv: 3,
      baseCost: 14,
      costMul: 1.60,
      desc: "Fire rate +, recoil/spread -"
    },
    Quick: {
      name: "Quick Revive",
      emoji: "💉",
      maxLv: 3,
      baseCost: 11,
      costMul: 1.55,
      desc: "HP regen over time"
    },
    Dead: {
      name: "Deadshot",
      emoji: "🎯",
      maxLv: 3,
      baseCost: 13,
      costMul: 1.60,
      desc: "Aim assist +, crit bonus (future)"
    }
  };

  function getPerksObj(run) {
    // overlay run has run.perks, CORE has CORE.state.perks
    if (!run) return null;
    if (run.perks && typeof run.perks === "object") return run.perks;
    if (run.state?.perks && typeof run.state.perks === "object") return run.state.perks;
    return null;
  }

  function getCoins(run) {
    if (!run) return 0;
    if (Number.isFinite(run.coins)) return run.coins;
    if (Number.isFinite(run.state?.coins)) return run.state.coins;
    return 0;
  }

  function setCoins(run, v) {
    if (!run) return;
    if (Number.isFinite(run.coins)) run.coins = v;
    else if (Number.isFinite(run.state?.coins)) run.state.coins = v;
  }

  function getMode(run) {
    const m = String(run?.mode || run?.meta?.mode || "").toLowerCase();
    if (m.includes("rogue")) return "roguelike";
    return "arcade";
  }

  function getPlayer(run) {
    // overlay: run.p ; CORE: run.state.player
    return run?.p || run?.state?.player || null;
  }

  function getCfg(run) {
    // overlay: CFG is inside zombies.js; CORE: run.cfg
    // We can still mutate some values if present in run.cfg.
    return run?.cfg || null;
  }

  function lvlOf(perkId, run) {
    const P = getPerksObj(run);
    if (!P) return 0;
    return clamp(Number(P[perkId] || 0) | 0, 0, (DEF[perkId]?.maxLv || 1));
  }

  function setLvl(perkId, run, lv) {
    const P = getPerksObj(run);
    if (!P) return;
    P[perkId] = clamp(lv | 0, 0, (DEF[perkId]?.maxLv || 1));
  }

  function cost(perkId, run) {
    const d = DEF[perkId];
    if (!d) return 999;
    const lv = lvlOf(perkId, run);
    if (lv >= d.maxLv) return 999;

    // Elite curve: base * mul^lv, rounded to even
    const raw = d.baseCost * Math.pow(d.costMul, lv);
    return Math.max(1, Math.round(raw));
  }

  function canBuy(perkId, run) {
    if (!DEF[perkId]) return false;
    if (getMode(run) !== "roguelike") return false;

    const lv = lvlOf(perkId, run);
    if (lv >= DEF[perkId].maxLv) return false;

    const c = cost(perkId, run);
    return getCoins(run) >= c;
  }

  function label(perkId, run) {
    const d = DEF[perkId];
    if (!d) return String(perkId || "");
    const lv = lvlOf(perkId, run);
    const max = d.maxLv;
    const c = cost(perkId, run);

    const lvTag = `L${lv}/${max}`;
    const price = (lv >= max) ? "MAX" : String(c);

    // Example: 🧪 Jug L1/3 (12)
    return `${d.emoji} ${perkId} ${lvTag} (${price})`;
  }

  // ---------------------------------------------------------
  // Apply perk effects (instant + passive tick)
  // ---------------------------------------------------------
  function apply(perkId, run) {
    const p = getPlayer(run);
    if (!p) return;

    // NOTE:
    // - Overlay zombies.js already has effectiveStats() based on Jug/Speed flags.
    // - CORE effectiveStats() already does Jug/Speed multipliers.
    // Here we add LUX extras: regen, resist, pierce tweaks, fire-rate, etc.
    const lv = lvlOf(perkId, run);

    // Small instant feedback: heal on buy (premium feel)
    if (perkId === "Jug") {
      // heal chunk each level
      const heal = 18 + lv * 6;
      p.hp = Math.min((p.hp || 0) + heal, (p.hpMax || 99999));
    }

    if (perkId === "Quick") {
      // immediate small heal, then regen in tick()
      const heal = 12 + lv * 4;
      p.hp = Math.min((p.hp || 0) + heal, (p.hpMax || 99999));
    }

    if (perkId === "Mag") {
      // If CORE cfg exists — buff pierce progressively
      const cfg = getCfg(run);
      if (cfg?.bullet) {
        cfg.bullet.pierce = Math.max(cfg.bullet.pierce || 0, 1 + (lv >= 2 ? 1 : 0) + (lv >= 3 ? 1 : 0));
      }
    }

    if (perkId === "Tap") {
      // If CORE cfg exists — buff rpm a bit (soft, no breaking)
      const cfg = getCfg(run);
      if (cfg?.weapons) {
        for (const k of Object.keys(cfg.weapons)) {
          const w = cfg.weapons[k];
          if (!w || !w.rpm) continue;
          const mul = (lv === 1) ? 1.10 : (lv === 2) ? 1.18 : 1.26;
          w.rpm = Math.round(w.rpm * mul);
          // reduce spread slightly
          if (Number.isFinite(w.spread)) w.spread = Math.max(0.01, w.spread * (lv === 1 ? 0.92 : lv === 2 ? 0.86 : 0.80));
        }
      }
    }

    if (perkId === "Speed") {
      // L2+: slightly longer iFrames if CORE cfg exists
      const cfg = getCfg(run);
      if (cfg?.player && lv >= 2) {
        cfg.player.iFramesMs = Math.round((cfg.player.iFramesMs || 220) * (lv === 2 ? 1.08 : 1.14));
      }
    }
  }

  // Passive tick effects (regen, resist, etc.)
  function tick(run, dt, tms) {
    const p = getPlayer(run);
    if (!p) return;

    // We’ll store perk runtime state on run._perkRT
    const rt = (run._perkRT = run._perkRT || { lastRegenAt: 0 });

    // QUICK REVIVE regen (if perk exists)
    const quickLv = lvlOf("Quick", run);
    if (quickLv > 0) {
      // regen rate per sec
      const regen = (quickLv === 1) ? 1.2 : (quickLv === 2) ? 2.0 : 3.0;
      // apply regen ~10x/sec to keep it smooth
      if ((tms - rt.lastRegenAt) > 90) {
        rt.lastRegenAt = tms;
        const maxHp = (p.hpMax || 99999);
        const cur = (p.hp || 0);
        if (cur > 0 && cur < maxHp) {
          p.hp = Math.min(maxHp, cur + regen);
        }
      }
    }

    // JUG damage resist flag (overlay/core should read it if you wire it later)
    // We'll add a simple scalar you can use in hitPlayer().
    const jugLv = lvlOf("Jug", run);
    run._dmgMul = (jugLv === 0) ? 1.0 : (jugLv === 1) ? 0.92 : (jugLv === 2) ? 0.86 : 0.80;
  }

  // Buy implements “levels” + calls apply()
  function buy(perkId, run) {
    if (!DEF[perkId]) return false;
    if (!canBuy(perkId, run)) return false;

    const c = cost(perkId, run);
    const coins = getCoins(run);
    if (coins < c) return false;

    setCoins(run, coins - c);

    const lv = lvlOf(perkId, run);
    setLvl(perkId, run, lv + 1);

    // Apply effects immediately
    try { apply(perkId, run); } catch {}

    return true;
  }

  // ---------------------------------------------------------
  // BACK-COMPAT: Your direct CORE style
  // ---------------------------------------------------------
  function Jug(CORE) {
    try {
      // Top-up on buy
      const st = CORE._effectiveStats();
      CORE.state.player.hp = Math.min(CORE.state.player.hp + 30, st.hpMax);
      // Add resist scalar for future usage
      CORE._dmgMul = 0.92;
    } catch {}
  }

  function Speed(CORE) {
    // Nothing required (core effectiveStats uses perk flag)
  }

  function Mag(CORE) {
    try {
      CORE.cfg.bullet.pierce = Math.max(CORE.cfg.bullet.pierce || 0, 1);
    } catch {}
  }

  window.BCO_ZOMBIES_PERKS = {
    // Shop API
    cost,
    canBuy,
    buy,
    apply,
    tick,
    label,

    // Back-compat direct functions
    Jug,
    Speed,
    Mag,

    // Expose defs (optional for UI)
    defs: DEF
  };

  console.log("[Z_PERKS] loaded (LUX+COMPAT)");
})();
