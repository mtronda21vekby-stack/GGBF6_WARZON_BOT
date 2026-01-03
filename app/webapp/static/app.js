/* app/webapp/static/app.js */
(() => {
  "use strict";

  // =========================
  // CONFIG
  // =========================
  const CONFIG = {
    VERSION: "mini-bridge-2.0.0",
    STORAGE_KEY: "bco_state_v1",
    CHAT_KEY: "bco_chat_v1",
    CHAT_LIMIT: 80,
    AIM_DURATION_MS: 20000,
    MAX_PAYLOAD: 15000
  };

  const $ = (q) => document.querySelector(q);
  const $$ = (q) => Array.from(document.querySelectorAll(q));
  const now = () => Date.now();
  const safe = (fn) => { try { return fn(); } catch (_) { return undefined; } };

  const tg = safe(() => window.Telegram && window.Telegram.WebApp) || null;

  // =========================
  // STATE
  // =========================
  const State = {
    tg,
    currentTab: "home",
    inGame: false,
    buildId: window.__BCO_BUILD__ || "dev",
    profile: {
      game: "Warzone",
      focus: "aim",
      mode: "Normal",
      platform: "PC",
      input: "Controller",
      voice: "TEAMMATE",
      role: "Flex",
      bf6_class: "Assault",
      zombies_map: "Ashes",
      zombies_mode: "arcade"
    },
    chat: {
      history: [],
      lastSendAt: 0
    },
    aim: {
      running: false,
      startedAt: 0,
      shots: 0,
      hits: 0,
      timer: null
    }
  };

  // =========================
  // UI: TOAST + DEBUG
  // =========================
  function toast(msg, ms = 1400) {
    const el = $("#toast");
    if (!el) return;
    el.textContent = String(msg || "");
    el.classList.add("show");
    setTimeout(() => el.classList.remove("show"), ms);
  }

  function setHealth(text) {
    const el = $("#jsHealth");
    if (el) el.textContent = text;
  }

  function fmtTime(ts) {
    try {
      const d = new Date(ts);
      return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
    } catch {
      return "";
    }
  }

  // =========================
  // STORAGE (local + cloud)
  // =========================
  const Storage = {
    async get(key) {
      if (tg?.CloudStorage?.getItem) {
        return await new Promise((resolve) => {
          tg.CloudStorage.getItem(key, (err, value) => resolve(err ? null : (value || null)));
        });
      }
      return localStorage.getItem(key);
    },
    async set(key, value) {
      try { localStorage.setItem(key, value); } catch (_) {}
      if (tg?.CloudStorage?.setItem) {
        return await new Promise((resolve) => {
          tg.CloudStorage.setItem(key, value, (err) => resolve(!err));
        });
      }
      return true;
    },
    defaults() {
      return {
        game: "Warzone",
        focus: "aim",
        mode: "Normal",
        platform: "PC",
        input: "Controller",
        voice: "TEAMMATE",
        role: "Flex",
        bf6_class: "Assault",
        zombies_map: "Ashes",
        zombies_mode: "arcade"
      };
    },
    async load() {
      const raw = await this.get(CONFIG.STORAGE_KEY);
      let obj = null;
      try { obj = JSON.parse(raw || ""); } catch (_) {}
      State.profile = Object.assign(this.defaults(), (obj && typeof obj === "object") ? obj : {});
      this.sanitize();
    },
    async save() {
      this.sanitize();
      return await this.set(CONFIG.STORAGE_KEY, JSON.stringify(State.profile));
    },
    async loadChat() {
      const raw = await this.get(CONFIG.CHAT_KEY);
      let obj = null;
      try { obj = JSON.parse(raw || ""); } catch (_) {}
      const hist = obj?.history;
      State.chat.history = Array.isArray(hist) ? hist.slice(-CONFIG.CHAT_LIMIT) : [];
    },
    async saveChat() {
      const payload = JSON.stringify({ history: State.chat.history.slice(-CONFIG.CHAT_LIMIT), ts: now() });
      return await this.set(CONFIG.CHAT_KEY, payload);
    },
    sanitize() {
      const p = State.profile;
      const validMode = ["Normal", "Pro", "Demon"];
      if (!validMode.includes(p.mode)) p.mode = "Normal";

      const validPlatform = ["PC", "PlayStation", "Xbox"];
      if (!validPlatform.includes(p.platform)) p.platform = "PC";

      const validInput = ["KBM", "Controller"];
      if (!validInput.includes(p.input)) p.input = "Controller";

      const validVoice = ["TEAMMATE", "COACH"];
      if (!validVoice.includes(p.voice)) p.voice = "TEAMMATE";

      const validMap = ["Ashes", "Astra"];
      if (!validMap.includes(p.zombies_map)) p.zombies_map = "Ashes";

      const validZMode = ["arcade", "roguelike"];
      if (!validZMode.includes(p.zombies_mode)) p.zombies_mode = "arcade";
    }
  };

  // =========================
  // BRIDGE SEND (ONLY TG sendData)
  // =========================
  function buildProfilePayload() {
    // это то, что надо боту (как раньше)
    const p = State.profile;
    return {
      game: p.game,
      platform: p.platform,
      input: p.input,
      difficulty: p.mode,
      voice: p.voice,
      role: p.role,
      bf6_class: p.bf6_class,
      zombies_map: p.zombies_map,
      mode: p.mode
    };
  }

  function sendToBot(payload) {
    const bridge = window.BCO_BRIDGE;
    const base = Object.assign({}, payload || {});
    if (base.profile === true) base.profile = buildProfilePayload();

    const ok = bridge?.sendData ? bridge.sendData(base) : (tg?.sendData ? (safe(() => tg.sendData(JSON.stringify(base))), true) : false);
    if (ok) toast("Отправлено в бота 🚀");
    else toast("sendData недоступен (открой в Telegram)");
    return !!ok;
  }

  // =========================
  // TABS
  // =========================
  function selectTab(tab) {
    if (!tab) tab = "home";
    State.currentTab = tab;

    $$(".tabpane").forEach((pane) => pane.classList.toggle("active", pane.id === `tab-${tab}`));
    $$(".nav-btn").forEach((btn) => btn.classList.toggle("active", btn.dataset.tab === tab));

    safe(() => window.scrollTo({ top: 0, behavior: "smooth" }));
    updateTGButtons();
  }

  // =========================
  // HEADER CHIPS
  // =========================
  function updateChips() {
    const p = State.profile;

    const chipVoice = $("#chipVoice");
    if (chipVoice) chipVoice.textContent = (p.voice === "COACH") ? "📚 Коуч" : "🤝 Тиммейт";

    const chipMode = $("#chipMode");
    if (chipMode) chipMode.textContent = p.mode === "Demon" ? "😈 Demon" : (p.mode === "Pro" ? "🔥 Pro" : "🧠 Normal");

    const chipPlatform = $("#chipPlatform");
    if (chipPlatform) chipPlatform.textContent = p.platform === "PC" ? "🖥 PC" : "🎮 " + p.platform;

    const pillRole = $("#pillRole");
    if (pillRole) pillRole.textContent = `🎭 Role: ${p.role}`;

    const pillBf6 = $("#pillBf6");
    if (pillBf6) pillBf6.textContent = `🟩 Class: ${p.bf6_class}`;

    const chatSub = $("#chatSub");
    if (chatSub) chatSub.textContent = `${p.voice} • ${p.mode} • ${p.platform}`;
  }

  function cycleMode() {
    const modes = ["Normal", "Pro", "Demon"];
    const i = modes.indexOf(State.profile.mode);
    State.profile.mode = modes[(i + 1) % modes.length];
  }

  function cyclePlatform() {
    const arr = ["PC", "PlayStation", "Xbox"];
    const i = arr.indexOf(State.profile.platform);
    State.profile.platform = arr[(i + 1) % arr.length];
  }

  // =========================
  // SEGMENTS (delegated)
  // =========================
  function applySegment(rootId, value) {
    const root = $(rootId);
    if (!root) return;
    root.querySelectorAll(".seg-btn").forEach((b) => {
      const on = (b.dataset.value === value);
      b.classList.toggle("active", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }

  function syncSegmentsFromState() {
    applySegment("#segGame", State.profile.game);
    applySegment("#segFocus", State.profile.focus);
    applySegment("#segMode", State.profile.mode);
    applySegment("#segPlatform", State.profile.platform);
    applySegment("#segInput", State.profile.input);
    applySegment("#segVoice", State.profile.voice);
    applySegment("#segZMap", State.profile.zombies_map);
  }

  // =========================
  // CHAT
  // =========================
  function chatRender() {
    const box = $("#chatLog");
    if (!box) return;

    const h = State.chat.history.slice(-CONFIG.CHAT_LIMIT);
    if (!h.length) {
      box.innerHTML = `
        <div class="chat-row bot">
          <div>
            <div class="bubble">🤝 Пиши сюда — это чат в Mini App. А если надо меню/команды — кнопки отправляют в бота.</div>
            <div class="chat-meta">BCO • ${fmtTime(now())}</div>
          </div>
        </div>
      `;
      return;
    }

    box.innerHTML = h.map((m) => {
      const isBot = m.role === "assistant";
      const cls = isBot ? "bot" : "me";
      const who = isBot ? "BCO" : "Ты";
      return `
        <div class="chat-row ${cls}">
          <div>
            <div class="bubble">${escapeHtml(m.text || "")}</div>
            <div class="chat-meta">${who} • ${fmtTime(m.ts || now())}</div>
          </div>
        </div>
      `;
    }).join("");

    setTimeout(() => { box.scrollTop = box.scrollHeight; }, 30);
  }

  function escapeHtml(s) {
    const div = document.createElement("div");
    div.textContent = String(s || "");
    return div.innerHTML;
  }

  function chatAdd(role, text) {
    const t = String(text || "").trim();
    if (!t) return;
    State.chat.history.push({ role, text: t, ts: now() });
    if (State.chat.history.length > 180) State.chat.history = State.chat.history.slice(-180);
    chatRender();
  }

  async function chatSend() {
    const input = $("#chatInput");
    const text = (input?.value || "").trim();
    if (!text) return toast("Напиши текст");

    const ts = now();
    if (ts - State.chat.lastSendAt < 350) return toast("Чуть пауза…");
    State.chat.lastSendAt = ts;

    chatAdd("user", text);
    if (input) input.value = "";
    await Storage.saveChat();

    // ВАЖНО: без сервера мы не “ответим” как AI, но мы МОЖЕМ:
    // 1) отправить в бота (бот ответит в Telegram чате)
    // 2) показать в mini-app, что команда ушла
    sendToBot({ type: "chat", text, profile: true });

    chatAdd("assistant", "✅ Отправил в бота. Ответ придёт в Telegram-чате (как раньше).");
    await Storage.saveChat();
  }

  // =========================
  // AIM GAME
  // =========================
  function aimReset() {
    State.aim.running = false;
    State.aim.startedAt = 0;
    State.aim.shots = 0;
    State.aim.hits = 0;
    if (State.aim.timer) { clearInterval(State.aim.timer); State.aim.timer = null; }
    aimUpdateUI();
  }

  function aimMoveTarget() {
    const arena = $("#aimArena");
    const target = $("#aimTarget");
    if (!arena || !target) return;

    const ar = arena.getBoundingClientRect();
    const tr = target.getBoundingClientRect();
    const pad = 14;

    const w = Math.max(30, tr.width || 44);
    const h = Math.max(30, tr.height || 44);

    const maxX = Math.max(pad, ar.width - pad - w);
    const maxY = Math.max(pad, ar.height - pad - h);

    const x = pad + Math.random() * (maxX - pad);
    const y = pad + Math.random() * (maxY - pad);

    target.style.transform = `translate(${x}px, ${y}px)`;
  }

  function aimUpdateUI() {
    const stat = $("#aimStat");
    const btnStart = $("#btnAimStart");
    const btnStop = $("#btnAimStop");
    const btnSend = $("#btnAimSend");

    const acc = State.aim.shots ? Math.round((State.aim.hits / State.aim.shots) * 100) : 0;
    const left = State.aim.running ? Math.max(0, CONFIG.AIM_DURATION_MS - (now() - State.aim.startedAt)) : 0;

    if (stat) {
      stat.textContent = State.aim.running
        ? `⏱ ${(left / 1000).toFixed(1)}s • 🎯 ${State.aim.hits}/${State.aim.shots} • Acc ${acc}%`
        : `🎯 ${State.aim.hits}/${State.aim.shots} • Acc ${acc}%`;
    }
    if (btnStart) btnStart.disabled = State.aim.running;
    if (btnStop) btnStop.disabled = !State.aim.running;
    if (btnSend) btnSend.disabled = State.aim.running || State.aim.shots < 5;
  }

  function aimStart() {
    if (State.aim.running) return;
    aimReset();
    State.aim.running = true;
    State.aim.startedAt = now();
    aimMoveTarget();
    aimUpdateUI();

    State.aim.timer = setInterval(() => {
      aimMoveTarget();
      aimUpdateUI();
      if (now() - State.aim.startedAt >= CONFIG.AIM_DURATION_MS) aimStop(true);
    }, 650);

    toast("AIM: поехали 😈");
  }

  function aimStop(auto = false) {
    if (!State.aim.running) return;
    State.aim.running = false;
    if (State.aim.timer) { clearInterval(State.aim.timer); State.aim.timer = null; }
    aimUpdateUI();
    toast(auto ? "AIM завершён" : "Остановлено");
  }

  function aimHit() {
    if (!State.aim.running) return;
    State.aim.shots += 1;
    State.aim.hits += 1;
    aimMoveTarget();
    aimUpdateUI();
  }

  function aimMiss() {
    if (!State.aim.running) return;
    State.aim.shots += 1;
    aimUpdateUI();
  }

  function aimSendResult() {
    const dur = State.aim.running ? (now() - State.aim.startedAt) : CONFIG.AIM_DURATION_MS;
    const acc = State.aim.shots ? (State.aim.hits / State.aim.shots) : 0;
    const score = Math.round(State.aim.hits * 100 + acc * 100);
    sendToBot({
      action: "game_result",
      game: "aim",
      mode: "arcade",
      shots: State.aim.shots,
      hits: State.aim.hits,
      accuracy: acc,
      score,
      duration_ms: dur,
      profile: true
    });
  }

  // =========================
  // ZOMBIES LAUNCH (uses your existing engine)
  // =========================
  function zombiesSetMode(mode) {
    State.profile.zombies_mode = (mode === "roguelike") ? "roguelike" : "arcade";
    Storage.save();
    toast(`Zombies: ${State.profile.zombies_mode}`);
  }

  function zombiesEnter() {
    // твои zombies.* должны сами создать overlay/канвас через zombies.init.js
    // мы просто дергаем стандартные точки входа если есть
    const z = window.BCO_ZOMBIES || window.BCO_ZOMBIES_CORE || null;

    if (!z) {
      toast("Zombies engine не найден (zombies.* не загрузились)");
      return;
    }

    // режим/карта
    const map = State.profile.zombies_map || "Ashes";
    const mode = State.profile.zombies_mode || "arcade";

    // BEST EFFORT: разные движки — разные методы
    safe(() => z.setMode?.(mode));
    safe(() => z.mode?.(mode));

    // open/start
    const started =
      safe(() => z.enter?.({ map, mode })) ??
      safe(() => z.open?.({ map, mode })) ??
      safe(() => z.start?.({ map, mode })) ??
      safe(() => z.start?.(mode));

    toast("Zombies: старт");
    return started;
  }

  // =========================
  // TELEGRAM BUTTONS (native)
  // =========================
  function updateTGButtons() {
    if (!tg) return;
    safe(() => tg.ready());
    safe(() => tg.expand());

    // back
    safe(() => {
      if (State.currentTab !== "home") tg.BackButton.show();
      else tg.BackButton.hide();
    });

    // main
    safe(() => {
      let text = "💎 Premium";
      if (State.currentTab === "settings") text = "✅ Применить профиль";
      if (State.currentTab === "coach") text = "🎯 План тренировки";
      if (State.currentTab === "vod") text = "🎬 Отправить VOD";
      if (State.currentTab === "game") text = "▶ Start Zombies";
      tg.MainButton.setParams({ is_visible: true, text });
    });
  }

  function wireTGButtonsOnce() {
    if (!tg) return;
    if (window.__BCO_TG_WIRED__) return;
    window.__BCO_TG_WIRED__ = true;

    safe(() => tg.MainButton.onClick(() => {
      if (State.currentTab === "settings") sendToBot({ type: "set_profile", profile: true });
      else if (State.currentTab === "coach") sendToBot({ type: "training_plan", focus: State.profile.focus, profile: true });
      else if (State.currentTab === "vod") {
        const t1 = ($("#vod1")?.value || "").trim();
        const t2 = ($("#vod2")?.value || "").trim();
        const t3 = ($("#vod3")?.value || "").trim();
        const note = ($("#vodNote")?.value || "").trim();
        sendToBot({ type: "vod", times: [t1, t2, t3].filter(Boolean), note, profile: true });
      } else if (State.currentTab === "game") zombiesEnter();
      else sendToBot({ type: "nav", target: "premium", profile: true });
    }));

    safe(() => tg.BackButton.onClick(() => selectTab("home")));
  }

  // =========================
  // HARD ROUTER (THIS FIXES “BUTTONS DEAD”)
  // =========================
  function hardRouteClick(target) {
    const el = target?.closest?.("button, .nav-btn, .seg-btn, .chip, .chat-send, .aim-target");
    if (!el) return false;

    const id = el.id || "";
    const tab = el.dataset?.tab || el.dataset?.value || "";

    //
