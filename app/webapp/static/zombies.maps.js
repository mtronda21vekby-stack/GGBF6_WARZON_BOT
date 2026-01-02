/* =========================================================
   BLACK CROWN OPS — ZOMBIES MAPS (Ashes/Astra) [ULTRA LUX | 3D-READY]
   File: app/webapp/static/zombies.maps.js
   Provides:
     - window.BCO_ZOMBIES_MAPS.get(name)
     - window.BCO_ZOMBIES_MAPS.list()
     - window.BCO_ZOMBIES_MAPS.normalizeWall(wall)
     - window.BCO_ZOMBIES_MAPS.getSpawnPoint(map, kind, seed)
     - window.BCO_ZOMBIES_MAPS.sampleSpawn(map, player, wave, kind)
     - window.BCO_ZOMBIES_MAPS.pointInWall(map, x, y, r)
     - window.BCO_ZOMBIES_MAPS.debugSummary(name)

   ULTRA LUX / 3D-READY:
     ✅ Deterministic RNG helpers (seeded) for stable roguelike + future 3D sync
     ✅ Rich map schema:
        - lanes/zones (for future objectives, 3D volumes)
        - nav nodes (for future pathing)
        - spawn profiles (ring/points/weights, anti-spawn-near-player)
        - ambience meta (fog/tint/light) for renderer (2D now / 3D later)
     ✅ Wall normalization supports center/tl + rotation (angle) + rounded corners (future)
     ✅ Safe fallbacks + backward compatible (still has walls/bossSpawns/spawn/theme)
     ✅ "Ultra cool" curated layouts: Ashes (open + debris + crater), Astra (lanes + choke + cover)
   ========================================================= */
