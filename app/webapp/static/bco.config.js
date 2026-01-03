// app/webapp/static/bco.config.js
(() => {
  "use strict";

  const CONFIG = {
    VERSION: "3.1.0-modular",
    STORAGE_KEY: "bco_state_v1",
    MAX_PAYLOAD_SIZE: 15000,

    // Contract
    DEFAULT_VOICE: "TEAMMATE",
    ZOOM_BUMP: 0.5, // +0.5 to current

    INPUT: {
      TAP_MAX_MOVE_PX: 12,
      TAP_MAX_MS: 450,
      CAPTURE: true
    },

    FULLSCREEN: {
      TAKEOVER_CLASS: "bco-game-takeover",
      ACTIVE_CLASS: "bco-game-active",
      LOCK_BODY_SCROLL: true
    }
  };

  window.BCO = window.BCO || {};
  window.BCO.CONFIG = CONFIG;
})();
