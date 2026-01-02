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
      assets: !!window.BCO_ZOMBIES_ASSETS
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
  console.log("[Z_INIT] BCO_ZOMBIES exported (LUX | 3D-ready)");
})();
