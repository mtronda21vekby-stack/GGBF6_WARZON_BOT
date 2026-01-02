// app/webapp/static/zombies.core.js
(() => {
  "use strict";

  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const len = (x, y) => Math.hypot(x, y) || 0;
  const norm = (x, y) => {
    const L = len(x, y);
    if (!L) return { x: 0, y: 0, L: 0 };
    return { x: x / L, y: y / L, L };
  };
  const rand = (a, b) => a + Math.random() * (b - a);

  const CFG = {
    tickHz: 60,
    dtMax: 1 / 20,

    arenaRadius: 780, // fallback arena if map not loaded

    player: {
      speed: 320,
      hpMax: 100,
      hitbox: 16,
      iFramesMs: 230
    },

    bullet: {
      speed: 980,
      lifeMs: 900,
      radius: 3,
      pierce: 0
    },

    zombie: {
      baseSpeed: 150,
      baseHp: 34,
      radius: 16,
      damage: 10,
      touchDpsMs: 340
    },

    wave: {
      baseCount: 7,
      countGrowth: 2,
      hpGrowth: 1.08,
      speedGrowth: 1.03,
      spawnRingMin: 520,
      spawnRingMax: 880
    },

    weapons: {
      SMG: { name: "SMG", rpm: 820, dmg: 10, spread: 0.08, bullets: 1 },
      AR:  { name: "AR",  rpm: 640, dmg: 14, spread: 0.05, bullets: 1 },
      SG:  { name: "SG",  rpm: 140, dmg: 8,  spread: 0.22, bullets: 6 }
    },

    perks: {
      Jug:   { id: "Jug",   cost: 12, name: "Jug"   },
      Speed: { id: "Speed", cost: 10, name: "Speed" },
      Mag:   { id: "Mag",   cost: 8,  name: "Mag"   }
    }
  };

  const CORE = {
    cfg: CFG,

    // runtime
    running: false,
    startedAt: 0,   // ms (rAF/perf clock)
    lastT: 0,       // ms (rAF/perf clock)

    // input
    input: {
      moveX: 0, moveY: 0,
      aimX: 1, aimY: 0,
      shooting: false
    },

    // meta
    meta: {
      mode: "arcade",
      map: "Ashes",
      character: "male",
      skin: "default",
      weaponKey: "SMG"
    },

    // state
    state: {
      w: 0, h: 0,
      camX: 0, camY: 0,

      timeMs: 0,
      wave: 1,
      kills: 0,
      coins: 0,

      perks: { Jug: 0, Speed: 0, Mag: 0 },

      player: { x: 0, y: 0, vx: 0, vy: 0, hp: CFG.player.hpMax, lastHitAt: -99999 },
      bullets: [],
      zombies: [],

      shoot: { lastShotAt: 0 },
      _bossSpawned: {}
    },

    // optional hooks (world module can wrap these)
    _tickWorld: null,
    _buyPerk: null,

    // -------------------------------------------------------
    // Public control
    // -------------------------------------------------------
    start(mode, w, h, opts = {}, tms = performance.now()) {
      this.meta.mode = (String(mode || "").toLowerCase().includes("rogue")) ? "roguelike" : "arcade";
      this.state.w = Math.max(1, w | 0);
      this.state.h = Math.max(1, h | 0);

      if (opts.map) this.meta.map = String(opts.map);
      if (opts.character) this.meta.character = String(opts.character);
      if (opts.skin) this.meta.skin = String(opts.skin);
      if (opts.weaponKey && CFG.weapons[opts.weaponKey]) this.meta.weaponKey = opts.weaponKey;

      this._resetRun();

      this.running = true;
      this.startedAt = Number(tms) || performance.now();
      this.lastT = 0;

      return true;
    },

    stop() {
      this.running = false;
      return true;
    },

    resize(w, h) {
      this.state.w = Math.max(1, w | 0);
      this.state.h = Math.max(1, h | 0);
      return true;
    },

    setMove(x, y) {
      this.input.moveX = clamp(Number(x) || 0, -1, 1);
      this.input.moveY = clamp(Number(y) || 0, -1, 1);
      return true;
    },

    setAim(x, y) {
      const nx = Number(x) || 0;
      const ny = Number(y) || 0;
      const n = norm(nx, ny);
      if (n.L > 0.02) {
        this.input.aimX = n.x;
        this.input.aimY = n.y;
      }
      return true;
    },

    setShooting(on) {
      this.input.shooting = !!on;
      return true;
    },

    setWeapon(key) {
      if (CFG.weapons[key]) this.meta.weaponKey = key;
      return this.meta.weaponKey;
    },

    buyPerk(perkId) {
      const id = String(perkId || "");
      const p = CFG.perks[id];
      if (!p) return false;

      if (this.meta.mode !== "roguelike") return false;
      if (this.state.perks[id]) return false;
      if (this.state.coins < p.cost) return false;

      this.state.coins -= p.cost;
      this.state.perks[id] = 1;

      // world module may apply perk effects
      if (typeof this._buyPerk === "function") {
        try { this._buyPerk(this, id); } catch {}
      } else {
        // fallback effects
        if (id === "Jug") {
          const st = this._effectiveStats();
          this.state.player.hp = Math.min(this.state.player.hp + 25, st.hpMax);
        }
      }

      return true;
    },

    updateFrame(tms) {
      if (!this.running) return false;

      const t = Number(tms) || performance.now();

      if (!this.lastT) this.lastT = t;
      let dt = (t - this.lastT) / 1000;
      this.lastT = t;

      dt = Math.min(CFG.dtMax, Math.max(0, dt));

      this._tick(dt, t);
      return true;
    },

    // -------------------------------------------------------
    // Internals
    // -------------------------------------------------------
    _weapon() {
      return CFG.weapons[this.meta.weaponKey] || CFG.weapons.SMG;
    },

    _effectiveStats() {
      const jug = this.state.perks.Jug ? 1.35 : 1.0;
      const speed = this.state.perks.Speed ? 1.18 : 1.0;
      return {
        hpMax: Math.round(CFG.player.hpMax * jug),
        speed: CFG.player.speed * speed
      };
    },

    _resetRun() {
      const S = this.state;
      const st = this._effectiveStats();

      S.timeMs = 0;
      S.wave = 1;
      S.kills = 0;
      S.coins = 0;
      S.perks = { Jug: 0, Speed: 0, Mag: 0 };

      S.player.x = 0;
      S.player.y = 0;
      S.player.vx = 0;
      S.player.vy = 0;
      S.player.hp = st.hpMax;
      S.player.lastHitAt = -99999;

      S.bullets = [];
      S.zombies = [];
      S.shoot.lastShotAt = 0;
      S._bossSpawned = {};

      this.input.aimX = 1;
      this.input.aimY = 0;
      this.input.moveX = 0;
      this.input.moveY = 0;
      this.input.shooting = false;

      this._spawnWave(S.wave);
    },

    _spawnWave(w) {
      const S = this.state;
      const count = CFG.wave.baseCount + (w - 1) * CFG.wave.countGrowth;
      const hpMul = Math.pow(CFG.wave.hpGrowth, (w - 1));
      const spMul = Math.pow(CFG.wave.speedGrowth, (w - 1));

      for (let i = 0; i < count; i++) {
        const ang = rand(0, Math.PI * 2);
        const r = rand(CFG.wave.spawnRingMin, CFG.wave.spawnRingMax);
        const x = S.player.x + Math.cos(ang) * r;
        const y = S.player.y + Math.sin(ang) * r;

        S.zombies.push({
          kind: "zombie",
          x, y, vx: 0, vy: 0,
          hp: CFG.zombie.baseHp * hpMul,
          sp: CFG.zombie.baseSpeed * spMul,
          r: CFG.zombie.radius,
          nextTouchAt: 0
        });
      }
    },

    _canShoot(tms) {
      const w = this._weapon();
      const intervalMs = (60_000 / w.rpm);
      return (tms - this.state.shoot.lastShotAt) >= intervalMs;
    },

    _shoot(tms) {
      if (!this._canShoot(tms)) return;

      const S = this.state;
      const w = this._weapon();
      S.shoot.lastShotAt = tms;

      const sp = CFG.bullet.speed;
      const ax = this.input.aimX;
      const ay = this.input.aimY;

      for (let i = 0; i < w.bullets; i++) {
        const a = Math.atan2(ay, ax) + rand(-w.spread, w.spread);
        const dx = Math.cos(a);
        const dy = Math.sin(a);

        S.bullets.push({
          x: S.player.x + dx * 18,
          y: S.player.y + dy * 18,
          vx: dx * sp,
          vy: dy * sp,
          born: tms,
          life: CFG.bullet.lifeMs,
          dmg: w.dmg,
          pierce: CFG.bullet.pierce,
          r: CFG.bullet.radius
        });
      }
    },

    _hitPlayer(tms) {
      const S = this.state;
      if (tms - S.player.lastHitAt < CFG.player.iFramesMs) return;

      S.player.lastHitAt = tms;
      S.player.hp = Math.max(0, S.player.hp - CFG.zombie.damage);

      if (S.player.hp <= 0) {
        this.running = false;
      }
    },

    _tick(dt, tms) {
      const S = this.state;

      // run clock
      S.timeMs = Math.max(0, (tms - this.startedAt));

      // movement
      const st = this._effectiveStats();
      const mx = this.input.moveX;
      const my = this.input.moveY;

      S.player.vx = mx * st.speed;
      S.player.vy = my * st.speed;
      S.player.x += S.player.vx * dt;
      S.player.y += S.player.vy * dt;

      // fallback arena clamp (world collisions can do better)
      const pr = len(S.player.x, S.player.y);
      if (pr > CFG.arenaRadius) {
        const n = norm(S.player.x, S.player.y);
        S.player.x = n.x * CFG.arenaRadius;
        S.player.y = n.y * CFG.arenaRadius;
      }

      // shooting
      if (this.input.shooting) this._shoot(tms);

      // bullets
      for (let i = S.bullets.length - 1; i >= 0; i--) {
        const b = S.bullets[i];
        b.x += b.vx * dt;
        b.y += b.vy * dt;

        if ((tms - b.born) > b.life) { S.bullets.splice(i, 1); continue; }
        if (len(b.x, b.y) > CFG.arenaRadius + 1200) { S.bullets.splice(i, 1); continue; }
      }

      // zombies seek
      for (let i = S.zombies.length - 1; i >= 0; i--) {
        const z = S.zombies[i];
        const dx = S.player.x - z.x;
        const dy = S.player.y - z.y;
        const n = norm(dx, dy);

        z.vx = n.x * z.sp;
        z.vy = n.y * z.sp;
        z.x += z.vx * dt;
        z.y += z.vy * dt;

        const dist = len(dx, dy);
        if (dist < (z.r + CFG.player.hitbox)) {
          if (tms >= z.nextTouchAt) {
            z.nextTouchAt = tms + CFG.zombie.touchDpsMs;
            this._hitPlayer(tms);
          }
        }
      }

      // allow world module to apply map collisions + bosses
      if (typeof this._tickWorld === "function") {
        try { this._tickWorld(this, dt, tms); } catch {}
      }

      // collisions bullets vs zombies
      for (let bi = S.bullets.length - 1; bi >= 0; bi--) {
        const b = S.bullets[bi];
        let consumed = false;

        for (let zi = S.zombies.length - 1; zi >= 0; zi--) {
          const z = S.zombies[zi];
          const dx = z.x - b.x;
          const dy = z.y - b.y;
          const dist = len(dx, dy);

          if (dist < (z.r + b.r)) {
            z.hp -= b.dmg;

            if (z.hp <= 0) {
              S.zombies.splice(zi, 1);
              S.kills += 1;
              S.coins += (this.meta.mode === "roguelike") ? 2 : 1;
            }

            if (b.pierce > 0) b.pierce -= 1;
            else consumed = true;

            break;
          }
        }

        if (consumed) S.bullets.splice(bi, 1);
      }

      // next wave
      if (S.zombies.length === 0 && this.running) {
        S.wave += 1;
        this._spawnWave(S.wave);
      }

      // camera follow
      S.camX = S.player.x;
      S.camY = S.player.y;
    }
  };

  window.BCO_ZOMBIES_CORE = CORE;
  console.log("[Z_CORE] loaded");
})();
