/* =========================================================
   BLACK CROWN OPS — ZOMBIES RENDER  [LUX]
   File: app/webapp/static/zombies.render.js
   Provides: window.BCO_ZOMBIES_RENDER
   Notes:
     - Works with your current CORE + GAME overlay
     - Supports:
         • Map floor vibe + walls visualization (from zombies.maps.js)
         • Boss telegraphs + projectiles (from zombies.bosses.js LUX via CORE._bossRT)
         • Boss HP bars + elite styling
         • Optional pickups/loot draw if CORE.state.pickups exists (future-proof)
     - Uses sprites if BCO_ZOMBIES_ASSETS is present; otherwise premium vector fallback
   ========================================================= */
(() => {
  "use strict";

  const ASSETS = () => window.BCO_ZOMBIES_ASSETS || null;

  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const len = (x, y) => Math.hypot(x, y) || 0;

  const RENDER = {
    render(ctx, CORE, input, view) {
      const S = CORE.state;
      const w = view.w, h = view.h;

      ctx.clearRect(0, 0, w, h);

      // -------------------------------------------------------
      // BACKGROUND (premium vignette + subtle grain)
      // -------------------------------------------------------
      drawBackdrop(ctx, w, h);

      // world transform (camera centered)
      const camX = S.camX, camY = S.camY;

      // map
      const map = safeMap(CORE);

      // -------------------------------------------------------
      // WORLD LAYER
      // -------------------------------------------------------
      ctx.save();
      ctx.translate(w / 2, h / 2);
      ctx.translate(-camX, -camY);

      // floor / tiles
      drawFloor(ctx, camX, camY, w, h, map);

      // walls (visual + premium glow)
      if (map?.walls?.length) drawWalls(ctx, map.walls);

      // telegraphs (boss windups)
      drawTelegraphs(ctx, CORE);

      // pickups / loot (future-proof)
      drawPickups(ctx, CORE);

      // bullets (player)
      drawBullets(ctx, S.bullets);

      // boss projectiles (spitter spit)
      drawBossProjectiles(ctx, CORE);

      // zombies (includes bosses inside S.zombies)
      drawZombies(ctx, CORE, S.zombies);

      // player
      drawPlayer(ctx, CORE, input);

      ctx.restore();

      // -------------------------------------------------------
      // SCREEN-SPACE UI
      // -------------------------------------------------------
      drawArenaHint(ctx, w, h, CORE, map);
      drawReticle(ctx, CORE, input, view);
      drawBossHpBars(ctx, CORE, view);
    }
  };

  // =========================================================
  // BACKDROP
  // =========================================================
  function drawBackdrop(ctx, w, h) {
    // vignette
    ctx.save();
    const g = ctx.createRadialGradient(w * 0.5, h * 0.35, 10, w * 0.5, h * 0.55, Math.max(w, h) * 0.9);
    g.addColorStop(0, "rgba(255,255,255,.05)");
    g.addColorStop(0.35, "rgba(0,0,0,.28)");
    g.addColorStop(1, "rgba(0,0,0,.76)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);

    // subtle scanlines
    ctx.globalAlpha = 0.06;
    ctx.fillStyle = "#fff";
    const step = 3;
    for (let y = 0; y < h; y += step) ctx.fillRect(0, y, w, 1);

    ctx.restore();
  }

  // =========================================================
  // MAP HELPERS
  // =========================================================
  function safeMap(CORE) {
    try {
      const MAPS = window.BCO_ZOMBIES_MAPS;
      return MAPS?.get?.(CORE?.meta?.map) || null;
    } catch {
      return null;
    }
  }

  function drawFloor(ctx, camX, camY, w, h, map) {
    // Premium: dotted + micro-grid, adapts to camera, stays subtle.
    const step = 64;
    const minX = (camX - w / 2 - 240) | 0;
    const minY = (camY - h / 2 - 240) | 0;
    const maxX = (camX + w / 2 + 240) | 0;
    const maxY = (camY + h / 2 + 240) | 0;

    ctx.save();
    ctx.globalAlpha = 0.16;
    ctx.fillStyle = "#ffffff";

    // dots
    for (let x = Math.floor(minX / step) * step; x < maxX; x += step) {
      for (let y = Math.floor(minY / step) * step; y < maxY; y += step) {
        ctx.fillRect(x + 1, y + 1, 1, 1);
      }
    }

    // faint grid lines
    ctx.globalAlpha = 0.06;
    ctx.strokeStyle = "rgba(255,255,255,.55)";
    ctx.lineWidth = 1;

    for (let x = Math.floor(minX / step) * step; x < maxX; x += step) {
      ctx.beginPath();
      ctx.moveTo(x, minY);
      ctx.lineTo(x, maxY);
      ctx.stroke();
    }
    for (let y = Math.floor(minY / step) * step; y < maxY; y += step) {
      ctx.beginPath();
      ctx.moveTo(minX, y);
      ctx.lineTo(maxX, y);
      ctx.stroke();
    }

    // subtle map tint per map
    const name = String(map?.name || "");
    ctx.globalAlpha = 0.10;
    if (name.toLowerCase().includes("astra")) ctx.fillStyle = "rgba(120,180,255,.22)";
    else ctx.fillStyle = "rgba(120,255,180,.16)";
    ctx.fillRect(minX, minY, (maxX - minX), (maxY - minY));

    ctx.restore();
  }

  function drawWalls(ctx, walls) {
    ctx.save();

    // glow underlay
    ctx.globalAlpha = 0.22;
    ctx.fillStyle = "rgba(255,255,255,.18)";
    for (const r of walls) {
      const x = r.x - r.w / 2;
      const y = r.y - r.h / 2;
      ctx.fillRect(x - 3, y - 3, r.w + 6, r.h + 6);
    }

    // main fill
    ctx.globalAlpha = 0.36;
    ctx.fillStyle = "rgba(0,0,0,.55)";
    for (const r of walls) {
      const x = r.x - r.w / 2;
      const y = r.y - r.h / 2;
      ctx.fillRect(x, y, r.w, r.h);
    }

    // edges
    ctx.globalAlpha = 0.42;
    ctx.strokeStyle = "rgba(255,255,255,.25)";
    ctx.lineWidth = 2;
    for (const r of walls) {
      const x = r.x - r.w / 2;
      const y = r.y - r.h / 2;
      roundRect(ctx, x, y, r.w, r.h, 10);
      ctx.stroke();
    }

    ctx.restore();
  }

  function roundRect(ctx, x, y, w, h, r) {
    const rr = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + rr, y);
    ctx.arcTo(x + w, y, x + w, y + h, rr);
    ctx.arcTo(x + w, y + h, x, y + h, rr);
    ctx.arcTo(x, y + h, x, y, rr);
    ctx.arcTo(x, y, x + w, y, rr);
    ctx.closePath();
  }

  // =========================================================
  // ENTITIES
  // =========================================================
  function drawBullets(ctx, bullets) {
    if (!bullets || !bullets.length) return;

    ctx.save();
    ctx.globalAlpha = 0.92;

    for (const b of bullets) {
      // premium bullet: core + glow streak
      ctx.fillStyle = "rgba(255,255,255,.88)";
      ctx.beginPath();
      ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2);
      ctx.fill();

      // tiny forward streak (based on velocity if exists)
      const vx = Number(b.vx || 0);
      const vy = Number(b.vy || 0);
      const L = len(vx, vy) || 1;
      const nx = vx / L, ny = vy / L;

      ctx.globalAlpha = 0.22;
      ctx.strokeStyle = "rgba(255,255,255,.55)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(b.x - nx * 10, b.y - ny * 10);
      ctx.lineTo(b.x + nx * 8, b.y + ny * 8);
      ctx.stroke();
      ctx.globalAlpha = 0.92;
    }

    ctx.restore();
  }

  function drawZombies(ctx, CORE, zombies) {
    if (!zombies || !zombies.length) return;

    const A = ASSETS();

    for (const z of zombies) {
      const kind = String(z.kind || "zombie");

      // sprite path
      if (A?.drawZombie) {
        try {
          A.drawZombie(ctx, z.x, z.y, { zombie: kind });
          // add boss ring overlay
          if (kind === "boss_brute" || kind === "boss_spitter") drawBossAura(ctx, z);
          continue;
        } catch {}
      }

      // vector fallback
      if (kind === "boss_brute" || kind === "boss_spitter") {
        fallbackBoss(ctx, z.x, z.y, z.r || 22, kind);
      } else {
        fallbackZombie(ctx, z.x, z.y, z.r || 16);
      }
    }
  }

  function drawBossAura(ctx, z) {
    ctx.save();
    ctx.translate(z.x, z.y);

    ctx.globalAlpha = 0.20;
    ctx.strokeStyle = "rgba(255,255,255,.45)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(0, 0, (z.r || 24) + 10, 0, Math.PI * 2);
    ctx.stroke();

    ctx.globalAlpha = 0.08;
    ctx.lineWidth = 8;
    ctx.beginPath();
    ctx.arc(0, 0, (z.r || 24) + 18, 0, Math.PI * 2);
    ctx.stroke();

    ctx.restore();
  }

  function drawPlayer(ctx, CORE, input) {
    const S = CORE.state;
    const A = ASSETS();

    if (A?.drawPlayer) {
      try {
        A.drawPlayer(ctx, S.player.x, S.player.y, input.aimX, input.aimY, {
          player: CORE.meta.character,
          skin: CORE.meta.skin
        });
        return;
      } catch {}
    }
    fallbackPlayer(ctx, S.player.x, S.player.y, input.aimX, input.aimY);
  }

  // =========================================================
  // BOSSES: TELEGRAPHS + PROJECTILES + HP BARS
  // =========================================================
  function drawTelegraphs(ctx, CORE) {
    const rt = CORE?._bossRT;
    const list = rt?.telegraphs || null;
    if (!Array.isArray(list) || !list.length) return;

    const tms = performance.now();

    ctx.save();
    for (const tg of list) {
      if (!tg) continue;
      const until = Number(tg.until || 0);
      const left = clamp((until - tms) / 700, 0, 1);

      if (tg.kind === "slam") {
        // brute slam circle
        const r = Number(tg.r || 120);
        ctx.globalAlpha = 0.10 + (1 - left) * 0.18;
        ctx.strokeStyle = "rgba(255,255,255,.65)";
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(tg.x, tg.y, r, 0, Math.PI * 2);
        ctx.stroke();

        // inner pulse
        ctx.globalAlpha = 0.06 + (1 - left) * 0.10;
        ctx.fillStyle = "rgba(255,255,255,.35)";
        ctx.beginPath();
        ctx.arc(tg.x, tg.y, r * (0.86 + (1 - left) * 0.12), 0, Math.PI * 2);
        ctx.fill();
      } else if (tg.kind === "spit") {
        // spitter aim line hint
        ctx.globalAlpha = 0.22;
        ctx.strokeStyle = "rgba(255,255,255,.35)";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(tg.x, tg.y, 14, 0, Math.PI * 2);
        ctx.stroke();
      }
    }
    ctx.restore();
  }

  function drawBossProjectiles(ctx, CORE) {
    const rt = CORE?._bossRT;
    const list = rt?.projectiles || null;
    if (!Array.isArray(list) || !list.length) return;

    ctx.save();
    for (const p of list) {
      // premium spit ball
      ctx.globalAlpha = 0.88;
      ctx.fillStyle = "rgba(255,255,255,.72)";
      ctx.beginPath();
      ctx.arc(p.x, p.y, (p.r || 7), 0, Math.PI * 2);
      ctx.fill();

      ctx.globalAlpha = 0.14;
      ctx.strokeStyle = "rgba(255,255,255,.55)";
      ctx.lineWidth = 5;
      ctx.beginPath();
      ctx.arc(p.x, p.y, (p.r || 7) + 8, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawBossHpBars(ctx, CORE, view) {
    const S = CORE?.state;
    if (!S?.zombies?.length) return;

    // show only if any boss exists
    let bosses = null;
    for (const z of S.zombies) {
      if (z && (z.kind === "boss_brute" || z.kind === "boss_spitter")) {
        (bosses || (bosses = [])).push(z);
      }
    }
    if (!bosses || !bosses.length) return;

    const w = view.w;
    const baseY = 84; // under top HUD in overlay
    const barW = Math.min(420, Math.floor(w * 0.62));
    const x0 = Math.floor((w - barW) / 2);

    const maxShow = 2;
    const show = bosses.slice(0, maxShow);

    ctx.save();
    for (let i = 0; i < show.length; i++) {
      const b = show[i];
      const y = baseY + i * 22;

      const hpMax = Math.max(1, Number(b.hpMax || b.hp || 1));
      const hp = clamp(Number(b.hp || 0) / hpMax, 0, 1);

      // container
      ctx.globalAlpha = 0.60;
      ctx.fillStyle = "rgba(0,0,0,.40)";
      roundRect(ctx, x0, y, barW, 12, 999);
      ctx.fill();

      // fill
      ctx.globalAlpha = 0.86;
      ctx.fillStyle = (b.kind === "boss_spitter")
        ? "rgba(180,220,255,.75)"
        : "rgba(220,255,200,.70)";
      roundRect(ctx, x0 + 1, y + 1, Math.max(2, Math.floor((barW - 2) * hp)), 10, 999);
      ctx.fill();

      // outline
      ctx.globalAlpha = 0.30;
      ctx.strokeStyle = "rgba(255,255,255,.35)";
      ctx.lineWidth = 1;
      roundRect(ctx, x0, y, barW, 12, 999);
      ctx.stroke();

      // label
      ctx.globalAlpha = 0.70;
      ctx.fillStyle = "rgba(255,255,255,.85)";
      ctx.font = "800 10px Inter,system-ui";
      const name = (b.kind === "boss_spitter") ? "SPITTER" : "BRUTE";
      ctx.fillText(name, x0 + 6, y + 10);
    }
    ctx.restore();
  }

  // =========================================================
  // OPTIONAL: PICKUPS / LOOT (future)
  // =========================================================
  function drawPickups(ctx, CORE) {
    const S = CORE?.state;
    const list = S?.pickups || S?.loot || null;
    if (!Array.isArray(list) || !list.length) return;

    ctx.save();
    for (const it of list) {
      const x = Number(it.x || 0);
      const y = Number(it.y || 0);
      const r = Number(it.r || 10);

      // rarity color mapping (kept subtle)
      const rar = String(it.rarity || "common").toLowerCase();
      let c = "rgba(255,255,255,.70)";
      if (rar.includes("uncommon")) c = "rgba(160,255,180,.70)";
      else if (rar.includes("rare")) c = "rgba(160,200,255,.75)";
      else if (rar.includes("epic")) c = "rgba(210,170,255,.75)";
      else if (rar.includes("legend")) c = "rgba(255,210,140,.78)";

      ctx.globalAlpha = 0.22;
      ctx.fillStyle = c;
      ctx.beginPath();
      ctx.arc(x, y, r + 10, 0, Math.PI * 2);
      ctx.fill();

      ctx.globalAlpha = 0.86;
      ctx.fillStyle = c;
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  // =========================================================
  // SCREEN SPACE: arena hint + reticle
  // =========================================================
  function drawArenaHint(ctx, w, h, CORE, map) {
    // Keep the old ring vibe but make it smarter:
    // If map exists, show a subtle "compass ring" around player.
    ctx.save();
    ctx.translate(w / 2, h / 2);

    ctx.globalAlpha = 0.10;
    ctx.strokeStyle = "rgba(255,255,255,.22)";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(0, 0, 360, 0, Math.PI * 2);
    ctx.stroke();

    ctx.globalAlpha = 0.06;
    ctx.lineWidth = 10;
    ctx.beginPath();
    ctx.arc(0, 0, 372, 0, Math.PI * 2);
    ctx.stroke();

    // map badge tiny
    if (map?.name) {
      ctx.globalAlpha = 0.55;
      ctx.fillStyle = "rgba(255,255,255,.75)";
      ctx.font = "800 11px Inter,system-ui";
      ctx.fillText(String(map.name).toUpperCase(), -26, 390);
    }

    ctx.restore();
  }

  function drawReticle(ctx, CORE, input, view) {
    const S = CORE.state;
    const w = view.w, h = view.h;
    const sx = (S.player.x - S.camX) + w / 2;
    const sy = (S.player.y - S.camY) + h / 2;

    const ax = input.aimX, ay = input.aimY;
    const r1 = 28, r2 = 56;

    ctx.save();
    ctx.translate(sx, sy);

    // line
    ctx.globalAlpha = 0.55;
    ctx.strokeStyle = "rgba(255,255,255,.80)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(ax * r1, ay * r1);
    ctx.lineTo(ax * r2, ay * r2);
    ctx.stroke();

    // dot
    ctx.globalAlpha = 0.22;
    ctx.beginPath();
    ctx.arc(ax * r2, ay * r2, 9, 0, Math.PI * 2);
    ctx.stroke();

    // tiny crosshair
    ctx.globalAlpha = 0.28;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(ax * r2 - 8, ay * r2);
    ctx.lineTo(ax * r2 + 8, ay * r2);
    ctx.moveTo(ax * r2, ay * r2 - 8);
    ctx.lineTo(ax * r2, ay * r2 + 8);
    ctx.stroke();

    ctx.restore();
  }

  // =========================================================
  // FALLBACK DRAWERS
  // =========================================================
  function fallbackPlayer(ctx, x, y, ax, ay) {
    ctx.save();
    ctx.translate(x, y);

    // body
    ctx.globalAlpha = 0.92;
    ctx.fillStyle = "rgba(255,255,255,.92)";
    ctx.beginPath();
    ctx.arc(0, 0, 14, 0, Math.PI * 2);
    ctx.fill();

    // head highlight
    ctx.globalAlpha = 0.22;
    ctx.fillStyle = "rgba(255,255,255,.55)";
    ctx.beginPath();
    ctx.arc(6, -6, 5, 0, Math.PI * 2);
    ctx.fill();

    // aim direction tick
    ctx.globalAlpha = 0.35;
    ctx.strokeStyle = "rgba(255,255,255,.85)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(ax * 16, ay * 16);
    ctx.stroke();

    ctx.restore();
  }

  function fallbackZombie(ctx, x, y, r) {
    ctx.save();
    ctx.translate(x, y);

    ctx.globalAlpha = 0.82;
    ctx.fillStyle = "rgba(160,255,160,.82)";
    ctx.beginPath();
    ctx.arc(0, 0, r, 0, Math.PI * 2);
    ctx.fill();

    ctx.globalAlpha = 0.35;
    ctx.fillStyle = "rgba(0,0,0,.55)";
    ctx.beginPath();
    ctx.arc(-5, -4, 3, 0, Math.PI * 2);
    ctx.arc(5, -4, 3, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
  }

  function fallbackBoss(ctx, x, y, r, kind) {
    ctx.save();
    ctx.translate(x, y);

    const isSpitter = String(kind || "").includes("spitter");

    // outer aura
    ctx.globalAlpha = 0.14;
    ctx.strokeStyle = isSpitter ? "rgba(180,220,255,.85)" : "rgba(220,255,200,.85)";
    ctx.lineWidth = 10;
    ctx.beginPath();
    ctx.arc(0, 0, r + 14, 0, Math.PI * 2);
    ctx.stroke();

    // core
    ctx.globalAlpha = 0.86;
    ctx.fillStyle = isSpitter ? "rgba(190,220,255,.70)" : "rgba(200,255,200,.70)";
    ctx.beginPath();
    ctx.arc(0, 0, r, 0, Math.PI * 2);
    ctx.fill();

    // face
    ctx.globalAlpha = 0.30;
    ctx.fillStyle = "rgba(0,0,0,.65)";
    ctx.beginPath();
    ctx.arc(-7, -5, 4, 0, Math.PI * 2);
    ctx.arc(7, -5, 4, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
  }

  // =========================================================
  // EXPORT
  // =========================================================
  window.BCO_ZOMBIES_RENDER = RENDER;
  console.log("[Z_RENDER] loaded (LUX)");
})();
