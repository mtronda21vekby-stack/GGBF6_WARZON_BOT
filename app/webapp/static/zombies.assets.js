/* =========================================================
   BLACK CROWN OPS — ZOMBIES ASSETS SYSTEM (PNG sprites + fallback)
   File: app/webapp/static/zombies.assets.js
   ========================================================= */

(() => {
  "use strict";

  if (!window.BCO_ZOMBIES) {
    console.error("[BCO_ZOMBIES_ASSETS] core not loaded (window.BCO_ZOMBIES missing)");
    return;
  }

  const tg = window.Telegram?.WebApp;

  // ✅ абсолютные пути (важно из-за <base href="/webapp/">)
  const PATHS = {
    single: "/webapp/assets/sprites/sheet.png",
    quad: {
      q1: "/webapp/assets/sprites/sheet_q1_tl.png",
      q2: "/webapp/assets/sprites/sheet_q2_tr.png",
      q3: "/webapp/assets/sprites/sheet_q3_bl.png",
      q4: "/webapp/assets/sprites/sheet_q4_br.png"
    }
  };

  // =========================
  // helpers
  // =========================
  const now = () => Date.now();

  function haptic(type = "impact", style = "light") {
    try {
      if (!tg?.HapticFeedback) return;
      if (type === "impact") tg.HapticFeedback.impactOccurred(style);
      if (type === "notif") tg.HapticFeedback.notificationOccurred(style);
    } catch {}
  }

  function loadImage(url) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.decoding = "async";
      img.crossOrigin = "anonymous";
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error("img_load_failed:" + url));
      img.src = url + (url.includes("?") ? "&" : "?") + "v=" + encodeURIComponent(String(window.__BCO_BUILD__ || now()));
    });
  }

  function makeCanvas(w, h) {
    const c = document.createElement("canvas");
    c.width = w;
    c.height = h;
    return c;
  }

  // =========================
  // Atlas loader
  // =========================
  const Atlas = {
    ready: false,
    failed: false,
    mode: "auto", // "auto" | "single" | "quad"
    img: null,    // Image or Canvas
    w: 0,
    h: 0
  };

  async function loadAtlasAuto() {
    Atlas.ready = false;
    Atlas.failed = false;
    Atlas.img = null;
    Atlas.w = 0;
    Atlas.h = 0;

    // 1) try single
    if (Atlas.mode === "auto" || Atlas.mode === "single") {
      try {
        const img = await loadImage(PATHS.single);
        Atlas.img = img;
        Atlas.w = img.naturalWidth || img.width;
        Atlas.h = img.naturalHeight || img.height;
        Atlas.ready = true;
        Atlas.failed = false;
        console.log("[BCO_ZOMBIES_ASSETS] atlas single OK", PATHS.single, Atlas.w, Atlas.h);
        return true;
      } catch (e) {
        console.warn("[BCO_ZOMBIES_ASSETS] atlas single failed, fallback to quad", String(e?.message || e));
        if (Atlas.mode === "single") {
          Atlas.failed = true;
          return false;
        }
      }
    }

    // 2) try quad
    if (Atlas.mode === "auto" || Atlas.mode === "quad") {
      try {
        const [q1, q2, q3, q4] = await Promise.all([
          loadImage(PATHS.quad.q1),
          loadImage(PATHS.quad.q2),
          loadImage(PATHS.quad.q3),
          loadImage(PATHS.quad.q4)
        ]);

        // assume quadrants same size
        const qw = q1.naturalWidth || q1.width;
        const qh = q1.naturalHeight || q1.height;

        const c = makeCanvas(qw * 2, qh * 2);
        const cx = c.getContext("2d", { alpha: true });

        cx.drawImage(q1, 0, 0);
        cx.drawImage(q2, qw, 0);
        cx.drawImage(q3, 0, qh);
        cx.drawImage(q4, qw, qh);

        Atlas.img = c;
        Atlas.w = c.width;
        Atlas.h = c.height;
        Atlas.ready = true;
        Atlas.failed = false;
        console.log("[BCO_ZOMBIES_ASSETS] atlas quad OK", Atlas.w, Atlas.h);
        return true;
      } catch (e) {
        console.warn("[BCO_ZOMBIES_ASSETS] atlas quad failed", String(e?.message || e));
        Atlas.ready = false;
        Atlas.failed = true;
        return false;
      }
    }

    Atlas.failed = true;
    return false;
  }

  // =========================
  // Sprite map (EDIT HERE later)
  // =========================
  // ⚠️ Это стартовый “безопасный” мэппинг.
  // ТЫ ПОТОМ ПОДГОНИШЬ x,y,w,h под свой лист.
  // Важно: игра НЕ УПАДЁТ, даже если мэппинг кривой — просто картинка будет не та.
  const SPRITES = {
    // player
    player_male_idle:   { x: 40,  y: 40,  w: 180, h: 220, anchorX: 0.5, anchorY: 0.72 },
    player_female_idle: { x: 420, y: 40,  w: 180, h: 220, anchorX: 0.5, anchorY: 0.72 },

    // zombies
    zombie_basic_walk:  { x: 40,  y: 320, w: 180, h: 220, anchorX: 0.5, anchorY: 0.74 },
    zombie_brute_walk:  { x: 420, y: 320, w: 180, h: 220, anchorX: 0.5, anchorY: 0.74 }
  };

  // =========================
  // Draw from atlas
  // =========================
  function drawSprite(ctx, key, x, y, opts = {}) {
    if (!Atlas.ready || !Atlas.img) return false;
    const sp = SPRITES[key];
    if (!sp) return false;

    const scale = (opts.scale ?? 1);
    const rot = (opts.rot ?? 0);

    const ax = (sp.anchorX ?? 0.5);
    const ay = (sp.anchorY ?? 0.5);

    const dw = sp.w * scale;
    const dh = sp.h * scale;

    ctx.save();
    ctx.translate(x, y);
    if (rot) ctx.rotate(rot);

    // draw with anchor
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(
      Atlas.img,
      sp.x, sp.y, sp.w, sp.h,
      -dw * ax, -dh * ay,
      dw, dh
    );

    ctx.restore();
    return true;
  }

  // =========================
  // Fallback vector drawings (твои текущие)
  // =========================
  const Fallback = {
    player: {
      male: {
        hitbox: 18,
        draw(ctx, x, y, dirX, dirY) {
          ctx.fillStyle = "#4af";
          ctx.beginPath(); ctx.arc(x, y, 14, 0, Math.PI * 2); ctx.fill();
          ctx.fillStyle = "#9bd";
          ctx.beginPath(); ctx.arc(x, y - 18, 8, 0, Math.PI * 2); ctx.fill();
          ctx.strokeStyle = "#fff"; ctx.lineWidth = 3;
          ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + dirX * 18, y + dirY * 18); ctx.stroke();
        }
      },
      female: {
        hitbox: 17,
        draw(ctx, x, y, dirX, dirY) {
          ctx.fillStyle = "#f6a";
          ctx.beginPath(); ctx.arc(x, y, 13, 0, Math.PI * 2); ctx.fill();
          ctx.fillStyle = "#fcd";
          ctx.beginPath(); ctx.arc(x, y - 17, 7, 0, Math.PI * 2); ctx.fill();
          ctx.strokeStyle = "#fff"; ctx.lineWidth = 3;
          ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + dirX * 18, y + dirY * 18); ctx.stroke();
        }
      }
    },
    zombies: {
      basic: {
        hitbox: 16,
        draw(ctx, x, y) {
          ctx.fillStyle = "#3f3";
          ctx.beginPath(); ctx.arc(x, y + 6, 12, 0, Math.PI * 2); ctx.fill();
          ctx.fillStyle = "#7f7";
          ctx.beginPath(); ctx.arc(x, y - 10, 9, 0, Math.PI * 2); ctx.fill();
          ctx.fillStyle = "#000";
          ctx.beginPath();
          ctx.arc(x - 3, y - 12, 2, 0, Math.PI * 2);
          ctx.arc(x + 3, y - 12, 2, 0, Math.PI * 2);
          ctx.fill();
        }
      },
      brute: {
        hitbox: 20,
        draw(ctx, x, y) {
          ctx.fillStyle = "#2c6";
          ctx.beginPath(); ctx.arc(x, y + 8, 16, 0, Math.PI * 2); ctx.fill();
          ctx.fillStyle = "#5fa";
          ctx.beginPath(); ctx.arc(x, y - 12, 11, 0, Math.PI * 2); ctx.fill();
        }
      }
    }
  };

  // =========================
  // Public Assets API
  // =========================
  let currentPlayer = "male";   // male | female
  let currentZombie = "basic";  // basic | brute

  function setPlayerSkin(type) {
    if (type === "male" || type === "female") currentPlayer = type;
  }

  function setZombieSkin(type) {
    if (type === "basic" || type === "brute") currentZombie = type;
  }

  function setAtlasMode(mode) {
    if (mode !== "auto" && mode !== "single" && mode !== "quad") return;
    Atlas.mode = mode;
  }

  // =========================
  // Core draw hooks
  // =========================
  const core = window.BCO_ZOMBIES;

  core._drawPlayer = function (ctx, player) {
    // aim rotation
    const rot = Math.atan2(player.dirY || 0, player.dirX || 1);

    // try sprite
    const key = (currentPlayer === "female") ? "player_female_idle" : "player_male_idle";
    const ok = drawSprite(ctx, key, player.x, player.y, { scale: 0.34, rot });

    // fallback
    if (!ok) {
      const skin = Fallback.player[currentPlayer] || Fallback.player.male;
      skin.draw(ctx, player.x, player.y, player.dirX || 1, player.dirY || 0);
    }
  };

  core._drawZombie = function (ctx, zombie) {
    const key = (currentZombie === "brute") ? "zombie_brute_walk" : "zombie_basic_walk";
    const ok = drawSprite(ctx, key, zombie.x, zombie.y, { scale: 0.34, rot: 0 });

    if (!ok) {
      const skin = Fallback.zombies[currentZombie] || Fallback.zombies.basic;
      skin.draw(ctx, zombie.x, zombie.y);
    }
  };

  // =========================
  // Debug helper (optional)
  // =========================
  let debugDrawAtlas = false;
  function setDebugAtlas(on) { debugDrawAtlas = !!on; }

  // This can be called from your core render loop if you want.
  core._assetsDebugOverlay = function (ctx, w, h) {
    if (!debugDrawAtlas || !Atlas.ready || !Atlas.img) return;
    ctx.save();
    ctx.globalAlpha = 0.95;
    const scale = 0.18;
    ctx.drawImage(Atlas.img, 12, 12, Atlas.w * scale, Atlas.h * scale);
    ctx.fillStyle = "rgba(0,0,0,.55)";
    ctx.fillRect(12, 12 + Atlas.h * scale + 8, 260, 26);
    ctx.fillStyle = "rgba(255,255,255,.92)";
    ctx.font = "12px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace";
    ctx.fillText(`atlas: ${Atlas.w}x${Atlas.h} (${Atlas.mode})`, 18, 12 + Atlas.h * scale + 26);
    ctx.restore();
  };

  // =========================
  // Boot load
  // =========================
  (async () => {
    const ok = await loadAtlasAuto();
    if (ok) {
      haptic("notif", "success");
    } else {
      console.warn("[BCO_ZOMBIES_ASSETS] PNG atlas not found -> using fallback vector draws");
      haptic("notif", "warning");
    }
  })();

  window.BCO_ZOMBIES_ASSETS = {
    setPlayerSkin,
    setZombieSkin,
    setAtlasMode,
    setDebugAtlas,
    getAtlasState: () => ({ ready: Atlas.ready, failed: Atlas.failed, mode: Atlas.mode, w: Atlas.w, h: Atlas.h }),
    SPRITES
  };

  console.log("[BCO_ZOMBIES_ASSETS] loaded");
})();
