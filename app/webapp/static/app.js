// app/webapp/static/app.js
(() => {
  window.__BCO_JS_OK__ = true;

  const tg = window.Telegram?.WebApp;

  const VERSION = "1.2.0";
  const STORAGE_KEY = "bco_state_v1";
  const CHAT_KEY = "bco_chat_v1";

  const defaults = {
    game: "Warzone",
    focus: "aim",
    mode: "Normal", // UI key
    platform: "PC",
    input: "Controller",
    voice: "TEAMMATE",
    role: "Flex",
    bf6_class: "Assault",
    zombies_map: "Ashes"
  };

  const state = { ...defaults };

  // chat state
  const chat = {
    history: [], // [{role:'user'|'assistant', text:'...', ts:number}]
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
      if (type === "notif") tg.HapticFeedback.notificationOccurred(style); // success|warning|error
    } catch {}
  }

  function toast(text) {
    const t = qs("#toast");
    if (!t) return;
    t.textContent = text;
    t.classList.add("show");
    setTimeout(() => t.classList.remove("show"), 1700);
  }

  // =========================================================
  // ✅ FAST TAP (iOS WebView SAFE)
  // =========================================================
  function onTap(el, handler) {
    if (!el) return;

    let locked = false;
    const lock = () => {
      locked = true;
      setTimeout(() => (locked = false), 320);
    };

    const fire = (e) => {
      if (locked) return;
      lock();
      try { handler(e); } catch {}
    };

    // iOS иногда "съедает" pointerup на вложенных элементах → даём fallback
    if (window.PointerEvent) {
      el.addEventListener("pointerup", fire, { passive: true });
      el.addEventListener("click", fire, { passive: true });
      return;
    }

    el.addEventListener("touchend", fire, { passive: true });
    el.addEventListener("click", fire, { passive: true });
  }

  // ---------- Theme sync (Telegram -> CSS vars) ----------
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
      difficulty: state.mode, // router expects difficulty
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

  // ✅ FIX: profile всегда должен уходить в формате router, а не state-объект
  function sendToBot(payload) {
    try {
      const fixed = { ...payload };

      // если в payload есть profile — подменяем на router-формат
      if ("profile" in fixed) fixed.profile = toRouterProfile();

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

  // ✅ FIX: router ждёт type="nav", а не "open"
  function openBotMenuHint(target) {
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

    tgMainHandler = () => {
      haptic("impact", "medium");

      if (currentTab === "settings") {
        sendToBot({ type: "set_profile", profile: true });
        return;
      }
      if (currentTab === "coach") {
        sendToBot({ type: "training_plan", focus: state.focus, profile: true });
        return;
      }
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

    try { tg.MainButton.offClick?.(tgMainHandler); } catch {}
    try { tg.MainButton.onClick(tgMainHandler); } catch {}

    try { tg.BackButton.offClick?.(tgBackHandler); } catch {}
    try { tg.BackButton.onClick(tgBackHandler); } catch {}
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
  // endpoint: POST /webapp/api/ask
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

    try {
      const res = await fetch("/webapp/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });

      const data = await res.json().catch(() => null);
      setTyping(false);

      if (!data || data.ok !== true) {
        const err = (data && (data.error || data.detail)) ? String(data.error || data.detail) : "api_error";
        return `🧠 Mini App: API error (${err}).`;
      }

      return String(data.reply ?? "");
    } catch (e) {
      setTyping(false);
      return `🧠 Mini App: network error (${String(e?.message || e)}).`;
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
  // 🎯 GAME #1: AIM TRIAL (ARCADE)
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
    const pad = 18;

    const w = Math.max(60, rect.width);
    const h = Math.max(160, rect.height);

    const x = pad + Math.random() * (w - pad * 2);
    const y = pad + Math.random() * (h - pad * 2);

    target.style.transform = `translate(${x}px, ${y}px)`;
  }

  function aimUpdateUI() {
    const { stat, btnStart, btnStop, btnSend } = aimEls();
    const acc = aim.shots ? Math.round((aim.hits / aim.shots) * 100) : 0;
    const tLeft = aim.running
      ? Math.max(0, aim.durationMs - (now() - aim.startedAt))
      : 0;

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
  // 🧟 GAME #2: ZOMBIES SURVIVAL (ARCADE + ROGUELIKE)
  // =========================================================
  const zgame = {
    running: false,
    startedAt: 0,
    mode: "arcade", // arcade | roguelike
    wave: 1,
    kills: 0,
    coins: 0,
    weapon: "SMG",
    perks: [],
    hp: 100,
    timerId: null
  };

  function zEls() {
    return {
      stat: qs("#zStat"),
      btnArcade: qs("#btnZModeArcade"),
      btnRogue: qs("#btnZModeRogue"),
      btnStart: qs("#btnZGameStart"),
      btnStop: qs("#btnZGameStop"),
      btnSend: qs("#btnZGameSend"),
      btnBuyJug: qs("#btnZBuyJug"),
      btnBuySpeed: qs("#btnZBuySpeed"),
      btnBuyAmmo: qs("#btnZBuyAmmo"),
      arena: qs("#zArena"),
      z1: qs("#z1"),
      z2: qs("#z2"),
      z3: qs("#z3")
    };
  }

  function zUpdateUI() {
    const { stat, btnStart, btnStop, btnSend } = zEls();
    const dur = zgame.running ? (now() - zgame.startedAt) : 0;

    if (stat) {
      stat.textContent =
        `🎮 ${zgame.mode.toUpperCase()} • 🧟 Wave ${zgame.wave} • ☠️ ${zgame.kills} • 💰 ${zgame.coins} • ❤️ ${zgame.hp} • 🔫 ${zgame.weapon}` +
        (zgame.perks.length ? ` • 🧪 ${zgame.perks.join(", ")}` : "") +
        (zgame.running ? ` • ⏱ ${(dur / 1000).toFixed(0)}s` : "");
    }

    if (btnStart) btnStart.disabled = zgame.running;
    if (btnStop) btnStop.disabled = !zgame.running;
    if (btnSend) btnSend.disabled = zgame.running || zgame.kills < 5;
  }

  function zReset() {
    zgame.running = false;
    zgame.startedAt = 0;
    zgame.wave = 1;
    zgame.kills = 0;
    zgame.coins = 0;
    zgame.weapon = "SMG";
    zgame.perks = [];
    zgame.hp = 100;
    if (zgame.timerId) { clearInterval(zgame.timerId); zgame.timerId = null; }
    zUpdateUI();
  }

  function zSpawn() {
    const { arena, z1, z2, z3 } = zEls();
    if (!arena || !z1 || !z2 || !z3) return;

    const rect = arena.getBoundingClientRect();
    const pad = 14;

    const place = (el) => {
      const x = pad + Math.random() * (Math.max(180, rect.width) - pad * 2);
      const y = pad + Math.random() * (Math.max(180, rect.height) - pad * 2);
      el.style.transform = `translate(${x}px, ${y}px)`;
      el.classList.remove("dead");
      el.dataset.alive = "1";
    };

    place(z1); place(z2); place(z3);
  }

  function zOnKill() {
    zgame.kills += 1;
    zgame.coins += (zgame.mode === "roguelike") ? 2 : 1;

    // wave up: каждые 10 киллов
    if (zgame.kills % 10 === 0) {
      zgame.wave += 1;
      // сложность: по чуть-чуть жмём HP
      if (zgame.mode === "roguelike") zgame.hp = Math.max(0, zgame.hp - 6);
      else zgame.hp = Math.max(0, zgame.hp - 3);
      toast(`Wave ${zgame.wave} 🔥`);
      haptic("impact", "medium");
      zSpawn();
    }

    // death condition
    if (zgame.hp <= 0) {
      zStop(true);
    }

    zUpdateUI();
  }

  function zStop(auto = false) {
    if (!zgame.running) return;
    zgame.running = false;
    if (zgame.timerId) { clearInterval(zgame.timerId); zgame.timerId = null; }
    zUpdateUI();
    toast(auto ? "Zombies: конец рана" : "Zombies: стоп");
    haptic("notif", auto ? "warning" : "success");
  }

  function zStart() {
    if (zgame.running) return;
    zReset();
    zgame.running = true;
    zgame.startedAt = now();
    zSpawn();
    zUpdateUI();

    // авто-спавн/давление
    zgame.timerId = setInterval(() => {
      // периодический “урон” как давление
      if (zgame.mode === "roguelike") zgame.hp = Math.max(0, zgame.hp - 2);
      else zgame.hp = Math.max(0, zgame.hp - 1);

      if (zgame.hp <= 0) zStop(true);
      zUpdateUI();
    }, 1800);

    toast(zgame.mode === "roguelike" ? "Roguelike: выживай 😈" : "Arcade: поехали 💥");
    haptic("notif", "success");
  }

  function zSendResult() {
    const duration = zgame.running ? (now() - zgame.startedAt) : (now() - (zgame.startedAt || now()));
    sendToBot({
      action: "game_result",
      game: "zombies",
      mode: zgame.mode,
      wave: zgame.wave,
      kills: zgame.kills,
      coins: zgame.coins,
      duration_ms: duration,
      loadout: { weapon: zgame.weapon, perks: zgame.perks.slice(0, 6) },
      score: Math.round(zgame.kills * 50 + zgame.wave * 80 + zgame.coins),
      profile: true
    });
  }

  function zSetMode(m) {
    zgame.mode = m;
    const { btnArcade, btnRogue } = zEls();
    if (btnArcade) btnArcade.classList.toggle("active", m === "arcade");
    if (btnRogue) btnRogue.classList.toggle("active", m === "roguelike");
    toast(m === "roguelike" ? "Режим: Roguelike 😈" : "Режим: Arcade 💥");
    haptic("impact", "light");
    zUpdateUI();
  }

  function zBuy(name, cost, effect) {
    if (!zgame.running || zgame.mode !== "roguelike") { toast("Roguelike только во время рана"); return; }
    if (zgame.coins < cost) { haptic("notif", "warning"); toast("Не хватает монет 💰"); return; }
    if (zgame.perks.includes(name)) { toast("Уже куплено"); return; }
    zgame.coins -= cost;
    zgame.perks.push(name);
    try { effect?.(); } catch {}
    toast(`Куплено: ${name} ✅`);
    haptic("notif", "success");
    zUpdateUI();
  }

  // ---------- Wire buttons ----------
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
        "Теперь ещё и мини-игры: Aim Trial + Zombies (Arcade/Roguelike).";
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
      // hit
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

      // miss (tap arena)
      onTap(arena, () => {
        if (!aim.running) return;
        aim.shots += 1;
        haptic("impact", "light");
        aimUpdateUI();
      });
    }

    // ZOMBIES game
    const ze = zEls();
    onTap(ze.btnArcade, () => zSetMode("arcade"));
    onTap(ze.btnRogue, () => zSetMode("roguelike"));
    onTap(ze.btnStart, () => zStart());
    onTap(ze.btnStop, () => zStop(false));
    onTap(ze.btnSend, () => zSendResult());

    onTap(ze.btnBuyJug, () => zBuy("Jug", 12, () => { zgame.hp = Math.min(140, zgame.hp + 25); }));
    onTap(ze.btnBuySpeed, () => zBuy("Speed", 10, () => { zgame.weapon = "AR"; }));
    onTap(ze.btnBuyAmmo, () => zBuy("Ammo", 8, () => { zgame.coins += 2; }));

    const hitZombie = (zEl) => {
      if (!zgame.running) return;
      if (!zEl || zEl.dataset.alive !== "1") return;
      zEl.dataset.alive = "0";
      zEl.classList.add("dead");
      haptic("impact", "light");
      zOnKill();
    };

    onTap(ze.z1, () => hitZombie(ze.z1));
    onTap(ze.z2, () => hitZombie(ze.z2));
    onTap(ze.z3, () => hitZombie(ze.z3));

    // miss on arena = hp down
    onTap(ze.arena, () => {
      if (!zgame.running) return;
      zgame.hp = Math.max(0, zgame.hp - (zgame.mode === "roguelike" ? 4 : 2));
      haptic("notif", "warning");
      zUpdateUI();
      if (zgame.hp <= 0) zStop(true);
    });
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

    // chat
    renderChat();

    // games init
    aimReset();
    zReset();
    zSetMode("arcade");

    selectTab("home");
  }

  boot();
})();
