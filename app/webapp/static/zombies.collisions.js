/* =========================================================
   app/webapp/static/zombies.collisions.js
   COLLISIONS: entity vs walls + bullet vs walls
   ========================================================= */
(() => {
  "use strict";

  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }

  function resolveCircleRect(cx, cy, r, rx, ry, rw, rh) {
    const nx = clamp(cx, rx, rx + rw);
    const ny = clamp(cy, ry, ry + rh);
    const dx = cx - nx;
    const dy = cy - ny;
    const d2 = dx * dx + dy * dy;
    if (d2 >= r * r || d2 === 0) return null;

    const d = Math.sqrt(d2);
    const push = (r - d);
    return { px: (dx / d) * push, py: (dy / d) * push };
  }

  function collideEntityWithMap(ent, map, w, h) {
    if (!ent || !map) return;

    const r = Math.max(6, ent.r || ent.radius || 14);

    // держим в пределах карты
    ent.x = clamp(ent.x, r, w - r);
    ent.y = clamp(ent.y, r, h - r);

    for (const wall of map.walls || []) {
      const res = resolveCircleRect(ent.x, ent.y, r, wall.x, wall.y, wall.w, wall.h);
      if (!res) continue;
      ent.x += res.px;
      ent.y += res.py;
    }
  }

  function collideBullets(bullets, map) {
    if (!bullets || !map) return;

    for (let i = bullets.length - 1; i >= 0; i--) {
      const b = bullets[i];
      if (!b) continue;

      // простая AABB проверка по стенам
      let hit = false;
      for (const w of map.walls || []) {
        if (b.x >= w.x && b.x <= w.x + w.w && b.y >= w.y && b.y <= w.y + w.h) {
          hit = true; break;
        }
      }
      if (hit) bullets.splice(i, 1);
    }
  }

  window.BCO_ZOMBIES_COLLISIONS = {
    collideEntityWithMap,
    collideBullets
  };

  console.log("[BCO_ZOMBIES_COLLISIONS] loaded");
})();
