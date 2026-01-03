// app/webapp/static/bco.config.js
(() => {
  "use strict";

  const CFG = {
    VERSION: "3.0.0-vnext",
    STORAGE_KEY: "bco_state_v1",
    CHAT_KEY: "bco_chat_v1",
    BUILD_KEY: "bco_build",

    // Contract
    DEFAULT_VOICE: "TEAMMATE",
    COACH_VOICE: "COACH",

    // Zombies vNext
    ZOMBIES: {
      // zoom bump contract (core snaps to 0.5 step)
      ZOOM_BUMP: 0.5,

      // input
      DEADZONE: 0.10,
      AIM_DEADZONE: 0.06,

      // iOS tap/gesture guard
      TAP_MAX_MOVE_PX: 12,
      TAP_MAX_MS: 520,

      // Game loop
      RAF_RESIZE_THROTTLE_MS: 120,

      // Runtime: “real different” modes policy knobs (core already has rogue vs arcade)
      MODES: {
        arcade: {
          name: "arcade",
          // arcade = no coin economy / no pickups application (core already guards on isRogue)
          allowShop: false
        },
        roguelike: {
          name: "roguelike",
          allowShop: true
        }
      }
    }
  };

  window.BCO_CFG = CFG;
  console.log("[BCO_CFG] loaded", CFG.VERSION);
})();
