// app/webapp/static/app.js
// BCO Mini App — CLICK RESTORE (UI untouched)
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
    try { logEl.scrollTop = logEl.scrollHeight; } catch {}
  }

  // ---------- Aim Trial (самодостаточный) ----------
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

  // ---------- Zombies ----------
  function zombiesStartFullscreen() {
    const rt = window.BCO?.zombies?.runtime || window.BCO_ZOMBIES_RUNTIME || null;
    if (rt && typeof rt.startGame === "function") return !!safe(() => rt.startGame());

    const engine = window.BCO?.engine || window.BCO_ENGINE || null;
    if (engine && typeof engine.start === "function") {
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

  function start() {
    setHealth("js: starting…");

    const input = window.BCO?.input || window.BCO_INPUT || null;
    if (input?.mount) safe(() => input.mount());

    const bind = input?.bindClickById
      ? (id, fn) => input.bindClickById(id, fn)
      : (id, fn) => { const el = q(id); if (el) { el.addEventListener("click", fn, { passive: true }); el.addEventListener("touchend", fn, { passive: true }); } };

    // --- CORE buttons ---
    bind("btnOpenBot", () => addChatLine("bot", "✅ btnOpenBot clicked"));
    bind("btnSync", () => addChatLine("bot", "✅ btnSync clicked"));
    bind("btnPremium", () => addChatLine("bot", "✅ btnPremium clicked"));
    bind("btnPlayZombies", () => zombiesStartFullscreen());

    // --- Game tab buttons ---
    bind("btnZEnterGame", () => zombiesStartFullscreen());
    bind("btnZQuickPlay", () => zombiesStartFullscreen());
    bind("btnZOpenHQ", () => addChatLine("bot", "✅ Zombies HQ clicked"));
    bind("btnOpenZombies", () => addChatLine("bot", "✅ Open Zombies clicked"));
    bind("btnZPerks", () => addChatLine("bot", "✅ Perks clicked"));
    bind("btnZLoadout", () => addChatLine("bot", "✅ Loadout clicked"));
    bind("btnZEggs", () => addChatLine("bot", "✅ Eggs clicked"));
    bind("btnZRound", () => addChatLine("bot", "✅ Round clicked"));
    bind("btnZTips", () => addChatLine("bot", "✅ Tips clicked"));

    // --- Chat send ---
    bind("btnChatSend", async () => {
      const inp = q("chatInput");
      const text = inp ? String(inp.value || "").trim() : "";
      if (!text) return;
      if (inp) inp.value = "";
      addChatLine("user", text);
      addChatLine("bot", "✅ Chat handler работает (сервер-мост подключим после стабилизации кликов).");
    });

    // --- Aim Trial ---
    bind("btnAimStart", () => aimStart());
    bind("btnAimStop", () => aimStop());
    bind("btnAimSend", () => addChatLine("bot", "✅ Aim result send clicked"));

    // target hits/misses
    const target = q("aimTarget");
    const arena = q("aimArena");
    if (target) {
      target.addEventListener("click", () => {
        if (!AIM.running) return;
        AIM.hits++;
        aimStat();
        aimMoveTarget();
      }, { passive: true });
      target.addEventListener("touchend", () => {
        if (!AIM.running) return;
        AIM.hits++;
        aimStat();
        aimMoveTarget();
      }, { passive: true });
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
    setHealth("js: OK (click restored)");
    log("click restored");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
