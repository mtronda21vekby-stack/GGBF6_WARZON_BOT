/* =========================================================
   app/webapp/static/zombies.bosses.js
   BOSSES: brute / warden / necromancer
   ========================================================= */
(() => {
  "use strict";

  function mkBase(type, x, y) {
    return {
      type,
      isBoss: true,
      id: Math.random().toString(16).slice(2),
      x, y,
      vx: 0, vy: 0,
      r: 26,
      hp: 520,
      maxHp: 520,
      spd: 72,
      dmg: 18,

      // спец
      nextSkillAt: 0,
      aura: type === "necromancer" ? "purple" : (type === "warden" ? "blue" : "green")
    };
  }

  function brute(x, y) {
    const z = mkBase("brute", x, y);
    z.r = 30;
    z.hp = z.maxHp = 700;
    z.spd = 68;
    z.dmg = 24;
    return z;
  }

  function warden(x, y) {
    const z = mkBase("warden", x, y);
    z.r = 28;
    z.hp = z.maxHp = 860;
    z.spd = 64;
    z.dmg = 20;
    z.shield = 0.35; // входящий урон * (1-shield)
    return z;
  }

  function necromancer(x, y) {
    const z = mkBase("necromancer", x, y);
    z.r = 26;
    z.hp = z.maxHp = 620;
    z.spd = 78;
    z.dmg = 16;
    z.summonEveryMs = 4500;
    z.nextSkillAt = 0;
    return z;
  }

  function create(type, x, y) {
    const t = String(type || "");
    if (t === "brute") return brute(x, y);
    if (t === "warden") return warden(x, y);
    if (t === "necromancer") return necromancer(x, y);
    return null;
  }

  window.BCO_ZOMBIES_BOSSES = {
    create
  };

  console.log("[BCO_ZOMBIES_BOSSES] loaded");
})();
