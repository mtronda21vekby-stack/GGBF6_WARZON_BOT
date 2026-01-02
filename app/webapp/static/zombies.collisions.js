// =========================================================
// ZOMBIES COLLISIONS SYSTEM (walls + bounds + entities)
// File: app/webapp/static/zombies.collisions.js
// =========================================================
(() => {
  "use strict";

  // requires:
  // - window.BCO_ZOMBIES_MAPS
  // - used inside main loop (tick)

  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

  function rectCircleCollide(cx, cy, r, rx, ry, rw, rh) {
    const nx = clamp(cx, rx, rx + rw);
    const ny = clamp(cy, ry, ry + rh);
    const dx = cx - nx;
    const dy = cy - ny;
    return (dx * dx + dy * dy) < (r * r);
  }

  function resolveCircleRect(entity, rect) {
    const cx = entity.x;
    const cy = entity.y;
    const r = entity.r;

    const nx = clamp(cx, rect.x, rect.x + rect.w);
    const ny = clamp(cy, rect.y, rect.y + rect.h);

    const dx = cx - nx;
    const dy = cy - ny;

    const dist = Math.hypot(dx, dy) || 0.0001;
    const overlap = r - dist;

    if (overlap > 0) {
      entity.x += (dx / dist) * overlap;
      entity.y += (dy / dist) * overlap;
      return true;
    }
    return false;
  }

  function applyMapBounds(entity, map, w, h) {
    const pad = 6;
    entity.x = clamp(entity.x, pad, w - pad);
    entity.y = clamp(entity.y, pad + 90, h - pad);
  }

  function collideEntityWithMap(entity, map, w, h) {
    if (!map || !map.walls) return;

    for (const wall of map.walls) {
      if (rectCircleCollide(entity.x, entity.y, entity.r, wall.x, wall.y, wall.w, wall.h)) {
        resolveCircleRect(entity, wall);
      }
    }

    applyMapBounds(entity, map, w, h);
  }

  function collideBullets(bullets, map) {
    if (!map || !map.walls) return;

    for (let i = bullets.length - 1; i >= 0; i--) {
      const b = bullets[i];
      for (const w of map.walls) {
        if (
          b.x > w.x &&
          b.x < w.x + w.w &&
          b.y > w.y &&
          b.y < w.y + w.h
        ) {
          bullets.splice(i, 1);
          break;
        }
      }
    }
  }

  function drawDebug(ctx, map) {
    if (!map || !map.walls) return;
    ctx.save();
    ctx.strokeStyle = "rgba(255,0,0,.6)";
    ctx.lineWidth = 2;
    for (const w of map.walls) {
      ctx.strokeRect(w.x, w.y, w.w, w.h);
    }
    ctx.restore();
  }

  window.BCO_ZOMBIES_COLLISIONS = {
    collideEntityWithMap,
    collideBullets,
    drawDebug
  };
})();
