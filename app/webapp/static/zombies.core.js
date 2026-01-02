// app/webapp/static/zombies.core.js  [LUX COD-ZOMBIES-2D v1]
// - Armor/plates, reload + ammo reserve
// - Weapon pool + rarities + upgrades
// - Loot drops/pickups + auto-pickup
// - Events (Max Ammo / Double Points / Insta-Kill)
// - Roguelike economy + progression (xp/level) inside run
// - Boss hook compatible with zombies.bosses.js [LUX] via CORE._onBulletHit
// - Map bounds + collisions integration if optional modules exist
(() => {
  "use strict";

  // -------------------------
  // Math utils
  // -------------------------
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const len = (x, y) => Math.hypot(x, y) || 0;
  const norm = (x, y) => {
    const L = len(x, y);
    if (!L) return { x: 0, y: 0, L: 0 };
    return { x: x / L, y: y / L, L };
  };
  const rand = (a, b) => a + Math.random() * (b - a);
  const randi = (a, b) => (a + Math.floor(Math.random() * (b - a + 1))) | 0;
  const pick = (arr) => arr[(Math.random() * arr.length) | 0];

  // -------------------------
  // Rarity / economy
  // -------------------------
  const RARITY = {
    common:    { id: "common",    name: "Common",    dmg: 1.00, rpm: 1.00, spread: 1.00, mag: 1.00, reload: 1.00, value: 1.0, color: "rgba(255,255,255,.85)" },
    uncommon:  { id: "uncommon",  name: "Uncommon",  dmg: 1.08, rpm: 1.02, spread: 0.96, mag: 1.06, reload: 0.96, value: 1.25, color: "rgba(140,255,140,.90)" },
    rare:      { id: "rare",      name: "Rare",      dmg: 1.18, rpm: 1.04, spread: 0.92, mag: 1.12, reload: 0.92, value: 1.6, color: "rgba(120,170,255,.92)" },
    epic:      { id: "epic",      name: "Epic",      dmg: 1.30, rpm: 1.06, spread: 0.88, mag: 1.18, reload: 0.88, value: 2.2, color: "rgba(210,140,255,.92)" },
    legendary: { id: "legendary", name: "Legendary", dmg: 1.45, rpm: 1.08, spread: 0.84, mag: 1.26, reload: 0.84, value: 3.0, color: "rgba(255,200,120,.95)" }
  };

  function rollRarity(wave) {
    // Wave-weighted roll: higher waves -> more rare drops
    const w = Math.max(1, wave | 0);
    const t = Math.random();
    const bonus = clamp((w - 1) / 18, 0, 0.35); // up to +35% to high tiers

    // base thresholds
    const thLegend = 0.015 + bonus * 0.35;
    const thEpic   = 0.055 + bonus * 0.55;
    const thRare   = 0.16  + bonus * 0.60;
    const thUnc    = 0.36  + bonus * 0.45;

    if (t < thLegend) return "legendary";
    if (t < thEpic)   return "epic";
    if (t < thRare)   return "rare";
    if (t < thUnc)    return "uncommon";
    return "common";
  }

  // -------------------------
  // Config
  // -------------------------
  const CFG = {
    tickHz: 60,
    dtMax: 1 / 20,

    // fallback if map not loaded
    arenaRadius: 780,

    // map edges if maps module provides w/h
    mapClampPadding: 80,

    player: {
      speed: 320,
      hpMax: 100,
      hitbox: 16,
      iFramesMs: 230,

      // armor system (COD-style)
      armorMax: 150,        // armor points (3 plates x 50)
      plateValue: 50,
      platesMax: 3,
      platesStart: 0,       // arcade 0; roguelike can start with 1 by event/loot
      plateUseMs: 680,      // "apply plate" speed
      armorDmgAbsorb: 0.72  // 72% damage goes to armor while armor > 0
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
      hpGrowth: 1.085,
      speedGrowth: 1.03,
      spawnRingMin: 520,
      spawnRingMax: 880
    },

    // Weapons base templates (stats are further modified by rarity, upgrades, perks, events)
    weapons: {
      // key: {name, type, rpm, dmg, spread, bullets, mag, reserve, reloadMs, movePenalty, crit, pierce}
      SMG:   { name: "SMG",   type: "smg",   rpm: 820, dmg: 10, spread: 0.080, bullets: 1, mag: 32, reserve: 160, reloadMs: 980,  movePenalty: 0.00, crit: 0.06, pierce: 0 },
      AR:    { name: "AR",    type: "ar",    rpm: 640, dmg: 14, spread: 0.050, bullets: 1, mag: 30, reserve: 180, reloadMs: 1100, movePenalty: 0.02, crit: 0.08, pierce: 0 },
      SG:    { name: "SG",    type: "sg",    rpm: 140, dmg: 8,  spread: 0.220, bullets: 7, mag: 7,  reserve: 56,  reloadMs: 1250, movePenalty: 0.05, crit: 0.03, pierce: 0 },
      LMG:   { name: "LMG",   type: "lmg",   rpm: 520, dmg: 15, spread: 0.065, bullets: 1, mag: 60, reserve: 240, reloadMs: 1650, movePenalty: 0.08, crit: 0.06, pierce: 0 },
      MARK:  { name: "DMR",   type: "dmr",   rpm: 310, dmg: 36, spread: 0.020, bullets: 1, mag: 12, reserve: 72,  reloadMs: 1350, movePenalty: 0.06, crit: 0.14, pierce: 1 },
      PIST:  { name: "Pistol",type: "pist",  rpm: 420, dmg: 12, spread: 0.060, bullets: 1, mag: 15, reserve: 90,  reloadMs: 880,  movePenalty: 0.00, crit: 0.06, pierce: 0 }
    },

    // Perks (keep old IDs for UI buttons; add more for depth)
    perks: {
      Jug:     { id: "Jug",     cost: 12, name: "Jug",     desc: "+HP max (premium)" },
      Speed:   { id: "Speed",   cost: 10, name: "Speed",   desc: "+Move speed" },
      Mag:     { id: "Mag",     cost: 8,  name: "Mag",     desc: "+Mag size +reserve +pierce" },

      // extra perks for future UI
      Armor:   { id: "Armor",   cost: 14, name: "Armor",   desc: "Start with plates + faster plating" },
      Reload:  { id: "Reload",  cost: 11, name: "Reload",  desc: "Faster reload" },
      Crit:    { id: "Crit",    cost: 13, name: "Crit",    desc: "Higher crit chance/dmg" },
      Loot:    { id: "Loot",    cost: 12, name: "Loot",    desc: "Better drop rates" },
      Sprint:  { id: "Sprint",  cost: 10, name: "Sprint",  desc: "Faster strafe / less move penalty" }
    },

    // Loot + pickups
    loot: {
      // base chances per zombie kill (roguelike only; arcade minimal)
      coinChance: 0.70,
      ammoChance: 0.16,
      plateChance: 0.12,
      weaponChance: 0.06,
      eventChance: 0.035,

      // wave scaling
      weaponChanceWaveBonus: 0.0025, // +0.25% per wave
      eventChanceWaveBonus:  0.0015,

      // pickup behavior
      pickupRadius: 42,
      pickupLifeMs: 12000,
      magnetRadius: 120,  // slight pull feel (lux)
      magnetStrength: 6.0
    },

    // Timed events
    events: {
      maxAmmoMs: 9000,
      doublePointsMs: 9000,
      instaKillMs: 6500
    },

    // XP / level (in-run)
    progress: {
      xpKill: 6,
      xpWave: 28,
      xpBoss: 80
    }
  };

  // -------------------------
  // Build weapon instance for run
  // -------------------------
  function mkWeapon(key, rarityId, upgradeLevel = 0) {
    const base = CFG.weapons[key] || CFG.weapons.SMG;
    const rar = RARITY[rarityId] || RARITY.common;

    const up = Math.max(0, upgradeLevel | 0);
    const upDmg = 1.0 + up * 0.10;
    const upMag = 1.0 + up * 0.07;
    const upReload = 1.0 - Math.min(0.22, up * 0.035);

    return {
      key,
      name: base.name,
      type: base.type,

      rarity: rar.id,
      rarityName: rar.name,
      rarityColor: rar.color,

      // computed stats
      rpm: base.rpm * rar.rpm,
      dmg: base.dmg * rar.dmg * upDmg,
      spread: base.spread * rar.spread,
      bullets: base.bullets | 0,

      magMax: Math.round(base.mag * rar.mag * upMag),
      reserveMax: Math.round(base.reserve * rar.mag * upMag), // reserve scales a bit too
      reloadMs: Math.round(base.reloadMs * rar.reload * upReload),

      movePenalty: base.movePenalty,
      crit: base.crit,
      pierce: base.pierce | 0,

      // runtime ammo
      mag: Math.round(base.mag * rar.mag * upMag),
      reserve: Math.round(base.reserve * rar.mag * upMag),

      upgrade: up
    };
  }

  // -------------------------
  // CORE
  // -------------------------
  const CORE = {
    cfg: CFG,

    // runtime
    running: false,
    startedAt: 0,   // ms (perf)
    lastT: 0,       // ms (perf)

    // input
    input: {
      moveX: 0, moveY: 0,
      aimX: 1, aimY: 0,
      shooting: false
    },

    // meta
    meta: {
      mode: "arcade",        // arcade/roguelike
      map: "Ashes",
      character: "male",
      skin: "default",

      // weapon selection (key only; actual weapon instance is state.weapon)
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

      // progression (in-run)
      xp: 0,
      level: 1,

      // perks flags
      perks: {
        Jug: 0, Speed: 0, Mag: 0,
        Armor: 0, Reload: 0, Crit: 0, Loot: 0, Sprint: 0
      },

      // player stats runtime
      player: {
        x: 0, y: 0, vx: 0, vy: 0,
        hp: CFG.player.hpMax,
        armor: 0,
        plates: 0,
        plating: { active: false, until: 0 },
        lastHitAt: -99999
      },

      // weapon runtime
      weapon: null,
      reload: { active: false, until: 0, startedAt: 0 },

      bullets: [],
      zombies: [],

      // loot/pickups
      pickups: [],

      // events (timed)
      events: {
        maxAmmoUntil: 0,
        doublePointsUntil: 0,
        instaKillUntil: 0
      },

      // shooting control
      shoot: { lastShotAt: 0 },

      // boss spawn state used by bosses module
      _bossSpawned: {}
    },

    // optional hooks (world module can wrap these)
    _tickWorld: null,
    _buyPerk: null,

    // bullet hit hook (boss module may install)
    _onBulletHit: null,

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

      // If bosses module exists and exposes install, attach once per core instance (safe)
      try {
        const B = window.BCO_ZOMBIES_BOSSES;
        if (B?.install && !this._bossInstalled) {
          B.install(this, () => window.BCO_ZOMBIES_MAPS?.get?.(this.meta.map) || null);
          this._bossInstalled = true;
        }
      } catch {}

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

      // If you call setWeapon mid-run, rebuild weapon with same rarity/upgrade if possible.
      try {
        const S = this.state;
        if (S.weapon && CFG.weapons[this.meta.weaponKey]) {
          const rar = S.weapon.rarity || "common";
          const up = S.weapon.upgrade || 0;
          S.weapon = mkWeapon(this.meta.weaponKey, rar, up);
        }
      } catch {}

      return this.meta.weaponKey;
    },

    // manual reload (optional)
    reload() {
      const S = this.state;
      if (!S.weapon) return false;
      if (S.reload.active) return false;
      const W = this._weaponEffective();
      if (S.weapon.mag >= W.magMax) return false;
      if (S.weapon.reserve <= 0) return false;

      this._startReload(performance.now());
      return true;
    },

    // apply armor plate (optional)
    usePlate() {
      if (this.meta.mode !== "roguelike") return false;
      const S = this.state;
      const P = S.player;
      const st = this._effectiveStats();

      if (P.plates <= 0) return false;
      if (P.plating.active) return false;
      if (P.armor >= st.armorMax) return false;

      const tms = performance.now();
      P.plating.active = true;
      P.plating.until = tms + st.plateUseMs;

      return true;
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
        // fallback: apply immediate feel-good effects
        if (id === "Jug") {
          const st = this._effectiveStats();
          this.state.player.hp = Math.min(this.state.player.hp + 40, st.hpMax);
        }
        if (id === "Armor") {
          const st = this._effectiveStats();
          this.state.player.plates = Math.min(st.platesMax, this.state.player.plates + 1);
          this.state.player.armor = Math.min(st.armorMax, this.state.player.armor + st.plateValue);
        }
        if (id === "Mag") {
          // slight pierce feels premium
          try { this.cfg.bullet.pierce = 1; } catch {}
        }
      }

      // after any perk, re-clamp hp/armor to new maxima
      this._clampVitals();

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
      // Keep backward compat: return a weapon-like object
      const w = this.state.weapon;
      if (w) return { name: w.name, rpm: w.rpm, dmg: w.dmg, spread: w.spread, bullets: w.bullets };
      const base = CFG.weapons[this.meta.weaponKey] || CFG.weapons.SMG;
      return base;
    },

    _effectiveStats() {
      const S = this.state;
      const perks = S.perks || {};

      const jug = perks.Jug ? 1.40 : 1.0;
      const speed = perks.Speed ? 1.18 : 1.0;
      const sprint = perks.Sprint ? 0.70 : 1.0; // reduces move penalty

      const armorMax = CFG.player.armorMax * (perks.Armor ? 1.12 : 1.0);
      const plateUseMs = CFG.player.plateUseMs * (perks.Armor ? 0.85 : 1.0);

      const platesMax = CFG.player.platesMax + (perks.Armor ? 1 : 0);
      const plateValue = CFG.player.plateValue;

      const reloadMul = perks.Reload ? 0.82 : 1.0;
      const critBonus = perks.Crit ? 0.06 : 0.0;
      const lootBonus = perks.Loot ? 0.45 : 0.0;

      return {
        hpMax: Math.round(CFG.player.hpMax * jug),
        speed: CFG.player.speed * speed,
        hitbox: CFG.player.hitbox,
        iFramesMs: CFG.player.iFramesMs,

        armorMax: Math.round(armorMax),
        plateValue,
        platesMax,
        plateUseMs,

        movePenaltyMul: sprint,
        reloadMul,
        critBonus,
        lootBonus
      };
    },

    _clampVitals() {
      const S = this.state;
      const st = this._effectiveStats();
      S.player.hp = Math.max(0, Math.min(S.player.hp, st.hpMax));
      S.player.armor = Math.max(0, Math.min(S.player.armor, st.armorMax));
      S.player.plates = Math.max(0, Math.min(S.player.plates, st.platesMax));
    },

    _resetRun() {
      const S = this.state;
      const st = this._effectiveStats();

      S.timeMs = 0;
      S.wave = 1;
      S.kills = 0;
      S.coins = 0;

      S.xp = 0;
      S.level = 1;

      // reset perks to baseline set (keep extra perks keys)
      S.perks = {
        Jug: 0, Speed: 0, Mag: 0,
        Armor: 0, Reload: 0, Crit: 0, Loot: 0, Sprint: 0
      };

      // weapon instance
      const startRarity = "common";
      S.weapon = mkWeapon(this.meta.weaponKey, startRarity, 0);

      // start full ammo
      S.weapon.mag = S.weapon.magMax;
      S.weapon.reserve = S.weapon.reserveMax;

      S.reload = { active: false, until: 0, startedAt: 0 };

      // player
      S.player.x = 0;
      S.player.y = 0;
      S.player.vx = 0;
      S.player.vy = 0;
      S.player.hp = st.hpMax;
      S.player.armor = 0;
      S.player.plates = (this.meta.mode === "roguelike") ? CFG.player.platesStart : 0;
      S.player.plating = { active: false, until: 0 };
      S.player.lastHitAt = -99999;

      // entities
      S.bullets = [];
      S.zombies = [];

      // loot/pickups
      S.pickups = [];

      // events
      S.events = { maxAmmoUntil: 0, doublePointsUntil: 0, instaKillUntil: 0 };

      // other
      S.shoot.lastShotAt = 0;
      S._bossSpawned = {};

      // input
      this.input.aimX = 1;
      this.input.aimY = 0;
      this.input.moveX = 0;
      this.input.moveY = 0;
      this.input.shooting = false;

      this._spawnWave(S.wave);
    },

    _mapInfo() {
      // returns {name,w,h,walls,bossSpawns} or null
      try {
        const M = window.BCO_ZOMBIES_MAPS;
        return M?.get?.(this.meta.map) || null;
      } catch { return null; }
    },

    _clampToMapOrArena(ent) {
      const map = this._mapInfo();
      if (map && map.w && map.h) {
        const pad = CFG.mapClampPadding;
        const halfW = map.w / 2 - pad;
        const halfH = map.h / 2 - pad;
        ent.x = clamp(ent.x, -halfW, halfW);
        ent.y = clamp(ent.y, -halfH, halfH);
        return;
      }

      // fallback arena
      const r = len(ent.x, ent.y);
      if (r > CFG.arenaRadius) {
        const n = norm(ent.x, ent.y);
        ent.x = n.x * CFG.arenaRadius;
        ent.y = n.y * CFG.arenaRadius;
      }
    },

    _spawnWave(w) {
      const S = this.state;

      const wave = Math.max(1, w | 0);
      const count = CFG.wave.baseCount + (wave - 1) * CFG.wave.countGrowth;

      const hpMul = Math.pow(CFG.wave.hpGrowth, (wave - 1));
      const spMul = Math.pow(CFG.wave.speedGrowth, (wave - 1));

      // small elite chance on higher waves
      const eliteChance = clamp(0.02 + (wave - 1) * 0.004, 0.02, 0.12);

      for (let i = 0; i < count; i++) {
        const ang = rand(0, Math.PI * 2);
        const r = rand(CFG.wave.spawnRingMin, CFG.wave.spawnRingMax);
        const x = S.player.x + Math.cos(ang) * r;
        const y = S.player.y + Math.sin(ang) * r;

        const elite = (Math.random() < eliteChance);

        S.zombies.push({
          kind: "zombie",
          x, y, vx: 0, vy: 0,
          hp: (CFG.zombie.baseHp * hpMul) * (elite ? 1.55 : 1.0),
          sp: (CFG.zombie.baseSpeed * spMul) * (elite ? 1.12 : 1.0),
          r: CFG.zombie.radius + (elite ? 2 : 0),
          elite: elite ? 1 : 0,
          nextTouchAt: 0
        });
      }
    },

    _eventsActive() {
      const e = this.state.events;
      const t = performance.now();
      return {
        maxAmmo: t < (e.maxAmmoUntil || 0),
        doublePoints: t < (e.doublePointsUntil || 0),
        instaKill: t < (e.instaKillUntil || 0)
      };
    },

    _weaponEffective() {
      // Apply perks/events modifiers on top of state.weapon
      const S = this.state;
      const st = this._effectiveStats();
      const ev = this._eventsActive();

      const w = S.weapon || mkWeapon(this.meta.weaponKey, "common", 0);

      const perkMag = S.perks.Mag ? 1.18 : 1.0;
      const perkPierce = S.perks.Mag ? 1 : 0;
      const perkReload = st.reloadMul;

      const rpm = w.rpm;
      const dmg = w.dmg;
      const spread = w.spread;
      const bullets = w.bullets;

      const magMax = Math.round(w.magMax * perkMag);
      const reserveMax = Math.round(w.reserveMax * perkMag);

      const reloadMs = Math.round(w.reloadMs * perkReload);

      const critChance = clamp((w.crit || 0) + st.critBonus, 0, 0.35);
      const pierce = Math.max(w.pierce | 0, perkPierce);

      return {
        ...w,
        rpm,
        dmg,
        spread,
        bullets,
        magMax,
        reserveMax,
        reloadMs,
        critChance,
        pierce,
        instaKill: !!ev.instaKill
      };
    },

    _canShoot(tms) {
      const W = this._weaponEffective();
      const intervalMs = (60000 / Math.max(60, W.rpm));
      return (tms - this.state.shoot.lastShotAt) >= intervalMs;
    },

    _startReload(tms) {
      const S = this.state;
      const W = this._weaponEffective();

      if (!S.weapon) return false;
      if (S.reload.active) return false;
      if (S.weapon.mag >= W.magMax) return false;
      if (S.weapon.reserve <= 0) return false;

      S.reload.active = true;
      S.reload.startedAt = tms;
      S.reload.until = tms + W.reloadMs;

      return true;
    },

    _finishReload() {
      const S = this.state;
      if (!S.weapon) return;

      const W = this._weaponEffective();

      const need = Math.max(0, W.magMax - S.weapon.mag);
      const take = Math.min(need, S.weapon.reserve);

      S.weapon.mag += take;
      S.weapon.reserve -= take;

      // clamp to maxima
      S.weapon.magMax = W.magMax;
      S.weapon.reserveMax = W.reserveMax;
      S.weapon.mag = clamp(S.weapon.mag, 0, W.magMax);
      S.weapon.reserve = clamp(S.weapon.reserve, 0, W.reserveMax);

      S.reload.active = false;
      S.reload.until = 0;
    },

    _shoot(tms) {
      if (!this._canShoot(tms)) return;

      const S = this.state;
      const W = this._weaponEffective();

      // if reloading -> block
      if (S.reload.active) return;

      // if empty -> auto reload
      if ((S.weapon.mag | 0) <= 0) {
        this._startReload(tms);
        return;
      }

      // ammo consumption
      S.weapon.mag = Math.max(0, (S.weapon.mag | 0) - 1);

      S.shoot.lastShotAt = tms;

      const sp = CFG.bullet.speed;
      const ax = this.input.aimX;
      const ay = this.input.aimY;

      // crit roll per shot group
      const isCrit = (Math.random() < (W.critChance || 0));
      const critMul = isCrit ? 1.45 : 1.0;

      for (let i = 0; i < (W.bullets | 0); i++) {
        const a = Math.atan2(ay, ax) + rand(-W.spread, W.spread);
        const dx = Math.cos(a);
        const dy = Math.sin(a);

        S.bullets.push({
          x: S.player.x + dx * 18,
          y: S.player.y + dy * 18,
          vx: dx * sp,
          vy: dy * sp,
          born: tms,
          life: CFG.bullet.lifeMs,
          dmg: (W.instaKill ? 9999 : (W.dmg * critMul)),
          pierce: Math.max(0, W.pierce | 0),
          r: CFG.bullet.radius,
          crit: isCrit ? 1 : 0
        });
      }

      // if mag hits 0 -> auto reload
      if ((S.weapon.mag | 0) <= 0 && S.weapon.reserve > 0) {
        this._startReload(tms);
      }
    },

    _applyPlateIfDone(tms) {
      const S = this.state;
      const P = S.player;
      if (!P.plating.active) return;

      if (tms < (P.plating.until || 0)) return;

      const st = this._effectiveStats();
      if (P.plates > 0 && P.armor < st.armorMax) {
        P.plates -= 1;
        P.armor = Math.min(st.armorMax, P.armor + st.plateValue);
      }

      P.plating.active = false;
      P.plating.until = 0;
    },

    _damagePlayer(amount, tms) {
      const S = this.state;
      const st = this._effectiveStats();

      if (tms - S.player.lastHitAt < st.iFramesMs) return;

      S.player.lastHitAt = tms;

      let dmg = Math.max(1, Math.round(Number(amount) || 0));

      // plating cancels if hit
      if (S.player.plating.active) {
        S.player.plating.active = false;
        S.player.plating.until = 0;
      }

      // armor absorbs a chunk if available
      if (S.player.armor > 0) {
        const toArmor = Math.min(S.player.armor, Math.round(dmg * CFG.player.armorDmgAbsorb));
        S.player.armor -= toArmor;
        dmg -= toArmor;
      }

      S.player.hp = Math.max(0, S.player.hp - dmg);

      if (S.player.hp <= 0) this.running = false;
    },

    _awardXP(xp) {
      const S = this.state;
      const add = Math.max(0, xp | 0);
      S.xp += add;

      // simple level curve
      while (S.xp >= (S.level * 120 + 60)) {
        S.xp -= (S.level * 120 + 60);
        S.level += 1;

        // tiny level-up rewards (roguelike only)
        if (this.meta.mode === "roguelike") {
          S.coins += 4 + Math.floor(S.level * 0.6);
          // small heal
          const st = this._effectiveStats();
          S.player.hp = Math.min(st.hpMax, S.player.hp + 12);
        }
      }
    },

    _spawnPickup(kind, x, y, data) {
      const S = this.state;
      S.pickups.push({
        kind,
        x, y,
        vx: rand(-18, 18),
        vy: rand(-18, 18),
        born: performance.now(),
        life: CFG.loot.pickupLifeMs,
        data: data || null,
        r: 10
      });
    },

    _dropOnKill(z) {
      if (this.meta.mode !== "roguelike") return;

      const S = this.state;
      const st = this._effectiveStats();
      const wave = S.wave | 0;

      // perk boosts
      const lootBoost = st.lootBonus || 0;

      const coinChance = clamp(CFG.loot.coinChance + lootBoost * 0.12, 0, 0.95);
      const ammoChance = clamp(CFG.loot.ammoChance + lootBoost * 0.07, 0, 0.50);
      const plateChance = clamp(CFG.loot.plateChance + lootBoost * 0.05, 0, 0.40);

      const weaponChance = clamp(CFG.loot.weaponChance + (wave - 1) * CFG.loot.weaponChanceWaveBonus + lootBoost * 0.08, 0, 0.22);
      const eventChance = clamp(CFG.loot.eventChance + (wave - 1) * CFG.loot.eventChanceWaveBonus + lootBoost * 0.06, 0, 0.16);

      const x = z.x, y = z.y;

      // coins
      if (Math.random() < coinChance) {
        const base = 1 + Math.floor(wave * 0.35);
        const elite = z.elite ? 1.6 : 1.0;
        const amt = Math.max(1, Math.round(base * elite));
        this._spawnPickup("coins", x, y, { amount: amt });
      }

      // ammo
      if (Math.random() < ammoChance) {
        const amt = 10 + Math.floor(wave * 1.2);
        this._spawnPickup("ammo", x, y, { amount: amt });
      }

      // plate
      if (Math.random() < plateChance) {
        this._spawnPickup("plate", x, y, { amount: 1 });
      }

      // weapon drop
      if (Math.random() < weaponChance) {
        const rarity = rollRarity(wave + (z.elite ? 3 : 0));
        const keys = Object.keys(CFG.weapons);
        const wkey = pick(keys);
        const up = clamp(Math.floor((wave - 1) / 6), 0, 3);
        this._spawnPickup("weapon", x, y, { weaponKey: wkey, rarity, upgrade: up });
      }

      // event drop
      if (Math.random() < eventChance) {
        const e = pick(["max_ammo", "double_points", "insta_kill"]);
        this._spawnPickup("event", x, y, { event: e });
      }
    },

    _applyPickup(pu) {
      const S = this.state;
      const st = this._effectiveStats();

      if (!pu) return false;

      if (pu.kind === "coins") {
        const ev = this._eventsActive();
        const amt = Math.max(1, (pu.data?.amount | 0) || 1);
        S.coins += ev.doublePoints ? (amt * 2) : amt;
        return true;
      }

      if (pu.kind === "ammo") {
        const amt = Math.max(1, (pu.data?.amount | 0) || 10);

        const W = this._weaponEffective();
        if (S.weapon) {
          S.weapon.reserve = Math.min(W.reserveMax, (S.weapon.reserve | 0) + amt);
          if (S.weapon.mag < W.magMax && Math.random() < 0.35) S.weapon.mag = Math.min(W.magMax, S.weapon.mag + 2);
        }
        return true;
      }

      if (pu.kind === "plate") {
        const amt = Math.max(1, (pu.data?.amount | 0) || 1);
        S.player.plates = Math.min(st.platesMax, (S.player.plates | 0) + amt);
        return true;
      }

      if (pu.kind === "weapon") {
        const wkey = pu.data?.weaponKey;
        const rarity = pu.data?.rarity || "common";
        const up = pu.data?.upgrade || 0;

        if (CFG.weapons[wkey]) {
          S.weapon = mkWeapon(wkey, rarity, up);
          this.meta.weaponKey = wkey;

          S.weapon.mag = S.weapon.magMax;
          S.weapon.reserve = S.weapon.reserveMax;

          S.reload.active = false;
          S.reload.until = 0;
          return true;
        }
        return false;
      }

      if (pu.kind === "event") {
        const now = performance.now();
        const e = String(pu.data?.event || "");

        if (e === "max_ammo") {
          S.events.maxAmmoUntil = now + CFG.events.maxAmmoMs;

          const W = this._weaponEffective();
          if (S.weapon) {
            S.weapon.mag = W.magMax;
            S.weapon.reserve = W.reserveMax;
          }
          return true;
        }

        if (e === "double_points") {
          S.events.doublePointsUntil = now + CFG.events.doublePointsMs;
          return true;
        }

        if (e === "insta_kill") {
          S.events.instaKillUntil = now + CFG.events.instaKillMs;
          return true;
        }

        return false;
      }

      return false;
    },

    _tickPickups(dt, tms) {
      const S = this.state;
      if (!S.pickups || !S.pickups.length) return;

      const px = S.player.x, py = S.player.y;

      for (let i = S.pickups.length - 1; i >= 0; i--) {
        const pu = S.pickups[i];

        if ((tms - pu.born) > pu.life) {
          S.pickups.splice(i, 1);
          continue;
        }

        pu.x += (pu.vx || 0) * dt;
        pu.y += (pu.vy || 0) * dt;
        pu.vx *= 0.92;
        pu.vy *= 0.92;

        const dx = px - pu.x;
        const dy = py - pu.y;
        const d = len(dx, dy);

        if (d < CFG.loot.magnetRadius) {
          const n = norm(dx, dy);
          const pull = (CFG.loot.magnetStrength * (1 - d / CFG.loot.magnetRadius));
          pu.x += n.x * pull;
          pu.y += n.y * pull;
        }

        if (d < CFG.loot.pickupRadius) {
          if (this._applyPickup(pu)) {
            S.pickups.splice(i, 1);
          }
        }
      }
    },

    _tick(dt, tms) {
      const S = this.state;

      // run clock
      S.timeMs = Math.max(0, (tms - this.startedAt));

      const st = this._effectiveStats();

      // plating finish
      this._applyPlateIfDone(tms);

      // reload finish
      if (S.reload.active && tms >= (S.reload.until || 0)) {
        this._finishReload();
      }

      // movement (with weapon move penalty)
      const mx = this.input.moveX;
      const my = this.input.moveY;

      let speed = st.speed;
      const W = this._weaponEffective();
      const penalty = (W.movePenalty || 0) * (st.movePenaltyMul || 1.0);
      speed *= (1.0 - clamp(penalty, 0, 0.22));

      if (S.player.plating.active) speed *= 0.86;

      S.player.vx = mx * speed;
      S.player.vy = my * speed;
      S.player.x += S.player.vx * dt;
      S.player.y += S.player.vy * dt;

      // clamp to map/arena
      this._clampToMapOrArena(S.player);

      // world/map collisions module can refine player entity collisions
      try {
        const C = window.BCO_ZOMBIES_COLLISIONS;
        const map = this._mapInfo();
        if (C?.collideEntityWithMap && map) {
          const ent = { x: S.player.x, y: S.player.y, r: st.hitbox };
          C.collideEntityWithMap(ent, map);
          S.player.x = ent.x;
          S.player.y = ent.y;
        }
      } catch {}

      // shooting
      if (this.input.shooting) this._shoot(tms);

      // bullets update
      for (let i = S.bullets.length - 1; i >= 0; i--) {
        const b = S.bullets[i];
        b.x += b.vx * dt;
        b.y += b.vy * dt;

        if ((tms - b.born) > b.life) { S.bullets.splice(i, 1); continue; }

        const map = this._mapInfo();
        if (map && map.w && map.h) {
          const pad = 900;
          const halfW = map.w / 2 + pad;
          const halfH = map.h / 2 + pad;
          if (b.x < -halfW || b.x > halfW || b.y < -halfH || b.y > halfH) {
            S.bullets.splice(i, 1);
            continue;
          }
        } else {
          if (len(b.x, b.y) > CFG.arenaRadius + 1200) { S.bullets.splice(i, 1); continue; }
        }
      }

      // allow collisions module to remove bullets hitting walls
      try {
        const C = window.BCO_ZOMBIES_COLLISIONS;
        const map = this._mapInfo();
        if (C?.collideBullets && map) C.collideBullets(S.bullets, map);
      } catch {}

      // zombies seek
      for (let i = S.zombies.length - 1; i >= 0; i--) {
        const z = S.zombies[i];

        // bosses are ticked by bosses module; we still want them to exist here
        if (z.kind === "boss_brute" || z.kind === "boss_spitter") {
          continue;
        }

        const dx = S.player.x - z.x;
        const dy = S.player.y - z.y;
        const n = norm(dx, dy);

        z.vx = n.x * z.sp;
        z.vy = n.y * z.sp;
        z.x += z.vx * dt;
        z.y += z.vy * dt;

        // map collisions for zombies
        try {
          const C = window.BCO_ZOMBIES_COLLISIONS;
          const map = this._mapInfo();
          if (C?.collideEntityWithMap && map) C.collideEntityWithMap(z, map);
        } catch {}

        const dist = len(dx, dy);
        if (dist < (z.r + st.hitbox)) {
          if (tms >= z.nextTouchAt) {
            z.nextTouchAt = tms + CFG.zombie.touchDpsMs;
            this._damagePlayer(CFG.zombie.damage, tms);
          }
        }
      }

      // allow world module to apply map collisions + bosses + extra systems
      if (typeof this._tickWorld === "function") {
        try { this._tickWorld(this, dt, tms); } catch {}
      }

      // bullets vs zombies (includes bosses via _onBulletHit hook)
      for (let bi = S.bullets.length - 1; bi >= 0; bi--) {
        const b = S.bullets[bi];
        let consumed = false;

        for (let zi = S.zombies.length - 1; zi >= 0; zi--) {
          const z = S.zombies[zi];
          const dx = z.x - b.x;
          const dy = z.y - b.y;
          const dist = len(dx, dy);

          if (dist < ((z.r || CFG.zombie.radius) + b.r)) {
            const isBoss = (z.kind === "boss_brute" || z.kind === "boss_spitter");

            // ---- Boss hook path (NO double damage / NO double pierce) ----
            if (isBoss && typeof this._onBulletHit === "function") {
              try {
                // _onBulletHit decides boss hp + pierce consumption, returns true if bullet consumed
                consumed = !!this._onBulletHit(this, z, b);
              } catch {
                // fallback if hook crashes
                z.hp -= b.dmg;
                if (b.pierce > 0) b.pierce -= 1;
                else consumed = true;
              }
            } else {
              // ---- Default damage path (all non-boss, or boss without hook) ----
              z.hp -= b.dmg;

              if (z.hp <= 0) {
                S.zombies.splice(zi, 1);
                S.kills += 1;

                if (this.meta.mode === "roguelike") {
                  S.coins += (z.elite ? 2 : 1);
                }

                this._awardXP(CFG.progress.xpKill + (z.elite ? 4 : 0));
                this._dropOnKill(z);
              }

              if (b.pierce > 0) b.pierce -= 1;
              else consumed = true;
            }

            // If boss died (hook or fallback), remove + reward + drops (SAFE remove)
            if (isBoss && z.hp <= 0) {
              if (S.zombies[zi] === z) S.zombies.splice(zi, 1);

              S.kills += 3;
              this._awardXP(CFG.progress.xpBoss);

              if (this.meta.mode === "roguelike") {
                this._spawnPickup("coins", z.x, z.y, { amount: 10 + Math.floor(S.wave * 1.2) });
                this._spawnPickup("event", z.x + 18, z.y, { event: pick(["max_ammo", "double_points", "insta_kill"]) });
                this._spawnPickup("weapon", z.x - 18, z.y, { weaponKey: pick(Object.keys(CFG.weapons)), rarity: rollRarity(S.wave + 6), upgrade: clamp(Math.floor((S.wave - 1) / 5), 1, 4) });
                this._spawnPickup("plate", z.x, z.y + 18, { amount: 1 });
              }
            }

            if (consumed) break;
          }
        }

        if (consumed) S.bullets.splice(bi, 1);
      }

      // pickups tick
      this._tickPickups(dt, tms);

      // next wave
      if (S.zombies.length === 0 && this.running) {
        S.wave += 1;

        this._awardXP(CFG.progress.xpWave + Math.floor(S.wave * 0.6));

        if (this.meta.mode === "roguelike") {
          S.coins += 2 + Math.floor(S.wave * 0.35);

          if (Math.random() < clamp(0.05 + (S.wave - 1) * 0.003, 0.05, 0.12)) {
            const e = pick(["double_points", "insta_kill"]);
            this._spawnPickup("event", S.player.x + rand(-40, 40), S.player.y + rand(-40, 40), { event: e });
          }
        }

        this._spawnWave(S.wave);
      }

      // clamp vitals
      this._clampVitals();

      // camera follow
      S.camX = S.player.x;
      S.camY = S.player.y;
    }
  };

  window.BCO_ZOMBIES_CORE = CORE;
  console.log("[Z_CORE] loaded (LUX COD-ZOMBIES-2D v1)");
})();
