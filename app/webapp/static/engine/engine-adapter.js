(() => {
  "use strict";

  /**
   * Engine Adapter (elite):
   * - Provides single interface for runtime to call:
   *   start(mode, opts), stop(), setZoom(z), getZoom(), setInput(inputState), tick(dt)
   * - Supports:
   *   - window.BCO_ZOMBIES (legacy monolith)
   *   - window.BCO_ZOMBIES_CORE (core logic)
   * - Render plugin readiness (2D now, 3D later):
   *   - runtime calls adapter.renderFrame(ctx) if available
   */
  function createEngineAdapter() {
    const log = window.BCO_LOG || console;

    function detect() {
      const legacy = window.BCO_ZOMBIES || null;
      const core = window.BCO_ZOMBIES_CORE || null;

      return { legacy, core };
    }

    const state = {
      mode: null,
      running: false,
      zoom: null,
      input: null,
      detected: detect(),
    };

    function refresh() {
      state.detected = detect();
      return state.detected;
    }

    function _applyZoomToEngine(z) {
      const { legacy, core } = state.detected;
      let applied = false;

      if (legacy && typeof legacy.setZoom === "function") {
        legacy.setZoom(z);
        applied = true;
      } else if (legacy && legacy.state && typeof legacy.state === "object") {
        legacy.state.zoom = z;
        applied = true;
      }

      if (core && typeof core.setZoom === "function") {
        core.setZoom(z);
        applied = true;
      } else if (core && core.state && typeof core.state === "object") {
        core.state.zoom = z;
        applied = true;
      }

      if (!applied) log.warn("EngineAdapter: zoom not applied (no compatible API found)");
    }

    function setZoom(z) {
      state.zoom = z;
      _applyZoomToEngine(z);
    }

    function getZoom() {
      const { legacy, core } = state.detected;
      if (legacy && typeof legacy.getZoom === "function") return legacy.getZoom();
      if (core && typeof core.getZoom === "function") return core.getZoom();
      if (legacy && legacy.state && legacy.state.zoom != null) return legacy.state.zoom;
      if (core && core.state && core.state.zoom != null) return core.state.zoom;
      return state.zoom;
    }

    function setInput(inputState) {
      state.input = inputState;
      const { legacy, core } = state.detected;

      if (legacy && typeof legacy.setInput === "function") legacy.setInput(inputState);
      if (core && typeof core.setInput === "function") core.setInput(inputState);
    }

    function start(mode, opts = {}) {
      refresh();
      state.mode = mode;
      state.running = true;

      const { legacy, core } = state.detected;

      // Prefer core if present, else legacy
      if (core && typeof core.start === "function") core.start(mode, opts);
      else if (legacy && typeof legacy.start === "function") legacy.start(mode, opts);
      else if (legacy && typeof legacy.init === "function") legacy.init(mode, opts);
      else log.warn("EngineAdapter: no start/init found");

      // Zoom bump contract handled in runtime; adapter only applies
      if (opts.zoom != null) setZoom(opts.zoom);
    }

    function stop() {
      const { legacy, core } = state.detected;
      state.running = false;

      if (core && typeof core.stop === "function") core.stop();
      if (legacy && typeof legacy.stop === "function") legacy.stop();
    }

    function tick(dt) {
      const { legacy, core } = state.detected;
      if (core && typeof core.tick === "function") core.tick(dt);
      if (legacy && typeof legacy.tick === "function") legacy.tick(dt);
    }

    function renderFrame(ctx) {
      const { legacy, core } = state.detected;
      // Prefer legacy render if it exists today; later we can route to plugin renderer
      if (legacy && typeof legacy.render === "function") return legacy.render(ctx);
      if (core && typeof core.render === "function") return core.render(ctx);
      return null;
    }

    return { refresh, start, stop, tick, setZoom, getZoom, setInput, renderFrame };
  }

  window.BCO_ENGINE = createEngineAdapter();
})();
