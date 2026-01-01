/* =========================================================
   BLACK CROWN OPS — ZOMBIES GAME v1 (FOUNDATION)
   File: app/webapp/static/zombies.js
   ========================================================= */

(() => {
  "use strict";

  // ---------- GLOBAL ----------
  window.__BCO_ZOMBIES_OK__ = false;

  const DPR = Math.min(2, window.devicePixelRatio || 1);

  // ---------- FULLSCREEN CANVAS ----------
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  document.body.appendChild(canvas);

  canvas.style.position = "fixed";
  canvas.style.left = "0";
  canvas.style.top = "0";
  canvas.style.width = "100vw";
  canvas.style.height = "100vh";
  canvas.style.zIndex = "9999";
  canvas.style.background = "#05070c";

  function resize() {
    canvas.width = Math.floor(window.innerWidth * DPR);
    canvas.height = Math.floor(window.innerHeight * DPR);
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  }
  window.addEventListener("resize", resize);
  resize();

  // ---------- GAME STATE ----------
  const GAME = {
    mode: "ARCADE", // or ROGUELIKE
    running: false,
    time: 0,
    wave: 1,
    kills: 0,
    coins: 0,
  };

  // ---------- PLAYER ----------
  const player = {
    x: canvas.width / (2 * DPR),
    y: canvas.height / (2 * DPR),
    r: 18,
    speed: 3.2,
    hp: 100,
    level: 1,
    dirX: 0,
    dirY: 0,
    fireCooldown: 0,
  };

  // ---------- BULLETS ----------
  const bullets = [];

  function shoot(dx, dy) {
    const len = Math.hypot(dx, dy) || 1;
    bullets.push({
      x: player.x,
      y: player.y,
      vx: (dx / len) * 8,
      vy: (dy / len) * 8,
      life: 60,
    });
  }

  // ---------- ZOMBIES ----------
  const zombies = [];

  function spawnZombie() {
    const edge = Math.floor(Math.random() * 4);
    let x, y;
    if (edge === 0) { x = 0; y = Math.random() * canvas.height / DPR; }
    if (edge === 1) { x = canvas.width / DPR; y = Math.random() * canvas.height / DPR; }
    if (edge === 2) { y = 0; x = Math.random() * canvas.width / DPR; }
    if (edge === 3) { y = canvas.height / DPR; x = Math.random() * canvas.width / DPR; }

    zombies.push({
      x, y,
      r: 16,
      hp: 30 + GAME.wave * 5,
      speed: 1 + GAME.wave * 0.05,
    });
  }

  // ---------- JOYSTICK ----------
  const joystick = {
    active: false,
    x: 0, y: 0,
    dx: 0, dy: 0,
    radius: 50,
  };

  canvas.addEventListener("touchstart", e => {
    const t = e.touches[0];
    joystick.active = true;
    joystick.x = t.clientX;
    joystick.y = t.clientY;
  });

  canvas.addEventListener("touchmove", e => {
    if (!joystick.active) return;
    const t = e.touches[0];
    joystick.dx = t.clientX - joystick.x;
    joystick.dy = t.clientY - joystick.y;
    const len = Math.hypot(joystick.dx, joystick.dy);
    if (len > joystick.radius) {
      joystick.dx *= joystick.radius / len;
      joystick.dy *= joystick.radius / len;
    }
  });

  canvas.addEventListener("touchend", () => {
    joystick.active = false;
    joystick.dx = joystick.dy = 0;
  });

  // ---------- GAME LOOP ----------
  function update() {
    if (!GAME.running) return;

    GAME.time++;

    // Player movement
    player.dirX = joystick.dx / joystick.radius;
    player.dirY = joystick.dy / joystick.radius;
    player.x += player.dirX * player.speed;
    player.y += player.dirY * player.speed;

    // Shooting
    if (player.fireCooldown-- <= 0 && (player.dirX || player.dirY)) {
      shoot(player.dirX, player.dirY);
      player.fireCooldown = GAME.mode === "ARCADE" ? 10 : 18;
    }

    // Bullets
    bullets.forEach(b => {
      b.x += b.vx;
      b.y += b.vy;
      b.life--;
    });

    // Zombies
    zombies.forEach(z => {
      const dx = player.x - z.x;
      const dy = player.y - z.y;
      const len = Math.hypot(dx, dy) || 1;
      z.x += (dx / len) * z.speed;
      z.y += (dy / len) * z.speed;
    });

    // Collisions
    zombies.forEach(z => {
      bullets.forEach(b => {
        if (Math.hypot(z.x - b.x, z.y - b.y) < z.r) {
          z.hp -= 20;
          b.life = 0;
          if (z.hp <= 0) {
            GAME.kills++;
            GAME.coins += 1;
            z.dead = true;
          }
        }
      });
    });

    // Cleanup
    for (let i = zombies.length - 1; i >= 0; i--) {
      if (zombies[i].dead) zombies.splice(i, 1);
    }
    for (let i = bullets.length - 1; i >= 0; i--) {
      if (bullets[i].life <= 0) bullets.splice(i, 1);
    }

    // Spawn logic
    if (zombies.length < 3 + GAME.wave) spawnZombie();
    if (GAME.kills >= GAME.wave * 10) {
      GAME.wave++;
    }
  }

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Player
    ctx.fillStyle = "#4af";
    ctx.beginPath();
    ctx.arc(player.x, player.y, player.r, 0, Math.PI * 2);
    ctx.fill();

    // Zombies
    ctx.fillStyle = "#3f3";
    zombies.forEach(z => {
      ctx.beginPath();
      ctx.arc(z.x, z.y, z.r, 0, Math.PI * 2);
      ctx.fill();
    });

    // Bullets
    ctx.fillStyle = "#fff";
    bullets.forEach(b => {
      ctx.fillRect(b.x - 2, b.y - 2, 4, 4);
    });

    // HUD
    ctx.fillStyle = "#fff";
    ctx.font = "14px monospace";
    ctx.fillText(`MODE: ${GAME.mode}`, 10, 20);
    ctx.fillText(`WAVE: ${GAME.wave}`, 10, 40);
    ctx.fillText(`KILLS: ${GAME.kills}`, 10, 60);
    ctx.fillText(`HP: ${player.hp}`, 10, 80);

    // Joystick
    if (joystick.active) {
      ctx.strokeStyle = "rgba(255,255,255,.3)";
      ctx.beginPath();
      ctx.arc(joystick.x, joystick.y, joystick.radius, 0, Math.PI * 2);
      ctx.stroke();

      ctx.fillStyle = "rgba(255,255,255,.5)";
      ctx.beginPath();
      ctx.arc(joystick.x + joystick.dx, joystick.y + joystick.dy, 15, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  function loop() {
    update();
    draw();
    requestAnimationFrame(loop);
  }

  // ---------- PUBLIC API ----------
  window.BCO_ZOMBIES = {
    start(mode = "ARCADE") {
      GAME.mode = mode;
      GAME.running = true;
      window.__BCO_ZOMBIES_OK__ = true;
    },
    stop() {
      GAME.running = false;
    },
  };

  loop();
})();
