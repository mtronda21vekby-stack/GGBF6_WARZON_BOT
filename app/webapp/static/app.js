// app/webapp/static/app.js
// BCO Mini App (RESTORE WORKING) vRESTORE-1
// - НЕ меняет UI/верстку
// - Чинит клики (никаких глобальных click-killer'ов)
// - Возвращает работу всех кнопок + Aim Trial
// - Возвращает sync/sendData в бота (type="nav" + action/cmd совместимость)
// - Zombies запуск: через window.BCO.zombies.runtime если есть, иначе через legacy BCO_ZOMBIES_*
// - Контракт: никаких “новых стеков” тут

(() => {
  "use strict";

  const log = (...a) => { try { console.log("[BCO_APP]", ...a); } catch {} };
  const warn = (...a) => { try { console.warn("[BCO_APP]", ...a); } catch {} };

  const TG = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;

  // -------------------------
  // Config / storage
  // -------------------------
  const CONFIG = {
    STORAGE_KEY: "bco_state_v1",
    CHAT_KEY: "bco_chat_v1",
    CHAT_HISTORY_LIMIT: 80,
    AIM_DURATION: 20000,
    MAX_PAYLOAD_SIZE: 15000
  };

  function safe(fn) { try { return fn(); } catch (_) { return undefined; } }
  function q(id) { return document.getElementById(id); }
  function qs(sel) { return document.querySelector(sel); }

  function setHealth(msg) {
    const el = q("jsHealth");
    if (el) el.textContent = String(msg || "");
  }

  function toast(msg, ms = 1600) {
    const el = q("toast");
    if (!el) return;
    el.textContent = String(msg || "OK");
    el.classList.add("show");
    setTimeout(() => el.classList.remove("show"), ms);
  }

  function loadJSON(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return fallback;
      return JSON.parse(raw);
    } catch {
      return fallback;
    }
  }

  function saveJSON(key, obj) {
    try { localStorage.setItem(key, JSON.stringify(obj)); } catch {}
  }

  // -------------------------
  // State
  // -------------------------
  const state = loadJSON(CONFIG.STORAGE_KEY, {
    voice: "TEAMMATE",     // TEAMMATE | COACH
    mode: "Normal",        // Normal | Pro | Demon
    platform: "PC",        // PC | PlayStation | Xbox
    input: "Controller",   // KBM | Controller
    game: "Warzone",       // Warzone | BO7 | BF6
    role: "Flex",
    bf6_class: "Assault",
    z_mode: "ARCADE",      // ARCADE | ROGUELIKE
    z_map: "Ashes"         // Ashes | Astra
  });

  // -------------------------
  // Telegram helpers
  // -------------------------
  function tgReady() {
    if (!TG) return;
    safe(() => TG.ready());
    safe(() => TG.expand());
    safe(() => TG.MainButton?.hide?.());
    safe(() => TG.BackButton?.hide?.());
  }

  function getInitDataUnsafe() {
    if (!TG) return "";
    return String(TG.initData || TG.initDataUnsafe || "");
  }

  function sendData(payloadObj) {
    if (!TG || !TG.sendData) {
      warn("TG not available; sendData skipped", payloadObj);
      return false;
    }
    try {
      const payload = JSON.stringify(payloadObj || {});
      if (payload.length > CONFIG.MAX_PAYLOAD_SIZE) {
        warn("payload too big", payload.length);
        toast("payload too big");
        return false;
      }
      TG.sendData(payload);
      return true;
    } catch (e) {
      warn("sendData error", e);
      return false;
    }
  }

  // Универсальный пакет: и nav и cmd одновременно (совместимость, чтобы бот точно отработал)
  function sendToBot({ type, action, cmd, data } = {}) {
    const pack = {
      // primary routing
      type: type || "nav",

      // compatibility fields (на случай разных версий роутера в боте)
      action: action || null,
      cmd: cmd || null,

      // useful context
      ts: Date.now(),
      profile: {
        voice: state.voice,
        mode: state.mode,
        platform: state.platform,
        input: state.input,
        game: state.game,
        role: state.role,
        bf6_class: state.bf6_class
      },

      data: data || {}
    };

    // also include "nav" field for older parsers
    if (pack.type === "nav" && pack.action) pack.nav = pack.action;

    const ok = sendData(pack);
    if (ok) toast("sent → bot");
    return ok;
  }

  // -------------------------
  // UI render helpers (no redesign)
  // -------------------------
  function updateTopChips() {
    const chipVoice = q("chipVoice");
    const chipMode = q("chipMode");
    const chipPlatform = q("chipPlatform");
    const chatSub = q("chatSub");

    if (chipVoice) chipVoice.textContent = (state.voice === "COACH") ? "📚 Коуч" : "🤝 Тиммейт";
    if (chipMode) chipMode.textContent = `🧠 ${state.mode}`;
    if (chipPlatform) chipPlatform.textContent = (state.platform === "PC") ? "🖥 PC" : (state.platform === "Xbox" ? "🎮 Xbox" : "🎮 PS");

    if (chatSub) chatSub.textContent = `${state.voice} • ${state.mode} • ${state.platform}`;
  }

  function setSegActive(segEl, value) {
    if (!segEl) return;
    const btns = Array.from(segEl.querySelectorAll(".seg-btn"));
    for (const b of btns) b.classList.toggle("active", (b.getAttribute("data-value") || "") === value);
  }

  function setTab(tabName) {
    const panes = Array.from(document.querySelectorAll(".tabpane"));
    for (const p of panes) p.classList.toggle("active", p.id === `tab-${tabName}`);

    const navBtns = Array.from(document.querySelectorAll(".bottom-nav .nav-btn"));
    for (const b of navBtns) {
      const on = (b.getAttribute("data-tab") === tabName);
      b.classList.toggle("active", on);
      b.setAttribute("aria-selected", on ? "true" : "false");
    }
  }

  // -------------------------
  // Chat (simple local + send to bot)
  // -------------------------
  const chat = loadJSON(CONFIG.CHAT_KEY, { items: [] });

  function pushChatItem(role, text) {
    chat.items.push({ role, text: String(text || ""), ts: Date.now() });
    if (chat.items.length > CONFIG.CHAT_HISTORY_LIMIT) chat.items.splice(0, chat.items.length - CONFIG.CHAT_HISTORY_LIMIT);
    saveJSON(CONFIG.CHAT_KEY, chat);
    renderChat();
  }

  function renderChat() {
    const logEl = q("chatLog");
    if (!logEl) return;
    logEl.innerHTML = "";
    for (const it of (chat.items || [])) {
      const div = document.createElement("div");
      div.className = "chat-msg " + (it.role === "me" ? "me" : "bot");
      div.textContent = it.text;
      logEl.appendChild(div);
    }
    try { logEl.scrollTop = logEl.scrollHeight; } catch {}
  }

  // -------------------------
  // Aim Trial
  // -------------------------
  const aim = {
    running: false,
    t0: 0,
    hits: 0,
    miss: 0,
    timer: 0
  };

  function aimUpdateStat() {
    const total = aim.hits + aim.miss;
    const acc = total ? Math.round((aim.hits / total) * 100) : 0;
    const el = q("aimStat");
    if (el) el.textContent = `🎯 ${aim.hits}/${total} • Acc ${acc}%`;
  }

  function aimPlaceTarget() {
    const arena = q("aimArena");
    const target = q("aimTarget");
    if (!arena || !target) return;

    const r = arena.getBoundingClientRect();
    const pad = 22;
    const maxX = Math.max(pad, r.width - pad);
    const maxY = Math.max(pad, r.height - pad);

    const x = pad + Math.random() * (maxX - pad);
    const y = pad + Math.random() * (maxY - pad);

    target.style.left = `${x}px`;
    target.style.top = `${y}px`;
  }

  function aimStart() {
    if (aim.running) return;
    aim.running = true;
    aim.hits = 0;
    aim.miss = 0;
    aim.t0 = Date.now();
    aimUpdateStat();
    aimPlaceTarget();
    toast("Aim: GO");

    if (aim.timer) clearTimeout(aim.timer);
    aim.timer = setTimeout(aimStop, CONFIG.AIM_DURATION);
  }

  function aimStop() {
    if (!aim.running) return;
    aim.running = false;
    if (aim.timer) clearTimeout(aim.timer);
    aim.timer = 0;
    toast("Aim: STOP");
  }

  function aimSend() {
    const total = aim.hits + aim.miss;
    const acc = total ? (aim.hits / total) : 0;
    const payload = {
      action: "game_result",
      game: "aim_trial",
      mode: "ARCADE",
      hits: aim.hits,
      miss: aim.miss,
      shots: total,
      acc: Number(acc.toFixed(4)),
      duration: Math.min(CONFIG.AIM_DURATION, Math.max(0, Date.now() - aim.t0))
    };
    sendToBot({ type: "nav", action: "game_result", cmd: "game_result", data: payload });
  }

  // -------------------------
  // Zombies launcher (start + send result + quick shop hotkeys)
  // -------------------------
  function zSetMode(m) {
    state.z_mode = (String(m).toUpperCase().includes("ROGUE")) ? "ROGUELIKE" : "ARCADE";
    saveJSON(CONFIG.STORAGE_KEY, state);

    const a1 = q("btnZModeArcade");
    const r1 = q("btnZModeRogue");
    const a2 = q("btnZModeArcade2");
    const r2 = q("btnZModeRogue2");
    if (a1) a1.classList.toggle("active", state.z_mode === "ARCADE");
    if (r1) r1.classList.toggle("active", state.z_mode === "ROGUELIKE");
    if (a2) a2.classList.toggle("active", state.z_mode === "ARCADE");
    if (r2) r2.classList.toggle("active", state.z_mode === "ROGUELIKE");

    // also inform runtime if exists
    safe(() => window.BCO?.zombies?.runtime?.setMode?.(state.z_mode));
  }

  function zSetMap(mp) {
    state.z_map = (String(mp) === "Astra") ? "Astra" : "Ashes";
    saveJSON(CONFIG.STORAGE_KEY, state);

    const seg = q("segZMap");
    if (seg) {
      const btns = Array.from(seg.querySelectorAll(".seg-btn"));
      for (const b of btns) b.classList.toggle("active", (b.getAttribute("data-value") || "") === state.z_map);
    }

    safe(() => window.BCO?.zombies?.runtime?.setMap?.(state.z_map));
  }

  function zStartFullscreen() {
    // switch to tab-game to keep UX consistent
    setTab("game");

    // prefer runtime (new) if present
    const rt = window.BCO?.zombies?.runtime;
    if (rt && typeof rt.startGame === "function") {
      const ok = safe(() => rt.startGame());
      if (ok) return true;
    }

    // fallback: legacy init/game api
    // 1) if you have BCO_ZOMBIES_INIT.startGame
    if (window.BCO_ZOMBIES_INIT && typeof window.BCO_ZOMBIES_INIT.startGame === "function") {
      const ok = safe(() => window.BCO_ZOMBIES_INIT.startGame({
        mode: (state.z_mode === "ROGUELIKE") ? "roguelike" : "arcade",
        map: state.z_map
      }));
      if (ok) return true;
    }

    // 2) if you have BCO_ZOMBIES_CORE.start + BCO_ZOMBIES_GAME runner
    if (window.BCO_ZOMBIES_CORE && typeof window.BCO_ZOMBIES_CORE.start === "function") {
      const core = window.BCO_ZOMBIES_CORE;
      const tms = (performance && performance.now) ? performance.now() : Date.now();
      safe(() => core.start((state.z_mode === "ROGUELIKE") ? "roguelike" : "arcade", window.innerWidth, window.innerHeight, { map: state.z_map }, tms));
      if (window.BCO_ZOMBIES_GAME && typeof window.BCO_ZOMBIES_GAME.startLoop === "function") {
        safe(() => window.BCO_ZOMBIES_GAME.setInGame?.(true));
        safe(() => window.BCO_ZOMBIES_GAME.startLoop());
        return true;
      }
    }

    toast("Zombies: engine missing");
    warn("Zombies start failed: no runtime/init/core+game");
    return false;
  }

  function zSendResult() {
    const snap = safe(() => window.BCO_ZOMBIES_GAME?.getSnapshot?.()) || safe(() => window.BCO_ZOMBIES_CORE?.getFrameData?.()) || null;
    const payload = {
      action: "game_result",
      game: "zombies",
      mode: snap?.meta?.mode || ((state.z_mode === "ROGUELIKE") ? "roguelike" : "arcade"),
      map: snap?.meta?.map || state.z_map,
      wave: snap?.hud?.wave || 1,
      kills: snap?.hud?.kills || 0,
      coins: snap?.hud?.coins || 0,
      duration: snap?.hud?.timeMs || 0,
      relics: snap?.hud?.relics || 0,
      wonderUnlocked: !!snap?.hud?.wonderUnlocked
    };
    sendToBot({ type: "nav", action: "game_result", cmd: "game_result", data: payload });
  }

  function zQuickBuy(perkId) {
    // passthrough if core supports
    const core = window.BCO_ZOMBIES_CORE;
    if (core && typeof core.buyPerk === "function") {
      const ok = safe(() => core.buyPerk(perkId));
      toast(ok ? "perk bought" : "no coins");
      return !!ok;
    }
    // still send to bot as cmd (if your bot handles it)
    sendToBot({ type: "cmd", action: "zombies_buy", cmd: "zombies_buy", data: { perk: perkId } });
    return true;
  }

  // -------------------------
  // Buttons binding (ALL)
  // -------------------------
  function bindAll() {
    // bottom tabs
    document.querySelectorAll(".bottom-nav .nav-btn").forEach((b) => {
      b.addEventListener("click", () => {
        const tab = b.getAttribute("data-tab");
        if (tab) setTab(tab);
      }, { passive: true });
    });

    // Top chips
    q("chipVoice")?.addEventListener("click", () => {
      state.voice = (state.voice === "COACH") ? "TEAMMATE" : "COACH";
      saveJSON(CONFIG.STORAGE_KEY, state);
      updateTopChips();
      toast(state.voice);
    }, { passive: true });

    q("chipMode")?.addEventListener("click", () => {
      const order = ["Normal", "Pro", "Demon"];
      const i = Math.max(0, order.indexOf(state.mode));
      state.mode = order[(i + 1) % order.length];
      saveJSON(CONFIG.STORAGE_KEY, state);
      updateTopChips();
      toast(state.mode);
    }, { passive: true });

    q("chipPlatform")?.addEventListener("click", () => {
      const order = ["PC", "PlayStation", "Xbox"];
      const i = Math.max(0, order.indexOf(state.platform));
      state.platform = order[(i + 1) % order.length];
      saveJSON(CONFIG.STORAGE_KEY, state);
      updateTopChips();
      toast(state.platform);
    }, { passive: true });

    // Quick actions
    q("btnClose")?.addEventListener("click", () => safe(() => TG?.close?.()), { passive: true });
    q("btnShare")?.addEventListener("click", () => {
      safe(() => TG?.showPopup?.({ title: "BLACK CROWN OPS", message: "Mini App активен ✅", buttons: [{ type: "ok" }] }));
    }, { passive: true });

    q("btnOpenBot")?.addEventListener("click", () => {
      // главное: type=nav (как ты и фиксировал)
      sendToBot({ type: "nav", action: "open_bot_menu", cmd: "open_bot_menu", data: { screen: "main" } });
    }, { passive: true });

    q("btnPremium")?.addEventListener("click", () => {
      sendToBot({ type: "nav", action: "premium", cmd: "premium", data: { plan: "hub" } });
    }, { passive: true });

    q("btnBuyMonth")?.addEventListener("click", () => {
      sendToBot({ type: "cmd", action: "buy_premium", cmd: "buy_premium", data: { plan: "month" } });
    }, { passive: true });

    q("btnBuyLife")?.addEventListener("click", () => {
      sendToBot({ type: "cmd", action: "buy_premium", cmd: "buy_premium", data: { plan: "lifetime" } });
    }, { passive: true });

    q("btnSync")?.addEventListener("click", () => {
      sendToBot({ type: "cmd", action: "sync_profile", cmd: "sync_profile", data: {} });
      toast("sync → bot");
    }, { passive: true });

    // Seg: Game
    q("segGame")?.addEventListener("click", (e) => {
      const b = e.target && e.target.closest ? e.target.closest(".seg-btn") : null;
      if (!b) return;
      const v = b.getAttribute("data-value") || "Warzone";
      state.game = v;
      saveJSON(CONFIG.STORAGE_KEY, state);
      setSegActive(q("segGame"), v);
      toast(v);
    }, { passive: true });

    // Coach mode seg
    q("segMode")?.addEventListener("click", (e) => {
      const b = e.target && e.target.closest ? e.target.closest(".seg-btn") : null;
      if (!b) return;
      state.mode = b.getAttribute("data-value") || "Normal";
      saveJSON(CONFIG.STORAGE_KEY, state);
      setSegActive(q("segMode"), state.mode);
      updateTopChips();
      toast(state.mode);
    }, { passive: true });

    // Focus seg
    q("segFocus")?.addEventListener("click", (e) => {
      const b = e.target && e.target.closest ? e.target.closest(".seg-btn") : null;
      if (!b) return;
      const focus = b.getAttribute("data-value") || "aim";
      setSegActive(q("segFocus"), focus);
      toast("focus: " + focus);
    }, { passive: true });

    // Platform/Input/Voice segs in settings
    q("segPlatform")?.addEventListener("click", (e) => {
      const b = e.target && e.target.closest ? e.target.closest(".seg-btn") : null;
      if (!b) return;
      state.platform = b.getAttribute("data-value") || "PC";
      saveJSON(CONFIG.STORAGE_KEY, state);
      setSegActive(q("segPlatform"), state.platform);
      updateTopChips();
    }, { passive: true });

    q("segInput")?.addEventListener("click", (e) => {
      const b = e.target && e.target.closest ? e.target.closest(".seg-btn") : null;
      if (!b) return;
      state.input = b.getAttribute("data-value") || "Controller";
      saveJSON(CONFIG.STORAGE_KEY, state);
      setSegActive(q("segInput"), state.input);
      toast(state.input);
    }, { passive: true });

    q("segVoice")?.addEventListener("click", (e) => {
      const b = e.target && e.target.closest ? e.target.closest(".seg-btn") : null;
      if (!b) return;
      state.voice = b.getAttribute("data-value") || "TEAMMATE";
      saveJSON(CONFIG.STORAGE_KEY, state);
      setSegActive(q("segVoice"), state.voice);
      updateTopChips();
      toast(state.voice);
    }, { passive: true });

    q("btnApplyProfile")?.addEventListener("click", () => {
      saveJSON(CONFIG.STORAGE_KEY, state);
      updateTopChips();
      sendToBot({ type: "cmd", action: "set_profile", cmd: "set_profile", data: { profile: state } });
      toast("profile saved");
    }, { passive: true });

    // Plan / VOD actions
    q("btnSendPlan")?.addEventListener("click", () => {
      const focusBtn = q("segFocus")?.querySelector(".seg-btn.active");
      const focus = focusBtn ? (focusBtn.getAttribute("data-value") || "aim") : "aim";
      sendToBot({ type: "cmd", action: "coach_plan", cmd: "coach_plan", data: { focus } });
    }, { passive: true });

    q("btnOpenTraining")?.addEventListener("click", () => {
      sendToBot({ type: "nav", action: "open_training", cmd: "open_training", data: {} });
    }, { passive: true });

    q("btnSendVod")?.addEventListener("click", () => {
      const vod1 = (q("vod1")?.value || "").trim();
      const vod2 = (q("vod2")?.value || "").trim();
      const vod3 = (q("vod3")?.value || "").trim();
      const note = (q("vodNote")?.value || "").trim();
      sendToBot({ type: "cmd", action: "vod", cmd: "vod", data: { vod1, vod2, vod3, note } });
    }, { passive: true });

    q("btnOpenVod")?.addEventListener("click", () => {
      sendToBot({ type: "nav", action: "open_vod", cmd: "open_vod", data: {} });
    }, { passive: true });

    // Chat buttons
    q("btnChatSend")?.addEventListener("click", () => {
      const txt = (q("chatInput")?.value || "").trim();
      if (!txt) return;
      q("chatInput").value = "";
      pushChatItem("me", txt);
      // send to bot (so it replies in chat via your existing pipeline)
      sendToBot({ type: "cmd", action: "chat", cmd: "chat", data: { text: txt } });
    }, { passive: true });

    q("btnChatClear")?.addEventListener("click", () => {
      chat.items = [];
      saveJSON(CONFIG.CHAT_KEY, chat);
      renderChat();
      toast("cleared");
    }, { passive: true });

    q("btnChatExport")?.addEventListener("click", () => {
      const text = (chat.items || []).map(x => `${x.role}: ${x.text}`).join("\n");
      safe(() => navigator.clipboard?.writeText?.(text));
      toast("copied");
    }, { passive: true });

    // Aim Trial buttons
    q("btnAimStart")?.addEventListener("click", aimStart, { passive: true });
    q("btnAimStop")?.addEventListener("click", aimStop, { passive: true });
    q("btnAimSend")?.addEventListener("click", aimSend, { passive: true });

    q("aimTarget")?.addEventListener("click", () => {
      if (!aim.running) return;
      aim.hits++;
      aimUpdateStat();
      aimPlaceTarget();
    }, { passive: true });

    q("aimArena")?.addEventListener("click", (e) => {
      if (!aim.running) return;
      // miss if arena clicked but not the target
      const t = e.target;
      if (t && t.id === "aimTarget") return;
      aim.miss++;
      aimUpdateStat();
    }, { passive: true });

    // Zombies mode buttons
    q("btnZModeArcade")?.addEventListener("click", () => zSetMode("ARCADE"), { passive: true });
    q("btnZModeRogue")?.addEventListener("click", () => zSetMode("ROGUELIKE"), { passive: true });
    q("btnZModeArcade2")?.addEventListener("click", () => zSetMode("ARCADE"), { passive: true });
    q("btnZModeRogue2")?.addEventListener("click", () => zSetMode("ROGUELIKE"), { passive: true });

    // Zombies map seg
    q("segZMap")?.addEventListener("click", (e) => {
      const b = e.target && e.target.closest ? e.target.closest(".seg-btn") : null;
      if (!b) return;
      zSetMap(b.getAttribute("data-value"));
    }, { passive: true });

    // Zombies enter buttons
    q("btnZEnterGame")?.addEventListener("click", zStartFullscreen, { passive: true });
    q("btnZQuickPlay")?.addEventListener("click", zStartFullscreen, { passive: true });
    q("btnPlayZombies")?.addEventListener("click", zStartFullscreen, { passive: true });

    // Zombies send results
    q("btnZGameSend")?.addEventListener("click", zSendResult, { passive: true });
    q("btnZGameSend2")?.addEventListener("click", zSendResult, { passive: true });

    // Zombies HQ / bot commands
    q("btnZOpenHQ")?.addEventListener("click", () => sendToBot({ type: "nav", action: "zombies_hq", cmd: "zombies_hq", data: {} }), { passive: true });
    q("btnOpenZombies")?.addEventListener("click", () => sendToBot({ type: "nav", action: "open_zombies", cmd: "open_zombies", data: {} }), { passive: true });
    q("btnZPerks")?.addEventListener("click", () => sendToBot({ type: "nav", action: "zombies_perks", cmd: "zombies_perks", data: {} }), { passive: true });
    q("btnZLoadout")?.addEventListener("click", () => sendToBot({ type: "nav", action: "zombies_loadout", cmd: "zombies_loadout", data: {} }), { passive: true });
    q("btnZEggs")?.addEventListener("click", () => sendToBot({ type: "nav", action: "zombies_eggs", cmd: "zombies_eggs", data: {} }), { passive: true });
    q("btnZRound")?.addEventListener("click", () => sendToBot({ type: "nav", action: "zombies_round", cmd: "zombies_round", data: {} }), { passive: true });
    q("btnZTips")?.addEventListener("click", () => sendToBot({ type: "nav", action: "zombies_tips", cmd: "zombies_tips", data: {} }), { passive: true });

    // Quick shop hotkeys (optional passthrough)
    q("btnZBuyJug")?.addEventListener("click", () => zQuickBuy("jug"), { passive: true });
    q("btnZBuySpeed")?.addEventListener("click", () => zQuickBuy("speed"), { passive: true });
    q("btnZBuyAmmo")?.addEventListener("click", () => zQuickBuy("ammo"), { passive: true });
  }

  // -------------------------
  // Diagnostics render
  // -------------------------
  function renderDiagnostics() {
    q("buildTag") && (q("buildTag").textContent = "build: " + String(window.__BCO_BUILD__ || "dev"));
    q("dbgInit") && (q("dbgInit").textContent = (TG && TG.initData) ? "ok" : "empty");
    q("dbgTheme") && (q("dbgTheme").textContent = (TG && TG.colorScheme) ? TG.colorScheme : "—");
    q("dbgUser") && (q("dbgUser").textContent = (TG && TG.initDataUnsafe && TG.initDataUnsafe.user && TG.initDataUnsafe.user.id) ? String(TG.initDataUnsafe.user.id) : "—");
    q("dbgChat") && (q("dbgChat").textContent = (TG && TG.initDataUnsafe && TG.initDataUnsafe.chat && TG.initDataUnsafe.chat.id) ? String(TG.initDataUnsafe.chat.id) : "—");
  }

  // -------------------------
  // Init
  // -------------------------
  function init() {
    tgReady();

    // restore UI state
    updateTopChips();
    setSegActive(q("segPlatform"), state.platform);
    setSegActive(q("segInput"), state.input);
    setSegActive(q("segVoice"), state.voice);
    setSegActive(q("segGame"), state.game);
    setSegActive(q("segMode"), state.mode);

    // zombies selections
    zSetMode(state.z_mode);
    zSetMap(state.z_map);

    renderChat();
    aimUpdateStat();

    // bind everything
    bindAll();

    renderDiagnostics();

    // mark OK
    window.__BCO_JS_OK__ = true;
    setHealth("js: OK (app restored)");
    log("READY", { hasTG: !!TG, build: window.__BCO_BUILD__ });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
