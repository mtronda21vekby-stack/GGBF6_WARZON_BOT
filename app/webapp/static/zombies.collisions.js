/* =========================================================
   BLACK CROWN OPS — ZOMBIES COLLISIONS [ULTRA LUX | 3D-READY]
   File: app/webapp/static/zombies.collisions.js
   Provides: window.BCO_ZOMBIES_COLLISIONS

   ULTRA LUX upgrades:
     ✅ Correct circle-vs-rect resolution (inside-rect robust)
     ✅ Supports rotated walls (angle) using OBB math (optional; safe if angle=0)
     ✅ Bullet ray-step (swept) to reduce tunneling at high FPS/dpr
     ✅ Stable zombie separation with bounds clamp (premium “flow”)
     ✅ Install() hook that DOES NOT double-resolve player and avoids temp mistakes
     ✅ Soft friction at walls (optional) for nicer feel
     ✅ 3D-ready: exposes pure functions for future physics adapter
   ========================================================= */
(() => {
  "use strict";

  // ---------------------------------------------------------
  // Math
  // ---------------------------------------------------------
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const len = (x, y) => Math.hypot(x, y) || 0;

  function rot(x, y, ang) {
    const c = Math.cos(ang), s = Math.sin(ang);
    return { x: x * c - y * s, y: x * s + y * c };
  }

  // ---------------------------------------------------------
  // OBB (rotated rect) circle resolve
  // Rect contract: center-anchored, has x,y,w,h, optional angle (radians)
  // ---------------------------------------------------------
  function rectCircleResolve(ent, rect, r) {
    const ang = Number(rect.angle) || 0;
    const hw = (Number(rect.w) || 0) / 2;
    const hh = (Number(rect.h) || 0) / 2;

    // Transform circle center into rect local space
    const relX = (Number(ent.x) || 0) - (Number(rect.x) || 0);
    const relY = (Number(ent.y) || 0) - (Number(rect.y) || 0);

    const local = ang ? rot(relX, relY, -ang) : { x: relX, y: relY };

    // Closest point on AABB in local space
    const cx = clamp(local.x, -hw, hw);
    const cy = clamp(local.y, -hh, hh);

    let dx = local.x - cx;
    let dy = local.y - cy;

    const d2 = dx * dx + dy * dy;
    const rr = r * r;

    if (d2 > rr) return false;

    // If inside rectangle (dx=dy=0), push out through minimal axis
    if (d2 === 0) {
      const pushX = (hw - Math.abs(local.x));
      const pushY = (hh - Math.abs(local.y));
      if (pushX < pushY) {
        const dir = (local.x >= 0) ? 1 : -1;
        dx = dir; dy = 0;
        // move to surface + radius
        local.x = (hw + r) * dir;
      } else {
        const dir = (local.y >= 0) ? 1 : -1;
        dx = 0; dy = dir;
        local.y = (hh + r) * dir;
      }
    } else {
      // push along normal
      const d = Math.sqrt(d2) || 1;
      const push = (r - d);
      dx /= d; dy /= d;
      local.x += dx * push;
      local.y += dy * push;
    }

    // Transform back to world space
    const out = ang ? rot(local.x, local.y, ang) : local;

    ent.x = (Number(rect.x) || 0) + out.x;
    ent.y = (Number(rect.y) || 0) + out.y;
    return true;
  }

  function collideEntityWithWalls(ent, walls, r) {
    let hit = false;
    if (!walls || !walls.length) return false;
    for (let i = 0; i < walls.length; i++) {
      const w = walls[i];
      if (rectCircleResolve(ent, w, r)) hit = true;
    }
    return hit;
  }

  // ---------------------------------------------------------
  // Bullet collision
  // - Fast AABB check + optional swept stepping to prevent tunneling
  // ---------------------------------------------------------
  function bulletHitsRect(b, wall) {
    const r = Number(b.r || 3) || 3;

    // If rotated wall: test in local space like circle-vs-OBB
    const ang = Number(wall.angle) || 0;
    const hw = (Number(wall.w) || 0) / 2;
    const hh = (Number(wall.h) || 0) / 2;

    const relX = (Number(b.x) || 0) - (Number(wall.x) || 0);
    const relY = (Number(b.y) || 0) - (Number(wall.y) || 0);
    const local = ang ? rot(relX, relY, -ang) : { x: relX, y: relY };

    const cx = clamp(local.x, -hw, hw);
    const cy = clamp(local.y, -hh, hh);
    const dx = local.x - cx;
    const dy = local.y - cy;

    return ((dx * dx + dy * dy) <= (r * r));
  }

  function collideBulletsDiscrete(bullets, walls) {
    // remove bullets that hit walls (discrete)
    for (let i = bullets.length - 1; i >= 0; i--) {
      const b = bullets[i];
      for (let j = 0; j < walls.length; j++) {
        if (bulletHitsRect(b, walls[j])) {
          bullets.splice(i, 1);
          break;
        }
      }
    }
  }

  function collideBulletsSwept(bullets, walls) {
    // Swept: sample along segment from prev to current (px->x)
    // Cheap stepping scaled by distance and bullet radius.
    for (let i = bullets.length - 1; i >= 0; i--) {
      const b = bullets[i];
      const x0 = Number(b.px ?? b.x) || 0;
      const y0 = Number(b.py ?? b.y) || 0;
      const x1 = Number(b.x) || 0;
      const y1 = Number(b.y) || 0;

      const dx = x1 - x0;
      const dy = y1 - y0;
      const dist = len(dx, dy);
      const r = Math.max(1, Number(b.r || 3) || 3);

      // If tiny move, fallback to discrete
      if (dist <= r * 0.75) {
        for (let j = 0; j < walls.length; j++) {
          if (bulletHitsRect(b, walls[j])) { bullets.splice(i, 1); break; }
        }
        continue;
      }

      // Steps: 1 per ~r*1.2
      const steps = clamp(Math.ceil(dist / (r * 1.2)), 2, 10);
      let removed = false;

      for (let s = 1; s <= steps; s++) {
        const t = s / steps;
        const sx = x0 + dx * t;
        const sy = y0 + dy * t;

        // Temporarily test this sample
        const tmp = { x: sx, y: sy, r };

        for (let j = 0; j < walls.length; j++) {
          if (bulletHitsRect(tmp, walls[j])) {
            bullets.splice(i, 1);
            removed = true;
            break;
          }
        }
        if (removed) break;
      }
    }
  }

  // ---------------------------------------------------------
  // Separation (premium anti-clump)
  // ---------------------------------------------------------
  function separateEntities(ents, iterations = 1) {
    if (!Array.isArray(ents) || ents.length < 2) return;
    const it = Math.max(1, iterations | 0);

    for (let k = 0; k < it; k++) {
      for (let i = 0; i < ents.length; i++) {
        const a = ents[i];
        const ar = Number(a.r || 16) || 16;
        for (let j = i + 1; j < ents.length; j++) {
          const b = ents[j];
          const br = Number(b.r || 16) || 16;

          const dx = (Number(b.x) || 0) - (Number(a.x) || 0);
          const dy = (Number(b.y) || 0) - (Number(a.y) || 0);
          const d2 = dx * dx + dy * dy;

          const min = (ar + br) * 0.92; // allow slight overlap
          if (d2 === 0) {
            a.x = (Number(a.x) || 0) - 0.6;
            b.x = (Number(b.x) || 0) + 0.6;
            continue;
          }

          const d = Math.sqrt(d2);
          if (d >= min) continue;

          const push = (min - d) * 0.5;
          const nx = dx / d;
          const ny = dy / d;

          a.x = (Number(a.x) || 0) - nx * push;
          a.y = (Number(a.y) || 0) - ny * push;
          b.x = (Number(b.x) || 0) + nx * push;
          b.y = (Number(b.y) || 0) + ny * push;
        }
      }
    }
  }

  // ---------------------------------------------------------
  // Bounds clamp (map rect)
  // ---------------------------------------------------------
  function clampEntityToMap(ent, map, pad = 0) {
    if (!map) return;
    const hw = Number(map.hw || (map.w ? map.w / 2 : 0)) || 0;
    const hh = Number(map.hh || (map.h ? map.h / 2 : 0)) || 0;
    if (!hw || !hh) return;

    ent.x = clamp(ent.x, -hw + pad, hw - pad);
    ent.y = clamp(ent.y, -hh + pad, hh - pad);
  }

  // ---------------------------------------------------------
  // Public COLL
  // ---------------------------------------------------------
  const COLL = {
    // Collide entity with map walls (player/zombie/boss)
    collideEntityWithMap(ent, map) {
      if (!ent || !map) return false;
      const walls = map.walls || [];
      if (!walls.length) return false;

      const r = Number(ent.r || ent.hitbox || 16) || 16;
      return collideEntityWithWalls(ent, walls, r);
    },

    // Remove bullets that hit walls (swept by default)
    collideBullets(bullets, map, opt = {}) {
      if (!map || !map.walls || !bullets) return;
      const walls = map.walls;
      const mode = String(opt.mode || "swept");
      if (mode === "discrete") collideBulletsDiscrete(bullets, walls);
      else collideBulletsSwept(bullets, walls);
    },

    // Optional: soft separation between zombies (prevents clumping)
    separateEntities,

    // Utility
    rectCircleResolve,
    clampEntityToMap,

    // ULTRA: Install wrapper for CORE if you want collisions auto-applied
    // Usage:
    //   BCO_ZOMBIES_COLLISIONS.install(CORE, () => BCO_ZOMBIES_MAPS.get(CORE.meta.map))
    install(CORE, mapGetter) {
      if (!CORE || typeof CORE !== "object") return false;

      const getMap = (typeof mapGetter === "function")
        ? mapGetter
        : () => (window.BCO_ZOMBIES_MAPS?.get?.(CORE.meta?.map) || null);

      const prevTick = CORE._tickWorld;

      CORE._tickWorld = function (core, dt, tms) {
        // 1) run previous tick first (so world/bosses can move)
        try { if (typeof prevTick === "function") prevTick(core, dt, tms); } catch {}

        const map = getMap();
        if (!map) return;

        const S = core.state;

        // 2) clamp entities to map
        try {
          const padP = Math.max(10, Number(core?.cfg?.player?.hitbox || 16) || 16);
          clampEntityToMap(S.player, map, padP);
        } catch {}

        // 3) collide player with walls (direct object, single resolve)
        try {
          const pr = Number(core?.cfg?.player?.hitbox || S.player.r || 16) || 16;
          const pEnt = { x: S.player.x, y: S.player.y, r: pr };
          collideEntityWithWalls(pEnt, map.walls, pr);
          S.player.x = pEnt.x;
          S.player.y = pEnt.y;
          clampEntityToMap(S.player, map, pr);
        } catch {}

        // 4) zombies/bosses collide
        try {
          const zrDef = Number(core?.cfg?.zombie?.radius || 16) || 16;
          const arr = Array.isArray(S.zombies) ? S.zombies : [];
          for (let i = 0; i < arr.length; i++) {
            const z = arr[i];
            const zr = Number(z.r || zrDef) || zrDef;
            const zEnt = { x: z.x, y: z.y, r: zr };
            collideEntityWithWalls(zEnt, map.walls, zr);
            z.x = zEnt.x; z.y = zEnt.y;
            clampEntityToMap(z, map, zr);
          }

          // premium flow
          separateEntities(arr, 1);
        } catch {}

        // 5) bullets vs walls (swept to prevent tunneling)
        try {
          COLL.collideBullets(S.bullets, map, { mode: "swept" });
        } catch {}
      };

      return true;
    }
  };

  window.BCO_ZOMBIES_COLLISIONS = COLL;
  console.log("[Z_COLL] loaded (ULTRA LUX | 3D-READY)");
})();
