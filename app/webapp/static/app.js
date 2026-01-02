// app/webapp/static/app.js
(() => {
  window.__BCO_JS_OK__ = true;

  const tg = window.Telegram?.WebApp;

  const VERSION = "1.3.2";
  const STORAGE_KEY = "bco_state_v1";
  const CHAT_KEY = "bco_chat_v1";

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
    skin: "default"    // depends on character
  };

  const state = { ...defaults };

  const chat = {
    history: [],
    lastAskAt: 0
  };

  let currentTab = "home";

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
    t.textContent = text;
    t.classList.add("show");
    setTimeout(() => t.classList.remove("show"), 1600);
  }

  // =========================================================
  // ✅ FAST TAP (iOS WebView SAFE)
  // =========================================================
  function onTap(el, handler) {
    if (!el) return;

    let locked = false;
    const lock = () => {
      locked = true;
      setTimeout(() => (locked = false), 260);
    };

    const fire = (e) => {
      if (locked) return;
      lock();
      try { handler(e); } catch {}
    };

    // PointerEvent exists on iOS modern; keep both pointerup and click,
    // but guard with lock (prevents double-fire).
    if (window.PointerEvent) {
      el.addEventListener("pointerup", fire, { passive: true });
      el.addEventListener("click", fire, { passive: true });
      return;
    }
    el.addEventListener("touchend", fire, { passive: true });
    el.addEventListener("click", fire, { passive: true });
  }

  // ---------- Theme sync ----------
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

  // ---------- Storage ----------
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

  // ---------- UI helpers ----------
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

  // ---------- Payload / sendData ----------
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

  // ✅ safer truncation: never slice JSON mid-string
  function packWithinLimit(pack, maxLen = 15000) {
    const tryStringify = (obj) => {
      try { return JSON.stringify(obj); } catch { return ""; }
    };

    let s = tryStringify(pack);
    if (s.length <= maxLen) return { ok: true, json: s, pack };

    // shrink common big fields first
    const clone = JSON.parse(JSON.stringify(pack || {}));
    const shrinkField = (path, limit) => {
      try {
        let ref = clone;
        for (let i = 0; i < path.length - 1; i++) ref = ref?.[path[i]];
        const k = path[path.length - 1];
        if (typeof ref?.[k] === "string") ref[k] = ref[k].slice(0, limit);
      } catch {}
    };

    shrinkField(["text"], 2500);
    shrinkField(["note"], 2500);
    shrinkField(["meta", "note"], 2000);

    // history can be big in some payloads
    if (Array.isArray(clone.history)) clone.history = clone.history.slice(-10);

    s = tryStringify(clone);
    if (s.length <= maxLen) return { ok: true, json: s, pack: clone };

    // last resort: drop non-critical
    if (clone.meta) {
      clone.meta = { ...clone.meta, dropped: true };
    }
    delete clone.history;
    delete clone.note;
    delete clone.text;

    s = tryStringify(clone);
    if (s.length <= maxLen) return { ok: true, json: s, pack: clone };

    // absolute last: minimal ping
    const min = { v: VERSION, t: now(), type: "ping" };
    return { ok: false, json: tryStringify(min), pack: min };
  }

  function sendToBot(payload) {
    try {
      const fixed = { ...(payload || {}) };

      // ✅ FIX: profile handling
      if (Object.prototype.hasOwnProperty.call(fixed, "profile")) {
        if (fixed.profile === true) fixed.profile = toRouterProfile();
      }

      const pack = enrichPayload(fixed);
      const bounded = packWithinLimit(pack, 15000);

      if (!tg?.sendData) {
        haptic("notif", "error");
        toast("Открой Mini App внутри Telegram");
        return;
      }

      tg.sendData(bounded.json);
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
    // ✅ router ждёт type="nav"
    sendToBot({ type: "nav", target, profile: true });
  }

  // ---------- Telegram native buttons ----------
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

    // Wire once, but keep stable references
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
        sendToBot({ type: "zombies_open", map: state.zombies_map, profile: true });
        return;
      }
      openBotMenuHint("premium");
    };

    tgBackHandler = () => {
      haptic("impact", "light");
      selectTab("home");
    };

    // ensure no duplicates
    try { tg.MainButton.offClick?.(tgMainHandler); } catch {}
    try { tg.BackButton.offClick?.(tgBackHandler); } catch {}

    try { tg.MainButton.onClick?.(tgMainHandler); } catch {}
    try { tg.BackButton.onClick?.(tgBackHandler); } catch {}
  }

  // ---------- Share ----------
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

  // ---------- Segments wiring ----------
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

    if (window.PointerEvent) {
      root.addEventListener("pointerup", (e) => {
        const btn = e.target.closest(".seg-btn");
        if (!btn) return;
        handler(btn);
      }, { passive: true });
      root.addEventListener("click", (e) => {
        const btn = e.target.closest(".seg-btn");
        if (!btn) return;
        handler(btn);
      }, { passive: true });
    } else {
      root.addEventListener("click", (e) => {
        const btn = e.target.closest(".seg-btn");
        if (!btn) return;
        handler(btn);
      }, { passive: true });
    }
  }

  // ---------- Nav wiring ----------
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

  // ---------- Header chips ----------
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
  // 🎯 GAME #1: AIM TRIAL
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
  // 🧟 GAME #2: ZOMBIES SURVIVAL — FULLSCREEN 2D CANVAS
  // =========================================================
  const Z = (() => {
    const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
    const dist2 = (ax, ay, bx, by) => {
      const dx = ax - bx, dy = ay - by;
      return dx * dx + dy * dy;
    };

    const SKINS = {
      male: [
        { id: "default", name: "Rookie", colors: ["#9ca3af", "#111827"] },
        { id: "shadow",  name: "Shadow", colors: ["#111827", "#000000"] },
        { id: "neon",    name: "Neon",   colors: ["#22d3ee", "#0a0a12"] },
        { id: "royal",   name: "Royal",  colors: ["#8b5cf6", "#0b1020"] }
      ],
      female: [
        { id: "default", name: "Valkyrie", colors: ["#e5e7eb", "#111827"] },
        { id: "ember",   name: "Ember",    colors: ["#fb7185", "#0a0a12"] },
        { id: "aqua",    name: "Aqua",     colors: ["#22d3ee", "#0b1020"] },
        { id: "royal",   name: "Royal",    colors: ["#8b5cf6", "#0b1020"] }
      ]
    };

    const WEAPONS = {
      Pistol:  { type: "pistol",  dmg: 18,  rpm: 320, speed: 880, spread: 0.06, mag: 12, reload: 1.25, pierce: 0, crit: 1.7 },
      SMG:     { type: "smg",     dmg: 13,  rpm: 720, speed: 980, spread: 0.09, mag: 30, reload: 1.35, pierce: 0, crit: 1.6 },
      AR:      { type: "ar",      dmg: 17,  rpm: 600, speed: 1050,spread: 0.07, mag: 30, reload: 1.55, pierce: 0, crit: 1.75 },
      Shotgun: { type: "shotgun", dmg: 8,   rpm: 110, speed: 920, spread: 0.25, mag: 6,  reload: 1.9,  pierce: 0, crit: 1.5, pellets: 8 },
      LMG:     { type: "lmg",     dmg: 16,  rpm: 520, speed: 980, spread: 0.10, mag: 60, reload: 2.15, pierce: 0, crit: 1.6 },
      Sniper:  { type: "sniper",  dmg: 70,  rpm: 70,  speed: 1400,spread: 0.02, mag: 5,  reload: 2.0,  pierce: 1, crit: 2.2 },
      Burst:   { type: "burst",   dmg: 15,  rpm: 780, speed: 1050,spread: 0.08, mag: 24, reload: 1.55, pierce: 0, crit: 1.75, burst: 3 },
      Launcher:{ type: "launcher",dmg: 55,  rpm: 55,  speed: 680, spread: 0.02, mag: 2,  reload: 2.4,  pierce: 0, crit: 1.0, splash: 90 }
    };

    const PERKS = [
      { id: "Jug",       name: "🧪 Jug",        desc: "+Max HP",         cost: 18, apply: (run) => { run.maxHp += 40; run.hp = Math.min(run.hp + 30, run.maxHp); } },
      { id: "Speed",     name: "⚡ Speed",      desc: "+Reload +RPM",    cost: 16, apply: (run) => { run.reloadMul *= 0.82; run.rpmMul *= 1.10; } },
      { id: "StaminUp",  name: "🏃 Stamin-Up",  desc: "+Move speed",     cost: 14, apply: (run) => { run.moveMul *= 1.16; } },
      { id: "DoubleTap", name: "🔥 Double Tap", desc: "+Damage",         cost: 18, apply: (run) => { run.dmgMul *= 1.16; } },
      { id: "Deadshot",  name: "🎯 Deadshot",   desc: "+Crit chance",    cost: 16, apply: (run) => { run.critChance = Math.min(0.35, run.critChance + 0.08); } },
      // ✅ perk "Armor" оставили, но теперь броня "настоящая" — через plates.
      { id: "Armor",     name: "🛡 Armor+",     desc: "+Armor points",   cost: 14, apply: (run) => { run.armor = Math.min(run.armor + 35, run.armorMax); run._syncPlates(); } },
      { id: "Mag",       name: "📦 Mag+",       desc: "+Mag size",       cost: 15, apply: (run) => { run.magMul *= 1.18; } },
      { id: "Pierce",    name: "🗡 Pierce",     desc: "Bullets pierce",  cost: 20, apply: (run) => { run.pierceBonus += 1; } },
      { id: "Lucky",     name: "🍀 Lucky",      desc: "+Coins per kill", cost: 15, apply: (run) => { run.coinMul *= 1.15; } }
    ];

    let overlay = null;
    let canvas = null;
    let ctx = null;
    let raf = 0;
    let lastT = 0;

    const ui = {
      modeArcade: null,
      modeRogue: null,
      btnStart: null,
      btnClose: null,
      btnShop: null,
      btnShoot: null,
      btnReload: null,
      btnSend: null,
      hud: null,
      toast: null
    };

    const input = {
      joyActive: false,
      joyId: null,
      joyCx: 0, joyCy: 0,
      joyX: 0, joyY: 0,
      shootHeld: false,
      aimX: 0, aimY: 0
    };

    const run = {
      running: false,
      mode: "arcade",
      startedAt: 0,
      endedAt: 0,

      wave: 1,
      kills: 0,
      coins: 0,

      x: 0, y: 0,
      r: 14,
      hp: 100,
      maxHp: 100,

      // ✅ REAL ARMOR (plates)
      armor: 0,           // armor points
      armorMax: 150,      // 3 plates * 50
      plates: 0,          // number of plates equipped
      platesMax: 3,
      plateValue: 50,
      plateCostBase: 10,  // base cost; grows with wave a bit

      perks: [],
      dmgMul: 1,
      rpmMul: 1,
      moveMul: 1,
      reloadMul: 1,
      magMul: 1,
      pierceBonus: 0,
      critChance: 0.10,
      coinMul: 1,

      weaponName: "SMG",
      ammo: 0,
      mag: 0,
      reloading: false,
      reloadAt: 0,
      lastShotAt: 0,

      zombies: [],
      bullets: [],
      particles: [],

      spawnAt: 0,
      waveEndsAt: 0,

      w: 0,
      h: 0,
      dpr: 1,

      _syncPlates() {
        const p = Math.ceil((run.armor || 0) / run.plateValue);
        run.plates = clamp(p, 0, run.platesMax);
        run.armor = clamp(run.armor, 0, run.armorMax);
      }
    };

    // ✅ FIX: event cleanup (no leaks)
    const listeners = [];
    const addL = (target, type, fn, opts) => {
      try {
        target.addEventListener(type, fn, opts);
        listeners.push([target, type, fn, opts]);
      } catch {}
    };
    const removeAllL = () => {
      for (const [target, type, fn, opts] of listeners.splice(0)) {
        try { target.removeEventListener(type, fn, opts); } catch {}
      }
    };

    let prevOverflow = "";
    let prevTouchAction = "";
    function lockBody(on) {
      try {
        const root = document.documentElement;
        const body = document.body;
        if (on) {
          prevOverflow = body.style.overflow || "";
          prevTouchAction = root.style.touchAction || "";
          body.style.overflow = "hidden";
          root.style.touchAction = "none";
        } else {
          body.style.overflow = prevOverflow;
          root.style.touchAction = prevTouchAction;
        }
      } catch {}
    }

    function zToast(t) {
      if (ui.toast) {
        ui.toast.textContent = t;
        ui.toast.style.opacity = "1";
        clearTimeout(ui.toast._t);
        ui.toast._t = setTimeout(() => { ui.toast.style.opacity = "0"; }, 1100);
      } else {
        toast(t);
      }
    }

    function injectStyleOnce() {
      if (qs("#bco-zstyle")) return;
      const st = document.createElement("style");
      st.id = "bco-zstyle";
      st.textContent = `
        .bcoz-ov{
          position:fixed; inset:0; z-index:9999;
          background: radial-gradient(1200px 800px at 20% 0%, rgba(139,92,246,.25), transparent 60%),
                      radial-gradient(900px 700px at 90% 30%, rgba(34,211,238,.18), transparent 55%),
                      linear-gradient(180deg, #07070b, #0a0a12);
          color: rgba(255,255,255,.92);
          font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
          overflow:hidden;
          touch-action:none;
        }
        .bcoz-top{
          position:absolute; left:0; right:0; top:0;
          padding: calc(12px + env(safe-area-inset-top,0px)) 12px 10px 12px;
          display:flex; align-items:center; justify-content:space-between; gap:10px;
          background: rgba(7,7,11,.55);
          backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
          border-bottom: 1px solid rgba(255,255,255,.08);
        }
        .bcoz-title{ font-weight: 1000; letter-spacing:.2px; font-size: 13px; }
        .bcoz-sub{ font-weight: 800; font-size: 11px; opacity:.7; margin-top:2px; }
        .bcoz-left{ display:flex; align-items:center; gap:10px; }
        .bcoz-badge{
          width:36px; height:36px; border-radius: 14px;
          display:grid; place-items:center;
          background: linear-gradient(135deg, rgba(139,92,246,.35), rgba(34,211,238,.20));
          border: 1px solid rgba(255,255,255,.12);
        }
        .bcoz-btn{
          border-radius: 14px;
          border: 1px solid rgba(255,255,255,.12);
          background: rgba(255,255,255,.06);
          color: rgba(255,255,255,.92);
          padding: 10px 10px;
          font-weight: 950;
          font-size: 12px;
          -webkit-tap-highlight-color: transparent;
          user-select:none;
        }
        .bcoz-btn.primary{
          border-color: rgba(139,92,246,.45);
          background: linear-gradient(135deg, rgba(139,92,246,.35), rgba(34,211,238,.18));
        }
        .bcoz-btn.small{ padding: 8px 10px; border-radius: 999px; font-size: 11px; }
        .bcoz-modes{ display:flex; gap:8px; flex-wrap:wrap; }
        .bcoz-seg{
          border-radius: 999px; padding: 8px 10px;
          border: 1px solid rgba(255,255,255,.12);
          background: rgba(255,255,255,.05);
          font-weight: 950; font-size: 11px;
          -webkit-tap-highlight-color: transparent;
        }
        .bcoz-seg.active{
          border-color: rgba(139,92,246,.45);
          background: linear-gradient(135deg, rgba(139,92,246,.25), rgba(34,211,238,.12));
        }
        .bcoz-hud{
          position:absolute; left:12px; right:12px;
          top: calc(62px + env(safe-area-inset-top,0px));
          display:flex; align-items:center; justify-content:space-between; gap:10px;
          font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
          font-size: 12px; font-weight: 900;
          padding: 10px 12px;
          border-radius: 16px;
          background: rgba(0,0,0,.28);
          border: 1px solid rgba(255,255,255,.10);
          backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
        }
        .bcoz-canvas{ position:absolute; inset:0; width:100%; height:100%; }
        .bcoz-joybase{
          position:absolute;
          left: 18px;
          bottom: calc(18px + env(safe-area-inset-bottom,0px));
          width: 120px; height: 120px;
          border-radius: 999px;
          background: rgba(255,255,255,.06);
          border: 1px solid rgba(255,255,255,.10);
          backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
        }
        .bcoz-joystick{
          position:absolute;
          left: 18px;
          bottom: calc(18px + env(safe-area-inset-bottom,0px));
          width: 120px; height: 120px;
          border-radius: 999px;
          pointer-events:none;
        }
        .bcoz-joyknob{
          position:absolute;
          width: 54px; height: 54px;
          left: 33px; top: 33px;
          border-radius: 999px;
          background: linear-gradient(135deg, rgba(139,92,246,.40), rgba(34,211,238,.18));
          border: 1px solid rgba(255,255,255,.14);
          box-shadow: 0 14px 35px rgba(0,0,0,.35);
        }
        .bcoz-right{
          position:absolute;
          right: 18px;
          bottom: calc(18px + env(safe-area-inset-bottom,0px));
          display:flex; flex-direction:column; gap:10px;
          align-items:flex-end;
        }
        .bcoz-shoot{
          width: 90px; height: 90px;
          border-radius: 999px;
          display:grid; place-items:center;
          border: 1px solid rgba(139,92,246,.45);
          background: linear-gradient(135deg, rgba(139,92,246,.40), rgba(34,211,238,.18));
          color: rgba(255,255,255,.95);
          font-weight: 1000;
          -webkit-tap-highlight-color: transparent;
          user-select:none;
        }
        .bcoz-minirow{ display:flex; gap:10px; }
        .bcoz-mini{
          border-radius: 16px;
          border: 1px solid rgba(255,255,255,.12);
          background: rgba(255,255,255,.06);
          color: rgba(255,255,255,.92);
          padding: 10px 12px;
          font-weight: 1000;
          font-size: 12px;
          -webkit-tap-highlight-color: transparent;
          user-select:none;
        }
        .bcoz-toast{
          position:absolute; left:50%;
          bottom: calc(126px + env(safe-area-inset-bottom,0px));
          transform: translateX(-50%);
          padding: 10px 12px;
          border-radius: 999px;
          background: rgba(0,0,0,.55);
          border: 1px solid rgba(255,255,255,.10);
          font-weight: 1000;
          opacity:0;
          transition: opacity .15s ease;
          pointer-events:none;
        }
        .bcoz-shop{
          position:absolute; inset:0;
          background: rgba(0,0,0,.55);
          backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
          display:none;
          padding: calc(14px + env(safe-area-inset-top,0px)) 14px calc(14px + env(safe-area-inset-bottom,0px)) 14px;
        }
        .bcoz-shop.show{ display:block; }
        .bcoz-panel{
          max-width: 740px;
          margin: 0 auto;
          border-radius: 18px;
          background: rgba(255,255,255,.06);
          border: 1px solid rgba(255,255,255,.12);
          box-shadow: 0 18px 55px rgba(0,0,0,.55);
          padding: 14px;
        }
        .bcoz-row{ display:flex; gap:10px; flex-wrap:wrap; align-items:center; justify-content:space-between; }
        .bcoz-grid{ display:grid; gap:10px; margin-top:12px; }
        .bcoz-item{
          border-radius: 16px;
          border: 1px solid rgba(255,255,255,.12);
          background: rgba(0,0,0,.18);
          padding: 12px;
          display:flex;
          align-items:flex-start;
          justify-content:space-between;
          gap:10px;
        }
        .bcoz-item .name{ font-weight: 1000; font-size: 13px; }
        .bcoz-item .desc{ opacity:.72; font-weight: 800; font-size: 12px; margin-top:4px; line-height:1.25; }
        .bcoz-item .cost{ font-weight: 1000; opacity:.9; }
        .bcoz-item .owned{ opacity:.6; font-weight: 1000; }
        .bcoz-hr{ height:1px; background: rgba(255,255,255,.10); margin: 12px 0; }
        .bcoz-char{
          position:absolute; inset:0;
          background: rgba(0,0,0,.50);
          backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
          display:none;
          padding: calc(14px + env(safe-area-inset-top,0px)) 14px calc(14px + env(safe-area-inset-bottom,0px)) 14px;
        }
        .bcoz-char.show{ display:block; }
        .bcoz-cards{ display:grid; gap:10px; grid-template-columns: 1fr 1fr; }
        @media (max-width: 520px){ .bcoz-cards{ grid-template-columns: 1fr; } }
        .bcoz-card{
          border-radius: 18px;
          border: 1px solid rgba(255,255,255,.12);
          background: rgba(255,255,255,.06);
          padding: 12px;
        }
        .bcoz-card .ttl{ font-weight: 1000; font-size: 13px; }
        .bcoz-chiprow{ display:flex; gap:8px; flex-wrap:wrap; margin-top:10px; }
        .bcoz-chip{
          border-radius: 999px;
          border: 1px solid rgba(255,255,255,.12);
          background: rgba(0,0,0,.18);
          padding: 8px 10px;
          font-weight: 1000; font-size: 11px;
          -webkit-tap-highlight-color: transparent;
        }
        .bcoz-chip.active{
          border-color: rgba(139,92,246,.45);
          background: linear-gradient(135deg, rgba(139,92,246,.25), rgba(34,211,238,.12));
        }
      `;
      document.head.appendChild(st);
    }

    function ensureSkinValid() {
      const arr = SKINS[state.character] || [];
      if (!arr.find(s => s.id === state.skin)) state.skin = (arr[0]?.id || "default");
    }

    function syncAssetsIfAny() {
      // Optional: if you подключишь zombies.assets.js, синхронизируем выбор скина безопасно.
      try {
        const A = window.BCO_ZOMBIES_ASSETS;
        if (!A) return;
        // API is optional; call only if functions exist.
        if (typeof A.setPlayerSkin === "function") A.setPlayerSkin(state.character, state.skin);
      } catch {}
    }

    function getSkin() {
      ensureSkinValid();
      syncAssetsIfAny();
      const arr = SKINS[state.character] || [];
      return arr.find(s => s.id === state.skin) || arr[0] || { id: "default", colors: ["#9ca3af", "#111827"] };
    }

    function resize() {
      if (!canvas) return;
      const dpr = Math.max(1, Math.min(2.2, window.devicePixelRatio || 1));
      run.dpr = dpr;

      const w = window.innerWidth;
      const h = window.innerHeight;
      run.w = w; run.h = h;

      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      canvas.style.width = w + "px";
      canvas.style.height = h + "px";

      if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function setMode(m) {
      run.mode = m;
      if (ui.modeArcade) ui.modeArcade.classList.toggle("active", m === "arcade");
      if (ui.modeRogue) ui.modeRogue.classList.toggle("active", m === "roguelike");

      const sub = qs("#bcozSub");
      if (sub) sub.textContent = (m === "roguelike")
        ? "ROGUELIKE • Shop • Permadeath"
        : "ARCADE • Endless waves";

      zToast(m === "roguelike" ? "Режим: Roguelike 😈" : "Режим: Arcade 💥");
      haptic("impact", "light");
      updateHud();
      renderPlateShop();
    }

    function baseWeapon() {
      const w = WEAPONS[run.weaponName] || WEAPONS.SMG;
      const mag = Math.max(1, Math.floor(w.mag * run.magMul));
      return { ...w, mag };
    }

    function resetRun(hard = true) {
      const centerX = run.w * 0.5;
      const centerY = run.h * 0.55;

      run.running = false;
      run.startedAt = 0;
      run.endedAt = 0;

      run.wave = 1;
      run.kills = 0;
      run.coins = 0;

      run.r = 14;
      run.x = centerX;
      run.y = centerY;

      run.maxHp = 100;
      run.hp = 100;

      // ✅ plates reset
      run.armor = 0;
      run.plates = 0;
      run._syncPlates();

      run.perks = [];
      run.dmgMul = 1;
      run.rpmMul = 1;
      run.moveMul = 1;
      run.reloadMul = 1;
      run.magMul = 1;
      run.pierceBonus = 0;
      run.critChance = 0.10;
      run.coinMul = 1;

      run.weaponName = "SMG";
      run.reloading = false;
      run.reloadAt = 0;
      run.lastShotAt = 0;

      run.zombies = [];
      run.bullets = [];
      run.particles = [];

      run.spawnAt = now() + 700;
      run.waveEndsAt = now() + 16000;

      const w = baseWeapon();
      run.mag = w.mag;
      run.ammo = w.mag;

      if (!hard) return;
      input.joyActive = false;
      input.joyX = 0; input.joyY = 0;
      input.shootHeld = false;

      // Default aim: forward
      input.aimX = centerX + 80;
      input.aimY = centerY;
    }

    function addParticle(x, y, c = "rgba(255,255,255,.8)", n = 10) {
      for (let i = 0; i < n; i++) {
        run.particles.push({
          x, y,
          vx: (Math.random() * 2 - 1) * 220,
          vy: (Math.random() * 2 - 1) * 220,
          life: 0.25 + Math.random() * 0.25,
          t: 0,
          c
        });
      }
    }

    function spawnZombie(edge = true) {
      const side = Math.floor(Math.random() * 4);
      const pad = 40;
      let x = 0, y = 0;

      if (edge) {
        if (side === 0) { x = -pad; y = Math.random() * run.h; }
        if (side === 1) { x = run.w + pad; y = Math.random() * run.h; }
        if (side === 2) { x = Math.random() * run.w; y = -pad; }
        if (side === 3) { x = Math.random() * run.w; y = run.h + pad; }
      } else {
        x = Math.random() * run.w;
        y = Math.random() * run.h;
      }

      const base = 22 + (run.wave * 1.4);
      const hp = (run.mode === "roguelike") ? base * 1.12 : base;

      const z = {
        x, y,
        r: 16 + Math.random() * 6,
        hp,
        maxHp: hp,
        spd: (run.mode === "roguelike" ? 58 : 52) + run.wave * 0.95 + Math.random() * 10,
        dmg: (run.mode === "roguelike" ? 10 : 8) + run.wave * 0.12, // DPS-ish
        id: Math.random().toString(16).slice(2)
      };
      run.zombies.push(z);
    }

    function difficultyTick(t) {
      const waveLen = (run.mode === "roguelike") ? 15000 : 17000;
      if (t >= run.waveEndsAt && run.running) {
        run.wave += 1;
        run.waveEndsAt = t + waveLen;

        const bonus = (run.mode === "roguelike") ? 6 : 4;
        run.coins += Math.round((bonus + run.wave * 0.6) * run.coinMul);

        zToast(`Wave ${run.wave} 🔥`);
        haptic("impact", "medium");

        if (run.mode === "arcade") {
          run.hp = Math.min(run.maxHp, run.hp + 12);
          run.armor = Math.min(run.armorMax, run.armor + 18);
          run._syncPlates();
        } else {
          run.hp = Math.min(run.maxHp, run.hp + 6);
        }
      }

      const baseInterval = (run.mode === "roguelike") ? 520 : 620;
      const interval = Math.max(180, baseInterval - run.wave * 14);

      if (t >= run.spawnAt && run.running) {
        const count = 1 + (run.wave >= 6 ? 1 : 0) + (run.wave >= 12 ? 1 : 0);
        for (let i = 0; i < count; i++) spawnZombie(true);
        run.spawnAt = t + interval + Math.random() * 120;
      }

      const cap = (run.mode === "roguelike") ? 70 : 60;
      if (run.zombies.length > cap) run.zombies.splice(0, run.zombies.length - cap);
    }

    function canShoot(t) {
      if (!run.running) return false;
      if (run.reloading) return false;

      const w = baseWeapon();
      const rpm = w.rpm * run.rpmMul;
      const dt = 60000 / Math.max(1, rpm);
      return (t - run.lastShotAt) >= dt;
    }

    function startReload(t) {
      if (!run.running) return;
      if (run.reloading) return;
      const w = baseWeapon();
      if (run.ammo >= w.mag) return;

      run.reloading = true;
      run.reloadAt = t + (w.reload * run.reloadMul * 1000);
      zToast("Reload…");
      haptic("impact", "light");
    }

    function finishReload() {
      const w = baseWeapon();
      run.ammo = w.mag;
      run.reloading = false;
      run.reloadAt = 0;
      zToast("Reloaded ✅");
      haptic("notif", "success");
    }

    function shoot(t) {
      if (!canShoot(t)) return;

      const w = baseWeapon();
      if (run.ammo <= 0) {
        startReload(t);
        haptic("notif", "warning");
        return;
      }

      run.lastShotAt = t;
      run.ammo -= 1;

      let dx = input.aimX - run.x;
      let dy = input.aimY - run.y;
      const len = Math.hypot(dx, dy) || 1;

      dx /= len; dy /= len;

      const spread = w.spread;
      const ang = Math.atan2(dy, dx);

      const pierce = (w.pierce || 0) + run.pierceBonus;
      const dmgBase = w.dmg * run.dmgMul;

      const mkBullet = (a) => {
        const vx = Math.cos(a) * w.speed;
        const vy = Math.sin(a) * w.speed;
        run.bullets.push({
          x: run.x + dx * (run.r + 10),
          y: run.y + dy * (run.r + 10),
          vx, vy,
          r: (w.type === "sniper") ? 3.2 : 2.6,
          life: 1.15,
          t: 0,
          dmg: dmgBase,
          pierce,
          splash: w.splash || 0
        });
      };

      if (w.type === "shotgun" && w.pellets) {
        for (let i = 0; i < w.pellets; i++) {
          const a = ang + (Math.random() * 2 - 1) * spread;
          mkBullet(a);
        }
      } else if (w.type === "burst" && w.burst) {
        for (let i = 0; i < w.burst; i++) {
          const delay = i * 30;
          setTimeout(() => {
            if (!overlay) return;
            const a = ang + (Math.random() * 2 - 1) * spread * 0.85;
            mkBullet(a);
          }, delay);
        }
      } else if (w.type === "launcher") {
        const a = ang + (Math.random() * 2 - 1) * spread * 0.25;
        mkBullet(a);
      } else {
        const a = ang + (Math.random() * 2 - 1) * spread;
        mkBullet(a);
      }

      haptic("impact", "light");
    }

    function applySplash(x, y, radius, dmg) {
      const r2 = radius * radius;
      for (const z of run.zombies) {
        const d = dist2(x, y, z.x, z.y);
        if (d <= r2) {
          const tt = 1 - Math.sqrt(d) / radius;
          z.hp -= dmg * (0.45 + 0.55 * tt);
        }
      }
    }

    // ✅ REAL ARMOR DAMAGE: armor absorbs same units as HP (no multipliers)
    function applyPlayerDamage(dmg) {
      let left = dmg;
      if (run.armor > 0) {
        const used = Math.min(run.armor, left);
        run.armor -= used;
        left -= used;
        run._syncPlates();
      }
      if (left > 0) run.hp -= left;
    }

    // ✅ plates shop
    function plateCost() {
      const extra = Math.floor(run.wave * 0.6);
      return clamp(run.plateCostBase + extra, 10, 26);
    }

    function buyPlate() {
      if (run.mode !== "roguelike") { zToast("Plates: только Roguelike 😈"); return false; }
      if (!run.running) { zToast("Стартани ран сначала"); return false; }
      if (run.plates >= run.platesMax) { zToast("Плиты уже MAX"); return false; }

      const cost = plateCost();
      if (run.coins < cost) { haptic("notif", "warning"); zToast("Не хватает 💰"); return false; }

      run.coins -= cost;
      run.plates += 1;
      run.armor = clamp(run.plates * run.plateValue, 0, run.armorMax);
      run._syncPlates();

      haptic("notif", "success");
      zToast("Плита установлена 🛡");
      updateHud();
      renderPlateShop();
      return true;
    }

    function tick(dt, t) {
      if (run.reloading && t >= run.reloadAt) finishReload();

      const moveSpeed = 220 * run.moveMul;
      run.x = clamp(run.x + input.joyX * moveSpeed * dt, 18, run.w - 18);
      run.y = clamp(run.y + input.joyY * moveSpeed * dt, 18 + 90, run.h - 24);

      if ((!input.aimX && !input.aimY) || (Number.isNaN(input.aimX) || Number.isNaN(input.aimY))) {
        input.aimX = run.x + 80;
        input.aimY = run.y;
      }

      if (input.shootHeld) shoot(t);

      difficultyTick(t);

      for (let i = run.bullets.length - 1; i >= 0; i--) {
        const b = run.bullets[i];
        b.t += dt;
        b.x += b.vx * dt;
        b.y += b.vy * dt;

        if (b.t >= b.life || b.x < -60 || b.y < -60 || b.x > run.w + 60 || b.y > run.h + 60) {
          run.bullets.splice(i, 1);
          continue;
        }

        let hit = false;
        for (let j = run.zombies.length - 1; j >= 0; j--) {
          const z = run.zombies[j];
          const rr = (z.r + b.r) * (z.r + b.r);
          if (dist2(b.x, b.y, z.x, z.y) <= rr) {
            hit = true;

            const crit = (Math.random() < run.critChance) ? (WEAPONS[run.weaponName]?.crit || 1.6) : 1;
            const dmg = b.dmg * crit;

            z.hp -= dmg;

            if (b.splash) applySplash(b.x, b.y, b.splash, dmg * 0.85);

            addParticle(b.x, b.y, crit > 1 ? "rgba(34,211,238,.9)" : "rgba(255,255,255,.75)", crit > 1 ? 14 : 9);

            if (b.pierce > 0) {
              b.pierce -= 1;
            } else {
              run.bullets.splice(i, 1);
            }

            if (z.hp <= 0) {
              run.zombies.splice(j, 1);
              run.kills += 1;

              const baseCoin = (run.mode === "roguelike") ? 2 : 1;
              const add = Math.round(baseCoin * run.coinMul);
              run.coins += add;

              addParticle(z.x, z.y, "rgba(139,92,246,.85)", 16);

              if (run.mode === "arcade" && Math.random() < 0.06) {
                run.hp = Math.min(run.maxHp, run.hp + 4);
              }
            }

            break;
          }
        }

        if (hit && WEAPONS[run.weaponName]?.type === "launcher") {
          applySplash(b.x, b.y, 120, b.dmg * 1.05);
          run.bullets.splice(i, 1);
        }
      }

      for (let i = run.zombies.length - 1; i >= 0; i--) {
        const z = run.zombies[i];
        const dx = run.x - z.x;
        const dy = run.y - z.y;
        const len = Math.hypot(dx, dy) || 1;

        const vx = (dx / len) * z.spd;
        const vy = (dy / len) * z.spd;

        const jx = (Math.random() * 2 - 1) * 12;
        const jy = (Math.random() * 2 - 1) * 12;

        z.x += (vx + jx) * dt;
        z.y += (vy + jy) * dt;

        const rr = (z.r + run.r + 6) * (z.r + run.r + 6);
        if (dist2(z.x, z.y, run.x, run.y) <= rr) {
          const dmg = z.dmg * dt;
          applyPlayerDamage(dmg);

          z.x -= (dx / len) * 18 * dt;
          z.y -= (dy / len) * 18 * dt;
        }
      }

      for (let i = run.particles.length - 1; i >= 0; i--) {
        const p = run.particles[i];
        p.t += dt;
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.vx *= 0.90;
        p.vy *= 0.90;
        if (p.t >= p.life) run.particles.splice(i, 1);
      }

      if (run.hp <= 0 && run.running) {
        run.hp = 0;
        endRun(true);
      }

      updateHud();
    }

    function draw() {
      if (!ctx || !canvas) return;

      ctx.clearRect(0, 0, run.w, run.h);

      // grid
      ctx.save();
      ctx.globalAlpha = 0.08;
      ctx.strokeStyle = "rgba(255,255,255,.25)";
      const step = 62;
      for (let x = 0; x < run.w; x += step) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, run.h);
        ctx.stroke();
      }
      for (let y = 0; y < run.h; y += step) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(run.w, y);
        ctx.stroke();
      }
      ctx.restore();

      // particles
      for (const p of run.particles) {
        const k = 1 - (p.t / p.life);
        ctx.save();
        ctx.globalAlpha = 0.75 * k;
        ctx.fillStyle = p.c;
        ctx.beginPath();
        ctx.arc(p.x, p.y, 2.2 + 2.8 * (1 - k), 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }

      // bullets
      ctx.save();
      for (const b of run.bullets) {
        ctx.globalAlpha = 0.95;
        ctx.fillStyle = (WEAPONS[run.weaponName]?.type === "sniper") ? "rgba(34,211,238,.95)" : "rgba(255,255,255,.95)";
        ctx.beginPath();
        ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();

      // zombies
      for (const z of run.zombies) {
        ctx.save();
        ctx.globalAlpha = 0.95;
        ctx.fillStyle = "rgba(34,197,94,.18)";
        ctx.beginPath();
        ctx.arc(z.x, z.y, z.r + 7, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = "rgba(34,197,94,.85)";
        ctx.beginPath();
        ctx.arc(z.x, z.y, z.r, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = "rgba(0,0,0,.45)";
        ctx.beginPath();
        ctx.arc(z.x - z.r * 0.25, z.y - z.r * 0.1, 2.2, 0, Math.PI * 2);
        ctx.arc(z.x + z.r * 0.25, z.y - z.r * 0.1, 2.2, 0, Math.PI * 2);
        ctx.fill();

        const hp = clamp(z.hp / z.maxHp, 0, 1);
        ctx.globalAlpha = 0.9;
        ctx.fillStyle = "rgba(0,0,0,.35)";
        ctx.fillRect(z.x - 22, z.y - z.r - 16, 44, 5);
        ctx.fillStyle = "rgba(239,68,68,.9)";
        ctx.fillRect(z.x - 22, z.y - z.r - 16, 44 * hp, 5);

        ctx.restore();
      }

      // player
      const skin = getSkin();
      const c1 = skin.colors[0] || "#9ca3af";
      const c2 = skin.colors[1] || "#111827";

      ctx.save();
      ctx.globalAlpha = 0.25;
      ctx.fillStyle = (state.skin === "royal") ? "rgba(139,92,246,.55)" : "rgba(34,211,238,.35)";
      ctx.beginPath();
      ctx.arc(run.x, run.y, run.r + 16, 0, Math.PI * 2);
      ctx.fill();

      ctx.globalAlpha = 0.95;
      ctx.fillStyle = c1;
      ctx.beginPath();
      ctx.arc(run.x, run.y, run.r, 0, Math.PI * 2);
      ctx.fill();

      // ✅ armor ring shows fill fraction (0..1)
      if (run.armor > 0) {
        ctx.globalAlpha = 0.85;
        ctx.strokeStyle = "rgba(59,130,246,.9)";
        ctx.lineWidth = 3;
        const k = clamp(run.armor / run.armorMax, 0, 1);
        ctx.beginPath();
        ctx.arc(run.x, run.y, run.r + 7, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * k);
        ctx.stroke();
      }

      ctx.globalAlpha = 0.9;
      ctx.fillStyle = c2;
      ctx.beginPath();
      ctx.arc(run.x - 4, run.y - 3, 2.1, 0, Math.PI * 2);
      ctx.arc(run.x + 4, run.y - 3, 2.1, 0, Math.PI * 2);
      ctx.fill();

      if (state.skin === "royal") {
        ctx.globalAlpha = 0.95;
        ctx.fillStyle = "rgba(250,204,21,.95)";
        ctx.fillText("👑", run.x - 10, run.y - 18);
      }

      // Aim line (yes: aim+shoot on map)
      ctx.globalAlpha = 0.22;
      ctx.strokeStyle = "rgba(255,255,255,.65)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(run.x, run.y);
      ctx.lineTo(input.aimX, input.aimY);
      ctx.stroke();

      ctx.restore();

      // vignette
      ctx.save();
      const g = ctx.createRadialGradient(run.w * 0.5, run.h * 0.45, 10, run.w * 0.5, run.h * 0.45, Math.max(run.w, run.h) * 0.65);
      g.addColorStop(0, "rgba(0,0,0,0)");
      g.addColorStop(1, "rgba(0,0,0,.45)");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, run.w, run.h);
      ctx.restore();
    }

    function loop(tms) {
      if (!overlay) { raf = 0; lastT = 0; return; }

      raf = requestAnimationFrame(loop);
      const t = tms || performance.now();
      if (!lastT) lastT = t;
      const dt = clamp((t - lastT) / 1000, 0, 0.033);
      lastT = t;

      if (run.running) tick(dt, now());
      draw();
    }

    function start() {
      if (!overlay) buildOverlay();
      if (run.running) { zToast("Уже запущено"); return; }

      resize();
      resetRun(true);

      run.running = true;
      run.startedAt = now();
      run.waveEndsAt = now() + ((run.mode === "roguelike") ? 15000 : 17000);
      run.spawnAt = now() + 600;

      for (let i = 0; i < 4; i++) spawnZombie(true);

      zToast(run.mode === "roguelike" ? "ROGUELIKE: выживай 😈" : "ARCADE: мясо пошло 💥");
      haptic("notif", "success");
      updateHud();
      renderPlateShop();
    }

    function endRun(auto = false) {
      if (!run.running) return;
      run.running = false;
      run.endedAt = now();

      zToast(auto ? "RUN закончился ☠️" : "STOP");
      haptic("notif", auto ? "error" : "warning");

      if (run.mode === "roguelike") {
        sendResult("auto");
      }
    }

    function stop() {
      run.running = false;
      run.endedAt = now();
      input.shootHeld = false;
    }

    function platesText() {
      const filled = Math.max(0, Math.min(run.plates, run.platesMax));
      const empty = Math.max(0, run.platesMax - filled);
      return "🛡".repeat(filled) + "▫️".repeat(empty);
    }

    function updateHud() {
      const l = qs("#bcozHudL");
      const m = qs("#bcozHudM");
      const r = qs("#bcozHudR");
      const w = baseWeapon();

      if (l) l.textContent = `HP ${Math.round(run.hp)}/${run.maxHp} • Armor ${Math.round(run.armor)}/${run.armorMax} ${platesText()}`;
      if (m) m.textContent = `Wave ${run.wave} • Kills ${run.kills} • 💰 ${run.coins}`;
      if (r) r.textContent = `${run.weaponName} • ${run.ammo}/${w.mag}` + (run.reloading ? " • Reload…" : "");

      const coins = qs("#bcozCoins");
      if (coins) coins.textContent = `💰 ${run.coins}`;
      renderPlateShop();
    }

    function sendResult(origin = "manual") {
      const ended = run.endedAt || now();
      const started = run.startedAt || ended;
      const duration = Math.max(0, ended - started);

      const score = Math.round(run.kills * 55 + run.wave * 120 + run.coins * 2);

      sendToBot({
        action: "game_result",
        game: "zombies",
        mode: run.mode,
        map: state.zombies_map,
        character: state.character,
        skin: state.skin,
        wave: run.wave,
        kills: run.kills,
        coins: run.coins,
        duration_ms: duration,
        loadout: {
          weapon: run.weaponName,
          perks: run.perks.slice(0, 10),
          upgrades: {
            dmgMul: +run.dmgMul.toFixed(3),
            rpmMul: +run.rpmMul.toFixed(3),
            moveMul: +run.moveMul.toFixed(3),
            reloadMul: +run.reloadMul.toFixed(3),
            magMul: +run.magMul.toFixed(3),
            pierce: run.pierceBonus,
            critChance: +run.critChance.toFixed(3),
            coinMul: +run.coinMul.toFixed(3),

            armor: Math.round(run.armor),
            armorMax: run.armorMax,
            plates: run.plates,
            platesMax: run.platesMax
          }
        },
        score,
        origin,
        profile: true
      });

      zToast("Отправлено в бота ✅");
    }

    function buyPerk(perkId) {
      if (run.mode !== "roguelike") { zToast("Shop = только Roguelike 😈"); return; }
      if (!run.running) { zToast("Стартани ран сначала"); return; }

      if (run.perks.includes(perkId)) { zToast("Уже куплено"); return; }

      const perk = PERKS.find(p => p.id === perkId);
      if (!perk) return;

      if (run.coins < perk.cost) { haptic("notif", "warning"); zToast("Не хватает 💰"); return; }

      run.coins -= perk.cost;
      run.perks.push(perkId);
      try { perk.apply?.(run); } catch {}

      run._syncPlates();
      haptic("notif", "success");
      zToast(`Куплено: ${perk.name}`);
      updateHud();
      renderPerkShop();
      renderPlateShop();
    }

    function buyWeapon(name) {
      if (run.mode !== "roguelike") { zToast("Оружие: только Roguelike"); return; }
      if (!run.running) { zToast("Стартани ран сначала"); return; }
      if (!WEAPONS[name]) return;

      const base = { Pistol: 0, SMG: 16, AR: 20, Burst: 22, Shotgun: 22, LMG: 26, Sniper: 28, Launcher: 32 }[name] ?? 20;
      const cost = Math.round(base + run.wave * 0.9);

      if (run.weaponName === name) { zToast("Уже в руках"); return; }
      if (run.coins < cost) { haptic("notif", "warning"); zToast("Не хватает 💰"); return; }

      run.coins -= cost;
      run.weaponName = name;

      const w = baseWeapon();
      run.mag = w.mag;
      run.ammo = w.mag;

      haptic("notif", "success");
      zToast(`Оружие: ${name} ✅`);
      updateHud();
      renderWeaponShop();
      renderPlateShop();
    }

    function renderPlateShop() {
      const root = qs("#bcozPlateItem");
      if (!root) return;

      const cost = plateCost();
      const can =
        run.mode === "roguelike" &&
        run.running &&
        run.plates < run.platesMax &&
        run.coins >= cost;

      const status =
        (run.plates >= run.platesMax) ? "MAX" :
        (!run.running) ? "START RUN" :
        (run.mode !== "roguelike") ? "ROGUELIKE ONLY" :
        (run.coins < cost) ? "NO 💰" : "READY";

      root.innerHTML = `
        <div class="bcoz-item">
          <div>
            <div class="name">🛡 Armor Plate</div>
            <div class="desc">+1 plate (+${run.plateValue} armor). Max ${run.platesMax}. Сейчас: ${run.plates}/${run.platesMax} ${platesText()}</div>
          </div>
          <div style="text-align:right;">
            <div class="cost">💰 ${cost}</div>
            <div class="owned" style="margin:6px 0 8px 0;">${status}</div>
            <button class="bcoz-btn small" data-buy-plate="1" type="button" ${can ? "" : "disabled"}>Plate</button>
          </div>
        </div>
      `;
    }

    function renderPerkShop() {
      const root = qs("#bcozPerkList");
      if (!root) return;

      root.innerHTML = PERKS.map(p => {
        const owned = run.perks.includes(p.id);
        return `
          <div class="bcoz-item" data-perk="${p.id}">
            <div>
              <div class="name">${p.name}</div>
              <div class="desc">${p.desc}</div>
            </div>
            <div style="text-align:right;">
              ${owned ? `<div class="owned">OWNED</div>` : `<div class="cost">💰 ${p.cost}</div>`}
              <button class="bcoz-btn small" data-buy-perk="${p.id}" type="button" ${owned ? "disabled" : ""}>Buy</button>
            </div>
          </div>
        `;
      }).join("");
    }

    function renderWeaponShop() {
      const root = qs("#bcozWeaponList");
      if (!root) return;

      const names = Object.keys(WEAPONS);
      root.innerHTML = names.map(name => {
        const base = { Pistol: 0, SMG: 16, AR: 20, Burst: 22, Shotgun: 22, LMG: 26, Sniper: 28, Launcher: 32 }[name] ?? 20;
        const cost = Math.round(base + run.wave * 0.9);
        const owned = (run.weaponName === name);

        const w = WEAPONS[name];
        const dps = Math.round(w.dmg * (w.rpm / 60));
        const tags = [
          `DMG ${w.dmg}`,
          `RPM ${w.rpm}`,
          `MAG ${w.mag}`,
          (w.pellets ? `PEL ${w.pellets}` : ""),
          (w.pierce ? `PIERCE ${w.pierce}` : ""),
          (w.splash ? `SPLASH` : "")
        ].filter(Boolean).join(" • ");

        return `
          <div class="bcoz-item">
            <div>
              <div class="name">🔫 ${name}</div>
              <div class="desc">${tags} • DPS~${dps}</div>
            </div>
            <div style="text-align:right;">
              ${owned ? `<div class="owned">EQUIPPED</div>` : `<div class="cost">💰 ${cost}</div>`}
              <button class="bcoz-btn small" data-buy-weapon="${name}" type="button" ${owned ? "disabled" : ""}>Take</button>
            </div>
          </div>
        `;
      }).join("");
    }

    function renderCharSelect() {
      const male = qs("#bcozMaleSkins");
      const female = qs("#bcozFemaleSkins");
      if (!male || !female) return;

      const mk = (sex, root) => {
        const arr = SKINS[sex] || [];
        root.innerHTML = arr.map(s => {
          const active = (state.character === sex && state.skin === s.id);
          return `<button class="bcoz-chip ${active ? "active" : ""}" data-skin="${sex}:${s.id}" type="button">${s.name}</button>`;
        }).join("");
      };

      mk("male", male);
      mk("female", female);
    }

    function openShop(open = true) {
      const modal = qs("#bcozShopModal");
      if (!modal) return;
      modal.classList.toggle("show", !!open);
      modal.setAttribute("aria-hidden", open ? "false" : "true");
      updateHud();
      renderPlateShop();
      renderPerkShop();
      renderWeaponShop();
      haptic("impact", "light");
    }

    function openChar(open = true) {
      const modal = qs("#bcozCharModal");
      if (!modal) return;
      modal.classList.toggle("show", !!open);
      modal.setAttribute("aria-hidden", open ? "false" : "true");
      renderCharSelect();
      haptic("impact", "light");
    }

    function joySetKnob(nx, ny) {
      const knob = qs("#bcozKnob");
      if (!knob) return;
      const baseX = 33, baseY = 33;
      const max = 30;
      knob.style.transform = `translate(${baseX + nx * max}px, ${baseY + ny * max}px)`;
    }

    function pointerToOverlayXY(e) {
      const x = e.clientX ?? (e.touches?.[0]?.clientX ?? 0);
      const y = e.clientY ?? (e.touches?.[0]?.clientY ?? 0);
      return { x, y };
    }

    function wireOverlayUI() {
      addL(window, "resize", resize);

      onTap(ui.modeArcade, () => setMode("arcade"));
      onTap(ui.modeRogue, () => setMode("roguelike"));

      onTap(ui.btnStart, () => {
        if (run.running) endRun(false);
        else start();
      });

      onTap(ui.btnClose, () => {
        destroyOverlay();
        try { tg?.HapticFeedback?.notificationOccurred?.("success"); } catch {}
      });

      onTap(ui.btnSend, () => sendResult("manual"));

      onTap(qs("#bcozChar"), () => openChar(true));
      onTap(qs("#bcozCharClose"), () => openChar(false));

      const charModal = qs("#bcozCharModal");
      if (charModal) {
        addL(charModal, "click", async (e) => {
          const btn = e.target.closest("[data-skin]");
          if (!btn) return;
          const [sex, skin] = String(btn.dataset.skin || "").split(":");
          if (!sex || !skin) return;

          state.character = sex;
          state.skin = skin;
          ensureSkinValid();
          await saveState();

          renderCharSelect();
          zToast(`Выбран: ${sex} • ${skin}`);
        }, { passive: true });
      }

      onTap(ui.btnShop, () => openShop(true));
      onTap(qs("#bcozShopClose"), () => openShop(false));

      const shop = qs("#bcozShopModal");
      if (shop) {
        addL(shop, "click", (e) => {
          const plate = e.target.closest("[data-buy-plate]");
          if (plate) { buyPlate(); return; }

          const pb = e.target.closest("[data-buy-perk]");
          if (pb) { buyPerk(pb.dataset.buyPerk); return; }

          const wb = e.target.closest("[data-buy-weapon]");
          if (wb) { buyWeapon(wb.dataset.buyWeapon); return; }
        }, { passive: true });
      }

      onTap(ui.btnReload, () => startReload(now()));

      // FIRE button: hold to shoot; also updates aim
      const shootBtn = ui.btnShoot;
      if (shootBtn) {
        const down = (e) => {
          input.shootHeld = true;
          const p = pointerToOverlayXY(e);
          input.aimX = p.x; input.aimY = p.y;
          e.preventDefault?.();
        };
        const up = (e) => { input.shootHeld = false; e.preventDefault?.(); };

        if (window.PointerEvent) {
          addL(shootBtn, "pointerdown", down, { passive: false });
          addL(shootBtn, "pointerup", up, { passive: false });
          addL(shootBtn, "pointercancel", up, { passive: false });
        } else {
          addL(shootBtn, "touchstart", down, { passive: false });
          addL(shootBtn, "touchend", up, { passive: false });
          addL(shootBtn, "touchcancel", up, { passive: false });
        }
      }

      // Left joystick: movement
      const joy = qs("#bcozJoy");
      const onJoyDown = (e) => {
        const p = pointerToOverlayXY(e);
        input.joyActive = true;
        input.joyId = (e.pointerId != null) ? e.pointerId : "touch";
        input.joyCx = p.x;
        input.joyCy = p.y;
        input.joyX = 0; input.joyY = 0;
        joySetKnob(0, 0);
        e.preventDefault?.();
      };

      const onJoyMove = (e) => {
        if (!input.joyActive) return;
        if (e.pointerId != null && input.joyId != null && e.pointerId !== input.joyId) return;

        const p = pointerToOverlayXY(e);
        const dx = p.x - input.joyCx;
        const dy = p.y - input.joyCy;
        const max = 42;
        const nx = clamp(dx / max, -1, 1);
        const ny = clamp(dy / max, -1, 1);
        input.joyX = nx;
        input.joyY = ny;
        joySetKnob(nx, ny);
        e.preventDefault?.();
      };

      const onJoyUp = (e) => {
        if (e && e.pointerId != null && input.joyId != null && e.pointerId !== input.joyId) return;
        input.joyActive = false;
        input.joyId = null;
        input.joyX = 0; input.joyY = 0;
        joySetKnob(0, 0);
        e.preventDefault?.();
      };

      if (joy) {
        if (window.PointerEvent) {
          addL(joy, "pointerdown", onJoyDown, { passive: false });
          addL(window, "pointermove", onJoyMove, { passive: false });
          addL(window, "pointerup", onJoyUp, { passive: false });
          addL(window, "pointercancel", onJoyUp, { passive: false });
        } else {
          addL(joy, "touchstart", onJoyDown, { passive: false });
          addL(window, "touchmove", onJoyMove, { passive: false });
          addL(window, "touchend", onJoyUp, { passive: false });
          addL(window, "touchcancel", onJoyUp, { passive: false });
        }
      }

      // Canvas aim: tap sets aim; drag updates aim while firing (so yes: aim+shoot on map)
      if (canvas) {
        const aimMove = (e) => {
          const p = pointerToOverlayXY(e);
          input.aimX = p.x;
          input.aimY = p.y;
        };

        if (window.PointerEvent) {
          addL(canvas, "pointerdown", aimMove, { passive: true });
          addL(canvas, "pointermove", (e) => { if (input.shootHeld) aimMove(e); }, { passive: true });
        } else {
          addL(canvas, "touchstart", aimMove, { passive: true });
          addL(canvas, "touchmove", (e) => { if (input.shootHeld) aimMove(e); }, { passive: true });
        }
      }

      if (!raf) raf = requestAnimationFrame(loop);
    }

    function buildOverlay() {
      injectStyleOnce();

      overlay = document.createElement("div");
      overlay.className = "bcoz-ov";
      overlay.innerHTML = `
        <canvas class="bcoz-canvas" id="bcozCanvas"></canvas>

        <div class="bcoz-top">
          <div class="bcoz-left">
            <div class="bcoz-badge">🧟</div>
            <div>
              <div class="bcoz-title">Zombies Survival</div>
              <div class="bcoz-sub" id="bcozSub">ARCADE • Fullscreen 2D</div>
            </div>
          </div>

          <div class="bcoz-modes">
            <button class="bcoz-seg active" id="bcozModeArcade" type="button">💥 Arcade</button>
            <button class="bcoz-seg" id="bcozModeRogue" type="button">😈 Roguelike</button>
            <button class="bcoz-btn small" id="bcozChar" type="button">🧍 Character</button>
            <button class="bcoz-btn small" id="bcozSend" type="button">📤 Send</button>
            <button class="bcoz-btn small" id="bcozClose" type="button">✖</button>
          </div>
        </div>

        <div class="bcoz-hud" id="bcozHud">
          <div id="bcozHudL">HP 100 • Armor 0</div>
          <div id="bcozHudM">Wave 1 • Kills 0 • 💰 0</div>
          <div id="bcozHudR">SMG • 30/30</div>
        </div>

        <div class="bcoz-joybase"></div>
        <div class="bcoz-joystick" id="bcozJoy">
          <div class="bcoz-joyknob" id="bcozKnob"></div>
        </div>

        <div class="bcoz-right">
          <button class="bcoz-shoot" id="bcozShoot" type="button">FIRE</button>
          <div class="bcoz-minirow">
            <button class="bcoz-mini" id="bcozReload" type="button">🔄</button>
            <button class="bcoz-mini" id="bcozShop" type="button">🛒</button>
            <button class="bcoz-mini" id="bcozStart" type="button">▶</button>
          </div>
        </div>

        <div class="bcoz-toast" id="bcozToast">OK</div>

        <div class="bcoz-shop" id="bcozShopModal" aria-hidden="true">
          <div class="bcoz-panel">
            <div class="bcoz-row">
              <div style="font-weight:1000;">🛒 Shop</div>
              <div style="opacity:.8; font-weight:1000;" id="bcozCoins">💰 0</div>
              <button class="bcoz-btn small" id="bcozShopClose" type="button">✖ Close</button>
            </div>

            <div class="bcoz-hr"></div>

            <div style="font-weight:1000; margin-bottom:8px;">Armor Plates</div>
            <div id="bcozPlateItem"></div>

            <div class="bcoz-hr"></div>

            <div style="font-weight:1000; margin-bottom:8px;">Perks</div>
            <div class="bcoz-grid" id="bcozPerkList"></div>

            <div class="bcoz-hr"></div>

            <div style="font-weight:1000; margin-bottom:8px;">Weapons</div>
            <div class="bcoz-grid" id="bcozWeaponList"></div>
          </div>
        </div>

        <div class="bcoz-char" id="bcozCharModal" aria-hidden="true">
          <div class="bcoz-panel">
            <div class="bcoz-row">
              <div style="font-weight:1000;">🧍 Character & Skins</div>
              <button class="bcoz-btn small" id="bcozCharClose" type="button">✖ Close</button>
            </div>

            <div class="bcoz-hr"></div>

            <div class="bcoz-cards">
              <div class="bcoz-card">
                <div class="ttl">Male</div>
                <div class="bcoz-chiprow" id="bcozMaleSkins"></div>
              </div>

              <div class="bcoz-card">
                <div class="ttl">Female</div>
                <div class="bcoz-chiprow" id="bcozFemaleSkins"></div>
              </div>
            </div>

            <div class="hint" style="opacity:.75; margin-top:12px; font-weight:900;">
              Выбор сохраняется. В игре цвет/аура скина видны.
            </div>
          </div>
        </div>
      `;

      document.body.appendChild(overlay);

      canvas = qs("#bcozCanvas");
      ctx = canvas?.getContext?.("2d", { alpha: true });

      ui.modeArcade = qs("#bcozModeArcade");
      ui.modeRogue = qs("#bcozModeRogue");
      ui.btnStart = qs("#bcozStart");
      ui.btnClose = qs("#bcozClose");
      ui.btnShop = qs("#bcozShop");
      ui.btnShoot = qs("#bcozShoot");
      ui.btnReload = qs("#bcozReload");
      ui.btnSend = qs("#bcozSend");
      ui.hud = qs("#bcozHud");
      ui.toast = qs("#bcozToast");

      addL(overlay, "touchmove", (e) => { e.preventDefault(); }, { passive: false });

      lockBody(true);

      wireOverlayUI();
      resize();
      renderPlateShop();
      renderPerkShop();
      renderWeaponShop();
      renderCharSelect();
      updateHud();
      syncAssetsIfAny();
    }

    function destroyOverlay() {
      stop();

      try { if (raf) cancelAnimationFrame(raf); } catch {}
      raf = 0;
      lastT = 0;

      removeAllL();
      lockBody(false);

      if (overlay) overlay.remove();
      overlay = null;
      canvas = null;
      ctx = null;
    }

    function open() {
      if (!overlay) buildOverlay();
      resize();
      resetRun(true);
      setMode(run.mode || "arcade");
      updateHud();
      renderPlateShop();
      zToast("Zombies ready 😈");
      haptic("notif", "success");
      if (!raf) raf = requestAnimationFrame(loop);
    }

    return {
      open,
      start,
      stop,
      destroy: destroyOverlay,
      setMode,
      sendResult,
      buyPerk,
      buyPlate,
      isOpen: () => !!overlay
    };
  })();

  // =========================================================
  // ---------- Wire buttons ----------
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

    // ✅ ZOMBIES Fullscreen launcher
    const btnZArc = qs("#btnZModeArcade");
    const btnZRog = qs("#btnZModeRogue");
    const btnZStart = qs("#btnZGameStart");
    const btnZStop = qs("#btnZGameStop");
    const btnZSend = qs("#btnZGameSend");

    onTap(btnZArc, () => { Z.open(); Z.setMode("arcade"); });
    onTap(btnZRog, () => { Z.open(); Z.setMode("roguelike"); });

    onTap(btnZStart, () => { Z.open(); Z.start(); });
    onTap(btnZStop, () => { Z.open(); Z.stop(); toast("Zombies: стоп"); });
    onTap(btnZSend, () => { Z.open(); Z.sendResult("manual"); });

    // ✅ Old home "Shop" buttons now реально покупают
    onTap(qs("#btnZBuyJug"), () => { Z.open(); Z.setMode("roguelike"); Z.start(); Z.buyPerk("Jug"); });
    onTap(qs("#btnZBuySpeed"), () => { Z.open(); Z.setMode("roguelike"); Z.start(); Z.buyPerk("Speed"); });
    onTap(qs("#btnZBuyAmmo"), () => { Z.open(); Z.setMode("roguelike"); Z.start(); Z.buyPerk("Mag"); });

    // (если хочешь отдельную кнопку Plate — добавим в HTML или повесим на Ammo)
    // onTap(qs("#btnZBuyAmmo"), () => { Z.open(); Z.setMode("roguelike"); Z.start(); Z.buyPlate(); });
  }

  // ---------- Build tag ----------
  function ensureBuildTag() {
    const buildFromIndex =
      (window.__BCO_BUILD__ && window.__BCO_BUILD__ !== "__BUILD__")
        ? window.__BCO_BUILD__
        : null;

    const txt = buildFromIndex ? `build ${buildFromIndex} • v${VERSION}` : `v${VERSION}`;
    const buildTag = qs("#buildTag");
    if (buildTag) buildTag.textContent = txt;
  }

  // ---------- Init Telegram ----------
  function initTelegram() {
    if (!tg) {
      const statOnline = qs("#statOnline");
      if (statOnline) statOnline.textContent = "BROWSER";
      const dbgInit = qs("#dbgInit");
      if (dbgInit) dbgInit.textContent = "no tg";
      return;
    }

    try { tg.ready(); } catch {}
    try { tg.expand(); } catch {}

    applyTelegramTheme();
    try { tg.onEvent("themeChanged", applyTelegramTheme); } catch {}

    const dbgUser = qs("#dbgUser");
    const dbgChat = qs("#dbgChat");
    const dbgInit = qs("#dbgInit");
    const statOnline = qs("#statOnline");

    if (dbgUser) dbgUser.textContent = tg.initDataUnsafe?.user?.id ?? "—";
    if (dbgChat) dbgChat.textContent = tg.initDataUnsafe?.chat?.id ?? "—";
    if (dbgInit) dbgInit.textContent = (tg.initData ? "ok" : "empty");
    if (statOnline) statOnline.textContent = "ONLINE";

    updateTelegramButtons();
  }

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

    selectTab("home");
  }

  boot();
})();
