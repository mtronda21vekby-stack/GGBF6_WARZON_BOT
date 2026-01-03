(() => {
  "use strict";

  const levels = { debug: 10, info: 20, warn: 30, error: 40 };
  const state = {
    level: "info",
    enabled: true,
    prefix: "[BCO]",
  };

  function _can(lvl) {
    return state.enabled && levels[lvl] >= levels[state.level];
  }

  const log = {
    setLevel(level) {
      if (levels[level] != null) state.level = level;
    },
    enable(v) {
      state.enabled = !!v;
    },
    debug(...args) { if (_can("debug")) console.log(state.prefix, ...args); },
    info(...args) { if (_can("info")) console.log(state.prefix, ...args); },
    warn(...args) { if (_can("warn")) console.warn(state.prefix, ...args); },
    error(...args) { if (_can("error")) console.error(state.prefix, ...args); },
  };

  window.BCO_LOG = log;
})();
