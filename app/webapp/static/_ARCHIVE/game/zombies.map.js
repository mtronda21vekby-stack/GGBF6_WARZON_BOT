// app/webapp/static/game/zombies.map.js
// Tile-based maps for Zombies Survival
// Symbols:
//  # = wall (collision)
//  . = floor (walkable)
//  Z = zombie spawn
//  P = player spawn
//  C = cover (slows zombies)
//  H = hazard (damage over time)

export const TILE = {
  WALL: "#",
  FLOOR: ".",
  ZSPAWN: "Z",
  PSPAWN: "P",
  COVER: "C",
  HAZARD: "H"
};

export const MAPS = {
  // =========================
  // 🧟 ASHES — RUINS / FIRE
  // =========================
  ashes: {
    id: "ashes",
    name: "Ashes",
    theme: "ruins_fire",
    tileSize: 64,
    width: 21,
    height: 13,
    description: "Сгоревшие руины. Узкие проходы, много choke-point'ов.",

    grid: [
      "#####################",
      "#....Z......C......#",
      "#..######..#####..#.#",
      "#..#....#..#...#..#.#",
      "#..#....#..#...#..#.#",
      "#..####..######..#..#",
      "#......P.......Z...#",
      "#..####..######..#..#",
      "#..#....#..#...#..#.#",
      "#..#....#..#...#..#.#",
      "#..######..#####..#.#",
      "#....Z......C......#",
      "#####################"
    ],

    rules: {
      ambientDamage: 0,      // постоянный урон
      hazardDamage: 8,       // урон от H
      zombieSpeedMul: 1.0,
      visibility: 0.95       // дым/пепел
    }
  },

  // =========================
  // 🧟 FACTORY — INDUSTRIAL
  // =========================
  factory: {
    id: "factory",
    name: "Abandoned Factory",
    theme: "industrial_dark",
    tileSize: 64,
    width: 23,
    height: 14,
    description: "Заброшенный завод. Открытые зоны + смертельные фланги.",

    grid: [
      "#######################",
      "#..Z........C.....Z..#",
      "#..######..#####..##.#",
      "#..#....#..#...#.....#",
      "#..#....#..#...#####.#",
      "#..####..######......#",
      "#........P.......Z...#",
      "#..####..######......#",
      "#..#....#..#...#####.#",
      "#..#....#..#...#.....#",
      "#..######..#####..##.#",
      "#..Z........C.....Z..#",
      "#..............H.....#",
      "#######################"
    ],

    rules: {
      ambientDamage: 0,
      hazardDamage: 12,      // опасные зоны (токсины/электричество)
      zombieSpeedMul: 1.05,
      visibility: 0.9
    }
  }
};

// =========================
// HELPERS
// =========================
export function getMap(id) {
  return MAPS[id] || MAPS.ashes;
}

export function parseMap(map) {
  const walls = [];
  const floors = [];
  const zombieSpawns = [];
  const playerSpawn = { x: 0, y: 0 };
  const covers = [];
  const hazards = [];

  map.grid.forEach((row, y) => {
    [...row].forEach((cell, x) => {
      const pos = { x, y };
      if (cell === TILE.WALL) walls.push(pos);
      if (cell === TILE.FLOOR) floors.push(pos);
      if (cell === TILE.ZSPAWN) zombieSpawns.push(pos);
      if (cell === TILE.PSPAWN) {
        playerSpawn.x = x;
        playerSpawn.y = y;
      }
      if (cell === TILE.COVER) covers.push(pos);
      if (cell === TILE.HAZARD) hazards.push(pos);
    });
  });

  return {
    ...map,
    walls,
    floors,
    zombieSpawns,
    playerSpawn,
    covers,
    hazards
  };
}
