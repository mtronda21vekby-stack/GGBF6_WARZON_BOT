/* =========================================================
   app/webapp/static/zombies.world.js  [LUX | 3D-READY]
   FULL WORLD LOGIC: maps + collisions + bosses + perks (+ optional map events)
   Requires:
     - zombies.maps.js
     - zombies.collisions.js
   Optional:
     - zombies.bosses.js (LUX)
     - zombies.perks.js
     - zombies.assets.js (skins/atlas)
   Provides:
     - window.BCO_ZOMBIES_WORLD

   Design:
     - World is PURE "world systems": map selection, collision, boss tick, map events hooks.
     - Core remains gameplay truth; World only calls safe helpers and optional modules.
     - 3D-ready: stable, deterministic order; no canvas/UI references; can be reused by 3D renderer.

   Guarantees:
     ✅ NO UI changes
     ✅ Backward compatible with older core hooks
     ✅ Safe if CORE loads before/after world
     ✅ Avoids double-wiring (idempotent attach)
   ========================================================= */
(() => {
  "use strict";

  const MAPS = () => window.BCO_ZOMBIES_MAPS || null;
  const COLL = () => window.BCO_ZOMBIES_COLLISIONS || null;
  const BOSSES = () => window.BCO_ZOMBIES_BOSSES || null;
  const PERKS = () => window.BCO_ZOMBIES_PERKS || null;
  const ASSETS = () => window.BCO_ZOMBIES_ASSETS || null;

  function safe(fn, fallback) {
    try { return fn(); } catch { return fallback; }
  }

  function now() {
    return (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now();
  }

  // ---------------------------------------------------------
  // WORLD
  // ---------------------------------------------------------
  const World = {
    mapName: "Ashes",
    map: null,

    // lightweight event state (optional)
    _evt: {
      lastWave: 0,
      lastBossWave: 0,
      lastMapName: "",
      lastTickAt: 0
    },

    load(mapName) {
      const maps = MAPS();
      if (!maps?.get) return null;

      const name = String(mapName || "Ashes");
      this.mapName = name;
      this.map = safe(() => maps.get(name), null);

      // optional: map-defined onLoad hook
      safe(() => {
        const m = this.map;
        if (m && typeof m.onLoad === "function") m.onLoad(m);
        return true;
      }, false);

      return this.map;
    },

    ensureMap(CORE) {
      const want = String(CORE?.meta?.map || "Ashes");
      if (!this.map || this.mapName !== want) {
        this.load(want);
        this._evt.lastMapName = want;

        // optional: tell assets module about map (skins/tiles in future)
        safe(() => {
          const A = ASSETS();
          if (A?.setMap && typeof A.setMap === "function") A.setMap(want);
          return true;
        }, false);
      }
      return this.map;
    },

    // -------------------------------------------------------
    // Collisions (authoritative geometry from collisions module)
    // Order matters: player -> zombies/bosses -> bullets
    // -------------------------------------------------------
    applyCollisions(CORE) {
      const coll = COLL();
      if (!coll) return false;

      const map = this.ensureMap(CORE);
      if (!map) return false;

      const S = CORE?.state;
      if (!S) return false;

      // Player vs map
      safe(() => {
        if (coll.collideEntityWithMap) {
          // allow core to pass either {x,y,r} or its player object
          coll.collideEntityWithMap(S.player, map);
        }
        return true;
      }, false);

      // Zombies/Bosses vs map
      safe(() => {
        if (coll.collideEntityWithMap && Array.isArray(S.zombies)) {
          for (const z of S.zombies) coll.collideEntityWithMap(z, map);
        }
        return true;
      }, false);

      // Bullets vs map
      safe(() => {
        if (coll.collideBullets && Array.isArray(S.bullets)) coll.collideBullets(S.bullets, map);
        return true;
      }, false);

      return true;
    },

    // -------------------------------------------------------
    // Boss systems (preferred = BOSSES.tick)
    // -------------------------------------------------------
    tickBosses(CORE, dt, tms) {
      const bosses = BOSSES();
      if (!bosses) return false;

      const map = this.ensureMap(CORE);
      const S = CORE?.state;
      if (!S) return false;

      // Preferred: LUX bosses module handles spawns + abilities + projectiles
      const ok = safe(() => {
        if (typeof bosses.tick === "function") {
          bosses.tick(CORE, dt, tms, map || null);
          return true;
        }
        return false;
      }, false);
      if (ok) return true;

      // Fallback spawn (minimal, compatible with your older boss configs)
      safe(() => {
        if (!map || !map.bossSpawns) return false;

        const w = (Number(S.wave || 1) | 0);
        S._bossSpawned = S._bossSpawned || {};

        for (const bs of map.bossSpawns) {
          const wave = (Number(bs.wave || 0) | 0);
          if (wave !== w) continue;

          const type = String(bs.type || "brute");
          const id = `${String(map.name || CORE?.meta?.map)}:${wave}:${type}`;
          if (S._bossSpawned[id]) continue;

          const ring = (map.spawn?.ringMax || CORE?.cfg?.wave?.spawnRingMax || 880) + 160;
          const ang = Math.random() * Math.PI * 2;
          const bx = S.player.x + Math.cos(ang) * ring;
          const by = S.player.y + Math.sin(ang) * ring;

          const b = (bosses.create && typeof bosses.create === "function")
            ? bosses.create(type, bx, by, { wave: w, map: map.name || CORE?.meta?.map })
            : null;

          if (b) {
            (S.zombies || (S.zombies = [])).push(b);
            S._bossSpawned[id] = true;
            this._evt.lastBossWave = w;
          }
        }
        return true;
      }, false);

      return true;
    },

    // -------------------------------------------------------
    // Perks hook (optional)
    // -------------------------------------------------------
    applyPerk(CORE, perkId) {
      const perks = PERKS();
      if (!perks) return false;

      return safe(() => {
        const fn = perks?.[String(perkId || "")];
        if (typeof fn === "function") {
          fn(CORE);
          return true;
        }
        return false;
      }, false);
    },

    // -------------------------------------------------------
    // Map events hook (optional future: relic quest, zones, etc.)
    // Keeps 3D-ready structure: everything is CORE state mutations only.
    // -------------------------------------------------------
    tickMapEvents(CORE, dt, tms) {
      const map = this.ensureMap(CORE);
      const S = CORE?.state;
      if (!map || !S) return false;

      // Optional map.tick(map, CORE, dt, tms)
      safe(() => {
        if (typeof map.tick === "function") map.tick(map, CORE, dt, tms);
        return true;
      }, false);

      // Optional: detect wave changes for map scripting
      const w = (Number(S.wave || 1) | 0);
      if (w !== (this._evt.lastWave | 0)) {
        this._evt.lastWave = w;

        safe(() => {
          if (typeof map.onWave === "function") map.onWave(map, CORE, w);
          return true;
        }, false);
      }

      return true;
    },

    // -------------------------------------------------------
    // Single tick entrypoint (used by core hook)
    // Order: map->collisions->bosses->map events
    // -------------------------------------------------------
    tick(CORE, dt, tms) {
      // soft guard
      if (!CORE?.state) return false;

      this.ensureMap(CORE);

      // Collision first (stable geometry)
      this.applyCollisions(CORE);

      // Boss systems (spawns/abilities/projectiles)
      this.tickBosses(CORE, dt, tms);

      // Any map scripting/events (optional)
      this.tickMapEvents(CORE, dt, tms);

      this._evt.lastTickAt = tms || now();
      return true;
    },

    // -------------------------------------------------------
    // Attach / wiring (idempotent)
    // -------------------------------------------------------
    attach(core) {
      if (!core) return false;
      if (core._bcoWorldAttached) return true;
      core._bcoWorldAttached = true;

      // Chain world tick into core._tickWorld
      const prevTick = core._tickWorld;
      core._tickWorld = function (CORE_ARG, dt, tms) {
        // prefer CORE_ARG but allow using captured core safely
        const C = CORE_ARG || core;
        safe(() => World.tick(C, dt, tms), false);
        safe(() => (typeof prevTick === "function") ? prevTick(CORE_ARG, dt, tms) : null, null);
      };

      // Chain perks into core._buyPerk
      const prevBuy = core._buyPerk;
      core._buyPerk = function (CORE_ARG, perkId) {
        const C = CORE_ARG || core;
        safe(() => World.applyPerk(C, perkId), false);
        safe(() => (typeof prevBuy === "function") ? prevBuy(CORE_ARG, perkId) : null, null);
      };

      // If bosses module supports install, do it once (safe)
      safe(() => {
        const bosses = BOSSES();
        if (bosses?.install && !core._bossInstalled) {
          bosses.install(core, () => World.ensureMap(core));
          core._bossInstalled = true;
        }
        return true;
      }, false);

      // prime map
      safe(() => World.ensureMap(core), false);

      return true;
    },

    // If core loads after world, caller can call World.tryAttach()
    tryAttach() {
      const core = window.BCO_ZOMBIES_CORE;
      if (!core) return false;
      return this.attach(core);
    }
  };

  // ---------------------------------------------------------
  // Export + auto-wire if possible
  // ---------------------------------------------------------
  window.BCO_ZOMBIES_WORLD = World;

  // Attempt attach now; if CORE not ready yet, retry a few times (safe, no loops forever)
  (function bootstrapAttach(attempt = 0) {
    if (World.tryAttach()) {
      console.log("[BCO_Z_WORLD] loaded + attached (LUX | 3D-ready)");
      return;
    }
    if (attempt >= 12) {
      console.log("[BCO_Z_WORLD] loaded (waiting CORE attach)");
      return;
    }
    setTimeout(() => bootstrapAttach(attempt + 1), 120);
  })();

})();
