/* =========================================================
   BLACK CROWN OPS — ZOMBIES BOSSES [ULTRA LUX | 3D-READY]
   File: app/webapp/static/zombies.bosses.js

   Provides:
     window.BCO_ZOMBIES_BOSSES.create(type,x,y,opts?)
     window.BCO_ZOMBIES_BOSSES.tick(CORE, dt, tms, map?)
     window.BCO_ZOMBIES_BOSSES.onBulletHit(CORE, boss, bullet) -> bool(consumed)
     window.BCO_ZOMBIES_BOSSES.install(CORE, mapGetter?)

   ULTRA LUX upgrades:
     ✅ Proper boss spawn controller (per-map schedule + cooldown guard)
     ✅ 3D-ready “fx bus”: CORE._bossRT.telegraphs/projectiles with stable ids
     ✅ Spitter projectiles use swept collision (no tunneling) + wall interaction
     ✅ Boss loot uses CORE._spawnPickup when available (roguelike economy fixed)
     ✅ Fairness: iFrames respected, telegraphed slams, soft aim/spacing
     ✅ Phase logic: enrage/frenzy with readable curves
     ✅ Back-compat: works if CORE is old (no crash) and if map is missing

   Notes:
     - No UI changes here.
     - Renderer can optionally read CORE._bossRT.telegraphs/projectiles.
   ========================================================= */
