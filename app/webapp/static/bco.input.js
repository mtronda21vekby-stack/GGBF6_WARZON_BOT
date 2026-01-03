// app/webapp/static/bco.input.js
(() => {
  "use strict";

  const W = window;

  // Single shared input state (NO DUPLICATES).
  const INPUT = (W.BCO_ZOMBIES_INPUT && typeof W.BCO_ZOMBIES_INPUT === "object")
    ? W.BCO_ZOMBIES_INPUT
    : (W.BCO_ZOMBIES_INPUT = {
        move: { x: 0, y: 0 },
        aim: { x: 0, y: 0 },
        firing: false,
        updatedAt: 0
      });

  function clamp(v) {
    v = +v || 0;
    if (v > 1) v = 1;
    if (v < -1) v = -1;
    return v;
  }

  const API = {
    state: INPUT,

    setMove(x, y) {
      INPUT.move.x = clamp(x);
      INPUT.move.y = clamp(y);
      INPUT.updatedAt = Date.now();
      return INPUT;
    },

    setAim(x, y) {
      INPUT.aim.x = clamp(x);
      INPUT.aim.y = clamp(y);
      INPUT.updatedAt = Date.now();
      return INPUT;
    },

    setFiring(on) {
      INPUT.firing = !!on;
      INPUT.updatedAt = Date.now();
      return INPUT;
    },

    flushToGame() {
      // Push input into BCO_GAME if present
      if (W.BCO_GAME && typeof W.BCO_GAME.input === "function") {
        W.BCO_GAME.input({
          move: INPUT.move,
          aim: INPUT.aim,
          firing: INPUT.firing
        });
      }
    }
  };

  W.BCO_INPUT = API;
})();
