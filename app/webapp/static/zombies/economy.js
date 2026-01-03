// app/webapp/static/zombies/economy.js
(() => {
  "use strict";

  window.BCO = window.BCO || {};
  window.BCO.zombies = window.BCO.zombies || {};

  const bus = window.BCO.bus || window.BCO_BUS || window.BCO_EVENTBUS || null;

  // Core accessor (legacy-compatible)
  function core() { return window.BCO_ZOMBIES_CORE || null; }
  function can() { return !!core(); }

  // Safe core calls
  function buyUpgrade() { try { return !!core()?.buyUpgrade?.(); } catch { return false; } }
  function rerollWeapon() { try { return !!core()?.rerollWeapon?.(); } catch { return false; } }
  function buyReload() { try { return !!core()?.buyReload?.(); } catch { return false; } }
  function usePlate() { try { return !!core()?.usePlate?.(); } catch { return false; } }
  function buyPerk(id) { try { return !!core()?.buyPerk?.(id); } catch { return false; } }

  // Pull HUD/frame safely for “send result”
  function getFrame() {
    const c = core();
    if (!c) return null;
    try {
      if (typeof c.getFrameData === "function") return c.getFrameData();
    } catch {}
    try {
      // fallback: some builds keep last frame
      if (c.frame) return c.frame;
    } catch {}
    return null;
  }

  function getHudSnapshot() {
    const frame = getFrame();
    if (frame && frame.hud) {
      // normalize keys
      const h = frame.hud;
      return {
        wave: Number(h.wave || 0),
        kills: Number(h.kills || 0),
        coins: Number(h.coins || 0),
        relics: Number(h.relics || 0),
        relicNeed: Number(h.relicNeed || 5),
        hp: Number(h.hp || h.health || 0),
        armor: Number(h.armor || 0),
        ammo: (h.ammo != null) ? h.ammo : null,
        mode: h.mode || null,
        map: h.map || null,
        score: Number(h.score || 0),
        durationMs: Number(h.durationMs || 0),
      };
    }

    // fallback: core.state
    const c = core();
    try {
      const s = c?.state;
      if (s && typeof s === "object") {
        return {
          wave: Number(s.wave || 0),
          kills: Number(s.kills || 0),
          coins: Number(s.coins || 0),
          relics: Number(s.relics || 0),
          relicNeed: Number(s.relicNeed || 5),
          hp: Number(s.hp || s.health || 0),
          armor: Number(s.armor || 0),
          ammo: (s.ammo != null) ? s.ammo : null,
          mode: s.mode || null,
          map: s.map || null,
          score: Number(s.score || 0),
          durationMs: Number(s.durationMs || 0),
        };
      }
    } catch {}

    return null;
  }

  // Emit “send result” event for app.js to pack into sendData(action=game_result)
  function emitSendResult(meta = {}) {
    const snap = getHudSnapshot();
    bus?.emit?.("zombies:result_snapshot", { ok: !!snap, snapshot: snap, meta });
    return snap;
  }

  // Hotkeys by ID (keep yours)
  function bindHotkeys() {
    const jug = document.getElementById("btnZBuyJug");
    const spd = document.getElementById("btnZBuySpeed");
    const ammo = document.getElementById("btnZBuyAmmo");

    jug?.addEventListener("click", () => {
      const ok = buyPerk("Jug");
      bus?.emit?.("zombies:perk", { id: "Jug", ok });
    }, { passive: true });

    spd?.addEventListener("click", () => {
      const ok = buyPerk("Speed");
      bus?.emit?.("zombies:perk", { id: "Speed", ok });
    }, { passive: true });

    ammo?.addEventListener("click", () => {
      const ok = buyReload();
      bus?.emit?.("zombies:reloadbuy", { ok });
    }, { passive: true });
  }

  // Bus integration (THIS is what makes it feel “alive”)
  function bindBus() {
    if (!bus?.on) return;

    // From zombies/ui.js fast-tap router:
    bus.on("zombies:shop_hotkey", (e) => {
      const item = (e && e.item) ? String(e.item) : "unknown";
      let ok = false;

      if (item === "jug") ok = buyPerk("Jug");
      else if (item === "speed") ok = buyPerk("Speed");
      else if (item === "ammo") ok = buyReload();

      bus?.emit?.("zombies:shop_hotkey_result", { item, ok });
    });

    // Send result (buttons in index.html trigger this via ui/router)
    bus.on("zombies:send_result", (e) => {
      const meta = (e && typeof e === "object") ? e : { from: "ui" };
      const snap = emitSendResult(meta);
      // app.js should listen to zombies:result_snapshot and actually sendData(action=game_result)
      if (!snap) bus?.emit?.("zombies:result_snapshot", { ok: false, snapshot: null, meta });
    });
  }

  // Expose
  window.BCO.zombies.economy = {
    can,
    buyUpgrade,
    rerollWeapon,
    buyReload,
    usePlate,
    buyPerk,
    getHudSnapshot,
    emitSendResult,
    _bind: bindHotkeys,
    _bindBus: bindBus,
  };

  // Auto-bind (safe)
  function boot() {
    try { bindHotkeys(); } catch {}
    try { bindBus(); } catch {}
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();
