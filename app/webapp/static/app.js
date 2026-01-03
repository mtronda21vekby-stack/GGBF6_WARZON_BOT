// app/webapp/static/app.js
// BCO Mini App — BRIDGE RESTORE (UI untouched)
(() => {
  "use strict";

  const log = (...a) => { try { console.log("[BCO_APP]", ...a); } catch {} };
  const warn = (...a) => { try { console.warn("[BCO_APP]", ...a); } catch {} };
  const err = (...a) => { try { console.error("[BCO_APP]", ...a); } catch {} };

  function safe(fn) { try { return fn(); } catch (_) { return undefined; } }
  function q(id) { return document.getElementById(id); }

  function setHealth(msg) {
    const el = q("jsHealth");
    if (el) el.textContent = String(msg || "");
  }

  // -------------------------
  // Chat UI helpers
  // -------------------------
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

    safe(() => { logEl.scrollTop = logEl.scrollHeight; });
  }

  function toast(msg) {
    const t = q("toast");
    if (!t) return;
    t.textContent = String(msg || "OK");
    t.classList.add("show");
    setTimeout(() => t.classList.remove("show"), 1400);
  }

  // -------------------------
  // Telegram bridge (single source)
  // -------------------------
  function tg() {
    return (window.Telegram && Telegram.WebApp) ? Telegram.WebApp : null;
  }

  function sendToBot(payloadObj) {
    const wa = tg();
    const payload = payloadObj || {};

    // Always attach basic context (non-breaking)
    payload.ts = Date.now();
    payload.source = "miniapp";

    try {
      const raw = JSON.stringify(payload);
      if (wa && typeof wa.sendData === "function") {
        wa.sendData(raw);
        return true;
      }
    } catch (e) {
      err("sendToBot failed", e);
      return false;
    }
    return false;
  }

  // This makes your bot-side router happy by sending BOTH:
  // 1) type:"nav" (your new fix)
  // 2) type:"cmd" fallback (your bot prints "Tip: cmd" now)
  function sendNav(to, extra) {
    const ok1 = sendToBot({ type: "nav", to: String(to || ""), ...(extra || {}) });
    // cmd fallback: bot can ignore if it already handled nav
    const ok2 = sendToBot({ type: "cmd", text: String(to || ""), ...(extra || {}) });
    return ok1 || ok2;
  }

  function sendCmd(text, extra) {
    return sendToBot({ type: "cmd", text: String(text || ""), ...(extra || {}) });
  }

  function sendChat(text, extra) {
    // chat request to bot (your server/bot can answer in Telegram; later we can pull responses back)
    return sendToBot({ type: "chat", text: String(text || ""), ...(extra || {}) });
  }

  function sendGameResult(game, result) {
    return sendToBot({ action: "game_result", game: String(game || ""), result: result || {} });
  }

  // -------------------------
  // Tabs (bottom nav) — restore
  // -------------------------
  function setActiveTab(name) {
    const panes = Array.from(document.querySelectorAll(".tabpane"));
    for (const p of panes) p.classList.toggle("active", p.id === `tab-${name}`);

    const btns = Array.from(document.querySelectorAll(".nav-btn"));
    for (const b of btns) {
      const is = (b.getAttribute("data-tab") === name);
      b.classList.toggle("active", is);
      b.setAttribute("aria-selected", is ? "true" : "false");
    }
  }

  function bindTabs() {
    const nav = document.querySelector("nav.bottom-nav");
    if (!nav) return;

    nav.addEventListener("click", (e) => {
      const b = e.target && e.target.closest ? e.target.closest(".nav-btn") : null;
      if (!b) return;
      const tab = b.getAttribute("data-tab");
      if (!tab) return;
      setActiveTab(tab);
    }, { passive: true });

    nav.addEventListener("touchend", (e) => {
      const b = e.target && e.target.closest ? e.target.closest(".nav-btn") : null;
      if (!b) return;
      const tab = b.getAttribute("data-tab");
      if (!tab) return;
      setActiveTab(tab);
    }, { passive: true });
  }

  // -------------------------
  // Aim Trial (рабочий)
  // -------------------------
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
    const size = 44;
    const x = pad + Math.random() * Math.max(1, (r.width - pad * 2 - size));
    const y = pad + Math.random() * Math.max(1, (r.height - pad * 2 - size));

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
    toast("Aim: START");
  }

  function aimStop() {
    if (!AIM.running) return;
    AIM.running = false;
    clearTimeout(AIM.timer);
    AIM.timer = 0;
    toast("Aim: STOP");
  }

  // -------------------------
  // Zombies launcher (не ломаем твою игру)
  // -------------------------
  function zombiesStartFullscreen() {
    const rt = window.BCO?.zombies?.runtime || window.BCO_ZOMBIES_RUNTIME || null;
    if (rt && typeof rt.startGame === "function") return !!safe(() => rt.startGame());

    const engine = window.BCO?.engine || window.BCO_ENGINE || null;
    if (engine && typeof engine.start === "function") {
      // read mode/map from UI
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

  // -------------------------
  // Input binder (uses your SAFE bco.input)
  // -------------------------
  function bind(id, fn) {
    const input = window.BCO?.input || window.BCO_INPUT || null;
    if (input && typeof input.bindClickById === "function") {
      input.bindClickById(id, fn);
      return;
    }
    // fallback
    const el = q(id);
    if (!el) return;
    el.addEventListener("click", fn, { passive: true });
    el.addEventListener("touchend", fn, { passive: true });
  }

  // -------------------------
  // Main start
  // -------------------------
  function start() {
    setHealth("js: starting…");

    // mount SAFE input (no global intercept)
    const input = window.BCO?.input || window.BCO_INPUT || null;
    if (input && typeof input.mount === "function") safe(() => input.mount());

    // tabs
    bindTabs();
    setActiveTab("home");

    // TG init
    const wa = tg();
    if (wa) {
      safe(() => wa.ready());
      safe(() => wa.expand());
      safe(() => wa.MainButton?.hide?.());
      safe(() => wa.BackButton?.hide?.());
    }

    // ----- Buttons: restore BOT actions -----

    // Home actions
    bind("btnOpenBot", () => {
      addChatLine("bot", "✅ Открываю меню бота…");
      // nav to bot menu (most compatible)
      sendNav("menu");
    });

    bind("btnSync", () => {
      addChatLine("bot", "✅ Синхронизация профиля…");
      sendNav("sync_profile");
      sendCmd("/profile");
    });

    bind("btnPremium", () => {
      addChatLine("bot", "✅ Premium Hub…");
      sendNav("premium");
      sendCmd("/premium");
    });

    bind("btnPlayZombies", () => {
      const ok = zombiesStartFullscreen();
      if (!ok) addChatLine("bot", "❌ Zombies не запустились (engine/runtime missing).");
    });

    // Game tab launcher
    bind("btnZEnterGame", () => {
      const ok = zombiesStartFullscreen();
      if (!ok) addChatLine("bot", "❌ Zombies не запустились (engine/runtime missing).");
    });

    bind("btnZOpenHQ", () => {
      addChatLine("bot", "✅ Zombies HQ…");
      sendNav("zombies_hq");
      sendCmd("/zombies");
    });

    bind("btnZGameSend2", () => {
      addChatLine("bot", "✅ Отправляю результат Zombies…");
      sendGameResult("zombies", { note: "manual_send", ts: Date.now() });
    });

    // Zombies штаб (команды боту)
    bind("btnOpenZombies", () => { sendCmd("/zombies"); addChatLine("bot", "✅ /zombies"); });
    bind("btnZPerks", () => { sendCmd("/zombies perks"); addChatLine("bot", "✅ perks"); });
    bind("btnZLoadout", () => { sendCmd("/zombies loadout"); addChatLine("bot", "✅ loadout"); });
    bind("btnZEggs", () => { sendCmd("/zombies eggs"); addChatLine("bot", "✅ eggs"); });
    bind("btnZRound", () => { sendCmd("/zombies strategy"); addChatLine("bot", "✅ strategy"); });
    bind("btnZTips", () => { sendCmd("/zombies tips"); addChatLine("bot", "✅ tips"); });

    // Chat
    bind("btnChatSend", () => {
      const inp = q("chatInput");
      const text = inp ? String(inp.value || "").trim() : "";
      if (!text) return;
      if (inp) inp.value = "";
      addChatLine("user", text);

      // send chat to bot
      const ok = sendChat(text, { voice: "TEAMMATE" });
      if (ok) addChatLine("bot", "✅ Отправлено боту (ответ придёт в Telegram; next сделаем ответ внутри Mini App).");
      else addChatLine("bot", "❌ Не удалось отправить (WebApp.sendData missing).");
    });

    // Chat tools
    bind("btnChatClear", () => {
      const logEl = q("chatLog");
      if (logEl) logEl.innerHTML = "";
      toast("Chat cleared");
    });

    bind("btnChatExport", () => {
      const logEl = q("chatLog");
      if (!logEl) return;
      const text = Array.from(logEl.querySelectorAll(".chat-bubble")).map(x => x.textContent || "").join("\n");
      safe(() => navigator.clipboard && navigator.clipboard.writeText(text));
      toast("Copied");
    });

    // Aim Trial
    bind("btnAimStart", () => aimStart());
    bind("btnAimStop", () => aimStop());
    bind("btnAimSend", () => {
      const total = AIM.hits + AIM.misses;
      const acc = total ? Math.round((AIM.hits / total) * 100) : 0;
      const result = { hits: AIM.hits, misses: AIM.misses, total, acc, duration: AIM.duration };
      addChatLine("bot", `✅ Aim result → bot: ${AIM.hits}/${total} (${acc}%)`);
      sendGameResult("aim_trial", result);
    });

    const target = q("aimTarget");
    const arena = q("aimArena");

    if (target) {
      const hit = () => {
        if (!AIM.running) return;
        AIM.hits++;
        aimStat();
        aimMoveTarget();
      };
      target.addEventListener("click", hit, { passive: true });
      target.addEventListener("touchend", hit, { passive: true });
    }

    if (arena) {
      const miss = (e) => {
        if (!AIM.running) return;
        const t = e.target;
        if (t === target || (t && t.closest && t.closest("#aimTarget"))) return;
        AIM.misses++;
        aimStat();
        aimMoveTarget();
      };
      arena.addEventListener("click", miss, { passive: true });
      arena.addEventListener("touchend", miss, { passive: true });
    }

    aimStat();

    window.__BCO_JS_OK__ = true;
    setHealth("js: OK (bridge restored)");
    log("Started: bridge restored");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
