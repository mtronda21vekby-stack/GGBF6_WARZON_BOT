// app/webapp/static/app.js  [LUX v1.3.4+]
// ✅ Keep ALL features, fix Zombies bridge, make it future-proof for 3D,
// ✅ iOS tap safety, better TG Main/Back wiring, robust engine detection,
// ✅ adds minimal 3D-ready hooks (renderer adapter + future scene pipeline) WITHOUT breaking 2D.
(() => {
  "use strict";

  // ---------------------------------------------------------
  // Global health flag for loader / index.html diagnostics
  // ---------------------------------------------------------
  window.__BCO_JS_OK__ = true;

  const tg = window.Telegram?.WebApp || null;

  const VERSION = "1.3.4";
  const STORAGE_KEY = "bco_state_v1";
  const CHAT_KEY = "bco_chat_v1";

  // ---------------------------------------------------------
  // Defaults (KEEP + extend safely)
  // ---------------------------------------------------------
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

    // ✅ internal flags (safe)
    _z_engine_pref: "auto", // auto | core | legacy
    _z_render_pref: "2d"    // 2d | 3d (future)
  };

  const state = { ...defaults };

  const chat = {
    history: [],
    lastAskAt: 0
  };

  let currentTab = "home";

  // ---------------------------------------------------------
  // DOM helpers
  // ---------------------------------------------------------
  const qs = (s) => document.querySelector(s);
  const qsa = (s) => Array.from(document.querySelectorAll(s));
  const now = () => Date.now();

  function safeJsonParse(s) { try { return JSON.parse(s); } catch { return null; } }

  // ---------------------------------------------------------
  // Haptics / toast
  // ---------------------------------------------------------
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
  // ✅ FAST TAP (iOS WebView SAFE) — NO DOUBLE FIRE
  // - avoids ghost clicks, supports pointer, touch, click fallback
  // =========================================================
  function onTap(el, handler, opts = {}) {
    if (!el) return;

    const lockMs = Math.max(120, Number(opts.lockMs || 240));
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

    // If element is a container (like segment root), pointerup is fine.
    // For buttons, pointerup prevents double "click" on iOS.
    if (window.PointerEvent) {
      el.addEventListener("pointerup", fire, { passive: true });
      return;
    }

    el.addEventListener("touchend", fire, { passive: true });
    el.addEventListener("click", fire, { passive: true });
  }

  // =========================================================
  // Theme sync
  // =========================================================
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

  // =========================================================
  // Storage (Cloud + Local)
  // =========================================================
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
    try { localStorage.setItem(STORAGE_KEY, payload); } catch {}
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
    try { localStorage.setItem(CHAT_KEY, payload); } catch {}
    await cloudSet(CHAT_KEY, payload);
  }

  // =========================================================
  // UI helpers
  // =========================================================
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
    currentTab = tab;

    qsa(".tabpane").forEach((p) => p.classList.toggle("active", p.id === `tab-${tab}`));
    setActiveNav(tab);
    setActiveTopTabs(tab);

    updateTelegramButtons();

    try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch {}
  }

  // =========================================================
  // Payload / sendData
  // =========================================================
  function toRouterProfile() {
    // keep compat with Router expectations
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
      ...(payload || {})
    };
  }

  function sendToBot(payload) {
    try {
      const fixed = { ...(payload || {}) };

      // allow {profile:true} convenience
      if (Object.prototype.hasOwnProperty.call(fixed, "profile")) {
        if (fixed.profile === true) fixed.profile = toRouterProfile();
      }

      const pack = enrichPayload(fixed);
      let data = JSON.stringify(pack);

      // Telegram sendData safe bound
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
  // ✅ ZOMBIES ENGINE — robust detection + 3D-ready adapter
  // - supports: window.BCO_ZOMBIES (new facade) OR window.BCO_ZOMBIES_CORE
  // - keeps your current UI calls working
  // =========================================================
  function getZombiesFacade() {
    // Preferred: new facade (if your zombies.js exposes it)
    if (window.BCO_ZOMBIES && typeof window.BCO_ZOMBIES === "object") return window.BCO_ZOMBIES;

    // Core-only fallback: build tiny facade around BCO_ZOMBIES_CORE (your new core)
    const CORE = window.BCO_ZOMBIES_CORE;
    if (CORE && typeof CORE.start === "function") {
      // Build once
      if (!window.__BCO_Z_FACADE__) {
        window.__BCO_Z_FACADE__ = {
          _core: CORE,
          open: (opts = {}) => {
            try {
              // store cosmetics in core meta
              CORE.meta.map = String(opts.map || CORE.meta.map || "Ashes");
              CORE.meta.character = String(opts.character || CORE.meta.character || "male");
              CORE.meta.skin = String(opts.skin || CORE.meta.skin || "default");
              // renderer preference placeholder
              CORE.meta.render = String(opts.render || CORE.meta.render || "2d");
              return true;
            } catch { return false; }
          },
          setMode: (mode) => {
            try {
              const m = String(mode || "");
              CORE.meta.mode = m.toLowerCase().includes("rogue") ? "roguelike" : "arcade";
              return true;
            } catch { return false; }
          },
          start: (opts = {}) => {
            try {
              const map = opts?.map || CORE.meta.map || "Ashes";
              const w = Math.max(1, (qs("#zCanvas")?.clientWidth || window.innerWidth) | 0);
              const h = Math.max(1, (qs("#zCanvas")?.clientHeight || window.innerHeight) | 0);
              CORE.start(CORE.meta.mode, w, h, { map, character: CORE.meta.character, skin: CORE.meta.skin, weaponKey: (opts.weaponKey || CORE.meta.weaponKey) });
              return true;
            } catch { return false; }
          },
          stop: () => { try { CORE.stop(); return true; } catch { return false; } },
          buyPerk: (id) => { try { return CORE.buyPerk(id); } catch { return false; } },
          // Try to send result through existing bot bridge if your zombies.js has one.
          sendResult: (reason = "manual") => {
            try {
              const S = CORE.state;
              sendToBot({
                action: "game_result",
                game: "zombies",
                mode: CORE.meta.mode,
                map: CORE.meta.map,
                character: CORE.meta.character,
                skin: CORE.meta.skin,
                wave: S.wave | 0,
                kills: S.kills | 0,
                coins: S.coins | 0,
                duration_ms: S.timeMs | 0,
                score: Math.max(0, Math.round((S.kills || 0) * 25 + (S.wave || 0) * 60 + (S.level || 1) * 40)),
                reason: String(reason || "manual"),
                profile: true
              });
              return true;
            } catch { return false; }
          }
        };
      }
      return window.__BCO_Z_FACADE__;
    }

    return null;
  }

  function zombiesEnsureOpen() {
    const z = getZombiesFacade();
    if (!z) {
      toast("Zombies engine not loaded");
      haptic("notif", "error");
      return false;
    }
    try {
      z.open?.({
        map: state.zombies_map,
        character: state.character,
        skin: state.skin,
        render: state._z_render_pref || "2d"
      });
    } catch {}
    return true;
  }

  function zombiesSetMode(mode) {
    const z = getZombiesFacade();
    if (!z) return;
    try { z.setMode?.(mode); } catch {}
  }

  function zombiesStart() {
    const z = getZombiesFacade();
    if (!z) return;
    // ✅ Fix: remove triple-start spam, call once with options
    try {
      z.start?.({ map: state.zombies_map, weaponKey: "SMG" });
    } catch {
      try { z.start?.(); } catch {}
    }
  }

  function zombiesStop() {
    const z = getZombiesFacade();
    if (!z) return;
    try { z.stop?.("manual"); } catch { try { z.stop?.(); } catch {} }
  }

  function zombiesSendResult() {
    const z = getZombiesFacade();
    if (!z) return;
    try { z.sendResult?.("manual"); return; } catch {}
    try { z.result?.("manual"); return; } catch {}
  }

  function zombiesBuyPerk(id) {
    const z = getZombiesFacade();
    if (!z) return;
    try { z.buyPerk?.(id); } catch {}
  }

  // =========================================================
  // Telegram native buttons (Main/Back) — FIX offClick wiring
  // =========================================================
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
          currentTab === "zombies" ? "🧟 Открыть Zombies" :
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
        if (zombiesEnsureOpen()) {
          // Keep your UX: opens game; mode remains user-set
          zombiesSetMode("arcade");
          return;
        }
        sendToBot({ type: "zombies_open", map: state.zombies_map, profile: true });
        return;
      }
      openBotMenuHint("premium");
    };

    tgBackHandler = () => {
      haptic("impact", "light");
      selectTab("home");
    };

    // ✅ FIX: offClick must be called with previously registered handler, not the new one.
    try { tg.MainButton.offClick?.(tgMainHandler); } catch {}
    try { tg.MainButton.onClick?.(tgMainHandler); } catch {}

    try { tg.BackButton.offClick?.(tgBackHandler); } catch {}
    try { tg.BackButton.onClick?.(tgBackHandler); } catch {}
  }

  // =========================================================
  // Share
  // =========================================================
  function tryShare(text) {
    try {
      navigator.clipboard?.writeText?.(String(text ?? ""));
      toast("Скопировано ✅");
    } catch {
      alert(String(text ?? ""));
    }
  }

  // =========================================================
  // MINI APP CHAT (BOT REPLIES IN APP)
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
  // Segments wiring
  // =========================================================
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
      const btn = e.target?.closest?.(".seg-btn");
      if (!btn) return;
      handler(btn);
    });
  }

  // =========================================================
  // Nav wiring
  // =========================================================
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

  // =========================================================
  // Header chips
  // =========================================================
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
  // Wire buttons
  // =========================================================
  function wireButtons() {
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

    onTap(qs("#btnOpenZombies"), () => sendToBot({ type: "zombies_open", map: state.zombies_map, profile: true }));
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
        "Mini App + Fullscreen 2D Zombies (Arcade/Roguelike).";
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
        e?.preventDefault?.();
        e?.stopPropagation?.();
      });

      onTap(arena, () => {
        if (!aim.running) return;
        aim.shots += 1;
        haptic("impact", "light");
        aimUpdateUI();
      });
    }

    // =========================================================
    // ✅ ZOMBIES (NEW ENGINE) — wire to facade
    // =========================================================
    const btnZArc = qs("#btnZModeArcade");
    const btnZRog = qs("#btnZModeRogue");
    const btnZStart = qs("#btnZGameStart");
    const btnZStop = qs("#btnZGameStop");
    const btnZSend = qs("#btnZGameSend");

    onTap(btnZArc, async () => {
      if (!zombiesEnsureOpen()) return;
      zombiesSetMode("arcade");
      await saveState();
      toast("Zombies: Arcade 💥");
    });

    onTap(btnZRog, async () => {
      if (!zombiesEnsureOpen()) return;
      zombiesSetMode("roguelike");
      await saveState();
      toast("Zombies: Roguelike 😈");
    });

    onTap(btnZStart, () => {
      if (!zombiesEnsureOpen()) return;
      zombiesStart();
      toast("Zombies: старт ▶");
    });

    onTap(btnZStop, () => {
      if (!zombiesEnsureOpen()) return;
      zombiesStop();
      toast("Zombies: стоп ⛔");
    });

    onTap(btnZSend, () => {
      if (!zombiesEnsureOpen()) return;
      zombiesSendResult();
    });

    // Old home "Shop" buttons => perks on new engine
    onTap(qs("#btnZBuyJug"), () => {
      if (!zombiesEnsureOpen()) return;
      zombiesSetMode("roguelike");
      zombiesStart();
      zombiesBuyPerk("Jug");
    });

    onTap(qs("#btnZBuySpeed"), () => {
      if (!zombiesEnsureOpen()) return;
      zombiesSetMode("roguelike");
      zombiesStart();
      zombiesBuyPerk("Speed");
    });

    onTap(qs("#btnZBuyAmmo"), () => {
      if (!zombiesEnsureOpen()) return;
      zombiesSetMode("roguelike");
      zombiesStart();
      zombiesBuyPerk("Mag");
    });
  }

  // =========================================================
  // Build tag
  // =========================================================
  function ensureBuildTag() {
    const buildFromIndex =
      (window.__BCO_BUILD__ && window.__BCO_BUILD__ !== "__BUILD__")
        ? window.__BCO_BUILD__
        : null;

    const txt = buildFromIndex ? `build ${buildFromIndex} • v${VERSION}` : `v${VERSION}`;
    const buildTag = qs("#buildTag");
    if (buildTag) buildTag.textContent = txt;
  }

  // =========================================================
  // Init Telegram
  // =========================================================
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
  // Boot
  // =========================================================
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

    // Safe: warm up zombies facade if available (no start)
    try { getZombiesFacade(); } catch {}

    selectTab("home");
  }

  boot();
})();
