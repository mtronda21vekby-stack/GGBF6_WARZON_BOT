// app/webapp/static/zombies.core.js  [LUX COD-ZOMBIES-2D v1.3 | 3D-READY CORE]
// ✅ FIX PACK v1.3 (NO UI CHANGES):
// - Roguelike truly works: coins/pickups/economy always active in roguelike
// - Stable public API aliases (engine/app compatibility): setMode, setFire, setShooting, setInput, step
// - Safer bullet/zombie kill handling (no double-splice / boss kill bugs)
// - Pickups born-time uses sim time for consistency, life checks stable
// - Better mode separation: Arcade = no economy/pickups; Roguelike = full loop
// - Snapshot HUD includes ammo/weapon/perks/events/xp/level/coins/wave/kills
(() => {
  "use strict";

  // -------------------------
  // Time helpers (safe)
  // -------------------------
  const _now = () => (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now();

  // -------------------------
  // Math utils
  // -------------------------
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const len = (x, y) => Math.hypot(x, y) || 0;
  const norm = (x, y) => {
    const L = len(x, y);
    if (!L || !Number.isFinite(L)) return { x: 0, y: 0, L: 0 };
    return { x: x / L, y: y / L, L };
  };
  const rand = (a, b) => a + Math.random() * (b - a);
  const pick = (arr) => arr[(Math.random() * arr.length) | 0];

  // -------------------------
  // Entity IDs (stable for render)
  // -------------------------
  let _eid = 1;
  const nextId = () => (_eid++);

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
    const w = Math.max(1, wave | 0);
    const t = Math.random();
    const bonus = clamp((w - 1) / 18, 0, 0.35);

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
    dtFixed: 1 / 60,
    dtMax: 1 / 18,
    maxSubSteps: 6,

    arenaRadius: 780,
    mapClampPadding: 80,

    player: {
      speed: 320,
      hpMax: 100,
      hitbox: 16,
      iFramesMs: 230,

      armorMax: 150,
      plateValue: 50,
      platesMax: 3,
      platesStart: 0,
      plateUseMs: 680,
      armorDmgAbsorb: 0.72
    },

    bullet: {
      speed: 980,
      lifeMs: 900,
      radius: 3
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

    weapons: {
      SMG:  { name: "SMG",    type: "smg",  rpm: 820, dmg: 10, spread: 0.080, bullets: 1, mag: 32, reserve: 160, reloadMs: 980,  movePenalty: 0.00, crit: 0.06, pierce: 0 },
      AR:   { name: "AR",     type: "ar",   rpm: 640, dmg: 14, spread: 0.050, bullets: 1, mag: 30, reserve: 180, reloadMs: 1100, movePenalty: 0.02, crit: 0.08, pierce: 0 },
      SG:   { name: "SG",     type: "sg",   rpm: 140, dmg: 8,  spread: 0.220, bullets: 7, mag: 7,  reserve: 56,  reloadMs: 1250, movePenalty: 0.05, crit: 0.03, pierce: 0 },
      LMG:  { name: "LMG",    type: "lmg",  rpm: 520, dmg: 15, spread: 0.065, bullets: 1, mag: 60, reserve: 240, reloadMs: 1650, movePenalty: 0.08, crit: 0.06, pierce: 0 },
      MARK: { name: "DMR",    type: "dmr",  rpm: 310, dmg: 36, spread: 0.020, bullets: 1, mag: 12, reserve: 72,  reloadMs: 1350, movePenalty: 0.06, crit: 0.14, pierce: 1 },
      PIST: { name: "Pistol", type: "pist", rpm: 420, dmg: 12, spread: 0.060, bullets: 1, mag: 15, reserve: 90,  reloadMs: 880,  movePenalty: 0.00, crit: 0.06, pierce: 0 }
    },

    perks: {
      Jug:    { id: "Jug",    cost: 12, name: "Jug",    desc: "+HP max (premium)" },
      Speed:  { id: "Speed",  cost: 10, name: "Speed",  desc: "+Move speed" },
      Mag:    { id: "Mag",    cost: 8,  name: "Mag",    desc: "+Mag size +reserve +pierce" },
      Armor:  { id: "Armor",  cost: 14, name: "Armor",  desc: "Start with plates + faster plating" },
      Reload: { id: "Reload", cost: 11, name: "Reload", desc: "Faster reload" },
      Crit:   { id: "Crit",   cost: 13, name: "Crit",   desc: "Higher crit chance/dmg" },
      Loot:   { id: "Loot",   cost: 12, name: "Loot",   desc: "Better drop rates" },
      Sprint: { id: "Sprint", cost: 10, name: "Sprint", desc: "Less move penalty" }
    },

    loot: {
      coinChance: 0.70,
      ammoChance: 0.16,
      plateChance: 0.12,
      weaponChance: 0.06,
      eventChance: 0.035,

      weaponChanceWaveBonus: 0.0025,
      eventChanceWaveBonus:  0.0015,

      pickupRadius: 42,
      pickupLifeMs: 12000,

      magnetRadius: 120,
      magnetStrength: 6.0
    },

    events: {
      maxAmmoMs: 9000,
      doublePointsMs: 9000,
      instaKillMs: 6500
    },

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

    const magMax = Math.max(1, Math.round(base.mag * rar.mag * upMag));
    const reserveMax = Math.max(0, Math.round(base.reserve * rar.mag * upMag));
    const reloadMs = Math.max(200, Math.round(base.reloadMs * rar.reload * upReload));

    return {
      key,
      name: base.name,
      type: base.type,

      rarity: rar.id,
      rarityName: rar.name,
      rarityColor: rar.color,

      rpm: Math.max(60, base.rpm * rar.rpm),
      dmg: Math.max(1, base.dmg * rar.dmg * upDmg),
      spread: Math.max(0.0001, base.spread * rar.spread),
      bullets: Math.max(1, base.bullets | 0),

      magMax,
      reserveMax,
      reloadMs,

      movePenalty: base.movePenalty,
      crit: base.crit,
      pierce: base.pierce | 0,

      mag: magMax,
      reserve: reserveMax,

      upgrade: up
    };
  }

  // -------------------------
  // CORE
  // -------------------------
  const CORE = {
    cfg: CFG,

    running: false,
    startedAt: 0,
    lastFrameAt: 0,
    _acc: 0,
    _alpha: 0,

    // input (renderer/controls writes here)
    input: {
      moveX: 0, moveY: 0,
      aimX: 1, aimY: 0,
      shooting: false
    },

    // meta
    meta: {
      mode: "arcade",   // arcade/roguelike
      map: "Ashes",
      character: "male",
      skin: "default",
      weaponKey: "SMG"
    },

    // state (gameplay truth)
    state: {
      w: 0, h: 0,
      camX: 0, camY: 0,

      timeMs: 0,
      wave: 1,
      kills: 0,
      coins: 0,

      xp: 0,
      level: 1,

      perks: { Jug: 0, Speed: 0, Mag: 0, Armor: 0, Reload: 0, Crit: 0, Loot: 0, Sprint: 0 },

      player: {
        id: 0,
        x: 0, y: 0, vx: 0, vy: 0,
        px: 0, py: 0,
        hp: CFG.player.hpMax,
        armor: 0,
        plates: 0,
        plating: { active: false, until: 0 },
        lastHitAt: -99999
      },

      weapon: null,
      reload: { active: false, until: 0, startedAt: 0 },

      bullets: [],
      zombies: [],
      pickups: [],

      events: { maxAmmoUntil: 0, doublePointsUntil: 0, instaKillUntil: 0 },
      shoot: { lastShotAt: 0 },

      _bossSpawned: {}
    },

    // optional hooks
    _tickWorld: null,
    _buyPerk: null,
    _onBulletHit: null,

    // renderer-facing hooks (optional)
    hooks: {
      onStart: null,
      onStop: null,
      onKill: null,
      onPickup: null,
      onWave: null,
      onDamage: null
    },

    // -------------------------------------------------------
    // Public control (API)
    // -------------------------------------------------------
    setMode(mode) {
      const m = (String(mode || "").toLowerCase().includes("rogue")) ? "roguelike" : "arcade";
      this.meta.mode = m;

      // If already running and someone toggles mode, do a safe "rules refresh" (no UI changes)
      if (this.running) {
        // Arcade disables economy/pickups; Roguelike enables
        if (m === "arcade") {
          // keep vitals, but zero coins and clear pickups to avoid weird state
          this.state.coins = 0;
          this.state.pickups = [];
          this.state.player.plates = 0;
          this.state.player.armor = 0;
        } else {
          // ensure roguelike has some baseline to feel alive
          if ((this.state.coins | 0) < 3) this.state.coins = 3;
          if ((this.state.player.plates | 0) < 1) this.state.player.plates = 1;
        }
        this._clampVitals();
        this._clampAmmoToEffective();
      }
      return this.meta.mode;
    },

    // Aliases for engine/app compatibility
    setFire(on) { return this.setShooting(on); },
    setShooting(on) { this.input.shooting = !!on; return true; },

    setInput(inp) {
      const o = inp || {};
      const mv = o.move || o.m || null;
      const am = o.aim || o.a || null;

      if (mv) this.setMove(mv.x, mv.y);
      if (am) this.setAim(am.x, am.y);

      if (typeof o.firing === "boolean") this.setShooting(o.firing);
      if (typeof o.shooting === "boolean") this.setShooting(o.shooting);
      if (typeof o.fire === "boolean") this.setShooting(o.fire);
      return true;
    },

    // Engine may call updateFrame; some code calls step()
    step(tms) { return this.updateFrame(tms); },

    start(mode, w, h, opts = {}, tms = _now()) {
      this.setMode(mode);

      this.state.w = Math.max(1, w | 0);
      this.state.h = Math.max(1, h | 0);

      if (opts.map) this.meta.map = String(opts.map);
      if (opts.character) this.meta.character = String(opts.character);
      if (opts.skin) this.meta.skin = String(opts.skin);
      if (opts.weaponKey && CFG.weapons[opts.weaponKey]) this.meta.weaponKey = opts.weaponKey;

      this._resetRun();

      // bosses module install (safe)
      try {
        const B = window.BCO_ZOMBIES_BOSSES;
        if (B?.install && !this._bossInstalled) {
          B.install(this, () => window.BCO_ZOMBIES_MAPS?.get?.(this.meta.map) || null);
          this._bossInstalled = true;
        }
      } catch {}

      this.running = true;
      this.startedAt = Number(tms) || _now();
      this.lastFrameAt = this.startedAt;
      this._acc = 0;
      this._alpha = 0;

      try { if (typeof this.hooks.onStart === "function") this.hooks.onStart(this); } catch {}
      return true;
    },

    stop() {
      this.running = false;
      try { if (typeof this.hooks.onStop === "function") this.hooks.onStop(this); } catch {}
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
      const n = norm(Number(x) || 0, Number(y) || 0);
      if (n.L > 0.02) {
        this.input.aimX = n.x;
        this.input.aimY = n.y;
      }
      return true;
    },

    setWeapon(key) {
      if (CFG.weapons[key]) this.meta.weaponKey = key;

      // mid-run swap: preserve rarity/upgrade, clamp ammo
      try {
        const S = this.state;
        if (S.weapon && CFG.weapons[this.meta.weaponKey]) {
          const rar = S.weapon.rarity || "common";
          const up = S.weapon.upgrade || 0;
          const oldMag = S.weapon.mag | 0;
          const oldRes = S.weapon.reserve | 0;

          S.weapon = mkWeapon(this.meta.weaponKey, rar, up);

          const W = this._weaponEffective();
          S.weapon.mag = clamp(oldMag, 0, W.magMax);
          S.weapon.reserve = clamp(oldRes, 0, W.reserveMax);
          S.weapon.magMax = W.magMax;
          S.weapon.reserveMax = W.reserveMax;

          S.reload.active = false;
          S.reload.until = 0;
        }
      } catch {}

      return this.meta.weaponKey;
    },

    reload() {
      const S = this.state;
      if (!S.weapon) return false;
      if (S.reload.active) return false;

      const W = this._weaponEffective();
      if ((S.weapon.mag | 0) >= (W.magMax | 0)) return false;
      if ((S.weapon.reserve | 0) <= 0) return false;

      this._startReload(_now());
      return true;
    },

    usePlate() {
      if (this.meta.mode !== "roguelike") return false;

      const S = this.state;
      const P = S.player;
      const st = this._effectiveStats();

      if ((P.plates | 0) <= 0) return false;
      if (P.plating.active) return false;
      if ((P.armor | 0) >= st.armorMax) return false;

      const tms = _now();
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
      if ((this.state.coins | 0) < p.cost) return false;

      this.state.coins -= p.cost;
      this.state.perks[id] = 1;

      if (typeof this._buyPerk === "function") {
        try { this._buyPerk(this, id); } catch {}
      } else {
        if (id === "Jug") {
          const st = this._effectiveStats();
          this.state.player.hp = Math.min((this.state.player.hp | 0) + 40, st.hpMax);
        }
        if (id === "Armor") {
          const st = this._effectiveStats();
          this.state.player.plates = Math.min(st.platesMax, (this.state.player.plates | 0) + 1);
          this.state.player.armor = Math.min(st.armorMax, (this.state.player.armor | 0) + st.plateValue);
        }
      }

      this._clampVitals();
      this._clampAmmoToEffective();
      return true;
    },

    // Fixed-step update (3D-ready)
    updateFrame(tms) {
      if (!this.running) return false;

      const t = Number(tms) || _now();
      let frameDt = (t - this.lastFrameAt) / 1000;
      this.lastFrameAt = t;

      if (!Number.isFinite(frameDt)) frameDt = 0;
      frameDt = clamp(frameDt, 0, CFG.dtMax);

      this._acc += frameDt;

      let steps = 0;
      while (this._acc >= CFG.dtFixed && steps < CFG.maxSubSteps) {
        this._tickFixed(CFG.dtFixed, t);
        this._acc -= CFG.dtFixed;
        steps++;
      }

      this._alpha = clamp(this._acc / CFG.dtFixed, 0, 1);
      return true;
    },

    // 3D renderer reads this every frame (no mutation)
    getFrameData() {
      const S = this.state;
      const a = this._alpha;

      const lerp = (p, c) => (p + (c - p) * a);

      const player = {
        id: S.player.id,
        x: lerp(S.player.px, S.player.x),
        y: lerp(S.player.py, S.player.y),
        vx: S.player.vx,
        vy: S.player.vy,
        hp: S.player.hp,
        armor: S.player.armor,
        plates: S.player.plates,
        plating: !!S.player.plating.active
      };

      const bullets = S.bullets.map(b => ({
        id: b.id,
        x: lerp(b.px, b.x),
        y: lerp(b.py, b.y),
        vx: b.vx,
        vy: b.vy,
        r: b.r,
        crit: b.crit,
        dmg: b.dmg,
        pierce: b.pierce
      }));

      const zombies = S.zombies.map(z => ({
        id: z.id,
        kind: z.kind,
        x: lerp(z.px, z.x),
        y: lerp(z.py, z.y),
        vx: z.vx,
        vy: z.vy,
        r: z.r,
        hp: z.hp,
        elite: z.elite ? 1 : 0
      }));

      const pickups = S.pickups.map(p => ({
        id: p.id,
        kind: p.kind,
        x: lerp(p.px, p.x),
        y: lerp(p.py, p.y),
        r: p.r,
        data: p.data || null
      }));

      const weapon = S.weapon ? {
        key: S.weapon.key,
        name: S.weapon.name,
        rarity: S.weapon.rarity,
        upgrade: S.weapon.upgrade,
        mag: S.weapon.mag,
        reserve: S.weapon.reserve,
        magMax: S.weapon.magMax,
        reserveMax: S.weapon.reserveMax
      } : null;

      const ev = this._eventsActive();

      return {
        alpha: a,
        meta: { ...this.meta },
        hud: {
          timeMs: S.timeMs,
          wave: S.wave,
          kills: S.kills,
          coins: S.coins,
          xp: S.xp,
          level: S.level,
          events: ev,
          perks: { ...S.perks },
          weapon
        },
        camera: { x: S.camX, y: S.camY },
        player,
        bullets,
        zombies,
        pickups
      };
    },

    // -------------------------------------------------------
    // Internals
    // -------------------------------------------------------
    _effectiveStats() {
      const perks = this.state.perks || {};
      const jug = perks.Jug ? 1.40 : 1.0;
      const speed = perks.Speed ? 1.18 : 1.0;
      const sprint = perks.Sprint ? 0.70 : 1.0;

      const armorMax = CFG.player.armorMax * (perks.Armor ? 1.12 : 1.0);
      const plateUseMs = CFG.player.plateUseMs * (perks.Armor ? 0.85 : 1.0);

      const platesMax = CFG.player.platesMax + (perks.Armor ? 1 : 0);
      const reloadMul = perks.Reload ? 0.82 : 1.0;
      const critBonus = perks.Crit ? 0.06 : 0.0;
      const lootBonus = perks.Loot ? 0.45 : 0.0;

      return {
        hpMax: Math.round(CFG.player.hpMax * jug),
        speed: CFG.player.speed * speed,
        hitbox: CFG.player.hitbox,
        iFramesMs: CFG.player.iFramesMs,

        armorMax: Math.round(armorMax),
        plateValue: CFG.player.plateValue,
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
      S.player.hp = clamp(S.player.hp | 0, 0, st.hpMax | 0);
      S.player.armor = clamp(S.player.armor | 0, 0, st.armorMax | 0);
      S.player.plates = clamp(S.player.plates | 0, 0, st.platesMax | 0);
    },

    _clampAmmoToEffective() {
      const S = this.state;
      if (!S.weapon) return;
      const W = this._weaponEffective();
      S.weapon.magMax = W.magMax | 0;
      S.weapon.reserveMax = W.reserveMax | 0;
      S.weapon.mag = clamp(S.weapon.mag | 0, 0, W.magMax | 0);
      S.weapon.reserve = clamp(S.weapon.reserve | 0, 0, W.reserveMax | 0);
    },

    _resetRun() {
      const S = this.state;
      const st = this._effectiveStats();

      S.timeMs = 0;
      S.wave = 1;
      S.kills = 0;

      // MODE DIFFERENCE (hard, real)
      if (this.meta.mode === "roguelike") {
        S.coins = 5; // ✅ baseline so shop/perks actually work instantly
      } else {
        S.coins = 0;
      }

      S.xp = 0;
      S.level = 1;

      S.perks = { Jug: 0, Speed: 0, Mag: 0, Armor: 0, Reload: 0, Crit: 0, Loot: 0, Sprint: 0 };

      // player init
      S.player.id = nextId();
      S.player.x = 0; S.player.y = 0;
      S.player.px = 0; S.player.py = 0;
      S.player.vx = 0; S.player.vy = 0;
      S.player.hp = st.hpMax;
      S.player.armor = 0;

      // plates only matter in roguelike
      S.player.plates = (this.meta.mode === "roguelike") ? Math.max(0, CFG.player.platesStart | 0) : 0;
      S.player.plating = { active: false, until: 0 };
      S.player.lastHitAt = -99999;

      // weapon
      S.weapon = mkWeapon(this.meta.weaponKey, "common", 0);
      this._clampAmmoToEffective();

      S.reload = { active: false, until: 0, startedAt: 0 };

      // entities
      S.bullets = [];
      S.zombies = [];
      S.pickups = [];

      // events
      S.events = { maxAmmoUntil: 0, doublePointsUntil: 0, instaKillUntil: 0 };

      // other
      S.shoot.lastShotAt = 0;
      S._bossSpawned = {};

      // input defaults
      this.input.aimX = 1; this.input.aimY = 0;
      this.input.moveX = 0; this.input.moveY = 0;
      this.input.shooting = false;

      this._spawnWave(S.wave);
    },

    _mapInfo() {
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

      const eliteChance = clamp(0.02 + (wave - 1) * 0.004, 0.02, 0.12);

      for (let i = 0; i < count; i++) {
        const ang = rand(0, Math.PI * 2);
        const rr = rand(CFG.wave.spawnRingMin, CFG.wave.spawnRingMax);
        const x = S.player.x + Math.cos(ang) * rr;
        const y = S.player.y + Math.sin(ang) * rr;

        const elite = (Math.random() < eliteChance);

        S.zombies.push({
          id: nextId(),
          kind: "zombie",
          x, y, vx: 0, vy: 0,
          px: x, py: y,
          hp: (CFG.zombie.baseHp * hpMul) * (elite ? 1.55 : 1.0),
          sp: (CFG.zombie.baseSpeed * spMul) * (elite ? 1.12 : 1.0),
          r: CFG.zombie.radius + (elite ? 2 : 0),
          elite: elite ? 1 : 0,
          nextTouchAt: 0
        });
      }

      try { if (typeof this.hooks.onWave === "function") this.hooks.onWave(this, wave); } catch {}
    },

    _eventsActive() {
      const e = this.state.events;
      const t = _now();
      return {
        maxAmmo: t < (e.maxAmmoUntil || 0),
        doublePoints: t < (e.doublePointsUntil || 0),
        instaKill: t < (e.instaKillUntil || 0)
      };
    },

    _weaponEffective() {
      const S = this.state;
      const st = this._effectiveStats();
      const ev = this._eventsActive();

      const w = S.weapon || mkWeapon(this.meta.weaponKey, "common", 0);

      const perkMag = S.perks.Mag ? 1.18 : 1.0;
      const perkPierce = S.perks.Mag ? 1 : 0;
      const perkReload = st.reloadMul;

      const magMax = Math.max(1, Math.round((w.magMax || 1) * perkMag));
      const reserveMax = Math.max(0, Math.round((w.reserveMax || 0) * perkMag));
      const reloadMs = Math.max(200, Math.round((w.reloadMs || 900) * perkReload));

      const critChance = clamp((w.crit || 0) + st.critBonus, 0, 0.35);
      const pierce = Math.max(w.pierce | 0, perkPierce);

      return {
        ...w,
        rpm: Math.max(60, w.rpm || 60),
        dmg: Math.max(1, w.dmg || 1),
        spread: Math.max(0.0001, w.spread || 0.02),
        bullets: Math.max(1, w.bullets | 0),

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
      if ((S.weapon.mag | 0) >= (W.magMax | 0)) return false;
      if ((S.weapon.reserve | 0) <= 0) return false;

      S.reload.active = true;
      S.reload.startedAt = tms;
      S.reload.until = tms + W.reloadMs;
      return true;
    },

    _finishReload() {
      const S = this.state;
      if (!S.weapon) return;

      const W = this._weaponEffective();

      const need = Math.max(0, (W.magMax | 0) - (S.weapon.mag | 0));
      const take = Math.min(need, (S.weapon.reserve | 0));

      S.weapon.mag = (S.weapon.mag | 0) + take;
      S.weapon.reserve = (S.weapon.reserve | 0) - take;

      S.weapon.magMax = W.magMax | 0;
      S.weapon.reserveMax = W.reserveMax | 0;

      this._clampAmmoToEffective();

      S.reload.active = false;
      S.reload.until = 0;
    },

    _shoot(tms) {
      if (!this._canShoot(tms)) return;

      const S = this.state;
      const W = this._weaponEffective();

      if (S.reload.active) return;

      if ((S.weapon.mag | 0) <= 0) {
        this._startReload(tms);
        return;
      }

      S.weapon.mag = Math.max(0, (S.weapon.mag | 0) - 1);
      S.shoot.lastShotAt = tms;

      const sp = CFG.bullet.speed;
      const ax = this.input.aimX;
      const ay = this.input.aimY;

      const isCrit = (Math.random() < (W.critChance || 0));
      const critMul = isCrit ? 1.45 : 1.0;

      for (let i = 0; i < (W.bullets | 0); i++) {
        const a = Math.atan2(ay, ax) + rand(-W.spread, W.spread);
        const dx = Math.cos(a);
        const dy = Math.sin(a);

        const sx = S.player.x + dx * 18;
        const sy = S.player.y + dy * 18;

        S.bullets.push({
          id: nextId(),
          x: sx, y: sy,
          px: sx, py: sy,
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

      if ((S.weapon.mag | 0) <= 0 && (S.weapon.reserve | 0) > 0) {
        this._startReload(tms);
      }
    },

    _applyPlateIfDone(tms) {
      const S = this.state;
      const P = S.player;
      if (!P.plating.active) return;
      if (tms < (P.plating.until || 0)) return;

      const st = this._effectiveStats();
      if ((P.plates | 0) > 0 && (P.armor | 0) < (st.armorMax | 0)) {
        P.plates -= 1;
        P.armor = Math.min(st.armorMax | 0, (P.armor | 0) + (st.plateValue | 0));
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

      if (S.player.plating.active) {
        S.player.plating.active = false;
        S.player.plating.until = 0;
      }

      if ((S.player.armor | 0) > 0) {
        const toArmor = Math.min((S.player.armor | 0), Math.round(dmg * CFG.player.armorDmgAbsorb));
        S.player.armor = (S.player.armor | 0) - toArmor;
        dmg -= toArmor;
      }

      S.player.hp = Math.max(0, (S.player.hp | 0) - dmg);

      try { if (typeof this.hooks.onDamage === "function") this.hooks.onDamage(this, dmg); } catch {}

      if (S.player.hp <= 0) this.running = false;
    },

    _awardXP(xp) {
      const S = this.state;
      const add = Math.max(0, xp | 0);
      S.xp += add;

      while (S.xp >= (S.level * 120 + 60)) {
        S.xp -= (S.level * 120 + 60);
        S.level += 1;

        if (this.meta.mode === "roguelike") {
          S.coins += 4 + Math.floor(S.level * 0.6);
          const st = this._effectiveStats();
          S.player.hp = Math.min(st.hpMax | 0, (S.player.hp | 0) + 12);
        }
      }
    },

    _spawnPickup(kind, x, y, data, tms) {
      const S = this.state;
      const born = Number(tms) || _now();
      S.pickups.push({
        id: nextId(),
        kind,
        x, y,
        px: x, py: y,
        vx: rand(-18, 18),
        vy: rand(-18, 18),
        born,
        life: CFG.loot.pickupLifeMs,
        data: data || null,
        r: 10
      });
    },

    _dropOnKill(z, tms) {
      // ✅ Arcade has NO economy/drops (real difference)
      if (this.meta.mode !== "roguelike") return;

      const S = this.state;
      const st = this._effectiveStats();
      const wave = S.wave | 0;

      const lootBoost = st.lootBonus || 0;

      const coinChance  = clamp(CFG.loot.coinChance  + lootBoost * 0.12, 0, 0.95);
      const ammoChance  = clamp(CFG.loot.ammoChance  + lootBoost * 0.07, 0, 0.50);
      const plateChance = clamp(CFG.loot.plateChance + lootBoost * 0.05, 0, 0.40);

      const weaponChance = clamp(CFG.loot.weaponChance + (wave - 1) * CFG.loot.weaponChanceWaveBonus + lootBoost * 0.08, 0, 0.22);
      const eventChance  = clamp(CFG.loot.eventChance  + (wave - 1) * CFG.loot.eventChanceWaveBonus  + lootBoost * 0.06, 0, 0.16);

      const x = z.x, y = z.y;

      if (Math.random() < coinChance) {
        const base = 1 + Math.floor(wave * 0.35);
        const elite = z.elite ? 1.6 : 1.0;
        const amt = Math.max(1, Math.round(base * elite));
        this._spawnPickup("coins", x, y, { amount: amt }, tms);
      }

      if (Math.random() < ammoChance) {
        const amt = 10 + Math.floor(wave * 1.2);
        this._spawnPickup("ammo", x, y, { amount: amt }, tms);
      }

      if (Math.random() < plateChance) {
        this._spawnPickup("plate", x, y, { amount: 1 }, tms);
      }

      if (Math.random() < weaponChance) {
        const rarity = rollRarity(wave + (z.elite ? 3 : 0));
        const keys = Object.keys(CFG.weapons);
        const wkey = pick(keys);
        const up = clamp(Math.floor((wave - 1) / 6), 0, 3);
        this._spawnPickup("weapon", x, y, { weaponKey: wkey, rarity, upgrade: up }, tms);
      }

      if (Math.random() < eventChance) {
        const e = pick(["max_ammo", "double_points", "insta_kill"]);
        this._spawnPickup("event", x, y, { event: e }, tms);
      }
    },

    _applyPickup(pu, tms) {
      const S = this.state;
      const st = this._effectiveStats();
      if (!pu) return false;

      // ✅ Arcade does not apply pickup effects (even if something spawned by mistake)
      if (this.meta.mode !== "roguelike") return false;

      if (pu.kind === "coins") {
        const ev = this._eventsActive();
        const amt = Math.max(1, (pu.data?.amount | 0) || 1);
        S.coins += ev.doublePoints ? (amt * 2) : amt;
        try { if (typeof this.hooks.onPickup === "function") this.hooks.onPickup(this, pu); } catch {}
        return true;
      }

      if (pu.kind === "ammo") {
        const amt = Math.max(1, (pu.data?.amount | 0) || 10);
        const W = this._weaponEffective();
        if (S.weapon) {
          S.weapon.reserve = Math.min(W.reserveMax | 0, (S.weapon.reserve | 0) + amt);
          if ((S.weapon.mag | 0) < (W.magMax | 0) && Math.random() < 0.35) {
            S.weapon.mag = Math.min(W.magMax | 0, (S.weapon.mag | 0) + 2);
          }
          this._clampAmmoToEffective();
        }
        try { if (typeof this.hooks.onPickup === "function") this.hooks.onPickup(this, pu); } catch {}
        return true;
      }

      if (pu.kind === "plate") {
        const amt = Math.max(1, (pu.data?.amount | 0) || 1);
        S.player.plates = Math.min(st.platesMax | 0, (S.player.plates | 0) + amt);
        try { if (typeof this.hooks.onPickup === "function") this.hooks.onPickup(this, pu); } catch {}
        return true;
      }

      if (pu.kind === "weapon") {
        const wkey = pu.data?.weaponKey;
        const rarity = pu.data?.rarity || "common";
        const up = pu.data?.upgrade || 0;

        if (CFG.weapons[wkey]) {
          S.weapon = mkWeapon(wkey, rarity, up);
          this.meta.weaponKey = wkey;

          this._clampAmmoToEffective();
          S.weapon.mag = S.weapon.magMax;
          S.weapon.reserve = S.weapon.reserveMax;

          S.reload.active = false;
          S.reload.until = 0;

          try { if (typeof this.hooks.onPickup === "function") this.hooks.onPickup(this, pu); } catch {}
          return true;
        }
        return false;
      }

      if (pu.kind === "event") {
        const t = Number(tms) || _now();
        const e = String(pu.data?.event || "");

        if (e === "max_ammo") {
          S.events.maxAmmoUntil = t + CFG.events.maxAmmoMs;
          const W = this._weaponEffective();
          if (S.weapon) {
            S.weapon.mag = W.magMax | 0;
            S.weapon.reserve = W.reserveMax | 0;
            this._clampAmmoToEffective();
          }
          try { if (typeof this.hooks.onPickup === "function") this.hooks.onPickup(this, pu); } catch {}
          return true;
        }

        if (e === "double_points") {
          S.events.doublePointsUntil = t + CFG.events.doublePointsMs;
          try { if (typeof this.hooks.onPickup === "function") this.hooks.onPickup(this, pu); } catch {}
          return true;
        }

        if (e === "insta_kill") {
          S.events.instaKillUntil = t + CFG.events.instaKillMs;
          try { if (typeof this.hooks.onPickup === "function") this.hooks.onPickup(this, pu); } catch {}
          return true;
        }

        return false;
      }

      return false;
    },

    _tickPickups(dt, tms) {
      const S = this.state;

      // ✅ Arcade ignores pickups completely
      if (this.meta.mode !== "roguelike") {
        if (S.pickups.length) S.pickups = [];
        return;
      }

      if (!S.pickups || !S.pickups.length) return;

      const px = S.player.x, py = S.player.y;

      for (let i = S.pickups.length - 1; i >= 0; i--) {
        const pu = S.pickups[i];

        if ((tms - pu.born) > pu.life) {
          S.pickups.splice(i, 1);
          continue;
        }

        pu.px = pu.x; pu.py = pu.y;

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
          if (this._applyPickup(pu, tms)) S.pickups.splice(i, 1);
        }
      }
    },

    // Fixed step tick (NO render here)
    _tickFixed(dt, tms) {
      const S = this.state;

      // keep previous for interpolation
      S.player.px = S.player.x; S.player.py = S.player.y;

      // run clock
      S.timeMs = Math.max(0, (tms - this.startedAt));

      const st = this._effectiveStats();

      // plating finish
      this._applyPlateIfDone(tms);

      // reload finish
      if (S.reload.active && tms >= (S.reload.until || 0)) this._finishReload();

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

      this._clampToMapOrArena(S.player);

      // collisions (player)
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

      // bullets
      for (let i = S.bullets.length - 1; i >= 0; i--) {
        const b = S.bullets[i];
        b.px = b.x; b.py = b.y;

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

      // bullets vs walls
      try {
        const C = window.BCO_ZOMBIES_COLLISIONS;
        const map = this._mapInfo();
        if (C?.collideBullets && map) C.collideBullets(S.bullets, map);
      } catch {}

      // zombies seek
      for (let i = S.zombies.length - 1; i >= 0; i--) {
        const z = S.zombies[i];
        z.px = z.x; z.py = z.y;

        // bosses move/tick from bosses module
        if (z.kind === "boss_brute" || z.kind === "boss_spitter") continue;

        const dx = S.player.x - z.x;
        const dy = S.player.y - z.y;
        const n = norm(dx, dy);

        z.vx = n.x * z.sp;
        z.vy = n.y * z.sp;
        z.x += z.vx * dt;
        z.y += z.vy * dt;

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

      // world module extra systems
      if (typeof this._tickWorld === "function") {
        try { this._tickWorld(this, dt, tms); } catch {}
      }

      // bullets vs zombies (+ bosses via hook)  ✅ SAFE KILL PATH
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

            // bullet hit -> damage
            if (isBoss && typeof this._onBulletHit === "function") {
              try {
                // _onBulletHit can decide consumption; if it doesn't, we do default
                const r = this._onBulletHit(this, z, b);
                if (typeof r === "boolean") consumed = r;
              } catch {}
            }

            // default damage if hook didn't handle it
            if (!isBoss || consumed === false) {
              z.hp -= b.dmg;
            }

            // pierce / consume
            if (b.pierce > 0) b.pierce -= 1;
            else consumed = true;

            // death
            if (z.hp <= 0) {
              // remove zombie now, safely
              S.zombies.splice(zi, 1);

              // rewards
              if (isBoss) {
                S.kills += 3;
                this._awardXP(CFG.progress.xpBoss);

                if (this.meta.mode === "roguelike") {
                  this._spawnPickup("coins", z.x, z.y, { amount: 10 + Math.floor(S.wave * 1.2) }, tms);
                  this._spawnPickup("event", z.x + 18, z.y, { event: pick(["max_ammo", "double_points", "insta_kill"]) }, tms);
                  this._spawnPickup("weapon", z.x - 18, z.y, { weaponKey: pick(Object.keys(CFG.weapons)), rarity: rollRarity(S.wave + 6), upgrade: clamp(Math.floor((S.wave - 1) / 5), 1, 4) }, tms);
                  this._spawnPickup("plate", z.x, z.y + 18, { amount: 1 }, tms);
                }
              } else {
                S.kills += 1;

                // small coin drip on kill (roguelike)
                if (this.meta.mode === "roguelike") S.coins += (z.elite ? 2 : 1);

                this._awardXP(CFG.progress.xpKill + (z.elite ? 4 : 0));
                this._dropOnKill(z, tms);
              }

              try { if (typeof this.hooks.onKill === "function") this.hooks.onKill(this, z); } catch {}
            }

            // consumed bullet exits zombie loop
            if (consumed) break;
          }
        }

        if (consumed) S.bullets.splice(bi, 1);
      }

      // pickups
      this._tickPickups(dt, tms);

      // next wave
      if (S.zombies.length === 0 && this.running) {
        S.wave += 1;

        this._awardXP(CFG.progress.xpWave + Math.floor(S.wave * 0.6));

        if (this.meta.mode === "roguelike") {
          S.coins += 2 + Math.floor(S.wave * 0.35);

          // small chance to spawn an event near player between waves
          if (Math.random() < clamp(0.05 + (S.wave - 1) * 0.003, 0.05, 0.12)) {
            const e = pick(["double_points", "insta_kill"]);
            this._spawnPickup("event", S.player.x + rand(-40, 40), S.player.y + rand(-40, 40), { event: e }, tms);
          }
        }

        this._spawnWave(S.wave);
      }

      // clamp vitals/ammo
      this._clampVitals();
      this._clampAmmoToEffective();

      // camera follow
      S.camX = S.player.x;
      S.camY = S.player.y;
    }
  };

  // Export
  window.BCO_ZOMBIES_CORE = CORE;
  console.log("[Z_CORE] loaded (LUX COD-ZOMBIES-2D v1.3 | 3D-READY CORE)");
})();
