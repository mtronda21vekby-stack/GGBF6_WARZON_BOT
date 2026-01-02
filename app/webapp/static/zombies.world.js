/* =========================================================
   app/webapp/static/zombies.world.js
   FULL WORLD LOGIC: maps + bosses + perks + collisions
   ========================================================= */
(() => {
  "use strict";

  const MAPS = window.BCO_ZOMBIES_MAPS;
  const COLL = window.BCO_ZOMBIES_COLLISIONS;
  const BOSSES = window.BCO_ZOMBIES_BOSSES;
  const PERKS = window.BCO_ZOMBIES_PERKS;

  if (!MAPS || !COLL || !BOSSES) {
    console.error("[BCO_ZOMBIES_WORLD] deps missing");
    return;
  }

  const World = {
    mapName: "Ashes",
    map: null,

    load(mapName) {
      this.mapName = mapName;
      this.map = MAPS.get(mapName);
    },

    applyCollisions(run) {
      if (!this.map) return;

      COLL.collideEntityWithMap(run, this.map, this.map.w, this.map.h);

      for (const z of run.zombies) {
        COLL.collideEntityWithMap(z, this.map, this.map.w, this.map.h);
      }

      COLL.collideBullets(run.bullets, this.map);
    },

    spawnBossIfNeeded(run) {
      if (!this.map || !this.map.bossSpawns) return;

      for (const bs of this.map.bossSpawns) {
        if (bs.wave === run.wave && !run._bossSpawned?.[bs.wave]) {
          const b = BOSSES.create(
            bs.type,
            Math.random() * this.map.w,
            Math.random() * this.map.h
          );
          if (b) {
            run.zombies.push(b);
            run._bossSpawned = run._bossSpawned || {};
            run._bossSpawned[bs.wave] = true;
          }
        }
      }
    },

    applyPerk(run, perkId) {
      const fn = PERKS[perkId];
      if (fn) fn(run);
    }
  };

  // =========================================================
  // HOOK INTO CORE GAME LOOP
  // =========================================================
  if (window.BCO_ZOMBIES) {
    const core = window.BCO_ZOMBIES;

    const _tick = core._tickWorld;
    core._tickWorld = function (run, dt, t) {
      if (!World.map) World.load(run.map || "Ashes");

      World.applyCollisions(run);
      World.spawnBossIfNeeded(run);

      if (_tick) _tick(run, dt, t);
    };

    const _buyPerk = core._buyPerk;
    core._buyPerk = function (run, perkId) {
      World.applyPerk(run, perkId);
      if (_buyPerk) _buyPerk(run, perkId);
    };
  }

  window.BCO_ZOMBIES_WORLD = World;

  console.log("[BCO_ZOMBIES_WORLD] loaded");
})();
