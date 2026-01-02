// =========================================================
// ZOMBIES MAPS — Ashes / Astra
// =========================================================
(() => {
  const MAPS = {
    Ashes: {
      id: "Ashes",
      bg: "#0b0b12",
      grid: 64,
      walls: [
        { x: 200, y: 300, w: 300, h: 40 },
        { x: 700, y: 180, w: 40, h: 260 }
      ],
      spawnZones: [
        { x: 0, y: 0, w: 100, h: 600 },
        { x: 900, y: 0, w: 100, h: 600 }
      ]
    },

    Astra: {
      id: "Astra",
      bg: "#070a10",
      grid: 72,
      walls: [
        { x: 350, y: 260, w: 420, h: 36 },
        { x: 520, y: 100, w: 36, h: 240 }
      ],
      spawnZones: [
        { x: 0, y: 0, w: 120, h: 700 },
        { x: 880, y: 0, w: 120, h: 700 }
      ]
    }
  };

  window.BCO_ZOMBIES_MAPS = {
    MAPS,
    get(name) {
      return MAPS[name] || MAPS.Ashes;
    }
  };
})();