(() => {
  "use strict";

  // ---------------------------------------------------------
  // Safe time
  // ---------------------------------------------------------
  const _now = () =>
    (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now();

  // ---------------------------------------------------------
  // Math
  // ---------------------------------------------------------
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const len = (x, y) => Math.hypot(x, y) || 0;
  const norm = (x, y) => {
    const L = len(x, y);
    if (!L || !Number.isFinite(L)) return { x: 0, y: 0, L: 0 };
    return { x: x / L, y: y / L, L };
  };
  const rand = (a, b) => a + Math.random() * (b - a);
  const pick = (arr) => arr[(Math.random() * arr.length) | 0];

  // Stable ids for 3D renderer (telegraphs/projectiles)
  let _fxid = 1;
  const nextFxId = () => (_fxid++);

  // ---------------------------------------------------------
  // Config (premium feel, not unfair)
  // ---------------------------------------------------------
  const CFG = {
    // Scaling by wave: hp * hpMul^(wave-1), speed * spMul^(wave-1)
    scale: { hpMul: 1.10, spMul: 1.03 },

    // Global spawn guard (prevents double-spawn with multiple modules)
    spawnGuardMs: 800,

    brute: {
      hp: 280,
      sp: 118,
      r: 28,
      touchDpsMs: 330,
      dmg: 16,

      slam: {
        cdMs: 3000,
        windupMs: 540,
        radius: 130,
        dmg: 22,
        knock: 240
      },

      enrageAt: 0.45,
      enrageSpMul: 1.18
    },

    spitter: {
      hp: 190,
      sp: 150,
      r: 22,
      touchDpsMs: 340,
      dmg: 12,

      spit: {
        cdMs: 1500,
        windupMs: 320,
        speed: 520,
        lifeMs: 2200,
        radius: 7,
        dmg: 14,
        slowSec: 1.2
      },

      frenzyAt: 0.40,
      frenzyCdMul: 0.75
    },

    drops: {
      coinsBase: 8,
      coinsWaveMul: 1.22,
      // roguelike “feel”: a boss always drops at least something good
      alwaysDropEvent: true,
      alwaysDropWeapon: true,
      // safety clamps
      maxCoinsDrop: 120
    }
  };

  // ---------------------------------------------------------
  // Helpers (CORE compatibility)
  // ---------------------------------------------------------
  function getPlayer(CORE) {
    return CORE?.state?.player || CORE?.p || null;
  }

  function getMapDefault(CORE) {
    try { return window.BCO_ZOMBIES_MAPS?.get?.(CORE?.meta?.map) || null; } catch { return null; }
  }

  function waveOf(CORE) {
    return (Number(CORE?.state?.wave || CORE?.wave || 1) | 0) || 1;
  }

  function playerHitbox(CORE) {
    const hb = CORE?.cfg?.player?.hitbox;
    return Number.isFinite(hb) ? hb : 16;
  }

  function scaleBoss(boss, wave) {
    const w = Math.max(1, wave | 0);
    const hpMul = Math.pow(CFG.scale.hpMul, Math.max(0, w - 1));
    const spMul = Math.pow(CFG.scale.spMul, Math.max(0, w - 1));
    boss.hpMax = Math.round((boss.hpMax || boss.hp || 1) * hpMul);
    boss.hp = boss.hpMax;
    boss.sp = (boss.sp || 0) * spMul;
  }

  function ensureRT(CORE) {
    // Single runtime bus for FX + spawn guards
    CORE._bossRT = CORE._bossRT || {
      projectiles: [], // spit balls
      telegraphs: [],  // slam/spit warnings
      spawnGuard: { lastAt: 0 }
    };
    return CORE._bossRT;
  }

  function coreIsRogue(CORE) {
    const m = String(CORE?.meta?.mode || CORE?.mode || "").toLowerCase();
    return m.includes("rogue");
  }

  // ---------------------------------------------------------
  // Loot helpers (fix roguelike economy)
  // ---------------------------------------------------------
  function spawnPickup(CORE, kind, x, y, data) {
    // Prefer CORE._spawnPickup if your LUX core exists (best feel: magnet, life, etc.)
    try {
      if (typeof CORE?._spawnPickup === "function") {
        CORE._spawnPickup(kind, x, y, data);
        return true;
      }
    } catch {}

    // Fallback: direct push into state.pickups (compatible with your core format)
    try {
      const S = CORE?.state;
      if (!S || !Array.isArray(S.pickups)) return false;
      const t = _now();
      S.pickups.push({
        id: nextFxId(),
        kind,
        x, y,
        px: x, py: y,
        vx: rand(-18, 18),
        vy: rand(-18, 18),
        born: t,
        life: 12000,
        data: data || null,
        r: 10
      });
      return true;
    } catch { return false; }
  }

  function bossDrops(CORE, boss) {
    if (!coreIsRogue(CORE)) return;

    const w = waveOf(CORE);
    const coinsRaw = Math.round(CFG.drops.coinsBase * Math.pow(CFG.drops.coinsWaveMul, Math.max(0, w - 1)));
    const coins = clamp(coinsRaw, 6, CFG.drops.maxCoinsDrop);

    // Coins
    spawnPickup(CORE, "coins", boss.x, boss.y, { amount: coins });

    // Always: one event + one weapon (ultra feel)
    if (CFG.drops.alwaysDropEvent) {
      spawnPickup(CORE, "event", boss.x + 22, boss.y, { event: pick(["max_ammo", "double_points", "insta_kill"]) });
    }

    if (CFG.drops.alwaysDropWeapon) {
      // Prefer CORE rollRarity if exists; else reasonable fallback
      let rarity = "rare";
      try {
        if (typeof CORE?.cfg?.loot?.weaponChanceWaveBonus === "number" && typeof CORE?.cfg?.weapons === "object") {
          // Slightly better than wave-based default
          const t = Math.random();
          if (t < 0.04) rarity = "legendary";
          else if (t < 0.12) rarity = "epic";
          else if (t < 0.30) rarity = "rare";
          else rarity = "uncommon";
        }
      } catch {}

      let wkey = "SMG";
      try {
        const keys = Object.keys(CORE?.cfg?.weapons || { SMG: 1, AR: 1, SG: 1, LMG: 1, MARK: 1, PIST: 1 });
        wkey = keys[(Math.random() * keys.length) | 0] || "SMG";
      } catch {}

      const up = clamp(Math.floor((w - 1) / 5), 1, 4);
      spawnPickup(CORE, "weapon", boss.x - 22, boss.y, { weaponKey: wkey, rarity, upgrade: up });
    }

    // Plate as “lux safety”
    spawnPickup(CORE, "plate", boss.x, boss.y + 22, { amount: 1 });
  }

  // ---------------------------------------------------------
  // Create (BACK-COMPAT)
  // ---------------------------------------------------------
  function mkBrute(x, y, wave = 1) {
    const b = {
      id: nextFxId(),
      kind: "boss_brute",
      type: "brute",
      x, y, vx: 0, vy: 0,
      r: CFG.brute.r,
      sp: CFG.brute.sp,
      hpMax: CFG.brute.hp,
      hp: CFG.brute.hp,

      nextTouchAt: 0,
      slam: { nextAt: 0, state: "ready", startedAt: 0 },
      enraged: false
    };
    scaleBoss(b, wave);
    return b;
  }

  function mkSpitter(x, y, wave = 1) {
    const b = {
      id: nextFxId(),
      kind: "boss_spitter",
      type: "spitter",
      x, y, vx: 0, vy: 0,
      r: CFG.spitter.r,
      sp: CFG.spitter.sp,
      hpMax: CFG.spitter.hp,
      hp: CFG.spitter.hp,

      nextTouchAt: 0,
      spit: { nextAt: 0, state: "ready", startedAt: 0 },
      frenzy: false
    };
    scaleBoss(b, wave);
    return b;
  }

  // Public create(type,x,y,opts?)
  function create(type, x, y, opts = null) {
    const t = String(type || "brute").toLowerCase();
    const w = Math.max(1, Number(opts?.wave || 1) | 0);
    if (t === "spitter") return mkSpitter(x, y, w);
    return mkBrute(x, y, w);
  }

  // ---------------------------------------------------------
  // Movement / Damage helpers
  // ---------------------------------------------------------
  function moveSeek(boss, player, dt, speedMul = 1.0) {
    const dx = (player.x - boss.x);
    const dy = (player.y - boss.y);
    const n = norm(dx, dy);
    boss.vx = n.x * (boss.sp * speedMul);
    boss.vy = n.y * (boss.sp * speedMul);
    boss.x += boss.vx * dt;
    boss.y += boss.vy * dt;
  }

  function damagePlayer(CORE, amount, tms) {
    const p = getPlayer(CORE);
    if (!p) return;

    const mul = Number(CORE?._dmgMul || CORE?._perkRT?._dmgMul || CORE?._dmgMultiplier || 1.0);
    const dmg = Math.max(1, Math.round((Number(amount) || 0) * (Number.isFinite(mul) ? mul : 1.0)));

    // Preferred: LUX core has _damagePlayer
    try {
      if (typeof CORE?._damagePlayer === "function") {
        CORE._damagePlayer(dmg, tms);
        return;
      }
    } catch {}

    // CORE-style (state.player)
    try {
      const S = CORE.state;
      const ifr = CORE?.cfg?.player?.iFramesMs || 220;
      if ((tms - (S.player.lastHitAt || -99999)) < ifr) return;
      S.player.lastHitAt = tms;

      S.player.hp = Math.max(0, (S.player.hp || 0) - dmg);
      if (S.player.hp <= 0) CORE.running = false;
      return;
    } catch {}

    // Overlay fallback
    try {
      const ifr = CORE?.cfg?.player?.iFramesMs || 220;
      if (typeof p.lastHitAt === "number" && (tms - p.lastHitAt) < ifr) return;
      p.lastHitAt = tms;
      p.hp = Math.max(0, (p.hp || 0) - dmg);
    } catch {}
  }

  // ---------------------------------------------------------
  // Boss ticks
  // ---------------------------------------------------------
  function bruteTick(CORE, boss, dt, tms, map) {
    const p = getPlayer(CORE);
    if (!p) return;

    const hpPct = (boss.hpMax > 0) ? (boss.hp / boss.hpMax) : 1;
    if (!boss.enraged && hpPct <= CFG.brute.enrageAt) boss.enraged = true;

    const spMul = boss.enraged ? CFG.brute.enrageSpMul : 1.0;

    const slam = boss.slam;
    if (slam.state === "ready" && tms >= slam.nextAt) {
      slam.state = "windup";
      slam.startedAt = tms;

      const rt = ensureRT(CORE);
      rt.telegraphs.push({
        id: nextFxId(),
        kind: "slam",
        x: boss.x, y: boss.y,
        r: CFG.brute.slam.radius,
        until: tms + CFG.brute.slam.windupMs
      });
    }

    if (slam.state === "windup") {
      // slower approach during windup for fairness
      moveSeek(boss, p, dt, spMul * 0.55);

      if ((tms - slam.startedAt) >= CFG.brute.slam.windupMs) {
        const dx = p.x - boss.x;
        const dy = p.y - boss.y;
        if (len(dx, dy) <= CFG.brute.slam.radius) {
          damagePlayer(CORE, CFG.brute.slam.dmg, tms);
          const n = norm(dx, dy);
          p.x += n.x * CFG.brute.slam.knock * 0.25;
          p.y += n.y * CFG.brute.slam.knock * 0.25;
        }

        slam.nextAt = tms + CFG.brute.slam.cdMs;
        slam.state = "ready";
      }
    } else {
      moveSeek(boss, p, dt, spMul);
    }

    // contact DPS
    const dist = len(p.x - boss.x, p.y - boss.y);
    if (dist < (boss.r + playerHitbox(CORE))) {
      if (tms >= boss.nextTouchAt) {
        boss.nextTouchAt = tms + CFG.brute.touchDpsMs;
        damagePlayer(CORE, CFG.brute.dmg, tms);
      }
    }

    // map collision
    try {
      const C = window.BCO_ZOMBIES_COLLISIONS;
      if (C?.collideEntityWithMap) C.collideEntityWithMap(boss, map);
    } catch {}
  }

  function spitterTick(CORE, boss, dt, tms, map) {
    const p = getPlayer(CORE);
    if (!p) return;

    const hpPct = (boss.hpMax > 0) ? (boss.hp / boss.hpMax) : 1;
    if (!boss.frenzy && hpPct <= CFG.spitter.frenzyAt) boss.frenzy = true;

    const spit = boss.spit;
    const cdMul = boss.frenzy ? CFG.spitter.frenzyCdMul : 1.0;
    const cdMs = Math.max(650, CFG.spitter.spit.cdMs * cdMul);

    // spacing: keep mid-range
    const dx = p.x - boss.x;
    const dy = p.y - boss.y;
    const d = len(dx, dy);

    if (d < 220) {
      const n = norm(-dx, -dy);
      boss.vx = n.x * boss.sp * 0.90;
      boss.vy = n.y * boss.sp * 0.90;
      boss.x += boss.vx * dt;
      boss.y += boss.vy * dt;
    } else {
      moveSeek(boss, p, dt, 1.0);
    }

    if (spit.state === "ready" && tms >= spit.nextAt) {
      spit.state = "windup";
      spit.startedAt = tms;

      const rt = ensureRT(CORE);
      rt.telegraphs.push({
        id: nextFxId(),
        kind: "spit",
        x: boss.x, y: boss.y,
        until: tms + CFG.spitter.spit.windupMs
      });
    }

    if (spit.state === "windup") {
      if ((tms - spit.startedAt) >= CFG.spitter.spit.windupMs) {
        const shots = boss.frenzy ? 2 : 1;
        const rt = ensureRT(CORE);

        const base = norm(p.x - boss.x, p.y - boss.y);
        const baseAng = Math.atan2(base.y, base.x);
        const spread = boss.frenzy ? 0.18 : 0.10;

        for (let i = 0; i < shots; i++) {
          const a = baseAng + (i === 0 ? 0 : (i === 1 ? spread : -spread));
          const vx = Math.cos(a) * CFG.spitter.spit.speed;
          const vy = Math.sin(a) * CFG.spitter.spit.speed;

          rt.projectiles.push({
            id: nextFxId(),
            kind: "spit",
            x: boss.x + Math.cos(a) * (boss.r + 6),
            y: boss.y + Math.sin(a) * (boss.r + 6),
            px: boss.x + Math.cos(a) * (boss.r + 6),
            py: boss.y + Math.sin(a) * (boss.r + 6),
            vx, vy,
            born: tms,
            life: CFG.spitter.spit.lifeMs,
            r: CFG.spitter.spit.radius,
            dmg: CFG.spitter.spit.dmg,
            slowSec: CFG.spitter.spit.slowSec
          });
        }

        spit.nextAt = tms + cdMs;
        spit.state = "ready";
      }
    }

    // contact DPS
    if (d < (boss.r + playerHitbox(CORE))) {
      if (tms >= boss.nextTouchAt) {
        boss.nextTouchAt = tms + CFG.spitter.touchDpsMs;
        damagePlayer(CORE, CFG.spitter.dmg, tms);
      }
    }

    // map collision
    try {
      const C = window.BCO_ZOMBIES_COLLISIONS;
      if (C?.collideEntityWithMap) C.collideEntityWithMap(boss, map);
    } catch {}
  }

  // ---------------------------------------------------------
  // Projectiles + telegraphs
  // ---------------------------------------------------------
  function tickProjectiles(CORE, dt, tms, map) {
    const rt = ensureRT(CORE);
    if (!rt.projectiles.length) return;

    const p = getPlayer(CORE);
    if (!p) return;

    const C = window.BCO_ZOMBIES_COLLISIONS || null;

    for (let i = rt.projectiles.length - 1; i >= 0; i--) {
      const pr = rt.projectiles[i];

      // keep prev for swept
      pr.px = pr.x; pr.py = pr.y;

      pr.x += pr.vx * dt;
      pr.y += pr.vy * dt;

      if ((tms - pr.born) > pr.life) {
        rt.projectiles.splice(i, 1);
        continue;
      }

      // wall collision (swept) -> vanish
      try {
        if (C?.collideBullets && map) {
          const tmp = [pr];
          C.collideBullets(tmp, map, { mode: "swept" });
          if (tmp.length === 0) {
            rt.projectiles.splice(i, 1);
            continue;
          }
        }
      } catch {}

      // hit player (swept-ish): check segment midpoint too
      const hb = playerHitbox(CORE);
      const d1 = len(p.x - pr.x, p.y - pr.y);
      const mx = (pr.px + pr.x) * 0.5;
      const my = (pr.py + pr.y) * 0.5;
      const d2 = len(p.x - mx, p.y - my);

      if (Math.min(d1, d2) < (hb + pr.r)) {
        damagePlayer(CORE, pr.dmg, tms);

        // slow hook (world/perks can read CORE._perkRT._slowUntil)
        try {
          const slowSec = Number(pr.slowSec || 0);
          if (slowSec > 0) {
            CORE._perkRT = CORE._perkRT || {};
            CORE._perkRT._slowUntil = Math.max(CORE._perkRT._slowUntil || 0, (tms + slowSec * 1000));
          }
        } catch {}

        rt.projectiles.splice(i, 1);
      }
    }
  }

  function pruneTelegraphs(CORE, tms) {
    const rt = ensureRT(CORE);
    if (!rt.telegraphs.length) return;
    for (let i = rt.telegraphs.length - 1; i >= 0; i--) {
      if (tms >= (rt.telegraphs[i].until || 0)) rt.telegraphs.splice(i, 1);
    }
  }

  // ---------------------------------------------------------
  // Bullet hit hook (boss takes damage; CORE decides pierce)
  // ---------------------------------------------------------
  function onBulletHit(CORE, boss, bullet) {
    if (!boss || !bullet) return false;

    const dmg = Number(bullet.dmg || 0);
    if (!Number.isFinite(dmg) || dmg <= 0) return false;

    // small crit spice (boss-only)
    const crit = (Math.random() < 0.10);
    const dealt = crit ? Math.round(dmg * 1.35) : Math.round(dmg);

    boss.hp -= dealt;

    if (boss.hp <= 0) {
      boss.hp = 0;

      // Drops (roguelike fix)
      try { bossDrops(CORE, boss); } catch {}
    }

    // Respect bullet pierce (if any); consumed if no pierce
    const pierce = Number(bullet.pierce || 0) | 0;
    if (pierce > 0) {
      bullet.pierce = pierce - 1;
      return false;
    }
    return true;
  }

  // ---------------------------------------------------------
  // Tick: spawn + AI + projectiles
  // ---------------------------------------------------------
  function tick(CORE, dt, tms, map) {
    if (!CORE) return false;

    const m = map || getMapDefault(CORE) || null;

    // Spawn bosses from map config (bossSpawns) with spawn guard
    try {
      const S = CORE.state || CORE;
      const w = waveOf(CORE);

      const rt = ensureRT(CORE);
      const guard = rt.spawnGuard || (rt.spawnGuard = { lastAt: 0 });
      const canSpawn = (tms - (guard.lastAt || 0)) > CFG.spawnGuardMs;

      S._bossSpawned = S._bossSpawned || {};
      const key = String(m?.name || CORE?.meta?.map || "Ashes");

      const sp = m?.bossSpawns || [];
      for (const s of sp) {
        const wave = Number(s.wave || 0) | 0;
        if (wave !== w) continue;

        const id = `${key}:${wave}:${String(s.type || "brute")}`;
        if (S._bossSpawned[id]) continue;
        if (!canSpawn) continue;

        const p = getPlayer(CORE);
        if (!p) continue;

        // Spawn around player outside ringMax
        const ang = Math.random() * Math.PI * 2;
        const ringMax = Number(m?.spawn?.ringMax || CORE?.cfg?.wave?.spawnRingMax || 880);
        const rr = ringMax + 140;

        const bx = p.x + Math.cos(ang) * rr;
        const by = p.y + Math.sin(ang) * rr;

        const boss = create(String(s.type || "brute"), bx, by, { wave: w });

        const list = CORE?.state?.zombies || CORE?.zombies;
        if (Array.isArray(list)) {
          list.push(boss);
          S._bossSpawned[id] = true;
          guard.lastAt = tms;

          // Add a spawn telegraph “ping” for renderer (optional)
          try {
            ensureRT(CORE).telegraphs.push({
              id: nextFxId(),
              kind: "boss_spawn",
              x: boss.x, y: boss.y,
              r: boss.r + 42,
              until: tms + 600
            });
          } catch {}
        }
      }
    } catch {}

    // Tick bosses that live in zombies list
    const list = CORE?.state?.zombies || CORE?.zombies || null;
    if (Array.isArray(list) && list.length) {
      for (let i = list.length - 1; i >= 0; i--) {
        const z = list[i];
        if (!z || (z.kind !== "boss_brute" && z.kind !== "boss_spitter")) continue;

        if (z.hp <= 0) {
          list.splice(i, 1);
          continue;
        }

        if (z.kind === "boss_brute") bruteTick(CORE, z, dt, tms, m);
        else spitterTick(CORE, z, dt, tms, m);
      }
    }

    tickProjectiles(CORE, dt, tms, m);
    pruneTelegraphs(CORE, tms);
    return true;
  }

  // ---------------------------------------------------------
  // Install: hook CORE world + bullet hit hook
  // ---------------------------------------------------------
  function install(CORE, mapGetter) {
    if (!CORE || typeof CORE !== "object") return false;

    const getMap = (typeof mapGetter === "function") ? mapGetter : () => getMapDefault(CORE);

    // wrap world tick
    const prevTick = CORE._tickWorld;
    CORE._tickWorld = function (core, dt, tms) {
      try { if (typeof prevTick === "function") prevTick(core, dt, tms); } catch {}
      try { tick(core, dt, tms, getMap()); } catch {}
    };

    // boss bullet hook
    const prevHit = CORE._onBulletHit;
    CORE._onBulletHit = function (core, zombie, bullet) {
      // allow previous hook first
      try {
        if (typeof prevHit === "function") {
          const consumed = !!prevHit(core, zombie, bullet);
          if (consumed) return true;
        }
      } catch {}

      if (zombie && (zombie.kind === "boss_brute" || zombie.kind === "boss_spitter")) {
        return !!onBulletHit(core, zombie, bullet);
      }
      return false;
    };

    // expose fx bus to renderer consumers
    ensureRT(CORE);

    return true;
  }

  // ---------------------------------------------------------
  // Export
  // ---------------------------------------------------------
  window.BCO_ZOMBIES_BOSSES = {
    cfg: CFG,
    create,
    tick,
    onBulletHit,
    install
  };

  console.log("[Z_BOSSES] loaded (ULTRA LUX | 3D-READY)");
})();
