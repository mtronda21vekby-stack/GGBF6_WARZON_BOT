// app/webapp/static/app.js
(() => {
  "use strict";
  window.__BCO_JS_OK__ = true;

  const tg = window.Telegram?.WebApp;

  // =========================
  // VERSION / STORAGE
  // =========================
  const VERSION = "1.4.1"; // ✅ bump (no breaking)
  const STORAGE_KEY = "bco_state_v1";
  const CHAT_KEY = "bco_chat_v1";

  // =========================
  // DEFAULTS / STATE
  // =========================
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

    // ✅ Zombies cosmetics
    character: "male", // male | female
    skin: "default",

    // ✅ Game tab defaults
    zombies_mode: "arcade", // arcade | roguelike

    // ✅ Future: 3D readiness flag
    render: "2d", // "2d" | "3d"

    // ✅ NEW: Roguelike economy fallback (if engine bugs)
    z_coins: 0,
    z_best: { arcade: 0, roguelike: 0 },

    // ✅ NEW: Wonder weapon quest
    z_relics: 0,              // 0..5
    z_wonder_unlocked: false, // true after 5 relics
    z_wonder_weapon: "CROWN_RAY", // name/id placeholder

    // ✅ Future: levels (saved for later, no UI yet)
    acc_xp: 0,
    acc_level: 1,
    z_xp: 0,
    z_level: 1
  };

  const state = { ...defaults };

  const chat = {
    history: [],
    lastAskAt: 0
  };

  // =========================
  // HELPERS
  // =========================
  const qs = (s) => document.querySelector(s);
  const qsa = (s) => Array.from(document.querySelectorAll(s));
  const now = () => Date.now();

  function safeJsonParse(s) { try { return JSON.parse(s); } catch { return null; } }

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
  // ✅ ULTRA TAP (iOS SAFE) — no dead clicks, no double fires
  // =========================================================
  // Upgrades vs your old onTap:
  // - pointerdown + pointerup (capture) to avoid lost events under overlays
  // - preventDefault on touchstart/touchend (non-passive) to kill ghost taps/scroll
  // - stronger target normalization + lock
  function onTap(el, handler, opts = {}) {
    if (!el) return;
    const lockMs = Math.max(120, opts.lockMs ?? 220);

    let locked = false;
    const lock = () => {
      locked = true;
      setTimeout(() => (locked = false), lockMs);
    };

    const fire = (e) => {
      if (locked) return;
      lock();
      try { handler(e); } catch {}
    };

    // Pointer path (best)
    if (window.PointerEvent) {
      // prevent text selection / click-through
      el.style.touchAction = el.style.touchAction || "manipulation";

      el.addEventListener("pointerdown", (e) => {
        if (typeof e.button === "number" && e.button !== 0) return;
        // capture helps when finger drifts
        try { el.setPointerCapture?.(e.pointerId); } catch {}
      }, { capture: true, passive: true });

      el.addEventListener("pointerup", (e) => {
        if (typeof e.button === "number" && e.button !== 0) return;
        fire(e);
      }, { capture: true, passive: true });

      // safety fallback
      el.addEventListener("click", (e) => fire(e), { capture: true, passive: true });
      return;
    }

    // Touch fallback (must be non-passive to preventDefault)
    el.addEventListener("touchstart", (e) => {
      try { e.preventDefault?.(); } catch {}
    }, { capture: true, passive: false });

    el.addEventListener("touchend", (e) => {
      try { e.preventDefault?.(); } catch {}
      fire(e);
    }, { capture: true, passive: false });

    // Click fallback
    el.addEventListener("click", (e) => fire(e), { capture: true, passive: true });
  }

  // =========================
  // THEME SYNC
  // =========================
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

  // =========================
  // STORAGE (Cloud + Local)
  // =========================
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
      // clamp new fields
      state.z_relics = clampInt(state.z_relics, 0, 5);
      state.z_coins = clampInt(state.z_coins, 0, 999999);
      state.acc_level = clampInt(state.acc_level, 1, 999999);
      state.z_level = clampInt(state.z_level, 1, 999999);
      return "cloud";
    }

    const fromLocal = localStorage.getItem(STORAGE_KEY);
    const parsedLocal = fromLocal ? safeJsonParse(fromLocal) : null;
    if (parsedLocal && typeof parsedLocal === "object") {
      Object.assign(state, defaults, parsedLocal);
      state.z_relics = clampInt(state.z_relics, 0, 5);
      state.z_coins = clampInt(state.z_coins, 0, 999999);
      state.acc_level = clampInt(state.acc_level, 1, 999999);
      state.z_level = clampInt(state.z_level, 1, 999999);
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

  // =========================
  // MATH / CLAMPS
  // =========================
  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
  function clampInt(v, a, b) {
    const n = Number.isFinite(+v) ? Math.floor(+v) : a;
    return clamp(n, a, b);
  }
  function len(x, y) { return Math.sqrt(x * x + y * y); }

  // =========================
  // UI HELPERS
  // =========================
  let currentTab = "home";

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

  function selectTab(tab) {
    if (tab === "zombies") tab = "game";
    currentTab = tab;

    qsa(".tabpane").forEach((p) => p.classList.toggle("active", p.id === `tab-${tab}`));
    setActiveNav(tab);
    setActiveTopTabs(tab);

    updateTelegramButtons();

    try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch {}
  }

  // =========================
  // PAYLOAD / SEND TO BOT
  // =========================
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

  // =========================
  // SHARE
  // =========================
  function tryShare(text) {
    try {
      navigator.clipboard?.writeText?.(text);
      toast("Скопировано ✅");
    } catch {
      alert(text);
    }
  }

  // =========================================================
  // ✅ STOP ZOOM (premium): kill pinch/double-tap zoom in GAME
  // =========================================================
  function installNoZoomGuards() {
    // iOS Safari / WebView: prevent pinch + dbltap zoom while game active
    let lastTouchEnd = 0;

    document.addEventListener("gesturestart", (e) => {
      if (!GAME.active) return;
      try { e.preventDefault?.(); } catch {}
    }, { passive: false });

    document.addEventListener("gesturechange", (e) => {
      if (!GAME.active) return;
      try { e.preventDefault?.(); } catch {}
    }, { passive: false });

    document.addEventListener("gestureend", (e) => {
      if (!GAME.active) return;
      try { e.preventDefault?.(); } catch {}
    }, { passive: false });

    document.addEventListener("touchmove", (e) => {
      if (!GAME.active) return;
      if ((e.touches?.length || 0) > 1) {
        try { e.preventDefault?.(); } catch {}
      }
    }, { passive: false });

    document.addEventListener("touchend", (e) => {
      if (!GAME.active) return;
      const nowt = Date.now();
      if (nowt - lastTouchEnd <= 260) {
        try { e.preventDefault?.(); } catch {}
      }
      lastTouchEnd = nowt;
    }, { passive: false });
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
  // 🧟 ZOMBIES ENGINE BRIDGE (BCO_ZOMBIES)
  // =========================================================
  function ZB() { return window.BCO_ZOMBIES || null; }

  function zombiesEnsureLoaded() {
    const z = ZB();
    if (!z) {
      toast("Zombies engine not loaded");
      haptic("notif", "error");
      return null;
    }
    return z;
  }

  function zombiesOpenCore() {
    const z = zombiesEnsureLoaded();
    if (!z) return false;
    try { z.open?.({ map: state.zombies_map, character: state.character, skin: state.skin }); } catch {}
    return true;
  }

  function zombiesSetMode(mode) {
    state.zombies_mode = (mode === "roguelike") ? "roguelike" : "arcade";
    const z = ZB();
    if (!z) return;
    try { z.setMode?.(state.zombies_mode); } catch {}
    try { z.mode?.(state.zombies_mode); } catch {}
  }

  function zombiesStartRun() {
    const z = zombiesEnsureLoaded();
    if (!z) return false;
    try { z.start?.({ map: state.zombies_map, mode: state.zombies_mode, character: state.character, skin: state.skin }); return true; } catch {}
    try { z.start?.(); return true; } catch {}
    return false;
  }

  function zombiesStopRun(reason = "manual") {
    const z = ZB();
    if (!z) return;
    try { z.stop?.(reason); } catch {}
    try { z.stop?.(); } catch {}
  }

  function zombiesSendResult(reason = "manual") {
    const z = ZB();
    // include premium extras (economy + quest)
    const extra = {
      coins: GAME?.econ?.coins ?? state.z_coins ?? 0,
      relics: state.z_relics ?? 0,
      wonder_unlocked: !!state.z_wonder_unlocked,
      wonder_weapon: state.z_wonder_unlocked ? state.z_wonder_weapon : null
    };

    if (z) {
      try { z.sendResult?.(reason, extra); return; } catch {}
      try { z.result?.(reason, extra); return; } catch {}
    }

    sendToBot({
      action: "game_result",
      game: "zombies",
      mode: state.zombies_mode,
      map: state.zombies_map,
      reason,
      profile: true,
      ...extra
    });
  }

  function zombiesBuyPerk(id) {
    const z = ZB();
    if (!z) return false;
    try { z.buyPerk?.(id); return true; } catch {}
    try { z.buy?.(id); return true; } catch {}
    try { z.perk?.(id); return true; } catch {}
    return false;
  }

  function zombiesUpgrade() {
    const z = ZB();
    if (!z) return false;
    try { z.upgrade?.(); return true; } catch {}
    try { z.shop?.("upgrade"); return true; } catch {}
    return false;
  }

  function zombiesReroll() {
    const z = ZB();
    if (!z) return false;
    try { z.reroll?.(); return true; } catch {}
    try { z.roll?.(); return true; } catch {}
    try { z.shop?.("reroll"); return true; } catch {}
    return false;
  }

  function zombiesReload() {
    const z = ZB();
    if (!z) return false;
    try { z.reload?.(); return true; } catch {}
    try { z.shop?.("reload"); return true; } catch {}
    return false;
  }

  function zombiesTryUnlockWonder() {
    const z = ZB();
    if (!z) return false;
    const id = state.z_wonder_weapon || "CROWN_RAY";
    try { z.unlockWeapon?.(id); return true; } catch {}
    try { z.unlock?.({ weapon: id }); return true; } catch {}
    try { z.grantWeapon?.(id); return true; } catch {}
    return false;
  }

  // =========================================================
  // ✅ FULLSCREEN GAME TAKEOVER (FIXES fullscreen + premium UX)
  // =========================================================
  const GAME = {
    active: false,
    overlay: null,
    canvas: null,
    hudPill: null,
    hudPill2: null,
    shop: null,
    modal: null,
    modalTitle: null,
    modalBody: null,

    // ✅ NEW: economy + quest runtime
    econ: {
      enabled: true,
      coins: 0,
      lastKills: 0,
      lastWave: 0,
      coinsPerKill: 1,
      coinsPerWave: 3,
      // relics: rare drops from kills (roguelike only)
      relicChancePerKill: 0.04, // 4% per kill (tunable)
      // shop prices fallback (if engine doesn't enforce)
      prices: {
        upgrade: 8,
        reroll: 4,
        reload: 3,
        Jug: 12,
        Speed: 10,
        Mag: 8,
        Armor: 10
      }
    }
  };

  function setAppChromeHidden(hidden) {
    const header = qs(".app-header");
    const topTabs = qs(".top-tabs");
    const bottom = qs(".bottom-nav");
    if (header) header.style.display = hidden ? "none" : "";
    if (topTabs) topTabs.style.display = hidden ? "none" : "none";
    if (bottom) bottom.style.display = hidden ? "none" : "";

    document.documentElement.classList.toggle("bco-game", !!hidden);
    document.body.classList.toggle("bco-game", !!hidden);
  }

  function tgFullscreenHints(on) {
    if (!tg) return;
    try { tg.expand?.(); } catch {}
    try { if (on) tg.setHeaderColor?.("#07070b"); } catch {}
    try { if (on) tg.setBackgroundColor?.("#07070b"); } catch {}
  }

  // Browser fullscreen helper (Telegram may ignore, but harmless)
  async function tryBrowserFullscreen(el) {
    try {
      if (!el) return false;
      if (document.fullscreenElement) return true;
      if (el.requestFullscreen) { await el.requestFullscreen({ navigationUI: "hide" }); return true; }
      return false;
    } catch { return false; }
  }

  // ===== Joystick
  class Joy {
    constructor(root, knob) {
      this.root = root;
      this.knob = knob;
      this.active = false;
      this.pid = null;
      this.cx = 0;
      this.cy = 0;
      this.r = 1;
      this.vx = 0;
      this.vy = 0;

      this._onDown = this._onDown.bind(this);
      this._onMove = this._onMove.bind(this);
      this._onUp = this._onUp.bind(this);

      this._wire();
      this._recalc();
      window.addEventListener("resize", () => this._recalc(), { passive: true });
      window.addEventListener("orientationchange", () => setTimeout(() => this._recalc(), 140), { passive: true });
    }

    _recalc() {
      const r = this.root.getBoundingClientRect();
      this.cx = r.left + r.width / 2;
      this.cy = r.top + r.height / 2;
      this.r = Math.max(1, (Math.min(r.width, r.height) / 2) - 10);
    }

    _setKnob(nx, ny) {
      const px = nx * (this.r * 0.62);
      const py = ny * (this.r * 0.62);
      this.knob.style.transform = `translate(${px}px, ${py}px)`;
    }

    _setVec(nx, ny) {
      this.vx = nx;
      this.vy = ny;
      this._setKnob(nx, ny);
    }

    _onDown(e) {
      this.active = true;
      this.pid = e.pointerId ?? "t";
      try { this.root.setPointerCapture?.(e.pointerId); } catch {}
      this._recalc();
      this._onMove(e);
    }

    _onMove(e) {
      if (!this.active) return;
      if (this.pid != null && e.pointerId != null && e.pointerId !== this.pid) return;
      const x = (e.clientX ?? 0) - this.cx;
      const y = (e.clientY ?? 0) - this.cy;
      const d = Math.max(1, len(x, y));
      const nx = clamp(x / d, -1, 1) * clamp(d / this.r, 0, 1);
      const ny = clamp(y / d, -1, 1) * clamp(d / this.r, 0, 1);
      this._setVec(nx, ny);
    }

    _onUp(e) {
      if (!this.active) return;
      if (this.pid != null && e.pointerId != null && e.pointerId !== this.pid) return;
      this.active = false;
      this.pid = null;
      this._setVec(0, 0);
    }

    _wire() {
      const el = this.root;

      // Make joysticks totally scroll-proof
      el.style.touchAction = "none";

      if (window.PointerEvent) {
        el.addEventListener("pointerdown", (e) => {
          // iOS: stop page gestures
          try { e.preventDefault?.(); } catch {}
          this._onDown(e);
        }, { passive: false });

        window.addEventListener("pointermove", this._onMove, { passive: true });
        window.addEventListener("pointerup", this._onUp, { passive: true });
        window.addEventListener("pointercancel", this._onUp, { passive: true });
        return;
      }

      el.addEventListener("touchstart", (ev) => {
        try { ev.preventDefault?.(); } catch {}
        const t = ev.changedTouches?.[0];
        if (!t) return;
        this.active = true;
        this.pid = "t";
        this._recalc();
        this._onMove({ clientX: t.clientX, clientY: t.clientY });
      }, { passive: false });

      window.addEventListener("touchmove", (ev) => {
        if (!this.active) return;
        const t = ev.changedTouches?.[0];
        if (!t) return;
        this._onMove({ clientX: t.clientX, clientY: t.clientY });
      }, { passive: true });

      window.addEventListener("touchend", () => this._onUp({}), { passive: true });
      window.addEventListener("touchcancel", () => this._onUp({}), { passive: true });
    }
  }

  // Expose input for engine polling (non-breaking)
  window.BCO_ZOMBIES_INPUT = window.BCO_ZOMBIES_INPUT || {
    move: { x: 0, y: 0 },
    aim: { x: 0, y: 0 },
    firing: false,
    updatedAt: 0
  };

  function pushZInput() {
    const z = ZB();
    const inp = window.BCO_ZOMBIES_INPUT;
    inp.updatedAt = now();

    try { z?.setMove?.(inp.move.x, inp.move.y); } catch {}
    try { z?.setAim?.(inp.aim.x, inp.aim.y); } catch {}
    try { z?.setFire?.(!!inp.firing); } catch {}
    try { z?.input?.(inp); } catch {}
  }

  let inputTimer = 0;
  function startInputPump() {
    if (inputTimer) return;
    inputTimer = setInterval(pushZInput, 33);
  }
  function stopInputPump() {
    if (!inputTimer) return;
    clearInterval(inputTimer);
    inputTimer = 0;
  }

  // =========================================================
  // ✅ ROGUELIKE ECONOMY FALLBACK (coins + relics) — premium fix
  // =========================================================
  function econResetForRun() {
    GAME.econ.coins = clampInt(state.z_coins ?? 0, 0, 999999);
    GAME.econ.lastKills = 0;
    GAME.econ.lastWave = 0;
  }

  function econAddCoins(n, why = "") {
    const add = clampInt(n, 0, 999999);
    if (!add) return;
    GAME.econ.coins = clampInt((GAME.econ.coins || 0) + add, 0, 999999);
    state.z_coins = GAME.econ.coins;
    // best effort: tell engine too
    const z = ZB();
    try { z?.addCoins?.(add); } catch {}
    try { z?.coins?.(GAME.econ.coins); } catch {}
    try { z?.setCoins?.(GAME.econ.coins); } catch {}
    try { z?.awardCoins?.(add); } catch {}
    // small feedback
    if (why) toast(`+${add} 💰 ${why}`);
    saveState().catch(() => {});
  }

  function econSpend(cost) {
    const c = clampInt(cost, 0, 999999);
    if (GAME.econ.coins < c) return false;
    GAME.econ.coins -= c;
    state.z_coins = GAME.econ.coins;
    // best effort engine sync
    const z = ZB();
    try { z?.coins?.(GAME.econ.coins); } catch {}
    try { z?.setCoins?.(GAME.econ.coins); } catch {}
    saveState().catch(() => {});
    return true;
  }

  function tryDropRelicFromKill() {
    if (state.z_wonder_unlocked) return;
    if (state.z_relics >= 5) return;
    if (state.zombies_mode !== "roguelike") return;

    const r = Math.random();
    if (r <= GAME.econ.relicChancePerKill) {
      state.z_relics = clampInt((state.z_relics || 0) + 1, 0, 5);
      saveState().catch(() => {});
      toast(`Реликвия найдена 🗿 (${state.z_relics}/5)`);

      // unlock at 5
      if (state.z_relics >= 5) {
        state.z_wonder_unlocked = true;
        saveState().catch(() => {});
        haptic("notif", "success");
        toast("ЧУДО-ОРУЖИЕ ОТКРЫТО 👑⚡");
        // try to unlock in engine
        zombiesTryUnlockWonder();
      }
    }
  }

  function econOnHud(h) {
    // If engine emits kills/wave — we patch coins + relics for roguelike
    const kills = clampInt(h?.kills ?? h?.frags ?? 0, 0, 999999);
    const wave = clampInt(h?.wave ?? h?.round ?? 0, 0, 999999);

    // coins by kills
    if (kills > GAME.econ.lastKills) {
      const dk = kills - GAME.econ.lastKills;
      GAME.econ.lastKills = kills;

      if (state.zombies_mode === "roguelike") {
        econAddCoins(dk * GAME.econ.coinsPerKill, "");
        // relic chance per kill
        for (let i = 0; i < dk; i++) tryDropRelicFromKill();
      }
    }

    // coins by waves
    if (wave > GAME.econ.lastWave) {
      const dw = wave - GAME.econ.lastWave;
      GAME.econ.lastWave = wave;

      if (state.zombies_mode === "roguelike") {
        econAddCoins(dw * GAME.econ.coinsPerWave, `Wave ${wave}`);
      }
    }
  }

  // =========================================================
  // ✅ OVERLAY DOM (fullscreen + shop clarity + modals)
  // =========================================================
  function buildOverlayDOM() {
    if (GAME.overlay) return GAME.overlay;

    const mount = qs("#zOverlayMount") || document.body;

    const overlay = document.createElement("div");
    overlay.className = "bco-z-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-label", "Zombies Fullscreen");

    // canvas
    const canvas = document.createElement("canvas");
    canvas.className = "bco-z-canvas";
    canvas.width = 1;
    canvas.height = 1;

    // topbar
    const topbar = document.createElement("div");
    topbar.className = "bco-z-topbar";

    const left = document.createElement("div");
    left.className = "left";
    left.innerHTML = `
      <div class="bco-z-title">🧟 Zombies Survival</div>
      <div class="bco-z-sub" id="bcoZSub">${esc(state.zombies_mode.toUpperCase())} • ${esc(state.zombies_map)}</div>
    `;

    const right = document.createElement("div");
    right.className = "right";

    const btnExit = document.createElement("button");
    btnExit.className = "bco-z-mini";
    btnExit.type = "button";
    btnExit.textContent = "✖ Exit";

    const btnShop = document.createElement("button");
    btnShop.className = "bco-z-mini";
    btnShop.type = "button";
    btnShop.textContent = "🛒 Shop";

    const btnCharacter = document.createElement("button");
    btnCharacter.className = "bco-z-mini";
    btnCharacter.type = "button";
    btnCharacter.textContent = "🎭 Character";

    const btnSend = document.createElement("button");
    btnSend.className = "bco-z-mini";
    btnSend.type = "button";
    btnSend.textContent = "📤 Send";

    right.appendChild(btnShop);
    right.appendChild(btnCharacter);
    right.appendChild(btnSend);
    right.appendChild(btnExit);

    topbar.appendChild(left);
    topbar.appendChild(right);

    // HUD
    const hud = document.createElement("div");
    hud.className = "bco-z-hud";

    const pill = document.createElement("div");
    pill.className = "bco-z-pill";
    pill.id = "bcoHud1";
    pill.textContent = "❤️ — • 🔫 — • 💰 —";

    const pill2 = document.createElement("div");
    pill2.className = "bco-z-pill";
    pill2.id = "bcoHud2";
    pill2.textContent = "Wave — • Kills — • Quest —";

    hud.appendChild(pill);
    hud.appendChild(pill2);

    // controls (dual-stick)
    const controls = document.createElement("div");
    controls.className = "bco-z-controls";

    // left stick
    const joyL = document.createElement("div");
    joyL.className = "bco-joy";
    joyL.innerHTML = `<div class="bco-joy-knob"></div>`;

    // right stick (aim)
    const joyR = document.createElement("div");
    joyR.className = "bco-joy";
    joyR.innerHTML = `<div class="bco-joy-knob"></div>`;

    // fire button (keep)
    const fire = document.createElement("div");
    fire.className = "bco-fire";
    fire.textContent = "FIRE";

    // layout
    const leftWrap = document.createElement("div");
    leftWrap.style.display = "flex";
    leftWrap.style.gap = "12px";
    leftWrap.appendChild(joyL);

    const rightWrap = document.createElement("div");
    rightWrap.style.display = "flex";
    rightWrap.style.gap = "12px";
    rightWrap.appendChild(fire);
    rightWrap.appendChild(joyR);

    controls.appendChild(leftWrap);
    controls.appendChild(rightWrap);

    // shop bar (quick)
    const shop = document.createElement("div");
    shop.className = "bco-z-shop";
    shop.innerHTML = `
      <button class="bco-shopbtn primary" type="button" data-act="upgrade">⬆️ Upgrade</button>
      <button class="bco-shopbtn" type="button" data-act="reroll">🎲 Reroll</button>
      <button class="bco-shopbtn" type="button" data-act="reload">🔄 Reload</button>
      <button class="bco-shopbtn" type="button" data-perk="Jug">🧪 Jug</button>
      <button class="bco-shopbtn" type="button" data-perk="Speed">⚡ Speed</button>
      <button class="bco-shopbtn" type="button" data-perk="Mag">📦 Mag</button>
      <button class="bco-shopbtn" type="button" data-perk="Armor">🛡 Armor</button>
    `;

    // modal
    const modal = document.createElement("div");
    modal.className = "bco-z-modal";
    modal.id = "bcoZModal";
    modal.innerHTML = `
      <div class="bco-z-card">
        <h3 id="bcoZModalTitle">Title</h3>
        <p id="bcoZModalDesc">Desc</p>
        <div id="bcoZModalBody"></div>
        <div style="display:flex; gap:10px; margin-top:12px; justify-content:flex-end;">
          <button class="bco-shopbtn" type="button" id="bcoZModalClose">Close</button>
        </div>
      </div>
    `;

    overlay.appendChild(canvas);
    overlay.appendChild(topbar);
    overlay.appendChild(hud);
    overlay.appendChild(shop);
    overlay.appendChild(controls);
    overlay.appendChild(modal);

    mount.appendChild(overlay);

    // refs
    GAME.overlay = overlay;
    GAME.canvas = canvas;
    GAME.hudPill = pill;
    GAME.hudPill2 = pill2;
    GAME.shop = shop;
    GAME.modal = modal;
    GAME.modalTitle = modal.querySelector("#bcoZModalTitle");
    GAME.modalBody = modal.querySelector("#bcoZModalBody");

    // ===== wire topbar buttons (tap-safe)
    onTap(btnExit, () => { haptic("impact", "medium"); exitGame(); });
    onTap(btnSend, () => { haptic("impact", "light"); zombiesSendResult("manual"); });
    onTap(btnShop, () => { haptic("impact", "light"); openShopModal(); });
    onTap(btnCharacter, () => { haptic("impact", "light"); openCharacterModal(); });

    // ===== shop quick actions (with economy guard in roguelike)
    onTap(shop, (e) => {
      const btn = e?.target?.closest?.(".bco-shopbtn");
      if (!btn) return;
      const act = btn.getAttribute("data-act");
      const perk = btn.getAttribute("data-perk");
      haptic("impact", "light");

      if (act) return shopAction(act);
      if (perk) return shopPerk(perk);
    }, { lockMs: 140 });

    // modal close
    onTap(modal.querySelector("#bcoZModalClose"), () => { haptic("impact", "light"); closeModal(); });

    // click outside card closes
    onTap(modal, (e) => { if (e?.target === modal) closeModal(); });

    // ===== Dual-stick
    const knobL = joyL.querySelector(".bco-joy-knob");
    const knobR = joyR.querySelector(".bco-joy-knob");
    const JL = new Joy(joyL, knobL);
    const JR = new Joy(joyR, knobR);

    // FIRE button (hold)
    let firing = false;
    const fireDown = () => {
      firing = true;
      window.BCO_ZOMBIES_INPUT.firing = true;
      haptic("impact", "light");
    };
    const fireUp = () => {
      firing = false;
      window.BCO_ZOMBIES_INPUT.firing = false;
    };

    if (window.PointerEvent) {
      fire.addEventListener("pointerdown", (e) => { try { e.preventDefault?.(); } catch {} fireDown(); }, { passive: false });
      window.addEventListener("pointerup", fireUp, { passive: true });
      window.addEventListener("pointercancel", fireUp, { passive: true });
    } else {
      fire.addEventListener("touchstart", (e) => { try { e.preventDefault?.(); } catch {} fireDown(); }, { passive: false });
      window.addEventListener("touchend", fireUp, { passive: true });
      window.addEventListener("touchcancel", fireUp, { passive: true });
    }

    // input pump from sticks
    const pump = () => {
      if (!GAME.active) return;

      window.BCO_ZOMBIES_INPUT.move.x = JL.vx;
      window.BCO_ZOMBIES_INPUT.move.y = JL.vy;

      window.BCO_ZOMBIES_INPUT.aim.x = JR.vx;
      window.BCO_ZOMBIES_INPUT.aim.y = JR.vy;

      const aimMag = len(JR.vx, JR.vy);
      window.BCO_ZOMBIES_INPUT.firing = !!firing || aimMag > 0.55;

      requestAnimationFrame(pump);
    };
    requestAnimationFrame(pump);

    // disable scroll inside overlay
    overlay.addEventListener("touchmove", (ev) => {
      try { ev.preventDefault?.(); } catch {}
    }, { passive: false });

    return overlay;
  }

  function closeModal() {
    if (!GAME.modal) return;
    GAME.modal.classList.remove("show");
  }

  function shopAffordOrWarn(cost) {
    if (state.zombies_mode !== "roguelike") return true; // arcade: no guard
    const c = clampInt(cost, 0, 999999);
    if (GAME.econ.coins >= c) return true;
    haptic("notif", "error");
    toast(`Не хватает монет 💰 (${GAME.econ.coins}/${c})`);
    return false;
  }

  function shopAction(act) {
    const price = GAME.econ.prices?.[act] ?? 0;

    if (state.zombies_mode === "roguelike") {
      if (!shopAffordOrWarn(price)) return;
      if (!econSpend(price)) return;
    }

    if (act === "upgrade") zombiesUpgrade();
    if (act === "reroll") zombiesReroll();
    if (act === "reload") zombiesReload();

    // small feedback
    if (state.zombies_mode === "roguelike" && price) toast(`-${price} 💰 ${act}`);
    updateOverlayLabels();
  }

  function shopPerk(perk) {
    const price = GAME.econ.prices?.[perk] ?? 0;

    if (state.zombies_mode === "roguelike") {
      if (!shopAffordOrWarn(price)) return;
      if (!econSpend(price)) return;
    }

    const ok = zombiesBuyPerk(perk);
    if (!ok) {
      // if engine missing, still keep UI consistent
      toast(`Perk: ${perk}`);
    }

    if (state.zombies_mode === "roguelike" && price) toast(`-${price} 💰 ${perk}`);
    updateOverlayLabels();
  }

  function openShopModal() {
    buildOverlayDOM();
    if (!GAME.modal) return;

    GAME.modal.classList.add("show");
    if (GAME.modalTitle) GAME.modalTitle.textContent = "🛒 Shop";
    const body = GAME.modal.querySelector("#bcoZModalBody");
    const desc = GAME.modal.querySelector("#bcoZModalDesc");

    const coins = GAME.econ.coins ?? 0;
    const relics = state.z_relics ?? 0;
    const questLine = state.z_wonder_unlocked
      ? `👑 Wonder weapon: UNLOCKED (${esc(state.z_wonder_weapon)})`
      : `🗿 Relics: ${relics}/5 (собери 5 → чудо-оружие)`;

    if (desc) {
      desc.textContent =
        state.zombies_mode === "roguelike"
          ? `Roguelike • 💰 ${coins} • ${questLine}`
          : `Arcade • Быстрые действия и перки. (Экономика активна в Roguelike.)`;
    }

    if (body) {
      const p = GAME.econ.prices;
      body.innerHTML = `
        <div class="bco-z-grid">
          <div class="bco-z-choice">
            <div class="ttl">⬆️ Upgrade</div>
            <div class="sub">Апгрейд оружия/урона/скорости.</div>
            <button class="bco-shopbtn primary" type="button" data-act="upgrade">Buy ${state.zombies_mode==="roguelike" ? `• ${p.upgrade}💰` : ""}</button>
          </div>
          <div class="bco-z-choice">
            <div class="ttl">🎲 Reroll</div>
            <div class="sub">Переброс предложений.</div>
            <button class="bco-shopbtn" type="button" data-act="reroll">Roll ${state.zombies_mode==="roguelike" ? `• ${p.reroll}💰` : ""}</button>
          </div>
          <div class="bco-z-choice">
            <div class="ttl">🔄 Reload</div>
            <div class="sub">Патроны/перезарядка.</div>
            <button class="bco-shopbtn" type="button" data-act="reload">Reload ${state.zombies_mode==="roguelike" ? `• ${p.reload}💰` : ""}</button>
          </div>

          <div class="bco-z-choice">
            <div class="ttl">🧪 Jug</div>
            <div class="sub">Выживаемость.</div>
            <button class="bco-shopbtn" type="button" data-perk="Jug">Buy ${state.zombies_mode==="roguelike" ? `• ${p.Jug}💰` : ""}</button>
          </div>
          <div class="bco-z-choice">
            <div class="ttl">⚡ Speed</div>
            <div class="sub">Скорость/мувмент.</div>
            <button class="bco-shopbtn" type="button" data-perk="Speed">Buy ${state.zombies_mode==="roguelike" ? `• ${p.Speed}💰` : ""}</button>
          </div>
          <div class="bco-z-choice">
            <div class="ttl">📦 Mag</div>
            <div class="sub">Боезапас/магазин.</div>
            <button class="bco-shopbtn" type="button" data-perk="Mag">Buy ${state.zombies_mode==="roguelike" ? `• ${p.Mag}💰` : ""}</button>
          </div>
          <div class="bco-z-choice">
            <div class="ttl">🛡 Armor</div>
            <div class="sub">Снижение урона.</div>
            <button class="bco-shopbtn" type="button" data-perk="Armor">Buy ${state.zombies_mode==="roguelike" ? `• ${p.Armor}💰` : ""}</button>
          </div>

          <div class="bco-z-choice">
            <div class="ttl">🎮 Mode</div>
            <div class="sub">Arcade / Roguelike</div>
            <div style="display:flex; gap:10px; flex-wrap:wrap; margin-top:10px;">
              <button class="bco-shopbtn" type="button" data-mode="arcade">Arcade</button>
              <button class="bco-shopbtn" type="button" data-mode="roguelike">Roguelike</button>
            </div>
          </div>

          <div class="bco-z-choice">
            <div class="ttl">👑 Wonder Quest</div>
            <div class="sub">${state.z_wonder_unlocked ? "Открыто ✅" : `Реликвии: ${relics}/5`}</div>
            <div style="display:flex; gap:10px; flex-wrap:wrap; margin-top:10px;">
              <button class="bco-shopbtn ${state.z_wonder_unlocked ? "primary" : ""}" type="button" data-wonder="status">
                ${state.z_wonder_unlocked ? "Equip/Grant" : "How to get"}
              </button>
              <button class="bco-shopbtn" type="button" data-wonder="reset">Reset quest</button>
            </div>
          </div>
        </div>
      `;

      onTap(body, async (e) => {
        const b = e?.target?.closest?.(".bco-shopbtn");
        if (!b) return;

        const act = b.getAttribute("data-act");
        const perk = b.getAttribute("data-perk");
        const mode = b.getAttribute("data-mode");
        const wonder = b.getAttribute("data-wonder");

        if (act) shopAction(act);
        if (perk) shopPerk(perk);

        if (mode) {
          zombiesSetMode(mode);
          updateOverlayLabels();
          toast(`Mode: ${mode}`);
          await saveState();
          openShopModal(); // refresh UI
        }

        if (wonder === "status") {
          if (state.z_wonder_unlocked) {
            const ok = zombiesTryUnlockWonder();
            toast(ok ? `Equipped: ${state.z_wonder_weapon}` : "Wonder unlocked ✅ (engine hook later)");
          } else {
            toast("Реликвии падают в Roguelike с убийств. Собери 5.");
          }
        }

        if (wonder === "reset") {
          state.z_relics = 0;
          state.z_wonder_unlocked = false;
          await saveState();
          toast("Quest reset ✅");
          openShopModal();
        }
      }, { lockMs: 120 });
    }
  }

  function openCharacterModal() {
    buildOverlayDOM();
    if (!GAME.modal) return;
    GAME.modal.classList.add("show");
    if (GAME.modalTitle) GAME.modalTitle.textContent = "🎭 Character";
    const desc = GAME.modal.querySelector("#bcoZModalDesc");
    if (desc) desc.textContent = "Выбор персонажа/скина сохраняется (state + CloudStorage).";

    const body = GAME.modal.querySelector("#bcoZModalBody");
    if (!body) return;

    const maleOn = state.character === "male";
    const femaleOn = state.character === "female";

    body.innerHTML = `
      <div class="bco-z-grid">
        <div class="bco-z-choice">
          <div class="ttl">👨 Male</div>
          <div class="sub">Текущий: ${maleOn ? "✅" : "—"}</div>
          <button class="bco-shopbtn ${maleOn ? "primary" : ""}" type="button" data-char="male">Select</button>
        </div>
        <div class="bco-z-choice">
          <div class="ttl">👩 Female</div>
          <div class="sub">Текущий: ${femaleOn ? "✅" : "—"}</div>
          <button class="bco-shopbtn ${femaleOn ? "primary" : ""}" type="button" data-char="female">Select</button>
        </div>

        <div class="bco-z-choice">
          <div class="ttl">🎨 Skin</div>
          <div class="sub">Сейчас: ${esc(state.skin)}</div>
          <div style="display:flex; gap:10px; flex-wrap:wrap; margin-top:10px;">
            <button class="bco-shopbtn" type="button" data-skin="default">default</button>
            <button class="bco-shopbtn" type="button" data-skin="neon">neon</button>
            <button class="bco-shopbtn" type="button" data-skin="tactical">tactical</button>
            <button class="bco-shopbtn" type="button" data-skin="shadow">shadow</button>
          </div>
        </div>

        <div class="bco-z-choice">
          <div class="ttl">🖼 Render</div>
          <div class="sub">Под 3D переход (пока 2D ядро)</div>
          <div style="display:flex; gap:10px; flex-wrap:wrap; margin-top:10px;">
            <button class="bco-shopbtn" type="button" data-render="2d">2D</button>
            <button class="bco-shopbtn" type="button" data-render="3d">3D (beta)</button>
          </div>
        </div>
      </div>
    `;

    onTap(body, async (e) => {
      const b = e?.target?.closest?.(".bco-shopbtn");
      if (!b) return;

      const c = b.getAttribute("data-char");
      const s = b.getAttribute("data-skin");
      const r = b.getAttribute("data-render");

      if (c) {
        state.character = c;
        await saveState();
        toast(`Character: ${c}`);
        try { ZB()?.setPlayerSkin?.(state.character, state.skin); } catch {}
        try { ZB()?.open?.({ map: state.zombies_map, character: state.character, skin: state.skin }); } catch {}
        openCharacterModal();
      }

      if (s) {
        state.skin = s;
        await saveState();
        toast(`Skin: ${s}`);
        try { ZB()?.setPlayerSkin?.(state.character, state.skin); } catch {}
        try { ZB()?.open?.({ map: state.zombies_map, character: state.character, skin: state.skin }); } catch {}
        openCharacterModal();
      }

      if (r) {
        state.render = (r === "3d") ? "3d" : "2d";
        await saveState();
        toast(`Render: ${state.render}`);
        try { ZB()?.setRenderMode?.(state.render); } catch {}
        try { ZB()?.renderer?.(state.render); } catch {}
        openCharacterModal();
      }
    }, { lockMs: 120 });
  }

  function updateOverlayLabels(hudLike = null) {
    if (!GAME.overlay) return;

    const sub = GAME.overlay.querySelector("#bcoZSub");
    if (sub) sub.textContent = `${String(state.zombies_mode).toUpperCase()} • ${state.zombies_map}`;

    if (GAME.shop) GAME.shop.style.opacity = (state.zombies_mode === "roguelike") ? "1" : "0.85";

    // HUD text: prefer engine values, but merge our economy + quest
    const h = hudLike || {};
    const hp = (h.hp ?? h.health ?? "—");
    const ammo = (h.ammo ?? "—");
    const gun = (h.weapon ?? h.gun ?? "—");
    const wave = clampInt(h.wave ?? "—", 0, 999999);
    const kills = clampInt(h.kills ?? "—", 0, 999999);

    const coinsEngine = (h.coins ?? h.money ?? null);
    const coins = (coinsEngine != null) ? coinsEngine : (GAME.econ.coins ?? state.z_coins ?? 0);

    const quest = state.z_wonder_unlocked
      ? `👑 Wonder ✅`
      : `🗿 ${clampInt(state.z_relics ?? 0, 0, 5)}/5`;

    if (GAME.hudPill) GAME.hudPill.textContent = `❤️ ${hp} • 🔫 ${gun} (${ammo}) • 💰 ${coins}`;
    if (GAME.hudPill2) GAME.hudPill2.textContent = `Wave ${wave} • Kills ${kills} • ${quest}`;
  }

  function attachEngineToOverlay() {
    const z = zombiesEnsureLoaded();
    if (!z || !GAME.canvas) return;

    try { z.setCanvas?.(GAME.canvas); } catch {}
    try { z.canvas?.(GAME.canvas); } catch {}
    try { z.attach?.(GAME.canvas); } catch {}
    try { z.mount?.(GAME.canvas); } catch {}

    zombiesOpenCore();
    startInputPump();
  }

  async function enterGame() {
    buildOverlayDOM();
    updateOverlayLabels();

    GAME.active = true;
    GAME.overlay.style.display = "block";

    // full takeover
    setAppChromeHidden(true);
    tgFullscreenHints(true);

    // enforce no-zoom in game
    document.body.style.overflow = "hidden";
    await tryBrowserFullscreen(GAME.overlay);

    // economy reset
    econResetForRun();

    // attach engine + run
    attachEngineToOverlay();
    zombiesSetMode(state.zombies_mode);
    zombiesStartRun();

    // ensure overlays are actually tappable on iOS
    installNoZoomGuards();

    haptic("notif", "success");
    toast("Zombies: Fullscreen ▶");
  }

  function exitGame() {
    if (!GAME.overlay) return;
    GAME.active = false;

    try { closeModal(); } catch {}
    try { zombiesStopRun("exit"); } catch {}

    stopInputPump();

    GAME.overlay.style.display = "none";
    setAppChromeHidden(false);

    document.body.style.overflow = "";

    // leave fullscreen if browser allowed it
    try { if (document.fullscreenElement) document.exitFullscreen?.(); } catch {}

    selectTab("game");

    haptic("notif", "warning");
    toast("Zombies: Exit");
  }

  // =========================================================
  // ENGINE HUD / RESULT HOOKS (fix roguelike “coins don’t drop” + quest)
  // =========================================================
  function hookEngineHud() {
    const z = ZB();
    if (!z) return;

    const on = z.on || z.addEventListener;
    if (!on) return;

    try {
      on.call(z, "hud", (hud) => {
        const h = hud || {};
        // patch economy + relic quest from kills/wave
        econOnHud(h);
        // render merged hud
        updateOverlayLabels(h);
      });
    } catch {}

    try {
      on.call(z, "result", async (res) => {
        const r = res || {};
        // sync best scores
        const modeKey = state.zombies_mode === "roguelike" ? "roguelike" : "arcade";
        const score = clampInt(r.score ?? r.points ?? 0, 0, 999999999);
        if (!state.z_best) state.z_best = { arcade: 0, roguelike: 0 };
        state.z_best[modeKey] = Math.max(clampInt(state.z_best[modeKey] ?? 0, 0, 999999999), score);
        // persist coins snapshot
        state.z_coins = clampInt(GAME.econ.coins ?? state.z_coins ?? 0, 0, 999999);
        await saveState();

        // auto-send to bot (keep manual button too)
        try {
          sendToBot({
            action: "game_result",
            game: "zombies",
            mode: state.zombies_mode,
            map: state.zombies_map,
            profile: true,
            coins: state.z_coins,
            relics: state.z_relics,
            wonder_unlocked: !!state.z_wonder_unlocked,
            wonder_weapon: state.z_wonder_unlocked ? state.z_wonder_weapon : null,
            ...r
          });
          toast("Результат отправлен ✅");
        } catch {}
      });
    } catch {}
  }

  // =========================================================
  // TELEGRAM NATIVE BUTTONS
  // =========================================================
  let tgButtonsWired = false;
  let tgMainHandler = null;
  let tgBackHandler = null;

  function updateTelegramButtons() {
    if (!tg) return;

    if (GAME.active) {
      try { tg.MainButton.hide(); } catch {}
      try { tg.BackButton.hide(); } catch {}
      return;
    }

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
          currentTab === "game" ? "🧟 Start Fullscreen" :
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
      if (currentTab === "game") { enterGame(); return; }
      openBotMenuHint("premium");
    };

    tgBackHandler = () => {
      haptic("impact", "light");
      selectTab("home");
    };

    try { tg.MainButton.offClick?.(tgMainHandler); } catch {}
    try { tg.MainButton.onClick?.(tgMainHandler); } catch {}

    try { tg.BackButton.offClick?.(tgBackHandler); } catch {}
    try { tg.BackButton.onClick?.(tgBackHandler); } catch {}
  }

  // =========================
  // BUILD TAG
  // =========================
  function ensureBuildTag() {
    const buildFromIndex =
      (window.__BCO_BUILD__ && window.__BCO_BUILD__ !== "__BUILD__")
        ? window.__BCO_BUILD__
        : null;

    const txt = buildFromIndex ? `build ${buildFromIndex} • v${VERSION}` : `v${VERSION}`;
    const buildTag = qs("#buildTag");
    if (buildTag) buildTag.textContent = txt;
  }

  // =========================
  // INIT TELEGRAM
  // =========================
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

  // =========================
  // SEGMENTS WIRING
  // =========================
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

    onTap(root, (e) => {
      const btn = e?.target?.closest?.(".seg-btn");
      if (!btn) return;
      handler(btn);
    }, { lockMs: 120 });
  }

  // =========================
  // NAV WIRING
  // =========================
  function wireNav() {
    qsa(".nav-btn").forEach((btn) => {
      onTap(btn, () => {
        haptic("impact", "light");
        selectTab(btn.dataset.tab);
      });
    });

    qsa(".tab").forEach((btn) => {
      onTap(btn, () => {
        haptic("impact", "light");
        selectTab(btn.dataset.tab);
      });
    });
  }

  // =========================
  // HEADER CHIPS
  // =========================
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
  // BUTTONS WIRING (ALL)
  // =========================================================
  function wireButtons() {
    onTap(qs("#btnClose"), () => { haptic("impact", "medium"); tg?.close?.(); });

    onTap(qs("#btnShare"), () => {
      const text =
        "BLACK CROWN OPS 😈\n" +
        "Тренировки, VOD, настройки, Zombies — всё в одном месте.\n" +
        "Mini App + Fullscreen Zombies (dual-stick).";
      tryShare(text);
    });

    // premium
    onTap(qs("#btnBuyMonth"), () => sendToBot({ type: "pay", plan: "premium_month", profile: true }));
    onTap(qs("#btnBuyLife"), () => sendToBot({ type: "pay", plan: "premium_lifetime", profile: true }));

    // home
    onTap(qs("#btnOpenBot"), () => openBotMenuHint("main"));
    onTap(qs("#btnPremium"), () => openBotMenuHint("premium"));
    onTap(qs("#btnSync"), () => sendToBot({ type: "sync_request", profile: true }));

    // coach / vod / settings
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

    // chat
    onTap(qs("#btnChatSend"), () => sendChatFromUI());
    onTap(qs("#btnChatClear"), async () => {
      haptic("impact", "light");
      chat.history = [];
      await saveChat();
      renderChat();
      toast("Чат очищен ✅");
    });
    onTap(qs("#btnChatExport"), () => { haptic("impact", "light"); tryShare(exportChatText() || "— пусто —"); });

    const chatInput = qs("#chatInput");
    if (chatInput) {
      chatInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChatFromUI(); }
      }, { passive: false });
    }

    // AIM
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
        e?.preventDefault?.();
        e?.stopPropagation?.();
      }, { lockMs: 60 });

      onTap(arena, () => {
        if (!aim.running) return;
        aim.shots += 1;
        haptic("impact", "light");
        aimUpdateUI();
      }, { lockMs: 60 });
    }

    // Zombies: preview buttons (Home)
    onTap(qs("#btnZModeArcade"), () => { zombiesSetMode("arcade"); toast("Zombies: Arcade 💥"); });
    onTap(qs("#btnZModeRogue"), () => { zombiesSetMode("roguelike"); toast("Zombies: Roguelike 😈"); });
    onTap(qs("#btnZQuickPlay"), () => enterGame());
    onTap(qs("#btnZGameSend"), () => zombiesSendResult("manual"));

    onTap(qs("#btnZBuyJug"), () => shopPerk("Jug"));
    onTap(qs("#btnZBuySpeed"), () => shopPerk("Speed"));
    onTap(qs("#btnZBuyAmmo"), () => shopPerk("Mag"));

    // GAME tab (launcher)
    onTap(qs("#btnPlayZombies"), () => { selectTab("game"); enterGame(); });
    onTap(qs("#btnZEnterGame"), () => enterGame());
    onTap(qs("#btnZGameSend2"), () => zombiesSendResult("manual"));

    onTap(qs("#btnZModeArcade2"), () => { zombiesSetMode("arcade"); updateOverlayLabels(); toast("Mode: Arcade 💥"); });
    onTap(qs("#btnZModeRogue2"), () => { zombiesSetMode("roguelike"); updateOverlayLabels(); toast("Mode: Roguelike 😈"); });

    onTap(qs("#btnZOpenHQ"), () => openBotMenuHint("zombies"));

    // Zombies HQ buttons (bot)
    onTap(qs("#btnOpenZombies"), () => sendToBot({ type: "zombies_open", map: state.zombies_map, profile: true }));
    onTap(qs("#btnZPerks"), () => sendToBot({ type: "zombies", action: "perks", map: state.zombies_map, profile: true }));
    onTap(qs("#btnZLoadout"), () => sendToBot({ type: "zombies", action: "loadout", map: state.zombies_map, profile: true }));
    onTap(qs("#btnZEggs"), () => sendToBot({ type: "zombies", action: "eggs", map: state.zombies_map, profile: true }));
    onTap(qs("#btnZRound"), () => sendToBot({ type: "zombies", action: "rounds", map: state.zombies_map, profile: true }));
    onTap(qs("#btnZTips"), () => sendToBot({ type: "zombies", action: "tips", map: state.zombies_map, profile: true }));

    // Safety: ESC exit
    window.addEventListener("keydown", (e) => { if (e.key === "Escape" && GAME.active) exitGame(); }, { passive: true });
  }

  // =========================
  // BOOT
  // =========================
  async function boot() {
    if (document.readyState !== "complete" && document.readyState !== "interactive") {
      await new Promise((r) => document.addEventListener("DOMContentLoaded", r, { once: true }));
    }

    initTelegram();
    ensureBuildTag();

    const src = await loadState();
    const statSession = qs("#statSession");
    if (statSession) statSession.textContent = src.toUpperCase();

    await loadChat();

    wireNav();

    wireSeg("#segGame", (v) => { state.game = v; });
    wireSeg("#segFocus", (v) => { state.focus = v; });
    wireSeg("#segMode", (v) => { state.mode = v; });
    wireSeg("#segPlatform", (v) => { state.platform = v; });
    wireSeg("#segInput", (v) => { state.input = v; });
    wireSeg("#segVoice", (v) => { state.voice = v; });

    wireSeg("#segZMap", (v) => {
      state.zombies_map = v;
      updateOverlayLabels();
    });

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

    // Engine hooks
    hookEngineHud();

    // start at home
    selectTab("home");

    // deep-link support
    try {
      const hash = String(location.hash || "").replace("#", "").trim();
      if (hash) selectTab(hash);
    } catch {}

    updateTelegramButtons();

    // install zoom guards (they only fully apply when GAME.active)
    installNoZoomGuards();
  }

  boot();
})();
