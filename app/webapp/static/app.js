// app/webapp/static/app.js
// BCO Mini App v3.0.0 (Elite Bootstrap)
// - No UI redesign (only click/scroll/fullscreen hardening)
// - 100% iOS WebView reliable taps
// - Binder for your existing DOM (ids / data-tab)
// - Engine adapter for BCO_ZOMBIES_CORE + future render plugins
// - Zoom contract: +0.5 bump (uses CORE.setZoomDelta(0.5))

(() => {
  "use strict";

  // =========================
  // CONFIG (local, to avoid extra files)
  // =========================
  const CONFIG = {
    VERSION: "3.0.0-elite-bootstrap",
    STORAGE_KEY: "bco_state_v1",
    MAX_PAYLOAD_SIZE: 15000,

    INPUT: {
      TAP_MAX_MOVE_PX: 12,
      TAP_MAX_MS: 450,
      CAPTURE: true,
    },

    FULLSCREEN: {
      LOCK_BODY_SCROLL: true,
      PREVENT_PINCH: true,
      PREVENT_DOUBLE_TAP_ZOOM: true,
      TAKEOVER_CLASS: "bco-game-takeover",
      TAKEOVER_ACTIVE_CLASS: "bco-game-active",
    },

    ZOOM_BUMP: 0.5, // contract
    DEFAULT_VOICE: "TEAMMATE", // contract
  };

  // =========================
  // Utils
  // =========================
  const log = {
    info: (...a) => console.log("[BCO]", ...a),
    warn: (...a) => console.warn("[BCO]", ...a),
    error: (...a) => console.error("[BCO]", ...a),
  };

  const nowMs = () => Date.now();

  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

  const safeJsonParse = (s, fallback) => {
    try { return JSON.parse(s); } catch { return fallback; }
  };

  const safeJsonStringify = (o, fallback = "{}") => {
    try { return JSON.stringify(o); } catch { return fallback; }
  };

  const isIOS = () => {
    const ua = navigator.userAgent || "";
    const iOS = /iPad|iPhone|iPod/.test(ua);
    const iPadOS13 = (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
    return iOS || iPadOS13;
  };

  const tg = () => (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;

  const qs = (id) => document.getElementById(id);

  function setHealth(msg) {
    const el = qs("jsHealth");
    if (el) el.textContent = msg;
  }

  // =========================
  // Store (local + TG CloudStorage best-effort)
  // =========================
  const STORE = (() => {
    const KEY = CONFIG.STORAGE_KEY;

    async function load() {
      let base = safeJsonParse(localStorage.getItem(KEY) || "{}", {});
      const wa = tg();
      if (wa && wa.CloudStorage) {
        const cloudVal = await new Promise((resolve) => {
          wa.CloudStorage.getItem(KEY, (err, val) => resolve(err ? null : val));
        });
        const cloudObj = cloudVal ? safeJsonParse(cloudVal, null) : null;
        if (cloudObj && typeof cloudObj === "object") base = { ...base, ...cloudObj };
      }
      return base;
    }

    async function save(obj) {
      localStorage.setItem(KEY, safeJsonStringify(obj, "{}"));
      const wa = tg();
      if (wa && wa.CloudStorage) {
        await new Promise((resolve) => {
          wa.CloudStorage.setItem(KEY, safeJsonStringify(obj, "{}"), () => resolve(true));
        });
      }
      return true;
    }

    async function get(path, fallback) {
      const obj = await load();
      const parts = String(path || "").split(".").filter(Boolean);
      let cur = obj;
      for (const k of parts) {
        if (!cur || typeof cur !== "object" || !(k in cur)) return fallback;
        cur = cur[k];
      }
      return cur ?? fallback;
    }

    async function set(path, value) {
      const obj = await load();
      const parts = String(path || "").split(".").filter(Boolean);
      if (!parts.length) return false;
      let cur = obj;
      for (let i = 0; i < parts.length - 1; i++) {
        const k = parts[i];
        if (!cur[k] || typeof cur[k] !== "object") cur[k] = {};
        cur = cur[k];
      }
      cur[parts[parts.length - 1]] = value;
      await save(obj);
      return true;
    }

    async function patch(p) {
      const obj = await load();
      const merged = { ...obj, ...(p || {}) };
      await save(merged);
      return true;
    }

    return { load, save, get, set, patch };
  })();

  // =========================
  // Telegram hardening (reuse your BCO_TG if present)
  // =========================
  function tgReadyMinimal() {
    const wa = tg();
    if (!wa) return;
    try {
      wa.ready();
      wa.expand();
      try { wa.MainButton?.hide?.(); } catch {}
      try { wa.BackButton?.hide?.(); } catch {}
    } catch (e) {
      log.warn("tgReadyMinimal failed", e);
    }
  }

  // =========================
  // Gesture Guard (we keep it minimal; your index already blocks pinch)
  // =========================
  function installGestureGuard() {
    // Only add takeover classes behavior & touch-action hints (no UI redesign)
    const st = document.createElement("style");
    st.id = "bco-gesture-guard-v3";
    st.textContent = `
      .${CONFIG.FULLSCREEN.TAKEOVER_CLASS}, .${CONFIG.FULLSCREEN.TAKEOVER_CLASS} * { touch-action: none; }
      .bco-modal-scroll, .bco-modal-scroll * { touch-action: pan-y; }
    `;
    document.head.appendChild(st);

    // Prevent iOS rubber-band ONLY during takeover (do not kill normal UI)
    document.addEventListener("touchmove", (e) => {
      if (!document.body.classList.contains(CONFIG.FULLSCREEN.TAKEOVER_CLASS)) return;
      const t = e.target;
      if (t && t.closest && t.closest(".bco-modal-scroll")) return;
      e.preventDefault();
    }, { passive: false, capture: true });

    // Double-tap zoom prevention during takeover (extra safety; index already has global)
    if (CONFIG.FULLSCREEN.PREVENT_DOUBLE_TAP_ZOOM && isIOS()) {
      let lastEnd = 0;
      document.addEventListener("touchend", (e) => {
        if (!document.body.classList.contains(CONFIG.FULLSCREEN.TAKEOVER_CLASS)) return;
        const n = Date.now();
        if (n - lastEnd <= 280) e.preventDefault();
        lastEnd = n;
      }, { passive: false, capture: true });
    }
  }

  // =========================
  // Pointer Router (100% reliable taps)
  // - We do NOT require data-action in HTML; we bind by ids & tabs.
  // =========================
  const PointerRouter = (() => {
    const cfg = CONFIG.INPUT;
    let active = null;

    function withinScrollAllowed(target) {
      return !!(target && target.closest && target.closest(".bco-modal-scroll"));
    }

    function isInteractive(target) {
      if (!target) return false;
      const tag = (target.tagName || "").toLowerCase();
      if (tag === "button" || tag === "a" || tag === "input" || tag === "textarea") return true;
      if (target.closest && target.closest("button,a,[role='button']")) return true;
      return false;
    }

    function onDown(ev) {
      const target = ev.target;
      if (!isInteractive(target)) return;
      if (withinScrollAllowed(target)) return;

      const x = ev.clientX || (ev.touches && ev.touches[0] && ev.touches[0].clientX) || 0;
      const y = ev.clientY || (ev.touches && ev.touches[0] && ev.touches[0].clientY) || 0;

      active = {
        t0: nowMs(),
        x0: x,
        y0: y,
        moved: false,
        target,
        canceled: false,
      };
    }

    function onMove(ev) {
      if (!active || active.canceled) return;
      const x = ev.clientX || (ev.touches && ev.touches[0] && ev.touches[0].clientX) || 0;
      const y = ev.clientY || (ev.touches && ev.touches[0] && ev.touches[0].clientY) || 0;
      const dx = x - active.x0;
      const dy = y - active.y0;
      const dist = Math.hypot(dx, dy);
      if (dist > (cfg.TAP_MAX_MOVE_PX || 12)) active.moved = true;
    }

    function onUp(ev) {
      if (!active || active.canceled) return;
      const dt = nowMs() - active.t0;
      const ok = (dt <= (cfg.TAP_MAX_MS || 450)) && !active.moved;

      const target = ev.target || active.target;
      if (withinScrollAllowed(target)) { active = null; return; }

      // In takeover we want to kill ghost clicks (common in iOS)
      if (document.body.classList.contains(CONFIG.FULLSCREEN.TAKEOVER_CLASS) && ok) {
        try { ev.preventDefault(); } catch {}
        try { ev.stopPropagation(); } catch {}
      }

      active = null;
    }

    function onCancel() { active = null; }

    function mount() {
      const cap = !!cfg.CAPTURE;

      document.addEventListener("pointerdown", onDown, { capture: cap, passive: false });
      document.addEventListener("pointermove", onMove, { capture: cap, passive: false });
      document.addEventListener("pointerup", onUp, { capture: cap, passive: false });
      document.addEventListener("pointercancel", onCancel, { capture: cap, passive: false });

      document.addEventListener("touchstart", onDown, { capture: cap, passive: false });
      document.addEventListener("touchmove", onMove, { capture: cap, passive: false });
      document.addEventListener("touchend", onUp, { capture: cap, passive: false });
      document.addEventListener("touchcancel", onCancel, { capture: cap, passive: false });

      // Ghost click killer ONLY in takeover (so normal UI remains native)
      document.addEventListener("click", (e) => {
        if (!document.body.classList.contains(CONFIG.FULLSCREEN.TAKEOVER_CLASS)) return;
        const t = e.target;
        if (withinScrollAllowed(t)) return;
        e.preventDefault();
        e.stopPropagation();
      }, { capture: true, passive: false });
    }

    return { mount };
  })();

  // =========================
  // Engine Adapter (CORE-first, 3D-ready)
  // =========================
  const Engine = (() => {
    const state = {
      core: null,
      running: false,
      mode: "arcade",
      map: "Ashes",
      canvas: null,
      ctx: null,
      raf: 0,
      w: 0,
      h: 0,
    };

    function detect() {
      const core = window.BCO_ZOMBIES_CORE || null;
      state.core = core;
      return !!core;
    }

    function ensureCanvas() {
      const mount = qs("zOverlayMount");
      if (!mount) return null;

      // reuse if exists
      let c = mount.querySelector("canvas#bcoZCanvas");
      if (!c) {
        c = document.createElement("canvas");
        c.id = "bcoZCanvas";
        c.style.position = "fixed";
        c.style.left = "0";
        c.style.top = "0";
        c.style.width = "100vw";
        c.style.height = "100vh";
        c.style.zIndex = "9999";
        c.style.display = "none";
        c.style.background = "transparent";
        c.style.pointerEvents = "none"; // IMPORTANT: UI overlay handles input (joysticks inside game module if any)
        mount.appendChild(c);
      }
      state.canvas = c;
      state.ctx = c.getContext("2d", { alpha: true, desynchronized: true });
      return c;
    }

    function resizeCanvas() {
      if (!state.canvas) return;
      const dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
      const w = Math.floor(window.innerWidth * dpr);
      const h = Math.floor(window.innerHeight * dpr);
      if (w === state.w && h === state.h) return;
      state.w = w; state.h = h;
      state.canvas.width = w;
      state.canvas.height = h;
    }

    function start({ mode, map, zoomBump }) {
      if (!detect()) {
        log.error("BCO_ZOMBIES_CORE not found");
        return false;
      }
      ensureCanvas();
      resizeCanvas();

      state.mode = (String(mode || "").toLowerCase().includes("rogue")) ? "roguelike" : "arcade";
      state.map = map || "Ashes";

      const CORE = state.core;

      // Start CORE (signature: start(mode, w, h, opts, tms))
      CORE.start(state.mode, state.w, state.h, { map: state.map }, (performance && performance.now) ? performance.now() : Date.now());

      // Contract zoom bump: +0.5 to current
      if (typeof CORE.setZoomDelta === "function") {
        CORE.setZoomDelta(Number(zoomBump) || CONFIG.ZOOM_BUMP);
      } else if (typeof CORE.setZoomLevel === "function") {
        // fallback: getZoom + bump
        const cur = (typeof CORE.getZoom === "function") ? CORE.getZoom() : 1.0;
        CORE.setZoomLevel((Number(cur) || 1.0) + (Number(zoomBump) || CONFIG.ZOOM_BUMP));
      }

      // Show canvas
      state.canvas.style.display = "block";

      state.running = true;
      tickLoop();
      return true;
    }

    function stop() {
      state.running = false;
      if (state.raf) cancelAnimationFrame(state.raf);
      state.raf = 0;

      try { state.core?.stop?.(); } catch {}

      if (state.canvas) state.canvas.style.display = "none";
      return true;
    }

    // INPUT bridge (for now minimal: if your zombies.game.js owns dual-stick,
    // it can call CORE.setMove/setAim/setShooting itself. We keep adapter ready.)
    function setMove(x, y) { try { state.core?.setMove?.(x, y); } catch {} }
    function setAim(x, y) { try { state.core?.setAim?.(x, y); } catch {} }
    function setShooting(on) { try { state.core?.setShooting?.(on); } catch {} }
    function reload() { try { return !!state.core?.reload?.(); } catch { return false; } }

    function getFrame() {
      try { return state.core?.getFrameData?.(); } catch { return null; }
    }

    function update(tms) {
      try { state.core?.updateFrame?.(tms); } catch {}
    }

    // Render:
    // - Prefer your zombies.render.js if it exposes BCO_ZOMBIES_RENDER.renderFrame(frame, ctx, canvas)
    // - Else fallback to simple debug render (never breaks)
    function render(frame) {
      const R = window.BCO_ZOMBIES_RENDER || window.BCO_ZOMBIES_RENDERER || null;
      if (R && typeof R.renderFrame === "function") {
        R.renderFrame(frame, state.ctx, state.canvas);
        return;
      }
      if (R && typeof R.render === "function") {
        R.render(frame, state.ctx, state.canvas);
        return;
      }

      // fallback debug render
      const ctx = state.ctx;
      ctx.clearRect(0, 0, state.canvas.width, state.canvas.height);
      ctx.save();
      ctx.globalAlpha = 0.9;
      ctx.fillStyle = "rgba(0,0,0,0.35)";
      ctx.fillRect(18, 18, 360, 120);
      ctx.fillStyle = "rgba(255,255,255,0.92)";
      ctx.font = "24px system-ui, -apple-system, Inter, Arial";
      ctx.fillText("ZOMBIES DEBUG RENDER", 28, 52);
      if (frame && frame.hud) {
        ctx.font = "18px system-ui, -apple-system, Inter, Arial";
        ctx.fillText(`mode: ${frame.meta?.mode} map: ${frame.meta?.map}`, 28, 78);
        ctx.fillText(`wave: ${frame.hud.wave} kills: ${frame.hud.kills} coins: ${frame.hud.coins}`, 28, 102);
      }
      ctx.restore();
    }

    function tickLoop() {
      if (!state.running) return;
      resizeCanvas();

      const t = (performance && performance.now) ? performance.now() : Date.now();
      update(t);

      const frame = getFrame();
      render(frame);

      state.raf = requestAnimationFrame(tickLoop);
    }

    return { start, stop, setMove, setAim, setShooting, reload, getFrame };
  })();

  // =========================
  // Fullscreen Takeover (NO UI redesign; hide existing header/nav by class toggles)
  // =========================
  const Takeover = (() => {
    let savedScrollY = 0;

    function lockBodyScroll(on) {
      if (!(CONFIG.FULLSCREEN.LOCK_BODY_SCROLL)) return;

      if (on) {
        savedScrollY = window.scrollY || 0;
        document.body.style.position = "fixed";
        document.body.style.top = `-${savedScrollY}px`;
        document.body.style.left = "0";
        document.body.style.right = "0";
        document.body.style.width = "100%";
      } else {
        document.body.style.position = "";
        document.body.style.top = "";
        document.body.style.left = "";
        document.body.style.right = "";
        document.body.style.width = "";
        window.scrollTo(0, savedScrollY);
      }
    }

    function applyTG(on) {
      // use your BCO_TG API if present
      if (window.BCO_TG && typeof window.BCO_TG.hideChrome === "function") {
        if (on) window.BCO_TG.hideChrome();
        else window.BCO_TG.showChrome();
        return;
      }
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

    function setUIHidden(on) {
      // Do NOT change visuals; just temporarily hide existing UI containers
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
      document.body.classList.add(CONFIG.FULLSCREEN.TAKEOVER_CLASS);
      document.body.classList.add(CONFIG.FULLSCREEN.TAKEOVER_ACTIVE_CLASS);
      lockBodyScroll(true);
      applyTG(true);
      setUIHidden(true);
    }

    function exit() {
      document.body.classList.remove(CONFIG.FULLSCREEN.TAKEOVER_CLASS);
      document.body.classList.remove(CONFIG.FULLSCREEN.TAKEOVER_ACTIVE_CLASS);
      setUIHidden(false);
      applyTG(false);
      lockBodyScroll(false);
    }

    return { enter, exit };
  })();

  // =========================
  // Navigation Tabs binder (bottom nav data-tab)
  // =========================
  function navTo(tabName) {
    const panes = Array.from(document.querySelectorAll(".tabpane"));
    const btns = Array.from(document.querySelectorAll(".nav-btn"));

    for (const p of panes) {
      const is = p.id === `tab-${tabName}`;
      p.classList.toggle("active", is);
      if (is) p.setAttribute("aria-hidden", "false");
      else p.setAttribute("aria-hidden", "true");
    }

    for (const b of btns) {
      const t = b.getAttribute("data-tab");
      const is = t === tabName;
      b.classList.toggle("active", is);
      b.setAttribute("aria-selected", is ? "true" : "false");
    }
  }

  // =========================
  // Bot sendData wrapper (uses your profile)
  // =========================
  async function sendDataToBot(payload) {
    const wa = tg();
    const profile = await STORE.get("profile", {});
    const packet = {
      ...payload,
      profile,
      ts: Date.now(),
      v: CONFIG.VERSION,
    };

    const raw = safeJsonStringify(packet, "{}");
    if (raw.length > CONFIG.MAX_PAYLOAD_SIZE) {
      const fallback = safeJsonStringify({ type: "error", reason: "payload_too_large", ts: Date.now() });
      if (wa && typeof wa.sendData === "function") wa.sendData(fallback);
      return false;
    }

    if (wa && typeof wa.sendData === "function") {
      wa.sendData(raw);
      return true;
    }

    log.warn("Telegram sendData unavailable; payload:", packet);
    return false;
  }

  // =========================
  // DOM helpers: allow modal scroll class marking (fix dead scroll on iOS)
  // =========================
  function markModalScrollContainers() {
    // We do not change UI styles, only add a class if element is scrollable
    const candidates = Array.from(document.querySelectorAll(
      ".modal, .modal-content, [data-modal], [data-popup], [role='dialog']"
    ));

    for (const el of candidates) {
      const cs = window.getComputedStyle(el);
      const oy = cs.overflowY;
      if (oy === "auto" || oy === "scroll") {
        el.classList.add("bco-modal-scroll");
        el.style.webkitOverflowScrolling = "touch";
      }
    }
  }

  // =========================
  // Binder to YOUR ids
  // =========================
  const App = (() => {
    const state = {
      zombiesMode: "ARCADE", // UI buttons toggle this
      zombiesMap: "Ashes",
      lastZSnapshot: null,
    };

    function toast(msg) {
      const el = qs("toast");
      if (!el) return;
      el.textContent = String(msg || "OK");
      el.classList.add("show");
      setTimeout(() => el.classList.remove("show"), 1200);
    }

    function setChipVoiceText(v) {
      const chip = qs("chipVoice");
      if (!chip) return;
      chip.textContent = (v === "COACH") ? "📚 Коуч" : "🤝 Тиммейт";
      const sub = qs("chatSub");
      if (sub) {
        const mode = (qs("chipMode")?.textContent || "🧠 Normal").replace("🧠 ", "");
        const plat = (qs("chipPlatform")?.textContent || "🖥 PC").replace("🖥 ", "");
        sub.textContent = `${v} • ${mode} • ${plat}`;
      }
    }

    async function ensureDefaults() {
      const voice = await STORE.get("profile.voice", null);
      if (!voice) await STORE.set("profile.voice", CONFIG.DEFAULT_VOICE);
      setChipVoiceText(await STORE.get("profile.voice", CONFIG.DEFAULT_VOICE));
    }

    // --- Zombies mode/map UI
    function setZMode(mode) {
      state.zombiesMode = (mode === "ROGUELIKE") ? "ROGUELIKE" : "ARCADE";

      const b1 = qs("btnZModeArcade");
      const b2 = qs("btnZModeRogue");
      const b3 = qs("btnZModeArcade2");
      const b4 = qs("btnZModeRogue2");

      const setActive = (el, on) => { if (el) el.classList.toggle("active", !!on); };

      setActive(b1, state.zombiesMode === "ARCADE");
      setActive(b2, state.zombiesMode === "ROGUELIKE");
      setActive(b3, state.zombiesMode === "ARCADE");
      setActive(b4, state.zombiesMode === "ROGUELIKE");
    }

    function setZMap(map) {
      state.zombiesMap = (map === "Astra") ? "Astra" : "Ashes";
      const seg = qs("segZMap");
      if (!seg) return;
      const btns = Array.from(seg.querySelectorAll(".seg-btn"));
      for (const b of btns) {
        const v = b.getAttribute("data-value");
        b.classList.toggle("active", v === state.zombiesMap);
      }
    }

    // --- Enter Fullscreen Game
    function startFullscreenZombies() {
      // takeover
      Takeover.enter();

      // start engine (CORE)
      const ok = Engine.start({
        mode: state.zombiesMode,
        map: state.zombiesMap,
        zoomBump: CONFIG.ZOOM_BUMP, // contract +0.5
      });

      if (!ok) {
        toast("Zombies core not loaded");
        Takeover.exit();
        return;
      }

      toast(`Zombies: ${state.zombiesMode} • ${state.zombiesMap}`);
    }

    function stopFullscreenZombies() {
      Engine.stop();
      Takeover.exit();
      toast("Exit game");
    }

    // --- Snapshot send
    async function sendZombiesResult() {
      const frame = Engine.getFrame();
      // We keep it small and stable for bot
      const data = {
        mode: frame?.meta?.mode || (state.zombiesMode === "ROGUELIKE" ? "roguelike" : "arcade"),
        map: frame?.meta?.map || state.zombiesMap,
        hud: frame?.hud || null,
        ts: Date.now(),
      };
      state.lastZSnapshot = data;
      await sendDataToBot({ type: "game_result", game: "zombies", data });
      toast("Sent → bot");
    }

    // --- “Zombies HQ / guides” buttons (nav messages)
    async function openZombiesHQ(action) {
      // Your bot expects nav payload (you already fixed type=nav earlier)
      await sendDataToBot({ type: "nav", action: action || "zombies_hq" });
      toast("Sent → bot");
    }

    // --- Premium buy
    async function buyPremium(kind) {
      await sendDataToBot({ type: "premium", plan: kind });
      toast("Invoice → bot");
    }

    // --- Open bot menu
    async function openBotMenu() {
      await sendDataToBot({ type: "nav", action: "open_bot_menu" });
      toast("Open bot menu");
    }

    async function syncProfile() {
      const profile = await STORE.get("profile", {});
      await sendDataToBot({ type: "profile_sync", profile });
      toast("Sync → bot");
    }

    // --- Close WebApp
    function closeApp() {
      const wa = tg();
      if (wa && typeof wa.close === "function") wa.close();
      else toast("Close not available");
    }

    function bindNavTabs() {
      const nav = document.querySelector("nav.bottom-nav");
      if (!nav) return;

      nav.addEventListener("click", (e) => {
        const btn = e.target && e.target.closest ? e.target.closest(".nav-btn") : null;
        if (!btn) return;
        const tab = btn.getAttribute("data-tab");
        if (!tab) return;
        navTo(tab);
      }, { passive: true });
    }

    function bindButtons() {
      // HOME
      const btnOpenBot = qs("btnOpenBot");
      if (btnOpenBot) btnOpenBot.addEventListener("click", openBotMenu, { passive: true });

      const btnSync = qs("btnSync");
      if (btnSync) btnSync.addEventListener("click", syncProfile, { passive: true });

      const btnPremium = qs("btnPremium");
      if (btnPremium) btnPremium.addEventListener("click", () => sendDataToBot({ type: "nav", action: "premium_hub" }), { passive: true });

      const btnPlayZombies = qs("btnPlayZombies");
      if (btnPlayZombies) btnPlayZombies.addEventListener("click", () => { navTo("game"); }, { passive: true });

      // Top actions
      const btnClose = qs("btnClose");
      if (btnClose) btnClose.addEventListener("click", closeApp, { passive: true });

      const btnShare = qs("btnShare");
      if (btnShare) btnShare.addEventListener("click", () => sendDataToBot({ type: "share" }), { passive: true });

      // Premium
      const btnBuyMonth = qs("btnBuyMonth");
      if (btnBuyMonth) btnBuyMonth.addEventListener("click", () => buyPremium("month"), { passive: true });

      const btnBuyLife = qs("btnBuyLife");
      if (btnBuyLife) btnBuyLife.addEventListener("click", () => buyPremium("lifetime"), { passive: true });

      // Zombies preview panel (home)
      const btnZModeArcade = qs("btnZModeArcade");
      if (btnZModeArcade) btnZModeArcade.addEventListener("click", () => setZMode("ARCADE"), { passive: true });

      const btnZModeRogue = qs("btnZModeRogue");
      if (btnZModeRogue) btnZModeRogue.addEventListener("click", () => setZMode("ROGUELIKE"), { passive: true });

      const btnZQuickPlay = qs("btnZQuickPlay");
      if (btnZQuickPlay) btnZQuickPlay.addEventListener("click", () => { navTo("game"); }, { passive: true });

      const btnZGameSend = qs("btnZGameSend");
      if (btnZGameSend) btnZGameSend.addEventListener("click", sendZombiesResult, { passive: true });

      // Game tab (launcher)
      const segZMap = qs("segZMap");
      if (segZMap) {
        segZMap.addEventListener("click", (e) => {
          const b = e.target && e.target.closest ? e.target.closest(".seg-btn") : null;
          if (!b) return;
          const v = b.getAttribute("data-value");
          if (!v) return;
          setZMap(v);
        }, { passive: true });
      }

      const btnZModeArcade2 = qs("btnZModeArcade2");
      if (btnZModeArcade2) btnZModeArcade2.addEventListener("click", () => setZMode("ARCADE"), { passive: true });

      const btnZModeRogue2 = qs("btnZModeRogue2");
      if (btnZModeRogue2) btnZModeRogue2.addEventListener("click", () => setZMode("ROGUELIKE"), { passive: true });

      const btnZEnterGame = qs("btnZEnterGame");
      if (btnZEnterGame) btnZEnterGame.addEventListener("click", startFullscreenZombies, { passive: true });

      const btnZGameSend2 = qs("btnZGameSend2");
      if (btnZGameSend2) btnZGameSend2.addEventListener("click", sendZombiesResult, { passive: true });

      const btnZOpenHQ = qs("btnZOpenHQ");
      if (btnZOpenHQ) btnZOpenHQ.addEventListener("click", () => openZombiesHQ("zombies_hq"), { passive: true });

      // Zombies HQ buttons
      const btnOpenZombies = qs("btnOpenZombies");
      if (btnOpenZombies) btnOpenZombies.addEventListener("click", () => openZombiesHQ("zombies_open"), { passive: true });

      const btnZPerks = qs("btnZPerks");
      if (btnZPerks) btnZPerks.addEventListener("click", () => openZombiesHQ("zombies_perks"), { passive: true });

      const btnZLoadout = qs("btnZLoadout");
      if (btnZLoadout) btnZLoadout.addEventListener("click", () => openZombiesHQ("zombies_loadout"), { passive: true });

      const btnZEggs = qs("btnZEggs");
      if (btnZEggs) btnZEggs.addEventListener("click", () => openZombiesHQ("zombies_easter_eggs"), { passive: true });

      const btnZRound = qs("btnZRound");
      if (btnZRound) btnZRound.addEventListener("click", () => openZombiesHQ("zombies_round_strategy"), { passive: true });

      const btnZTips = qs("btnZTips");
      if (btnZTips) btnZTips.addEventListener("click", () => openZombiesHQ("zombies_quick_tips"), { passive: true });

      // Emergency exit from takeover: hardware back / ESC
      window.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && document.body.classList.contains(CONFIG.FULLSCREEN.TAKEOVER_CLASS)) {
          stopFullscreenZombies();
        }
      });

      // Tap anywhere with 2-finger? (no — contract; keep simple)
    }

    function bindVoiceChips() {
      const chip = qs("chipVoice");
      if (!chip) return;

      chip.addEventListener("click", async () => {
        const cur = await STORE.get("profile.voice", CONFIG.DEFAULT_VOICE);
        const next = (cur === "COACH") ? "TEAMMATE" : "COACH";
        await STORE.set("profile.voice", next);
        setChipVoiceText(next);
        toast(next === "COACH" ? "COACH (elite)" : "TEAMMATE");
      }, { passive: true });
    }

    // Fullscreen exit on Telegram back button if needed (we keep BackButton hidden, but still safe)
    function bindTakeoverExitGestures() {
      // Long-press top-left? no UI change. We'll add a safe “tap 4 corners” hidden? — not now.
      // Instead: if user closes overlay via bot/back - we handle visibility.
      document.addEventListener("visibilitychange", () => {
        // if app backgrounded while in takeover, do not break
        if (document.hidden) return;
        if (document.body.classList.contains(CONFIG.FULLSCREEN.TAKEOVER_CLASS)) {
          // re-hide TG chrome
          try { window.BCO_TG?.hideChrome?.(); } catch {}
        }
      });
    }

    // Allow clicking on modals if they exist later (shop/character overlays inside game modules)
    function markModalsLoop() {
      let t = 0;
      const tick = () => {
        t++;
        if (t < 120) markModalScrollContainers();
        requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    }

    function setInitialState() {
      setZMode("ARCADE");
      setZMap("Ashes");
      navTo("home");
    }

    function start() {
      setHealth("js: app boot…");

      tgReadyMinimal();
      installGestureGuard();
      PointerRouter.mount();

      bindNavTabs();
      bindButtons();
      bindVoiceChips();
      bindTakeoverExitGestures();
      markModalsLoop();

      setInitialState();
      ensureDefaults();

      // expose for debug
      window.BCO_APP = {
        version: CONFIG.VERSION,
        sendDataToBot,
        startFullscreenZombies,
        stopFullscreenZombies,
        Engine,
        Takeover,
      };

      window.__BCO_JS_OK__ = true;
      setHealth("js: OK (app.js v3 booted)");
      log.info("Booted", CONFIG.VERSION);
    }

    return { start, stopFullscreenZombies };
  })();

  // =========================
  // Boot
  // =========================
  function boot() {
    try {
      App.start();

      // If CORE exists but render not, warn (still works)
      if (!window.BCO_ZOMBIES_CORE) log.warn("BCO_ZOMBIES_CORE not found at boot (check loader order)");
    } catch (e) {
      log.error("BCO app boot crash", e);
      setHealth("js: BOOT CRASH (console)");
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }

})();
