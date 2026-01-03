(() => {
  "use strict";

  const CONFIG = {
    VERSION: "3.0.0-core",
    STORAGE_KEY: "bco_state_v1",
    CHAT_KEY: "bco_chat_v1",
    BUILD_KEY: "bco_build",
    API_TIMEOUT: 12000,
    CHAT_HISTORY_LIMIT: 80,
    MAX_PAYLOAD_SIZE: 15000,

    // Contract / defaults
    DEFAULT_VOICE: "TEAMMATE", // TEAMMATE default
    COACH_ELITE_STRUCTURED: true,

    // Zombies economy baseline (runtime can override per mode)
    ZOMBIES: {
      // IMPORTANT: zoom bump = +0.5 to current (applied in runtime)
      ZOOM_BUMP: 0.5,

      // Arcade: faster, score chasing
      ARCADE: {
        COINS_PER_KILL: 1,
        RELIC_DROP_CHANCE: 0.02,
        MAGNET_RADIUS: 120,
        SHOP_ENABLED: true,
        DEATH_PENALTY: "none",
      },

      // Roguelike: real loop, meta-progression in-run
      ROGUELIKE: {
        COINS_PER_KILL: 1,
        COINS_PER_WAVE: 8,
        RELIC_DROP_CHANCE: 0.04,
        MAGNET_RADIUS: 160,
        SHOP_ENABLED: true,
        DEATH_PENALTY: "loss_run",
        RARITY: {
          common: 0.62,
          rare: 0.25,
          epic: 0.10,
          legendary: 0.03,
        },
      },
    },

    // iOS / WebView hardening
    INPUT: {
      TAP_MAX_MOVE_PX: 12,
      TAP_MAX_MS: 450,
      LONGPRESS_MS: 380,
      CAPTURE: true,
      PASSIVE_FALSE: true,
    },

    FULLSCREEN: {
      // We do NOT redesign UI; only “takeover” bugfix
      LOCK_BODY_SCROLL: true,
      PREVENT_PINCH: true,
      PREVENT_DOUBLE_TAP_ZOOM: true,
    },
  };

  window.BCO_CONFIG = CONFIG;
})();
