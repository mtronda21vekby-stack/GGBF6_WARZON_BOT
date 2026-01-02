/* =========================================================
   BLACK CROWN OPS — ZOMBIES RENDER
   File: app/webapp/static/zombies.render.js
   Provides: window.BCO_ZOMBIES_RENDER
   ========================================================= */
(() => {
  "use strict";

  const ASSETS = () => window.BCO_ZOMBIES_ASSETS || null;

  const RENDER = {
    render(ctx, CORE, input, view) {
      const S = CORE.state;
      const w = view.w, h = view.h;

      ctx.clearRect(0, 0, w, h);

      // background vignette
      ctx.save();
      ctx.fillStyle = "rgba(0,0,0,.18)";
      ctx.fillRect(0, 0, w, h);
      ctx.restore();

      // world transform (camera centered)
      const camX = S.camX, camY = S.camY;

      // map (optional)
      try {
        const MAPS = window.BCO_ZOMBIES_MAPS;
        const map = MAPS?.get?.(CORE.meta.map);
        if (map) {
          // simple dark tile back
          ctx.save();
          ctx.translate(w / 2, h / 2);
          ctx.translate(-camX, -camY);
          ctx.globalAlpha = 0.18;
          ctx.fillStyle = "#ffffff";
          const step = 64;
          const minX = (camX - w / 2 - 200) | 0;
          const minY = (camY - h / 2 - 200) | 0;
          const maxX = (camX + w / 2 + 200) | 0;
          const maxY = (camY + h / 2 + 200) | 0;
          for (let x = Math.floor(minX / step) * step; x < maxX; x += step) {
            for (let y = Math.floor(minY / step) * step; y < maxY; y += step) {
              ctx.fillRect(x + 1, y + 1, 1, 1);
            }
          }
          ctx.restore();
        }
      } catch {}

      // arena ring (fallback visual)
      ctx.save();
      ctx.translate(w / 2, h / 2);
      ctx.strokeStyle = "rgba(255,255,255,.10)";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(0, 0, 360, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();

      // draw entities
      ctx.save();
      ctx.translate(w / 2, h / 2);
      ctx.translate(-camX, -camY);

      // bullets
      ctx.globalAlpha = 0.92;
      ctx.fillStyle = "rgba(255,255,255,.92)";
      for (const b of S.bullets) {
        ctx.beginPath();
        ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2);
        ctx.fill();
      }

      // zombies
      for (const z of S.zombies) {
        const A = ASSETS();
        if (A?.drawZombie) {
          try { A.drawZombie(ctx, z.x, z.y, { zombie: z.kind || "basic" }); }
          catch { fallbackZombie(ctx, z.x, z.y); }
        } else fallbackZombie(ctx, z.x, z.y);
      }

      // player
      const A = ASSETS();
      if (A?.drawPlayer) {
        try { A.drawPlayer(ctx, S.player.x, S.player.y, input.aimX, input.aimY, { player: CORE.meta.character, skin: CORE.meta.skin }); }
        catch { fallbackPlayer(ctx, S.player.x, S.player.y); }
      } else fallbackPlayer(ctx, S.player.x, S.player.y);

      ctx.restore();

      // aim reticle (lux)
      drawReticle(ctx, CORE, input, view);
    }
  };

  function fallbackPlayer(ctx, x, y) {
    ctx.save();
    ctx.translate(x, y);
    ctx.fillStyle = "rgba(255,255,255,.92)";
    ctx.beginPath();
    ctx.arc(0, 0, 14, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "rgba(255,255,255,.22)";
    ctx.beginPath();
    ctx.arc(6, -6, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  function fallbackZombie(ctx, x, y) {
    ctx.save();
    ctx.translate(x, y);
    ctx.fillStyle = "rgba(160,255,160,.82)";
    ctx.beginPath();
    ctx.arc(0, 0, 16, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "rgba(0,0,0,.35)";
    ctx.beginPath();
    ctx.arc(-5, -4, 3, 0, Math.PI * 2);
    ctx.arc(5, -4, 3, 0, Math.PI * 2);
    ctx.fill();
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
    ctx.globalAlpha = 0.55;
    ctx.strokeStyle = "rgba(255,255,255,.80)";
    ctx.lineWidth = 2;

    ctx.beginPath();
    ctx.moveTo(ax * r1, ay * r1);
    ctx.lineTo(ax * r2, ay * r2);
    ctx.stroke();

    ctx.globalAlpha = 0.18;
    ctx.beginPath();
    ctx.arc(ax * r2, ay * r2, 9, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }

  window.BCO_ZOMBIES_RENDER = RENDER;
  console.log("[Z_RENDER] loaded");
})();
