/* =========================================================
   BLACK CROWN OPS — ZOMBIES COLLISIONS [LUX]
   File: app/webapp/static/zombies.collisions.js
   Provides: window.BCO_ZOMBIES_COLLISIONS
   ========================================================= */
(() => {
  "use strict";

  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }

  // Robust circle-vs-rect resolution (rect is CENTER-anchored).
  // Works even if circle center is inside rect (dx=dy=0 case).
  function rectCircleResolve(ent, rect, r) {
    const rx = rect.x, ry = rect.y, rw = rect.w, rh = rect.h;
    const left = rx - rw / 2;
    const right = rx + rw / 2;
    const top = ry - rh / 2;
    const bottom = ry + rh / 2;

    const cx = clamp(ent.x, left, right);
    const cy = clamp(ent.y, top, bottom);

    let dx = ent.x - cx;
    let dy = ent.y - cy;

    const d2 = dx * dx + dy * dy;
    const rr = r * r;

    if (d2 > rr) {
      // no overlap
      return false;
    }

    // If the circle center is inside the rect, dx=dy=0 — choose minimal escape axis.
    if (d2 === 0) {
      const pushLeft = (ent.x - left);
      const pushRight = (right - ent.x);
      const pushTop = (ent.y - top);
      const pushBottom = (bottom - ent.y);

      const minX = Math.min(pushLeft, pushRight);
      const minY = Math.min(pushTop, pushBottom);

      if (minX < minY) {
        ent.x = (pushLeft < pushRight) ? (left - r) : (right + r);
      } else {
        ent.y = (pushTop < pushBottom) ? (top - r) : (bottom + r);
      }
      return true;
    }

    // Otherwise push out along shortest axis (approx)
    const adx = Math.abs(dx);
    const ady = Math.abs(dy);

    if (adx > ady) {
      ent.x = (dx > 0) ? (right + r) : (left - r);
    } else {
      ent.y = (dy > 0) ? (bottom + r) : (top - r);
    }
    return true;
  }

  function collideEntityWithWalls(ent, walls, r) {
    let hit = false;
    for (const wall of walls) {
      if (rectCircleResolve(ent, wall, r)) hit = true;
    }
    return hit;
  }

  function bulletHitsRect(b, wall) {
    const r = b.r || 3;
    const rx = wall.x, ry = wall.y, rw = wall.w, rh = wall.h;
    const left = rx - rw / 2, right = rx + rw / 2;
    const top = ry - rh / 2, bottom = ry + rh / 2;

    const cx = clamp(b.x, left, right);
    const cy = clamp(b.y, top, bottom);
    const dx = b.x - cx;
    const dy = b.y - cy;

    return ((dx * dx + dy * dy) <= (r * r));
  }

  const COLL = {
    // Collide entity with map walls (player/zombie/boss)
    collideEntityWithMap(ent, map) {
      if (!ent || !map) return false;
      const walls = map.walls || [];
      if (!walls.length) return false;

      const r = Number(ent.r || ent.hitbox || 16);
      return collideEntityWithWalls(ent, walls, r);
    },

    // Remove bullets that hit walls
    collideBullets(bullets, map) {
      if (!map || !map.walls || !bullets) return;
      const walls = map.walls;

      for (let i = bullets.length - 1; i >= 0; i--) {
        const b = bullets[i];
        for (const wall of walls) {
          if (bulletHitsRect(b, wall)) {
            bullets.splice(i, 1);
            break;
          }
        }
      }
    },

    // Optional: soft separation between zombies (prevents clumping)
    // entities: [{x,y,r}]
    separateEntities(ents, iterations = 1) {
      if (!Array.isArray(ents) || ents.length < 2) return;
      const it = Math.max(1, iterations | 0);

      for (let k = 0; k < it; k++) {
        for (let i = 0; i < ents.length; i++) {
          const a = ents[i];
          const ar = a.r || 16;
          for (let j = i + 1; j < ents.length; j++) {
            const b = ents[j];
            const br = b.r || 16;

            const dx = b.x - a.x;
            const dy = b.y - a.y;
            const d2 = dx * dx + dy * dy;
            const min = (ar + br) * 0.92; // slight overlap allowed for speed
            if (d2 === 0) {
              // nudge
              a.x -= 0.5; b.x += 0.5;
              continue;
            }
            const d = Math.sqrt(d2);
            if (d >= min) continue;

            const push = (min - d) * 0.5;
            const nx = dx / d;
            const ny = dy / d;

            a.x -= nx * push;
            a.y -= ny * push;
            b.x += nx * push;
            b.y += ny * push;
          }
        }
      }
    },

    // LUX: Install wrapper for CORE (zombies.core.js) if you want collisions auto-applied
    // Usage (optional, world module can call): BCO_ZOMBIES_COLLISIONS.install(CORE, mapGetter)
    install(CORE, mapGetter) {
      if (!CORE || typeof CORE !== "object") return false;

      const getMap = (typeof mapGetter === "function")
        ? mapGetter
        : () => (window.BCO_ZOMBIES_MAPS?.get?.(CORE.meta?.map) || null);

      const prevTick = CORE._tickWorld;

      CORE._tickWorld = (core, dt, tms) => {
        // allow previous world hook first
        try { if (typeof prevTick === "function") prevTick(core, dt, tms); } catch {}

        const map = getMap();
        if (!map) return;

        const S = core.state;

        // Clamp to map bounds (in addition to arena)
        // Map bounds are rectangles: [-hw..hw], [-hh..hh]
        const hw = map.hw || Math.floor((map.w || 2400) / 2);
        const hh = map.hh || Math.floor((map.h || 2400) / 2);

        // player
        S.player.x = clamp(S.player.x, -hw, hw);
        S.player.y = clamp(S.player.y, -hh, hh);

        // collide player with walls
        COLL.collideEntityWithMap({ x: S.player.x, y: S.player.y, r: core.cfg.player.hitbox }, map);
        // write back (we used temp object for simplicity)
        // (do it properly)
        // re-run with direct object:
        const pEnt = { x: S.player.x, y: S.player.y, r: core.cfg.player.hitbox };
        COLL.collideEntityWithMap(pEnt, map);
        S.player.x = pEnt.x;
        S.player.y = pEnt.y;

        // zombies
        for (let i = 0; i < S.zombies.length; i++) {
          const z = S.zombies[i];
          const ent = { x: z.x, y: z.y, r: z.r || core.cfg.zombie.radius };
          COLL.collideEntityWithMap(ent, map);
          z.x = ent.x; z.y = ent.y;
          z.x = clamp(z.x, -hw, hw);
          z.y = clamp(z.y, -hh, hh);
        }

        // optional separation to make movement feel premium
        COLL.separateEntities(S.zombies, 1);

        // bullets
        COLL.collideBullets(S.bullets, map);
      };

      return true;
    }
  };

  window.BCO_ZOMBIES_COLLISIONS = COLL;
  console.log("[Z_COLL] loaded (LUX)");
})();
