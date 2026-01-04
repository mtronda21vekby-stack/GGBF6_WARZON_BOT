/* app/webapp/static/app.js */
(() => {
  "use strict";

  // =========================
  // CONFIG (LUX stable)
  // =========================
  const CONFIG = {
    VERSION: "mini-app-2.1.0",
    STORAGE_KEY: "bco_state_v1",
    CHAT_KEY: "bco_chat_v1",
    CHAT_LIMIT: 80,
    AIM_DURATION_MS: 20000,
    MAX_PAYLOAD: 15000,
    TAP_THROTTLE_MS: 80,
    IOS_PREVENT_DOUBLE_TAP_ZOOM_MS: 360,

    // Mini App chat: prefer local web API
    API_TIMEOUT_MS: 12000,
    API_ASK_URL: "/webapp/api/ask",         // DO NOT CHANGE ROUTER
    API_GAME_EVENT_URL: "/webapp/api/game/event", // optional

    // Chat behavior
    CHAT_USE_WEB_API: true,                // primary: answer in Mini App
    CHAT_FALLBACK_TO_BOT: true,            // if api fails -> sendData to bot
    CHAT_LOCAL_ACK: true                   // show local ack lines
  };

  // =========================
  // Utils
  // =========================
  const $ = (q) => document.querySelector(q);
  const $$ = (q) => Array.from(document.querySelectorAll(q));
  const now = () => Date.now();
  const safe = (fn) => { try { return fn(); } catch (_) { return undefined; } };

  const tg = safe(() => window.Telegram && window.Telegram.WebApp) || null;

  function toast(msg, ms = 1400) {
    const el = $("#toast");
    if (!el) return;
    el.textContent = String(msg || "");
    el.classList.add("show");
    setTimeout(() => el.classList.remove("show"), ms);
  }

  function setHealth(text) {
    const el = $("#jsHealth");
    if (el) el.textContent = String(text || "");
  }

  function clampStr(s, n) {
    const x = String(s ?? "");
    return x.length <= n ? x : (x.slice(0, n - 1) + "…");
  }

  function fmtTime(ts) {
    try {
      const d = new Date(ts);
      return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
    } catch {
      return "";
    }
  }

  function escapeHtml(s) {
    const div = document.createElement("div");
    div.textContent = String(s || "");
    return div.innerHTML;
  }

  function safeJSONStringify(obj) {
    try {
      const s = JSON.stringify(obj);
      if (s.length > CONFIG.MAX_PAYLOAD) {
        return JSON.stringify({ truncated: true, keys: Object.keys(obj || {}).slice(0, 60) });
      }
      return s;
    } catch {
      return "{}";
    }
  }

  // =========================
  // State (single source of truth)
  // =========================
  const State = {
    tg,
    buildId: window.__BCO_BUILD__ || "dev",
    currentTab: "home",
    inGame: false,

    lastTapAt: 0,
    lastTouchEndAt: 0,

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
      lastSendAt: 0,
      webApiOk: null, // null/true/false
      lastApiError: ""
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
  // Storage (local + cloud)
  // =========================
  const Storage = {
    async get(key) {
      if (tg?.CloudStorage?.getItem) {
        return await new Promise((resolve) => {
          tg.CloudStorage.getItem(key, (err, value) => resolve(err ? null : (value || null)));
        });
      }
      return safe(() => localStorage.getItem(key)) || null;
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

      const validGame = ["Warzone", "BO7", "BF6"];
      if (!validGame.includes(p.game)) p.game = "Warzone";

      const validFocus = ["aim", "movement", "position"];
      if (!validFocus.includes(p.focus)) p.focus = "aim";
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
    }
  };

  // =========================
  // Profile payload
  // =========================
  function buildProfilePayload() {
    const p = State.profile;
    return {
      game: p.game,
      platform: p.platform,
      input: p.input,
      difficulty: p.mode,
      mode: p.mode,
      voice: p.voice,
      role: p.role,
      bf6_class: p.bf6_class,
      zombies_map: p.zombies_map,
      zombies_mode: p.zombies_mode
    };
  }

  function getInitData() {
    return String(safe(() => tg?.initData) || "").trim();
  }

  // =========================
  // Bridge send (TG sendData)
  // =========================
  function sendToBot(payload) {
    const bridge = window.BCO_BRIDGE || null;
    const base = Object.assign({}, payload || {});
    if (base.profile === true) base.profile = buildProfilePayload();
    if (!base.initData) base.initData = getInitData();

    const raw = safeJSONStringify(base);

    let ok = false;
    if (bridge?.sendData) ok = !!safe(() => bridge.sendData(base));
    else if (tg?.sendData) ok = !!safe(() => (tg.sendData(raw), true));

    if (ok) toast("Отправлено в бота 🚀");
    else toast("sendData недоступен (открой в Telegram)");

    return ok;
  }

  // =========================
  // Web API (NO ROUTER CHANGES)
  // =========================
  async function apiPost(url, body, timeoutMs) {
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), Math.max(250, timeoutMs || CONFIG.API_TIMEOUT_MS));

    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {}),
        signal: ctl.signal,
        cache: "no-store",
        credentials: "same-origin"
      });

      const txt = await res.text();
      let data = null;
      try { data = JSON.parse(txt || "{}"); } catch (_) { data = { raw: txt }; }

      if (!res.ok) {
        const e = new Error(`HTTP ${res.status}`);
        e.data = data; // attach
        throw e;
      }
      return data;
    } finally {
      clearTimeout(t);
    }
  }

  async function apiAsk(text) {
    const payload = {
      text: String(text || "").trim(),
      profile: buildProfilePayload(),
      initData: getInitData(),
      build: State.buildId,
      source: "miniapp"
    };
    const data = await apiPost(CONFIG.API_ASK_URL, payload, CONFIG.API_TIMEOUT_MS);
    return data;
  }

  // =========================
  // UI sync (chips + segments)
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

  function cycleVoice() {
    State.profile.voice = (State.profile.voice === "COACH") ? "TEAMMATE" : "COACH";
  }

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

  function syncZModeButtons() {
    const onArc = (State.profile.zombies_mode !== "roguelike");
    const a1 = $("#btnZModeArcade"); const r1 = $("#btnZModeRogue");
    const a2 = $("#btnZModeArcade2"); const r2 = $("#btnZModeRogue2");
    [a1, a2].forEach((b) => b && b.classList.toggle("active", onArc));
    [r1, r2].forEach((b) => b && b.classList.toggle("active", !onArc));
  }

  // =========================
  // Tabs
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
  // Chat (Mini App local)
  // =========================
  function chatRender() {
    const box = $("#chatLog");
    if (!box) return;

    const h = State.chat.history.slice(-CONFIG.CHAT_LIMIT);
    if (!h.length) {
      box.innerHTML = `
        <div class="chat-row bot">
          <div>
            <div class="bubble">🤝 Пиши сюда — <b>я отвечаю здесь</b>. Если сервер недоступен — тогда fallback в Telegram.</div>
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

  function chatAdd(role, text) {
    const t = String(text || "").trim();
    if (!t) return;
    State.chat.history.push({ role, text: t, ts: now() });
    if (State.chat.history.length > 220) State.chat.history = State.chat.history.slice(-220);
    chatRender();
  }

  async function chatClear() {
    State.chat.history = [];
    await Storage.saveChat();
    chatRender();
    toast("Чат очищен");
  }

  async function chatExportCopy() {
    const txt = State.chat.history.map((m) => `${m.role === "assistant" ? "BCO" : "YOU"}: ${m.text}`).join("\n");
    const out = txt || "—";
    const ok = await safe(() => navigator.clipboard?.writeText(out));
    toast(ok ? "Скопировано 📋" : "Не удалось (iOS ограничение)");
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

    // 1) Prefer web API: reply inside Mini App
    if (CONFIG.CHAT_USE_WEB_API) {
      chatAdd("assistant", "…"); // placeholder
      const phIndex = State.chat.history.length - 1;

      try {
        const data = await apiAsk(text);
        const reply = String(data?.reply || data?.answer || data?.text || "").trim();
        if (!reply) throw new Error("empty_reply");

        // replace placeholder with real reply
        State.chat.history[phIndex] = { role: "assistant", text: reply, ts: now() };
        State.chat.webApiOk = true;
        State.chat.lastApiError = "";
        chatRender();
        await Storage.saveChat();
        return;
      } catch (e) {
        // remove placeholder
        State.chat.history.splice(phIndex, 1);
        State.chat.webApiOk = false;
        State.chat.lastApiError = String(e?.message || e || "api_error");
        chatRender();
        await Storage.saveChat();

        if (!CONFIG.CHAT_FALLBACK_TO_BOT) {
          chatAdd("assistant", "Сервер чата недоступен. Попробуй ещё раз.");
          await Storage.saveChat();
          return;
        }
      }
    }

    // 2) Fallback: send to bot (Telegram chat)
    sendToBot({ type: "chat", text, profile: true });
    if (CONFIG.CHAT_LOCAL_ACK) {
      chatAdd("assistant", "✅ Отправил в бота. Ответ придёт в Telegram-чате.");
      await Storage.saveChat();
    }
  }

  // =========================
  // Aim game
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
    const pad = 14;
    const w = 46;
    const h = 46;

    const maxX = Math.max(pad, ar.width - pad - w);
    const maxY = Math.max(pad, ar.height - pad - h);

    const x = pad + Math.random() * Math.max(0, (maxX - pad));
    const y = pad + Math.random() * Math.max(0, (maxY - pad));

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
  // Zombies entry (engine facade)
  // =========================
  function zombiesSetMode(mode) {
    State.profile.zombies_mode = (mode === "roguelike") ? "roguelike" : "arcade";
    Storage.save();
    syncZModeButtons();
    toast(`Zombies: ${State.profile.zombies_mode}`);
  }

  function enterGameTakeover() {
    if (State.inGame) return;
    State.inGame = true;
    document.documentElement.classList.add("bco-game");
    document.body.classList.add("bco-game");

    safe(() => window.BCO_TG?.hideChrome?.());
    safe(() => tg?.MainButton?.hide?.());
    safe(() => tg?.BackButton?.hide?.());
    safe(() => tg?.setHeaderColor?.("#000000"));
    safe(() => tg?.setBackgroundColor?.("#000000"));

    updateTGButtons();
  }

  function exitGameTakeover() {
    if (!State.inGame) return;
    State.inGame = false;
    document.documentElement.classList.remove("bco-game");
    document.body.classList.remove("bco-game");

    safe(() => window.BCO_TG?.showChrome?.());
    updateTGButtons();
  }

  function zombiesEnter() {
    const engine = window.BCO_ENGINE || null;

    const map = State.profile.zombies_map || "Ashes";
    const mode = State.profile.zombies_mode || "arcade";

    // Always switch tab to Game before entering
    selectTab("game");

    if (!engine?.zombies?.enter) {
      const z = window.BCO_ZOMBIES || window.BCO_ZOMBIES_CORE || null;
      if (!z) {
        toast("Zombies engine не найден (zombies.* не загрузились)");
        return false;
      }
      enterGameTakeover();
      safe(() => z.setMode?.(mode));
      safe(() => z.mode?.(mode));
      safe(() => z.enter?.({ map, mode, onExit: exitGameTakeover }));
      safe(() => z.open?.({ map, mode, onExit: exitGameTakeover }));
      safe(() => z.start?.({ map, mode, onExit: exitGameTakeover }));
      toast("Zombies: старт");
      return true;
    }

    enterGameTakeover();
    safe(() => engine.zombies.setMode?.(mode));
    safe(() => engine.zombies.enter?.({ map, mode, onExit: exitGameTakeover }));
    toast("Zombies: старт");
    return true;
  }

  // =========================
  // Telegram native buttons
  // =========================
  function updateTGButtons() {
    if (!tg) return;

    safe(() => tg.ready());
    safe(() => tg.expand());
    safe(() => window.BCO_TG?.applyInsets?.());

    safe(() => {
      if (State.inGame) return tg.BackButton.hide();
      if (State.currentTab !== "home") tg.BackButton.show();
      else tg.BackButton.hide();
    });

    safe(() => {
      if (State.inGame) return tg.MainButton.hide();
      let text = "💎 Premium";
      if (State.currentTab === "settings") text = "✅ Применить профиль";
      if (State.currentTab === "coach") text = "🎯 План тренировки";
      if (State.currentTab === "vod") text = "🎬 Отправить VOD";
      if (State.currentTab === "game") text = "▶ Start Zombies";
      tg.MainButton.setParams({ is_visible: true, text });
      tg.MainButton.show();
    });
  }

  function wireTGButtonsOnce() {
    if (!tg) return;
    if (window.__BCO_TG_WIRED__) return;
    window.__BCO_TG_WIRED__ = true;

    safe(() => tg.MainButton.onClick(() => {
      if (State.inGame) return;

      if (State.currentTab === "settings") {
        Storage.save();
        sendToBot({ type: "set_profile", profile: true });
        toast("Профиль отправлен ✅");
      } else if (State.currentTab === "coach") {
        sendToBot({ type: "training_plan", focus: State.profile.focus, profile: true });
      } else if (State.currentTab === "vod") {
        const t1 = ($("#vod1")?.value || "").trim();
        const t2 = ($("#vod2")?.value || "").trim();
        const t3 = ($("#vod3")?.value || "").trim();
        const note = ($("#vodNote")?.value || "").trim();
        sendToBot({ type: "vod", times: [t1, t2, t3].filter(Boolean), note, profile: true });
      } else if (State.currentTab === "game") {
        zombiesEnter();
      } else {
        sendToBot({ type: "nav", target: "premium", profile: true });
      }
    }));

    safe(() => tg.BackButton.onClick(() => {
      if (State.inGame) return;
      selectTab("home");
    }));
  }

  // =========================
  // Hard router (iOS dead taps killer)
  // =========================
  function isInteractiveText(el) {
    if (!el) return false;
    const tag = String(el.tagName || "").toLowerCase();
    return tag === "input" || tag === "textarea" || el.isContentEditable;
  }

  function hardRouteClick(target) {
    const el = target?.closest?.("button, .nav-btn, .seg-btn, .chip, .chat-send, .aim-target");
    if (!el) return false;

    const t = now();
    if (t - State.lastTapAt < CONFIG.TAP_THROTTLE_MS) return true;
    State.lastTapAt = t;

    const id = el.id || "";
    const tab = el.dataset?.tab || "";
    const segVal = el.dataset?.value || "";

    // Bottom nav
    if (el.classList.contains("nav-btn") && tab) {
      selectTab(tab);
      return true;
    }

    // Chips
    if (id === "chipVoice") {
      cycleVoice();
      Storage.save();
      syncSegmentsFromState();
      updateChips();
      toast(State.profile.voice === "COACH" ? "Коуч включён" : "Тиммейт включён");
      return true;
    }
    if (id === "chipMode") {
      cycleMode();
      Storage.save();
      syncSegmentsFromState();
      updateChips();
      toast("Mode: " + State.profile.mode);
      return true;
    }
    if (id === "chipPlatform") {
      cyclePlatform();
      Storage.save();
      syncSegmentsFromState();
      updateChips();
      toast("Platform: " + State.profile.platform);
      return true;
    }

    // Segments
    if (el.classList.contains("seg-btn") && segVal) {
      const root = el.closest(".seg");
      const rootId = root?.id || "";

      if (rootId === "segGame") State.profile.game = segVal;
      else if (rootId === "segFocus") State.profile.focus = segVal;
      else if (rootId === "segMode") State.profile.mode = segVal;
      else if (rootId === "segPlatform") State.profile.platform = segVal;
      else if (rootId === "segInput") State.profile.input = segVal;
      else if (rootId === "segVoice") State.profile.voice = segVal;
      else if (rootId === "segZMap") State.profile.zombies_map = segVal;

      Storage.save();
      syncSegmentsFromState();
      updateChips();
      syncZModeButtons();
      return true;
    }

    // Aim clicks
    if (id === "aimTarget") { aimHit(); return true; }

    // Buttons
    switch (id) {
      case "btnShare":
        sendToBot({ type: "nav", target: "share", profile: true });
        return true;

      case "btnClose":
        safe(() => tg?.close?.());
        toast("Закрываю…");
        return true;

      case "btnOpenBot":
        sendToBot({ type: "nav", target: "menu", profile: true });
        return true;

      case "btnSync":
        Storage.save();
        sendToBot({ type: "set_profile", profile: true });
        return true;

      case "btnPremium":
        sendToBot({ type: "nav", target: "premium", profile: true });
        return true;

      case "btnPlayZombies":
      case "btnZQuickPlay":
      case "btnZEnterGame":
        zombiesEnter();
        return true;

      case "btnBuyMonth":
        sendToBot({ type: "nav", target: "premium_month", profile: true });
        return true;

      case "btnBuyLife":
        sendToBot({ type: "nav", target: "premium_lifetime", profile: true });
        return true;

      // Chat
      case "btnChatSend":
        chatSend();
        return true;

      case "btnChatClear":
        chatClear();
        return true;

      case "btnChatExport":
        chatExportCopy();
        return true;

      // Coach
      case "btnSendPlan":
        sendToBot({ type: "training_plan", focus: State.profile.focus, profile: true });
        return true;

      case "btnOpenTraining":
        sendToBot({ type: "nav", target: "training", profile: true });
        return true;

      // VOD
      case "btnSendVod": {
        const t1 = ($("#vod1")?.value || "").trim();
        const t2 = ($("#vod2")?.value || "").trim();
        const t3 = ($("#vod3")?.value || "").trim();
        const note = ($("#vodNote")?.value || "").trim();
        sendToBot({ type: "vod", times: [t1, t2, t3].filter(Boolean), note, profile: true });
        return true;
      }
      case "btnOpenVod":
        sendToBot({ type: "nav", target: "vod", profile: true });
        return true;

      // Settings
      case "btnApplyProfile":
        Storage.save();
        sendToBot({ type: "set_profile", profile: true });
        toast("Профиль сохранён ✅");
        return true;

      case "btnOpenSettings":
        sendToBot({ type: "nav", target: "settings", profile: true });
        return true;

      // Aim
      case "btnAimStart":
        aimStart();
        return true;

      case "btnAimStop":
        aimStop(false);
        return true;

      case "btnAimSend":
        aimSendResult();
        return true;

      // Zombies modes
      case "btnZModeArcade":
      case "btnZModeArcade2":
        zombiesSetMode("arcade");
        return true;

      case "btnZModeRogue":
      case "btnZModeRogue2":
        zombiesSetMode("roguelike");
        return true;

      // Zombies hotkeys
      case "btnZBuyJug":
        sendToBot({ type: "zombies_hotkey", buy: "jug", profile: true });
        return true;

      case "btnZBuySpeed":
        sendToBot({ type: "zombies_hotkey", buy: "speed", profile: true });
        return true;

      case "btnZBuyAmmo":
        sendToBot({ type: "zombies_hotkey", buy: "ammo", profile: true });
        return true;

      // Zombies HQ
      case "btnZOpenHQ":
      case "btnOpenZombies":
        sendToBot({ type: "nav", target: "zombies", profile: true });
        return true;

      case "btnZPerks":
        sendToBot({ type: "zombies", action: "perks", profile: true });
        return true;

      case "btnZLoadout":
        sendToBot({ type: "zombies", action: "loadout", profile: true });
        return true;

      case "btnZEggs":
        sendToBot({ type: "zombies", action: "easter_eggs", profile: true });
        return true;

      case "btnZRound":
        sendToBot({ type: "zombies", action: "round_strategy", profile: true });
        return true;

      case "btnZTips":
        sendToBot({ type: "zombies", action: "quick_tips", profile: true });
        return true;

      // Send launcher result
      case "btnZGameSend":
      case "btnZGameSend2":
        sendToBot({
          action: "game_result",
          game: "zombies",
          mode: State.profile.zombies_mode,
          map: State.profile.zombies_map,
          note: "launcher_send",
          profile: true
        });
        return true;

      default:
        break;
    }

    return false;
  }

  // =========================
  // iOS anti-zoom (keep)
  // =========================
  function wireAntiZoomIOS() {
    document.addEventListener("gesturestart", (e) => {
      try { e.preventDefault(); } catch (_) {}
    }, { passive: false });

    document.addEventListener("touchmove", (e) => {
      if (!State.inGame) return;
      if (e.touches && e.touches.length > 1) {
        try { e.preventDefault(); } catch (_) {}
      }
    }, { passive: false });

    document.addEventListener("touchend", (e) => {
      const t = now();
      const dt = t - (State.lastTouchEndAt || 0);
      State.lastTouchEndAt = t;
      if (!State.inGame) return;
      if (dt > 0 && dt < CONFIG.IOS_PREVENT_DOUBLE_TAP_ZOOM_MS) {
        try { e.preventDefault(); } catch (_) {}
      }
    }, { passive: false });
  }

  // =========================
  // Wire events
  // =========================
  function wireHardRouter() {
    document.addEventListener("pointerdown", (e) => {
      const t = e.target;
      if (isInteractiveText(t)) return;

      if (hardRouteClick(t)) {
        const inScrollable = !!t?.closest?.(".chat-log, .bco-z-card");
        if (!inScrollable) {
          try { e.preventDefault(); } catch (_) {}
        }
      }
    }, { capture: true, passive: false });

    document.addEventListener("click", (e) => {
      const t = e.target;
      if (isInteractiveText(t)) return;
      if (hardRouteClick(t)) {
        try { e.preventDefault(); } catch (_) {}
      }
    }, { capture: true });

    // Aim miss
    const arena = $("#aimArena");
    if (arena) {
      arena.addEventListener("pointerdown", (e) => {
        const tgt = e.target;
        if (tgt && (tgt.id === "aimTarget" || tgt.closest?.("#aimTarget"))) return;
        if (State.aim.running) {
          aimMiss();
          try { e.preventDefault(); } catch (_) {}
        }
      }, { passive: false });
    }
  }

  // =========================
  // Debug info
  // =========================
  function fillDebug() {
    const wa = tg;
    const userId = safe(() => wa?.initDataUnsafe?.user?.id) || "—";
    const chatId = safe(() => wa?.initDataUnsafe?.chat?.id) || "—";
    const theme = safe(() => wa?.colorScheme) || "—";
    const init = (safe(() => wa?.initData) || "").trim();

    const dbgUser = $("#dbgUser");
    const dbgChat = $("#dbgChat");
    const dbgTheme = $("#dbgTheme");
    const dbgInit = $("#dbgInit");

    if (dbgUser) dbgUser.textContent = String(userId);
    if (dbgChat) dbgChat.textContent = String(chatId);
    if (dbgTheme) dbgTheme.textContent = String(theme);
    if (dbgInit) dbgInit.textContent = init ? ("ok • " + clampStr(init, 18)) : "empty";

    const bt = $("#buildTag");
    if (bt) bt.textContent = "build: " + State.buildId;
  }

  // =========================
  // Public hooks for engine
  // =========================
  function exposePublicAPI() {
    window.BCO_APP = window.BCO_APP || {};
    window.BCO_APP.enterGameTakeover = enterGameTakeover;
    window.BCO_APP.exitGameTakeover = exitGameTakeover;
    window.BCO_APP.sendToBot = sendToBot;
    window.BCO_APP.getProfile = () => ({ ...State.profile });
    window.BCO_APP.setTab = (t) => selectTab(t);
    window.BCO_APP.toast = toast;
  }

  // =========================
  // Init
  // =========================
  async function init() {
    setHealth("js: init…");

    if (tg) {
      safe(() => tg.ready());
      safe(() => tg.expand());
      safe(() => window.BCO_TG?.applyInsets?.());
    }

    await Storage.load();
    await Storage.loadChat();

    syncSegmentsFromState();
    syncZModeButtons();
    updateChips();
    chatRender();
    aimUpdateUI();

    wireAntiZoomIOS();
    wireHardRouter();
    wireTGButtonsOnce();
    updateTGButtons();
    fillDebug();
    exposePublicAPI();

    setHealth("js: OK (app) • build=" + State.buildId);

    // micro: detect api availability (non-blocking)
    if (CONFIG.CHAT_USE_WEB_API) {
      // silent ping by asking empty? (we won't call server). Instead set unknown.
      State.chat.webApiOk = State.chat.webApiOk ?? null;
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