(() => {
  "use strict";

  const MAPS = new Map();

  // ---------------------------------------------------------
  // Math / helpers
  // ---------------------------------------------------------
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const len = (x, y) => Math.hypot(x, y) || 0;

  // Deterministic RNG (Mulberry32)
  function mulberry32(seed) {
    let t = (seed >>> 0) || 0x12345678;
    return function () {
      t += 0x6D2B79F5;
      let r = Math.imul(t ^ (t >>> 15), 1 | t);
      r ^= r + Math.imul(r ^ (r >>> 7), 61 | r);
      return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
    };
  }

  function hashStrToSeed(str) {
    const s = String(str || "");
    let h = 2166136261 >>> 0;
    for (let i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  }

  function pickWeighted(rng, arr, wKey = "w") {
    if (!arr || !arr.length) return null;
    let sum = 0;
    for (const a of arr) sum += Math.max(0, Number(a?.[wKey] ?? 1) || 0);
    if (sum <= 0) return arr[(rng() * arr.length) | 0];

    let t = rng() * sum;
    for (const a of arr) {
      t -= Math.max(0, Number(a?.[wKey] ?? 1) || 0);
      if (t <= 0) return a;
    }
    return arr[arr.length - 1];
  }

  // Wall point test (axis-aligned for now; angle support as future)
  function pointInWallRect(w, x, y, r = 0) {
    const hw = (w.w || 0) / 2;
    const hh = (w.h || 0) / 2;
    return (
      x >= (w.x - hw - r) &&
      x <= (w.x + hw + r) &&
      y >= (w.y - hh - r) &&
      y <= (w.y + hh + r)
    );
  }

  // ---------------------------------------------------------
  // Wall normalization (center/tl + optional angle)
  // ---------------------------------------------------------
  function normalizeWall(w) {
    const wall = { ...w };
    wall.w = Number(wall.w) || 0;
    wall.h = Number(wall.h) || 0;
    wall.x = Number(wall.x) || 0;
    wall.y = Number(wall.y) || 0;

    wall.anchor = wall.anchor || "center";
    if (wall.anchor === "tl") {
      wall.x = wall.x + wall.w / 2;
      wall.y = wall.y + wall.h / 2;
      wall.anchor = "center";
    }

    // angle is kept for 3D / future rotated collisions (current collisions can ignore)
    wall.angle = Number(wall.angle) || 0;

    // optional rounded corners for future mesh/collision
    wall.round = Number(wall.round) || 0;

    wall.w = Math.max(2, wall.w);
    wall.h = Math.max(2, wall.h);

    // determinism-friendly rounding
    wall.x = Math.round(wall.x);
    wall.y = Math.round(wall.y);
    wall.w = Math.round(wall.w);
    wall.h = Math.round(wall.h);

    wall.mat = wall.mat || "stone";

    // tags for future (loot density, cover rating, sound)
    wall.tags = Array.isArray(wall.tags) ? wall.tags.slice() : (wall.tags ? [String(wall.tags)] : []);

    return wall;
  }

  // ---------------------------------------------------------
  // Map builder (keeps backward compat + adds ultra schema)
  // ---------------------------------------------------------
  function mkMap(opts) {
    const name = String(opts?.name || "Ashes");
    const w = Math.max(400, Number(opts?.w) || 2400);
    const h = Math.max(400, Number(opts?.h) || 2400);

    const hw = Math.floor(w / 2);
    const hh = Math.floor(h / 2);

    const walls = Array.isArray(opts?.walls) ? opts.walls.map(normalizeWall) : [];
    const bossSpawns = Array.isArray(opts?.bossSpawns) ? opts.bossSpawns.slice() : [];

    const spawn = {
      ringMin: Number(opts?.spawn?.ringMin) || 520,
      ringMax: Number(opts?.spawn?.ringMax) || 880,

      // curated spawn points (optional)
      points: Array.isArray(opts?.spawn?.points) ? opts.spawn.points.map(p => ({
        x: Math.round(Number(p.x) || 0),
        y: Math.round(Number(p.y) || 0),
        w: Math.max(0.1, Number(p.w ?? 1) || 1)
      })) : [],

      // spawn profiles (ultra)
      // - far: prefer far ring and corners
      // - lanes: prefer lane endpoints
      // - chaos: mixed
      profiles: opts?.spawn?.profiles || {},

      // anti-spawn controls
      avoidPlayerRadius: Number(opts?.spawn?.avoidPlayerRadius) || 340,
      avoidRecentRadius: Number(opts?.spawn?.avoidRecentRadius) || 220,
      maxTries: Math.max(6, Number(opts?.spawn?.maxTries) || 18)
    };

    const theme = {
      bg: opts?.theme?.bg || (name === "Astra" ? "asphalt" : "ashes"),
      fog: clamp(Number(opts?.theme?.fog ?? (name === "Astra" ? 0.22 : 0.30)), 0, 0.7),
      tint: opts?.theme?.tint || (name === "Astra" ? "cool" : "warm"),
      // ultra: renderer hints
      light: opts?.theme?.light || (name === "Astra"
        ? { key: "neon", intensity: 0.85, flicker: 0.08 }
        : { key: "ember", intensity: 0.78, flicker: 0.12 }),
      particles: opts?.theme?.particles || (name === "Astra"
        ? { kind: "dust", density: 0.22 }
        : { kind: "ash", density: 0.30 })
    };

    // zones/lanes (3D volumes later)
    const zones = Array.isArray(opts?.zones) ? opts.zones.map(z => ({
      id: String(z.id || ""),
      name: String(z.name || z.id || ""),
      x: Math.round(Number(z.x) || 0),
      y: Math.round(Number(z.y) || 0),
      r: Math.max(60, Math.round(Number(z.r) || 160)),
      tags: Array.isArray(z.tags) ? z.tags.slice() : (z.tags ? [String(z.tags)] : []),
      w: Math.max(0.1, Number(z.w ?? 1) || 1)
    })) : [];

    // nav nodes for future pathing (optional)
    const nav = Array.isArray(opts?.nav) ? opts.nav.map(n => ({
      id: String(n.id || ""),
      x: Math.round(Number(n.x) || 0),
      y: Math.round(Number(n.y) || 0),
      links: Array.isArray(n.links) ? n.links.map(String) : []
    })) : [];

    // metadata
    const meta = {
      version: String(opts?.meta?.version || "ULTRA_LUX_MAPS_v2"),
      author: String(opts?.meta?.author || "BCO"),
      difficulty: clamp(Number(opts?.meta?.difficulty ?? (name === "Astra" ? 1.10 : 1.00)), 0.6, 2.0),
      lootBias: clamp(Number(opts?.meta?.lootBias ?? (name === "Astra" ? 1.05 : 1.00)), 0.6, 1.8),
      // seed salt for deterministic spawns
      seedSalt: String(opts?.meta?.seedSalt || `${name}:seed`)
    };

    return { name, w, h, hw, hh, walls, bossSpawns, spawn, theme, zones, nav, meta };
  }

  // ---------------------------------------------------------
  // Spawn sampling
  // ---------------------------------------------------------
  function inBounds(map, x, y, pad = 80) {
    if (!map?.w || !map?.h) return true;
    const hw = map.w / 2 - pad;
    const hh = map.h / 2 - pad;
    return (x >= -hw && x <= hw && y >= -hh && y <= hh);
  }

  function pointInWall(map, x, y, r = 0) {
    if (!map?.walls?.length) return false;
    for (const w of map.walls) {
      // angle ignored for now (safe)
      if (pointInWallRect(w, x, y, r)) return true;
    }
    return false;
  }

  // returns a curated point by kind or a ring point
  function getSpawnPoint(map, kind = "ring", seed = 0) {
    const m = map || MAPS.get("Ashes");
    const rng = mulberry32((seed >>> 0) ^ hashStrToSeed(m?.meta?.seedSalt || "seed"));

    // Weighted points first (if exist)
    if (m?.spawn?.points?.length) {
      const p = pickWeighted(rng, m.spawn.points, "w");
      if (p) return { x: p.x, y: p.y };
    }

    // Fallback to ring
    const ringMin = Number(m?.spawn?.ringMin) || 520;
    const ringMax = Number(m?.spawn?.ringMax) || 880;
    const ang = rng() * Math.PI * 2;
    const rr = ringMin + rng() * Math.max(10, (ringMax - ringMin));
    return { x: Math.cos(ang) * rr, y: Math.sin(ang) * rr };
  }

  // smarter spawn: avoids player + walls; uses map points/rings; deterministic per wave
  function sampleSpawn(map, player, wave = 1, kind = "zombie") {
    const m = map || MAPS.get("Ashes");
    const px = Number(player?.x) || 0;
    const py = Number(player?.y) || 0;

    const avoidP = Number(m?.spawn?.avoidPlayerRadius) || 340;
    const tries = Number(m?.spawn?.maxTries) || 18;

    // deterministic seed: map + wave + kind
    const seed = (hashStrToSeed(`${m.name}:${kind}:${wave}`) ^ 0xA5A5F00D) >>> 0;
    const rng = mulberry32(seed);

    const ringMin = Number(m?.spawn?.ringMin) || 520;
    const ringMax = Number(m?.spawn?.ringMax) || 880;

    // optionally bias by zones (future objectives)
    const zones = Array.isArray(m.zones) ? m.zones : [];
    const zoneBias = (kind === "boss") ? "boss" : (kind === "zombie") ? "combat" : "any";

    function propose() {
      // 1) 40%: weighted spawn points
      if (m?.spawn?.points?.length && rng() < 0.40) {
        const p = pickWeighted(rng, m.spawn.points, "w");
        if (p) return { x: p.x, y: p.y };
      }

      // 2) 25%: zone-based (if any)
      if (zones.length && rng() < 0.25) {
        const z = pickWeighted(rng, zones.filter(z => !z.tags.length || z.tags.includes(zoneBias) || z.tags.includes("any")), "w")
          || zones[(rng() * zones.length) | 0];
        if (z) {
          const ang = rng() * Math.PI * 2;
          const rr = (z.r * 0.55) + rng() * (z.r * 0.45);
          return { x: z.x + Math.cos(ang) * rr, y: z.y + Math.sin(ang) * rr };
        }
      }

      // 3) ring around player (prefer outside)
      const ang = rng() * Math.PI * 2;
      const rr = ringMin + rng() * Math.max(10, (ringMax - ringMin));
      return { x: px + Math.cos(ang) * rr, y: py + Math.sin(ang) * rr };
    }

    for (let i = 0; i < tries; i++) {
      const p = propose();
      const dx = p.x - px;
      const dy = p.y - py;
      const d = len(dx, dy);

      // keep spawns away from player
      if (d < avoidP) continue;

      // bounds + walls
      if (!inBounds(m, p.x, p.y, 120)) continue;
      if (pointInWall(m, p.x, p.y, 18)) continue;

      return p;
    }

    // hard fallback: ring point (even if not perfect)
    const ang = rng() * Math.PI * 2;
    const rr = ringMin + rng() * Math.max(10, (ringMax - ringMin));
    return { x: px + Math.cos(ang) * rr, y: py + Math.sin(ang) * rr };
  }

  function debugSummary(name) {
    const m = MAPS.get(String(name || "")) || MAPS.get("Ashes");
    if (!m) return null;
    return {
      name: m.name,
      size: `${m.w}x${m.h}`,
      walls: m.walls?.length || 0,
      zones: m.zones?.length || 0,
      spawns: m.spawn?.points?.length || 0,
      bosses: m.bossSpawns?.length || 0,
      theme: m.theme
    };
  }

  // =========================================================
  // MAP: ASHES — “ember field” (open + crater + debris)
  // =========================================================
  MAPS.set("Ashes", mkMap({
    name: "Ashes",
    w: 2600,
    h: 2400,

    // chunky cover + crater ring
    walls: [
      // central crater rim (broken ring with gaps)
      { x: -220, y: -380, w: 560, h: 120, mat: "stone", tags: ["cover","rim"] },
      { x:  420, y: -220, w: 520, h: 120, mat: "stone", tags: ["cover","rim"] },
      { x:  140, y:  380, w: 560, h: 120, mat: "stone", tags: ["cover","rim"] },
      { x: -520, y:  220, w: 520, h: 120, mat: "stone", tags: ["cover","rim"] },

      // wreckage blocks
      { x: -980, y: -120, w: 380, h: 180, mat: "metal", tags: ["cover","wreck"] },
      { x:  980, y:  140, w: 420, h: 200, mat: "metal", tags: ["cover","wreck"] },

      // wood stacks
      { x: -240, y:  760, w: 240, h: 360, mat: "wood", tags: ["cover"] },
      { x:  520, y:  760, w: 240, h: 360, mat: "wood", tags: ["cover"] },

      // side slabs
      { x: -1120, y:  740, w: 520, h: 130, mat: "stone", tags: ["lane"] },
      { x:  1120, y: -720, w: 520, h: 130, mat: "stone", tags: ["lane"] }
    ],

    bossSpawns: [
      { wave: 5,  type: "brute" },
      { wave: 9,  type: "spitter" },
      { wave: 13, type: "brute" }
    ],

    spawn: {
      ringMin: 600,
      ringMax: 980,
      avoidPlayerRadius: 360,
      maxTries: 22,

      // weighted corners + mid edges
      points: [
        { x: -1120, y: -880, w: 1.10 },
        { x:  1120, y: -880, w: 1.10 },
        { x: -1120, y:  880, w: 1.10 },
        { x:  1120, y:  880, w: 1.10 },
        { x: -1240, y:    0, w: 0.85 },
        { x:  1240, y:    0, w: 0.85 },
        { x:    0, y: -980, w: 0.85 },
        { x:    0, y:  980, w: 0.85 }
      ],

      profiles: {
        far:   { preferPoints: 0.65, preferZones: 0.18 },
        chaos: { preferPoints: 0.40, preferZones: 0.28 }
      }
    },

    zones: [
      { id: "crater", name: "Crater", x: 0, y: 0, r: 420, tags: ["combat","any"], w: 1.1 },
      { id: "east",   name: "Wreck East", x: 980, y: 120, r: 260, tags: ["combat"], w: 1.0 },
      { id: "west",   name: "Wreck West", x: -980, y: -120, r: 260, tags: ["combat"], w: 1.0 },
      { id: "south",  name: "Stacks", x: 0, y: 780, r: 380, tags: ["combat"], w: 0.9 }
    ],

    theme: {
      bg: "ashes",
      fog: 0.30,
      tint: "warm",
      light: { key: "ember", intensity: 0.80, flicker: 0.12 },
      particles: { kind: "ash", density: 0.32 }
    },

    meta: {
      version: "ULTRA_LUX_MAPS_v2",
      author: "BCO",
      difficulty: 1.00,
      lootBias: 1.00,
      seedSalt: "Ashes:seed:v2"
    }
  }));

  // =========================================================
  // MAP: ASTRA — “neon lanes” (chokes + cover + routes)
  // =========================================================
  MAPS.set("Astra", mkMap({
    name: "Astra",
    w: 2600,
    h: 2400,

    // lanes/chokes + cover islands
    walls: [
      // north lane segments
      { x: -980, y: -520, w: 620, h: 140, mat: "metal", tags: ["lane","cover"] },
      { x: -240, y: -520, w: 520, h: 140, mat: "metal", tags: ["lane","cover"] },
      { x:  520, y: -520, w: 760, h: 140, mat: "metal", tags: ["lane","cover"] },

      // mid choke
      { x: -520, y:  140, w: 1120, h: 160, mat: "stone", tags: ["choke","cover"] },
      { x:  620, y:  140, w: 820,  h: 160, mat: "stone", tags: ["choke","cover"] },

      // south cover
      { x: -980, y:  720, w: 560, h: 140, mat: "stone", tags: ["lane","cover"] },
      { x:  260, y:  720, w: 900, h: 140, mat: "stone", tags: ["lane","cover"] },

      // small islands
      { x: -220, y: -80, w: 220, h: 220, mat: "metal", tags: ["island","cover"] },
      { x:  220, y: -80, w: 220, h: 220, mat: "metal", tags: ["island","cover"] }
    ],

    bossSpawns: [
      { wave: 4,  type: "spitter" },
      { wave: 8,  type: "brute" },
      { wave: 12, type: "brute" },
      { wave: 16, type: "spitter" }
    ],

    spawn: {
      ringMin: 560,
      ringMax: 900,
      avoidPlayerRadius: 360,
      maxTries: 22,

      // weighted lane endpoints
      points: [
        { x: -1240, y: 0,     w: 1.15 },
        { x:  1240, y: 0,     w: 1.15 },
        { x:  0,    y: -1040, w: 1.05 },
        { x:  0,    y:  1040, w: 1.05 },
        { x: -1180, y: -820,  w: 0.90 },
        { x:  1180, y: -820,  w: 0.90 },
        { x: -1180, y:  820,  w: 0.90 },
        { x:  1180, y:  820,  w: 0.90 }
      ],

      profiles: {
        lanes: { preferPoints: 0.72, preferZones: 0.10 },
        chaos: { preferPoints: 0.45, preferZones: 0.25 }
      }
    },

    zones: [
      { id: "north", name: "Neon Lane (N)", x: 0, y: -520, r: 540, tags: ["combat","any"], w: 1.15 },
      { id: "mid",   name: "Choke (Mid)",   x: 0, y: 120,  r: 460, tags: ["combat","boss"], w: 1.25 },
      { id: "south", name: "Depot (S)",     x: 0, y: 720,  r: 520, tags: ["combat","any"], w: 1.10 }
    ],

    theme: {
      bg: "asphalt",
      fog: 0.22,
      tint: "cool",
      light: { key: "neon", intensity: 0.88, flicker: 0.08 },
      particles: { kind: "dust", density: 0.22 }
    },

    meta: {
      version: "ULTRA_LUX_MAPS_v2",
      author: "BCO",
      difficulty: 1.10,
      lootBias: 1.05,
      seedSalt: "Astra:seed:v2"
    }
  }));

  // ---------------------------------------------------------
  // Public API
  // ---------------------------------------------------------
  window.BCO_ZOMBIES_MAPS = {
    get(name) {
      const key = String(name || "");
      return MAPS.get(key) || MAPS.get("Ashes");
    },
    list() {
      return Array.from(MAPS.keys());
    },
    normalizeWall,
    getSpawnPoint,
    sampleSpawn,
    pointInWall,
    debugSummary
  };

  console.log("[Z_MAPS] loaded (ULTRA LUX | 3D-READY)");
})();
