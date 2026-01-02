// app/webapp/static/app.js
// LUX Mini App controller (v1.4.0) — iOS-tap hardening + Zombies “Game Tab” full takeover
// - НЕ урезано: всё что было — оставлено
// - Улучшено: стабильные тапы (iOS WebView), правильный “переход в игру” (Zombies как отдельный Game-screen),
//             авто-open движка, нормальный Back (выход из игры), задел под 3D-рендер (bridge/hints)

(() => {
  "use strict";
  window.__BCO_JS_OK__ = true;

  const tg = window.Telegram?.WebApp;

  const VERSION = "1.4.0";
  const STORAGE_KEY = "bco_state_v1";
  const CHAT_KEY = "bco_chat_v1";

  // -------------------------
  // State
  // -------------------------
  const defaults = {
    game: "Warzone",
    focus: "aim",
    mode: "Normal",
    platform: "PC",
    input: "Controller",
    voice: "TEAMMATE",
    role: "Flex",
    bf6_class: "Assault",
    zombies_map: "Ashes",

    // ✅ Zombies character cosmetics
    character: "male", // male | female
    skin: "default" // depends on character
  };

  const state = { ...defaults };

  const chat = {
    history: [],
    lastAskAt: 0
  };

  // "home" | "training" | "vod" | "settings" | "zombies" | "coach"
  let currentTab = "home";

  const qs = (s) => document.querySelector(s);
  const qsa = (s) => Array.from(document.querySelectorAll(s));
  const now = () => Date.now();

  function safeJsonParse(s) {
    try { return JSON.parse(s); } catch { return null; }
  }

  // -------------------------
  // Haptics / toast
  // -------------------------
  function haptic(type = "impact", style = "medium") {
    try {
      if (!tg?.HapticFeedback) return;
      if (type === "impact") tg.HapticFeedback.impactOccurred(style);
      if (type === "notif") tg.HapticFeedback.notificationOccurred(style);
    } catch {}
  }

  function toast(text) {
    const t = qs("#toast");
    if (!t) return;
    t.textContent = text;
    t.classList.add("show");
    setTimeout(() => t.classList.remove("show"), 1600);
  }

  // =========================================================
  // ✅ ULTRA FAST TAP (iOS WebView SAFE) — no dead taps, no double fire
  // =========================================================
  // Причина “кнопки не нажимаются” в iOS WebView часто:
  // - конфликт pointer/click
  // - скролл/панорама (touch-action)
  // - passive listeners не дают preventDefault
  // - overlay ловит события
  //
  // Этот менеджер:
  // - слушает pointerdown/up (или touchstart/end) в CAPTURE
  // - делает короткий “lock” от дабл-таба
  // - ставит touch-action: manipulation (где можно)
  // - жёстко фильтрует multi-touch
  //
  // ВАЖНО: handler вызывается один раз на “подтверждённый” тап.
  function onTap(el, handler, opts = {}) {
    if (!el || typeof handler !== "function") return;

    const cfg = {
      lockMs: 220,
      moveTol: 14, // px
      prevent: true,
      ...opts
    };

    try {
      // helps iOS: faster, less “300ms click delay”
      el.style.touchAction = el.style.touchAction || "manipulation";
      el.style.webkitTapHighlightColor = "rgba(0,0,0,0)";
    } catch {}

    let locked = false;
    let startX = 0, startY = 0;
    let tracking = false;
    let pointerId = null;
    let startT = 0;

    const lock = () => {
      locked = true;
      setTimeout(() => (locked = false), cfg.lockMs);
    };

    const fire = (e) => {
      if (locked) return;
      lock();
      try { handler(e); } catch {}
    };

    const dist = (x1, y1, x2, y2) => Math.hypot(x1 - x2, y1 - y2);

    // Pointer path
    if (window.PointerEvent) {
      const onDown = (e) => {
        if (locked) return;
        // only primary pointer, no multi
        if (e.isPrimary === false) return;
        tracking = true;
        pointerId = e.pointerId;
        startX = e.clientX || 0;
        startY = e.clientY || 0;
        startT = now();
        if (cfg.prevent) { try { e.preventDefault(); } catch {} }
      };

      const onUp = (e) => {
        if (!tracking) return;
        if (pointerId !== null && e.pointerId !== pointerId) return;

        const x = e.clientX || 0;
        const y = e.clientY || 0;
        const d = dist(startX, startY, x, y);
        const dt = now() - startT;

        tracking = false;
        pointerId = null;

        // ignore drags
        if (d > cfg.moveTol) return;
        // ignore long press
        if (dt > 1200) return;

        if (cfg.prevent) { try { e.preventDefault(); } catch {} }
        fire(e);
      };

      const onCancel = () => { tracking = false; pointerId = null; };

      el.addEventListener("pointerdown", onDown, { capture: true, passive: false });
      el.addEventListener("pointerup", onUp, { capture: true, passive: false });
      el.addEventListener("pointercancel", onCancel, { capture: true, passive: true });

      // Fallback click (some edge cases)
      el.addEventListener("click", (e) => {
        // if pointer path already fired, lock blocks it
        if (cfg.prevent) { try { e.preventDefault(); } catch {} }
        fire(e);
      }, { capture: true, passive: false });

      return;
    }

    // Touch path
    const touchXY = (te) => {
      const t = te?.changedTouches?.[0] || te?.touches?.[0] || null;
      return { x: t?.clientX || 0, y: t?.clientY || 0, count: (te?.touches?.length || 0) };
    };

    const onTs = (e) => {
      if (locked) return;
      const p = touchXY(e);
      if (p.count > 1) return; // ignore multi-touch
      tracking = true;
      startX = p.x; startY = p.y;
      startT = now();
      if (cfg.prevent) { try { e.preventDefault(); } catch {} }
    };

    const onTe = (e) => {
      if (!tracking) return;
      const p = touchXY(e);
      tracking = false;

      const d = dist(startX, startY, p.x, p.y);
      const dt = now() - startT;

      if (d > cfg.moveTol) return;
      if (dt > 1200) return;

      if (cfg.prevent) { try { e.preventDefault(); } catch {} }
      fire(e);
    };

    el.addEventListener("touchstart", onTs, { capture: true, passive: false });
    el.addEventListener("touchend", onTe, { capture: true, passive: false });
    el.addEventListener("touchcancel", () => { tracking = false; }, { capture: true, passive: true });

    el.addEventListener("click", (e) => {
      if (cfg.prevent) { try { e.preventDefault(); } catch {} }
      fire(e);
    }, { capture: true, passive: false });
  }

  // -------------------------
  // Telegram theme
  // -------------------------
  function applyTelegramTheme() {
    if (!tg) return;
    const p = tg.themeParams || {};
    const root = document.documentElement;

    const map = {
      "--tg-bg": p.bg_color,
      "--tg-text": p.text_color,
      "--tg-hint": p.hint_color,
      "--tg-link": p.link_color,
      "--tg-btn": p.button_color,
      "--tg-btn-text": p.button_text_color,
      "--tg-secondary-bg": p.secondary_bg_color
    };
    Object.entries(map).forEach(([k, v]) => { if (v) root.style.setProperty(k, v); });

    const dbgTheme = qs("#dbgTheme");
    if (dbgTheme) dbgTheme.textContent = tg.colorScheme ?? "—";

    try { tg.setBackgroundColor?.(p.bg_color || "#07070b"); } catch {}
    try { tg.setHeaderColor?.(p.secondary_bg_color || p.bg_color || "#07070b"); } catch {}
  }

  // -------------------------
  // Cloud/local storage
  // -------------------------
  async function cloudGet(key) {
    if (!tg?.CloudStorage?.getItem) return null;
    return new Promise((resolve) => {
      tg.CloudStorage.getItem(key, (err, value) => {
        if (err) return resolve(null);
        resolve(value ?? null);
      });
    });
  }

  async function cloudSet(key, value) {
    if (!tg?.CloudStorage?.setItem) return false;
    return new Promise((resolve) => {
      tg.CloudStorage.setItem(key, value, (err) => resolve(!err));
    });
  }

  async function loadState() {
    const fromCloud = await cloudGet(STORAGE_KEY);
    const parsedCloud = fromCloud ? safeJsonParse(fromCloud) : null;
    if (parsedCloud && typeof parsedCloud === "object") {
      Object.assign(state, defaults, parsedCloud);
      return "cloud";
    }

    const fromLocal = localStorage.getItem(STORAGE_KEY);
    const parsedLocal = fromLocal ? safeJsonParse(fromLocal) : null;
    if (parsedLocal && typeof parsedLocal === "object") {
      Object.assign(state, defaults, parsedLocal);
      return "local";
    }

    Object.assign(state, defaults);
    return "default";
  }

  async function saveState() {
    const payload = JSON.stringify(state);
    localStorage.setItem(STORAGE_KEY, payload);
    await cloudSet(STORAGE_KEY, payload);
  }

  async function loadChat() {
    const fromCloud = await cloudGet(CHAT_KEY);
    const parsedCloud = fromCloud ? safeJsonParse(fromCloud) : null;
    if (parsedCloud && typeof parsedCloud === "object" && Array.isArray(parsedCloud.history)) {
      chat.history = parsedCloud.history.slice(-80);
      return "cloud";
    }

    const fromLocal = localStorage.getItem(CHAT_KEY);
    const parsedLocal = fromLocal ? safeJsonParse(fromLocal) : null;
    if (parsedLocal && typeof parsedLocal === "object" && Array.isArray(parsedLocal.history)) {
      chat.history = parsedLocal.history.slice(-80);
      return "local";
    }

    chat.history = [];
    return "default";
  }

  async function saveChat() {
    const payload = JSON.stringify({ history: chat.history.slice(-120) });
    localStorage.setItem(CHAT_KEY, payload);
    await cloudSet(CHAT_KEY, payload);
  }

  // -------------------------
  // UI helpers
  // -------------------------
  function setChipText() {
    const vv = state.voice === "COACH" ? "📚 Коуч" : "🤝 Тиммейт";
    const chipVoice = qs("#chipVoice");
    if (chipVoice) chipVoice.textContent = vv;

    const mm = state.mode === "Demon" ? "😈 Demon" : (state.mode === "Pro" ? "🔥 Pro" : "🧠 Normal");
    const chipMode = qs("#chipMode");
    if (chipMode) chipMode.textContent = mm;

    const pp =
      state.platform === "PlayStation" ? "🎮 PlayStation" :
      state.platform === "Xbox" ? "🎮 Xbox" : "🖥 PC";
    const chipPlatform = qs("#chipPlatform");
    if (chipPlatform) chipPlatform.textContent = pp;

    const pillRole = qs("#pillRole");
    if (pillRole) pillRole.textContent = `🎭 Role: ${state.role}`;

    const pillBf6 = qs("#pillBf6");
    if (pillBf6) pillBf6.textContent = `🟩 Class: ${state.bf6_class}`;

    const chatSub = qs("#chatSub");
    if (chatSub) chatSub.textContent = `${state.voice} • ${state.mode} • ${state.platform}`;
  }

  function setActiveSeg(rootId, value) {
    const root = qs(rootId);
    if (!root) return;
    root.querySelectorAll(".seg-btn").forEach((b) => {
      const on = b.dataset.value === value;
      b.classList.toggle("active", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }

  function setActiveNav(tab) {
    qsa(".nav-btn").forEach((b) => {
      const on = b.dataset.tab === tab;
      b.classList.toggle("active", on);
      b.setAttribute("aria-selected", on ? "true" : "false");
    });
  }

  function setActiveTopTabs(tab) {
    qsa(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  }

  // -------------------------
  // Profile payload
  // -------------------------
  function toRouterProfile() {
    return {
      game: state.game,
      platform: state.platform,
      input: state.input,
      difficulty: state.mode,
      voice: state.voice,
      role: state.role,
      bf6_class: state.bf6_class,
      zombies_map: state.zombies_map,
      mode: state.mode
    };
  }

  function enrichPayload(payload) {
    const initUnsafe = tg?.initDataUnsafe || {};
    return {
      v: VERSION,
      t: now(),
      meta: {
        user_id: initUnsafe?.user?.id ?? null,
        chat_id: initUnsafe?.chat?.id ?? null,
        platform: tg?.platform ?? null,
        build: (window.__BCO_BUILD__ || null)
      },
      ...payload
    };
  }

  function sendToBot(payload) {
    try {
      const fixed = { ...(payload || {}) };

      if (Object.prototype.hasOwnProperty.call(fixed, "profile")) {
        if (fixed.profile === true) fixed.profile = toRouterProfile();
      }

      const pack = enrichPayload(fixed);
      let data = JSON.stringify(pack);

      const MAX = 15000;
      if (data.length > MAX) {
        if (typeof pack.text === "string") pack.text = pack.text.slice(0, 4000);
        if (typeof pack.note === "string") pack.note = pack.note.slice(0, 4000);
        data = JSON.stringify(pack).slice(0, MAX);
      }

      if (!tg?.sendData) {
        haptic("notif", "error");
        toast("Открой Mini App внутри Telegram");
        return;
      }

      tg.sendData(data);
      haptic("notif", "success");
      const statSession = qs("#statSession");
      if (statSession) statSession.textContent = "SENT";
      toast("Отправлено в бота 🚀");
    } catch {
      haptic("notif", "error");
      alert("Не могу отправить данные в бот. Открой мини-апп из Telegram.");
    }
  }

  function openBotMenuHint(target) {
    sendToBot({ type: "nav", target, profile: true });
  }

  // =========================================================
  // ✅ ZOMBIES ENGINE BRIDGE (new engine first, core fallback)
  // =========================================================
  function ZB() { return window.BCO_ZOMBIES || null; }
  function ZCORE() { return window.BCO_ZOMBIES_CORE || null; }

  function zombiesEnsureOpen(reason = "ui") {
    // Prefer new wrapper if exists
    const z = ZB();
    if (z) {
      try {
        z.open?.({
          map: state.zombies_map,
          character: state.character,
          skin: state.skin,
          reason
        });
      } catch {}
      return true;
    }

    // Fallback: core present but wrapper missing
    const core = ZCORE();
    if (core) {
      // We can still run core, but without renderer/hud the game won’t be visible.
      // This keeps compatibility and prevents “nothing happens”.
      try {
        core.meta = core.meta || {};
        core.meta.map = state.zombies_map;
        core.meta.character = state.character;
        core.meta.skin = state.skin;
      } catch {}
      return true;
    }

    toast("Zombies engine not loaded");
    haptic("notif", "error");
    return false;
  }

  function zombiesSetMode(mode) {
    const z = ZB();
    if (z) { try { z.setMode?.(mode); } catch {} return; }
    const core = ZCORE();
    if (core) {
      try { core.meta.mode = String(mode || "").toLowerCase().includes("rogue") ? "roguelike" : "arcade"; } catch {}
    }
  }

  function zombiesStart() {
    const z = ZB();
    if (z) {
      // keep 3 tries like you had, but do it clean
      try { z.start?.({ map: state.zombies_map, character: state.character, skin: state.skin }); return; } catch {}
      try { z.start?.({ map: state.zombies_map }); return; } catch {}
      try { z.start?.(); return; } catch {}
      return;
    }
    const core = ZCORE();
    if (core) {
      try {
        const mode = (state.mode || "").toLowerCase().includes("rogue") ? "roguelike" : "arcade";
        core.start?.(mode, core.state?.w || 1080, core.state?.h || 1920, { map: state.zombies_map, character: state.character, skin: state.skin });
      } catch {}
    }
  }

  function zombiesStop() {
    const z = ZB();
    if (z) { try { z.stop?.("manual"); } catch {}; try { z.stop?.(); } catch {}; return; }
    const core = ZCORE();
    if (core) { try { core.stop?.(); } catch {} }
  }

  function zombiesSendResult() {
    const z = ZB();
    if (z) { try { z.sendResult?.("manual"); return; } catch {}; try { z.result?.("manual"); return; } catch {} }
    // fallback: send a snapshot from core if possible
    const core = ZCORE();
    if (!core) return;
    try {
      const S = core.state || {};
      sendToBot({
        action: "game_result",
        game: "zombies",
        mode: core.meta?.mode || "arcade",
        map: core.meta?.map || state.zombies_map,
        character: core.meta?.character || state.character,
        skin: core.meta?.skin || state.skin,
        wave: S.wave || 1,
        kills: S.kills || 0,
        coins: S.coins || 0,
        duration_ms: (S.timeMs || 0),
        score: Math.round((S.kills || 0) * 35 + (S.wave || 1) * 120 + (S.coins || 0) * 10),
        profile: true
      });
    } catch {}
  }

  function zombiesBuyPerk(id) {
    const z = ZB();
    if (z) { try { z.buyPerk?.(id); } catch {} return; }
    const core = ZCORE();
    if (core) { try { core.buyPerk?.(id); } catch {} }
  }

  function zombiesReload() {
    const z = ZB();
    if (z) { try { z.reload?.(); } catch {} return; }
    const core = ZCORE();
    if (core) { try { core.reload?.(); } catch {} }
  }

  function zombiesUsePlate() {
    const z = ZB();
    if (z) { try { z.usePlate?.(); } catch {} return; }
    const core = ZCORE();
    if (core) { try { core.usePlate?.(); } catch {} }
  }

  // =========================================================
  // ✅ “ZOMBIES = GAME TAB” FULL TAKEOVER
  // =========================================================
  // Проблема на скринах:
  // - игра “внутри вкладки” и поверх ещё UI => неудобно, не фуллскрин
  // - кнопки не кликаются из-за перекрытий/слоёв
  //
  // Решение:
  // - вкладка Zombies превращается в “Game screen”: прячем нижний таббар/лишние панели,
  //   расширяем WebApp, включаем стабилизацию скролла,
  //   даём Back = выйти из игры (не из миниаппа)
  //
  const GAME = {
    active: false,
    prevTab: "home",
    hidden: [],
    scrollY: 0
  };

  function _hideSelectors(selectors) {
    const hidden = [];
    for (const sel of selectors) {
      qsa(sel).forEach((el) => {
        if (!el || el.dataset.__bcoHidden === "1") return;
        const prev = el.style.display;
        el.dataset.__bcoHidden = "1";
        el.dataset.__bcoPrevDisplay = prev || "";
        el.style.display = "none";
        hidden.push(el);
      });
    }
    return hidden;
  }

  function _restoreHidden(list) {
    (list || []).forEach((el) => {
      try {
        el.style.display = el.dataset.__bcoPrevDisplay || "";
        delete el.dataset.__bcoPrevDisplay;
        delete el.dataset.__bcoHidden;
      } catch {}
    });
  }

  function _freezeScroll(on) {
    try {
      if (on) {
        GAME.scrollY = window.scrollY || 0;
        document.body.style.position = "fixed";
        document.body.style.top = `-${GAME.scrollY}px`;
        document.body.style.left = "0";
        document.body.style.right = "0";
        document.body.style.width = "100%";
        document.body.style.overflow = "hidden";
      } else {
        document.body.style.position = "";
        document.body.style.top = "";
        document.body.style.left = "";
        document.body.style.right = "";
        document.body.style.width = "";
        document.body.style.overflow = "";
        window.scrollTo(0, GAME.scrollY || 0);
      }
    } catch {}
  }

  function enterZombiesGame() {
    if (GAME.active) return;
    GAME.active = true;
    GAME.prevTab = currentTab || "home";

    // Mark mode for CSS if you want
    try { document.documentElement.classList.add("bco-game"); } catch {}
    try { document.body.classList.add("bco-game"); } catch {}

    // Expand / theme
    try { tg?.expand?.(); } catch {}
    try { tg?.MainButton?.hide?.(); } catch {}

    // Hide nav/tabbars/headers that often block touches
    GAME.hidden = _hideSelectors([
      ".bottom-nav",
      "#bottomNav",
      ".nav",
      ".tabs",
      ".top-tabs",
      ".header",
      "#header",
      "#tabbar",
      "#premiumBar",
      ".premium-bar"
    ]);

    _freezeScroll(true);

    // Make sure engine is open and the game is visible
    zombiesEnsureOpen("enter_game");
    // When entering game, default to roguelike only if user picked it before
    // (we don’t force mode; you can still toggle)
    try { zombiesSetMode(String(state.mode || "").toLowerCase().includes("rogue") ? "roguelike" : "arcade"); } catch {}

    // Back = exit game (not close app)
    updateTelegramButtons();
  }

  function exitZombiesGame() {
    if (!GAME.active) return;
    GAME.active = false;

    try { document.documentElement.classList.remove("bco-game"); } catch {}
    try { document.body.classList.remove("bco-game"); } catch {}

    _restoreHidden(GAME.hidden);
    GAME.hidden = [];

    _freezeScroll(false);

    try { tg?.MainButton?.show?.(); } catch {}
    updateTelegramButtons();
  }

  // -------------------------
  // Tabs
  // -------------------------
  function selectTab(tab) {
    const t = String(tab || "home");
    currentTab = t;

    // If leaving zombies tab, exit game takeover
    if (GAME.active && t !== "zombies") exitZombiesGame();

    qsa(".tabpane").forEach((p) => p.classList.toggle("active", p.id === `tab-${t}`));
    setActiveNav(t);
    setActiveTopTabs(t);

    // If entering zombies tab — DO THE FULL TAKEOVER
    if (t === "zombies") {
      // show the tabpane first, then takeover
      setTimeout(() => enterZombiesGame(), 0);
    }

    updateTelegramButtons();

    try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch {}
  }

  // -------------------------
  // Telegram buttons
  // -------------------------
  let tgButtonsWired = false;
  let tgMainHandler = null;
  let tgBackHandler = null;

  function updateTelegramButtons() {
    if (!tg) return;

    // BackButton logic:
    // - if game active => back exits game
    // - else if not home => back to home
    try {
      if (GAME.active) tg.BackButton.show();
      else if (currentTab !== "home") tg.BackButton.show();
      else tg.BackButton.hide();
    } catch {}

    // MainButton text:
    // - In game: we hide it to not block touches.
    // - Else normal behavior.
    try {
      if (GAME.active) {
        tg.MainButton.hide();
      } else {
        tg.MainButton.setParams({
          is_visible: true,
          text:
            currentTab === "settings" ? "✅ Применить профиль" :
            currentTab === "coach" ? "🎯 План тренировки" :
            currentTab === "vod" ? "🎬 Отправить VOD" :
            currentTab === "zombies" ? "🧟 Играть" :
            "💎 Premium"
        });
      }
    } catch {}

    if (tgButtonsWired) return;
    tgButtonsWired = true;

    tgMainHandler = () => {
      haptic("impact", "medium");

      if (GAME.active) {
        // If somehow visible, start game / show shop
        zombiesEnsureOpen("main_in_game");
        return;
      }

      if (currentTab === "settings") { sendToBot({ type: "set_profile", profile: true }); return; }
      if (currentTab === "coach") { sendToBot({ type: "training_plan", focus: state.focus, profile: true }); return; }
      if (currentTab === "vod") {
        const t1 = (qs("#vod1")?.value || "").trim();
        const t2 = (qs("#vod2")?.value || "").trim();
        const t3 = (qs("#vod3")?.value || "").trim();
        const note = (qs("#vodNote")?.value || "").trim();
        sendToBot({ type: "vod", times: [t1, t2, t3].filter(Boolean), note, profile: true });
        return;
      }
      if (currentTab === "zombies") {
        enterZombiesGame();
        return;
      }
      openBotMenuHint("premium");
    };

    tgBackHandler = () => {
      haptic("impact", "light");
      if (GAME.active) {
        exitZombiesGame();
        // return to previous non-game tab if it exists
        selectTab(GAME.prevTab && GAME.prevTab !== "zombies" ? GAME.prevTab : "home");
        return;
      }
      selectTab("home");
    };

    try { tg.MainButton.offClick?.(tgMainHandler); } catch {}
    try { tg.MainButton.onClick?.(tgMainHandler); } catch {}

    try { tg.BackButton.offClick?.(tgBackHandler); } catch {}
    try { tg.BackButton.onClick?.(tgBackHandler); } catch {}
  }

  // -------------------------
  // Share
  // -------------------------
  function tryShare(text) {
    try {
      navigator.clipboard?.writeText?.(text);
      toast("Скопировано ✅");
    } catch {
      alert(text);
    }
  }

  // =========================================================
  // ✅ MINI APP CHAT (BOT REPLIES IN APP)
  // =========================================================
  function chatLogEl() { return qs("#chatLog"); }

  function esc(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function fmtTime(ts) {
    try {
      const d = new Date(ts);
      const hh = String(d.getHours()).padStart(2, "0");
      const mm = String(d.getMinutes()).padStart(2, "0");
      return `${hh}:${mm}`;
    } catch { return ""; }
  }

  function renderChat() {
    const root = chatLogEl();
    if (!root) return;

    const items = chat.history.slice(-80);
    let html = "";

    for (const m of items) {
      const who = (m.role === "assistant") ? "bot" : "me";
      const label = (m.role === "assistant") ? "BCO" : "Ты";
      html += `
        <div class="chat-row ${who}">
          <div>
            <div class="bubble">${esc(m.text)}</div>
            <div class="chat-meta">${label} • ${esc(fmtTime(m.ts || now()))}</div>
          </div>
        </div>
      `;
    }

    root.innerHTML = html || `
      <div class="chat-row bot">
        <div>
          <div class="bubble">🤝 Готов. Пиши как есть: где умираешь и что хочешь получить — отвечу тут же. 😈</div>
          <div class="chat-meta">BCO • ${esc(fmtTime(now()))}</div>
        </div>
      </div>
    `;

    try { root.scrollTop = root.scrollHeight; } catch {}
  }

  function pushChat(role, text) {
    const t = String(text ?? "").trim();
    if (!t) return;
    chat.history.push({ role, text: t, ts: now() });
    chat.history = chat.history.slice(-160);
  }

  function setTyping(on) {
    const root = chatLogEl();
    if (!root) return;

    const id = "bco-typing-row";
    const existing = qs(`#${id}`);
    if (on) {
      if (existing) return;
      const row = document.createElement("div");
      row.className = "chat-row bot";
      row.id = id;
      row.innerHTML = `
        <div>
          <div class="bubble">
            <span class="typing">
              <span class="dot"></span><span class="dot"></span><span class="dot"></span>
            </span>
          </div>
          <div class="chat-meta">BCO • печатает…</div>
        </div>
      `;
      root.appendChild(row);
      try { root.scrollTop = root.scrollHeight; } catch {}
      return;
    }
    if (existing) existing.remove();
  }

  async function askBrain(text) {
    const t = String(text ?? "").trim();
    if (!t) return null;

    const delta = now() - (chat.lastAskAt || 0);
    if (delta < 450) return null;
    chat.lastAskAt = now();

    setTyping(true);

    const body = {
      initData: tg?.initData || "",
      text: t,
      profile: toRouterProfile(),
      history: chat.history.slice(-20).map(m => ({ role: m.role, content: m.text }))
    };

    const controller = ("AbortController" in window) ? new AbortController() : null;
    const timeoutMs = 12000;
    let timer = 0;
    if (controller) timer = window.setTimeout(() => controller.abort(), timeoutMs);

    try {
      const res = await fetch("/webapp/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: controller?.signal
      });

      const data = await res.json().catch(() => null);
      setTyping(false);
      if (timer) clearTimeout(timer);

      if (!data || data.ok !== true) {
        const err = (data && (data.error || data.detail)) ? String(data.error || data.detail) : "api_error";
        return `🧠 Mini App: API error (${err}).`;
      }

      return String(data.reply ?? "");
    } catch (e) {
      setTyping(false);
      if (timer) clearTimeout(timer);
      const msg = String(e?.name === "AbortError" ? "timeout" : (e?.message || e));
      return `🧠 Mini App: network error (${msg}).`;
    }
  }

  async function sendChatFromUI() {
    const input = qs("#chatInput");
    const text = (input?.value || "").trim();
    if (!text) { haptic("notif", "warning"); toast("Напиши текст"); return; }

    haptic("impact", "light");
    pushChat("user", text);
    if (input) input.value = "";
    renderChat();
    await saveChat();

    const reply = await askBrain(text);

    if (reply) {
      pushChat("assistant", reply);
      renderChat();
      await saveChat();
      haptic("notif", "success");
      return;
    }

    haptic("notif", "warning");
    toast("Нет ответа. Можно отправить в бота.");
  }

  function exportChatText() {
    const lines = chat.history.slice(-80).map(m => {
      const who = (m.role === "assistant") ? "BCO" : "YOU";
      return `[${fmtTime(m.ts)}] ${who}: ${m.text}`;
    });
    return lines.join("\n");
  }

  // -------------------------
  // Segments wiring
  // -------------------------
  function wireSeg(rootId, onPick) {
    const root = qs(rootId);
    if (!root) return;

    const handler = async (btn) => {
      haptic("impact", "light");
      onPick(btn.dataset.value);

      setActiveSeg(rootId, btn.dataset.value);
      setChipText();

      await saveState();
      toast("Сохранено ✅");
    };

    // delegate inside root
    onTap(root, (e) => {
      const btn = e.target?.closest?.(".seg-btn");
      if (!btn) return;
      handler(btn);
    }, { lockMs: 160 });
  }

  // -------------------------
  // Nav wiring
  // -------------------------
  function wireNav() {
    qsa(".nav-btn").forEach((btn) => {
      onTap(btn, () => {
        haptic("impact", "light");
        selectTab(btn.dataset.tab);
      }, { lockMs: 160 });
    });

    qsa(".tab").forEach((btn) => {
      onTap(btn, () => {
        haptic("impact", "light");
        selectTab(btn.dataset.tab);
      }, { lockMs: 160 });
    });
  }

  // -------------------------
  // Header chips
  // -------------------------
  function wireHeaderChips() {
    const chipVoice = qs("#chipVoice");
    const chipMode = qs("#chipMode");
    const chipPlatform = qs("#chipPlatform");

    onTap(chipVoice, async () => {
      haptic("impact", "light");
      state.voice = (state.voice === "COACH") ? "TEAMMATE" : "COACH";
      setChipText();
      setActiveSeg("#segVoice", state.voice);
      await saveState();
      toast(state.voice === "COACH" ? "Коуч включён 📚" : "Тиммейт 🤝");
    });

    onTap(chipMode, async () => {
      haptic("impact", "light");
      state.mode = (state.mode === "Normal") ? "Pro" : (state.mode === "Pro" ? "Demon" : "Normal");
      setChipText();
      setActiveSeg("#segMode", state.mode);
      await saveState();
      toast(`Режим: ${state.mode}`);
    });

    onTap(chipPlatform, async () => {
      haptic("impact", "light");
      state.platform = (state.platform === "PC") ? "PlayStation" : (state.platform === "PlayStation" ? "Xbox" : "PC");
      setChipText();
      setActiveSeg("#segPlatform", state.platform);
      await saveState();
      toast(`Platform: ${state.platform}`);
    });
  }

  // =========================================================
  // 🎯 GAME #1: AIM TRIAL (kept)
  // =========================================================
  const aim = {
    running: false,
    startedAt: 0,
    durationMs: 20000,
    shots: 0,
    hits: 0,
    timerId: null
  };

  function aimEls() {
    return {
      arena: qs("#aimArena"),
      target: qs("#aimTarget"),
      stat: qs("#aimStat"),
      btnStart: qs("#btnAimStart"),
      btnStop: qs("#btnAimStop"),
      btnSend: qs("#btnAimSend")
    };
  }

  function aimReset() {
    aim.running = false;
    aim.startedAt = 0;
    aim.shots = 0;
    aim.hits = 0;
    if (aim.timerId) { clearInterval(aim.timerId); aim.timerId = null; }
    aimUpdateUI();
  }

  function aimMoveTarget() {
    const { arena, target } = aimEls();
    if (!arena || !target) return;

    const rect = arena.getBoundingClientRect();
    const pad = 14;

    const tRect = target.getBoundingClientRect();
    const tw = Math.max(30, tRect.width || 44);
    const th = Math.max(30, tRect.height || 44);

    const w = Math.max(60, rect.width);
    const h = Math.max(160, rect.height);

    const maxX = Math.max(pad, w - pad - tw);
    const maxY = Math.max(pad, h - pad - th);

    const x = pad + Math.random() * (maxX - pad);
    const y = pad + Math.random() * (maxY - pad);

    target.style.transform = `translate(${x}px, ${y}px)`;
  }

  function aimUpdateUI() {
    const { stat, btnStart, btnStop, btnSend } = aimEls();
    const acc = aim.shots ? Math.round((aim.hits / aim.shots) * 100) : 0;
    const tLeft = aim.running ? Math.max(0, aim.durationMs - (now() - aim.startedAt)) : 0;

    if (stat) stat.textContent = aim.running
      ? `⏱ ${(tLeft / 1000).toFixed(1)}s • 🎯 ${aim.hits}/${aim.shots} • Acc ${acc}%`
      : `🎯 ${aim.hits}/${aim.shots} • Acc ${acc}%`;

    if (btnStart) btnStart.disabled = aim.running;
    if (btnStop) btnStop.disabled = !aim.running;
    if (btnSend) btnSend.disabled = aim.running || aim.shots < 5;
  }

  function aimStop(auto = false) {
    if (!aim.running) return;
    aim.running = false;
    if (aim.timerId) { clearInterval(aim.timerId); aim.timerId = null; }
    aimUpdateUI();
    haptic("notif", auto ? "warning" : "success");
    toast(auto ? "AIM завершён" : "Остановлено");
  }

  function aimStart() {
    if (aim.running) return;
    aimReset();
    aim.running = true;
    aim.startedAt = now();
    aimMoveTarget();
    aimUpdateUI();

    aim.timerId = setInterval(() => {
      aimMoveTarget();
      aimUpdateUI();
      if (now() - aim.startedAt >= aim.durationMs) aimStop(true);
    }, 650);

    toast("AIM: поехали 😈");
    haptic("notif", "success");
  }

  function aimSendResult() {
    const duration = aim.running ? (now() - aim.startedAt) : aim.durationMs;
    const acc = aim.shots ? (aim.hits / aim.shots) : 0;

    sendToBot({
      action: "game_result",
      game: "aim",
      mode: "arcade",
      shots: aim.shots,
      hits: aim.hits,
      accuracy: acc,
      score: Math.round(aim.hits * 100 + acc * 100),
      duration_ms: duration,
      profile: true
    });
  }

  // =========================================================
  // Buttons wiring
  // =========================================================
  function wireButtons() {
    // close
    onTap(qs("#btnClose"), () => {
      haptic("impact", "medium");
      tg?.close?.();
    });

    // home / bot
    onTap(qs("#btnOpenBot"), () => openBotMenuHint("main"));
    onTap(qs("#btnPremium"), () => openBotMenuHint("premium"));
    onTap(qs("#btnSync"), () => sendToBot({ type: "sync_request", profile: true }));

    // coach / vod / settings / zombies (bot-side)
    onTap(qs("#btnOpenTraining"), () => openBotMenuHint("training"));
    onTap(qs("#btnSendPlan"), () => sendToBot({ type: "training_plan", focus: state.focus, profile: true }));

    onTap(qs("#btnOpenVod"), () => openBotMenuHint("vod"));
    onTap(qs("#btnSendVod"), () => {
      const t1 = (qs("#vod1")?.value || "").trim();
      const t2 = (qs("#vod2")?.value || "").trim();
      const t3 = (qs("#vod3")?.value || "").trim();
      const note = (qs("#vodNote")?.value || "").trim();
      sendToBot({ type: "vod", times: [t1, t2, t3].filter(Boolean), note, profile: true });
    });

    onTap(qs("#btnOpenSettings"), () => openBotMenuHint("settings"));
    onTap(qs("#btnApplyProfile"), () => sendToBot({ type: "set_profile", profile: true }));

    // Zombies info buttons to bot
    onTap(qs("#btnOpenZombies"), () => { selectTab("zombies"); }); // теперь это “войти в игру”
    onTap(qs("#btnZPerks"), () => sendToBot({ type: "zombies", action: "perks", map: state.zombies_map, profile: true }));
    onTap(qs("#btnZLoadout"), () => sendToBot({ type: "zombies", action: "loadout", map: state.zombies_map, profile: true }));
    onTap(qs("#btnZEggs"), () => sendToBot({ type: "zombies", action: "eggs", map: state.zombies_map, profile: true }));
    onTap(qs("#btnZRound"), () => sendToBot({ type: "zombies", action: "rounds", map: state.zombies_map, profile: true }));
    onTap(qs("#btnZTips"), () => sendToBot({ type: "zombies", action: "tips", map: state.zombies_map, profile: true }));

    // pay
    onTap(qs("#btnBuyMonth"), () => sendToBot({ type: "pay", plan: "premium_month", profile: true }));
    onTap(qs("#btnBuyLife"), () => sendToBot({ type: "pay", plan: "premium_lifetime", profile: true }));

    onTap(qs("#btnShare"), () => {
      const text =
        "BLACK CROWN OPS 😈\n" +
        "Тренировки, VOD, настройки, Zombies — всё в одном месте.\n" +
        "Mini App + Fullscreen Zombies Game (Arcade/Roguelike).";
      tryShare(text);
    });

    // chat
    onTap(qs("#btnChatSend"), () => sendChatFromUI());
    onTap(qs("#btnChatClear"), async () => {
      haptic("impact", "light");
      chat.history = [];
      await saveChat();
      renderChat();
      toast("Чат очищен ✅");
    });
    onTap(qs("#btnChatExport"), () => {
      haptic("impact", "light");
      tryShare(exportChatText() || "— пусто —");
    });

    const chatInput = qs("#chatInput");
    if (chatInput) {
      chatInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          sendChatFromUI();
        }
      });
    }

    // AIM game
    const { arena, target, btnStart, btnStop, btnSend } = aimEls();
    onTap(btnStart, () => aimStart());
    onTap(btnStop, () => aimStop(false));
    onTap(btnSend, () => aimSendResult());

    if (arena && target) {
      onTap(target, (e) => {
        if (!aim.running) return;
        aim.shots += 1;
        aim.hits += 1;
        haptic("impact", "light");
        aimMoveTarget();
        aimUpdateUI();
        try { e?.preventDefault?.(); e?.stopPropagation?.(); } catch {}
      });

      onTap(arena, () => {
        if (!aim.running) return;
        aim.shots += 1;
        haptic("impact", "light");
        aimUpdateUI();
      }, { prevent: false });
    }

    // =========================================================
    // ✅ ZOMBIES (NEW ENGINE) — Game controls (if buttons exist in HTML)
    // =========================================================
    const btnZArc = qs("#btnZModeArcade");
    const btnZRog = qs("#btnZModeRogue");
    const btnZStart = qs("#btnZGameStart");
    const btnZStop = qs("#btnZGameStop");
    const btnZSend = qs("#btnZGameSend");

    onTap(btnZArc, () => {
      if (!zombiesEnsureOpen("btn_arcade")) return;
      zombiesSetMode("arcade");
      toast("Zombies: Arcade 💥");
    });

    onTap(btnZRog, () => {
      if (!zombiesEnsureOpen("btn_rogue")) return;
      zombiesSetMode("roguelike");
      toast("Zombies: Roguelike 😈");
    });

    onTap(btnZStart, () => {
      if (!zombiesEnsureOpen("btn_start")) return;
      zombiesStart();
      toast("Zombies: старт ▶");
    });

    onTap(btnZStop, () => {
      if (!zombiesEnsureOpen("btn_stop")) return;
      zombiesStop();
      toast("Zombies: стоп ⛔");
    });

    onTap(btnZSend, () => {
      if (!zombiesEnsureOpen("btn_send")) return;
      zombiesSendResult();
    });

    // Old shop buttons => perks on new engine
    onTap(qs("#btnZBuyJug"), () => {
      if (!zombiesEnsureOpen("perk_jug")) return;
      zombiesSetMode("roguelike");
      zombiesStart();
      zombiesBuyPerk("Jug");
    });

    onTap(qs("#btnZBuySpeed"), () => {
      if (!zombiesEnsureOpen("perk_speed")) return;
      zombiesSetMode("roguelike");
      zombiesStart();
      zombiesBuyPerk("Speed");
    });

    onTap(qs("#btnZBuyAmmo"), () => {
      if (!zombiesEnsureOpen("perk_mag")) return;
      zombiesSetMode("roguelike");
      zombiesStart();
      zombiesBuyPerk("Mag");
    });

    // Extra: if your HUD buttons exist (Upgrade/Reroll/Reload/Plate) — bind them
    onTap(qs("#btnZReload"), () => { zombiesEnsureOpen("reload"); zombiesReload(); });
    onTap(qs("#btnZPlate"), () => { zombiesEnsureOpen("plate"); zombiesUsePlate(); });

    // Always keep taps working even if overlays exist
    // (doesn’t break anything if elements are absent)
  }

  // -------------------------
  // Build tag
  // -------------------------
  function ensureBuildTag() {
    const buildFromIndex =
      (window.__BCO_BUILD__ && window.__BCO_BUILD__ !== "__BUILD__")
        ? window.__BCO_BUILD__
        : null;

    const txt = buildFromIndex ? `build ${buildFromIndex} • v${VERSION}` : `v${VERSION}`;
    const buildTag = qs("#buildTag");
    if (buildTag) buildTag.textContent = txt;
  }

  // -------------------------
  // Telegram init
  // -------------------------
  function initTelegram() {
    const dbgUser = qs("#dbgUser");
    const dbgChat = qs("#dbgChat");
    const dbgInit = qs("#dbgInit");
    const statOnline = qs("#statOnline");

    if (!tg) {
      if (statOnline) statOnline.textContent = "BROWSER";
      if (dbgInit) dbgInit.textContent = "no tg";
      return;
    }

    try { tg.ready(); } catch {}
    try { tg.expand(); } catch {}

    applyTelegramTheme();
    try { tg.onEvent("themeChanged", applyTelegramTheme); } catch {}

    const hasInit = !!(tg.initData && String(tg.initData).length > 10);
    const hasUser = !!tg.initDataUnsafe?.user?.id;

    if (dbgUser) dbgUser.textContent = tg.initDataUnsafe?.user?.id ?? "—";
    if (dbgChat) dbgChat.textContent = tg.initDataUnsafe?.chat?.id ?? "—";
    if (dbgInit) dbgInit.textContent = hasInit ? "ok" : "empty";

    if (statOnline) {
      statOnline.textContent = hasUser ? "TG_WEBVIEW" : (hasInit ? "TG_NOUSER" : "NO_INITDATA");
    }

    updateTelegramButtons();
  }

  // =========================================================
  // 3D-READY HOOK (no break)
  // =========================================================
  // Задел: когда вы начнёте 3D (Three/Babylon), у вас будет единая “Game Takeover” оболочка,
  // а движок можно переключать через window.BCO_ZOMBIES_RENDERER = "2d" | "3d".
  // Сейчас ничего не ломаем — просто оставляем точку расширения.
  function getRendererMode() {
    try { return String(window.BCO_ZOMBIES_RENDERER || "2d").toLowerCase(); } catch { return "2d"; }
  }

  // -------------------------
  // Boot
  // -------------------------
  async function boot() {
    if (document.readyState !== "complete" && document.readyState !== "interactive") {
      await new Promise((r) => document.addEventListener("DOMContentLoaded", r, { once: true }));
    }

    initTelegram();
    ensureBuildTag();

    const src = await loadState();
    const statSession = qs("#statSession");
    if (statSession) statSession.textContent = String(src).toUpperCase();

    await loadChat();

    wireNav();

    // Segments
    wireSeg("#segGame", (v) => { state.game = v; });
    wireSeg("#segFocus", (v) => { state.focus = v; });
    wireSeg("#segMode", (v) => { state.mode = v; });
    wireSeg("#segPlatform", (v) => { state.platform = v; });
    wireSeg("#segInput", (v) => { state.input = v; });
    wireSeg("#segVoice", (v) => { state.voice = v; });
    wireSeg("#segZMap", (v) => { state.zombies_map = v; });

    setChipText();

    setActiveSeg("#segPlatform", state.platform);
    setActiveSeg("#segInput", state.input);
    setActiveSeg("#segVoice", state.voice);
    setActiveSeg("#segMode", state.mode);
    setActiveSeg("#segZMap", state.zombies_map);
    setActiveSeg("#segGame", state.game);
    setActiveSeg("#segFocus", state.focus);

    wireHeaderChips();
    wireButtons();

    renderChat();
    aimReset();

    // Default tab
    selectTab("home");

    // Preflight: if zombies tab exists and renderer mode indicates 3D soon, show subtle debug
    try {
      const jsHealth = qs("#jsHealth");
      if (jsHealth) jsHealth.textContent = `OK • renderer:${getRendererMode()} • v${VERSION}`;
    } catch {}
  }

  boot();
})();
