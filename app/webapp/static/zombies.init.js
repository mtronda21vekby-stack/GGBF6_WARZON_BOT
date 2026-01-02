/* =========================================================
   BLACK CROWN OPS — ZOMBIES INIT (Public API)  [LUX | 3D-READY]
   File: app/webapp/static/zombies.init.js
   Exposes: window.BCO_ZOMBIES (single API)

   Goals (NO UI redesign, systems only):
     ✅ Auto-install BOSSES into CORE if available
     ✅ Wire PERKS module into CORE._buyPerk (if perks module exists)
     ✅ Optional WORLD hook wiring into CORE._tickWorld (if world module exists)
     ✅ Optional MAPS/COLLISIONS presence check (soft)
     ✅ Helpers: listMaps/listWeapons/listPerks/getState/getMeta/getSnapshot/onSnapshot/health
     ✅ Backward compatible with existing calls

   LUX PATCHES (requested):
     ✅ Player skins scale smaller x1.5  (playerScale = 1/1.5)
     ✅ Player feels faster vs zombies (player speed up, zombie speed down)

   Requires (typical):
     - zombies.core.js
     - zombies.game.js
     - zombies.render.js
   Optional:
     - zombies.bosses.js
     - zombies.perks.js
     - zombies.world.js
     - zombies.maps.js
     - zombies.collisions.js
     - zombies.assets.js
   ========================================================= */
