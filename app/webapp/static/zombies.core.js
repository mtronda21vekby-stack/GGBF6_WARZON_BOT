/* =========================================================
   BLACK CROWN OPS — ZOMBIES CORE (GAME LOGIC ONLY)
   File: app/webapp/static/zombies.core.js
   ========================================================= */

(() => {
  "use strict";

  // =========================================================
  // CONFIG
  // =========================================================
  const CFG = {
    arenaRadius: 1400,

    player: {
      speed: 320,
      hpMax: 100,
      hitbox: 18,
      iFramesMs: 220
    },

    bullet: {
      speed: 980,
      lifeMs: 900,
      radius: 4
    },

    zombie: {
      baseSpeed: 150,
      baseHp: 36,
      radius: 18,
      damage: 10,
      touchCdMs: 320
    },

    wave: {
      baseCount: 6,
      growth: 2,
      hpMul: 1.08,
      spMul: 1.04,
      spawnMin: 520,
      spawnMax: 880
    },

    weapons: {
      SMG: { rpm: 820, dmg: 10, spread: 0.08, pellets: 1 },
      AR:  { rpm: 640, dmg: 14, spread: 0.05, pellets: 1 },
      SG:  { rpm: 120, dmg: 8,  spread: 0.22, pellets: 6 }
    }
  };

  // =========================================================
  // UTILS
  // =========================================================
  const now = () => performance.now();
  const clamp = (v,a,b)=>Math.max(a,Math.min(b,v));
  const len = (x,y)=>Math.hypot(x,y)||0;
  const norm = (x,y)=>{ const l=len(x,y); return l?{x:x/l,y:y/l,l}:{x:0,y:0,l:0}; };
  const rand = (a,b)=>a+Math.random()*(b-a);

  // =========================================================
  // STATE
  // =========================================================
  const state = {
    time: 0,
    running: false,

    wave: 1,
    kills: 0,
    coins: 0,

    weaponKey: "SMG",

    player: {
      x: 0, y: 0,
      vx: 0, vy: 0,
      hp: CFG.player.hpMax,
      lastHit: -99999
    },

    input: {
      moveX: 0, moveY: 0,
      aimX: 1, aimY: 0,
      firing: false
    },

    bullets: [],
    zombies: [],

    shoot: {
      last: 0
    }
  };

  function weapon() {
    return CFG.weapons[state.weaponKey] || CFG.weapons.SMG;
  }

  // =========================================================
  // WAVES
  // =========================================================
  function spawnWave(w) {
    const count = CFG.wave.baseCount + (w - 1) * CFG.wave.growth;
    const hpMul = Math.pow(CFG.wave.hpMul, w - 1);
    const spMul = Math.pow(CFG.wave.spMul, w - 1);

    for (let i = 0; i < count; i++) {
      const a = rand(0, Math.PI * 2);
      const r = rand(CFG.wave.spawnMin, CFG.wave.spawnMax);
      state.zombies.push({
        x: Math.cos(a) * r,
        y: Math.sin(a) * r,
        vx: 0, vy: 0,
        hp: CFG.zombie.baseHp * hpMul,
        sp: CFG.zombie.baseSpeed * spMul,
        nextTouch: 0
      });
    }
  }

  // =========================================================
  // COMBAT
  // =========================================================
  function canShoot(t) {
    const w = weapon();
    return (t - state.shoot.last) >= (60000 / w.rpm);
  }

  function shoot(t) {
    if (!canShoot(t)) return;
    state.shoot.last = t;

    const w = weapon();
    const ax = state.input.aimX;
    const ay = state.input.aimY;

    for (let i = 0; i < w.pellets; i++) {
      const ang = Math.atan2(ay, ax) + rand(-w.spread, w.spread);
      const dx = Math.cos(ang);
      const dy = Math.sin(ang);

      state.bullets.push({
        x: state.player.x + dx * 18,
        y: state.player.y + dy * 18,
        vx: dx * CFG.bullet.speed,
        vy: dy * CFG.bullet.speed,
        born: t,
        dmg: w.dmg
      });
    }
  }

  function hitPlayer(t) {
    if (t - state.player.lastHit < CFG.player.iFramesMs) return;
    state.player.lastHit = t;
    state.player.hp -= CFG.zombie.damage;
    if (state.player.hp <= 0) {
      state.running = false;
    }
  }

  // =========================================================
  // UPDATE
  // =========================================================
  function update(dt, t) {
    if (!state.running) return;

    // movement
    state.player.vx = state.input.moveX * CFG.player.speed;
    state.player.vy = state.input.moveY * CFG.player.speed;
    state.player.x += state.player.vx * dt;
    state.player.y += state.player.vy * dt;

    // arena clamp
    const d = len(state.player.x, state.player.y);
    if (d > CFG.arenaRadius) {
      const n = norm(state.player.x, state.player.y);
      state.player.x = n.x * CFG.arenaRadius;
      state.player.y = n.y * CFG.arenaRadius;
    }

    // shooting
    if (state.input.firing) shoot(t);

    // bullets
    for (let i = state.bullets.length - 1; i >= 0; i--) {
      const b = state.bullets[i];
      b.x += b.vx * dt;
      b.y += b.vy * dt;
      if (t - b.born > CFG.bullet.lifeMs) {
        state.bullets.splice(i, 1);
      }
    }

    // zombies
    for (let zi = state.zombies.length - 1; zi >= 0; zi--) {
      const z = state.zombies[zi];
      const dx = state.player.x - z.x;
      const dy = state.player.y - z.y;
      const n = norm(dx, dy);

      z.vx = n.x * z.sp;
      z.vy = n.y * z.sp;
      z.x += z.vx * dt;
      z.y += z.vy * dt;

      if (n.l < CFG.zombie.radius + CFG.player.hitbox && t > z.nextTouch) {
        z.nextTouch = t + CFG.zombie.touchCdMs;
        hitPlayer(t);
      }
    }

    // collisions
    for (let bi = state.bullets.length - 1; bi >= 0; bi--) {
      const b = state.bullets[bi];
      for (let zi = state.zombies.length - 1; zi >= 0; zi--) {
        const z = state.zombies[zi];
        if (len(z.x - b.x, z.y - b.y) < CFG.zombie.radius + CFG.bullet.radius) {
          z.hp -= b.dmg;
          state.bullets.splice(bi, 1);
          if (z.hp <= 0) {
            state.zombies.splice(zi, 1);
            state.kills++;
            state.coins++;
          }
          break;
        }
      }
    }

    // next wave
    if (state.zombies.length === 0) {
      state.wave++;
      spawnWave(state.wave);
    }
  }

  // =========================================================
  // API (USED BY RENDER / UI)
  // =========================================================
  const API = {
    state,

    start() {
      state.running = true;
      state.wave = 1;
      state.kills = 0;
      state.coins = 0;
      state.player.hp = CFG.player.hpMax;
      state.player.x = 0;
      state.player.y = 0;
      state.bullets.length = 0;
      state.zombies.length = 0;
      spawnWave(1);
    },

    updateFrame(t) {
      const dt = Math.min(0.033, (t - state.time) / 1000 || 0);
      state.time = t;
      update(dt, t);
    },

    setMove(x, y) {
      state.input.moveX = clamp(x, -1, 1);
      state.input.moveY = clamp(y, -1, 1);
    },

    setAim(x, y) {
      const n = norm(x, y);
      if (n.l > 0.1) {
        state.input.aimX = n.x;
        state.input.aimY = n.y;
      }
    },

    setShooting(on) {
      state.input.firing = !!on;
    },

    setWeapon(key) {
      if (CFG.weapons[key]) state.weaponKey = key;
    }
  };

  window.BCO_ZOMBIES_CORE = API;
  console.log("[Z_CORE] loaded");
})();
