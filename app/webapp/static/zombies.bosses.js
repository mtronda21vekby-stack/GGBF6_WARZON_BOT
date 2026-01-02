/* =========================================================
   BLACK CROWN OPS — ZOMBIES BOSSES
   File: app/webapp/static/zombies.bosses.js
   Provides: window.BCO_ZOMBIES_BOSSES.create(type,x,y)
   ========================================================= */
(() => {
  "use strict";

  const BOSSES = {
    create(type, x, y) {
      const t = String(type || "brute").toLowerCase();
      if (t === "spitter") return mkSpitter(x, y);
      return mkBrute(x, y);
    }
  };

  function mkBrute(x, y) {
    return {
      kind: "brute",
      x, y, vx: 0, vy: 0,
      hp: 260,
      sp: 120,
      r: 26,
      nextTouchAt: 0
    };
  }

  function mkSpitter(x, y) {
    return {
      kind: "spitter",
      x, y, vx: 0, vy: 0,
      hp: 160,
      sp: 155,
      r: 20,
      nextTouchAt: 0
    };
  }

  window.BCO_ZOMBIES_BOSSES = BOSSES;
  console.log("[Z_BOSSES] loaded");
})();
