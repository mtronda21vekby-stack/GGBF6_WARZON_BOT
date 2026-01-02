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

    applyCollisions(CORE) {
      if (!this.map) return;
      const S = CORE.state;

      // player + zombies vs walls
      COLL.collideEntityWithMap(S.player, this.map);
      for (const z of S.zombies) COLL.collideEntityWithMap(z, this.map);

      // bullets vs walls
      COLL.collideBullets(S.bullets, this.map);
    },

    spawnBossIfNeeded(CORE) {
      if (!this.map || !this.map.bossSpawns) return;
      const S = CORE.state;

      for (const bs of this.map.bossSpawns) {
        if (bs.wave === S.wave && !S._bossSpawned?.[bs.wave]) {
          const b = BOSSES.create(bs.type, S.player.x + (Math.random() * 400 - 200), S.player.y + (Math.random() * 400 - 200));
          if (b) {
            S.zombies.push(b);
            S._bossSpawned = S._bossSpawned || {};
            S._bossSpawned[bs.wave] = true;
          }
        }
      }
    },

    applyPerk(CORE, perkId) {
      const fn = PERKS?.[perkId];
      if (fn) fn(CORE);
    }
  };

  // =========================================================
  // HOOK INTO CORE GAME LOOP
  // =========================================================
  if (window.BCO_ZOMBIES_CORE) {
    const core = window.BCO_ZOMBIES_CORE;

    const prevTick = core._tickWorld;
    core._tickWorld = function (CORE, dt, t) {
      if (!World.map) World.load(core.meta.map || "Ashes");
      World.applyCollisions(core);
      World.spawnBossIfNeeded(core);
      if (prevTick) prevTick(CORE, dt, t);
    };

    const prevBuy = core._buyPerk;
    core._buyPerk = function (CORE, perkId) {
      World.applyPerk(core, perkId);
      if (prevBuy) prevBuy(CORE, perkId);
    };
  }

  window.BCO_ZOMBIES_WORLD = World;
  console.log("[BCO_ZOMBIES_WORLD] loaded");
})();
