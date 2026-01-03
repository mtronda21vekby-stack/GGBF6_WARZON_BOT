(() => {
  "use strict";

  const log = window.BCO_LOG || console;

  function ensureTelegramReady() {
    const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
    if (!tg) return null;
    try {
      tg.ready();
      tg.expand();
      // Default: hide buttons (UI not changed, but prevents overlap)
      try { tg.MainButton.hide(); } catch {}
      try { tg.BackButton.hide(); } catch {}
    } catch (e) {
      log.warn("Telegram ready failed", e);
    }
    return tg;
  }

  function mountInputLayer() {
    // Gesture guard first (pinch/ghost/scroll bugs)
    if (window.BCO_GESTURE_GUARD?.installGestureGuard) {
      window.BCO_GESTURE_GUARD.installGestureGuard();
    }

    // Pointer router: 100% taps
    const pr = window.BCO_POINTER_ROUTER;
    pr.mount();

    // Bind actions without HTML redesign:
    // If you add data-action in HTML later, it just works.
    const runtime = window.BCO_ZOMBIES_RUNTIME;
    const store = window.BCO_STORE;
    const bus = window.BCO_EVENTBUS;

    // Start game actions (you can attach these to existing buttons via data-action)
    pr.onAction("zombies:start_arcade", async () => {
      runtime.start("ARCADE");
      bus.emit("zombies:started", { mode: "ARCADE" });
    });

    pr.onAction("zombies:start_roguelike", async () => {
      runtime.start("ROGUELIKE");
      bus.emit("zombies:started", { mode: "ROGUELIKE" });
    });

    pr.onAction("zombies:stop", async () => {
      runtime.stop();
      bus.emit("zombies:stopped", {});
    });

    pr.onAction("zombies:send_result", async () => {
      const snap = runtime.getSnapshot();
      await sendDataToBot({ type: "game_result", game: "zombies", data: snap });
    });

    // Route handler (generic)
    pr.onAction("route:home", () => bus.emit("nav:go", { route: "home" }));
    pr.onAction("route:zombies", () => bus.emit("nav:go", { route: "zombies" }));

    // Optional: if your existing UI uses data-route only
    pr.onAction("route:game", () => bus.emit("nav:go", { route: "game" }));

    // Basic: ensure modals become scroll-allowed when opened
    document.addEventListener("transitionend", () => {
      window.BCO_ZOMBIES_UI?.markModalScrollContainers?.();
    }, { passive: true });

    // Store default voice (TEAMMATE)
    (async () => {
      const cur = await store.get("profile.voice", null);
      if (!cur) await store.set("profile.voice", window.BCO_CONFIG?.DEFAULT_VOICE || "TEAMMATE");
    })();
  }

  async function sendDataToBot(payload) {
    const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
    const store = window.BCO_STORE;

    const profile = await store.get("profile", {});
    const packet = {
      ...payload,
      profile,
      ts: Date.now(),
      v: window.BCO_CONFIG?.VERSION || "3.x",
    };

    const raw = JSON.stringify(packet);
    const max = window.BCO_CONFIG?.MAX_PAYLOAD_SIZE || 15000;

    const safeRaw = (raw.length > max)
      ? JSON.stringify({ type: "error", reason: "payload_too_large", ts: Date.now() })
      : raw;

    if (tg && typeof tg.sendData === "function") {
      tg.sendData(safeRaw);
      return true;
    }

    log.warn("Telegram sendData unavailable. Payload:", packet);
    return false;
  }

  function boot() {
    ensureTelegramReady();
    mountInputLayer();

    // Health marker
    window.BCO_APP = {
      booted: true,
      sendDataToBot,
    };

    log.info("BCO App booted", window.BCO_CONFIG?.VERSION);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
