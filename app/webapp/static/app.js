(() => {
  const tg = window.Telegram?.WebApp;

  const VERSION = "1.0.1";
  const STORAGE_KEY = "bco_state_v1";

  const defaults = {
    game: "Warzone",
    focus: "aim",
    mode: "Normal",
    platform: "PC",
    input: "Controller",
    voice: "TEAMMATE",
    role: "Flex",
    bf6_class: "Assault",
    zombies_map: "Ashes"
  };

  const state = { ...defaults };

  const qs = (s) => document.querySelector(s);
  const qsa = (s) => Array.from(document.querySelectorAll(s));

  function now() { return Date.now(); }

  function safeJsonParse(s) {
    try { return JSON.parse(s); } catch { return null; }
  }

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
    setTimeout(() => t.classList.remove("show"), 1700);
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

    Object.entries(map).forEach(([k, v]) => {
      if (v) root.style.setProperty(k, v);
    });

    const dbgTheme = qs("#dbgTheme");
    if (dbgTheme) dbgTheme.textContent = tg.colorScheme ?? "—";
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

  // ---------- UI helpers ----------
  function setChipText() {
    const vv = state.voice === "COACH" ? "📚 Коуч" : "🤝 Тиммейт";
    const chipVoice = qs("#chipVoice");
    if (chipVoice) chipVoice.textContent = vv;

    const mm = state.mode === "Demon" ? "😈 Demon" : (state.mode === "Pro" ? "🔥 Pro" : "🧠 Normal");
    const chipMode = qs("#chipMode");
    if (chipMode) chipMode.textContent = mm;

    const pp = state.platform === "PlayStation" ? "🎮 PlayStation" : (state.platform === "Xbox" ? "🎮 Xbox" : "🖥 PC");
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
    root.querySelectorAll(".seg-btn").forEach(b => {
      b.classList.toggle("active", b.dataset.value === value);
      b.setAttribute("aria-pressed", b.dataset.value === value ? "true" : "false");
    });
  }

  function setActiveNav(tab) {
    qsa(".nav-btn").forEach(b => {
      const on = b.dataset.tab === tab;
      b.classList.toggle("active", on);
      b.setAttribute("aria-selected", on ? "true" : "false");
    });
  }

  function selectTab(tab) {
    qsa(".tabpane").forEach(p => p.classList.toggle("active", p.id === `tab-${tab}`));
    setActiveNav(tab);
    updateTelegramButtons(tab);

    // лёгкий “premium” эффект: при смене вкладки чуть подскроллить вверх
    try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch {}
  }

  function wireNav() {
    qsa(".nav-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        haptic("impact", "light");
        selectTab(btn.dataset.tab);
      });
    });
  }

  function wireSeg(rootId, onPick) {
    const root = qs(rootId);
    if (!root) return;

    root.addEventListener("click", async (e) => {
      const btn = e.target.closest(".seg-btn");
      if (!btn) return;
      haptic("impact", "light");
      onPick(btn.dataset.value);

      root.querySelectorAll(".seg-btn").forEach(b => b.classList.toggle("active", b === btn));
      setChipText();
      await saveState();
      toast("Сохранено ✅");
    });
  }

  function enrichPayload(payload) {
    const initUnsafe = tg?.initDataUnsafe || {};
    return {
      v: VERSION,
      t: now(),
      meta: {
        user_id: initUnsafe?.user?.id ?? null,
        chat_id: initUnsafe?.chat?.id ?? null,
        platform: tg?.platform ?? null
      },
      ...payload
    };
  }

  function sendToBot(payload) {
    try {
      const pack = enrichPayload(payload);
      const data = JSON.stringify(pack);
      tg?.sendData(data);

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
    sendToBot({ type: "nav", target });
  }

  // ---------- Telegram native buttons ----------
  function updateTelegramButtons(activeTab) {
    if (!tg) return;

    // BackButton
    try {
      if (activeTab !== "home") tg.BackButton.show();
      else tg.BackButton.hide();
    } catch {}

    // MainButton
    try {
      tg.MainButton.setParams({
        is_visible: true,
        text:
          activeTab === "settings" ? "✅ Применить профиль" :
          activeTab === "coach" ? "🎯 План тренировки" :
          activeTab === "vod" ? "🎬 Отправить VOD" :
          activeTab === "zombies" ? "🧟 Открыть Zombies" :
          "💎 Premium"
      });

      tg.MainButton.offClick?.(); // если поддерживается
      tg.MainButton.onClick(() => {
        haptic("impact", "medium");

        if (activeTab === "settings") {
          sendToBot({ type: "set_profile", profile: state });
          return;
        }
        if (activeTab === "coach") {
          sendToBot({ type: "training_plan", focus: state.focus, profile: state });
          return;
        }
        if (activeTab === "vod") {
          const t1 = (qs("#vod1")?.value || "").trim();
          const t2 = (qs("#vod2")?.value || "").trim();
          const t3 = (qs("#vod3")?.value || "").trim();
          const note = (qs("#vodNote")?.value || "").trim();
          sendToBot({ type: "vod", times: [t1, t2, t3].filter(Boolean), note, profile: state });
          return;
        }
        if (activeTab === "zombies") {
          sendToBot({ type: "zombies_open", map: state.zombies_map });
          return;
        }

        openBotMenuHint("premium");
      });
    } catch {}
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

  // ---------- Header chip quick toggles (premium UX) ----------
  async function wireHeaderChips() {
    const chipVoice = qs("#chipVoice");
    const chipMode = qs("#chipMode");
    const chipPlatform = qs("#chipPlatform");

    chipVoice?.addEventListener("click", async () => {
      haptic("impact", "light");
      state.voice = (state.voice === "COACH") ? "TEAMMATE" : "COACH";
      setChipText();
      setActiveSeg("#segVoice", state.voice);
      await saveState();
      toast(state.voice === "COACH" ? "Коуч включён 📚" : "Тиммейт 🤝");
    });

    chipMode?.addEventListener("click", async () => {
      haptic("impact", "light");
      state.mode = (state.mode === "Normal") ? "Pro" : (state.mode === "Pro" ? "Demon" : "Normal");
      setChipText();
      setActiveSeg("#segMode", state.mode);
      await saveState();
      toast(`Режим: ${state.mode}`);
    });

    chipPlatform?.addEventListener("click", async () => {
      haptic("impact", "light");
      state.platform = (state.platform === "PC") ? "PlayStation" : (state.platform === "PlayStation" ? "Xbox" : "PC");
      setChipText();
      setActiveSeg("#segPlatform", state.platform);
      await saveState();
      toast(`Platform: ${state.platform}`);
    });
  }

  // ---------- Wire buttons ----------
  function wireButtons() {
    qs("#btnClose")?.addEventListener("click", () => {
      haptic("impact", "medium");
      tg?.close?.();
    });

    qs("#btnClearOneLine")?.addEventListener("click", () => {
      haptic("impact", "light");
      const el = qs("#inputOneLine");
      if (el) el.value = "";
    });

    qs("#btnSendOneLine")?.addEventListener("click", () => {
      const v = (qs("#inputOneLine")?.value || "").trim();
      if (!v) { haptic("notif", "warning"); toast("Заполни строку"); return; }
      sendToBot({ type: "one_line", text: v, profile: state });
    });

    qs("#btnOpenBot")?.addEventListener("click", () => openBotMenuHint("main"));
    qs("#btnPremium")?.addEventListener("click", () => openBotMenuHint("premium"));
    qs("#btnSync")?.addEventListener("click", () => sendToBot({ type: "sync_request" }));

    qs("#btnOpenTraining")?.addEventListener("click", () => openBotMenuHint("training"));
    qs("#btnSendPlan")?.addEventListener("click", () => sendToBot({ type: "training_plan", focus: state.focus, profile: state }));

    qs("#btnOpenVod")?.addEventListener("click", () => openBotMenuHint("vod"));
    qs("#btnSendVod")?.addEventListener("click", () => {
      const t1 = (qs("#vod1")?.value || "").trim();
      const t2 = (qs("#vod2")?.value || "").trim();
      const t3 = (qs("#vod3")?.value || "").trim();
      const note = (qs("#vodNote")?.value || "").trim();
      sendToBot({ type: "vod", times: [t1, t2, t3].filter(Boolean), note, profile: state });
    });

    // ✅ ВОТ ТУТ БЫЛ ТВОЙ БАГ: "clicks" -> "click"
    qs("#btnOpenSettings")?.addEventListener("click", () => openBotMenuHint("settings"));

    qs("#btnApplyProfile")?.addEventListener("click", () => {
      sendToBot({ type: "set_profile", profile: state });
    });

    // Zombies shortcuts
    qs("#btnOpenZombies")?.addEventListener("click", () => sendToBot({ type: "zombies_open", map: state.zombies_map }));
    qs("#btnZPerks")?.addEventListener("click", () => sendToBot({ type: "zombies", action: "perks", map: state.zombies_map }));
    qs("#btnZLoadout")?.addEventListener("click", () => sendToBot({ type: "zombies", action: "loadout", map: state.zombies_map }));
    qs("#btnZEggs")?.addEventListener("click", () => sendToBot({ type: "zombies", action: "eggs", map: state.zombies_map }));
    qs("#btnZRound")?.addEventListener("click", () => sendToBot({ type: "zombies", action: "rounds", map: state.zombies_map }));
    qs("#btnZTips")?.addEventListener("click", () => sendToBot({ type: "zombies", action: "tips", map: state.zombies_map }));

    // Premium “buy” (пока просто команда в бот)
    qs("#btnBuyMonth")?.addEventListener("click", () => sendToBot({ type: "pay", plan: "premium_month" }));
    qs("#btnBuyLife")?.addEventListener("click", () => sendToBot({ type: "pay", plan: "premium_lifetime" }));

    // Share
    qs("#btnShare")?.addEventListener("click", () => {
      const text =
        "BLACK CROWN OPS 😈\n" +
        "Тренировки, VOD, настройки, Zombies — всё в одном месте.\n" +
        "Открой мини-апп внутри Telegram и стань сильнее.";
      tryShare(text);
    });
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

    tg.ready();
    tg.expand();

    // Theme sync
    applyTelegramTheme();
    try { tg.onEvent("themeChanged", applyTelegramTheme); } catch {}

    // Back button behavior
    try {
      tg.BackButton.onClick(() => {
        haptic("impact", "light");
        selectTab("home");
      });
    } catch {}

    // Debug
    const dbgUser = qs("#dbgUser");
    const dbgChat = qs("#dbgChat");
    const dbgInit = qs("#dbgInit");
    const statOnline = qs("#statOnline");

    if (dbgUser) dbgUser.textContent = tg.initDataUnsafe?.user?.id ?? "—";
    if (dbgChat) dbgChat.textContent = tg.initDataUnsafe?.chat?.id ?? "—";
    if (dbgInit) dbgInit.textContent = (tg.initData ? "ok" : "empty");
    if (statOnline) statOnline.textContent = "ONLINE";
  }

  async function boot() {
    initTelegram();

    const src = await loadState();
    const statSession = qs("#statSession");
    if (statSession) statSession.textContent = src.toUpperCase();

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

    await wireHeaderChips();
    wireButtons();

    selectTab("home");
  }

  boot();
})();
