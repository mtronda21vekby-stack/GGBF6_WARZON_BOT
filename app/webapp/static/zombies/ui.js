(() => {
  "use strict";

  /**
   * UI module (NO visual redesign):
   * - Only: reliable modal scroll/click behavior + HUD sync helpers
   * - Adds technical classes for scroll containers when detected
   */

  const log = window.BCO_LOG || console;

  function markModalScrollContainers() {
    // Heuristic: elements that look like modal content
    const candidates = Array.from(document.querySelectorAll(
      ".modal, .modal-content, .shop, .character, [data-modal], [data-sheet], [data-popup]"
    ));

    for (const el of candidates) {
      // we do NOT change styles; only add class for gesture guard to allow scroll
      if (!el.classList.contains("bco-modal-scroll")) {
        // allow scroll if it's tall content
        const cs = window.getComputedStyle(el);
        const overflowY = cs.overflowY;
        if (overflowY === "auto" || overflowY === "scroll") {
          el.classList.add("bco-modal-scroll");
          el.style.webkitOverflowScrolling = "touch";
        }
      }
    }
  }

  function setTakeover(on) {
    if (on) document.body.classList.add("bco-game-takeover");
    else document.body.classList.remove("bco-game-takeover");
  }

  function lockBodyScroll(on) {
    const cfg = window.BCO_CONFIG?.FULLSCREEN || {};
    if (!(cfg.LOCK_BODY_SCROLL ?? true)) return;

    if (on) {
      // stable iOS technique
      const y = window.scrollY || 0;
      document.body.dataset.bcoScrollY = String(y);
      document.body.style.position = "fixed";
      document.body.style.top = `-${y}px`;
      document.body.style.left = "0";
      document.body.style.right = "0";
      document.body.style.width = "100%";
    } else {
      const y = parseInt(document.body.dataset.bcoScrollY || "0", 10) || 0;
      document.body.style.position = "";
      document.body.style.top = "";
      document.body.style.left = "";
      document.body.style.right = "";
      document.body.style.width = "";
      delete document.body.dataset.bcoScrollY;
      window.scrollTo(0, y);
    }
  }

  function telegramFullscreen(on) {
    const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
    if (!tg) return;

    try {
      tg.ready();
      tg.expand();

      // Hide TG chrome as much as possible (bugfix level, no UI redesign)
      if (on) {
        try { tg.MainButton.hide(); } catch {}
        try { tg.BackButton.hide(); } catch {}
        try { tg.enableClosingConfirmation(); } catch {}
        try { tg.setHeaderColor && tg.setHeaderColor("#000000"); } catch {}
        try { tg.setBackgroundColor && tg.setBackgroundColor("#000000"); } catch {}
      } else {
        // keep hidden by default unless your UI uses them
        try { tg.MainButton.hide(); } catch {}
        try { tg.BackButton.hide(); } catch {}
        try { tg.disableClosingConfirmation(); } catch {}
      }
    } catch (e) {
      log.warn("telegramFullscreen failed", e);
    }
  }

  // HUD binding helpers (optional; if your DOM has these IDs, it will fill them)
  function updateHud(hud) {
    const map = {
      hp: "bcoHudHp",
      armor: "bcoHudArmor",
      plates: "bcoHudPlates",
      coins: "bcoHudCoins",
      relics: "bcoHudRelics",
      ammo: "bcoHudAmmo",
      wave: "bcoHudWave",
      level: "bcoHudLevel",
      xp: "bcoHudXp",
    };

    for (const k of Object.keys(map)) {
      const id = map[k];
      const el = document.getElementById(id);
      if (!el) continue;
      const v = hud && hud[k] != null ? hud[k] : "";
      el.textContent = String(v);
    }
  }

  window.BCO_ZOMBIES_UI = {
    markModalScrollContainers,
    setTakeover,
    lockBodyScroll,
    telegramFullscreen,
    updateHud,
  };
})();
