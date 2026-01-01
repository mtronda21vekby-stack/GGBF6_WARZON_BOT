/* =========================================================
   BLACK CROWN OPS — ZOMBIES ASSETS SYSTEM
   File: app/webapp/static/zombies.assets.js
   ========================================================= */

(() => {
  "use strict";

  if (!window.BCO_ZOMBIES) {
    console.error("[BCO_ZOMBIES] core not loaded");
    return;
  }

  /* =========================
     ASSET REGISTRY
  ========================= */

  const Assets = {
    player: {
      male: {
        id: "player_male",
        hitbox: 18,
        draw(ctx, x, y, dirX, dirY) {
          // тело
          ctx.fillStyle = "#4af";
          ctx.beginPath();
          ctx.arc(x, y, 14, 0, Math.PI * 2);
          ctx.fill();

          // голова
          ctx.fillStyle = "#9bd";
          ctx.beginPath();
          ctx.arc(x, y - 18, 8, 0, Math.PI * 2);
          ctx.fill();

          // оружие
          ctx.strokeStyle = "#fff";
          ctx.lineWidth = 3;
          ctx.beginPath();
          ctx.moveTo(x, y);
          ctx.lineTo(x + dirX * 18, y + dirY * 18);
          ctx.stroke();
        }
      },

      female: {
        id: "player_female",
        hitbox: 17,
        draw(ctx, x, y, dirX, dirY) {
          ctx.fillStyle = "#f6a";
          ctx.beginPath();
          ctx.arc(x, y, 13, 0, Math.PI * 2);
          ctx.fill();

          ctx.fillStyle = "#fcd";
          ctx.beginPath();
          ctx.arc(x, y - 17, 7, 0, Math.PI * 2);
          ctx.fill();

          ctx.strokeStyle = "#fff";
          ctx.lineWidth = 3;
          ctx.beginPath();
          ctx.moveTo(x, y);
          ctx.lineTo(x + dirX * 18, y + dirY * 18);
          ctx.stroke();
        }
      }
    },

    zombies: {
      basic: {
        id: "zombie_basic",
        hitbox: 16,
        draw(ctx, x, y) {
          // тело
          ctx.fillStyle = "#3f3";
          ctx.beginPath();
          ctx.arc(x, y + 6, 12, 0, Math.PI * 2);
          ctx.fill();

          // голова
          ctx.fillStyle = "#7f7";
          ctx.beginPath();
          ctx.arc(x, y - 10, 9, 0, Math.PI * 2);
          ctx.fill();

          // глаза
          ctx.fillStyle = "#000";
          ctx.beginPath();
          ctx.arc(x - 3, y - 12, 2, 0, Math.PI * 2);
          ctx.arc(x + 3, y - 12, 2, 0, Math.PI * 2);
          ctx.fill();
        }
      },

      brute: {
        id: "zombie_brute",
        hitbox: 20,
        draw(ctx, x, y) {
          ctx.fillStyle = "#2c6";
          ctx.beginPath();
          ctx.arc(x, y + 8, 16, 0, Math.PI * 2);
          ctx.fill();

          ctx.fillStyle = "#5fa";
          ctx.beginPath();
          ctx.arc(x, y - 12, 11, 0, Math.PI * 2);
          ctx.fill();
        }
      }
    }
  };

  /* =========================
     PLAYER SELECTION
  ========================= */

  let currentPlayer = "male";

  function setPlayerSkin(type) {
    if (Assets.player[type]) currentPlayer = type;
  }

  /* =========================
     DRAW HOOKS
  ========================= */

  const core = window.BCO_ZOMBIES;

  core._drawPlayer = function (ctx, player) {
    const skin = Assets.player[currentPlayer];
    skin.draw(ctx, player.x, player.y, player.dirX, player.dirY);
  };

  core._drawZombie = function (ctx, zombie) {
    const skin = Assets.zombies.basic;
    skin.draw(ctx, zombie.x, zombie.y);
  };

  /* =========================
     PUBLIC API
  ========================= */

  window.BCO_ZOMBIES_ASSETS = {
    setPlayerSkin,
    Assets
  };

  console.log("[BCO_ZOMBIES] assets loaded");
})();
