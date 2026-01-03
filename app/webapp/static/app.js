// app/webapp/static/app.js
// BCO App Entry — ELITE WIRING (data-action + runtime + engine)
// CONTRACT:
// - NO UI redesign
// - iOS WebView clicks 100%
// - Uses BCO_POINTER_ROUTER as single tap source
// - Zombies fullscreen MUST start

(() => {
  "use strict";

  const log = (...a) => console.log("[BCO_APP]", ...a);
  const warn = (...a) => console.warn("[BCO_APP]", ...a);

  function safe(fn) { try { return fn(); } catch { return undefined; } }
  function q(id) { return document.getElementById(id); }

  function setHealth(msg) {
    const el = q("jsHealth");
    if (el) el.textContent = String(msg || "");
  }

  // -------------------------------------------------
  // Detect modules (STRICT but tolerant)
  // -------------------------------------------------
  function detect() {
    const input = window.BCO_POINTER_ROUTER || window.BCO?.input || null;
    const engine = window.BCO?.engine || window.BCO_ENGINE || null;
    const runtime = window.BCO?.zombies?.runtime || null;
    const economy = window.BCO?.zombies?.economy || null;
    const core = window.BCO_ZOMBIES_CORE || null;
    const TG = window.Telegram?.WebApp || null;

    return { input, engine, runtime, economy, core, TG };
  }

  // -------------------------------------------------
  // iOS / takeover hardening (NO UI CHANGE)
  // -------------------------------------------------
  function installIOSGuards() {
    const prevent = (e) => { try { e.preventDefault(); } catch {} };

    document.addEventListener("gesturestart", prevent, { passive: false });
    document.addEventListener("gesturechange", prevent, { passive: false });
    document.addEventListener("gestureend", prevent, { passive: false });

    document.addEventListener("touchmove", (e) => {
      const takeover = document.body.classList.contains("bco-game-takeover");
      if (!takeover) return;

      const t = e.target;
      const allow = t && t.closest && t.closest(".bco-modal-scroll,.modal,[role='dialog']");
      if (allow) return;

      prevent(e);
    }, { passive: false, capture: true });
  }

  // -------------------------------------------------
  // Zombies actions (SINGLE SOURCE)
  // -------------------------------------------------
  function bindActions(mods) {
    const { input, runtime, engine, economy, TG } = mods;
    if (!input || !input.onAction) {
      warn("Pointer router missing");
      return;
    }

    // --- START GAME (Fullscreen) ---
    input.onAction("zombies:start", () => {
      log("action: zombies:start");

      if (runtime?.startGame) return runtime.startGame();
      if (engine?.start) {
        // fallback (should not happen normally)
        return engine.start({ mode: "arcade", map: "Ashes" });
      }
      warn("No startGame handler");
    });

    // --- OPEN GAME TAB + START ---
    input.onAction("zombies:open", () => {
      log("action: zombies:open");

      // switch tab → game
      const nav = document.querySelector('.nav-btn[data-tab="game"]');
      nav?.click?.();

      // small delay for layout
      setTimeout(() => {
        if (runtime?.startGame) runtime.startGame();
        else if (engine?.start) engine.start({ mode: "arcade", map: "Ashes" });
      }, 60);
    });

    // --- SEND RESULT ---
    input.onAction("zombies:send", () => {
      log("action: zombies:send");

      // Prefer game runner result sender
      if (window.BCO_ZOMBIES_GAME?.sendResult) {
        window.BCO_ZOMBIES_GAME.sendResult("manual");
        return;
      }

      // Fallback: minimal payload
      try {
        const payload = {
          action: "game_result",
          game: "zombies",
          source: "miniapp"
        };
        TG?.sendData?.(JSON.stringify(payload));
      } catch {}
    });

    // --- OPEN HQ IN BOT ---
    input.onAction("zombies:hq", () => {
      log("action: zombies:hq");

      try {
        TG?.sendData?.(JSON.stringify({
          type: "nav",
          action: "zombies_hq"
        }));
      } catch {}
    });

    // --- ECONOMY HOTKEYS (SAFE) ---
    input.onAction("zombies:perk:jug", () => economy?.buyPerk?.("Jug"));
    input.onAction("zombies:perk:speed", () => economy?.buyPerk?.("Speed"));
    input.onAction("zombies:ammo", () => economy?.buyReload?.());
  }

  // -------------------------------------------------
  // START
  // -------------------------------------------------
  function start() {
    setHealth("js: app wiring…");

    installIOSGuards();

    const mods = detect();

    // 1) Mount input FIRST (critical)
    safe(() => mods.input?.mount?.());

    // 2) Init runtime/economy if they expose init/bind
    safe(() => mods.runtime?.init?.());
    safe(() => mods.runtime?.bind?.());
    safe(() => mods.economy?._bind?.());

    // 3) Bind actions (THIS FIXES YOUR BUTTONS)
    bindActions(mods);

    // 4) Hide TG chrome by default
    safe(() => mods.TG?.MainButton?.hide?.());
    safe(() => mods.TG?.BackButton?.hide?.());

    window.__BCO_JS_OK__ = true;
    setHealth("js: OK (app wired)");

    log("READY", {
      input: !!mods.input,
      runtime: !!mods.runtime,
      engine: !!mods.engine,
      core: !!mods.core
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
