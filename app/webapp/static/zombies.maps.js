/* =========================================================
   app/webapp/static/zombies.maps.js
   MAPS: Ashes / Astra + walls + boss spawns
   ========================================================= */
(() => {
  "use strict";

  function rect(x, y, w, h) { return { x, y, w, h }; }

  const ASHES = {
    name: "Ashes",
    w: 2200,
    h: 1400,

    // простая геометрия для коллизий + визуала
    walls: [
      // рамка
      rect(0, 0, 2200, 40),
      rect(0, 1360, 2200, 40),
      rect(0, 0, 40, 1400),
      rect(2160, 0, 40, 1400),

      // центр-обломки
      rect(860, 520, 480, 70),
      rect(980, 650, 240, 220),

      // левый двор
      rect(220, 260, 140, 520),
      rect(380, 420, 220, 90),

      // правый двор
      rect(1780, 300, 160, 520),
      rect(1540, 440, 220, 90)
    ],

    // волны с боссами
    bossSpawns: [
      { wave: 5, type: "brute" },
      { wave: 10, type: "warden" },
      { wave: 15, type: "necromancer" }
    ]
  };

  const ASTRA = {
    name: "Astra",
    w: 2400,
    h: 1500,

    walls: [
      // рамка
      rect(0, 0, 2400, 40),
      rect(0, 1460, 2400, 40),
      rect(0, 0, 40, 1500),
      rect(2360, 0, 40, 1500),

      // "лаборатория" блоки
      rect(540, 240, 520, 90),
      rect(540, 330, 90, 520),
      rect(970, 420, 520, 90),

      rect(1540, 280, 620, 90),
      rect(1900, 370, 90, 520),
      rect(1400, 600, 520, 90),

      // центральный круг (квадратно)
      rect(1070, 760, 260, 260)
    ],

    bossSpawns: [
      { wave: 6, type: "brute" },
      { wave: 12, type: "warden" },
      { wave: 18, type: "necromancer" }
    ]
  };

  const byName = new Map([
    ["Ashes", ASHES],
    ["Astra", ASTRA]
  ]);

  window.BCO_ZOMBIES_MAPS = {
    get(name) {
      return byName.get(String(name || "Ashes")) || ASHES;
    },
    list() {
      return ["Ashes", "Astra"];
    }
  };

  console.log("[BCO_ZOMBIES_MAPS] loaded");
})();
