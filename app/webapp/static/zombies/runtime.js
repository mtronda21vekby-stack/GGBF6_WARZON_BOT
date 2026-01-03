// app/webapp/static/zombies/runtime.js
(() => {
  "use strict";

  window.BCO = window.BCO || {};
  const CFG = window.BCO.CONFIG || {};
  const bus = window.BCO.bus;

  function qs(id) { return document.getElementById(id); }

  function tg() { return (window.Telegram && Telegram.WebApp) ? Telegram.WebApp : null; }

  // Full takeover: hide header/nav/main/footer WITHOUT redesign
  const Takeover = (() => {
    let savedY = 0;

    function lockScroll(on) {
      if (!(CFG.FULLSCREEN && CFG.FULLSCREEN.LOCK_BODY_SCROLL)) return;
      if (on) {
        savedY = window.scrollY || 0;
        document.body.style.position = "fixed";
        document.body.style.top = `-${savedY}px`;
        document.body.style.left = "0";
        document.body.style.right = "0";
        document.body.style.width = "100%";
      } else {
        document.body.style.position = "";
        document.body.style.top = "";
        document.body.style.left = "";
        document.body.style.right = "";
        document.body.style.width = "";
        window.scrollTo(0, savedY);
      }
    }

    function hideTG(on) {
      const wa = tg();
      if (!wa) return;
      try {
        wa.ready();
        wa.expand();
        if (on) {
          try { wa.MainButton?.hide?.(); } catch {}
          try { wa.BackButton?.hide?.(); } catch {}
          try { wa.enableClosingConfirmation?.(); } catch {}
        } else {
          try { wa.MainButton?.hide?.(); } catch {}
          try { wa.BackButton?.hide?.(); } catch {}
          try { wa.disableClosingConfirmation?.(); } catch {}
        }
      } catch {}
    }

    function hideUI(on) {
      const header = document.querySelector("header.app-header");
      const nav = document.querySelector("nav.bottom-nav");
      const main = document.querySelector("main.app-main");
      const foot = document.querySelector("footer.foot");

      if (on) {
        if (header) header.style.display = "none";
        if (nav) nav.style.display = "none";
        if (foot) foot.style.display = "none";
        if (main) main.style.display = "none";
      } else {
        if (header) header.style.display = "";
        if (nav) nav.style.display = "";
        if (foot) foot.style.display = "";
        if (main) main.style.display = "";
      }
    }

    function enter() {
      const cls = (CFG.FULLSCREEN && CFG.FULLSCREEN.TAKEOVER_CLASS) || "bco-game-takeover";
      const act = (CFG.FULLSCREEN && CFG.FULLSCREEN.ACTIVE_CLASS) || "bco-game-active";
      document.body.classList.add(cls);
      document.body.classList.add(act);
      lockScroll(true);
      hideTG(true);
      hideUI(true);
      bus?.emit?.("zombies:takeover", { on: true });
    }

    function exit() {
      const cls = (CFG.FULLSCREEN && CFG.FULLSCREEN.TAKEOVER_CLASS) || "bco-game-takeover";
      const act = (CFG.FULLSCREEN && CFG.FULLSCREEN.ACTIVE_CLASS) || "bco-game-active";
      document.body.classList.remove(cls);
      document.body.classList.remove(act);
      hideUI(false);
      hideTG(false);
      lockScroll(false);
      bus?.emit?.("zombies:takeover", { on: false });
    }

    return { enter, exit };
  })();

  // Minimal state (launcher -> runtime)
  const state = {
    mode: "ARCADE",
    map: "Ashes"
  };

  function setMode(m) {
    state.mode = (String(m).toUpperCase().includes("ROGUE")) ? "ROGUELIKE" : "ARCADE";
    // sync both mode button pairs
    const a1 = qs("btnZModeArcade"); const r1 = qs("btnZModeRogue");
    const a2 = qs("btnZModeArcade2"); const r2 = qs("btnZModeRogue2");
    if (a1) a1.classList.toggle("active", state.mode === "ARCADE");
    if (r1) r1.classList.toggle("active", state.mode === "ROGUELIKE");
    if (a2) a2.classList.toggle("active", state.mode === "ARCADE");
    if (r2) r2.classList.toggle("active", state.mode === "ROGUELIKE");
    bus?.emit?.("zombies:mode", { mode: state.mode });
  }

  function setMap(mp) {
    state.map = (String(mp) === "Astra") ? "Astra" : "Ashes";
    const seg = qs("segZMap");
    if (seg) {
      const btns = Array.from(seg.querySelectorAll(".seg-btn"));
      for (const b of btns) b.classList.toggle("active", b.getAttribute("data-value") === state.map);
    }
    bus?.emit?.("zombies:map", { map: state.map });
  }

  function startGame() {
    Takeover.enter();
    const ok = window.BCO.engine?.start?.({
      mode: state.mode === "ROGUELIKE" ? "roguelike" : "arcade",
      map: state.map
    });
    if (!ok) {
      Takeover.exit();
      console.warn("[Z_RUNTIME] engine start failed");
      return;
    }
    bus?.emit?.("zombies:started", { ...state });
  }

  function stopGame() {
    window.BCO.engine?.stop?.();
    Takeover.exit();
    bus?.emit?.("zombies:stopped", {});
  }

  // Expose runtime API
  window.BCO.zombies = window.BCO.zombies || {};
  window.BCO.zombies.runtime = { startGame, stopGame, setMode, setMap, getState: () => ({ ...state }) };

  // Bind UI (NO redesign)
  function bind() {
    qs("btnZModeArcade")?.addEventListener("click", () => setMode("ARCADE"), { passive: true });
    qs("btnZModeRogue")?.addEventListener("click", () => setMode("ROGUELIKE"), { passive: true });
    qs("btnZModeArcade2")?.addEventListener("click", () => setMode("ARCADE"), { passive: true });
    qs("btnZModeRogue2")?.addEventListener("click", () => setMode("ROGUELIKE"), { passive: true });

    qs("btnZEnterGame")?.addEventListener("click", startGame, { passive: true });

    const seg = qs("segZMap");
    if (seg) {
      seg.addEventListener("click", (e) => {
        const b = e.target && e.target.closest ? e.target.closest(".seg-btn") : null;
        if (!b) return;
        setMap(b.getAttribute("data-value"));
      }, { passive: true });
    }

    // Escape exit
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape") stopGame();
    });

    // If app becomes visible again during takeover, re-hide TG chrome
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) {
        const cls = (CFG.FULLSCREEN && CFG.FULLSCREEN.TAKEOVER_CLASS) || "bco-game-takeover";
        if (document.body.classList.contains(cls)) {
          try {
            const wa = tg();
            wa?.MainButton?.hide?.();
            wa?.BackButton?.hide?.();
          } catch {}
        }
      }
    });
  }

  window.BCO.zombies.runtime._bind = bind;
})();
