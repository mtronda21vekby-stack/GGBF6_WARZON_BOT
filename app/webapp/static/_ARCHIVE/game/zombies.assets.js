// app/webapp/static/game/zombies.assets.js
// Asset & sprite system for Zombies Survival
// Supports characters, zombies, skins, animations
// READY FOR REAL PNG SPRITES

// =========================
// ASSET REGISTRY
// =========================
export const ASSETS = {
  characters: {
    male: {
      id: "male",
      name: "Soldier",
      baseSize: { w: 48, h: 64 },
      skins: {
        default: {
          id: "default",
          name: "Recruit",
          sprite: "/webapp/static/assets/characters/male/default.png"
        },
        royal: {
          id: "royal",
          name: "Royal Guard",
          sprite: "/webapp/static/assets/characters/male/royal.png"
        }
      }
    },

    female: {
      id: "female",
      name: "Operative",
      baseSize: { w: 48, h: 64 },
      skins: {
        default: {
          id: "default",
          name: "Valkyrie",
          sprite: "/webapp/static/assets/characters/female/default.png"
        },
        neon: {
          id: "neon",
          name: "Neon",
          sprite: "/webapp/static/assets/characters/female/neon.png"
        }
      }
    }
  },

  zombies: {
    walker: {
      id: "walker",
      name: "Walker",
      size: { w: 44, h: 60 },
      hpMul: 1.0,
      speedMul: 1.0,
      sprite: "/webapp/static/assets/zombies/walker.png"
    },

    runner: {
      id: "runner",
      name: "Runner",
      size: { w: 42, h: 58 },
      hpMul: 0.75,
      speedMul: 1.6,
      sprite: "/webapp/static/assets/zombies/runner.png"
    },

    brute: {
      id: "brute",
      name: "Brute",
      size: { w: 60, h: 78 },
      hpMul: 2.5,
      speedMul: 0.65,
      sprite: "/webapp/static/assets/zombies/brute.png"
    }
  }
};

// =========================
// IMAGE LOADER
// =========================
const imageCache = new Map();

export function loadImage(src) {
  if (imageCache.has(src)) return imageCache.get(src);

  const img = new Image();
  img.src = src;
  imageCache.set(src, img);
  return img;
}

// =========================
// CHARACTER HELPERS
// =========================
export function getCharacterAsset(character, skin) {
  const ch = ASSETS.characters[character];
  if (!ch) return null;
  return ch.skins[skin] || Object.values(ch.skins)[0];
}

// =========================
// ZOMBIE HELPERS
// =========================
export function getZombieAsset(type) {
  return ASSETS.zombies[type] || ASSETS.zombies.walker;
}

// =========================
// DRAW HELPERS (CANVAS)
// =========================
export function drawSprite(ctx, img, x, y, w, h, flip = false) {
  if (!img || !img.complete) return;

  ctx.save();
  ctx.translate(x, y);

  if (flip) {
    ctx.scale(-1, 1);
    ctx.drawImage(img, -w / 2, -h / 2, w, h);
  } else {
    ctx.drawImage(img, -w / 2, -h / 2, w, h);
  }

  ctx.restore();
}

// =========================
// FALLBACK (NO SPRITE YET)
// =========================
export function drawFallback(ctx, x, y, w, h, color = "#22d3ee") {
  ctx.save();
  ctx.fillStyle = color;
  ctx.fillRect(x - w / 2, y - h / 2, w, h);
  ctx.restore();
}
