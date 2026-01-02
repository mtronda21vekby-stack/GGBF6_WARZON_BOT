/* =========================================================
   BLACK CROWN OPS — ZOMBIES BOSSES [LUX]
   File: app/webapp/static/zombies.bosses.js
   Provides:
     window.BCO_ZOMBIES_BOSSES.create(type,x,y,opts?)
     window.BCO_ZOMBIES_BOSSES.tick(CORE, dt, tms, map?)
     window.BCO_ZOMBIES_BOSSES.onBulletHit(CORE, boss, bullet) -> bool(consumed)
     window.BCO_ZOMBIES_BOSSES.install(CORE, mapGetter?)
   Notes:
     - Backward compatible with create(type,x,y)
     - Safe no-op if you don't call install()
     - Premium behaviors: phases, telegraphs, projectiles, shockwave, drops, wave scaling
   ========================================================= */
(() => {
  "use strict";

  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const len = (x, y) => Math.hypot(x, y) || 0;
  const norm = (x, y) => {
    const L = len(x, y);
    if (!L) return { x: 0, y: 0, L: 0 };
    return { x: x / L, y: y / L, L };
  };

  // ---------------------------------------------------------
  // Config (premium feel, not unfair)
  // ---------------------------------------------------------
  const CFG = {
    // Scaling by wave: hp * hpMul^(wave-1), speed * spMul^(wave-1)
    scale: { hpMul: 1.10, spMul: 1.03 },

    brute: {
      hp: 280,
      sp: 118,
      r: 28,
      touchDpsMs: 330,
      dmg: 16,

      slam: {
        cdMs: 3000,
        windupMs: 520,
        radius: 120,
        dmg: 22,
        knock: 220
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
      coinsWaveMul: 1.22
    }
  };

  // ---------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------
  function now() { return performance.now(); }

  function getPlayer(CORE) {
    return CORE?.state?.player || CORE?.p || null;
  }

  function getMapDefault(CORE) {
    return window.BCO_ZOMBIES_MAPS?.get?.(CORE?.meta?.map) || null;
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
    CORE._bossRT = CORE._bossRT || {
      projectiles: [], // spitter spit balls
      telegraphs: []   // render hints (optional)
    };
    return CORE._bossRT;
  }

  // ---------------------------------------------------------
  // Create (BACK-COMPAT)
  // ---------------------------------------------------------
  function mkBrute(x, y, wave = 1) {
    const b = {
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
  // opts: { wave }
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

  function damagePlayer(CORE, amount) {
    const p = getPlayer(CORE);
    if (!p) return;

    const mul = Number(CORE?._dmgMul || CORE?._perkRT?._dmgMul || CORE?._dmgMultiplier || 1.0);
    const dmg = Math.max(1, Math.round((Number(amount) || 0) * (Number.isFinite(mul) ? mul : 1.0)));

    // CORE-style
    if (CORE?.state?.player && typeof CORE.cfg?.player?.iFramesMs === "number") {
      try {
        const S = CORE.state;
        const tms = now();
        if ((tms - (S.player.lastHitAt || -99999)) < CORE.cfg.player.iFramesMs) return;
        S.player.lastHitAt = tms;
        S.player.hp = Math.max(0, (S.player.hp || 0) - dmg);
        if (S.player.hp <= 0) CORE.running = false;
      } catch {}
      return;
    }

    // Overlay fallback
    try {
      const tms = now();
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
        kind: "slam",
        x: boss.x, y: boss.y,
        r: CFG.brute.slam.radius,
        until: tms + CFG.brute.slam.windupMs
      });
    }

    if (slam.state === "windup") {
      moveSeek(boss, p, dt, spMul * 0.55);

      if ((tms - slam.startedAt) >= CFG.brute.slam.windupMs) {
        const dx = p.x - boss.x;
        const dy = p.y - boss.y;
        if (len(dx, dy) <= CFG.brute.slam.radius) {
          damagePlayer(CORE, CFG.brute.slam.dmg);
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
        damagePlayer(CORE, CFG.brute.dmg);
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

    // spacing
    const dx = p.x - boss.x;
    const dy = p.y - boss.y;
    const d = len(dx, dy);

    if (d < 220) {
      const n = norm(-dx, -dy);
      boss.vx = n.x * boss.sp * 0.85;
      boss.vy = n.y * boss.sp * 0.85;
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
        kind: "spit",
        x: boss.x, y: boss.y,
        until: tms + CFG.spitter.spit.windupMs
      });
    }

    if (spit.state === "windup") {
      if ((tms - spit.startedAt) >= CFG.spitter.spit.windupMs) {
        const shots = boss.frenzy ? 2 : 1;
        const rt = ensureRT(CORE);

        for (let i = 0; i < shots; i++) {
          const n = norm(p.x - boss.x, p.y - boss.y);
          const spread = boss.frenzy ? 0.18 : 0.10;
          const ang = Math.atan2(n.y, n.x) + (i === 0 ? 0 : (i === 1 ? spread : -spread));
          const vx = Math.cos(ang) * CFG.spitter.spit.speed;
          const vy = Math.sin(ang) * CFG.spitter.spit.speed;

          rt.projectiles.push({
            kind: "spit",
            x: boss.x + Math.cos(ang) * (boss.r + 6),
            y: boss.y + Math.sin(ang) * (boss.r + 6),
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
        damagePlayer(CORE, CFG.spitter.dmg);
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

    const walls = map?.walls || null;

    for (let i = rt.projectiles.length - 1; i >= 0; i--) {
      const pr = rt.projectiles[i];
      pr.x += pr.vx * dt;
      pr.y += pr.vy * dt;

      if ((tms - pr.born) > pr.life) {
        rt.projectiles.splice(i, 1);
        continue;
      }

      // hit walls -> vanish
      if (walls && window.BCO_ZOMBIES_COLLISIONS?.collideBullets) {
        const tmp = [pr];
        window.BCO_ZOMBIES_COLLISIONS.collideBullets(tmp, map);
        if (tmp.length === 0) {
          rt.projectiles.splice(i, 1);
          continue;
        }
      }

      // hit player
      const d = len(p.x - pr.x, p.y - pr.y);
      if (d < (playerHitbox(CORE) + pr.r)) {
        damagePlayer(CORE, pr.dmg);

        // optional slow hook (if perks/world uses it)
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
  // Bullet hit hook
  // ---------------------------------------------------------
  function onBulletHit(CORE, boss, bullet) {
    if (!boss || !bullet) return false;

    const crit = (Math.random() < 0.10);
    const dmg = Number(bullet.dmg || 0);
    const dealt = crit ? Math.round(dmg * 1.35) : dmg;

    boss.hp -= dealt;

    if (boss.hp <= 0) {
      try {
        const w = waveOf(CORE);
        const add = Math.round(CFG.drops.coinsBase * Math.pow(CFG.drops.coinsWaveMul, Math.max(0, w - 1)));
        if (Number.isFinite(CORE?.state?.coins)) CORE.state.coins += add;
        else if (Number.isFinite(CORE?.coins)) CORE.coins += add;
      } catch {}
    }

    if (Number(bullet.pierce || 0) > 0) {
      bullet.pierce -= 1;
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

    // spawn bosses from map config (bossSpawns)
    try {
      const S = CORE.state || CORE;
      const w = waveOf(CORE);
      S._bossSpawned = S._bossSpawned || {};
      const key = String(m?.name || CORE?.meta?.map || "Ashes");

      const sp = m?.bossSpawns || [];
      for (const s of sp) {
        const wave = Number(s.wave || 0) | 0;
        if (wave !== w) continue;

        const id = `${key}:${wave}:${String(s.type || "brute")}`;
        if (S._bossSpawned[id]) continue;

        const p = getPlayer(CORE);
        if (!p) continue;

        const ang = Math.random() * Math.PI * 2;
        const ringMax = Number(m?.spawn?.ringMax || 880);
        const rr = ringMax + 120;
        const bx = p.x + Math.cos(ang) * rr;
        const by = p.y + Math.sin(ang) * rr;

        const boss = create(String(s.type || "brute"), bx, by, { wave: w });

        const list = CORE?.state?.zombies || CORE?.zombies;
        if (Array.isArray(list)) list.push(boss);

        S._bossSpawned[id] = true;
      }
    } catch {}

    // tick bosses that live in zombies list
    const list = CORE?.state?.zombies || CORE?.zombies || null;
    if (!Array.isArray(list) || !list.length) {
      tickProjectiles(CORE, dt, tms, m);
      pruneTelegraphs(CORE, tms);
      return true;
    }

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

    tickProjectiles(CORE, dt, tms, m);
    pruneTelegraphs(CORE, tms);

    return true;
  }

  // ---------------------------------------------------------
  // Install: hook CORE world + bullet hook
  // ---------------------------------------------------------
  function install(CORE, mapGetter) {
    if (!CORE || typeof CORE !== "object") return false;

    const getMap = (typeof mapGetter === "function") ? mapGetter : () => getMapDefault(CORE);

    // wrap tick world
    const prevTick = CORE._tickWorld;
    CORE._tickWorld = (core, dt, tms) => {
      try { if (typeof prevTick === "function") prevTick(core, dt, tms); } catch {}
      try { tick(core, dt, tms, getMap()); } catch {}
    };

    // bullet hit hook for boss damage
    const prevHit = CORE._onBulletHit;
    CORE._onBulletHit = (core, zombie, bullet) => {
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

  console.log("[Z_BOSSES] loaded (LUX)");
})();
