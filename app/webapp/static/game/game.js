(() => {
  const tg = window.Telegram?.WebApp;
  const $ = (id) => document.getElementById(id);

  function safeJsonParse(s) {
    try { return JSON.parse(s); } catch { return null; }
  }

  function setStatus(text, color) {
    const el = $("status");
    if (!el) return;
    el.textContent = text;
    el.style.color = color || "";
  }

  function getProfile() {
    return {
      game: "gamehub",
      platform: $("platform")?.value || "pc",
      input: $("input")?.value || "kbm",
      difficulty: $("difficulty")?.value || "pro",
      voice: $("voice")?.value || "TEAMMATE",
      role: $("role")?.value || "slayer",
    };
  }

  function applyTelegram() {
    if (!tg) {
      setStatus("Открой это внутри Telegram через кнопку WebApp.", "var(--warn)");
      return;
    }

    tg.ready();
    tg.expand();

    // мягкая подстройка под тему TG
    try {
      tg.setHeaderColor?.("secondary_bg_color");
      tg.setBackgroundColor?.("#070A12");
    } catch {}

    const u = tg.initDataUnsafe?.user;
    $("userLine").textContent = u
      ? `Пилот: ${u.first_name || "anon"}${u.username ? " @" + u.username : ""}`
      : "Пилот: anon";

    $("cloudLine").textContent = tg.initData ? "Cloud link: OK" : "Cloud link: limited";
    setStatus("Готов. Выбирай режим.", "var(--ok)");
  }

  function sendToBot(action, extra = {}) {
    if (!tg) return;
    const payload = {
      v: 1,
      action,
      ts: Date.now(),
      profile: getProfile(),
      ...extra,
      initData: tg.initData || null
    };
    tg.sendData(JSON.stringify(payload));
  }

  function boot() {
    applyTelegram();

    $("voice")?.addEventListener("change", () => {
      $("modePillText").textContent = $("voice").value;
    });

    $("btnAim")?.addEventListener("click", () => {
      const qs = new URLSearchParams(getProfile()).toString();
      location.href = `./aim/index.html?${qs}`;
    });

    $("btnZ")?.addEventListener("click", () => {
      const qs = new URLSearchParams(getProfile()).toString();
      location.href = `./zombies/index.html?${qs}`;
    });

    $("btnSave")?.addEventListener("click", () => {
      sendToBot("save_profile");
      setStatus("Профиль отправлен ✅ Закрывай панель — бот подтвердит.", "var(--ok)");
    });

    // таббар: Home / Aim / Zombies
    $("tabHome")?.addEventListener("click", () => location.href = "./index.html");
    $("tabAim")?.addEventListener("click", () => $("btnAim")?.click());
    $("tabZ")?.addEventListener("click", () => $("btnZ")?.click());
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
