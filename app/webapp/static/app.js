// app/webapp/static/app.js
// BCO Mini App — STABLE UI (NO VISUAL CHANGES) + iOS TAP FIX + FULL BINDINGS (RESTORE FUNCTIONALITY)
(() => {
  "use strict";

  const log = (...a) => { try { console.log("[BCO_APP]", ...a); } catch {} };
  const warn = (...a) => { try { console.warn("[BCO_APP]", ...a); } catch {} };

  const TG = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;

  // -------------------------
  // Config / Storage (compatible with your earlier keys)
  // -------------------------
  const STORAGE_KEY = "bco_state_v1";
  const CHAT_KEY = "bco_chat_v1";
  const CHAT_LIMIT = 80;
  const MAX_PAYLOAD = 15000;

  function safe(fn) { try { return fn(); } catch { return undefined; } }
  function q(id) { return document.getElementById(id); }
  function qs(sel) { return document.querySelector(sel); }
  function qa(sel) { return Array.from(document.querySelectorAll(sel)); }

  function setHealth(msg) {
    const el = q("jsHealth");
    if (el) el.textContent = String(msg || "");
  }

  // -------------------------
  // Toast
  // -------------------------
  const Toast = (() => {
    const el = () => q("toast");
    let t = 0;

    function show(msg, ms = 1400) {
      const e = el();
      if (!e) return;
      e.textContent = String(msg || "OK");
      e.style.opacity = "1";
      e.style.transform = "translateY(0)";
      clearTimeout(t);
      t = setTimeout(() => {
        try {
          e.style.opacity = "0";
          e.style.transform = "translateY(6px)";
        } catch {}
      }, ms);
    }
    return { show };
  })();

  // -------------------------
  // State/Profile
  // -------------------------
  const State = (() => {
    const DEFAULT = {
      profile: {
        voice: "TEAMMATE", // TEAMMATE | COACH
        mode: "Normal",    // Normal | Pro | Demon
        platform: "PC",    // PC | PlayStation | Xbox
        input: "Controller", // Controller | KBM
        game: "Warzone",   // Warzone | BO7 | BF6
        role: "Flex",
        bf6_class: "Assault"
      },
      ui: {
        tab: "home",
        zMode: "arcade",   // arcade | roguelike
        zMap: "Ashes"      // Ashes | Astra
      }
    };

    function load() {
      try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return structuredClone(DEFAULT);
        const parsed = JSON.parse(raw);
        return {
          profile: { ...DEFAULT.profile, ...(parsed.profile || {}) },
          ui: { ...DEFAULT.ui, ...(parsed.ui || {}) }
        };
      } catch {
        return structuredClone(DEFAULT);
      }
    }

    function save(st) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(st));
        return true;
      } catch {
        return false;
      }
    }

    let st = load();

    function get() { return st; }
    function set(next) { st = next; save(st); return st; }
    function patch(partial) {
      st = {
        profile: { ...st.profile, ...(partial.profile || {}) },
        ui: { ...st.ui, ...(partial.ui || {}) }
      };
      save(st);
      return st;
    }

    return { get, set, patch, save };
  })();

  // -------------------------
  // SendData (single reliable pipe)
  // -------------------------
  function sendToBot(payload) {
    try {
      if (!payload || typeof payload !== "object") payload = { value: String(payload || "") };

      const st = State.get();
      const pack = {
        ...payload,
        profile: st.profile,
        ts: Date.now()
      };

      const json = JSON.stringify(pack);
      if (json.length > MAX_PAYLOAD) {
        Toast.show("Payload too big");
        warn("sendToBot payload too big", json.length);
        return false;
      }

      if (TG && typeof TG.sendData === "function") {
        TG.sendData(json);
        return true;
      }

      // Fallback (opened outside TG)
      warn("TG.sendData missing. Payload:", pack);
      return false;
    } catch (e) {
      warn("sendToBot failed", e);
      return false;
    }
  }

  // -------------------------
  // iOS FastTap (fix dead taps)
  // -------------------------
  const FastTap = (() => {
    const MODAL_SCROLL_SEL = ".bco-modal-scroll, .modal, .modal-body, [role='dialog'], .allow-scroll";
    const TAP_MAX_MOVE = 14;
    const TAP_MAX_MS = 450;
    let active = null;
    let lastFireAt = 0;

    function withinScrollable(target) {
      return !!(target && target.closest && target.closest(MODAL_SCROLL_SEL));
    }

    function isInteractive(target) {
      if (!target) return false;
      if (withinScrollable(target)) return false;
      if (target.closest && target.closest("[data-tab],[data-value],[data-action],[data-route],[data-z]")) return true;
      const el = target.closest ? target.closest("button,a,[role='button'],input,textarea,select,label") : null;
      return !!el;
    }

    function getPoint(ev) {
      if (ev.changedTouches && ev.changedTouches[0]) return ev.changedTouches[0];
      if (ev.touches && ev.touches[0]) return ev.touches[0];
      return ev;
    }

    function onDown(ev) {
      const t = ev.target;
      if (!isInteractive(t)) return;
      const p = getPoint(ev);
      active = { t0: Date.now(), x0: p.clientX || 0, y0: p.clientY || 0, moved: false, target: t };
    }

    function onMove(ev) {
      if (!active) return;
      const p = getPoint(ev);
      const x = p.clientX || 0;
      const y = p.clientY || 0;
      const dx = x - active.x0;
      const dy = y - active.y0;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist > TAP_MAX_MOVE) active.moved = true;
    }

    function onUp(ev) {
      if (!active) return;
      const dt = Date.now() - active.t0;
      const okTap = (dt <= TAP_MAX_MS) && !active.moved;
      const t = ev.target || active.target;
      active = null;

      if (!okTap) return;
      if (!isInteractive(t)) return;

      const now = Date.now();
      if (now - lastFireAt < 220) return;
      lastFireAt = now;

      safe(() => ev.preventDefault());
      safe(() => ev.stopPropagation());

      const el =
        (t && t.closest && t.closest("button,a,[role='button'],[data-tab],[data-value],[data-action],[data-route],[data-z]"))
        || t;

      safe(() => el && el.click && el.click());
    }

    function mount() {
      document.addEventListener("pointerdown", onDown, { capture: true, passive: false });
      document.addEventListener("pointermove", onMove, { capture: true, passive: false });
      document.addEventListener("pointerup", onUp, { capture: true, passive: false });
      document.addEventListener("pointercancel", () => { active = null; }, { capture: true, passive: true });

      document.addEventListener("touchstart", onDown, { capture: true, passive: false });
      document.addEventListener("touchmove", onMove, { capture: true, passive: false });
      document.addEventListener("touchend", onUp, { capture: true, passive: false });
      document.addEventListener("touchcancel", () => { active = null; }, { capture: true, passive: true });

      return true;
    }

    return { mount };
  })();

  // -------------------------
  // Tabs (restore nav)
  // -------------------------
  function setTab(name) {
    const panes = qa(".tabpane");
    const navs = qa(".bottom-nav .nav-btn");
    for (const p of panes) p.classList.toggle("active", p.id === ("tab-" + name));
    for (const b of navs) {
      const ok = b.getAttribute("data-tab") === name;
      b.classList.toggle("active", ok);
      b.setAttribute("aria-selected", ok ? "true" : "false");
    }
    State.patch({ ui: { tab: name } });
    safe(() => { location.hash = "#" + name; });
  }

  function bindTabs() {
    const nav = qs(".bottom-nav");
    if (nav) {
      nav.addEventListener("click", (e) => {
        const b = e.target && e.target.closest ? e.target.closest(".nav-btn") : null;
        if (!b) return;
        const name = b.getAttribute("data-tab") || "home";
        setTab(name);
      }, { passive: true });
    }

    const st = State.get();
    const h = (location.hash || "").replace("#", "");
    if (h && q("tab-" + h)) setTab(h);
    else if (st.ui.tab && q("tab-" + st.ui.tab)) setTab(st.ui.tab);
    else setTab("home");
  }

  // -------------------------
  // Chips / Segments (restore behavior)
  // -------------------------
  function refreshChips() {
    const st = State.get();

    const chipVoice = q("chipVoice");
    const chipMode = q("chipMode");
    const chipPlatform = q("chipPlatform");

    if (chipVoice) chipVoice.textContent = (st.profile.voice === "COACH") ? "📚 Коуч" : "🤝 Тиммейт";
    if (chipMode) chipMode.textContent = `🧠 ${st.profile.mode || "Normal"}`;
    if (chipPlatform) {
      const p = st.profile.platform || "PC";
      chipPlatform.textContent = (p === "PlayStation") ? "🎮 PS" : (p === "Xbox") ? "🎮 Xbox" : "🖥 PC";
    }

    const chatSub = q("chatSub");
    if (chatSub) chatSub.textContent = `${st.profile.voice} • ${st.profile.mode} • ${st.profile.platform}`;
  }

  function bindProfileControls() {
    const st = State.get();

    // Voice seg in Settings
    qa("#segVoice .seg-btn").forEach((b) => {
      const v = b.getAttribute("data-value");
      b.classList.toggle("active", v === st.profile.voice);
      b.addEventListener("click", () => {
        State.patch({ profile: { voice: v } });
        qa("#segVoice .seg-btn").forEach(x => x.classList.toggle("active", x === b));
        refreshChips();
        Toast.show("Voice: " + v);
      }, { passive: true });
    });

    // Mode seg in Coach
    qa("#segMode .seg-btn").forEach((b) => {
      const v = b.getAttribute("data-value");
      b.classList.toggle("active", v === st.profile.mode);
      b.addEventListener("click", () => {
        State.patch({ profile: { mode: v } });
        qa("#segMode .seg-btn").forEach(x => x.classList.toggle("active", x === b));
        refreshChips();
        Toast.show("Mode: " + v);
      }, { passive: true });
    });

    // Platform seg in Settings
    qa("#segPlatform .seg-btn").forEach((b) => {
      const v = b.getAttribute("data-value");
      b.classList.toggle("active", v === st.profile.platform);
      b.addEventListener("click", () => {
        State.patch({ profile: { platform: v } });
        qa("#segPlatform .seg-btn").forEach(x => x.classList.toggle("active", x === b));
        refreshChips();
        Toast.show("Platform: " + v);
      }, { passive: true });
    });

    // Input seg in Settings
    qa("#segInput .seg-btn").forEach((b) => {
      const v = b.getAttribute("data-value");
      b.classList.toggle("active", v === st.profile.input);
      b.addEventListener("click", () => {
        State.patch({ profile: { input: v } });
        qa("#segInput .seg-btn").forEach(x => x.classList.toggle("active", x === b));
        refreshChips();
        Toast.show("Input: " + v);
      }, { passive: true });
    });

    // Game seg in Home
    qa("#segGame .seg-btn").forEach((b) => {
      const v = b.getAttribute("data-value");
      b.classList.toggle("active", v === st.profile.game);
      b.addEventListener("click", () => {
        State.patch({ profile: { game: v } });
        qa("#segGame .seg-btn").forEach(x => x.classList.toggle("active", x === b));
        Toast.show("Game: " + v);
      }, { passive: true });
    });

    // Chip quick toggles
    q("chipVoice")?.addEventListener("click", () => {
      const cur = State.get().profile.voice;
      const next = (cur === "COACH") ? "TEAMMATE" : "COACH";
      State.patch({ profile: { voice: next } });
      qa("#segVoice .seg-btn").forEach((b) => b.classList.toggle("active", b.getAttribute("data-value") === next));
      refreshChips();
      Toast.show("Voice: " + next);
    }, { passive: true });

    q("chipMode")?.addEventListener("click", () => {
      const order = ["Normal", "Pro", "Demon"];
      const cur = State.get().profile.mode || "Normal";
      const i = Math.max(0, order.indexOf(cur));
      const next = order[(i + 1) % order.length];
      State.patch({ profile: { mode: next } });
      qa("#segMode .seg-btn").forEach((b) => b.classList.toggle("active", b.getAttribute("data-value") === next));
      refreshChips();
      Toast.show("Mode: " + next);
    }, { passive: true });

    q("chipPlatform")?.addEventListener("click", () => {
      const order = ["PC", "PlayStation", "Xbox"];
      const cur = State.get().profile.platform || "PC";
      const i = Math.max(0, order.indexOf(cur));
      const next = order[(i + 1) % order.length];
      State.patch({ profile: { platform: next } });
      qa("#segPlatform .seg-btn").forEach((b) => b.classList.toggle("active", b.getAttribute("data-value") === next));
      refreshChips();
      Toast.show("Platform: " + next);
    }, { passive: true });

    q("btnApplyProfile")?.addEventListener("click", () => {
      State.save(State.get());
      Toast.show("✅ Profile saved");
      sendToBot({ type: "profile", action: "sync_profile" });
    }, { passive: true });
  }

  // -------------------------
  // Chat (restore basic)
  // -------------------------
  function loadChat() {
    try {
      const raw = localStorage.getItem(CHAT_KEY);
      if (!raw) return [];
      const arr = JSON.parse(raw);
      return Array.isArray(arr) ? arr.slice(-CHAT_LIMIT) : [];
    } catch {
      return [];
    }
  }

  function saveChat(arr) {
    try {
      localStorage.setItem(CHAT_KEY, JSON.stringify(arr.slice(-CHAT_LIMIT)));
    } catch {}
  }

  function renderChat() {
    const logEl = q("chatLog");
    if (!logEl) return;
    const items = loadChat();
    logEl.innerHTML = "";
    for (const it of items) {
      const row = document.createElement("div");
      row.className = "chat-row";
      row.style.margin = "8px 0";
      row.style.display = "flex";
      row.style.gap = "10px";
      row.style.alignItems = "flex-start";

      const badge = document.createElement("div");
      badge.textContent = (it.who === "me") ? "🫵" : "😈";
      badge.style.width = "30px";
      badge.style.flex = "0 0 30px";
      badge.style.opacity = "0.9";

      const bubble = document.createElement("div");
      bubble.textContent = it.text || "";
      bubble.style.padding = "10px 12px";
      bubble.style.borderRadius = "12px";
      bubble.style.maxWidth = "82%";
      bubble.style.whiteSpace = "pre-wrap";
      bubble.style.wordBreak = "break-word";
      bubble.style.background = (it.who === "me") ? "rgba(140,120,255,0.22)" : "rgba(255,255,255,0.10)";

      row.appendChild(badge);
      row.appendChild(bubble);
      logEl.appendChild(row);
    }
    try { logEl.scrollTop = logEl.scrollHeight; } catch {}
  }

  function pushChat(who, text) {
    const items = loadChat();
    items.push({ who, text: String(text || ""), t: Date.now() });
    saveChat(items);
    renderChat();
  }

  function bindChat() {
    const inp = q("chatInput");
    const btn = q("btnChatSend");
    const btnClear = q("btnChatClear");
    const btnCopy = q("btnChatExport");

    function send() {
      const txt = (inp && inp.value) ? inp.value.trim() : "";
      if (!txt) return;
      if (inp) inp.value = "";
      pushChat("me", txt);

      // send to bot
      sendToBot({ type: "chat", action: "chat", text: txt });
      Toast.show("Sent → bot");
    }

    btn?.addEventListener("click", send, { passive: true });
    inp?.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        send();
      }
    });

    btnClear?.addEventListener("click", () => {
      saveChat([]);
      renderChat();
      Toast.show("Chat cleared");
    }, { passive: true });

    btnCopy?.addEventListener("click", async () => {
      const items = loadChat();
      const text = items.map(x => (x.who === "me" ? "ME: " : "BOT: ") + x.text).join("\n");
      try {
        await navigator.clipboard.writeText(text);
        Toast.show("Copied");
      } catch {
        Toast.show("Copy failed");
      }
    }, { passive: true });

    renderChat();
  }

  // -------------------------
  // Zombies Launcher (restore)
  // -------------------------
  const Takeover = (() => {
    const takeoverClass = "bco-game-takeover";
    const activeClass = "bco-game-active";

    function hideTG(on) {
      if (!TG) return;
      safe(() => TG.ready());
      safe(() => TG.expand());
      safe(() => TG.MainButton?.hide?.());
      safe(() => TG.BackButton?.hide?.());
      if (on) safe(() => TG.enableClosingConfirmation?.());
      else safe(() => TG.disableClosingConfirmation?.());
      safe(() => window.BCO_TG?.applyInsets?.());
    }

    function setOverlayPointer(on) {
      const mount = q("zOverlayMount");
      if (!mount) return;
      mount.style.pointerEvents = on ? "auto" : "none";
    }

    function hideChrome(on) {
      const header = qs("header.app-header");
      const nav = qs("nav.bottom-nav");
      const foot = qs("footer.foot");
      if (on) {
        if (header) header.style.display = "none";
        if (nav) nav.style.display = "none";
        if (foot) foot.style.display = "none";
      } else {
        if (header) header.style.display = "";
        if (nav) nav.style.display = "";
        if (foot) foot.style.display = "";
      }
    }

    function enter() {
      document.body.classList.add(takeoverClass);
      document.body.classList.add(activeClass);
      hideTG(true);
      hideChrome(true);
      setOverlayPointer(true);
    }

    function exit() {
      document.body.classList.remove(takeoverClass);
      document.body.classList.remove(activeClass);
      setOverlayPointer(false);
      hideChrome(false);
      hideTG(false);
      safe(() => window.BCO_TG?.hideChrome?.());
    }

    function isActive() { return document.body.classList.contains(takeoverClass); }

    return { enter, exit, isActive };
  })();

  function setZModeUI(isRogue) {
    q("btnZModeArcade")?.classList.toggle("active", !isRogue);
    q("btnZModeRogue")?.classList.toggle("active", isRogue);
    q("btnZModeArcade2")?.classList.toggle("active", !isRogue);
    q("btnZModeRogue2")?.classList.toggle("active", isRogue);
    State.patch({ ui: { zMode: isRogue ? "roguelike" : "arcade" } });
  }

  function setZMapUI(map) {
    const m = (String(map) === "Astra") ? "Astra" : "Ashes";
    const seg = q("segZMap");
    if (seg) {
      qa("#segZMap .seg-btn").forEach((b) => {
        b.classList.toggle("active", b.getAttribute("data-value") === m);
      });
    }
    State.patch({ ui: { zMap: m } });
  }

  function readZMode() {
    const st = State.get();
    // trust state, fallback to UI
    if (st.ui.zMode) return st.ui.zMode;
    const r = q("btnZModeRogue2");
    return (r && r.classList.contains("active")) ? "roguelike" : "arcade";
  }

  function readZMap() {
    const st = State.get();
    if (st.ui.zMap) return st.ui.zMap;
    const seg = q("segZMap");
    if (!seg) return "Ashes";
    const b = seg.querySelector(".seg-btn.active");
    const v = b ? (b.getAttribute("data-value") || "Ashes") : "Ashes";
    return (v === "Astra") ? "Astra" : "Ashes";
  }

  function ensureZCanvas() {
    const mount = q("zOverlayMount");
    if (!mount) return null;

    let canvas = mount.querySelector("#bcoZCanvas");
    if (!canvas) {
      canvas = document.createElement("canvas");
      canvas.id = "bcoZCanvas";
      canvas.style.position = "fixed";
      canvas.style.left = "0";
      canvas.style.top = "0";
      canvas.style.width = "100vw";
      canvas.style.height = "100vh";
      canvas.style.zIndex = "9999";
      canvas.style.background = "transparent";
      canvas.style.display = "block";
      canvas.style.pointerEvents = "none"; // controls overlay must be clickable above if present
      mount.appendChild(canvas);
    } else {
      canvas.style.display = "block";
    }

    const dpr = Math.max(1, Math.min(3, window.devicePixelRatio || 1));
    canvas.width = Math.floor(window.innerWidth * dpr);
    canvas.height = Math.floor(window.innerHeight * dpr);

    return canvas;
  }

  function startZombies() {
    const mode = readZMode();
    const map = readZMap();

    // First: if NEW runtime exists, use it (does takeover)
    const runtime =
      window.BCO_ZOMBIES_RUNTIME ||
      window.BCO?.zombies?.runtime ||
      window.BCO?.zombies?.runtime ||
      null;

    if (runtime && (runtime.startGame || runtime.start)) {
      safe(() => runtime.setMode?.(mode.toUpperCase()));
      safe(() => runtime.setMap?.(map));
      const ok = safe(() => runtime.startGame?.()) ?? safe(() => runtime.start?.());
      if (ok !== false) return true;
    }

    // Legacy path: use your core+game runner (zombies.game.js)
    const CORE = window.BCO_ZOMBIES_CORE || null;
    const ZGAME = window.BCO_ZOMBIES_GAME || null;

    if (!CORE || !ZGAME) {
      Toast.show("Zombies core not loaded");
      warn("Missing CORE/ZGAME", { CORE: !!CORE, ZGAME: !!ZGAME });
      return false;
    }

    Takeover.enter();

    const canvas = ensureZCanvas();
    if (!canvas) {
      Takeover.exit();
      return false;
    }

    safe(() => ZGAME.setCanvas?.(canvas));
    safe(() => ZGAME.setInGame?.(true));

    const tms = (performance && performance.now) ? performance.now() : Date.now();
    // core.start(mode, w, h, opts, tms) — css px
    safe(() => CORE.start?.(mode, Math.floor(window.innerWidth), Math.floor(window.innerHeight), { map }, tms));

    // ZOOM contract +0.5 delta
    safe(() => CORE.setZoomDelta?.(+0.5));

    safe(() => ZGAME.startLoop?.());
    Toast.show("Game started");
    return true;
  }

  function stopZombies() {
    const CORE = window.BCO_ZOMBIES_CORE || null;
    const ZGAME = window.BCO_ZOMBIES_GAME || null;
    safe(() => ZGAME?.setInGame?.(false));
    safe(() => ZGAME?.stopLoop?.());
    safe(() => CORE?.stop?.());
    const c = q("bcoZCanvas");
    if (c) c.style.display = "none";
    Takeover.exit();
    Toast.show("Exit game");
  }

  function bindZombies() {
    // mode buttons (both places)
    q("btnZModeArcade")?.addEventListener("click", () => setZModeUI(false), { passive: true });
    q("btnZModeArcade2")?.addEventListener("click", () => setZModeUI(false), { passive: true });
    q("btnZModeRogue")?.addEventListener("click", () => setZModeUI(true), { passive: true });
    q("btnZModeRogue2")?.addEventListener("click", () => setZModeUI(true), { passive: true });

    // map seg
    q("segZMap")?.addEventListener("click", (e) => {
      const b = e.target && e.target.closest ? e.target.closest(".seg-btn") : null;
      if (!b) return;
      setZMapUI(b.getAttribute("data-value"));
    }, { passive: true });

    // start buttons
    q("btnPlayZombies")?.addEventListener("click", () => { setTab("game"); startZombies(); }, { passive: true });
    q("btnZQuickPlay")?.addEventListener("click", startZombies, { passive: true });
    q("btnZEnterGame")?.addEventListener("click", startZombies, { passive: true });

    // HQ + bot commands
    q("btnZOpenHQ")?.addEventListener("click", () => sendToBot({ type: "nav", action: "zombies_hq" }), { passive: true });
    q("btnOpenZombies")?.addEventListener("click", () => sendToBot({ type: "nav", action: "zombies_open" }), { passive: true });
    q("btnZPerks")?.addEventListener("click", () => sendToBot({ type: "cmd", action: "zombies_perks" }), { passive: true });
    q("btnZLoadout")?.addEventListener("click", () => sendToBot({ type: "cmd", action: "zombies_loadout" }), { passive: true });
    q("btnZEggs")?.addEventListener("click", () => sendToBot({ type: "cmd", action: "zombies_eggs" }), { passive: true });
    q("btnZRound")?.addEventListener("click", () => sendToBot({ type: "cmd", action: "zombies_round" }), { passive: true });
    q("btnZTips")?.addEventListener("click", () => sendToBot({ type: "cmd", action: "zombies_tips" }), { passive: true });

    // send result buttons
    q("btnZGameSend")?.addEventListener("click", () => safe(() => window.BCO_ZOMBIES_GAME?.sendResult?.("manual") || sendToBot({ type: "game", action: "game_result", game: "zombies" })), { passive: true });
    q("btnZGameSend2")?.addEventListener("click", () => safe(() => window.BCO_ZOMBIES_GAME?.sendResult?.("manual") || sendToBot({ type: "game", action: "game_result", game: "zombies" })), { passive: true });

    // hotkey shop preview (safe passthrough)
    q("btnZBuyJug")?.addEventListener("click", () => safe(() => window.BCO_ZOMBIES_GAME?.buyPerk?.("jug") || sendToBot({ type: "cmd", action: "zombies_buy", perk: "jug" })), { passive: true });
    q("btnZBuySpeed")?.addEventListener("click", () => safe(() => window.BCO_ZOMBIES_GAME?.buyPerk?.("speed") || sendToBot({ type: "cmd", action: "zombies_buy", perk: "speed" })), { passive: true });
    q("btnZBuyAmmo")?.addEventListener("click", () => safe(() => window.BCO_ZOMBIES_GAME?.reload?.() || sendToBot({ type: "cmd", action: "zombies_reload" })), { passive: true });

    // Escape/back exit
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && Takeover.isActive()) stopZombies();
    }, { passive: true });

    window.addEventListener("popstate", () => {
      if (Takeover.isActive()) stopZombies();
    });
  }

  // -------------------------
  // Home actions / Premium / Close / Open bot menu
  // -------------------------
  function bindHome() {
    q("btnOpenBot")?.addEventListener("click", () => {
      Toast.show("Open bot menu");
      sendToBot({ type: "nav", action: "open_bot_menu" });
    }, { passive: true });

    q("btnSync")?.addEventListener("click", () => {
      Toast.show("Sync profile → bot");
      sendToBot({ type: "profile", action: "sync_profile" });
    }, { passive: true });

    q("btnPremium")?.addEventListener("click", () => {
      Toast.show("Premium Hub → bot");
      sendToBot({ type: "nav", action: "premium_hub" });
    }, { passive: true });

    q("btnBuyMonth")?.addEventListener("click", () => {
      Toast.show("Buy Month → bot");
      sendToBot({ type: "pay", action: "buy_month" });
    }, { passive: true });

    q("btnBuyLife")?.addEventListener("click", () => {
      Toast.show("Buy Lifetime → bot");
      sendToBot({ type: "pay", action: "buy_lifetime" });
    }, { passive: true });

    q("btnShare")?.addEventListener("click", () => {
      // WebApp share is limited; we just show popup if available
      const url = safe(() => location.href) || "";
      if (TG && TG.showPopup) {
        safe(() => TG.showPopup({ title: "BCO", message: "Скопировать ссылку?", buttons: [{ type: "default", text: "Copy" }, { type: "cancel" }] }, (id) => {
          if (id === "default") safe(() => navigator.clipboard.writeText(url));
        }));
      } else {
        safe(() => navigator.clipboard.writeText(url));
        Toast.show("Copied link");
      }
    }, { passive: true });

    q("btnClose")?.addEventListener("click", () => {
      safe(() => TG?.close?.());
      Toast.show("Close");
    }, { passive: true });
  }

  // -------------------------
  // Coach/VOD buttons (send to bot)
  // -------------------------
  function bindCoachVod() {
    q("btnSendPlan")?.addEventListener("click", () => {
      const focusBtn = qs("#segFocus .seg-btn.active");
      const focus = focusBtn ? (focusBtn.getAttribute("data-value") || "aim") : "aim";
      sendToBot({ type: "cmd", action: "training_plan", focus });
      Toast.show("Plan → bot");
    }, { passive: true });

    q("btnOpenTraining")?.addEventListener("click", () => {
      sendToBot({ type: "nav", action: "open_training" });
      Toast.show("Open training");
    }, { passive: true });

    q("btnSendVod")?.addEventListener("click", () => {
      const v1 = (q("vod1")?.value || "").trim();
      const v2 = (q("vod2")?.value || "").trim();
      const v3 = (q("vod3")?.value || "").trim();
      const note = (q("vodNote")?.value || "").trim();
      sendToBot({ type: "cmd", action: "vod_submit", v1, v2, v3, note });
      Toast.show("VOD → bot");
    }, { passive: true });

    q("btnOpenVod")?.addEventListener("click", () => {
      sendToBot({ type: "nav", action: "open_vod" });
      Toast.show("Open VOD");
    }, { passive: true });
  }

  // -------------------------
  // Diagnostics block
  // -------------------------
  function fillDiagnostics() {
    const st = State.get();

    q("dbgTheme") && (q("dbgTheme").textContent = safe(() => TG?.colorScheme) || "—");
    q("dbgUser") && (q("dbgUser").textContent = safe(() => TG?.initDataUnsafe?.user?.id) || "—");
    q("dbgChat") && (q("dbgChat").textContent = safe(() => TG?.initDataUnsafe?.chat?.id) || "—");
    q("dbgInit") && (q("dbgInit").textContent = (safe(() => TG?.initData) ? "ok" : "—"));

    const buildTag = q("buildTag");
    if (buildTag) buildTag.textContent = "build: " + (window.__BCO_BUILD__ || "—");

    // restore last zombies state UI
    setZModeUI(st.ui.zMode === "roguelike");
    setZMapUI(st.ui.zMap || "Ashes");

    refreshChips();
  }

  // -------------------------
  // Init
  // -------------------------
  function init() {
    setHealth("js: init…");

    // Make sure overlay NEVER blocks UI when not in game
    const mount = q("zOverlayMount");
    if (mount) mount.style.pointerEvents = "none";

    // TG init (keep your chrome hidden like you want)
    safe(() => window.BCO_TG?.hideChrome?.());

    // iOS tap fix (this is the key)
    FastTap.mount();

    // Bind everything back
    bindTabs();
    bindProfileControls();
    bindChat();
    bindHome();
    bindCoachVod();
    bindZombies();

    fillDiagnostics();

    window.__BCO_JS_OK__ = true;
    setHealth("js: OK");
    log("OK: UI restored + iOS tap fixed");
    Toast.show("OK");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }

  // Debug API
  window.BCO_APP = { sendToBot, startZombies, stopZombies, setTab };
})();