(() => {
  "use strict";

  const GAME = () => window.BCO_ZOMBIES_GAME || null;
  const CORE = () => window.BCO_ZOMBIES_CORE || null;

  let _installed = false;

  function safe(fn, fallback) {
    try { return fn(); } catch { return fallback; }
  }

  // --------------------------
  // LUX PATCHES (NO UI change)
  // --------------------------
  function applyLuxPatches(core) {
    return safe(() => {
      if (!core || !core.cfg) return false;
      if (core._bcoLuxPatched) return true;

      // 1) SCALE: skins/player render smaller by 1.5x
      // Renderer/Assets may consume these globals. We don't assume their existence.
      const scale = window.BCO_ZOMBIES_SCALE || {};
      scale.player = 1 / 1.5;     // ~0.6667
      scale.zombie = scale.zombie ?? 1.0;
      scale.pickup = scale.pickup ?? 1.0;
      window.BCO_ZOMBIES_SCALE = scale;

      // Best-effort: if renderer/assets expose setters, call them safely.
      try {
        const R = window.BCO_ZOMBIES_RENDER || window.BCO_ZOMBIES_RENDERER || window.BCO_ZOMBIES_DRAW;
        if (R && typeof R.setScale === "function") R.setScale(scale);
        if (R && typeof R.setPlayerScale === "function") R.setPlayerScale(scale.player);
      } catch {}

      try {
        const A = window.BCO_ZOMBIES_ASSETS;
        if (A && typeof A.setPlayerScale === "function") A.setPlayerScale(scale.player);
        if (A && typeof A.setScale === "function") A.setScale(scale);
      } catch {}

      // 2) SPEED FEEL: player faster vs zombies (balance-friendly)
      // Keep it soft, but noticeable.
      const cfg = core.cfg;

      if (cfg.player && Number.isFinite(cfg.player.speed)) {
        cfg.player.speed = Math.round(cfg.player.speed * 1.18);
      }

      if (cfg.zombie && Number.isFinite(cfg.zombie.baseSpeed)) {
        cfg.zombie.baseSpeed = Math.round(cfg.zombie.baseSpeed * 0.92);
      }

      // Also: if there are already spawned zombies with z.sp, adjust current run speed a bit
      try {
        const S = core.state;
        if (S && Array.isArray(S.zombies)) {
          for (const z of S.zombies) {
            if (!z || !Number.isFinite(z.sp)) continue;
            z.sp = z.sp * 0.92;
          }
        }
      } catch {}

      core._bcoLuxPatched = true;
      return true;
    }, false);
  }

  function onceInstallBosses(core) {
    return safe(() => {
      const BOSSES = window.BCO_ZOMBIES_BOSSES;
      if (!BOSSES?.install || typeof BOSSES.install !== "function") return false;

      // avoid double install even if init reloaded
      if (core._bcoBossesInstalled) return true;

      BOSSES.install(core, () => {
        try { return window.BCO_ZOMBIES_MAPS?.get?.(core?.meta?.map) || null; } catch { return null; }
      });

      core._bcoBossesInstalled = true;
      return true;
    }, false);
  }

  function onceWirePerks(core) {
    return safe(() => {
      const PERKS = window.BCO_ZOMBIES_PERKS;
      if (!PERKS) return false;

      if (core._bcoPerksWired) return true;

      const prev = core._buyPerk;

      core._buyPerk = function (CORE_ARG, perkId) {
        // 1) Apply perk effect from perks module
        try {
          const fn = PERKS?.[String(perkId || "")];
          if (typeof fn === "function") fn(CORE_ARG);
        } catch {}

        // 2) keep previous hook if existed
        try { if (typeof prev === "function") prev(CORE_ARG, perkId); } catch {}
      };

      core._bcoPerksWired = true;
      return true;
    }, false);
  }

  function onceWireWorld(core) {
    return safe(() => {
      const WORLD = window.BCO_ZOMBIES_WORLD;
      if (!WORLD) return false;

      if (core._bcoWorldWired) return true;

      // If world provides tick(core, dt, tms) — attach it
      const prev = core._tickWorld;
      core._tickWorld = function (CORE_ARG, dt, tms) {
        try {
          if (typeof WORLD.tick === "function") WORLD.tick(CORE_ARG, dt, tms);
        } catch {}

        try { if (typeof prev === "function") prev(CORE_ARG, dt, tms); } catch {}
      };

      core._bcoWorldWired = true;
      return true;
    }, false);
  }

  function installOnce() {
    if (_installed) return true;
    _installed = true;

    const core = CORE();
    if (!core) return false;

    // LUX patches first (safe)
    applyLuxPatches(core);

    // 1) Bosses (optional)
    onceInstallBosses(core);

    // 2) Perks -> CORE._buyPerk (optional)
    onceWirePerks(core);

    // 3) World systems hook (optional)
    onceWireWorld(core);

    return true;
  }

  function ensureInstalled() {
    installOnce();

    // If init loads before optional modules, allow re-wire later
    // (safe: checks flags)
    const core = CORE();
    if (core) {
      // Re-apply lux patches if something reloaded core/cfg
      applyLuxPatches(core);

      onceInstallBosses(core);
      onceWirePerks(core);
      onceWireWorld(core);
    }
    return true;
  }

  // --------------------------
  // Helpers
  // --------------------------
  function listMaps() {
    return safe(() => window.BCO_ZOMBIES_MAPS?.list?.() || ["Ashes"], ["Ashes"]);
  }

  function listWeapons() {
    return safe(() => Object.keys(CORE()?.cfg?.weapons || { SMG: 1, AR: 1, SG: 1 }), ["SMG", "AR", "SG"]);
  }

  function listPerks() {
    const core = CORE();
    return safe(() => Object.keys(core?.cfg?.perks || { Jug: 1, Speed: 1, Mag: 1, Armor: 1 }), ["Jug", "Speed", "Mag", "Armor"]);
  }

  function getState() {
    const c = CORE();
    return c?.state ? c.state : null;
  }

  function getMeta() {
    const c = CORE();
    return c?.meta ? c.meta : null;
  }

  function getSnapshot() {
    const g = GAME();
    if (g?.getSnapshot) return safe(() => g.getSnapshot(), null);
    const c = CORE();
    if (c?.getFrameData) return safe(() => c.getFrameData(), null);
    return null;
  }

  function onSnapshot(cb) {
    const g = GAME();
    if (g?.onSnapshot) return safe(() => g.onSnapshot(cb), false);
    return false;
  }

  function health() {
    const c = CORE();
    const g = GAME();
    return {
      ok: !!(c && g),
      core: !!c,
      game: !!g,
      render: !!window.BCO_ZOMBIES_RENDER,
      maps: !!window.BCO_ZOMBIES_MAPS,
      collisions: !!window.BCO_ZOMBIES_COLLISIONS,
      bosses: !!window.BCO_ZOMBIES_BOSSES,
      perks: !!window.BCO_ZOMBIES_PERKS,
      world: !!window.BCO_ZOMBIES_WORLD,
      assets: !!window.BCO_ZOMBIES_ASSETS,

      // expose LUX scalars for quick debug
      scale: window.BCO_ZOMBIES_SCALE || null
    };
  }

  // --------------------------
  // Public API
  // --------------------------
  const API = {
    // overlay
    open() {
      ensureInstalled();
      return GAME()?.open?.() ?? false;
    },

    close() {
      return GAME()?.close?.() ?? false;
    },

    // run control
    start(mode = "arcade", opts = {}) {
      // opts: { map, character, skin, weaponKey }
      ensureInstalled();
      return GAME()?.start?.(mode, opts) ?? false;
    },

    // convenience (explicit modes)
    startArcade(opts = {}) {
      ensureInstalled();
      return GAME()?.start?.("arcade", opts) ?? false;
    },

    startRoguelike(opts = {}) {
      ensureInstalled();
      return GAME()?.start?.("roguelike", opts) ?? false;
    },

    stop(reason = "manual") {
      return GAME()?.stop?.(reason) ?? false;
    },

    // runtime tweaks
    setMode(mode) {
      ensureInstalled();
      return GAME()?.setMode?.(mode) ?? "arcade";
    },

    setMap(name) {
      ensureInstalled();
      return GAME()?.setMap?.(name) ?? "Ashes";
    },

    setCharacter(character, skin) {
      ensureInstalled();
      return GAME()?.setCharacter?.(character, skin) ?? { character, skin };
    },

    setWeapon(key) {
      ensureInstalled();
      return GAME()?.setWeapon?.(key) ?? "SMG";
    },

    buyPerk(id) {
      ensureInstalled();
      return GAME()?.buyPerk?.(id) ?? false;
    },

    reload() {
      ensureInstalled();
      return GAME()?.reload?.() ?? false;
    },

    usePlate() {
      ensureInstalled();
      return GAME()?.usePlate?.() ?? false;
    },

    sendResult(reason) {
      return GAME()?.sendResult?.(reason) ?? false;
    },

    // 3D-ready IO bridge (optional)
    getSnapshot,
    onSnapshot,

    getInput() {
      ensureInstalled();
      const g = GAME();
      if (g?.getInput) return safe(() => g.getInput(), null);
      return null;
    },

    setInput(obj) {
      ensureInstalled();
      const g = GAME();
      if (g?.setInput) return safe(() => g.setInput(obj), false);
      return false;
    },

    // helpers (lux)
    listMaps,
    listWeapons,
    listPerks,
    getState,
    getMeta,

    // diagnostics
    health
  };

  // auto-install on load (safe)
  ensureInstalled();

  window.BCO_ZOMBIES = API;
  console.log("[Z_INIT] BCO_ZOMBIES exported (LUX | 3D-ready) | patches:", window.BCO_ZOMBIES_SCALE || null);
})();
