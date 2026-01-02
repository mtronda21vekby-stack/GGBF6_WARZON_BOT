/* =========================================================
   BLACK CROWN OPS — ZOMBIES GAME v1.2 (FOUNDATION + ARMOR + MOBILE FIX)
   File: app/webapp/static/zombies.js
   ========================================================= */

(() => {
  "use strict";

  // ---------- GLOBAL ----------
  window.__BCO_ZOMBIES_OK__ = false;

  const DPR = Math.min(2, window.devicePixelRatio || 1);

  // ---------- HELPERS ----------
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const dist = (x1, y1, x2, y2) => Math.hypot(x2 - x1, y2 - y1);

  function nowMs() { return (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now(); }

  // ---------- OVERLAY / CANVAS (created only on start) ----------
  let overlay = null;
  let canvas = null;
  let ctx = null;

  function ensureOverlay() {
    if (overlay && canvas && ctx) return;

    const mount = document.getElementById("zOverlayMount") || document.body;

    overlay = document.createElement("div");
    overlay.id = "bcoZOverlay";
    overlay.style.position = "fixed";
    overlay.style.left = "0";
    overlay.style.top = "0";
    overlay.style.width = "100vw";
    overlay.style.height = "100vh";
    overlay.style.zIndex = "9999";
    overlay.style.background = "rgba(0,0,0,.92)";
    overlay.style.backdropFilter = "blur(10px)";
    overlay.style.webkitBackdropFilter = "blur(10px)";
    overlay.style.display = "none";
    overlay.style.overflow = "hidden";
    overlay.style.touchAction = "none"; // critical for iOS
    overlay.style.userSelect = "none";
    overlay.style.webkitUserSelect = "none";

    canvas = document.createElement("canvas");
    ctx = canvas.getContext("2d", { alpha: false });

    canvas.style.position = "absolute";
    canvas.style.left = "0";
    canvas.style.top = "0";
    canvas.style.width = "100%";
    canvas.style.height = "100%";
    canvas.style.background = "#05070c";
    canvas.style.touchAction = "none"; // critical for iOS
    canvas.style.userSelect = "none";
    canvas.style.webkitUserSelect = "none";

    overlay.appendChild(canvas);
    mount.appendChild(overlay);

    // Prevent page scroll behind overlay (iOS)
    overlay.addEventListener("touchmove", (e) => e.preventDefault(), { passive: false });
  }

  function resize() {
    if (!canvas || !ctx) return;
    const w = Math.floor(window.innerWidth * DPR);
    const h = Math.floor(window.innerHeight * DPR);
    canvas.width = w;
    canvas.height = h;
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);

    // keep player on screen after rotate
    player.x = clamp(player.x, 24, (canvas.width / DPR) - 24);
    player.y = clamp(player.y, 24, (canvas.height / DPR) - 24);
  }

  function showOverlay() {
    ensureOverlay();
    overlay.style.display = "block";
    overlay.setAttribute("aria-hidden", "false");
    window.addEventListener("resize", resize);
    resize();

    // Best-effort: try to go immersive (may fail silently)
    try {
      if (window.Telegram && Telegram.WebApp) {
        Telegram.WebApp.expand();
        Telegram.WebApp.disableClosingConfirmation?.();
      }
    } catch {}
    // Best-effort lock (may fail on iOS)
    try {
      if (screen.orientation && screen.orientation.lock) {
        screen.orientation.lock("landscape").catch(() => {});
      }
    } catch {}
  }

  function hideOverlay() {
    if (!overlay) return;
    overlay.style.display = "none";
    overlay.setAttribute("aria-hidden", "true");
    window.removeEventListener("resize", resize);
  }

  // ---------- GAME STATE ----------
  const GAME = {
    mode: "ARCADE", // or ROGUELIKE
    running: false,
    startedAt: 0,
    time: 0,
    wave: 1,
    kills: 0,
    coins: 0,

    // pacing
    spawnCapBase: 3,
    waveKills: 10,
  };

  // ---------- PLAYER ----------
  const player = {
    x: 240,
    y: 240,
    r: 18,
    speed: 3.2,
    hp: 100,

    // ARMOR SYSTEM (Warzone-ish)
    armor: 0,          // current armor points
    armorMax: 150,     // 3 plates * 50
    plates: 0,         // number of plates
    platesMax: 3,      // max plates
    plateValue: 50,    // each plate adds 50 armor
    plateCost: 10,     // cost in coins (roguelike shop can change)

    level: 1,
    xp: 0,
    xpNext: 50,

    dirX: 0,
    dirY: 0,
    fireCooldown: 0,
    invulnUntil: 0, // short i-frames after hit
  };

  function addXP(amount) {
    player.xp += amount;
    while (player.xp >= player.xpNext) {
      player.xp -= player.xpNext;
      player.level += 1;
      player.xpNext = Math.floor(player.xpNext * 1.35 + 10);
      // tiny scaling
      player.hp = Math.min(130, player.hp + 5);
      player.speed = Math.min(4.4, player.speed + 0.05);
    }
  }

  function applyDamage(dmg) {
    const t = nowMs();
    if (t < player.invulnUntil) return;

    // hit first consumes armor, then hp
    let left = dmg;

    if (player.armor > 0) {
      const used = Math.min(player.armor, left);
      player.armor -= used;
      left -= used;

      // recompute plates as "ceil(armor/plateValue)"
      player.plates = Math.ceil(player.armor / player.plateValue);
      if (player.plates < 0) player.plates = 0;
    }

    if (left > 0) {
      player.hp -= left;
    }

    player.invulnUntil = t + 300; // 300ms i-frames

    if (player.hp <= 0) {
      // end run
      player.hp = 0;
      GAME.running = false;
    }
  }

  function buyPlate() {
    if (player.plates >= player.platesMax) return false;
    if (GAME.coins < player.plateCost) return false;

    GAME.coins -= player.plateCost;
    player.plates += 1;
    player.armor = clamp(player.plates * player.plateValue, 0, player.armorMax);
    return true;
  }

  // ---------- BULLETS ----------
  const bullets = [];

  function shoot(dx, dy) {
    const len = Math.hypot(dx, dy) || 1;
    bullets.push({
      x: player.x,
      y: player.y,
      vx: (dx / len) * 8.5,
      vy: (dy / len) * 8.5,
      life: 60,
    });
  }

  // ---------- ZOMBIES ----------
  const zombies = [];

  function spawnZombie() {
    if (!canvas) return;
    const cw = canvas.width / DPR;
    const ch = canvas.height / DPR;

    const edge = Math.floor(Math.random() * 4);
    let x, y;
    if (edge === 0) { x = -20; y = Math.random() * ch; }
    if (edge === 1) { x = cw + 20; y = Math.random() * ch; }
    if (edge === 2) { y = -20; x = Math.random() * cw; }
    if (edge === 3) { y = ch + 20; x = Math.random() * cw; }

    const baseHp = 30 + GAME.wave * 6;
    const baseSpd = 1.05 + GAME.wave * 0.06;

    zombies.push({
      x, y,
      r: 16,
      hp: baseHp,
      speed: baseSpd,
      touchDmg: 10 + Math.floor(GAME.wave * 0.6),
      dead: false,
    });
  }

  // ---------- MOBILE CONTROLS (iOS-proof) ----------
  // Left thumb = joystick (movement)
  // Right thumb = fire button (optional, but comfy)
  const stick = {
    pointerId: null,
    active: false,
    baseX: 0, baseY: 0,
    dx: 0, dy: 0,
    radius: 54,
  };

  const fire = {
    pointerId: null,
    active: false,
    x: 0, y: 0,
    r: 44,
  };

  function inLeftZone(x) {
    return x < window.innerWidth * 0.5;
  }
  function inRightZone(x) {
    return x >= window.innerWidth * 0.5;
  }

  function onPointerDown(e) {
    if (!GAME.running) return;
    if (!canvas) return;

    // Important for iOS: stop page gestures
    e.preventDefault();

    const x = e.clientX;
    const y = e.clientY;

    // Assign joystick pointer (left side)
    if (!stick.active && inLeftZone(x)) {
      stick.active = true;
      stick.pointerId = e.pointerId;
      stick.baseX = x;
      stick.baseY = y;
      stick.dx = 0;
      stick.dy = 0;
      try { canvas.setPointerCapture(e.pointerId); } catch {}
      return;
    }

    // Assign fire pointer (right side)
    if (!fire.active && inRightZone(x)) {
      fire.active = true;
      fire.pointerId = e.pointerId;
      fire.x = x;
      fire.y = y;
      try { canvas.setPointerCapture(e.pointerId); } catch {}
      return;
    }
  }

  function onPointerMove(e) {
    if (!GAME.running) return;
    if (!canvas) return;
    e.preventDefault();

    const x = e.clientX;
    const y = e.clientY;

    if (stick.active && e.pointerId === stick.pointerId) {
      let dx = x - stick.baseX;
      let dy = y - stick.baseY;
      const len = Math.hypot(dx, dy);
      if (len > stick.radius) {
        dx = dx * (stick.radius / len);
        dy = dy * (stick.radius / len);
      }
      stick.dx = dx;
      stick.dy = dy;
      return;
    }

    if (fire.active && e.pointerId === fire.pointerId) {
      fire.x = x;
      fire.y = y;
      return;
    }
  }

  function onPointerUp(e) {
    if (!canvas) return;
    e.preventDefault();

    if (stick.active && e.pointerId === stick.pointerId) {
      stick.active = false;
      stick.pointerId = null;
      stick.dx = 0;
      stick.dy = 0;
      try { canvas.releasePointerCapture(e.pointerId); } catch {}
      return;
    }

    if (fire.active && e.pointerId === fire.pointerId) {
      fire.active = false;
      fire.pointerId = null;
      try { canvas.releasePointerCapture(e.pointerId); } catch {}
      return;
    }
  }

  function bindControls() {
    if (!canvas) return;

    // Pointer events are the most stable on iOS WebView
    canvas.addEventListener("pointerdown", onPointerDown, { passive: false });
    canvas.addEventListener("pointermove", onPointerMove, { passive: false });
    canvas.addEventListener("pointerup", onPointerUp, { passive: false });
    canvas.addEventListener("pointercancel", onPointerUp, { passive: false });

    // Disable default gestures
    canvas.addEventListener("contextmenu", (e) => e.preventDefault());
  }

  function unbindControls() {
    if (!canvas) return;
    canvas.removeEventListener("pointerdown", onPointerDown);
    canvas.removeEventListener("pointermove", onPointerMove);
    canvas.removeEventListener("pointerup", onPointerUp);
    canvas.removeEventListener("pointercancel", onPointerUp);
  }

  // ---------- DRAW HOOKS (assets system will override these) ----------
  // Default simple vector render
  function defaultDrawPlayer(ctx2, p) {
    ctx2.fillStyle = "#4af";
    ctx2.beginPath();
    ctx2.arc(p.x, p.y, p.r, 0, Math.PI * 2);
    ctx2.fill();

    // gun direction
    ctx2.strokeStyle = "rgba(255,255,255,.9)";
    ctx2.lineWidth = 3;
    ctx2.beginPath();
    ctx2.moveTo(p.x, p.y);
    ctx2.lineTo(p.x + p.dirX * 20, p.y + p.dirY * 20);
    ctx2.stroke();
  }

  function defaultDrawZombie(ctx2, z) {
    ctx2.fillStyle = "#3f3";
    ctx2.beginPath();
    ctx2.arc(z.x, z.y, z.r, 0, Math.PI * 2);
    ctx2.fill();
  }

  // These will be overridden by zombies.assets.js
  const core = {
    _drawPlayer: (ctx2, p) => defaultDrawPlayer(ctx2, p),
    _drawZombie: (ctx2, z) => defaultDrawZombie(ctx2, z),
  };

  // ---------- MAP (2 simple themes now; real tiles later) ----------
  let currentMap = "Ashes"; // or Astra

  function drawMap(ctx2) {
    if (!canvas) return;
    const w = canvas.width / DPR;
    const h = canvas.height / DPR;

    // premium gradient base
    const g = ctx2.createLinearGradient(0, 0, w, h);
    if (currentMap === "Ashes") {
      g.addColorStop(0, "#070a10");
      g.addColorStop(1, "#14080a");
    } else {
      g.addColorStop(0, "#050814");
      g.addColorStop(1, "#071322");
    }
    ctx2.fillStyle = g;
    ctx2.fillRect(0, 0, w, h);

    // subtle grid
    ctx2.strokeStyle = "rgba(255,255,255,.05)";
    ctx2.lineWidth = 1;
    const step = 40;
    for (let x = 0; x < w; x += step) {
      ctx2.beginPath();
      ctx2.moveTo(x, 0);
      ctx2.lineTo(x, h);
      ctx2.stroke();
    }
    for (let y = 0; y < h; y += step) {
      ctx2.beginPath();
      ctx2.moveTo(0, y);
      ctx2.lineTo(w, y);
      ctx2.stroke();
    }
  }

  // ---------- GAME LOOP ----------
  function resetRun(mode) {
    GAME.mode = mode;
    GAME.running = true;
    GAME.startedAt = nowMs();
    GAME.time = 0;
    GAME.wave = 1;
    GAME.kills = 0;
    GAME.coins = 0;

    player.hp = 100;
    player.armor = 0;
    player.plates = 0;
    player.level = 1;
    player.xp = 0;
    player.xpNext = 50;
    player.fireCooldown = 0;

    bullets.length = 0;
    zombies.length = 0;

    // center
    if (canvas) {
      player.x = (canvas.width / DPR) * 0.5;
      player.y = (canvas.height / DPR) * 0.5;
    }
  }

  function update() {
    if (!GAME.running) return;
    if (!canvas) return;

    GAME.time++;

    const cw = canvas.width / DPR;
    const ch = canvas.height / DPR;

    // Movement from stick
    player.dirX = stick.dx / stick.radius;
    player.dirY = stick.dy / stick.radius;

    const spd = player.speed;
    player.x += player.dirX * spd;
    player.y += player.dirY * spd;
    player.x = clamp(player.x, 18, cw - 18);
    player.y = clamp(player.y, 18, ch - 18);

    // Fire direction:
    // - if fire active: shoot towards fire pointer
    // - else: auto-fire in move direction (like before)
    let fx = 0, fy = 0;
    if (fire.active) {
      fx = fire.x - player.x;
      fy = fire.y - player.y;
    } else {
      fx = player.dirX;
      fy = player.dirY;
    }

    // Shooting cadence
    const wantsShoot = (fire.active && (fx || fy)) || (!fire.active && (player.dirX || player.dirY));
    if (wantsShoot) {
      if (player.fireCooldown-- <= 0) {
        shoot(fx, fy);
        player.fireCooldown = (GAME.mode === "ARCADE") ? 10 : 16;
      }
    } else {
      player.fireCooldown = Math.min(player.fireCooldown, 1);
    }

    // Bullets
    for (let i = bullets.length - 1; i >= 0; i--) {
      const b = bullets[i];
      b.x += b.vx;
      b.y += b.vy;
      b.life--;
      if (b.life <= 0) bullets.splice(i, 1);
    }

    // Zombies chase
    for (let i = 0; i < zombies.length; i++) {
      const z = zombies[i];
      const dx = player.x - z.x;
      const dy = player.y - z.y;
      const len = Math.hypot(dx, dy) || 1;
      z.x += (dx / len) * z.speed;
      z.y += (dy / len) * z.speed;
    }

    // Bullet hits
    for (let zi = 0; zi < zombies.length; zi++) {
      const z = zombies[zi];
      if (z.dead) continue;

      for (let bi = 0; bi < bullets.length; bi++) {
        const b = bullets[bi];
        if (b.life <= 0) continue;

        if (dist(z.x, z.y, b.x, b.y) < z.r + 2) {
          z.hp -= 20;
          b.life = 0;

          if (z.hp <= 0) {
            z.dead = true;
            GAME.kills++;
            GAME.coins += 1;

            // XP reward
            addXP(8 + Math.floor(GAME.wave * 0.5));
          }
        }
      }
    }

    // Zombie touch damage
    for (let zi = 0; zi < zombies.length; zi++) {
      const z = zombies[zi];
      if (z.dead) continue;

      if (dist(z.x, z.y, player.x, player.y) < (z.r + player.r) * 0.9) {
        applyDamage(z.touchDmg);
      }
    }

    // Cleanup dead zombies
    for (let i = zombies.length - 1; i >= 0; i--) {
      if (zombies[i].dead) zombies.splice(i, 1);
    }

    // Wave logic
    const cap = GAME.spawnCapBase + GAME.wave;
    if (zombies.length < cap) spawnZombie();

    if (GAME.kills >= GAME.wave * GAME.waveKills) {
      GAME.wave++;
      // small heal reward
      player.hp = Math.min(130, player.hp + 5);
    }

    // Auto plate in roguelike if enough coins (optional “lux”)
    if (GAME.mode === "ROGUELIKE") {
      // super gentle auto-buy if armor empty and you have coins
      if (player.plates < player.platesMax && player.armor <= 0 && GAME.coins >= player.plateCost) {
        buyPlate();
      }
    }
  }

  function drawHUD(ctx2) {
    // HUD
    ctx2.fillStyle = "rgba(255,255,255,.92)";
    ctx2.font = "14px ui-monospace, Menlo, monospace";

    const mode = GAME.mode;
    const line1 = `MODE: ${mode}   MAP: ${currentMap}`;
    const line2 = `WAVE: ${GAME.wave}   KILLS: ${GAME.kills}   💰: ${GAME.coins}`;
    const armorPlates = "🛡".repeat(player.plates) + "▫️".repeat(Math.max(0, player.platesMax - player.plates));
    const line3 = `HP: ${Math.floor(player.hp)}   ARMOR: ${Math.floor(player.armor)}/${player.armorMax}  ${armorPlates}`;
    const line4 = `LVL: ${player.level}   XP: ${player.xp}/${player.xpNext}`;

    ctx2.fillText(line1, 12, 22);
    ctx2.fillText(line2, 12, 42);
    ctx2.fillText(line3, 12, 62);
    ctx2.fillText(line4, 12, 82);

    if (!GAME.running && player.hp <= 0) {
      ctx2.fillStyle = "rgba(255,60,60,.95)";
      ctx2.font = "20px ui-monospace, Menlo, monospace";
      ctx2.fillText("YOU DIED — tap Stop / restart", 12, 120);
    }
  }

  function drawControls(ctx2) {
    // Joystick render (left)
    if (stick.active) {
      ctx2.strokeStyle = "rgba(255,255,255,.28)";
      ctx2.lineWidth = 2;
      ctx2.beginPath();
      ctx2.arc(stick.baseX, stick.baseY, stick.radius, 0, Math.PI * 2);
      ctx2.stroke();

      ctx2.fillStyle = "rgba(255,255,255,.45)";
      ctx2.beginPath();
      ctx2.arc(stick.baseX + stick.dx, stick.baseY + stick.dy, 15, 0, Math.PI * 2);
      ctx2.fill();
    } else {
      // subtle hint zone
      ctx2.fillStyle = "rgba(255,255,255,.06)";
      ctx2.beginPath();
      ctx2.arc(72, (canvas.height / DPR) - 92, 48, 0, Math.PI * 2);
      ctx2.fill();
    }

    // Fire button (right)
    const w = canvas.width / DPR;
    const fx = w - 72;
    const fy = (canvas.height / DPR) - 92;

    ctx2.strokeStyle = fire.active ? "rgba(255,255,255,.55)" : "rgba(255,255,255,.22)";
    ctx2.lineWidth = 3;
    ctx2.beginPath();
    ctx2.arc(fx, fy, 44, 0, Math.PI * 2);
    ctx2.stroke();

    ctx2.fillStyle = fire.active ? "rgba(255,255,255,.18)" : "rgba(255,255,255,.08)";
    ctx2.beginPath();
    ctx2.arc(fx, fy, 44, 0, Math.PI * 2);
    ctx2.fill();

    ctx2.fillStyle = "rgba(255,255,255,.82)";
    ctx2.font = "12px ui-monospace, Menlo, monospace";
    ctx2.fillText("FIRE", fx - 16, fy + 4);
  }

  function draw() {
    if (!ctx || !canvas) return;

    // map bg
    drawMap(ctx);

    // player (through hook)
    core._drawPlayer(ctx, player);

    // zombies (through hook)
    for (let i = 0; i < zombies.length; i++) {
      core._drawZombie(ctx, zombies[i]);
    }

    // bullets
    ctx.fillStyle = "#fff";
    for (let i = 0; i < bullets.length; i++) {
      const b = bullets[i];
      ctx.fillRect(b.x - 2, b.y - 2, 4, 4);
    }

    // controls + hud on top
    drawControls(ctx);
    drawHUD(ctx);
  }

  function loop() {
    if (GAME.running) update();
    draw();
    requestAnimationFrame(loop);
  }

  // ---------- PUBLIC API ----------
  window.BCO_ZOMBIES = {
    // draw hooks for assets system
    _drawPlayer: core._drawPlayer,
    _drawZombie: core._drawZombie,

    // assets system will overwrite these references
    setDrawHooks(drawPlayer, drawZombie) {
      if (typeof drawPlayer === "function") core._drawPlayer = drawPlayer;
      if (typeof drawZombie === "function") core._drawZombie = drawZombie;
    },

    start(mode = "ARCADE", opts = {}) {
      ensureOverlay();
      showOverlay();
      bindControls();

      GAME.mode = (mode === "ROGUELIKE") ? "ROGUELIKE" : "ARCADE";
      currentMap = (opts.map === "Astra") ? "Astra" : "Ashes";

      resetRun(GAME.mode);
      GAME.running = true;
      window.__BCO_ZOMBIES_OK__ = true;

      // expose flags
      window.__BCO_ZOMBIES_OK__ = true;
      window.__BCO_ZOMBIES_OK__ = true;
    },

    stop() {
      GAME.running = false;
      unbindControls();
      hideOverlay();
    },

    // armor actions (for shop buttons later)
    buyPlate() {
      return buyPlate();
    },

    // stats for app.js to read and отправлять game_result
    getState() {
      const durationSec = Math.floor((nowMs() - GAME.startedAt) / 1000);
      return {
        mode: GAME.mode,
        map: currentMap,
        wave: GAME.wave,
        kills: GAME.kills,
        coins: GAME.coins,
        duration: durationSec,

        player: {
          hp: player.hp,
          armor: player.armor,
          armorMax: player.armorMax,
          plates: player.plates,
          platesMax: player.platesMax,
          level: player.level,
          xp: player.xp,
          xpNext: player.xpNext,
        }
      };
    },

    // allow changing map without restart if needed
    setMap(name) {
      currentMap = (name === "Astra") ? "Astra" : "Ashes";
    }
  };

  // Start render loop always (lightweight)
  loop();
})();
