/* =========================================================
   BLACK CROWN OPS — ZOMBIES CORE (GAME LOGIC ONLY)
   File: app/webapp/static/zombies.core.js
   ========================================================= */

(() => {
  "use strict";

  // =========================================================
  // CORE STATE (NO UI, NO DOM)
  // =========================================================
  const now = () => performance.now();

  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const dist2 = (ax, ay, bx, by) => {
    const dx = ax - bx, dy = ay - by;
    return dx * dx + dy * dy;
  };

  // =========================================================
  // CONFIG
  // =========================================================
  const CONFIG = {
    player: {
      r: 14,
      baseHp: 100,
      baseSpeed: 220
    },
    armor: {
      plateValue: 50,
      platesMax: 3,
      armorMax: 150
    },
    waves: {
      arcadeLen: 17000,
      rogueLen: 15000
    }
  };

  // =========================================================
  // WEAPONS
  // =========================================================
  const WEAPONS = {
    SMG:   { dmg: 13, rpm: 720, speed: 980, spread: 0.09, mag: 30, reload: 1.35, crit: 1.6 },
    AR:    { dmg: 17, rpm: 600, speed: 1050, spread: 0.07, mag: 30, reload: 1.55, crit: 1.75 },
    LMG:   { dmg: 16, rpm: 520, speed: 980, spread: 0.10, mag: 60, reload: 2.15, crit: 1.6 },
    SNIPER:{ dmg: 70, rpm: 70,  speed: 1400,spread: 0.02, mag: 5,  reload: 2.0,  crit: 2.2 }
  };

  // =========================================================
  // CORE RUNTIME
  // =========================================================
  const CORE = {
    running: false,
    mode: "arcade", // arcade | roguelike

    startedAt: 0,
    lastTick: 0,

    wave: 1,
    kills: 0,
    coins: 0,

    world: { w: 0, h: 0 },

    player: {
      x: 0, y: 0,
      r: CONFIG.player.r,
      hp: CONFIG.player.baseHp,
      maxHp: CONFIG.player.baseHp,
      armor: 0,
      plates: 0,
      speedMul: 1
    },

    weapon: {
      name: "SMG",
      ammo: 0,
      reloading: false,
      reloadAt: 0,
      lastShot: 0
    },

    input: {
      moveX: 0,
      moveY: 0,
      aimX: 1,
      aimY: 0,
      shooting: false
    },

    zombies: [],
    bullets: [],
    particles: [],

    spawnAt: 0,
    waveEndsAt: 0
  };

  // =========================================================
  // INIT / RESET
  // =========================================================
  function reset(worldW, worldH) {
    CORE.world.w = worldW;
    CORE.world.h = worldH;

    CORE.running = false;
    CORE.startedAt = 0;
    CORE.lastTick = 0;

    CORE.wave = 1;
    CORE.kills = 0;
    CORE.coins = 0;

    CORE.player.x = worldW * 0.5;
    CORE.player.y = worldH * 0.55;
    CORE.player.hp = CORE.player.maxHp;
    CORE.player.armor = 0;
    CORE.player.plates = 0;

    CORE.weapon.name = "SMG";
    const w = WEAPONS.SMG;
    CORE.weapon.ammo = w.mag;
    CORE.weapon.reloading = false;
    CORE.weapon.reloadAt = 0;
    CORE.weapon.lastShot = 0;

    CORE.zombies.length = 0;
    CORE.bullets.length = 0;

    CORE.spawnAt = now() + 800;
    CORE.waveEndsAt = now() + CONFIG.waves.arcadeLen;
  }

  // =========================================================
  // ZOMBIES
  // =========================================================
  function spawnZombie() {
    const side = Math.floor(Math.random() * 4);
    const pad = 40;
    let x = 0, y = 0;

    if (side === 0) { x = -pad; y = Math.random() * CORE.world.h; }
    if (side === 1) { x = CORE.world.w + pad; y = Math.random() * CORE.world.h; }
    if (side === 2) { x = Math.random() * CORE.world.w; y = -pad; }
    if (side === 3) { x = Math.random() * CORE.world.w; y = CORE.world.h + pad; }

    const baseHp = 22 + CORE.wave * 1.4;

    CORE.zombies.push({
      x, y,
      r: 16,
      hp: baseHp,
      maxHp: baseHp,
      spd: 52 + CORE.wave * 0.95,
      dmg: 8 + CORE.wave * 0.12
    });
  }

  // =========================================================
  // SHOOTING
  // =========================================================
  function canShoot(t) {
    if (!CORE.running) return false;
    if (CORE.weapon.reloading) return false;
    const w = WEAPONS[CORE.weapon.name];
    const dt = 60000 / w.rpm;
    return (t - CORE.weapon.lastShot) >= dt;
  }

  function startReload(t) {
    const w = WEAPONS[CORE.weapon.name];
    if (CORE.weapon.ammo >= w.mag) return;
    CORE.weapon.reloading = true;
    CORE.weapon.reloadAt = t + w.reload * 1000;
  }

  function finishReload() {
    const w = WEAPONS[CORE.weapon.name];
    CORE.weapon.ammo = w.mag;
    CORE.weapon.reloading = false;
  }

  function shoot(t) {
    if (!canShoot(t)) return;
    const w = WEAPONS[CORE.weapon.name];

    if (CORE.weapon.ammo <= 0) {
      startReload(t);
      return;
    }

    CORE.weapon.lastShot = t;
    CORE.weapon.ammo--;

    const dx = CORE.input.aimX;
    const dy = CORE.input.aimY;
    const ang = Math.atan2(dy, dx) + (Math.random() * 2 - 1) * w.spread;

    CORE.bullets.push({
      x: CORE.player.x,
      y: CORE.player.y,
      vx: Math.cos(ang) * w.speed,
      vy: Math.sin(ang) * w.speed,
      dmg: w.dmg,
      life: 1.2,
      t: 0
    });
  }

  // =========================================================
  // DAMAGE
  // =========================================================
  function applyPlayerDamage(dmg) {
    let left = dmg;
    if (CORE.player.armor > 0) {
      const used = Math.min(CORE.player.armor, left);
      CORE.player.armor -= used;
      left -= used;
    }
    if (left > 0) CORE.player.hp -= left;
  }

  // =========================================================
  // UPDATE LOOP
  // =========================================================
  function tick(dt, t) {
    // reload
    if (CORE.weapon.reloading && t >= CORE.weapon.reloadAt) finishReload();

    // movement
    const speed = CONFIG.player.baseSpeed * CORE.player.speedMul;
    CORE.player.x = clamp(
      CORE.player.x + CORE.input.moveX * speed * dt,
      18,
      CORE.world.w - 18
    );
    CORE.player.y = clamp(
      CORE.player.y + CORE.input.moveY * speed * dt,
      90,
      CORE.world.h - 24
    );

    // shooting
    if (CORE.input.shooting) shoot(t);

    // spawn zombies
    if (t >= CORE.spawnAt) {
      spawnZombie();
      CORE.spawnAt = t + Math.max(180, 620 - CORE.wave * 14);
    }

    // bullets
    for (let i = CORE.bullets.length - 1; i >= 0; i--) {
      const b = CORE.bullets[i];
      b.t += dt;
      b.x += b.vx * dt;
      b.y += b.vy * dt;

      if (b.t >= b.life) {
        CORE.bullets.splice(i, 1);
        continue;
      }

      for (let j = CORE.zombies.length - 1; j >= 0; j--) {
        const z = CORE.zombies[j];
        if (dist2(b.x, b.y, z.x, z.y) <= (z.r * z.r)) {
          z.hp -= b.dmg;
          CORE.bullets.splice(i, 1);

          if (z.hp <= 0) {
            CORE.zombies.splice(j, 1);
            CORE.kills++;
            CORE.coins++;
          }
          break;
        }
      }
    }

    // zombies move + damage
    for (const z of CORE.zombies) {
      const dx = CORE.player.x - z.x;
      const dy = CORE.player.y - z.y;
      const len = Math.hypot(dx, dy) || 1;
      z.x += (dx / len) * z.spd * dt;
      z.y += (dy / len) * z.spd * dt;

      if (dist2(z.x, z.y, CORE.player.x, CORE.player.y) <= (z.r + CORE.player.r) ** 2) {
        applyPlayerDamage(z.dmg * dt);
      }
    }

    // waves
    if (t >= CORE.waveEndsAt) {
      CORE.wave++;
      CORE.waveEndsAt = t + (CORE.mode === "roguelike" ? CONFIG.waves.rogueLen : CONFIG.waves.arcadeLen);
    }

    // death
    if (CORE.player.hp <= 0) {
      CORE.running = false;
    }
  }

  // =========================================================
  // PUBLIC API (FOR UI LAYER)
  // =========================================================
  window.BCO_ZOMBIES_CORE = {
    reset,
    start(mode = "arcade", w = 360, h = 640) {
      CORE.mode = mode;
      reset(w, h);
      CORE.running = true;
      CORE.startedAt = now();
      CORE.lastTick = CORE.startedAt;
    },
    stop() { CORE.running = false; },

    updateFrame(tms) {
      if (!CORE.running) return;
      const t = tms || now();
      const dt = clamp((t - CORE.lastTick) / 1000, 0, 0.033);
      CORE.lastTick = t;
      tick(dt, t);
    },

    // INPUT
    setMove(x, y) { CORE.input.moveX = x; CORE.input.moveY = y; },
    setAim(x, y) { CORE.input.aimX = x; CORE.input.aimY = y; },
    setShooting(on) { CORE.input.shooting = !!on; },

    // STATE (read-only outside)
    get state() { return CORE; },
    get weapons() { return WEAPONS; }
  };

  console.log("[BCO_ZOMBIES_CORE] loaded");
})();
