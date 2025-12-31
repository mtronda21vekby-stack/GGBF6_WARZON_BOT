// app/webapp/static/app.js
(() => {
  // ✅ health indicator for index.html
  window.__BCO_JS_OK__ = true;

  const tg = window.Telegram?.WebApp;

  const VERSION = "1.1.0";
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
    zombies_map: "Ashes",
  };

  const state = { ...defaults };

  // current UI tab (single source of truth)
  let currentTab = "home";

  // mini chat state
  const chat = {
    messages: [], // { id, role: "user"|"assistant"|"system", text, ts }
    typing: false,
  };

  const qs = (s) => document.querySelector(s);
  const qsa = (s) => Array.from(document.querySelectorAll(s));

  function now() {
    return Date.now();
  }

  function uid() {
    return `${Date.now().toString(36)}_${Math.random().toString(16).slice(2)}`;
  }

  function safeJsonParse(s) {
    try {
      return JSON.parse(s);
    } catch {
      return null;
    }
  }

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
  // Причина "по кругу": pointerup + touchend + click = triple fire
  // Делает 1 событие максимум, с блокировкой 350ms.
  // =========================================================
  function onTap(el, handler) {
    if (!el) return;

    let locked = false;
    const lock = () => {
      locked = true;
      setTimeout(() => (locked = false), 350);
    };

    const fire = (e) => {
      if (locked) return;
      lock();
      try {
        handler(e);
      } catch {}
    };

    // prefer Pointer Events
    if (window.PointerEvent) {
      el.addEventListener("pointerup", fire, { passive: true });
      return;
    }

    // fallback
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
      "--tg-secondary-bg": p.secondary_bg_color,
    };

    Object.entries(map).forEach(([k, v]) => {
      if (v) root.style.setProperty(k, v);
    });

    const dbgTheme = qs("#dbgTheme");
    if (dbgTheme) dbgTheme.textContent = tg.colorScheme ?? "—";

    try {
      tg.setBackgroundColor?.(p.bg_color || "#07070b");
    } catch {}
    try {
      tg.setHeaderColor?.(p.secondary_bg_color || p.bg_color || "#07070b");
    } catch {}
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

  function loadChat() {
    const raw = localStorage.getItem(CHAT_KEY);
    const parsed = raw ? safeJsonParse(raw) : null;
    if (parsed && Array.isArray(parsed.messages)) {
      chat.messages = parsed.messages.slice(-60);
    } else {
      chat.messages = [];
    }
  }

  function saveChat() {
    localStorage.setItem(CHAT_KEY, JSON.stringify({ messages: chat.messages.slice(-80) }));
  }

  // ---------- UI helpers ----------
  function setChipText() {
    const vv = state.voice === "COACH" ? "📚 Коуч" : "🤝 Тиммейт";
    const chipVoice = qs("#chipVoice");
    if (chipVoice) chipVoice.textContent = vv;

    const mm = state.mode === "Demon" ? "😈 Demon" : state.mode === "Pro" ? "🔥 Pro" : "🧠 Normal";
    const chipMode = qs("#chipMode");
    if (chipMode) chipMode.textContent = mm;

    const pp =
      state.platform === "PlayStation"
        ? "🎮 PlayStation"
        : state.platform === "Xbox"
        ? "🎮 Xbox"
        : "🖥 PC";
    const chipPlatform = qs("#chipPlatform");
    if (chipPlatform) chipPlatform.textContent = pp;

    const pillRole = qs("#pillRole");
    if (pillRole) pillRole.textContent = `🎭 Role: ${state.role}`;

    const pillBf6 = qs("#pillBf6");
    if (pillBf6) pillBf6.textContent = `🟩 Class: ${state.bf6_class}`;
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

    try {
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch {}
  }

  // ---------- Payload ----------
  function toRouterProfile() {
    // router ждёт difficulty, UI держит mode → маппим
    return {
      game: state.game,
      platform: state.platform,
      input: state.input,
      difficulty: state.mode, // ✅ FIX
      voice: state.voice,
      role: state.role,
      bf6_class: state.bf6_class,
      zombies_map: state.zombies_map,
      mode: state.mode,
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
        build: window.__BCO_BUILD__ || null,
      },
      ...payload,
    };
  }

  function sendToBot(payload) {
    try {
      const fixed = { ...payload };

      // если profile есть → конвертим в router-profile
      if (fixed.profile && typeof fixed.profile === "object") {
        fixed.profile = toRouterProfile();
      }

      const pack = enrichPayload(fixed);
      let data = JSON.stringify(pack);

      // защита от слишком больших payload
      const MAX = 15000;
      if (data.length > MAX) {
        if (typeof pack.text === "string") pack.text = pack.text.slice(0, 4000);
        if (typeof pack.note === "string") pack.note = pack.note.slice(0, 4000);
        data = JSON.stringify(pack).slice(0, MAX);
      }

      if (!tg?.sendData) {
        haptic("notif", "error");
        toast("Открой Mini App внутри Telegram");
        return false;
      }

      tg.sendData(data);

      haptic("notif", "success");
      const statSession = qs("#statSession");
      if (statSession) statSession.textContent = "SENT";
      toast("Отправлено в бота 🚀");
      return true;
    } catch {
      haptic("notif", "error");
      alert("Не могу отправить данные в бот. Открой мини-апп из Telegram.");
      return false;
    }
  }

  function openBotMenuHint(target) {
    // router у тебя не обрабатывает type=open — поэтому делаем nav
    sendToBot({ type: "nav", target, profile: state });
  }

  // =========================================================
  // ✅ MINI APP CHAT (ответы прямо в приложении)
  // POST /webapp/api/ask
  // Заголовок: X-Telegram-Init-Data = tg.initData
  // Body: { text, profile }
  // Response: { reply: "..." } (или { text: "..." })
  // =========================================================
  function chatPush(role, text) {
    chat.messages.push({ id: uid(), role, text: String(text || ""), ts: now() });
    chat.messages = chat.messages.slice(-80);
    saveChat();
    renderChat();
  }

  function setTyping(on) {
    chat.typing = !!on;
    renderChat();
  }

  function renderChat() {
    const box = qs("#chatBox");
    if (!box) return;

    const typing = qs("#chatTyping");
    if (typing) typing.style.display = chat.typing ? "flex" : "none";

    box.innerHTML = "";

    if (!chat.messages.length) {
      const empty = document.createElement("div");
      empty.className = "chat-empty";
      empty.textContent = "Напиши в чат — и я отвечу прямо здесь 😈";
      box.appendChild(empty);
    } else {
      chat.messages.forEach((m) => {
        const row = document.createElement("div");
        row.className = `chat-row ${m.role}`;

        const bubble = document.createElement("div");
        bubble.className = "chat-bubble";
        bubble.textContent = m.text;

        row.appendChild(bubble);
        box.appendChild(row);
      });
    }

    // автоскролл вниз
    try {
      box.scrollTop = box.scrollHeight + 9999;
    } catch {}
  }

  async function askInMiniApp(text) {
    const msg = String(text || "").trim();
    if (!msg) return;

    chatPush("user", msg);
    setTyping(true);

    const initData = tg?.initData || "";
    const body = {
      text: msg,
      profile: toRouterProfile(),
    };

    // если не из Telegram — покажем честно, но всё равно попробуем
    const isTg = !!tg;

    try {
      const res = await fetch("/webapp/api/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Telegram-Init-Data": initData,
          "X-BCO-Version": VERSION,
        },
        body: JSON.stringify(body),
      });

      const ct = (res.headers.get("content-type") || "").toLowerCase();
      const data = ct.includes("application/json") ? await res.json() : { reply: await res.text() };

      const reply = (data && (data.reply || data.text || data.message)) || "";
      if (!res.ok) {
        setTyping(false);

        // fallback: если API недоступен — отправим в бота
        if (isTg) {
          sendToBot({ type: "one_line", text: msg, profile: state });
          chatPush("system", "⚠️ API недоступен — отправил в бота (fallback).");
        } else {
          chatPush("system", "⚠️ API недоступен и Telegram initData пустой. Открой Mini App из Telegram.");
        }
        return;
      }

      setTyping(false);
      chatPush("assistant", reply || "…");
    } catch (e) {
      setTyping(false);
      if (isTg) {
        sendToBot({ type: "one_line", text: msg, profile: state });
        chatPush("system", "⚠️ Ошибка сети — отправил в бота (fallback).");
      } else {
        chatPush("system", "⚠️ Ошибка сети. Открой Mini App из Telegram.");
      }
    }
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
          currentTab === "settings"
            ? "✅ Применить профиль"
            : currentTab === "coach"
            ? "🎯 План тренировки"
            : currentTab === "vod"
            ? "🎬 Отправить VOD"
            : currentTab === "zombies"
            ? "🧟 Открыть Zombies"
            : "💎 Premium",
      });
    } catch {}

    if (tgButtonsWired) return;
    tgButtonsWired = true;

    tgMainHandler = () => {
      haptic("impact", "medium");

      if (currentTab === "settings") {
        sendToBot({ type: "set_profile", profile: state });
        return;
      }
      if (currentTab === "coach") {
        sendToBot({ type: "training_plan", focus: state.focus, profile: state });
        return;
      }
      if (currentTab === "vod") {
        const t1 = (qs("#vod1")?.value || "").trim();
        const t2 = (qs("#vod2")?.value || "").trim();
        const t3 = (qs("#vod3")?.value || "").trim();
        const note = (qs("#vodNote")?.value || "").trim();
        sendToBot({ type: "vod", times: [t1, t2, t3].filter(Boolean), note, profile: state });
        return;
      }
      if (currentTab === "zombies") {
        sendToBot({ type: "zombies_open", map: state.zombies_map, profile: state });
        return;
      }

      openBotMenuHint("premium");
    };

    tgBackHandler = () => {
      haptic("impact", "light");
      selectTab("home");
    };

    try {
      tg.MainButton.offClick?.(tgMainHandler);
      tg.MainButton.onClick(tgMainHandler);
    } catch {
      try {
        tg.MainButton.onClick(tgMainHandler);
      } catch {}
    }

    try {
      tg.BackButton.offClick?.(tgBackHandler);
      tg.BackButton.onClick(tgBackHandler);
    } catch {
      try {
        tg.BackButton.onClick(tgBackHandler);
      } catch {}
    }
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
      root.addEventListener(
        "pointerup",
        (e) => {
          const btn = e.target.closest(".seg-btn");
          if (!btn) return;
          handler(btn);
        },
        { passive: true }
      );
    } else {
      root.addEventListener(
        "click",
        (e) => {
          const btn = e.target.closest(".seg-btn");
          if (!btn) return;
          handler(btn);
        },
        { passive: true }
      );
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
      state.voice = state.voice === "COACH" ? "TEAMMATE" : "COACH";
      setChipText();
      setActiveSeg("#segVoice", state.voice);
      await saveState();
      toast(state.voice === "COACH" ? "Коуч включён 📚" : "Тиммейт 🤝");
    });

    onTap(chipMode, async () => {
      haptic("impact", "light");
      state.mode = state.mode === "Normal" ? "Pro" : state.mode === "Pro" ? "Demon" : "Normal";
      setChipText();
      setActiveSeg("#segMode", state.mode);
      await saveState();
      toast(`Режим: ${state.mode}`);
    });

    onTap(chipPlatform, async () => {
      haptic("impact", "light");
      state.platform = state.platform === "PC" ? "PlayStation" : state.platform === "PlayStation" ? "Xbox" : "PC";
      setChipText();
      setActiveSeg("#segPlatform", state.platform);
      await saveState();
      toast(`Platform: ${state.platform}`);
    });
  }

  // ---------- Wire buttons ----------
  function wireButtons() {
    onTap(qs("#btnClose"), () => {
      haptic("impact", "medium");
      tg?.close?.();
    });

    onTap(qs("#btnClearOneLine"), () => {
      haptic("impact", "light");
      const el = qs("#inputOneLine");
      if (el) el.value = "";
    });

    // ✅ 1-строка в чат Mini App (API), fallback — в бот
    onTap(qs("#btnSendOneLine"), () => {
      const v = (qs("#inputOneLine")?.value || "").trim();
      if (!v) {
        haptic("notif", "warning");
        toast("Заполни строку");
        return;
      }
      askInMiniApp(v);
    });

    // ✅ чат-кнопка
    onTap(qs("#btnChatSend"), () => {
      const v = (qs("#chatInput")?.value || "").trim();
      if (!v) {
        haptic("notif", "warning");
        toast("Напиши текст");
        return;
      }
      const input = qs("#chatInput");
      if (input) input.value = "";
      askInMiniApp(v);
    });

    // enter to send (mobile safe)
    const chatInput = qs("#chatInput");
    if (chatInput) {
      chatInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          qs("#btnChatSend")?.click?.();
        }
      });
    }

    onTap(qs("#btnOpenBot"), () => openBotMenuHint("main"));
    onTap(qs("#btnPremium"), () => openBotMenuHint("premium"));
    onTap(qs("#btnSync"), () => sendToBot({ type: "sync_request", profile: state }));

    onTap(qs("#btnOpenTraining"), () => openBotMenuHint("training"));
    onTap(qs("#btnSendPlan"), () => sendToBot({ type: "training_plan", focus: state.focus, profile: state }));

    onTap(qs("#btnOpenVod"), () => openBotMenuHint("vod"));
    onTap(qs("#btnSendVod"), () => {
      const t1 = (qs("#vod1")?.value || "").trim();
      const t2 = (qs("#vod2")?.value || "").trim();
      const t3 = (qs("#vod3")?.value || "").trim();
      const note = (qs("#vodNote")?.value || "").trim();
      sendToBot({ type: "vod", times: [t1, t2, t3].filter(Boolean), note, profile: state });
    });

    onTap(qs("#btnOpenSettings"), () => openBotMenuHint("settings"));
    onTap(qs("#btnApplyProfile"), () => sendToBot({ type: "set_profile", profile: state }));

    // Zombies shortcuts
    onTap(qs("#btnOpenZombies"), () => sendToBot({ type: "zombies_open", map: state.zombies_map, profile: state }));
    onTap(qs("#btnZPerks"), () => sendToBot({ type: "zombies", action: "perks", map: state.zombies_map, profile: state }));
    onTap(qs("#btnZLoadout"), () => sendToBot({ type: "zombies", action: "loadout", map: state.zombies_map, profile: state }));
    onTap(qs("#btnZEggs"), () => sendToBot({ type: "zombies", action: "eggs", map: state.zombies_map, profile: state }));
    onTap(qs("#btnZRound"), () => sendToBot({ type: "zombies", action: "rounds", map: state.zombies_map, profile: state }));
    onTap(qs("#btnZTips"), () => sendToBot({ type: "zombies", action: "tips", map: state.zombies_map, profile: state }));

    // Premium buy
    onTap(qs("#btnBuyMonth"), () => sendToBot({ type: "pay", plan: "premium_month", profile: state }));
    onTap(qs("#btnBuyLife"), () => sendToBot({ type: "pay", plan: "premium_lifetime", profile: state }));

    // Share
    onTap(qs("#btnShare"), () => {
      const text =
        "BLACK CROWN OPS 😈\n" +
        "Тренировки, VOD, настройки, Zombies — всё в одном месте.\n" +
        "Открой мини-апп внутри Telegram и стань сильнее.";
      tryShare(text);
    });
  }

  // ---------- Build tag ----------
  function ensureBuildTag() {
    const buildFromIndex = window.__BCO_BUILD__ && window.__BCO_BUILD__ !== "__BUILD__" ? window.__BCO_BUILD__ : null;
    const txt = buildFromIndex ? `build ${buildFromIndex} • v${VERSION}` : `v${VERSION}`;

    const buildTag = qs("#buildTag");
    if (buildTag) {
      buildTag.textContent = txt;
      return;
    }

    const footLeft = qs(".foot-left");
    if (footLeft) {
      const span = document.createElement("span");
      span.id = "buildTag";
      span.style.display = "block";
      span.style.marginTop = "8px";
      span.style.opacity = "0.65";
      span.style.fontSize = "12px";
      span.textContent = txt;
      footLeft.appendChild(span);
    }
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

    try {
      tg.ready();
    } catch {}
    try {
      tg.expand();
    } catch {}

    applyTelegramTheme();
    try {
      tg.onEvent("themeChanged", applyTelegramTheme);
    } catch {}

    const dbgUser = qs("#dbgUser");
    const dbgChat = qs("#dbgChat");
    const dbgInit = qs("#dbgInit");
    const statOnline = qs("#statOnline");

    if (dbgUser) dbgUser.textContent = tg.initDataUnsafe?.user?.id ?? "—";
    if (dbgChat) dbgChat.textContent = tg.initDataUnsafe?.chat?.id ?? "—";
    if (dbgInit) dbgInit.textContent = tg.initData ? "ok" : "empty";
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

    loadChat();
    renderChat();

    wireNav();

    // Segments
    wireSeg("#segGame", (v) => {
      state.game = v;
    });
    wireSeg("#segFocus", (v) => {
      state.focus = v;
    });
    wireSeg("#segMode", (v) => {
      state.mode = v;
    });
    wireSeg("#segPlatform", (v) => {
      state.platform = v;
    });
    wireSeg("#segInput", (v) => {
      state.input = v;
    });
    wireSeg("#segVoice", (v) => {
      state.voice = v;
    });
    wireSeg("#segZMap", (v) => {
      state.zombies_map = v;
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

    selectTab("home");

    // subtle greeting in mini chat (only if empty)
    if (!chat.messages.length) {
      chatPush("assistant", "🖤 Я здесь. Пиши — отвечу прямо в Mini App. 😈");
    }
  }

  boot();
})();
