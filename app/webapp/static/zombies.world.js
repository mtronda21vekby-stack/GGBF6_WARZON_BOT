/* =========================================================
   app/webapp/static/zombies.world.js  [LUX]
   FULL WORLD LOGIC: maps + collisions + bosses + perks
   Requires:
     - zombies.maps.js
     - zombies.collisions.js
     - zombies.bosses.js (LUX)
     - zombies.perks.js (optional)
   Provides:
     - window.BCO_ZOMBIES_WORLD
   Notes:
     - Works with your upgraded zombies.core.js (LUX COD-ZOMBIES-2D v1)
     - Boss spawning is handled by BOSSES.tick() (preferred) + safe fallback
     - Keeps backward compatibility with older core/world hooks
   ========================================================= */
(() => {
  "use strict";

  const MAPS = window.BCO_ZOMBIES_MAPS;
  const COLL = window.BCO_ZOMBIES_COLLISIONS;
  const BOSSES = window.BCO_ZOMBIES_BOSSES;
  const PERKS = window.BCO_ZOMBIES_PERKS;

  if (!MAPS || !COLL) {
    console.error("[BCO_Z_WORLD] deps missing (maps/collisions)");
    return;
  }

  const World = {
    mapName: "Ashes",
    map: null,

    load(mapName) {
      const name = String(mapName || "Ashes");
      this.mapName = name;
      this.map = MAPS.get(name);
      return this.map;
    },

    ensureMap(CORE) {
      const want = String(CORE?.meta?.map || "Ashes");
      if (!this.map || this.mapName !== want) this.load(want);
      return this.map;
    },

    applyCollisions(CORE) {
      const map = this.ensureMap(CORE);
      if (!map) return;

      const S = CORE.state;

      // player + zombies vs walls
      try { COLL.collideEntityWithMap(S.player, map); } catch {}
      try {
        for (const z of (S.zombies || [])) {
          // bosses are entities too (they have r)
          COLL.collideEntityWithMap(z, map);
        }
      } catch {}

      // bullets vs walls
      try { COLL.collideBullets(S.bullets, map); } catch {}
    },

    // Prefer BOSSES.tick(), because LUX bosses module handles:
    // - wave-based spawns from map.bossSpawns
    // - abilities + projectiles + telegraphs
    // - optional coin drops
    tickBosses(CORE, dt, tms) {
      const map = this.ensureMap(CORE);
      if (!BOSSES) return;

      try {
        if (typeof BOSSES.tick === "function") {
          BOSSES.tick(CORE, dt, tms, map || null);
          return;
        }
      } catch {}

      // Fallback: old-style spawnBossIfNeeded (minimal)
      try {
        if (!map || !map.bossSpawns) return;
        const S = CORE.state;
        const w = Number(S.wave || 1) | 0;
        S._bossSpawned = S._bossSpawned || {};

        for (const bs of map.bossSpawns) {
          const wave = Number(bs.wave || 0) | 0;
          if (wave !== w) continue;

          const id = `${map.name || CORE.meta.map}:${wave}:${String(bs.type || "brute")}`;
          if (S._bossSpawned[id]) continue;

          const ang = Math.random() * Math.PI * 2;
          const rr = (map.spawn?.ringMax || CORE.cfg?.wave?.spawnRingMax || 880) + 140;
          const bx = S.player.x + Math.cos(ang) * rr;
          const by = S.player.y + Math.sin(ang) * rr;

          const b = (BOSSES?.create) ? BOSSES.create(bs.type, bx, by, { wave: w }) : null;
          if (b) {
            (S.zombies || (S.zombies = [])).push(b);
            S._bossSpawned[id] = true;
          }
        }
      } catch {}
    },

    applyPerk(CORE, perkId) {
      try {
        const fn = PERKS?.[String(perkId || "")];
        if (typeof fn === "function") fn(CORE);
      } catch {}
    }
  };

  // =========================================================
  // HOOK INTO CORE GAME LOOP
  // =========================================================
  if (window.BCO_ZOMBIES_CORE) {
    const core = window.BCO_ZOMBIES_CORE;

    const prevTick = core._tickWorld;
    core._tickWorld = function (CORE, dt, tms) {
      try { World.ensureMap(core); } catch {}

      // collisions first (so bosses/zombies don't clip during special moves)
      try { World.applyCollisions(core); } catch {}

      // bosses logic (spawns + abilities + projectiles)
      try { World.tickBosses(core, dt, tms); } catch {}

      // allow chaining
      try { if (typeof prevTick === "function") prevTick(CORE, dt, tms); } catch {}
    };

    const prevBuy = core._buyPerk;
    core._buyPerk = function (CORE, perkId) {
      try { World.applyPerk(core, perkId); } catch {}
      try { if (typeof prevBuy === "function") prevBuy(CORE, perkId); } catch {}
    };

    // If bosses module supports install, do it once (safe)
    try {
      if (BOSSES?.install && !core._bossInstalled) {
        BOSSES.install(core, () => World.ensureMap(core));
        core._bossInstalled = true;
      }
    } catch {}
  }

  window.BCO_ZOMBIES_WORLD = World;
  console.log("[BCO_Z_WORLD] loaded (LUX)");
})();
