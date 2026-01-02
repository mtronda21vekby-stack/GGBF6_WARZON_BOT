/* =========================================================
   app/webapp/static/zombies.maps.js
   ========================================================= */
(() => {
  "use strict";

  const MAPS = {
    Ashes: {
      w: 2000,
      h: 2000,
      walls: [
        { x: 300, y: 300, w: 1400, h: 40 },
        { x: 300, y: 1660, w: 1400, h: 40 },
        { x: 300, y: 300, w: 40, h: 1400 },
        { x: 1660, y: 300, w: 40, h: 1400 },

        { x: 600, y: 600, w: 300, h: 40 },
        { x: 1100, y: 900, w: 40, h: 300 }
      ],
      bossSpawns: [
        { wave: 5, type: "brute" },
        { wave: 10, type: "tank" }
      ]
    },

    Astra: {
      w: 2200,
      h: 2200,
      walls: [
        { x: 400, y: 400, w: 1400, h: 40 },
        { x: 400, y: 1760, w: 1400, h: 40 },
        { x: 400, y: 400, w: 40, h: 1400 },
        { x: 1760, y: 400, w: 40, h: 1400 },

        { x: 900, y: 700, w: 400, h: 40 },
        { x: 700, y: 1100, w: 40, h: 400 }
      ],
      bossSpawns: [
        { wave: 7, type: "brute" },
        { wave: 14, type: "tank" }
      ]
    }
  };

  window.BCO_ZOMBIES_MAPS = {
    get(name) {
      return MAPS[name] || MAPS.Ashes;
    },
    all: MAPS
  };
})();
