// app/webapp/static/zombies/ui.js
(() => {
  "use strict";

  window.BCO = window.BCO || {};
  const bus = window.BCO.bus;

  const TAKEOVER_CLASS = (window.BCO.CONFIG && window.BCO.CONFIG.FULLSCREEN && window.BCO.CONFIG.FULLSCREEN.TAKEOVER_CLASS)
    || (window.BCO_CONFIG && window.BCO_CONFIG.FULLSCREEN && window.BCO_CONFIG.FULLSCREEN.TAKEOVER_CLASS)
    || "bco-game-takeover";

  function qs(id) { return document.getElementById(id); }
  function qsa(sel) { return Array.from(document.querySelectorAll(sel)); }
  function safe(fn) { try { return fn(); } catch (_) { return undefined; } }

  // ----------------------------------------------------------
  // 1) Mark scrollable modal containers for iOS (.bco-modal-scroll)
  // ----------------------------------------------------------
  function markModalScroll() {
    const nodes = Array.from(document.querySelectorAll(
      ".modal, .modal-content, [role='dialog'], [data-modal], [data-popup], .sheet, .sheet-content"
    ));

    for (const el of nodes) {
      let cs;
      try { cs = window.getComputedStyle(el); } catch { cs = null; }
      if (!cs) continue;

      const oy = cs.overflowY;
      const ox = cs.overflowX;

      // Only mark real scrollables (avoid marking everything)
      const scrollY = (oy === "auto" || oy === "scroll");
      const scrollX = (ox === "auto" || ox === "scroll");

      if (scrollY || scrollX) {
        el.classList.add("bco-modal-scroll");
        // iOS momentum scroll
        el.style.webkitOverflowScrolling = "touch";
        // allow pan in scroll blocks (input module also respects .bco-modal-scroll)
        if (!el.style.touchAction) el.style.touchAction = scrollY ? "pan-y" : "pan-x";
      }
    }
  }

  // Light loop to catch dynamically created dialogs for a short time
  function loopMark() {
    let frames = 0;
    const tick = () => {
      frames++;
      if (frames <= 240) markModalScroll(); // ~4 seconds at 60fps
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  // ----------------------------------------------------------
  // 2) Takeover touch guard (ONLY prevents rubber-band in takeover)
  //    IMPORTANT: do NOT block scroll inside .bco-modal-scroll
  // ----------------------------------------------------------
  function installTakeoverTouchGuard() {
    document.addEventListener("touchmove", (e) => {
      const takeover = document.body.classList.contains(TAKEOVER_CLASS);
      if (!takeover) return;

      const t = e.target;
      if (t && t.closest && t.closest(".bco-modal-scroll")) return;

      // Prevent page scroll / rubber-band while game takeover active
      e.preventDefault();
    }, { passive: false, capture: true });
  }

  // ----------------------------------------------------------
  // 3) Action wiring (NO redesign):
  //    - add data-action/data-payload to existing buttons by id
  //    - register handlers in BCO_POINTER_ROUTER / BCO.input
  // ----------------------------------------------------------
  function setAction(el, action, payload) {
    if (!el) return;
    el.setAttribute("data-action", String(action));
    if (payload !== undefined) {
      try { el.setAttribute("data-payload", JSON.stringify(payload)); }
      catch { el.setAttribute("data-payload", String(payload)); }
    }
  }

  function wireActionsAttributes() {
    // Launchers
    setAction(qs("btnZEnterGame"), "zombies:start", {});
    setAction(qs("btnZQuickPlay"), "zombies:start", {});
    setAction(qs("btnPlayZombies"), "zombies:openTabGame", {});

    // Mode buttons (two places)
    setAction(qs("btnZModeArcade"), "zombies:mode", { mode: "ARCADE" });
    setAction(qs("btnZModeRogue"), "zombies:mode", { mode: "ROGUELIKE" });
    setAction(qs("btnZModeArcade2"), "zombies:mode", { mode: "ARCADE" });
    setAction(qs("btnZModeRogue2"), "zombies:mode", { mode: "ROGUELIKE" });

    // Map segment buttons
    const seg = qs("segZMap");
    if (seg) {
      const btns = Array.from(seg.querySelectorAll(".seg-btn"));
      for (const b of btns) {
        const v = b.getAttribute("data-value") || "Ashes";
        setAction(b, "zombies:map", { map: v });
      }
    }

    // Hotkey shop buttons in HOME preview
    setAction(qs("btnZBuyJug"), "zombies:shopHotkey", { item: "jug" });
    setAction(qs("btnZBuySpeed"), "zombies:shopHotkey", { item: "speed" });
    setAction(qs("btnZBuyAmmo"), "zombies:shopHotkey", { item: "ammo" });

    // Send results (placeholders, will just emit bus if engine provides last result)
    setAction(qs("btnZGameSend"), "zombies:sendResult", { from: "home" });
    setAction(qs("btnZGameSend2"), "zombies:sendResult", { from: "game" });

    // HQ buttons (bot commands — app.js may also bind them; action router ensures reliability)
    setAction(qs("btnZOpenHQ"), "zombies:hq", {});
    setAction(qs("btnOpenZombies"), "zombies:hq", { section: "menu" });
    setAction(qs("btnZPerks"), "zombies:hq", { section: "perks" });
    setAction(qs("btnZLoadout"), "zombies:hq", { section: "loadout" });
    setAction(qs("btnZEggs"), "zombies:hq", { section: "eggs" });
    setAction(qs("btnZRound"), "zombies:hq", { section: "round" });
    setAction(qs("btnZTips"), "zombies:hq", { section: "tips" });
  }

  function getRuntime() {
    return window.BCO && window.BCO.zombies && window.BCO.zombies.runtime
      ? window.BCO.zombies.runtime
      : null;
  }

  function openTabGame() {
    // no redesign: just simulate click on bottom nav Game tab
    const btn = document.querySelector("nav.bottom-nav .nav-btn[data-tab='game']");
    if (btn) safe(() => btn.click());
  }

  function registerRouterHandlers() {
    const router = window.BCO_POINTER_ROUTER || (window.BCO && window.BCO.input) || null;
    const onAction = router && typeof router.onAction === "function" ? router.onAction.bind(router) : null;

    // If router not ready yet, just skip — app.js may bind normally; but most times router is loaded before this file.
    if (!onAction) return;

    onAction("zombies:openTabGame", () => {
      openTabGame();
    });

    onAction("zombies:mode", (p) => {
      const rt = getRuntime();
      const m = (p && p.payload && p.payload.mode) ? p.payload.mode : (p && p.mode) ? p.mode : "ARCADE";
      if (rt && typeof rt.setMode === "function") rt.setMode(m);
      bus?.emit?.("zombies:mode_ui", { mode: m });
    });

    onAction("zombies:map", (p) => {
      const rt = getRuntime();
      const mp = (p && p.payload && p.payload.map) ? p.payload.map : (p && p.map) ? p.map : "Ashes";
      if (rt && typeof rt.setMap === "function") rt.setMap(mp);
      bus?.emit?.("zombies:map_ui", { map: mp });
    });

    onAction("zombies:start", () => {
      const rt = getRuntime();
      if (rt && typeof rt.startGame === "function") rt.startGame();
      else bus?.emit?.("zombies:start_ui", {});
    });

    onAction("zombies:sendResult", (p) => {
      // This is a “router-level” event. Actual send implementation can live in app.js.
      // We just emit consistent event to bus so app.js can hook it.
      bus?.emit?.("zombies:send_result", p && p.payload ? p.payload : { from: "ui" });
    });

    onAction("zombies:shopHotkey", (p) => {
      // These are preview hotkeys; actual shop is in-game. We emit to bus for core/economy.
      const item = (p && p.payload && p.payload.item) ? p.payload.item : "unknown";
      bus?.emit?.("zombies:shop_hotkey", { item });
    });

    onAction("zombies:hq", (p) => {
      // HQ actions should be handled by app.js (sendData to bot).
      // We normalize and emit. app.js can map section->payload type="nav".
      const section = (p && p.payload && p.payload.section) ? p.payload.section : "menu";
      bus?.emit?.("zombies:hq", hint(section));
    });

    function hint(section) {
      return { section: section || "menu" };
    }
  }

  // ----------------------------------------------------------
  // 4) Boot
  // ----------------------------------------------------------
  function boot() {
    installTakeoverTouchGuard();
    markModalScroll();
    loopMark();

    // Add data-action attrs so FastTap router can route reliably (no UI change)
    wireActionsAttributes();

    // Register router actions so it works even if app.js bindings are flaky on iOS
    registerRouterHandlers();

    // On takeover events: re-mark scrollables
    bus?.on?.("zombies:takeover", () => markModalScroll());
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();
