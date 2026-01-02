// app/webapp/static/app.js
(() => {
  "use strict";
  window.__BCO_JS_OK__ = true;

  const tg = window.Telegram?.WebApp;

  // =========================
  // VERSION / STORAGE
  // =========================
  const VERSION = "1.4.0";
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

    // ✅ Zombies character cosmetics
    character: "male", // male | female
    skin: "default",   // depends on character

    // ✅ Game tab defaults
    zombies_mode: "arcade", // arcade | roguelike

    // ✅ Future: 3D readiness flag (doesn't break 2D)
    render: "2d" // "2d" | "3d" (we keep 2d default)
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
  // Why buttons "don't click" on iOS:
  // - overlay layers / pointer-events
  // - passive touch listeners can't prevent default
  // - click delay / ghost clicks
  // Fix: pointer events + capture + "tap guard" + preventDefault on touch.
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

    // pointer events (preferred)
    if (window.PointerEvent) {
      el.addEventListener("pointerup", (e) => {
        // ignore right/middle click
        if (typeof e.button === "number" && e.button !== 0) return;
        fire(e);
      }, { capture: true, passive: true });
      return;
    }

    // iOS touch fallback (NOT passive so we can preventDefault)
    el.addEventListener("touchend", (e) => {
      try { e.preventDefault?.(); } catch {}
      fire(e);
    }, { capture: true, passive: false });

    // click fallback
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
    // backwards compatibility: if old HTML still has zombies tab, map -> game
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
    if (!z) return;
    try { z.sendResult?.(reason); return; } catch {}
    try { z.result?.(reason); return; } catch {}
    // fallback: send minimal packet to bot
    sendToBot({
      action: "game_result",
      game: "zombies",
      mode: state.zombies_mode,
      map: state.zombies_map,
      reason,
      profile: true
    });
  }

  function zombiesBuyPerk(id) {
    const z = ZB();
    if (!z) return;
    // accept both "Jug" and "Juggernog" etc (engine decides)
    try { z.buyPerk?.(id); return; } catch {}
    try { z.buy?.(id); return; } catch {}
    try { z.perk?.(id); return; } catch {}
  }

  function zombiesUpgrade() {
    const z = ZB();
    if (!z) return;
    try { z.upgrade?.(); return; } catch {}
    try { z.shop?.("upgrade"); return; } catch {}
  }

  function zombiesReroll() {
    const z = ZB();
    if (!z) return;
    try { z.reroll?.(); return; } catch {}
    try { z.roll?.(); return; } catch {}
    try { z.shop?.("reroll"); return; } catch {}
  }

  function zombiesReload() {
    const z = ZB();
    if (!z) return;
    try { z.reload?.(); return; } catch {}
    try { z.shop?.("reload"); return; } catch {}
  }

  // =========================================================
  // ✅ FULLSCREEN GAME TAKEOVER (THIS FIXES "UNPLAYABLE")
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
    modalBody: null
  };

  function setAppChromeHidden(hidden) {
    // Hide sticky header + bottom nav while game runs
    const header = qs(".app-header");
    const topTabs = qs(".top-tabs");
    const bottom = qs(".bottom-nav");
    if (header) header.style.display = hidden ? "none" : "";
    if (topTabs) topTabs.style.display = hidden ? "none" : "none"; // keep hidden as in your HTML
    if (bottom) bottom.style.display = hidden ? "none" : "";

    // add class for future CSS hardening (optional)
    document.documentElement.classList.toggle("bco-game", !!hidden);
    document.body.classList.toggle("bco-game", !!hidden);
  }

  function tgFullscreenHints(on) {
    if (!tg) return;
    try { tg.expand?.(); } catch {}
    try { if (on) tg.setHeaderColor?.("#07070b"); } catch {}
    try { if (on) tg.setBackgroundColor?.("#07070b"); } catch {}
  }

  // ===== Joystick
  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
  function len(x, y) { return Math.sqrt(x * x + y * y); }

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
      window.addEventListener("orientationchange", () => setTimeout(() => this._recalc(), 120), { passive: true });
    }

    _recalc() {
      const r = this.root.getBoundingClientRect();
      this.cx = r.left + r.width / 2;
      this.cy = r.top + r.height / 2;
      this.r = Math.max(1, (Math.min(r.width, r.height) / 2) - 10);
    }

    _setKnob(nx, ny) {
      // knob translate relative to center
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
      if (window.PointerEvent) {
        el.addEventListener("pointerdown", this._onDown, { passive: true });
        window.addEventListener("pointermove", this._onMove, { passive: true });
        window.addEventListener("pointerup", this._onUp, { passive: true });
        window.addEventListener("pointercancel", this._onUp, { passive: true });
        return;
      }
      // fallback touch
      el.addEventListener("touchstart", (ev) => {
        const t = ev.changedTouches?.[0];
        if (!t) return;
        this.active = true;
        this.pid = "t";
        this._recalc();
        this._onMove({ clientX: t.clientX, clientY: t.clientY });
      }, { passive: true });

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

    // If engine supports setters — use them (best)
    try { z?.setMove?.(inp.move.x, inp.move.y); } catch {}
    try { z?.setAim?.(inp.aim.x, inp.aim.y); } catch {}
    try { z?.setFire?.(!!inp.firing); } catch {}
    try { z?.input?.(inp); } catch {}
  }

  let inputTimer = 0;
  function startInputPump() {
    if (inputTimer) return;
    inputTimer = setInterval(pushZInput, 33); // ~30fps input
  }
  function stopInputPump() {
    if (!inputTimer) return;
    clearInterval(inputTimer);
    inputTimer = 0;
  }

  function buildOverlayDOM() {
    // already?
    if (GAME.overlay) return GAME.overlay;

    const mount = qs("#zOverlayMount") || document.body;

    const overlay = document.createElement("div");
    overlay.className = "bco-z-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-label", "Zombies Fullscreen");

    // canvas (engine can use it)
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
    pill2.textContent = "Wave — • Kills — • Mode —";

    hud.appendChild(pill);
    hud.appendChild(pill2);

    // controls (dual-stick)
    const controls = document.createElement("div");
    controls.className = "bco-z-controls";

    // left joystick
    const joyL = document.createElement("div");
    joyL.className = "bco-joy";
    joyL.innerHTML = `<div class="bco-joy-knob"></div>`;

    // right stick (FIRE = aim stick)
    const joyR = document.createElement("div");
    joyR.className = "bco-joy";
    joyR.innerHTML = `<div class="bco-joy-knob"></div>`;

    // fire button (optional, but we keep it for comfort)
    const fire = document.createElement("div");
    fire.className = "bco-fire";
    fire.textContent = "FIRE";

    // layout: left joy / center fire / right joy
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

    // shop bar (quick buy)
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

    // store refs
    GAME.overlay = overlay;
    GAME.canvas = canvas;
    GAME.hudPill = pill;
    GAME.hudPill2 = pill2;
    GAME.shop = shop;
    GAME.modal = modal;
    GAME.modalTitle = modal.querySelector("#bcoZModalTitle");
    GAME.modalBody = modal.querySelector("#bcoZModalBody");

    // wire overlay buttons
    onTap(btnExit, () => {
      haptic("impact", "medium");
      exitGame();
    });

    onTap(btnSend, () => {
      haptic("impact", "light");
      zombiesSendResult("manual");
    });

    onTap(btnShop, () => {
      haptic("impact", "light");
      openShopModal();
    });

    onTap(btnCharacter, () => {
      haptic("impact", "light");
      openCharacterModal();
    });

    // shop quick actions
    onTap(shop, (e) => {
      const btn = e?.target?.closest?.(".bco-shopbtn");
      if (!btn) return;
      const act = btn.getAttribute("data-act");
      const perk = btn.getAttribute("data-perk");
      haptic("impact", "light");

      if (act) {
        if (act === "upgrade") zombiesUpgrade();
        if (act === "reroll") zombiesReroll();
        if (act === "reload") zombiesReload();
        return;
      }

      if (perk) zombiesBuyPerk(perk);
    }, { lockMs: 140 });

    // modal close
    onTap(modal.querySelector("#bcoZModalClose"), () => {
      haptic("impact", "light");
      closeModal();
    });

    // click outside card closes (but only if click background)
    onTap(modal, (e) => {
      if (e?.target === modal) closeModal();
    });

    // Dual-stick logic
    const knobL = joyL.querySelector(".bco-joy-knob");
    const knobR = joyR.querySelector(".bco-joy-knob");
    const JL = new Joy(joyL, knobL);
    const JR = new Joy(joyR, knobR);

    // FIRE button (hold)
    let firing = false;
    if (window.PointerEvent) {
      fire.addEventListener("pointerdown", () => {
        firing = true;
        window.BCO_ZOMBIES_INPUT.firing = true;
        haptic("impact", "light");
      }, { passive: true });
      window.addEventListener("pointerup", () => {
        firing = false;
        window.BCO_ZOMBIES_INPUT.firing = false;
      }, { passive: true });
      window.addEventListener("pointercancel", () => {
        firing = false;
        window.BCO_ZOMBIES_INPUT.firing = false;
      }, { passive: true });
    } else {
      fire.addEventListener("touchstart", () => {
        firing = true;
        window.BCO_ZOMBIES_INPUT.firing = true;
        haptic("impact", "light");
      }, { passive: true });
      window.addEventListener("touchend", () => {
        firing = false;
        window.BCO_ZOMBIES_INPUT.firing = false;
      }, { passive: true });
      window.addEventListener("touchcancel", () => {
        firing = false;
        window.BCO_ZOMBIES_INPUT.firing = false;
      }, { passive: true });
    }

    // input pump from joysticks
    const pump = () => {
      if (!GAME.active) return;
      // left = move
      window.BCO_ZOMBIES_INPUT.move.x = JL.vx;
      window.BCO_ZOMBIES_INPUT.move.y = JL.vy;

      // right = aim direction. If aim is significant, auto-fire even without FIRE button (elite feel)
      window.BCO_ZOMBIES_INPUT.aim.x = JR.vx;
      window.BCO_ZOMBIES_INPUT.aim.y = JR.vy;

      const aimMag = len(JR.vx, JR.vy);
      // If user holds FIRE or aims strongly -> firing true
      window.BCO_ZOMBIES_INPUT.firing = !!firing || aimMag > 0.55;

      requestAnimationFrame(pump);
    };
    requestAnimationFrame(pump);

    // disable iOS scroll/zoom gestures inside overlay
    overlay.addEventListener("touchmove", (ev) => {
      try { ev.preventDefault?.(); } catch {}
    }, { passive: false });

    return overlay;
  }

  function closeModal() {
    if (!GAME.modal) return;
    GAME.modal.classList.remove("show");
  }

  function openShopModal() {
    buildOverlayDOM();
    if (!GAME.modal) return;
    GAME.modal.classList.add("show");
    if (GAME.modalTitle) GAME.modalTitle.textContent = "🛒 Shop";
    const body = GAME.modal.querySelector("#bcoZModalBody");
    const desc = GAME.modal.querySelector("#bcoZModalDesc");
    if (desc) desc.textContent = "Upgrade / Reroll / Reload + быстрые перки. (В Roguelike — must.)";

    if (body) {
      body.innerHTML = `
        <div class="bco-z-grid">
          <div class="bco-z-choice">
            <div class="ttl">⬆️ Upgrade</div>
            <div class="sub">Апгрейд оружия/урона/скорости. </div>
            <button class="bco-shopbtn primary" type="button" data-act="upgrade">Buy</button>
          </div>
          <div class="bco-z-choice">
            <div class="ttl">🎲 Reroll</div>
            <div class="sub">Переброс апгрейдов/предложений.</div>
            <button class="bco-shopbtn" type="button" data-act="reroll">Roll</button>
          </div>
          <div class="bco-z-choice">
            <div class="ttl">🔄 Reload</div>
            <div class="sub">Мгновенная перезарядка/патроны.</div>
            <button class="bco-shopbtn" type="button" data-act="reload">Reload</button>
          </div>
          <div class="bco-z-choice">
            <div class="ttl">🧪 Jug</div>
            <div class="sub">Больше HP/выживаемость.</div>
            <button class="bco-shopbtn" type="button" data-perk="Jug">Buy</button>
          </div>
          <div class="bco-z-choice">
            <div class="ttl">⚡ Speed</div>
            <div class="sub">Скорость/перезарядка/мувмент.</div>
            <button class="bco-shopbtn" type="button" data-perk="Speed">Buy</button>
          </div>
          <div class="bco-z-choice">
            <div class="ttl">📦 Mag</div>
            <div class="sub">Больше магазина/боезапаса.</div>
            <button class="bco-shopbtn" type="button" data-perk="Mag">Buy</button>
          </div>
          <div class="bco-z-choice">
            <div class="ttl">🛡 Armor</div>
            <div class="sub">Броня/снижение урона.</div>
            <button class="bco-shopbtn" type="button" data-perk="Armor">Buy</button>
          </div>
          <div class="bco-z-choice">
            <div class="ttl">🎮 Mode</div>
            <div class="sub">Arcade / Roguelike</div>
            <div style="display:flex; gap:10px; flex-wrap:wrap; margin-top:10px;">
              <button class="bco-shopbtn" type="button" data-mode="arcade">Arcade</button>
              <button class="bco-shopbtn" type="button" data-mode="roguelike">Roguelike</button>
            </div>
          </div>
        </div>
      `;

      // wire inside modal
      onTap(body, (e) => {
        const b = e?.target?.closest?.(".bco-shopbtn");
        if (!b) return;
        const act = b.getAttribute("data-act");
        const perk = b.getAttribute("data-perk");
        const mode = b.getAttribute("data-mode");

        if (act === "upgrade") zombiesUpgrade();
        if (act === "reroll") zombiesReroll();
        if (act === "reload") zombiesReload();
        if (perk) zombiesBuyPerk(perk);
        if (mode) {
          zombiesSetMode(mode);
          updateOverlayLabels();
          toast(`Mode: ${mode}`);
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
        // keep skin if incompatible? for now keep, engine can clamp
        await saveState();
        toast(`Character: ${c}`);
        try { ZB()?.setPlayerSkin?.(state.character, state.skin); } catch {}
        try { ZB()?.open?.({ map: state.zombies_map, character: state.character, skin: state.skin }); } catch {}
        openCharacterModal(); // refresh UI
      }

      if (s) {
        state.skin = s;
        await saveState();
        toast(`Skin: ${s}`);
        try { ZB()?.setPlayerSkin?.(state.character, state.skin); } catch {}
        try { ZB()?.open?.({ map: state.zombies_map, character: state.character, skin: state.skin }); } catch {}
        openCharacterModal(); // refresh UI
      }

      if (r) {
        state.render = (r === "3d") ? "3d" : "2d";
        await saveState();
        toast(`Render: ${state.render}`);
        // if engine supports toggling renderer — do it, else safe no-op
        try { ZB()?.setRenderMode?.(state.render); } catch {}
        try { ZB()?.renderer?.(state.render); } catch {}
        openCharacterModal(); // refresh UI
      }
    }, { lockMs: 120 });
  }

  function updateOverlayLabels() {
    if (!GAME.overlay) return;
    const sub = GAME.overlay.querySelector("#bcoZSub");
    if (sub) sub.textContent = `${String(state.zombies_mode).toUpperCase()} • ${state.zombies_map}`;

    // show shop bar stronger in roguelike
    if (GAME.shop) GAME.shop.style.opacity = (state.zombies_mode === "roguelike") ? "1" : "0.85";
  }

  function attachEngineToOverlay() {
    const z = zombiesEnsureLoaded();
    if (!z || !GAME.canvas) return;

    // give engine a canvas if it supports
    try { z.setCanvas?.(GAME.canvas); } catch {}
    try { z.canvas?.(GAME.canvas); } catch {}
    try { z.attach?.(GAME.canvas); } catch {}
    try { z.mount?.(GAME.canvas); } catch {}

    // open in engine
    zombiesOpenCore();

    // start input pump for engines that poll BCO_ZOMBIES_INPUT
    startInputPump();
  }

  function enterGame() {
    // build UI
    buildOverlayDOM();
    updateOverlayLabels();

    GAME.active = true;
    GAME.overlay.style.display = "block";

    setAppChromeHidden(true);
    tgFullscreenHints(true);

    // prevent iOS scroll behind
    document.body.style.overflow = "hidden";

    // attach engine + start run
    attachEngineToOverlay();
    zombiesSetMode(state.zombies_mode);
    zombiesStartRun();

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

    // go back to Game tab (launcher)
    selectTab("game");

    haptic("notif", "warning");
    toast("Zombies: Exit");
  }

  // Allow engine -> UI HUD updates if it exposes events
  function hookEngineHud() {
    const z = ZB();
    if (!z) return;

    // common event patterns
    const on = z.on || z.addEventListener;
    if (!on) return;

    try {
      on.call(z, "hud", (hud) => {
        if (!GAME.hudPill || !GAME.hudPill2) return;
        const h = hud || {};
        const hp = (h.hp ?? h.health ?? "—");
        const ammo = (h.ammo ?? "—");
        const coins = (h.coins ?? h.money ?? "—");
        const gun = (h.weapon ?? h.gun ?? "—");
        const wave = (h.wave ?? "—");
        const kills = (h.kills ?? "—");
        GAME.hudPill.textContent = `❤️ ${hp} • 🔫 ${gun} (${ammo}) • 💰 ${coins}`;
        GAME.hudPill2.textContent = `Wave ${wave} • Kills ${kills} • ${String(state.zombies_mode).toUpperCase()}`;
      });
    } catch {}

    try {
      on.call(z, "result", (res) => {
        // auto send to bot (optional) — but keep manual too
        // You asked: results go to bot. We'll keep: engine might call this.
        try {
          sendToBot({
            action: "game_result",
            game: "zombies",
            mode: state.zombies_mode,
            map: state.zombies_map,
            profile: true,
            ...res
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

    // When game is active: hide telegram buttons (less clutter)
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
      if (currentTab === "game") {
        enterGame();
        return;
      }
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

    // delegate taps from root
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
    // close mini app
    onTap(qs("#btnClose"), () => {
      haptic("impact", "medium");
      tg?.close?.();
    });

    // share
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

    // home / bot
    onTap(qs("#btnOpenBot"), () => openBotMenuHint("main"));
    onTap(qs("#btnPremium"), () => openBotMenuHint("premium"));
    onTap(qs("#btnSync"), () => sendToBot({ type: "sync_request", profile: true }));

    // coach / vod / settings (bot-side)
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
      }, { passive: false });
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

    // =========================
    // ZOMBIES: PREVIEW buttons (Home)
    // =========================
    onTap(qs("#btnZModeArcade"), () => {
      zombiesSetMode("arcade");
      toast("Zombies: Arcade 💥");
    });

    onTap(qs("#btnZModeRogue"), () => {
      zombiesSetMode("roguelike");
      toast("Zombies: Roguelike 😈");
    });

    onTap(qs("#btnZQuickPlay"), () => {
      // open fullscreen from home preview
      enterGame();
    });

    onTap(qs("#btnZGameSend"), () => zombiesSendResult("manual"));

    // quick buy hotkeys (still useful)
    onTap(qs("#btnZBuyJug"), () => zombiesBuyPerk("Jug"));
    onTap(qs("#btnZBuySpeed"), () => zombiesBuyPerk("Speed"));
    onTap(qs("#btnZBuyAmmo"), () => zombiesBuyPerk("Mag"));

    // =========================
    // GAME TAB (launcher)
    // =========================
    onTap(qs("#btnPlayZombies"), () => {
      selectTab("game");
      enterGame();
    });

    onTap(qs("#btnZEnterGame"), () => enterGame());
    onTap(qs("#btnZGameSend2"), () => zombiesSendResult("manual"));

    onTap(qs("#btnZModeArcade2"), () => {
      zombiesSetMode("arcade");
      updateOverlayLabels();
      toast("Mode: Arcade 💥");
    });

    onTap(qs("#btnZModeRogue2"), () => {
      zombiesSetMode("roguelike");
      updateOverlayLabels();
      toast("Mode: Roguelike 😈");
    });

    onTap(qs("#btnZOpenHQ"), () => {
      // open the bot-side HQ
      openBotMenuHint("zombies");
    });

    // =========================
    // Zombies HQ buttons (bot)
    // =========================
    onTap(qs("#btnOpenZombies"), () => sendToBot({ type: "zombies_open", map: state.zombies_map, profile: true }));
    onTap(qs("#btnZPerks"), () => sendToBot({ type: "zombies", action: "perks", map: state.zombies_map, profile: true }));
    onTap(qs("#btnZLoadout"), () => sendToBot({ type: "zombies", action: "loadout", map: state.zombies_map, profile: true }));
    onTap(qs("#btnZEggs"), () => sendToBot({ type: "zombies", action: "eggs", map: state.zombies_map, profile: true }));
    onTap(qs("#btnZRound"), () => sendToBot({ type: "zombies", action: "rounds", map: state.zombies_map, profile: true }));
    onTap(qs("#btnZTips"), () => sendToBot({ type: "zombies", action: "tips", map: state.zombies_map, profile: true }));

    // Safety: ESC-like exit for desktop browsers
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && GAME.active) exitGame();
    }, { passive: true });
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

    // NAV
    wireNav();

    // Segments
    wireSeg("#segGame", (v) => { state.game = v; });
    wireSeg("#segFocus", (v) => { state.focus = v; });
    wireSeg("#segMode", (v) => { state.mode = v; });
    wireSeg("#segPlatform", (v) => { state.platform = v; });
    wireSeg("#segInput", (v) => { state.input = v; });
    wireSeg("#segVoice", (v) => { state.voice = v; });

    // Zombies map segment exists both in home tab and game tab — same id (#segZMap)
    wireSeg("#segZMap", (v) => {
      state.zombies_map = v;
      updateOverlayLabels();
    });

    // Set UI
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

    // Engine hooks (if loaded)
    hookEngineHud();

    // start at home
    selectTab("home");

    // If someone opens /webapp/#game or deep link in future
    // (non-breaking)
    try {
      const hash = String(location.hash || "").replace("#", "").trim();
      if (hash) selectTab(hash);
    } catch {}

    updateTelegramButtons();
  }

  boot();
})();
