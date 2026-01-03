// app/webapp/static/app.js
// BCO Mini App (STABLE) — restores full functionality without UI changes
(() => {
  "use strict";

  const log = (...a) => console.log("[BCO_APP]", ...a);
  const warn = (...a) => console.warn("[BCO_APP]", ...a);

  const CONFIG = window.BCO_CONFIG || window.BCO?.CONFIG || {
    STORAGE_KEY: "bco_state_v1",
    CHAT_KEY: "bco_chat_v1",
    CHAT_HISTORY_LIMIT: 80,
    AIM_DURATION: 20000
  };

  function safe(fn) { try { return fn(); } catch (_) { return undefined; } }
  function q(id) { return document.getElementById(id); }

  function setHealth(msg) {
    const el = q("jsHealth");
    if (el) el.textContent = msg;
  }

  // ----------------------------
  // HARD FIX: clickability layers
  // ----------------------------
  function ensureClickLayers() {
    // Background FX must never intercept taps
    const bg = document.querySelector(".bg");
    if (bg) bg.style.pointerEvents = "none";
    for (const el of document.querySelectorAll(".bg, .bg *")) el.style.pointerEvents = "none";

    // Overlay mount must NOT block UI when not in game
    const zMount = q("zOverlayMount");
    if (zMount) {
      zMount.style.pointerEvents = "none";
      zMount.style.position = "fixed";
      zMount.style.left = "0";
      zMount.style.top = "0";
      zMount.style.width = "100vw";
      zMount.style.height = "100vh";
      zMount.style.zIndex = "9999";
    }
  }

  function isTG() {
    return !!(window.Telegram && Telegram.WebApp);
  }

  function tg() {
    return isTG() ? Telegram.WebApp : null;
  }

  // ----------------------------
  // STATE / PROFILE
  // ----------------------------
  function defaultProfile() {
    return {
      game: "Warzone",
      platform: "PC",
      input: "Controller",
      difficulty: "Normal",
      voice: "TEAMMATE",
      role: "Flex",
      bf6_class: "Assault"
    };
  }

  function loadState() {
    const raw = safe(() => localStorage.getItem(CONFIG.STORAGE_KEY));
    if (!raw) return { profile: defaultProfile() };
    try {
      const obj = JSON.parse(raw);
      if (!obj || typeof obj !== "object") return { profile: defaultProfile() };
      obj.profile = obj.profile || defaultProfile();
      return obj;
    } catch {
      return { profile: defaultProfile() };
    }
  }

  function saveState(st) {
    safe(() => localStorage.setItem(CONFIG.STORAGE_KEY, JSON.stringify(st)));
  }

  // ----------------------------
  // BOT BRIDGE (sendData)
  // ----------------------------
  function sendToBot(payload) {
    // payload MUST include {type, cmd} for bot router
    const wa = tg();
    const st = loadState();
    const full = {
      ...payload,
      profile: st.profile || defaultProfile(),
      ts: Date.now()
    };

    const s = JSON.stringify(full);
    if (wa && wa.sendData) {
      wa.sendData(s);
      return true;
    }

    // fallback for browser debug
    log("[BRIDGE] Telegram missing, payload:", full);
    return false;
  }

  // A single helper that makes iOS taps reliable without killing clicks
  function bindTap(el, fn) {
    if (!el) return;
    let last = 0;

    const run = (ev) => {
      const now = Date.now();
      if (now - last < 250) return; // anti double-fire
      last = now;
      safe(() => fn(ev));
    };

    // pointerup works best in iOS WebView
    el.addEventListener("pointerup", (e) => {
      // DO NOT preventDefault globally; only stop when it’s a real button tap
      run(e);
    }, { passive: true });

    // click fallback
    el.addEventListener("click", (e) => run(e), { passive: true });
  }

  // ----------------------------
  // UI: Tabs (bottom nav)
  // ----------------------------
  function initTabs() {
    const tabs = Array.from(document.querySelectorAll(".tabpane"));
    const navBtns = Array.from(document.querySelectorAll(".nav-btn"));

    function show(name) {
      for (const t of tabs) t.classList.remove("active");
      const pane = q("tab-" + name);
      if (pane) pane.classList.add("active");

      for (const b of navBtns) {
        const on = b.getAttribute("data-tab") === name;
        b.classList.toggle("active", on);
        b.setAttribute("aria-selected", on ? "true" : "false");
      }
    }

    for (const b of navBtns) {
      bindTap(b, () => show(b.getAttribute("data-tab")));
    }

    // default
    show("home");
  }

  // ----------------------------
  // UI: Seg buttons helper
  // ----------------------------
  function segBind(segEl, onPick) {
    if (!segEl) return;
    bindTap(segEl, (e) => {
      const btn = e.target && e.target.closest ? e.target.closest(".seg-btn") : null;
      if (!btn) return;
      for (const b of segEl.querySelectorAll(".seg-btn")) b.classList.remove("active");
      btn.classList.add("active");
      onPick(btn.getAttribute("data-value"));
    });
  }

  // ----------------------------
  // AIM TRIAL (guaranteed working)
  // ----------------------------
  function initAimTrial() {
    const arena = q("aimArena");
    const target = q("aimTarget");
    const stat = q("aimStat");
    const btnStart = q("btnAimStart");
    const btnStop = q("btnAimStop");
    const btnSend = q("btnAimSend");

    if (!arena || !target || !stat) return;

    let running = false;
    let hits = 0;
    let shots = 0;
    let endAt = 0;
    let timer = 0;

    function placeTarget() {
      const r = arena.getBoundingClientRect();
      const size = Math.max(44, Math.min(88, Math.floor(Math.min(r.width, r.height) * 0.14)));
      target.style.width = size + "px";
      target.style.height = size + "px";

      const pad = 12;
      const x = pad + Math.random() * Math.max(0, r.width - size - pad * 2);
      const y = pad + Math.random() * Math.max(0, r.height - size - pad * 2);

      target.style.left = x + "px";
      target.style.top = y + "px";
    }

    function updateStat() {
      const acc = shots ? Math.round((hits / shots) * 100) : 0;
      stat.textContent = `🎯 ${hits}/${shots} • Acc ${acc}%`;
    }

    function stop() {
      running = false;
      if (timer) clearInterval(timer);
      timer = 0;
      updateStat();
    }

    function start() {
      hits = 0;
      shots = 0;
      running = true;
      endAt = Date.now() + Number(CONFIG.AIM_DURATION || 20000);

      placeTarget();
      updateStat();

      if (timer) clearInterval(timer);
      timer = setInterval(() => {
        if (!running) return;
        if (Date.now() >= endAt) stop();
      }, 120);
    }

    // Shots inside arena (miss if not target)
    bindTap(arena, (e) => {
      if (!running) return;
      const isHit = e.target === target || (e.target && e.target.closest && e.target.closest("#aimTarget"));
      shots++;
      if (isHit) {
        hits++;
        placeTarget();
      }
      updateStat();
    });

    bindTap(btnStart, start);
    bindTap(btnStop, stop);

    bindTap(btnSend, () => {
      sendToBot({
        type: "game_result",
        game: "aim_trial",
        result: { hits, shots, duration_ms: Number(CONFIG.AIM_DURATION || 20000) }
      });
    });

    // on resize reposition
    window.addEventListener("resize", () => safe(placeTarget), { passive: true });
    safe(placeTarget);
  }

  // ----------------------------
  // ZOMBIES: Launcher -> Runtime/Engine
  // ----------------------------
  function initZombiesLauncher() {
    const btnPlay = q("btnPlayZombies");
    const btnEnter = q("btnZEnterGame");
    const btnQuick = q("btnZQuickPlay");

    const btnModeA1 = q("btnZModeArcade");
    const btnModeR1 = q("btnZModeRogue");
    const btnModeA2 = q("btnZModeArcade2");
    const btnModeR2 = q("btnZModeRogue2");

    const segMap = q("segZMap");

    const runtime = window.BCO?.zombies?.runtime || window.BCO_ZOMBIES_RUNTIME || null;
    const engine = window.BCO?.engine || window.BCO_ENGINE || null;

    const state = { mode: "ARCADE", map: "Ashes" };

    function setMode(m) {
      state.mode = String(m).toUpperCase().includes("ROGUE") ? "ROGUELIKE" : "ARCADE";
      [btnModeA1, btnModeA2].forEach(b => b && b.classList.toggle("active", state.mode === "ARCADE"));
      [btnModeR1, btnModeR2].forEach(b => b && b.classList.toggle("active", state.mode === "ROGUELIKE"));

      safe(() => runtime?.setMode?.(state.mode));
    }

    function setMap(mp) {
      state.map = (String(mp) === "Astra") ? "Astra" : "Ashes";
      if (segMap) {
        for (const b of segMap.querySelectorAll(".seg-btn")) {
          b.classList.toggle("active", b.getAttribute("data-value") === state.map);
        }
      }
      safe(() => runtime?.setMap?.(state.map));
    }

    function startGame() {
      // allow overlay pointer events ONLY during game
      const zMount = q("zOverlayMount");
      if (zMount) zMount.style.pointerEvents = "auto";

      // prefer runtime
      if (runtime?.startGame) return runtime.startGame();

      // fallback engine
      if (engine?.start) {
        return engine.start({
          mode: (state.mode === "ROGUELIKE") ? "roguelike" : "arcade",
          map: state.map
        });
      }

      warn("Zombies runtime/engine missing");
      return false;
    }

    bindTap(btnPlay, startGame);
    bindTap(btnEnter, startGame);
    bindTap(btnQuick, startGame);

    bindTap(btnModeA1, () => setMode("ARCADE"));
    bindTap(btnModeR1, () => setMode("ROGUELIKE"));
    bindTap(btnModeA2, () => setMode("ARCADE"));
    bindTap(btnModeR2, () => setMode("ROGUELIKE"));

    if (segMap) {
      bindTap(segMap, (e) => {
        const b = e.target && e.target.closest ? e.target.closest(".seg-btn") : null;
        if (!b) return;
        setMap(b.getAttribute("data-value"));
      });
    }

    // Default state reflect
    setMode("ARCADE");
    setMap("Ashes");
  }

  // ----------------------------
  // BOT COMMAND BUTTONS (restore your bridge)
  // ----------------------------
  function initBotButtons() {
    // Home quick actions
    bindTap(q("btnOpenBot"), () => sendToBot({ type: "cmd", cmd: "open_bot_menu" }));
    bindTap(q("btnSync"), () => sendToBot({ type: "cmd", cmd: "sync_profile" }));
    bindTap(q("btnPremium"), () => sendToBot({ type: "cmd", cmd: "premium_hub" }));

    // Premium buy
    bindTap(q("btnBuyMonth"), () => sendToBot({ type: "cmd", cmd: "buy_month" }));
    bindTap(q("btnBuyLife"), () => sendToBot({ type: "cmd", cmd: "buy_lifetime" }));

    // Coach/VOD open
    bindTap(q("btnOpenTraining"), () => sendToBot({ type: "cmd", cmd: "open_training" }));
    bindTap(q("btnOpenVod"), () => sendToBot({ type: "cmd", cmd: "open_vod" }));
    bindTap(q("btnSendPlan"), () => sendToBot({ type: "cmd", cmd: "send_plan" }));
    bindTap(q("btnSendVod"), () => {
      const payload = {
        type: "cmd",
        cmd: "send_vod",
        vod: {
          t1: (q("vod1")?.value || "").trim(),
          t2: (q("vod2")?.value || "").trim(),
          t3: (q("vod3")?.value || "").trim(),
          note: (q("vodNote")?.value || "").trim()
        }
      };
      sendToBot(payload);
    });

    // Zombies HQ / Bot buttons
    bindTap(q("btnZOpenHQ"), () => sendToBot({ type: "cmd", cmd: "zombies_hq" }));
    bindTap(q("btnOpenZombies"), () => sendToBot({ type: "cmd", cmd: "zombies_open" }));
    bindTap(q("btnZPerks"), () => sendToBot({ type: "cmd", cmd: "zombies_perks" }));
    bindTap(q("btnZLoadout"), () => sendToBot({ type: "cmd", cmd: "zombies_loadout" }));
    bindTap(q("btnZEggs"), () => sendToBot({ type: "cmd", cmd: "zombies_eggs" }));
    bindTap(q("btnZRound"), () => sendToBot({ type: "cmd", cmd: "zombies_round" }));
    bindTap(q("btnZTips"), () => sendToBot({ type: "cmd", cmd: "zombies_tips" }));

    // Share / Close
    bindTap(q("btnClose"), () => safe(() => tg()?.close?.()));
    bindTap(q("btnShare"), () => {
      const wa = tg();
      if (wa?.openTelegramLink) safe(() => wa.openTelegramLink("https://t.me/share/url?url=BLACK%20CROWN%20OPS"));
      else sendToBot({ type: "cmd", cmd: "share" });
    });
  }

  // ----------------------------
  // CHAT (basic send to bot)
  // ----------------------------
  function initChat() {
    const input = q("chatInput");
    const btn = q("btnChatSend");
    const logEl = q("chatLog");
    const btnClear = q("btnChatClear");
    const btnCopy = q("btnChatExport");

    function append(line) {
      if (!logEl) return;
      const div = document.createElement("div");
      div.className = "chat-line";
      div.textContent = line;
      logEl.appendChild(div);
      logEl.scrollTop = logEl.scrollHeight;
    }

    function send() {
      const text = (input?.value || "").trim();
      if (!text) return;
      input.value = "";
      append("🫵 " + text);
      sendToBot({ type: "chat", text });
    }

    bindTap(btn, send);

    if (input) {
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          send();
        }
      });
    }

    bindTap(btnClear, () => {
      if (logEl) logEl.innerHTML = "";
      safe(() => localStorage.removeItem(CONFIG.CHAT_KEY));
    });

    bindTap(btnCopy, () => {
      const txt = logEl ? logEl.innerText : "";
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(txt);
      }
    });
  }

  // ----------------------------
  // SETTINGS PROFILE (local save + send to bot)
  // ----------------------------
  function initProfileUI() {
    const st = loadState();
    const profile = st.profile || defaultProfile();

    // platform seg
    segBind(q("segPlatform"), (v) => { profile.platform = v; });
    segBind(q("segInput"), (v) => { profile.input = v; });
    segBind(q("segVoice"), (v) => { profile.voice = v; });

    bindTap(q("btnApplyProfile"), () => {
      const newSt = loadState();
      newSt.profile = { ...(newSt.profile || defaultProfile()), ...profile };
      saveState(newSt);
      sendToBot({ type: "cmd", cmd: "profile_update", profile: newSt.profile });
    });

    bindTap(q("btnOpenSettings"), () => sendToBot({ type: "cmd", cmd: "open_settings" }));
  }

  // ----------------------------
  // BOOT
  // ----------------------------
  function start() {
    setHealth("js: starting…");

    ensureClickLayers();

    // mount input SAFE (does not kill native click)
    safe(() => window.BCO?.input?.mount?.());

    initTabs();
    initAimTrial();
    initZombiesLauncher();
    initBotButtons();
    initChat();
    initProfileUI();

    // diagnostics
    safe(() => {
      q("dbgTheme") && (q("dbgTheme").textContent = String(tg()?.colorScheme || "—"));
      q("dbgInit") && (q("dbgInit").textContent = tg()?.initDataUnsafe ? "ok" : "—");
      q("dbgUser") && (q("dbgUser").textContent = String(tg()?.initDataUnsafe?.user?.id || "—"));
    });

    window.__BCO_JS_OK__ = true;
    setHealth("js: OK");
    log("BOOT OK");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
