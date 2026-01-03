(() => {
  "use strict";

  const log = window.BCO_LOG || console;
  const { clamp, nowMs } = window.BCO_UTILS;

  /**
   * Runtime:
   * - Owns mode switching (Arcade/Roguelike реально разные)
   * - Applies zoom bump contract (+0.5)
   * - Drives engine tick/render (adapter)
   * - Syncs economy + UI
   */
  function createRuntime() {
    const econ = window.BCO_ZOMBIES_ECON;
    const ui = window.BCO_ZOMBIES_UI;
    const engine = window.BCO_ENGINE;

    const state = {
      running: false,
      mode: "ARCADE",
      startedAt: 0,
      lastTickAt: 0,
      hud: {
        hp: 100, armor: 0, plates: 0,
        coins: 0, relics: 0, ammo: 0,
        wave: 1, level: 1, xp: 0,
      },
    };

    function _applyZoomBump() {
      const bump = window.BCO_CONFIG?.ZOMBIES?.ZOOM_BUMP ?? 0.5;
      const cur = engine.getZoom();
      const next = (cur == null) ? bump : (Number(cur) + bump);
      engine.setZoom(next);
      log.info("Zoom bump applied", { cur, bump, next });
    }

    function start(mode) {
      state.mode = (mode === "ROGUELIKE") ? "ROGUELIKE" : "ARCADE";
      econ.setMode(state.mode);

      ui.setTakeover(true);
      ui.lockBodyScroll(true);
      ui.telegramFullscreen(true);
      ui.markModalScrollContainers();

      // Start engine (legacy/core) with opts
      engine.start(state.mode, { zoom: engine.getZoom() });

      // Contract: zoom bump +0.5
      _applyZoomBump();

      state.running = true;
      state.startedAt = nowMs();
      state.lastTickAt = state.startedAt;
      _loop();
    }

    function stop() {
      state.running = false;

      try { engine.stop(); } catch {}
      ui.telegramFullscreen(false);
      ui.lockBodyScroll(false);
      ui.setTakeover(false);
    }

    function onKill() {
      const res = econ.onKill();
      state.hud.coins = econ.state.coins;
      state.hud.relics = econ.state.relics;
      ui.updateHud(state.hud);
      return res;
    }

    function onWaveComplete() {
      econ.onWaveComplete();
      state.hud.coins = econ.state.coins;
      state.hud.relics = econ.state.relics;
      state.hud.level = econ.state.runLevel;
      state.hud.xp = econ.state.runXP;
      ui.updateHud(state.hud);
    }

    function getSnapshot() {
      const dur = nowMs() - state.startedAt;
      econ.state.stats.durationMs = dur;
      return {
        mode: state.mode,
        ...econ.snapshot(),
      };
    }

    function _loop() {
      if (!state.running) return;
      const t = nowMs();
      const dt = clamp(t - state.lastTickAt, 0, 50);
      state.lastTickAt = t;

      try {
        engine.tick(dt);
        // render handled by engine internally; adapter keeps future hook
      } catch (e) {
        log.error("Runtime loop error", e);
      }

      requestAnimationFrame(_loop);
    }

    return { state, start, stop, onKill, onWaveComplete, getSnapshot };
  }

  window.BCO_ZOMBIES_RUNTIME = createRuntime();
})();
