// app/webapp/static/app.js
// BCO Mini App Entry — FIXED (iOS taps + bot sync + Aim Trial) | NO UI CHANGES
(() => {
  "use strict";

  const log = (...a) => { try { console.log("[BCO_APP]", ...a); } catch {} };
  const warn = (...a) => { try { console.warn("[BCO_APP]", ...a); } catch {} };
  const err = (...a) => { try { console.error("[BCO_APP]", ...a); } catch {} };

  function safe(fn) { try { return fn(); } catch (e) { return undefined; } }
  function q(id) { return document.getElementById(id); }
  function qs(sel) { return document.querySelector(sel); }

  const TG = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;

  const CONFIG = (window.BCO && window.BCO.CONFIG) || window.BCO_CONFIG || window.CONFIG || {
    VERSION: "restore-2.0.1",
    MAX_PAYLOAD_SIZE: 15000,
    AIM_DURATION: 20000
  };

  // -------------------------
  // Health
  // -------------------------
  function setHealth(msg) {
    const el = q("jsHealth");
    if (el) el.textContent = String(msg || "");
  }

  // -------------------------
  // State (minimal, safe)
  // -------------------------
  const STATE = {
    profile: {
      voice: "TEAMMATE",
      mode: "Normal",
      platform: "PC",
      game: "Warzone",
      input: "Controller",
      role: "Flex",
      bf6_class: "Assault"
    },
    zombies: {
      mode: "ARCADE", // ARCADE | ROGUELIKE
      map: "Ashes"    // Ashes | Astra
    },
    aim: {
      running: false,
      t0: 0,
      hits: 0,
      misses: 0,
      timer: 0
    }
  };

  // -------------------------
  // Telegram helpers
  // -------------------------
  function tgReady() {
    if (!TG) return false;
    safe(() => TG.ready());
    safe(() => TG.expand());
    // не трогаем UI, просто не даем TG кнопкам перекрывать
    safe(() => TG.MainButton?.hide?.());
    safe(() => TG.BackButton?.hide?.());
    return true;
  }

  function clampPayloadSize(str) {
    const max = Number(CONFIG.MAX_PAYLOAD_SIZE || 15000);
    if (!str || str.length <= max) return str;
    return str.slice(0, max - 16) + `…(cut:${str.length})`;
  }

  function sendData(payloadObj) {
    if (!TG || typeof TG.sendData !== "function") {
      warn("TG.sendData missing");
      return false;
    }
    try {
      // всегда приклеиваем профиль, чтобы бот был “одним целым” с мини-аппом
      const p = {
        ...payloadObj,
        profile: payloadObj.profile || STATE.profile,
        _src: "miniapp",
        _v: String(CONFIG.VERSION || "unknown")
      };
      const json = clampPayloadSize(JSON.stringify(p));
      TG.sendData(json);
      return true;
    } catch (e) {
      warn("sendData failed", e);
      return false;
    }
  }

  // NAV контракт (у тебя в боте это обрабатывается)
  function sendNav(key, extra) {
    return sendData({
      type: "nav",
      nav: String(key || ""),
      ...((extra && typeof extra === "object") ? extra : {})
    });
  }

  // Команда/действие (но НЕ type=cmd, потому что бот сейчас отвечает “принял, без действия”)
  // Мы отправляем как nav + cmd, чтобы router точно пошел по nav ветке.
  function sendCmd(cmd, extra) {
    return sendData({
      type: "nav",
      nav: "cmd",
      cmd: String(cmd || ""),
      ...((extra && typeof extra === "object") ? extra : {})
    });
  }

  // -------------------------
  // iOS FastTap (НЕ ломает скролл)
  // -------------------------
  function bindFastTap(el, handler) {
    if (!el || typeof handler !== "function") return false;

    let down = null;

    function getPt(ev) {
      const t = (ev.touches && ev.touches[0]) ? ev.touches[0]
        : (ev.changedTouches && ev.changedTouches[0]) ? ev.changedTouches[0]
        : ev;
      return { x: Number(t.clientX || 0), y: Number(t.clientY || 0) };
    }

    function isScrollAllowedTarget(target) {
      // ничего не блокируем внутри скролл-зон
      return !!(target && target.closest && target.closest(".bco-modal-scroll, .modal, [role='dialog'], .chat-log, .chat-shell"));
    }

    function onDown(ev) {
      if (isScrollAllowedTarget(ev.target)) return;
      down = { t: Date.now(), ...getPt(ev) };
    }

    function onUp(ev) {
      if (!down) return;
      if (isScrollAllowedTarget(ev.target)) { down = null; return; }

      const up = getPt(ev);
      const dt = Date.now() - down.t;
      const dx = up.x - down.x;
      const dy = up.y - down.y;
      const dist = Math.sqrt(dx*dx + dy*dy);

      down = null;

      if (dt > 450) return;
      if (dist > 14) return;

      // ✅ важно: не делаем глобальный preventDefault по документу
      // только на конкретной кнопке, чтобы не было “мертвых” тапов
      safe(() => ev.preventDefault());
      safe(() => ev.stopPropagation());

      safe(() => handler(ev));
    }

    el.addEventListener("pointerdown", onDown, { passive: true });
    el.addEventListener("pointerup", onUp, { passive: false });

    // touch fallback (iOS WebView)
    el.addEventListener("touchstart", onDown, { passive: true });
    el.addEventListener("touchend", onUp, { passive: false });

    // click fallback (desktop)
    el.addEventListener("click", (e) => { safe(() => handler(e)); }, { passive: true });

    return true;
  }

  // -------------------------
  // UI helpers (toggle active классы, не меняя верстку)
  // -------------------------
  function setSegActive(containerEl, value) {
    if (!containerEl) return;
    const btns = Array.from(containerEl.querySelectorAll(".seg-btn"));
    for (const b of btns) {
      const v = b.getAttribute("data-value");
      b.classList.toggle("active", String(v) === String(value));
    }
  }

  function setModeButtons(activeArcade) {
    const a1 = q("btnZModeArcade");
    const r1 = q("btnZModeRogue");
    const a2 = q("btnZModeArcade2");
    const r2 = q("btnZModeRogue2");

    if (a1) a1.classList.toggle("active", !!activeArcade);
    if (r1) r1.classList.toggle("active", !activeArcade);
    if (a2) a2.classList.toggle("active", !!activeArcade);
    if (r2) r2.classList.toggle("active", !activeArcade);
  }

  // -------------------------
  // Aim Trial (working снова)
  // -------------------------
  function aimUpdateUI() {
    const stat = q("aimStat");
    const total = STATE.aim.hits + STATE.aim.misses;
    const acc = total ? Math.round((STATE.aim.hits / total) * 100) : 0;
    if (stat) stat.textContent = `🎯 ${STATE.aim.hits}/${total} • Acc ${acc}%`;
  }

  function aimMoveTarget() {
    const arena = q("aimArena");
    const target = q("aimTarget");
    if (!arena || !target) return;

    const rect = arena.getBoundingClientRect();
    const size = Math.min(rect.width, rect.height);

    // safe margins
    const pad = 18;
    const x = pad + Math.random() * Math.max(1, (rect.width - pad*2 - 44));
    const y = pad + Math.random() * Math.max(1, (rect.height - pad*2 - 44));

    target.style.left = `${x}px`;
    target.style.top = `${y}px`;
  }

  function aimStart() {
    if (STATE.aim.running) return;
    STATE.aim.running = true;
    STATE.aim.t0 = Date.now();
    STATE.aim.hits = 0;
    STATE.aim.misses = 0;
    aimUpdateUI();
    aimMoveTarget();

    // таймер авто-стоп
    clearTimeout(STATE.aim.timer);
    STATE.aim.timer = setTimeout(() => {
      aimStop();
    }, Number(CONFIG.AIM_DURATION || 20000));

    setHealth("aim: running");
  }

  function aimStop() {
    if (!STATE.aim.running) return;
    STATE.aim.running = false;
    clearTimeout(STATE.aim.timer);
    STATE.aim.timer = 0;
    setHealth("aim: stopped");
  }

  function aimSend() {
    const total = STATE.aim.hits + STATE.aim.misses;
    const acc = total ? Math.round((STATE.aim.hits / total) * 100) : 0;

    sendData({
      action: "game_result",
      type: "game_result",
      game: "aim_trial",
      mode: "ARCADE",
      durationMs: Number(CONFIG.AIM_DURATION || 20000),
      hits: STATE.aim.hits,
      misses: STATE.aim.misses,
      total,
      acc
    });
  }

  // -------------------------
  // Zombies launcher (НЕ ломаем mini app; просто дергаем runtime/engine)
  // -------------------------
  function zombiesStartFullscreen() {
    // 1) runtime new-stack
    const rt = window.BCO?.zombies?.runtime || window.BCO_ZOMBIES_RUNTIME || null;
    if (rt && typeof rt.startGame === "function") {
      return !!safe(() => rt.startGame());
    }

    // 2) engine direct
    const engine = window.BCO?.engine || window.BCO_ENGINE || null;
    if (engine && typeof engine.start === "function") {
      const mode = (STATE.zombies.mode === "ROGUELIKE") ? "roguelike" : "arcade";
      const map = STATE.zombies.map;
      const ok = safe(() => engine.start({ mode, map }));
      return (typeof ok === "boolean") ? ok : true;
    }

    // 3) legacy game runner (if you use BCO_ZOMBIES_GAME + core already started elsewhere)
    const game = window.BCO_ZOMBIES_GAME || null;
    if (game && typeof game.startLoop === "function") {
      const ok = safe(() => game.startLoop());
      return !!ok;
    }

    warn("No zombies runtime/engine found");
    return false;
  }

  function zombiesSendResult() {
    // просим существующий модуль, если он уже умеет
    const game = window.BCO_ZOMBIES_GAME || null;
    if (game && typeof game.sendResult === "function") {
      return !!safe(() => game.sendResult("miniapp"));
    }
    // fallback
    sendData({
      action: "game_result",
      type: "game_result",
      game: "zombies",
      reason: "miniapp_send",
      mode: (STATE.zombies.mode === "ROGUELIKE") ? "roguelike" : "arcade",
      map: STATE.zombies.map
    });
    return true;
  }

  // -------------------------
  // Bind buttons (IDs from твоего index.html)
  // -------------------------
  function bindAllButtons() {
    // HOME quick actions
    bindFastTap(q("btnOpenBot"), () => {
      // открыть меню бота
      sendNav("open_bot_menu", { hint: "menu" });
    });

    bindFastTap(q("btnSync"), () => {
      // запрос синхронизации профиля с ботом
      sendNav("sync_profile");
    });

    bindFastTap(q("btnPremium"), () => {
      sendNav("premium_hub");
    });

    bindFastTap(q("btnPlayZombies"), () => {
      // просто старт fullscreen зомби
      zombiesStartFullscreen();
    });

    // GAME tab launcher
    bindFastTap(q("btnZEnterGame"), () => { zombiesStartFullscreen(); });
    bindFastTap(q("btnZQuickPlay"), () => { zombiesStartFullscreen(); });

    bindFastTap(q("btnZGameSend"), () => { zombiesSendResult(); });
    bindFastTap(q("btnZGameSend2"), () => { zombiesSendResult(); });

    bindFastTap(q("btnZOpenHQ"), () => {
      // открыть zombies hub в боте
      sendNav("zombies_hq");
    });

    bindFastTap(q("btnOpenZombies"), () => { sendNav("zombies_open"); });
    bindFastTap(q("btnZPerks"), () => { sendNav("zombies_perks"); });
    bindFastTap(q("btnZLoadout"), () => { sendNav("zombies_loadout"); });
    bindFastTap(q("btnZEggs"), () => { sendNav("zombies_eggs"); });
    bindFastTap(q("btnZRound"), () => { sendNav("zombies_round"); });
    bindFastTap(q("btnZTips"), () => { sendNav("zombies_tips"); });

    // Zombies mode buttons
    bindFastTap(q("btnZModeArcade"), () => {
      STATE.zombies.mode = "ARCADE";
      setModeButtons(true);
      sendNav("zombies_mode", { mode: "ARCADE" });
    });

    bindFastTap(q("btnZModeRogue"), () => {
      STATE.zombies.mode = "ROGUELIKE";
      setModeButtons(false);
      sendNav("zombies_mode", { mode: "ROGUELIKE" });
    });

    bindFastTap(q("btnZModeArcade2"), () => {
      STATE.zombies.mode = "ARCADE";
      setModeButtons(true);
      sendNav("zombies_mode", { mode: "ARCADE" });
    });

    bindFastTap(q("btnZModeRogue2"), () => {
      STATE.zombies.mode = "ROGUELIKE";
      setModeButtons(false);
      sendNav("zombies_mode", { mode: "ROGUELIKE" });
    });

    // Zombies map seg
    const segMap = q("segZMap");
    if (segMap) {
      segMap.addEventListener("click", (e) => {
        const b = e.target && e.target.closest ? e.target.closest(".seg-btn") : null;
        if (!b) return;
        const mp = b.getAttribute("data-value") || "Ashes";
        STATE.zombies.map = (String(mp) === "Astra") ? "Astra" : "Ashes";
        setSegActive(segMap, STATE.zombies.map);
        sendNav("zombies_map", { map: STATE.zombies.map });
      }, { passive: true });
    }

    // Aim Trial buttons
    bindFastTap(q("btnAimStart"), () => aimStart());
    bindFastTap(q("btnAimStop"), () => aimStop());
    bindFastTap(q("btnAimSend"), () => aimSend());

    // Aim target hit/miss
    const arena = q("aimArena");
    const target = q("aimTarget");

    if (arena && target) {
      // hit
      bindFastTap(target, () => {
        if (!STATE.aim.running) return;
        STATE.aim.hits++;
        aimUpdateUI();
        aimMoveTarget();
      });

      // miss (tap on arena but not target)
      arena.addEventListener("click", (e) => {
        if (!STATE.aim.running) return;
        const t = e.target;
        if (t === target || (t && t.closest && t.closest("#aimTarget"))) return;
        STATE.aim.misses++;
        aimUpdateUI();
        aimMoveTarget();
      }, { passive: true });
    }

    // Chat send (минимально: шлём в бота как nav:chat, чтобы router точно обрабатывал)
    bindFastTap(q("btnChatSend"), () => {
      const input = q("chatInput");
      const text = input ? String(input.value || "").trim() : "";
      if (!text) return;
      if (input) input.value = "";
      sendNav("chat", { text });
    });

    // Share/Close
    bindFastTap(q("btnShare"), () => {
      if (!TG) return;
      safe(() => TG.shareMessage?.(TG.initDataUnsafe?.start_param || ""));
      // если shareMessage нет — просто отправим hint в бота
      sendNav("share");
    });

    bindFastTap(q("btnClose"), () => {
      if (TG && TG.close) safe(() => TG.close());
      else sendNav("close");
    });

    // Premium buy
    bindFastTap(q("btnBuyMonth"), () => { sendNav("buy_premium", { plan: "month" }); });
    bindFastTap(q("btnBuyLife"), () => { sendNav("buy_premium", { plan: "lifetime" }); });

    // Hotkeys shop (быстрые)
    bindFastTap(q("btnZBuyJug"), () => { sendNav("zombies_buy", { item: "jug" }); });
    bindFastTap(q("btnZBuySpeed"), () => { sendNav("zombies_buy", { item: "speed" }); });
    bindFastTap(q("btnZBuyAmmo"), () => { sendNav("zombies_buy", { item: "ammo" }); });
  }

  // -------------------------
  // Optional: mount your input router (НО он не должен ломать ID-кнопки)
  // -------------------------
  function mountInputRouter() {
    // твой новый iOS input модуль
    const inp = window.BCO?.input || window.BCO_INPUT || null;
    if (inp && typeof inp.mount === "function") {
      safe(() => inp.mount());
      return true;
    }
    return false;
  }

  // -------------------------
  // Init
  // -------------------------
  function init() {
    setHealth("js: starting…");

    // TG
    tgReady();
    safe(() => window.BCO_TG?.applyInsets?.());

    // IMPORTANT:
    // НЕ ставим глобальный “click killer” по document — он и убил тебе UI.
    // Только безопасный fastTap на нужных кнопках.

    // input router (если есть) — он совместим, потому что без data-action он не блокирует native click
    mountInputRouter();

    // bind all UI buttons
    bindAllButtons();

    // default UI state
    setModeButtons(STATE.zombies.mode === "ARCADE");
    setSegActive(q("segZMap"), STATE.zombies.map);
    aimUpdateUI();

    // mark ok
    window.__BCO_JS_OK__ = true;
    setHealth("js: OK (restored)");

    log("ready", {
      tg: !!TG,
      input: !!(window.BCO?.input || window.BCO_INPUT),
      zombiesRuntime: !!(window.BCO?.zombies?.runtime || window.BCO_ZOMBIES_RUNTIME),
      engine: !!(window.BCO?.engine || window.BCO_ENGINE)
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
