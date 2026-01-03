// app/webapp/static/bco.engine.js
(() => {
  "use strict";

  // BCO_ENGINE: single stable facade for Zombies engine.
  // Goal: no matter what internal engine exists (BCO_ZOMBIES or BCO_ZOMBIES_CORE),
  // UI talks to ONE object: window.BCO_GAME.

  const W = window;

  function pickEngine() {
    return W.BCO_ZOMBIES || W.BCO_ZOMBIES_CORE || null;
  }

  function safe(fn) {
    try { return fn(); } catch { return undefined; }
  }

  function ensureInputBridge() {
    if (!W.BCO_ZOMBIES_INPUT || typeof W.BCO_ZOMBIES_INPUT !== "object") {
      W.BCO_ZOMBIES_INPUT = {
        move: { x: 0, y: 0 },
        aim: { x: 0, y: 0 },
        firing: false,
        updatedAt: 0
      };
    }
    return W.BCO_ZOMBIES_INPUT;
  }

  function makeEventBus() {
    const map = new Map();
    return {
      on(evt, fn) {
        if (!evt || typeof fn !== "function") return () => {};
        if (!map.has(evt)) map.set(evt, new Set());
        map.get(evt).add(fn);
        return () => map.get(evt)?.delete(fn);
      },
      emit(evt, payload) {
        const set = map.get(evt);
        if (!set) return;
        for (const fn of Array.from(set)) {
          try { fn(payload); } catch {}
        }
      }
    };
  }

  const bus = makeEventBus();

  // We expose ONE stable API: window.BCO_GAME
  const BCO_GAME = {
    // read-only: which engine is active right now
    get engine() { return pickEngine(); },

    // events
    on(evt, fn) { return bus.on(evt, fn); },

    // attach canvas (best-effort across engines)
    setCanvas(canvas) {
      const e = pickEngine();
      if (!e || !canvas) return false;

      let ok = false;
      ok = !!safe(() => e.setCanvas?.(canvas)) || ok;
      ok = !!safe(() => e.canvas?.(canvas)) || ok;
      ok = !!safe(() => e.attach?.(canvas)) || ok;

      // some cores expect resize after canvas attach
      ok = !!safe(() => e.resize?.(canvas.clientWidth || 1, canvas.clientHeight || 1)) || ok;
      ok = !!safe(() => W.BCO_ZOMBIES_CORE?.resize?.(canvas.width || 1, canvas.height || 1)) || ok;

      return ok;
    },

    // open/start/stop (best-effort)
    open(opts = {}) {
      const e = pickEngine();
      if (!e) return false;
      let ok = false;
      ok = !!safe(() => e.open?.(opts)) || ok;
      ok = !!safe(() => e.start?.(opts)) || ok;
      return ok;
    },

    start(opts = {}) {
      const e = pickEngine();
      if (!e) return false;
      let ok = false;

      ok = !!safe(() => e.start?.(opts)) || ok;

      // compatibility: some core uses start(mode,w,h,meta)
      if (!ok && W.BCO_ZOMBIES_CORE?.start) {
        const mode = String(opts.mode || "arcade");
        const w = Number(opts.w || opts.width || 1) || 1;
        const h = Number(opts.h || opts.height || 1) || 1;
        ok = !!safe(() => W.BCO_ZOMBIES_CORE.start(mode, w, h, opts.meta || opts));
      }

      return ok;
    },

    stop(reason = "manual") {
      const e = pickEngine();
      let ok = false;
      ok = !!safe(() => e?.stop?.(reason)) || ok;
      ok = !!safe(() => e?.stop?.()) || ok;
      ok = !!safe(() => W.BCO_ZOMBIES_CORE?.stop?.()) || ok;
      return ok;
    },

    // input: single path for move/aim/firing
    input(data = {}) {
      const input = ensureInputBridge();
      if (data.move) {
        input.move.x = +data.move.x || 0;
        input.move.y = +data.move.y || 0;
      }
      if (data.aim) {
        input.aim.x = +data.aim.x || 0;
        input.aim.y = +data.aim.y || 0;
      }
      if (typeof data.firing === "boolean") input.firing = data.firing;
      input.updatedAt = Date.now();

      const e = pickEngine();
      if (e) {
        safe(() => e.setMove?.(input.move.x, input.move.y));
        safe(() => e.setAim?.(input.aim.x, input.aim.y));
        safe(() => e.setFire?.(!!input.firing));
        safe(() => e.input?.(input));
      }
      const core = W.BCO_ZOMBIES_CORE;
      if (core) {
        safe(() => core.setMove?.(input.move.x, input.move.y));
        safe(() => core.setAim?.(input.aim.x, input.aim.y));
        safe(() => core.setShooting?.(!!input.firing));
      }
      return true;
    }
  };

  // Hook engine events if they exist
  function hookEngineEvents() {
    const e = pickEngine();
    if (!e || e.__BCO_EVENTS_HOOKED__) return;
    e.__BCO_EVENTS_HOOKED__ = true;

    // If engine has its own event emitter
    safe(() => e.on?.("hud", (hud) => bus.emit("hud", hud)));
    safe(() => e.on?.("result", (res) => bus.emit("result", res)));

    // If engine updates via callbacks
    if (typeof e.setOnHud === "function") safe(() => e.setOnHud((hud) => bus.emit("hud", hud)));
    if (typeof e.setOnResult === "function") safe(() => e.setOnResult((r) => bus.emit("result", r)));
  }

  // watch for engine appearing later (script load order)
  let tries = 0;
  (function waitEngine() {
    hookEngineEvents();
    tries++;
    if (pickEngine() || tries > 80) return; // ~4-5 sec
    setTimeout(waitEngine, 60);
  })();

  W.BCO_GAME = BCO_GAME;
})();
