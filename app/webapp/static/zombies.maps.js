/* =========================================================
   BLACK CROWN OPS — ZOMBIES MAPS (Ashes/Astra)
   File: app/webapp/static/zombies.maps.js
   Provides: window.BCO_ZOMBIES_MAPS.get(name)
   ========================================================= */
(() => {
  "use strict";

  // Super-safe simple maps: world extents + walls for collisions module
  // coords are in world units (same space as CORE state)

  const MAPS = new Map();

  function mkMap(name, w, h, walls, bossSpawns) {
    return {
      name, w, h,
      // wall rects: {x,y,w,h}
      walls: walls || [],
      bossSpawns: bossSpawns || []
    };
  }

  // Ashes: more open, few chunky blocks
  MAPS.set("Ashes", mkMap(
    "Ashes",
    2400, 2400,
    [
      { x: -220, y: -520, w: 440, h: 140 },
      { x: -860, y:  120, w: 420, h: 160 },
      { x:  440, y:  220, w: 520, h: 180 },
      { x: -120, y:  640, w: 240, h: 320 }
    ],
    [
      { wave: 5, type: "brute" },
      { wave: 9, type: "spitter" }
    ]
  ));

  // Astra: tighter lanes, more cover
  MAPS.set("Astra", mkMap(
    "Astra",
    2400, 2400,
    [
      { x: -900, y: -260, w: 560, h: 140 },
      { x: -240, y: -260, w: 480, h: 140 },
      { x:  420, y: -260, w: 620, h: 140 },
      { x: -520, y:  260, w: 1040, h: 160 },
      { x: -900, y:  720, w: 520, h: 140 },
      { x:  220, y:  720, w: 820, h: 140 }
    ],
    [
      { wave: 4, type: "spitter" },
      { wave: 8, type: "brute" },
      { wave: 12, type: "brute" }
    ]
  ));

  window.BCO_ZOMBIES_MAPS = {
    get(name) {
      return MAPS.get(String(name || "")) || MAPS.get("Ashes");
    },
    list() {
      return Array.from(MAPS.keys());
    }
  };

  console.log("[Z_MAPS] loaded");
})();
