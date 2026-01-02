/* =========================================================
   BLACK CROWN OPS — ZOMBIES COLLISIONS
   File: app/webapp/static/zombies.collisions.js
   Provides: window.BCO_ZOMBIES_COLLISIONS
   ========================================================= */
(() => {
  "use strict";

  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }

  function rectCircleResolve(ent, rect, r) {
    // rect: center-based? we use x/y as center coords. Keep simple:
    // Treat rect x/y as center of rect
    const rx = rect.x, ry = rect.y, rw = rect.w, rh = rect.h;

    const left = rx - rw / 2;
    const right = rx + rw / 2;
    const top = ry - rh / 2;
    const bottom = ry + rh / 2;

    const cx = clamp(ent.x, left, right);
    const cy = clamp(ent.y, top, bottom);

    const dx = ent.x - cx;
    const dy = ent.y - cy;
    const d2 = dx * dx + dy * dy;
    const rr = r * r;

    if (d2 >= rr) return;

    // push out (minimal axis)
    const adx = Math.abs(dx);
    const ady = Math.abs(dy);

    if (adx > ady) {
      ent.x = (dx > 0) ? (right + r) : (left - r);
    } else {
      ent.y = (dy > 0) ? (bottom + r) : (top - r);
    }
  }

  const COLL = {
    collideEntityWithMap(ent, map) {
      if (!map || !map.walls) return;

      const r = ent.r || 16;
      for (const wall of map.walls) rectCircleResolve(ent, wall, r);
    },

    collideBullets(bullets, map) {
      if (!map || !map.walls || !bullets) return;

      // remove bullets that hit walls
      for (let i = bullets.length - 1; i >= 0; i--) {
        const b = bullets[i];
        const r = b.r || 3;

        for (const wall of map.walls) {
          const rx = wall.x, ry = wall.y, rw = wall.w, rh = wall.h;
          const left = rx - rw / 2, right = rx + rw / 2;
          const top = ry - rh / 2, bottom = ry + rh / 2;

          const cx = clamp(b.x, left, right);
          const cy = clamp(b.y, top, bottom);
          const dx = b.x - cx;
          const dy = b.y - cy;

          if ((dx * dx + dy * dy) < (r * r)) {
            bullets.splice(i, 1);
            break;
          }
        }
      }
    }
  };

  window.BCO_ZOMBIES_COLLISIONS = COLL;
  console.log("[Z_COLL] loaded");
})();
