// app/webapp/static/app.js
// BCO App Entry — RESTORE STABLE (LEGACY zombies.*) + Tabs + Buttons
(() => {
  "use strict";

  const log = (...a) => { try { console.log("[BCO_APP]", ...a); } catch {} };
  const warn = (...a) => { try { console.warn("[BCO_APP]", ...a); } catch {} };

  const TG = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;

  function q(id) { return document.getElementById(id); }
  function qa(sel) { return Array.from(document.querySelectorAll(sel)); }
  function safe(fn) { try { return fn(); } catch { return undefined; } }

  function setHealth(msg) {
    const el = q("jsHealth");
    if (el) el.textContent = String(msg || "");
  }

  // -------------------------
  // Tabs (restore full UI)
  // -------------------------
  function setTab(name) {
    const panes = qa(".tabpane");
    const navs = qa(".bottom-nav .nav-btn");

    for (const p of panes) {
      const ok = p.id === ("tab-" + name);
      p.classList.toggle("active", ok);
    }

    for (const b of navs) {
      const ok = b.getAttribute("data-tab") === name;
      b.classList.toggle("active", ok);
      b.setAttribute("aria-selected", ok ? "true" : "false");
    }

    // keep in URL hash (nice for debug)
    try { location.hash = "#"+name; } catch {}
  }

  function bindTabs() {
    const nav = document.querySelector(".bottom-nav");
    if (!nav) return;

    nav.addEventListener("click", (e) => {
      const b = e.target && e.target.closest ? e.target.closest(".nav-btn") : null;
      if (!b) return;
      const name = b.getAttribute("data-tab") || "home";
      setTab(name);
    }, { passive: true });

    // initial
    const h = (location.hash || "").replace("#", "");
    if (h && q("tab-" + h)) setTab(h);
    else setTab("home");
  }

  // -------------------------
  // Zombies start (LEGACY)
  // tries every known API, then hard fallback.
  // -------------------------
  const ZState = { mode: "arcade", map: "Ashes", inGame: false };

  function readZModeFromUI() {
    const r = q("btnZModeRogue2");
    const isRogue = !!(r && r.classList.contains("active"));
    return isRogue ? "roguelike" : "arcade";
  }

  function readZMapFromUI() {
    const seg = q("segZMap");
    if (!seg) return "Ashes";
    const b = seg.querySelector(".seg-btn.active");
    const v = b ? (b.getAttribute("data-value") || "Ashes") : "Ashes";
    return (v === "Astra") ? "Astra" : "Ashes";
  }

  function hideAppUI(on) {
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

  function ensureGameCanvas() {
    const mount = q("zOverlayMount");
    if (!mount) return null;

    let c = mount.querySelector("#bcoZCanvas");
    if (!c) {
      c = document.createElement("canvas");
      c.id = "bcoZCanvas";
      c.style.position = "fixed";
      c.style.left = "0";
      c.style.top = "0";
      c.style.width = "100vw";
      c.style.height = "100vh";
      c.style.zIndex = "9999";
      c.style.background = "transparent";
      c.style.display = "none";
      // input/joysticks are handled by your zombies.init.js overlays; canvas itself no pointer
      c.style.pointerEvents = "none";
      mount.appendChild(c);
    }
    return c;
  }

  function startZombies() {
    ZState.mode = readZModeFromUI();
    ZState.map = readZMapFromUI();

    // always hide TG chrome during game
    safe(() => window.BCO_TG?.hideChrome?.());
    safe(() => TG?.MainButton?.hide?.());
    safe(() => TG?.BackButton?.hide?.());

    // Preferred: your legacy init module (if it has an entry)
    const ZINIT = window.BCO_ZOMBIES_INIT || window.BCO_ZOMBIES_INITER || window.BCO_ZOMBIES_BOOT || null;
    const ZGAME = window.BCO_ZOMBIES_GAME || null;
    const CORE = window.BCO_ZOMBIES_CORE || null;

    // Try “init/start” style
    if (ZINIT) {
      const ok =
        safe(() => ZINIT.startGame?.(ZState.mode, { map: ZState.map })) ??
        safe(() => ZINIT.start?.(ZState.mode, { map: ZState.map })) ??
        safe(() => ZINIT.enter?.(ZState.mode, { map: ZState.map })) ??
        null;

      if (ok !== null) {
        ZState.inGame = true;
        hideAppUI(true);
        return true;
      }
    }

    // Try runtime (if exists but without NEW stack dependence)
    const RT = window.BCO_ZOMBIES_RUNTIME || window.BCO?.zombies?.runtime || null;
    if (RT) {
      safe(() => RT.setMode?.(ZState.mode));
      safe(() => RT.setMap?.(ZState.map));
      const ok = safe(() => RT.startGame?.()) ?? safe(() => RT.start?.());
      if (ok !== undefined) {
        ZState.inGame = true;
        hideAppUI(true);
        return true;
      }
    }

    // Hard fallback: directly start CORE + runner
    if (!CORE || !ZGAME) {
      warn("Zombies missing CORE or GAME runner", { CORE: !!CORE, ZGAME: !!ZGAME });
      return false;
    }

    const canvas = ensureGameCanvas();
    if (!canvas) return false;

    // size
    const dpr = Math.max(1, Math.min(3, window.devicePixelRatio || 1));
    const w = Math.floor(window.innerWidth * dpr);
    const h = Math.floor(window.innerHeight * dpr);
    canvas.width = w;
    canvas.height = h;
    canvas.style.display = "block";

    safe(() => ZGAME.setCanvas?.(canvas));
    safe(() => ZGAME.setInGame?.(true));

    const tms = (performance && performance.now) ? performance.now() : Date.now();

    // core.start(mode, w, h, opts, tms) — твой контракт
    safe(() => CORE.start?.(ZState.mode, Math.floor(window.innerWidth), Math.floor(window.innerHeight), { map: ZState.map }, tms));

    // ✅ ZOOM contract: +0.5 delta (если есть API)
    safe(() => CORE.setZoomDelta?.(+0.5));

    safe(() => ZGAME.startLoop?.());

    ZState.inGame = true;
    hideAppUI(true);

    // back/escape exits
    const onKey = (e) => { if (e.key === "Escape") stopZombies(); };
    window.addEventListener("keydown", onKey, { passive: true });

    return true;
  }

  function stopZombies() {
    const ZINIT = window.BCO_ZOMBIES_INIT || null;
    const ZGAME = window.BCO_ZOMBIES_GAME || null;
    const CORE = window.BCO_ZOMBIES_CORE || null;

    safe(() => ZINIT?.stopGame?.());
    safe(() => ZINIT?.stop?.());

    safe(() => ZGAME?.setInGame?.(false));
    safe(() => ZGAME?.stopLoop?.());
    safe(() => CORE?.stop?.());

    const c = q("bcoZCanvas");
    if (c) c.style.display = "none";

    hideAppUI(false);
    ZState.inGame = false;

    // keep TG chrome hidden (your app design)
    safe(() => window.BCO_TG?.hideChrome?.());
  }

  // -------------------------
  // Simple sendData helpers
  // -------------------------
  function sendData(obj) {
    if (!TG || !TG.sendData) return false;
    try {
      TG.sendData(JSON.stringify(obj));
      return true;
    } catch {
      return false;
    }
  }

  // -------------------------
  // Bind buttons
  // -------------------------
  function bindButtons() {
    // zombies launch
    q("btnPlayZombies")?.addEventListener("click", () => {
      setTab("game");
      safe(() => startZombies());
    }, { passive: true });

    q("btnZQuickPlay")?.addEventListener("click", () => { safe(() => startZombies()); }, { passive: true });
    q("btnZEnterGame")?.addEventListener("click", () => { safe(() => startZombies()); }, { passive: true });

    // mode buttons (UI only)
    function setModeUI(isRogue) {
      q("btnZModeArcade")?.classList.toggle("active", !isRogue);
      q("btnZModeRogue")?.classList.toggle("active", isRogue);
      q("btnZModeArcade2")?.classList.toggle("active", !isRogue);
      q("btnZModeRogue2")?.classList.toggle("active", isRogue);
    }
    q("btnZModeArcade")?.addEventListener("click", () => setModeUI(false), { passive: true });
    q("btnZModeArcade2")?.addEventListener("click", () => setModeUI(false), { passive: true });
    q("btnZModeRogue")?.addEventListener("click", () => setModeUI(true), { passive: true });
    q("btnZModeRogue2")?.addEventListener("click", () => setModeUI(true), { passive: true });

    // map seg
    q("segZMap")?.addEventListener("click", (e) => {
      const b = e.target && e.target.closest ? e.target.closest(".seg-btn") : null;
      if (!b) return;
      const v = b.getAttribute("data-value") || "Ashes";
      for (const x of qa("#segZMap .seg-btn")) x.classList.toggle("active", x === b);
      ZState.map = (v === "Astra") ? "Astra" : "Ashes";
    }, { passive: true });

    // send result
    q("btnZGameSend")?.addEventListener("click", () => {
      const snap = safe(() => window.BCO_ZOMBIES_GAME?.getSnapshot?.()) || null;
      sendData({ action: "game_result", game: "zombies", snap });
    }, { passive: true });

    q("btnZGameSend2")?.addEventListener("click", () => {
      const snap = safe(() => window.BCO_ZOMBIES_GAME?.getSnapshot?.()) || null;
      sendData({ action: "game_result", game: "zombies", snap });
    }, { passive: true });

    // close
    q("btnClose")?.addEventListener("click", () => safe(() => TG?.close?.()), { passive: true });
  }

  function init() {
    setHealth("js: app init…");

    // keep chrome hidden (your app)
    safe(() => window.BCO_TG?.hideChrome?.());

    bindTabs();
    bindButtons();

    window.__BCO_JS_OK__ = true;
    setHealth("js: OK (restored)");
    log("RESTORED: legacy boot + tabs + zombies start");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }

  // expose minimal control
  window.BCO_APP = { startZombies, stopZombies, setTab };
})();
