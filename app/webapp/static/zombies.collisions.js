/* =========================================================
   app/webapp/static/zombies.collisions.js
   ========================================================= */
(() => {
  "use strict";

  function rectCircleCollide(rx, ry, rw, rh, cx, cy, cr) {
    const nx = Math.max(rx, Math.min(cx, rx + rw));
    const ny = Math.max(ry, Math.min(cy, ry + rh));
    const dx = cx - nx;
    const dy = cy - ny;
    return (dx * dx + dy * dy) < cr * cr;
  }

  function resolveCircleRect(e, r) {
    const cx = e.x;
    const cy = e.y;
    const cr = e.r || 16;

    const nx = Math.max(r.x, Math.min(cx, r.x + r.w));
    const ny = Math.max(r.y, Math.min(cy, r.y + r.h));

    const dx = cx - nx;
    const dy = cy - ny;

    if (dx === 0 && dy === 0) return;

    if (Math.abs(dx) > Math.abs(dy)) {
      e.x += dx > 0 ? (cr - dx) : -(cr + dx);
    } else {
      e.y += dy > 0 ? (cr - dy) : -(cr + dy);
    }
  }

  function collideEntityWithMap(entity, map, maxW, maxH) {
    if (!map || !map.walls) return;

    entity.x = Math.max(entity.r, Math.min(entity.x, maxW - entity.r));
    entity.y = Math.max(entity.r, Math.min(entity.y, maxH - entity.r));

    for (const w of map.walls) {
      if (rectCircleCollide(w.x, w.y, w.w, w.h, entity.x, entity.y, entity.r)) {
        resolveCircleRect(entity, w);
      }
    }
  }

  function collideBullets(bullets, map) {
    if (!map || !map.walls) return;
    for (let i = bullets.length - 1; i >= 0; i--) {
      const b = bullets[i];
      for (const w of map.walls) {
        if (b.x > w.x && b.x < w.x + w.w && b.y > w.y && b.y < w.y + w.h) {
          bullets.splice(i, 1);
          break;
        }
      }
    }
  }

  window.BCO_ZOMBIES_COLLISIONS = {
    collideEntityWithMap,
    collideBullets
  };
})();
