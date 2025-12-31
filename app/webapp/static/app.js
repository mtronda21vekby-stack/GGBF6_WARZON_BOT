(() => {
  const tg = window.Telegram?.WebApp;

  const state = {
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

  const qs = (s) => document.querySelector(s);
  const qsa = (s) => Array.from(document.querySelectorAll(s));

  function haptic(type = "impact", style = "medium") {
    try {
      if (!tg?.HapticFeedback) return;
      if (type === "impact") tg.HapticFeedback.impactOccurred(style);
      if (type === "notif") tg.HapticFeedback.notificationOccurred(style); // 'success'|'warning'|'error'
    } catch {}
  }

  function setChipText() {
    const vv = state.voice === "COACH" ? "📚 Коуч" : "🤝 Тиммейт";
    qs("#chipVoice").textContent = vv;

    const mm = state.mode === "Demon" ? "😈 Demon" : (state.mode === "Pro" ? "🔥 Pro" : "🧠 Normal");
    qs("#chipMode").textContent = mm;

    const pp = state.platform === "PlayStation" ? "🎮 PlayStation" : (state.platform === "Xbox" ? "🎮 Xbox" : "🖥 PC");
    qs("#chipPlatform").textContent = pp;

    qs("#pillRole").textContent = `🎭 Role: ${state.role}`;
    qs("#pillBf6").textContent = `🟩 Class: ${state.bf6_class}`;
  }

  function setActiveSeg(rootId, value) {
    const root = qs(rootId);
    if (!root) return;
    root.querySelectorAll(".seg-btn").forEach(b => {
      b.classList.toggle("active", b.dataset.value === value);
    });
  }

  function setTabs() {
    qsa(".tab").forEach(btn => {
      btn.addEventListener("click", () => {
        haptic("impact", "light");
        const tab = btn.dataset.tab;
        qsa(".tab").forEach(b => b.classList.toggle("active", b === btn));
        qsa(".tabpane").forEach(p => p.classList.toggle("active", p.id === `tab-${tab}`));
        try { tg?.MainButton?.hide(); } catch {}
      });
    });
  }

  function wireSeg(rootId, onPick) {
    const root = qs(rootId);
    if (!root) return;
    root.addEventListener("click", (e) => {
      const btn = e.target.closest(".seg-btn");
      if (!btn) return;
      haptic("impact", "light");
      onPick(btn.dataset.value);
      root.querySelectorAll(".seg-btn").forEach(b => b.classList.toggle("active", b === btn));
      setChipText();
    });
  }

  function sendToBot(payload) {
    // payload улетит в бот через web_app_data
    try {
      tg?.sendData(JSON.stringify(payload));
      haptic("notif", "success");
    } catch {
      // fallback — хотя бы показываем
      alert("Не могу отправить данные в бот. Открой мини-апп из Telegram.");
    }
  }

  function initTelegram() {
    if (!tg) return;

    tg.ready();
    tg.expand();

    // Цвета под тему Telegram (чтобы выглядело нативно)
    try {
      tg.setHeaderColor("secondary_bg_color");
      tg.setBackgroundColor("bg_color");
    } catch {}

    // Debug
    qs("#dbgUser").textContent = tg.initDataUnsafe?.user?.id ?? "—";
    qs("#dbgChat").textContent = tg.initDataUnsafe?.chat?.id ?? "—";
    qs("#dbgTheme").textContent = tg.colorScheme ?? "—";
    qs("#dbgInit").textContent = (tg.initData ? "ok" : "empty");
  }

  function openBotMenuHint(text) {
    // Мы не знаем username бота изнутри без конфига,
    // поэтому используем sendData + подсказку боту "что открыть".
    sendToBot({ type: "nav", target: text });
  }

  function wireButtons() {
    qs("#btnClose").addEventListener("click", () => {
      haptic("impact", "medium");
      tg?.close?.();
    });

    qs("#btnClearOneLine").addEventListener("click", () => {
      haptic("impact", "light");
      qs("#inputOneLine").value = "";
    });

    qs("#btnSendOneLine").addEventListener("click", () => {
      const v = (qs("#inputOneLine").value || "").trim();
      if (!v) { haptic("notif", "warning"); return; }
      sendToBot({ type: "one_line", text: v, profile: state });
    });

    qs("#btnOpenBot").addEventListener("click", () => openBotMenuHint("main"));
    qs("#btnPremium").addEventListener("click", () => openBotMenuHint("premium"));
    qs("#btnSync").addEventListener("click", () => sendToBot({ type: "sync_request" }));

    qs("#btnOpenTraining").addEventListener("click", () => openBotMenuHint("training"));
    qs("#btnSendPlan").addEventListener("click", () => {
      sendToBot({ type: "training_plan", focus: state.focus, profile: state });
    });

    qs("#btnOpenVod").addEventListener("click", () => openBotMenuHint("vod"));
    qs("#btnSendVod").addEventListener("click", () => {
      const t1 = (qs("#vod1").value || "").trim();
      const t2 = (qs("#vod2").value || "").trim();
      const t3 = (qs("#vod3").value || "").trim();
      const note = (qs("#vodNote").value || "").trim();
      sendToBot({ type: "vod", times: [t1,t2,t3].filter(Boolean), note, profile: state });
    });

    qs("#btnOpenSettings").addEventListener("click", () => openBotMenuHint("settings"));

    qs("#btnApplyProfile").addEventListener("click", () => {
      sendToBot({ type: "set_profile", profile: state });
    });

    // Zombies shortcuts
    qs("#btnOpenZombies").addEventListener("click", () => sendToBot({ type: "zombies_open", map: state.zombies_map }));
    qs("#btnZPerks").addEventListener("click", () => sendToBot({ type: "zombies", action: "perks", map: state.zombies_map }));
    qs("#btnZLoadout").addEventListener("click", () => sendToBot({ type: "zombies", action: "loadout", map: state.zombies_map }));
    qs("#btnZEggs").addEventListener("click", () => sendToBot({ type: "zombies", action: "eggs", map: state.zombies_map }));
    qs("#btnZRound").addEventListener("click", () => sendToBot({ type: "zombies", action: "rounds", map: state.zombies_map }));
    qs("#btnZTips").addEventListener("click", () => sendToBot({ type: "zombies", action: "tips", map: state.zombies_map }));
  }

  function boot() {
    initTelegram();
    setTabs();

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

    wireButtons();
  }

  boot();
})();
