// app/webapp/static/app.js
// BCO Mini App — RESTORE BRIDGE (Mini App == bot inside) | UI untouched
(() => {
  "use strict";

  const log = (...a) => { try { console.log("[BCO_APP]", ...a); } catch {} };
  const warn = (...a) => { try { console.warn("[BCO_APP]", ...a); } catch {} };

  function safe(fn) { try { return fn(); } catch (e) { return undefined; } }
  function q(id) { return document.getElementById(id); }

  function setHealth(msg) {
    const el = q("jsHealth");
    if (el) el.textContent = String(msg || "");
  }

  // --------- Chat UI (inside Mini App) ----------
  function addChatLine(role, text) {
    const logEl = q("chatLog");
    if (!logEl) return;

    const item = document.createElement("div");
    item.className = "chat-item " + (role === "user" ? "me" : "bot");

    const bubble = document.createElement("div");
    bubble.className = "chat-bubble";
    bubble.textContent = String(text || "");

    item.appendChild(bubble);
    logEl.appendChild(item);

    // scroll to bottom
    try { logEl.scrollTop = logEl.scrollHeight; } catch {}
  }

  function bindClick(id, fn) {
    const el = q(id);
    if (!el) return;
    el.addEventListener("click", (e) => {
      // НЕ делаем глобальные preventDefault — чтобы не убивать iOS клики
      safe(() => fn(e));
    }, { passive: true });
  }

  // --------- Zombies launcher ----------
  function zombiesStartFullscreen() {
    const rt = window.BCO?.zombies?.runtime || window.BCO_ZOMBIES_RUNTIME || null;
    if (rt && typeof rt.startGame === "function") return !!safe(() => rt.startGame());

    const engine = window.BCO?.engine || window.BCO_ENGINE || null;
    if (engine && typeof engine.start === "function") {
      // читаем текущий UI (active классы)
      const modeBtnR = q("btnZModeRogue2");
      const mode = (modeBtnR && modeBtnR.classList.contains("active")) ? "roguelike" : "arcade";
      let map = "Ashes";
      const seg = q("segZMap");
      if (seg) {
        const b = seg.querySelector(".seg-btn.active");
        if (b) map = b.getAttribute("data-value") || "Ashes";
      }
      const ok = safe(() => engine.start({ mode, map }));
      return (typeof ok === "boolean") ? ok : true;
    }

    warn("Zombies runtime/engine missing");
    return false;
  }

  // --------- Aim Trial (самодостаточный, без бота) ----------
  const AIM = { running: false, hits: 0, misses: 0, timer: 0, duration: 20000 };

  function aimStat() {
    const el = q("aimStat");
    if (!el) return;
    const total = AIM.hits + AIM.misses;
    const acc = total ? Math.round((AIM.hits / total) * 100) : 0;
    el.textContent = `🎯 ${AIM.hits}/${total} • Acc ${acc}%`;
  }

  function aimMoveTarget() {
    const arena = q("aimArena");
    const t = q("aimTarget");
    if (!arena || !t) return;

    const r = arena.getBoundingClientRect();
    const pad = 18;
    const x = pad + Math.random() * Math.max(1, (r.width - pad * 2 - 44));
    const y = pad + Math.random() * Math.max(1, (r.height - pad * 2 - 44));

    t.style.left = `${x}px`;
    t.style.top = `${y}px`;
  }

  function aimStart() {
    if (AIM.running) return;
    AIM.running = true;
    AIM.hits = 0;
    AIM.misses = 0;
    aimStat();
    aimMoveTarget();

    clearTimeout(AIM.timer);
    AIM.timer = setTimeout(() => aimStop(), AIM.duration);
  }

  function aimStop() {
    if (!AIM.running) return;
    AIM.running = false;
    clearTimeout(AIM.timer);
    AIM.timer = 0;
  }

  async function aimSendResult() {
    const bridge = window.BCO?.bridge;
    const total = AIM.hits + AIM.misses;
    const acc = total ? Math.round((AIM.hits / total) * 100) : 0;

    // 1) отправляем на сервер (чтобы Mini App был “ботом внутри”)
    if (bridge && bridge.api) {
      await safe(() => bridge.api("game_result", {
        game: "aim_trial",
        mode: "ARCADE",
        hits: AIM.hits,
        misses: AIM.misses,
        total,
        acc,
        durationMs: AIM.duration
      }));
    }

    // 2) sync в бота (fallback)
    bridge?.sendToBot?.({
      type: "game_result",
      action: "game_result",
      game: "aim_trial",
      mode: "ARCADE",
      hits: AIM.hits,
      misses: AIM.misses,
      total,
      acc,
      durationMs: AIM.duration
    });
  }

  // --------- MAIN ----------
  async function start() {
    setHealth("js: starting…");

    const bridge = window.BCO?.bridge;
    if (!bridge) {
      setHealth("js: ERROR (bridge missing)");
      return;
    }

    // TG ready
    safe(() => bridge.tgReady());

    // ✅ Главное: Mini App <-> Server bridge
    // если серверный мост не отвечает — мы всё равно не ломаем UI, просто пишем в health.
    let bridgeOk = false;
    try {
      const ping = await bridge.api("ping", { t: Date.now() });
      bridgeOk = !!ping?.ok;
    } catch {
      bridgeOk = false;
    }

    setHealth(bridgeOk ? "js: OK (bridge)" : "js: OK (NO BRIDGE, bot-sync only)");

    // --- Buttons -> Server actions (Mini App работает сам), + fallback sendToBot ---
    bindClick("btnOpenBot", async () => {
      // в мини-апп можно показать “меню бота” как текст/карточки через сервер
      const r = await safe(() => bridge.nav("open_bot_menu"));
      if (r?.ok && r?.text) addChatLine("bot", r.text);
      bridge.sendToBot({ type: "nav", nav: "open_bot_menu" });
    });

    bindClick("btnSync", async () => {
      const r = await safe(() => bridge.nav("sync_profile"));
      if (r?.ok && r?.text) addChatLine("bot", r.text);
      bridge.sendToBot({ type: "nav", nav: "sync_profile" });
    });

    bindClick("btnPremium", async () => {
      const r = await safe(() => bridge.nav("premium_hub"));
      if (r?.ok && r?.text) addChatLine("bot", r.text);
      bridge.sendToBot({ type: "nav", nav: "premium_hub" });
    });

    bindClick("btnPlayZombies", () => zombiesStartFullscreen());
    bindClick("btnZEnterGame", () => zombiesStartFullscreen());
    bindClick("btnZQuickPlay", () => zombiesStartFullscreen());

    bindClick("btnZOpenHQ", async () => {
      const r = await safe(() => bridge.nav("zombies_hq"));
      if (r?.ok && r?.text) addChatLine("bot", r.text);
      bridge.sendToBot({ type: "nav", nav: "zombies_hq" });
    });

    bindClick("btnOpenZombies", async () => {
      const r = await safe(() => bridge.nav("zombies_open"));
      if (r?.ok && r?.text) addChatLine("bot", r.text);
      bridge.sendToBot({ type: "nav", nav: "zombies_open" });
    });

    bindClick("btnZPerks", async () => {
      const r = await safe(() => bridge.nav("zombies_perks"));
      if (r?.ok && r?.text) addChatLine("bot", r.text);
      bridge.sendToBot({ type: "nav", nav: "zombies_perks" });
    });

    bindClick("btnZLoadout", async () => {
      const r = await safe(() => bridge.nav("zombies_loadout"));
      if (r?.ok && r?.text) addChatLine("bot", r.text);
      bridge.sendToBot({ type: "nav", nav: "zombies_loadout" });
    });

    bindClick("btnZEggs", async () => {
      const r = await safe(() => bridge.nav("zombies_eggs"));
      if (r?.ok && r?.text) addChatLine("bot", r.text);
      bridge.sendToBot({ type: "nav", nav: "zombies_eggs" });
    });

    bindClick("btnZRound", async () => {
      const r = await safe(() => bridge.nav("zombies_round"));
      if (r?.ok && r?.text) addChatLine("bot", r.text);
      bridge.sendToBot({ type: "nav", nav: "zombies_round" });
    });

    bindClick("btnZTips", async () => {
      const r = await safe(() => bridge.nav("zombies_tips"));
      if (r?.ok && r?.text) addChatLine("bot", r.text);
      bridge.sendToBot({ type: "nav", nav: "zombies_tips" });
    });

    // --- Aim Trial ---
    bindClick("btnAimStart", () => aimStart());
    bindClick("btnAimStop", () => aimStop());
    bindClick("btnAimSend", () => aimSendResult());

    const target = q("aimTarget");
    const arena = q("aimArena");
    if (target) {
      target.addEventListener("click", () => {
        if (!AIM.running) return;
        AIM.hits++;
        aimStat();
        aimMoveTarget();
      }, { passive: true });
    }
    if (arena) {
      arena.addEventListener("click", (e) => {
        if (!AIM.running) return;
        const t = e.target;
        if (t === target || (t && t.closest && t.closest("#aimTarget"))) return;
        AIM.misses++;
        aimStat();
        aimMoveTarget();
      }, { passive: true });
    }
    aimStat();

    // --- Chat внутри Mini App ---
    bindClick("btnChatSend", async () => {
      const inp = q("chatInput");
      const text = inp ? String(inp.value || "").trim() : "";
      if (!text) return;
      if (inp) inp.value = "";

      addChatLine("user", text);

      // 1) основной путь: сервер отвечает текстом -> показываем внутри Mini App
      const r = await safe(() => bridge.chat(text));
      if (r?.ok && r?.text) addChatLine("bot", r.text);
      else addChatLine("bot", "⚠️ Сервер-мост не ответил. Проверь /webapp/api/ping");

      // 2) sync в бота (по желанию)
      bridge.sendToBot({ type: "nav", nav: "chat", text });
    });

    // mark OK
    window.__BCO_JS_OK__ = true;
    log("started", { bridgeOk });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
