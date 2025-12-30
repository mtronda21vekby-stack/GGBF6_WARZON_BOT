(() => {
  const tg = window.Telegram?.WebApp;
  if (tg) {
    tg.expand();
    tg.setHeaderColor?.("#0a0a0f");
    tg.setBackgroundColor?.("#07070b");
  }

  const state = {
    voice: "TEAMMATE",
    game: "Warzone",
    input: "Controller",
    difficulty: "Normal",
  };

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  const toast = $("#toast");
  const pillText = $(".pillText");

  function showToast(text) {
    toast.textContent = text;
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), 1200);
  }

  function setPill(ok, text) {
    pillText.textContent = text;
    const dot = $(".dot");
    dot.style.background = ok ? "var(--good)" : "var(--danger)";
    dot.style.boxShadow = ok
      ? "0 0 18px rgba(0,214,143,.6)"
      : "0 0 18px rgba(255,45,85,.55)";
  }

  // UI bindings
  $$(".segBtn").forEach((btn) => {
    btn.addEventListener("click", () => {
      $$(".segBtn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.voice = btn.dataset.voice || "TEAMMATE";
      showToast(state.voice === "COACH" ? "Коуч включен." : "Тиммейт включен.");
    });
  });

  $$(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const group = chip.dataset.game ? "game" :
                    chip.dataset.input ? "input" :
                    chip.dataset.difficulty ? "difficulty" : null;
      if (!group) return;

      // toggle group
      const selector = group === "game" ? "[data-game]" :
                       group === "input" ? "[data-input]" :
                       "[data-difficulty]";
      $$(selector).forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");

      if (group === "game") state.game = chip.dataset.game;
      if (group === "input") state.input = chip.dataset.input;
      if (group === "difficulty") state.difficulty = chip.dataset.difficulty;
    });
  });

  // Presets
  const situation = $("#situation");
  const presets = {
    angle: "Умираю на углах: переоткрываюсь/меня читают. Нужны правила пика + микро-тренировка.",
    tracking: "Не держу трекинг: теряю цель на страйфе. Нужен план на 15 минут + метрика.",
    rotation: "Ротации: умираю на переходах/меня ловят. Нужен маршрут/тайминги/правила принятия позиций.",
    tilt: "Тильт/хаос: решения ломаются, паника. Нужен протокол стабилизации + правила файта.",
  };

  $$(".card").forEach((card) => {
    card.addEventListener("click", () => {
      const key = card.dataset.preset;
      if (presets[key]) {
        situation.value = presets[key];
        showToast("Заряжено.");
      }
    });
  });

  // Copy
  $("#btnCopy").addEventListener("click", async () => {
    const txt = buildOneLine();
    try {
      await navigator.clipboard.writeText(txt);
      showToast("Скопировано.");
    } catch {
      showToast("Не смог скопировать 😈");
    }
  });

  // Send -> Bot
  $("#btnSend").addEventListener("click", () => {
    const payload = {
      type: "bco_webapp",
      v: 1,
      profile: {
        game: state.game,
        input: state.input,
        difficulty: state.difficulty,
        voice: state.voice,
      },
      text: situation.value || "",
      one_line: buildOneLine(),
      ts: Date.now(),
    };

    if (tg && tg.sendData) {
      tg.sendData(JSON.stringify(payload));
      showToast("Отправлено в BCO.");
      setPill(true, "отправлено в бот");
    } else {
      // fallback если не WebApp окружение
      showToast("Открой через Telegram 😈");
      setPill(false, "открой в Telegram");
    }
  });

  function buildOneLine() {
    const t = (situation.value || "").trim();
    const tail = t ? ` | ${t}` : "";
    return `${state.game} | ${state.input} | ${state.difficulty} | ${state.voice}${tail}`;
  }

  // Init pill
  if (tg?.initDataUnsafe?.user) {
    const u = tg.initDataUnsafe.user;
    setPill(true, `на связи: ${u.first_name || "оператор"}`);
  } else {
    setPill(true, "готов к запуску");
  }
})();
