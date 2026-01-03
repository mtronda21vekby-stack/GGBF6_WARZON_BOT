/* app/webapp/static/bco.input.js */
(() => {
  "use strict";

  // Unified input placeholder (2D now, 3D later)
  const State = {
    dualStick: true,
    left: { x: 0, y: 0 },
    right: { x: 0, y: 0 },
    firing: false
  };

  window.BCO_INPUT = {
    State,
    reset() {
      State.left.x = 0; State.left.y = 0;
      State.right.x = 0; State.right.y = 0;
      State.firing = false;
    }
  };
})();
