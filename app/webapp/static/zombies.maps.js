/* =========================================================
   BLACK CROWN OPS — ZOMBIES MAPS (Ashes/Astra) [LUX]
   File: app/webapp/static/zombies.maps.js
   Provides: window.BCO_ZOMBIES_MAPS.get(name)
             window.BCO_ZOMBIES_MAPS.list()
             window.BCO_ZOMBIES_MAPS.normalizeWall(wall)
   ========================================================= */
(() => {
  "use strict";

  // Contract:
  // - World coords are centered around (0,0).
  // - Map extents defined by half-size (hw, hh) derived from w/h.
  // - Walls: by default x/y are CENTER of rect (anchor="center").
  //   If you ever want top-left style, set wall.anchor="tl".
  // - Boss spawns: { wave, type } (world/bosses module can use).
  // - Spawn: rings + optional points for curated spawns.

  const MAPS = new Map();

  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }

  function normalizeWall(w) {
    // Supports both center-anchored and top-left anchored definitions.
    const wall = { ...w };
    wall.w = Number(wall.w) || 0;
    wall.h = Number(wall.h) || 0;
    wall.x = Number(wall.x) || 0;
    wall.y = Number(wall.y) || 0;

    wall.anchor = wall.anchor || "center";

    if (wall.anchor === "tl") {
      // convert tl => center
      wall.x = wall.x + wall.w / 2;
      wall.y = wall.y + wall.h / 2;
      wall.anchor = "center";
    }

    // sane minimums
    wall.w = Math.max(2, wall.w);
    wall.h = Math.max(2, wall.h);

    // optional rounding for determinism
    wall.x = Math.round(wall.x);
    wall.y = Math.round(wall.y);
    wall.w = Math.round(wall.w);
    wall.h = Math.round(wall.h);

    // optional material tag (future): "stone", "metal", "wood"
    wall.mat = wall.mat || "stone";

    return wall;
  }

  function mkMap(opts) {
    const name = String(opts?.name || "Ashes");
    const w = Math.max(400, Number(opts?.w) || 2400);
    const h = Math.max(400, Number(opts?.h) || 2400);

    const hw = Math.floor(w / 2);
    const hh = Math.floor(h / 2);

    const walls = Array.isArray(opts?.walls) ? opts.walls.map(normalizeWall) : [];
    const bossSpawns = Array.isArray(opts?.bossSpawns) ? opts.bossSpawns.slice() : [];

    const spawn = {
      // default spawn ring (used by wave spawn if module wants)
      ringMin: Number(opts?.spawn?.ringMin) || 520,
      ringMax: Number(opts?.spawn?.ringMax) || 880,
      // curated spawn points (optional)
      points: Array.isArray(opts?.spawn?.points) ? opts.spawn.points.slice() : []
    };

    const theme = {
      // purely descriptive (future render layers)
      bg: opts?.theme?.bg || (name === "Astra" ? "asphalt" : "ashes"),
      fog: clamp(Number(opts?.theme?.fog ?? (name === "Astra" ? 0.22 : 0.30)), 0, 0.7),
      tint: opts?.theme?.tint || (name === "Astra" ? "cool" : "warm")
    };

    return { name, w, h, hw, hh, walls, bossSpawns, spawn, theme };
  }

  // -------------------------
  // Ashes: open space + chunky cover
  // -------------------------
  MAPS.set("Ashes", mkMap({
    name: "Ashes",
    w: 2400,
    h: 2400,
    walls: [
      { x: -220, y: -520, w: 440, h: 140, mat: "stone" },
      { x: -860, y:  120, w: 420, h: 160, mat: "metal" },
      { x:  440, y:  220, w: 520, h: 180, mat: "stone" },
      { x: -120, y:  640, w: 240, h: 320, mat: "wood"  }
    ],
    bossSpawns: [
      { wave: 5, type: "brute" },
      { wave: 9, type: "spitter" }
    ],
    spawn: {
      ringMin: 560,
      ringMax: 920,
      points: [
        { x: -980, y: -820 },
        { x:  980, y: -820 },
        { x: -980, y:  820 },
        { x:  980, y:  820 }
      ]
    },
    theme: { bg: "ashes", fog: 0.30, tint: "warm" }
  }));

  // -------------------------
  // Astra: lanes + more cover
  // -------------------------
  MAPS.set("Astra", mkMap({
    name: "Astra",
    w: 2400,
    h: 2400,
    walls: [
      { x: -900, y: -260, w: 560, h: 140, mat: "metal" },
      { x: -240, y: -260, w: 480, h: 140, mat: "metal" },
      { x:  420, y: -260, w: 620, h: 140, mat: "metal" },
      { x: -520, y:  260, w: 1040, h: 160, mat: "stone" },
      { x: -900, y:  720, w: 520, h: 140, mat: "stone" },
      { x:  220, y:  720, w: 820, h: 140, mat: "stone" }
    ],
    bossSpawns: [
      { wave: 4, type: "spitter" },
      { wave: 8, type: "brute" },
      { wave: 12, type: "brute" }
    ],
    spawn: {
      ringMin: 520,
      ringMax: 860,
      points: [
        { x: -1040, y: 0 },
        { x:  1040, y: 0 },
        { x: 0, y: -1040 },
        { x: 0, y:  1040 }
      ]
    },
    theme: { bg: "asphalt", fog: 0.22, tint: "cool" }
  }));

  window.BCO_ZOMBIES_MAPS = {
    get(name) {
      return MAPS.get(String(name || "")) || MAPS.get("Ashes");
    },
    list() {
      return Array.from(MAPS.keys());
    },
    normalizeWall
  };

  console.log("[Z_MAPS] loaded (LUX)");
})();
