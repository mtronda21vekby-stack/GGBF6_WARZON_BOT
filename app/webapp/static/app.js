// app/webapp/static/app.js
// BCO App Entry — STABLE UI (DO NOT TOUCH VISUAL) + iOS FastTap + Proper Takeover
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

  // ------------------------------------------------------------
  // 1) Tabs (UI only, no visual changes)
  // ------------------------------------------------------------
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

    try { location.hash = "#" + name; } catch {}
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

    const h = (location.hash || "").replace("#", "");
    if (h && q("tab-" + h)) setTab(h);
    else setTab("home");
  }

  // ------------------------------------------------------------
  // 2) iOS FastTap (fix "buttons not responding")
  // - Works for ALL buttons/links + any element with role=button
  // - Does NOT break scroll inside modal areas
  // - Prevents ghost double fire
  // ------------------------------------------------------------
  const FastTap = (() => {
    const MODAL_SCROLL_SEL = ".bco-modal-scroll, .modal, .modal-body, [role='dialog'], .allow-scroll";
    const TAP_MAX_MOVE = 14;
    const TAP_MAX_MS = 450;

    let active = null; // {t0,x0,y0,target,moved}
    let lastFireAt = 0;

    function withinScrollable(target) {
      return !!(target && target.closest && target.closest(MODAL_SCROLL_SEL));
    }

    function isInteractive(target) {
      if (!target) return false;

      // If inside scroll modal, allow native (don't hijack)
      if (withinScrollable(target)) return false;

      const el = target.closest ? target.closest("button,a,[role='button'],input,textarea,select,label") : null;
      if (el) return true;

      // Any element with click handler attributes / dataset that your app uses
      if (target.closest && target.closest("[data-tab],[data-action],[data-route],[data-z]")) return true;

      return false;
    }

    function getPoint(ev) {
      if (ev.changedTouches && ev.changedTouches[0]) return ev.changedTouches[0];
      if (ev.touches && ev.touches[0]) return ev.touches[0];
      return ev;
    }

    function onDown(ev) {
      const t = ev.target;
      if (!isInteractive(t)) return;

      const p = getPoint(ev);
      active = {
        t0: Date.now(),
        x0: p.clientX || 0,
        y0: p.clientY || 0,
        moved: false,
        target: t
      };
    }

    function onMove(ev) {
      if (!active) return;
      const p = getPoint(ev);
      const x = p.clientX || 0;
      const y = p.clientY || 0;
      const dx = x - active.x0;
      const dy = y - active.y0;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist > TAP_MAX_MOVE) active.moved = true;
    }

    function fireClick(target, ev) {
      const now = Date.now();
      if (now - lastFireAt < 220) return; // anti double-fire
      lastFireAt = now;

      const el =
        (target && target.closest && target.closest("button,a,[role='button'],[data-tab],[data-action],[data-route],[data-z]"))
        || target;

      if (!el) return;

      // We trigger native click reliably
      safe(() => el.click());
    }

    function onUp(ev) {
      if (!active) return;

      const dt = Date.now() - active.t0;
      const okTap = (dt <= TAP_MAX_MS) && !active.moved;
      const t = ev.target || active.target;

      active = null;

      if (!okTap) return;
      if (!isInteractive(t)) return;

      // Prevent iOS "sometimes no click" + stop ghost chain
      safe(() => ev.preventDefault());
      safe(() => ev.stopPropagation());

      fireClick(t, ev);
    }

    function mount() {
      // Pointer first
      document.addEventListener("pointerdown", onDown, { capture: true, passive: false });
      document.addEventListener("pointermove", onMove, { capture: true, passive: false });
      document.addEventListener("pointerup", onUp, { capture: true, passive: false });
      document.addEventListener("pointercancel", () => { active = null; }, { capture: true, passive: true });

      // Touch fallback
      document.addEventListener("touchstart", onDown, { capture: true, passive: false });
      document.addEventListener("touchmove", onMove, { capture: true, passive: false });
      document.addEventListener("touchend", onUp, { capture: true, passive: false });
      document.addEventListener("touchcancel", () => { active = null; }, { capture: true, passive: true });

      return true;
    }

    return { mount };
  })();

  // ------------------------------------------------------------
  // 3) Takeover (DO NOT KILL main UI полностью)
  // - Hide only header/nav/footer (visual unchanged)
  // - Keep main in DOM so game overlays/handlers still work
  // - zOverlayMount pointer events: off in UI, on in takeover
  // ------------------------------------------------------------
  const Takeover = (() => {
    const takeoverClass = "bco-game-takeover";
    const activeClass = "bco-game-active";

    function hideTG(on) {
      if (!TG) return;
      safe(() => TG.ready());
      safe(() => TG.expand());
      safe(() => TG.MainButton?.hide?.());
      safe(() => TG.BackButton?.hide?.());
      if (on) safe(() => TG.enableClosingConfirmation?.());
      else safe(() => TG.disableClosingConfirmation?.());
      safe(() => window.BCO_TG?.applyInsets?.());
    }

    function setOverlayPointer(on) {
      const mount = q("zOverlayMount");
      if (!mount) return;
      // In UI: must not block clicks
      // In game: allow overlays/controls to be clickable
      mount.style.pointerEvents = on ? "auto" : "none";
    }

    function hideChrome(on) {
      const header = document.querySelector("header.app-header");
      const nav = document.querySelector("nav.bottom-nav");
      const foot = document.querySelector("footer.foot");

      if (on) {
        if (header) header.style.display = "none";
        if (nav) nav.style.display = "none";
        if (foot) foot.style.display = "none";
      } else {
        if (header) header.style.display = "";
        if (nav) nav.style.display = "";
        if (foot) foot.style.display = "";
      }
    }

    function enter() {
      document.body.classList.add(takeoverClass);
      document.body.classList.add(activeClass);

      hideTG(true);
      hideChrome(true);
      setOverlayPointer(true);
    }

    function exit() {
      document.body.classList.remove(takeoverClass);
      document.body.classList.remove(activeClass);

      setOverlayPointer(false);
      hideChrome(false);
      hideTG(false);

      // Keep TG minimal for app design
      safe(() => window.BCO_TG?.hideChrome?.());
    }

    function isActive() {
      return document.body.classList.contains(takeoverClass);
    }

    return { enter, exit, isActive };
  })();

  // ------------------------------------------------------------
  // 4) Zombies start (legacy-first, then fallbacks)
  // ------------------------------------------------------------
  const ZState = { mode: "arcade", map: "Ashes" };

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

  function startZombies() {
    ZState.mode = readZModeFromUI();
    ZState.map = readZMapFromUI();

    // 0) Enter takeover FIRST (so overlays can receive input)
    Takeover.enter();

    // 1) Prefer your legacy zombies.init.js entrypoints (UNKNOWN names => try many)
    const ZINIT = window.BCO_ZOMBIES_INIT || window.BCO_ZOMBIES_INITER || window.BCO_ZOMBIES_BOOT || window.ZOMBIES_INIT || null;

    const ok1 =
      safe(() => ZINIT?.startGame?.(ZState.mode, { map: ZState.map })) ??
      safe(() => ZINIT?.start?.(ZState.mode, { map: ZState.map })) ??
      safe(() => ZINIT?.enter?.(ZState.mode, { map: ZState.map })) ??
      safe(() => ZINIT?.run?.(ZState.mode, { map: ZState.map })) ??
      undefined;

    if (ok1 !== undefined) return true;

    // 2) If you have BCO_ZOMBIES_GAME runner that needs canvas, do that
    const CORE = window.BCO_ZOMBIES_CORE || null;
    const ZGAME = window.BCO_ZOMBIES_GAME || null;

    if (!CORE || !ZGAME) {
      warn("Zombies missing CORE or GAME runner", { CORE: !!CORE, ZGAME: !!ZGAME });
      Takeover.exit();
      return false;
    }

    // Ensure canvas exists in overlay mount
    const mount = q("zOverlayMount");
    if (!mount) {
      Takeover.exit();
      return false;
    }

    let canvas = mount.querySelector("#bcoZCanvas");
    if (!canvas) {
      canvas = document.createElement("canvas");
      canvas.id = "bcoZCanvas";
      canvas.style.position = "fixed";
      canvas.style.left = "0";
      canvas.style.top = "0";
      canvas.style.width = "100vw";
      canvas.style.height = "100vh";
      canvas.style.zIndex = "9999";
      canvas.style.background = "transparent";
      canvas.style.display = "block";
      // IMPORTANT: keep canvas non-interactive; your joysticks/overlays handle input
      canvas.style.pointerEvents = "none";
      mount.appendChild(canvas);
    } else {
      canvas.style.display = "block";
    }

    // Size
    const dpr = Math.max(1, Math.min(3, window.devicePixelRatio || 1));
    const pxW = Math.floor(window.innerWidth * dpr);
    const pxH = Math.floor(window.innerHeight * dpr);
    canvas.width = pxW;
    canvas.height = pxH;

    safe(() => ZGAME.setCanvas?.(canvas));
    safe(() => ZGAME.setInGame?.(true));

    const tms = (performance && performance.now) ? performance.now() : Date.now();

    // core.start(mode, w, h, opts, tms) — use CSS px for core contract
    safe(() => CORE.start?.(ZState.mode, Math.floor(window.innerWidth), Math.floor(window.innerHeight), { map: ZState.map }, tms));

    // ✅ ZOOM contract +0.5 delta
    safe(() => CORE.setZoomDelta?.(+0.5));

    safe(() => ZGAME.startLoop?.());
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

    Takeover.exit();
  }

  // ------------------------------------------------------------
  // 5) Bind UI buttons (no redesign)
  // ------------------------------------------------------------
  function bindButtons() {
    // Zombies launch from Home
    q("btnPlayZombies")?.addEventListener("click", () => {
      setTab("game");
      startZombies();
    }, { passive: true });

    // Zombies launch from Game tab
    q("btnZQuickPlay")?.addEventListener("click", startZombies, { passive: true });
    q("btnZEnterGame")?.addEventListener("click", startZombies, { passive: true });

    // Mode toggles (UI class only)
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

    // Map select
    q("segZMap")?.addEventListener("click", (e) => {
      const b = e.target && e.target.closest ? e.target.closest(".seg-btn") : null;
      if (!b) return;
      for (const x of qa("#segZMap .seg-btn")) x.classList.toggle("active", x === b);
    }, { passive: true });

    // Close
    q("btnClose")?.addEventListener("click", () => safe(() => TG?.close?.()), { passive: true });

    // Escape/back stop
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && Takeover.isActive()) stopZombies();
    }, { passive: true });

    window.addEventListener("popstate", () => {
      if (Takeover.isActive()) stopZombies();
    });
  }

  // ------------------------------------------------------------
  // 6) Init
  // ------------------------------------------------------------
  function init() {
    setHealth("js: app init…");

    // IMPORTANT: overlay must NEVER block UI clicks when not in game
    const mount = q("zOverlayMount");
    if (mount) mount.style.pointerEvents = "none";

    // Keep TG minimal (your design)
    safe(() => window.BCO_TG?.hideChrome?.());

    // Mount fast tap (this is the iOS fix for unresponsive buttons)
    FastTap.mount();

    bindTabs();
    bindButtons();

    window.__BCO_JS_OK__ = true;
    setHealth("js: OK");
    log("OK: FastTap + Tabs + Takeover separated");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }

  // Export minimal API (debug)
  window.BCO_APP = { setTab, startZombies, stopZombies };
})();
