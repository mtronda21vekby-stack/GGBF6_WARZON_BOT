// app/webapp/static/app.js  (LUX v1.3.4+)
// - фикс “кнопки не нажимаются” (iOS WebView): нормальный tap-движок + touch-action + без passive на критичных местах
// - Zombies как “полный переход в игру”: при входе во вкладку Zombies включаем fullscreen/overlay-режим (без урезания функционала)
// - аккуратный bridge к BCO_ZOMBIES / CORE: пробуем разные сигнатуры, не ломаем старые версии движка
(() => {
  "use strict";

  window.__BCO_JS_OK__ = true;

  const tg = window.Telegram?.WebApp || null;

  const VERSION = "1.3.4";
  const STORAGE_KEY = "bco_state_v1";
  const CHAT_KEY = "bco_chat_v1";

  // -----------------------------
  // Defaults / state
  // -----------------------------
  const defaults = {
    game: "Warzone",
    focus: "aim",
    mode: "Normal",          // Normal/Pro/Demon (coach style & also difficulty chip)
    platform: "PC",
    input: "Controller",
    voice: "TEAMMATE",
    role: "Flex",
    bf6_class: "Assault",
    zombies_map: "Ashes",

    // ✅ Zombies cosmetics
    character: "male",       // male | female
    skin: "default",         // depends on character

    // ✅ Zombies run mode (separate from coach mode)
    zombies_mode: "arcade"   // arcade | roguelike
  };

  const state = { ...defaults };

  const chat = {
    history: [],
    lastAskAt: 0
  };

  let currentTab = "home";

  // -----------------------------
  // DOM utils
  // -----------------------------
  const qs = (s) => document.querySelector(s);
  const qsa = (s) => Array.from(document.querySelectorAll(s));
  const now = () => Date.now();

  function safeJsonParse(s) { try { return JSON.parse(s); } catch { return null; } }

  // -----------------------------
  // Haptics / toast
  // -----------------------------
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
    t.textContent = String(text ?? "");
    t.classList.add("show");
    setTimeout(() => t.classList.remove("show"), 1600);
  }

  // =========================================================
  // ✅ LUX TAP ENGINE (iOS WebView SAFE)
  // - решает “кнопки не нажимаются / двойные тапы”
  // - НЕ passive на critical, чтобы можно было preventDefault()
  // =========================================================
  const TAP = (() => {
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent || "");
    const supportsPointer = !!window.PointerEvent;

    function bind(el, handler, opts = {}) {
      if (!el || typeof handler !== "function") return () => {};

      const moveTol = Math.max(6, opts.moveTol || 10);
      const lockMs = Math.max(160, opts.lockMs || 220);
      const prevent = opts.prevent !== false;

      let locked = false;
      let startX = 0, startY = 0;
      let down = false;
      let pid = null;
      let downAt = 0;

      const unlockLater = () => setTimeout(() => { locked = false; }, lockMs);

      const onDown = (e) => {
        try {
          if (locked) return;
          down = true;
          downAt = now();

          if (supportsPointer && e.pointerId != null) pid = e.pointerId;
          const pt = pointOf(e);
          startX = pt.x;
          startY = pt.y;

          // критично для iOS: предотвращаем “ghost click” и скролл при таче по кнопкам
          if (prevent) {
            try { e.preventDefault?.(); } catch {}
            try { e.stopPropagation?.(); } catch {}
          }
          // pointer capture помогает когда палец чуть уезжает
          try { el.setPointerCapture?.(pid); } catch {}
        } catch {}
      };

      const onUp = (e) => {
        try {
          if (!down) return;
          down = false;

          const pt = pointOf(e);
          const dx = pt.x - startX;
          const dy = pt.y - startY;
          const dist = Math.hypot(dx, dy);

          if (dist <= moveTol) {
            locked = true;
            unlockLater();
            handler(e);
          }
          if (prevent) {
            try { e.preventDefault?.(); } catch {}
            try { e.stopPropagation?.(); } catch {}
          }
          try { el.releasePointerCapture?.(pid); } catch {}
          pid = null;
        } catch {}
      };

      const onCancel = () => {
        down = false;
        pid = null;
      };

      // Prefer Pointer Events
      if (supportsPointer) {
        el.addEventListener("pointerdown", onDown, { passive: false });
        el.addEventListener("pointerup", onUp, { passive: false });
        el.addEventListener("pointercancel", onCancel, { passive: true });
        return () => {
          el.removeEventListener("pointerdown", onDown);
          el.removeEventListener("pointerup", onUp);
          el.removeEventListener("pointercancel", onCancel);
        };
      }

      // Touch fallback
      el.addEventListener("touchstart", onDown, { passive: false });
      el.addEventListener("touchend", onUp, { passive: false });
      el.addEventListener("touchcancel", onCancel, { passive: true });

      // Click fallback (desktop)
      el.addEventListener("click", (e) => {
        if (locked) return;
        locked = true; unlockLater();
        try { handler(e); } catch {}
      }, { passive: true });

      return () => {
        el.removeEventListener("touchstart", onDown);
        el.removeEventListener("touchend", onUp);
        el.removeEventListener("touchcancel", onCancel);
      };
    }

    function pointOf(e) {
      const t = e?.changedTouches?.[0] || e?.touches?.[0];
      if (t) return { x: t.clientX || 0, y: t.clientY || 0 };
      return { x: e?.clientX || 0, y: e?.clientY || 0 };
    }

    function hardenUI() {
      // “кнопки не нажимаются” часто из-за touch-action / pointer-events / overlay
      // мы безболезненно усилим интерактив через style-inject
      const style = document.createElement("style");
      style.id = "bco-tap-harden";
      style.textContent = `
        * { -webkit-tap-highlight-color: transparent; }
        button, a, .seg-btn, .nav-btn, .tab, .btn, [role="button"] { touch-action: manipulation; }
        .seg, .seg * , .nav, .nav * { pointer-events: auto !important; }
        .tabpane { pointer-events: auto; }
        #toast { pointer-events: none; }
        /* Zombies fullscreen helper (без ломания вёрстки) */
        body.bco-zombies-full { overflow: hidden !important; }
        body.bco-zombies-full .nav { display: none !important; }
        body.bco-zombies-full .top-tabs { display: none !important; }
        body.bco-zombies-full .tabpane:not(#tab-zombies) { display: none !important; }
        body.bco-zombies-full #tab-zombies { display: block !important; position: relative; z-index: 10; }
      `;
      document.head.appendChild(style);
    }

    return { bind, hardenUI };
  })();

  // -----------------------------
  // Telegram theme sync
  // -----------------------------
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

  // -----------------------------
  // Storage (Cloud + local)
  // -----------------------------
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

  // -----------------------------
  // UI chips
  // -----------------------------
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

  // -----------------------------
  // Tabs + Zombies fullscreen behavior
  // -----------------------------
  function enterZombiesFullscreen() {
    document.body.classList.add("bco-zombies-full");
  }
  function exitZombiesFullscreen() {
    document.body.classList.remove("bco-zombies-full");
  }

  function selectTab(tab) {
    const prev = currentTab;
    currentTab = tab;

    // If leaving zombies -> exit fullscreen
    if (prev === "zombies" && tab !== "zombies") {
      exitZombiesFullscreen();
      try { ZB()?.close?.(); } catch {}
      try { ZB()?.hide?.(); } catch {}
    }

    qsa(".tabpane").forEach((p) => p.classList.toggle("active", p.id === `tab-${tab}`));
    setActiveNav(tab);
    setActiveTopTabs(tab);

    // If entering zombies -> go fullscreen + open game overlay
    if (tab === "zombies") {
      enterZombiesFullscreen();
      // open game view immediately (полный переход)
      zombiesEnsureOpen(true);
    }

    updateTelegramButtons();

    try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch {}
  }

  // -----------------------------
  // Payload / sendData
  // -----------------------------
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
  // ✅ ZOMBIES BRIDGE
  // =========================================================
  function ZB() { return window.BCO_ZOMBIES || null; }

  function zombiesEnsureOpen(fullscreen = false) {
    const z = ZB();
    if (!z) {
      toast("Zombies engine not loaded");
      haptic("notif", "error");
      return false;
    }

    // prepare opts
    const opts = {
      map: state.zombies_map,
      character: state.character,
      skin: state.skin,
      mode: state.zombies_mode
    };

    // try open / show / enter
    try { z.open?.({ ...opts, fullscreen: !!fullscreen }); } catch {}
    try { z.show?.({ ...opts, fullscreen: !!fullscreen }); } catch {}
    try { z.enter?.({ ...opts, fullscreen: !!fullscreen }); } catch {}

    // If your engine uses CORE directly
    try {
      const CORE = window.BCO_ZOMBIES_CORE;
      if (CORE?.start && fullscreen) {
        // don't auto-start here; only ensure UI/game canvas becomes active
      }
    } catch {}

    return true;
  }

  function zombiesSetMode(mode) {
    const m = String(mode || "").toLowerCase().includes("rogue") ? "roguelike" : "arcade";
    state.zombies_mode = m;
    const z = ZB();
    if (!z) return;
    try { z.setMode?.(m); } catch {}
    try { z.mode?.(m); } catch {}
  }

  function zombiesStart() {
    const z = ZB();
    if (!z) return;

    const payload = {
      mode: state.zombies_mode,
      map: state.zombies_map,
      character: state.character,
      skin: state.skin
    };

    // Try modern signatures first
    try { z.start?.(payload); return; } catch {}
    try { z.start?.(state.zombies_mode); return; } catch {}
    try { z.start?.(); } catch {}
  }

  function zombiesStop() {
    const z = ZB();
    if (!z) return;
    try { z.stop?.("manual"); return; } catch {}
    try { z.stop?.(); } catch {}
  }

  function zombiesSendResult() {
    const z = ZB();
    if (!z) return;
    try { z.sendResult?.("manual"); return; } catch {}
    try { z.result?.("manual"); return; } catch {}
  }

  function zombiesBuyPerk(id) {
    const z = ZB();
    if (!z) return;
    try { z.buyPerk?.(id); return; } catch {}
    // fallback: core direct
    try { window.BCO_ZOMBIES_CORE?.buyPerk?.(id); } catch {}
  }

  // -----------------------------
  // Telegram native buttons
  // -----------------------------
  let tgButtonsWired = false;
  let tgMainHandler = null;
  let tgBackHandler = null;

  function updateTelegramButtons() {
    if (!tg) return;

    try {
      if (currentTab !== "home") tg.BackButton.show();
      else tg.BackButton.hide();
    } catch {}

    try {
      tg.MainButton.setParams({
        is_visible: true,
        text:
          currentTab === "settings" ? "✅ Применить профиль" :
          currentTab === "coach" ? "🎯 План тренировки" :
          currentTab === "vod" ? "🎬 Отправить VOD" :
          currentTab === "zombies" ? "🧟 Войти в игру" :
          "💎 Premium"
      });
    } catch {}

    if (tgButtonsWired) return;
    tgButtonsWired = true;

    tgMainHandler = () => {
      haptic("impact", "medium");

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
        // "полный переход": гарантируем fullscreen overlay + старт по кнопке
        if (zombiesEnsureOpen(true)) {
          zombiesStart();
          return;
        }
        sendToBot({ type: "zombies_open", map: state.zombies_map, profile: true });
        return;
      }

      openBotMenuHint("premium");
    };

    tgBackHandler = () => {
      haptic("impact", "light");

      // if zombies tab -> first exit fullscreen, then home
      if (currentTab === "zombies") {
        exitZombiesFullscreen();
        try { ZB()?.close?.(); } catch {}
        try { ZB()?.hide?.(); } catch {}
        selectTab("home");
        return;
      }

      selectTab("home");
    };

    try { tg.MainButton.offClick?.(tgMainHandler); } catch {}
    try { tg.MainButton.onClick?.(tgMainHandler); } catch {}

    try { tg.BackButton.offClick?.(tgBackHandler); } catch {}
    try { tg.BackButton.onClick?.(tgBackHandler); } catch {}
  }

  // -----------------------------
  // Share helper
  // -----------------------------
  function tryShare(text) {
    try {
      navigator.clipboard?.writeText?.(text);
      toast("Скопировано ✅");
    } catch {
      alert(text);
    }
  }

  // =========================================================
  // ✅ MINI APP CHAT
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

  // -----------------------------
  // Segments wiring (FIXED)
  // -----------------------------
  function wireSeg(rootId, onPick) {
    const root = qs(rootId);
    if (!root) return;

    // ВАЖНО: на iOS pointerup на контейнере иногда не проходит из-за вложенных слоёв.
    // Делаем надёжно: ловим down/up на root, но выбираем ближайшую .seg-btn.
    TAP.bind(root, async (e) => {
      const btn = e.target?.closest?.(".seg-btn");
      if (!btn || !root.contains(btn)) return;

      const v = btn.dataset.value;
      if (v == null) return;

      haptic("impact", "light");
      try { onPick(v); } catch {}

      setActiveSeg(rootId, v);
      setChipText();

      await saveState();
      toast("Сохранено ✅");
    }, { lockMs: 180, moveTol: 12, prevent: true });
  }

  // -----------------------------
  // Nav wiring (FIXED)
  // -----------------------------
  function wireNav() {
    qsa(".nav-btn").forEach((btn) => {
      TAP.bind(btn, () => {
        haptic("impact", "light");
        selectTab(btn.dataset.tab);
      }, { lockMs: 160, moveTol: 14, prevent: true });
    });

    qsa(".tab").forEach((btn) => {
      TAP.bind(btn, () => {
        haptic("impact", "light");
        selectTab(btn.dataset.tab);
      }, { lockMs: 160, moveTol: 14, prevent: true });
    });
  }

  // -----------------------------
  // Header chips
  // -----------------------------
  function wireHeaderChips() {
    const chipVoice = qs("#chipVoice");
    const chipMode = qs("#chipMode");
    const chipPlatform = qs("#chipPlatform");

    TAP.bind(chipVoice, async () => {
      haptic("impact", "light");
      state.voice = (state.voice === "COACH") ? "TEAMMATE" : "COACH";
      setChipText();
      setActiveSeg("#segVoice", state.voice);
      await saveState();
      toast(state.voice === "COACH" ? "Коуч включён 📚" : "Тиммейт 🤝");
    });

    TAP.bind(chipMode, async () => {
      haptic("impact", "light");
      state.mode = (state.mode === "Normal") ? "Pro" : (state.mode === "Pro" ? "Demon" : "Normal");
      setChipText();
      setActiveSeg("#segMode", state.mode);
      await saveState();
      toast(`Режим: ${state.mode}`);
    });

    TAP.bind(chipPlatform, async () => {
      haptic("impact", "light");
      state.platform = (state.platform === "PC") ? "PlayStation" : (state.platform === "PlayStation" ? "Xbox" : "PC");
      setChipText();
      setActiveSeg("#segPlatform", state.platform);
      await saveState();
      toast(`Platform: ${state.platform}`);
    });
  }

  // =========================================================
  // 🎯 AIM TRIAL
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
    const y = pad + Math.random() * (maxY - pad - 6);

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

  // -----------------------------
  // Buttons wiring (FIXED)
  // -----------------------------
  function wireButtons() {
    TAP.bind(qs("#btnClose"), () => {
      haptic("impact", "medium");
      tg?.close?.();
    });

    // home / bot
    TAP.bind(qs("#btnOpenBot"), () => openBotMenuHint("main"));
    TAP.bind(qs("#btnPremium"), () => openBotMenuHint("premium"));
    TAP.bind(qs("#btnSync"), () => sendToBot({ type: "sync_request", profile: true }));

    // coach / vod / settings / zombies (bot-side)
    TAP.bind(qs("#btnOpenTraining"), () => openBotMenuHint("training"));
    TAP.bind(qs("#btnSendPlan"), () => sendToBot({ type: "training_plan", focus: state.focus, profile: true }));

    TAP.bind(qs("#btnOpenVod"), () => openBotMenuHint("vod"));
    TAP.bind(qs("#btnSendVod"), () => {
      const t1 = (qs("#vod1")?.value || "").trim();
      const t2 = (qs("#vod2")?.value || "").trim();
      const t3 = (qs("#vod3")?.value || "").trim();
      const note = (qs("#vodNote")?.value || "").trim();
      sendToBot({ type: "vod", times: [t1, t2, t3].filter(Boolean), note, profile: true });
    });

    TAP.bind(qs("#btnOpenSettings"), () => openBotMenuHint("settings"));
    TAP.bind(qs("#btnApplyProfile"), () => sendToBot({ type: "set_profile", profile: true }));

    TAP.bind(qs("#btnOpenZombies"), () => sendToBot({ type: "zombies_open", map: state.zombies_map, profile: true }));
    TAP.bind(qs("#btnZPerks"), () => sendToBot({ type: "zombies", action: "perks", map: state.zombies_map, profile: true }));
    TAP.bind(qs("#btnZLoadout"), () => sendToBot({ type: "zombies", action: "loadout", map: state.zombies_map, profile: true }));
    TAP.bind(qs("#btnZEggs"), () => sendToBot({ type: "zombies", action: "eggs", map: state.zombies_map, profile: true }));
    TAP.bind(qs("#btnZRound"), () => sendToBot({ type: "zombies", action: "rounds", map: state.zombies_map, profile: true }));
    TAP.bind(qs("#btnZTips"), () => sendToBot({ type: "zombies", action: "tips", map: state.zombies_map, profile: true }));

    // pay
    TAP.bind(qs("#btnBuyMonth"), () => sendToBot({ type: "pay", plan: "premium_month", profile: true }));
    TAP.bind(qs("#btnBuyLife"), () => sendToBot({ type: "pay", plan: "premium_lifetime", profile: true }));

    TAP.bind(qs("#btnShare"), () => {
      const text =
        "BLACK CROWN OPS 😈\n" +
        "Тренировки, VOD, настройки, Zombies — всё в одном месте.\n" +
        "Mini App + Fullscreen Zombies (Arcade/Roguelike).";
      tryShare(text);
    });

    // chat
    TAP.bind(qs("#btnChatSend"), () => sendChatFromUI());
    TAP.bind(qs("#btnChatClear"), async () => {
      haptic("impact", "light");
      chat.history = [];
      await saveChat();
      renderChat();
      toast("Чат очищен ✅");
    });
    TAP.bind(qs("#btnChatExport"), () => {
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
      }, { passive: true });
    }

    // AIM game
    const { arena, target, btnStart, btnStop, btnSend } = aimEls();
    TAP.bind(btnStart, () => aimStart());
    TAP.bind(btnStop, () => aimStop(false));
    TAP.bind(btnSend, () => aimSendResult());

    if (arena && target) {
      TAP.bind(target, (e) => {
        if (!aim.running) return;
        aim.shots += 1;
        aim.hits += 1;
        haptic("impact", "light");
        aimMoveTarget();
        aimUpdateUI();
        try { e?.preventDefault?.(); } catch {}
        try { e?.stopPropagation?.(); } catch {}
      }, { lockMs: 80, moveTol: 18, prevent: true });

      TAP.bind(arena, () => {
        if (!aim.running) return;
        aim.shots += 1;
        haptic("impact", "light");
        aimUpdateUI();
      }, { lockMs: 80, moveTol: 18, prevent: true });
    }

    // =========================================================
    // ✅ ZOMBIES (NEW ENGINE) — fixed taps + fullscreen entry
    // =========================================================
    const btnZArc = qs("#btnZModeArcade");
    const btnZRog = qs("#btnZModeRogue");
    const btnZStart = qs("#btnZGameStart");
    const btnZStop = qs("#btnZGameStop");
    const btnZSend = qs("#btnZGameSend");

    TAP.bind(btnZArc, async () => {
      if (!zombiesEnsureOpen(true)) return;
      zombiesSetMode("arcade");
      await saveState();
      toast("Zombies: Arcade 💥");
    });

    TAP.bind(btnZRog, async () => {
      if (!zombiesEnsureOpen(true)) return;
      zombiesSetMode("roguelike");
      await saveState();
      toast("Zombies: Roguelike 😈");
    });

    TAP.bind(btnZStart, () => {
      if (!zombiesEnsureOpen(true)) return;
      zombiesStart();
      toast("Zombies: старт ▶");
    });

    TAP.bind(btnZStop, () => {
      if (!zombiesEnsureOpen(true)) return;
      zombiesStop();
      toast("Zombies: стоп ⛔");
    });

    TAP.bind(btnZSend, () => {
      if (!zombiesEnsureOpen(true)) return;
      zombiesSendResult();
    });

    // Old home "Shop" buttons => perks on new engine
    TAP.bind(qs("#btnZBuyJug"), () => {
      if (!zombiesEnsureOpen(true)) return;
      zombiesSetMode("roguelike");
      zombiesStart();
      zombiesBuyPerk("Jug");
    });

    TAP.bind(qs("#btnZBuySpeed"), () => {
      if (!zombiesEnsureOpen(true)) return;
      zombiesSetMode("roguelike");
      zombiesStart();
      zombiesBuyPerk("Speed");
    });

    TAP.bind(qs("#btnZBuyAmmo"), () => {
      if (!zombiesEnsureOpen(true)) return;
      zombiesSetMode("roguelike");
      zombiesStart();
      zombiesBuyPerk("Mag");
    });

    // Bonus: reload / plate buttons if exist in UI (future-proof)
    TAP.bind(qs("#btnZReload"), () => { try { window.BCO_ZOMBIES_CORE?.reload?.(); } catch {} }, { prevent: true });
    TAP.bind(qs("#btnZPlate"), () => { try { window.BCO_ZOMBIES_CORE?.usePlate?.(); } catch {} }, { prevent: true });
  }

  // -----------------------------
  // Build tag
  // -----------------------------
  function ensureBuildTag() {
    const buildFromIndex =
      (window.__BCO_BUILD__ && window.__BCO_BUILD__ !== "__BUILD__")
        ? window.__BCO_BUILD__
        : null;

    const txt = buildFromIndex ? `build ${buildFromIndex} • v${VERSION}` : `v${VERSION}`;
    const buildTag = qs("#buildTag");
    if (buildTag) buildTag.textContent = txt;
  }

  // -----------------------------
  // Telegram init
  // -----------------------------
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

  // -----------------------------
  // Boot
  // -----------------------------
  async function boot() {
    if (document.readyState !== "complete" && document.readyState !== "interactive") {
      await new Promise((r) => document.addEventListener("DOMContentLoaded", r, { once: true }));
    }

    // harden tap & UI first (fix “не нажимаются”)
    try { TAP.hardenUI(); } catch {}

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

    // If user already on zombies tab by hash, respect (future-proof)
    try {
      const hash = String(location.hash || "").replace("#", "");
      if (hash && qs(`#tab-${hash}`)) selectTab(hash);
    } catch {}
  }

  boot();
})();
