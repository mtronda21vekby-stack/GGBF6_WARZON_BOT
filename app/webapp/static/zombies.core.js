/* =========================================================
   BLACK CROWN OPS — ZOMBIES CORE (LOGIC ONLY)
   File: app/webapp/static/zombies.core.js
   ========================================================= */

(() => {
  "use strict";

  // =========================================================
  // CONFIG
  // =========================================================
  const CFG = {
    tick: 60,
    arenaR: 1200,

    player: {
      speed: 320,
      hp: 100,
      hitbox: 18
    },

    bullet: {
      speed: 900,
      life: 900,
      r: 4,
      dmg: 10
    },

    zombie: {
      speed: 140,
      hp: 30,
      r: 18,
      dmg: 10
    },

    wave: {
      base: 6,
      add: 2
    }
  };

  // =========================================================
  // STATE
  // =========================================================
  const state = {
    running: false,
    time: 0,
    wave: 1,
    kills: 0,
    coins: 0,

    player: {
      x: 0, y: 0,
      vx: 0, vy: 0,
      hp: CFG.player.hp
    },

    bullets: [],
    zombies: [],

    input: {
      moveX: 0,
      moveY: 0,
      aimX: 1,
      aimY: 0,
      firing: false
    },

    lastShot: 0
  };

  // =========================================================
  // UTILS
  // =========================================================
  const now = () => performance.now();
  const len = (x, y) => Math.hypot(x, y) || 1;
  const norm = (x, y) => {
    const l = len(x, y);
    return { x: x / l, y: y / l };
  };

  // =========================================================
  // CORE API
  // =========================================================
  function start(mode = "arcade") {
    state.running = true;
    state.time = 0;
    state.wave = 1;
    state.kills = 0;
    state.coins = 0;

    state.player.x = 0;
    state.player.y = 0;
    state.player.hp = CFG.player.hp;

    state.bullets.length = 0;
    state.zombies.length = 0;

    spawnWave();
  }

  function stop() {
    state.running = false;
  }

  function spawnWave() {
    const count = CFG.wave.base + (state.wave - 1) * CFG.wave.add;
    for (let i = 0; i < count; i++) {
      const a = Math.random() * Math.PI * 2;
      const r = CFG.arenaR * 0.7;
      state.zombies.push({
        x: Math.cos(a) * r,
        y: Math.sin(a) * r,
        hp: CFG.zombie.hp,
        vx: 0, vy: 0
      });
    }
  }

  function setMove(x, y) {
    state.input.moveX = x;
    state.input.moveY = y;
  }

  function setAim(x, y) {
    state.input.aimX = x;
    state.input.aimY = y;
  }

  function setShooting(on) {
    state.input.firing = on;
  }

  // =========================================================
  // UPDATE
  // =========================================================
  function updateFrame(t) {
    if (!state.running) return;

    const dt = Math.min(0.033, (t - state.time) / 1000 || 0);
    state.time = t;

    // player move
    state.player.vx = state.input.moveX * CFG.player.speed;
    state.player.vy = state.input.moveY * CFG.player.speed;
    state.player.x += state.player.vx * dt;
    state.player.y += state.player.vy * dt;

    // shooting
    if (state.input.firing && t - state.lastShot > 90) {
      state.lastShot = t;
      const n = norm(state.input.aimX, state.input.aimY);
      state.bullets.push({
        x: state.player.x,
        y: state.player.y,
        vx: n.x * CFG.bullet.speed,
        vy: n.y * CFG.bullet.speed,
        born: t
      });
    }

    // bullets
    for (let i = state.bullets.length - 1; i >= 0; i--) {
      const b = state.bullets[i];
      b.x += b.vx * dt;
      b.y += b.vy * dt;
      if (t - b.born > CFG.bullet.life) {
        state.bullets.splice(i, 1);
      }
    }

    // zombies
    for (let zi = state.zombies.length - 1; zi >= 0; zi--) {
      const z = state.zombies[zi];
      const dx = state.player.x - z.x;
      const dy = state.player.y - z.y;
      const n = norm(dx, dy);

      z.vx = n.x * CFG.zombie.speed;
      z.vy = n.y * CFG.zombie.speed;
      z.x += z.vx * dt;
      z.y += z.vy * dt;

      // hit player
      if (len(dx, dy) < CFG.zombie.r + CFG.player.hitbox) {
        state.player.hp -= CFG.zombie.dmg * dt;
        if (state.player.hp <= 0) stop();
      }
    }

    // bullet hits
    for (let bi = state.bullets.length - 1; bi >= 0; bi--) {
      const b = state.bullets[bi];
      for (let zi = state.zombies.length - 1; zi >= 0; zi--) {
        const z = state.zombies[zi];
        if (len(z.x - b.x, z.y - b.y) < CFG.zombie.r) {
          z.hp -= CFG.bullet.dmg;
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
      spawnWave();
    }
  }

  // =========================================================
  // EXPORT
  // =========================================================
  window.BCO_ZOMBIES_CORE = {
    state,
    start,
    stop,
    updateFrame,
    setMove,
    setAim,
    setShooting
  };

  console.log("[Z_CORE] loaded");
})();
