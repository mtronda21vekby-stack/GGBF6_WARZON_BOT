/* =========================================================
   app/webapp/static/zombies.draw.map.js
   MAP RENDER (VISUAL MAP LAYER)
   ========================================================= */
(() => {
  "use strict";

  const MAPS = window.BCO_ZOMBIES_MAPS;
  if (!MAPS) return;

  function drawMap(ctx, map, camX = 0, camY = 0) {
    if (!map) return;

    ctx.save();
    ctx.translate(-camX, -camY);

    ctx.fillStyle = "rgba(255,255,255,.04)";
    for (const w of map.walls) {
      ctx.fillRect(w.x, w.y, w.w, w.h);
    }

    ctx.restore();
  }

  if (window.BCO_ZOMBIES) {
    const core = window.BCO_ZOMBIES;
    core._drawMap = function (ctx, run) {
      const map = MAPS.get(run.map || "Ashes");
      drawMap(ctx, map, 0, 0);
    };
  }

  window.BCO_ZOMBIES_DRAW_MAP = { drawMap };

})();
