// app/webapp/static/app.js
(() => {
  "use strict";

  const log = (...a) => { try { console.log("[APP]", ...a); } catch {} };
  const warn = (...a) => { try { console.warn("[APP]", ...a); } catch {} };

  const TG = (window.Telegram && Telegram.WebApp) ? Telegram.WebApp : null;

  function q(id){ return document.getElementById(id); }

  function setHealth(msg){
    const el = q("jsHealth");
    if (el) el.textContent = String(msg || "");
  }

  function safe(fn){ try { return fn(); } catch(e){ return undefined; } }

  function sendToBot(payload){
    if (!TG || !TG.sendData) return false;
    try {
      TG.sendData(JSON.stringify(payload));
      return true;
    } catch {
      return false;
    }
  }

  // -------------------------
  // Minimal tabs (не меняем UI — просто оживляем nav)
  // -------------------------
  function showTab(name){
    const panes = document.querySelectorAll(".tabpane");
    panes.forEach(p => p.classList.remove("active"));
    const el = document.getElementById("tab-" + name);
    if (el) el.classList.add("active");

    const btns = document.querySelectorAll(".bottom-nav .nav-btn");
    btns.forEach(b => b.classList.toggle("active", b.getAttribute("data-tab") === name));
  }

  function bindNav(){
    const nav = document.querySelector(".bottom-nav");
    if (!nav) return;

    nav.addEventListener("click", (e) => {
      const b = e.target && e.target.closest ? e.target.closest(".nav-btn") : null;
      if (!b) return;
      const tab = b.getAttribute("data-tab");
      if (tab) showTab(tab);
    }, { passive: true });
  }

  // -------------------------
  // Zombies запуск: пытаемся через твой legacy стек
  // -------------------------
  function startZombies(){
    // 1) если у тебя есть BCO.zombies.runtime
    const rt = window.BCO?.zombies?.runtime;
    if (rt && typeof rt.startGame === "function") return rt.startGame();

    // 2) если есть BCO.engine.start({mode,map})
    const eng = window.BCO?.engine || window.BCO_ENGINE || null;
    if (eng && typeof eng.start === "function") {
      return !!safe(() => eng.start({ mode: "arcade", map: "Ashes" }));
    }

    // 3) если есть legacy core + game runner — стартуем самым простым способом
    const core = window.BCO_ZOMBIES_CORE || null;
    const game = window.BCO_ZOMBIES_GAME || null;
    const mount = q("zOverlayMount");
    if (core && game && mount) {
      let c = mount.querySelector("#bcoZCanvas");
      if (!c) {
        c = document.createElement("canvas");
        c.id = "bcoZCanvas";
        c.style.position = "fixed";
        c.style.left = "0";
        c.style.top = "0";
        c.style.width = "100vw";
        c.style.height = "100vh";
        c.style.zIndex = "9999";
        c.style.background = "transparent";
        c.style.pointerEvents = "auto";
        mount.appendChild(c);
      }

      safe(() => TG?.MainButton?.hide?.());
      safe(() => TG?.BackButton?.hide?.());
      safe(() => TG?.expand?.());

      const tms = (performance && performance.now) ? performance.now() : Date.now();
      // start(mode, w, h, opts, tms)
      safe(() => core.start?.("arcade", window.innerWidth, window.innerHeight, { map: "Ashes" }, tms));

      safe(() => game.setCanvas(c));
      safe(() => game.setInGame(true));
      const ok = safe(() => game.startLoop());
      return !!ok;
    }

    warn("Zombies start failed: modules missing");
    setHealth("js: Zombies modules missing");
    return false;
  }

  function bindButtons(){
    q("btnZEnterGame")?.addEventListener("click", () => {
      showTab("game");
      const ok = startZombies();
      setHealth(ok ? "js: Zombies started" : "js: start failed");
    }, { passive: true });

    q("btnPlayZombies")?.addEventListener("click", () => {
      showTab("game");
      const ok = startZombies();
      setHealth(ok ? "js: Zombies started" : "js: start failed");
    }, { passive: true });

    q("btnZGameSend2")?.addEventListener("click", () => {
      const ok = sendToBot({ action: "game_result", game: "zombies", reason: "manual_send" });
      setHealth(ok ? "js: sent → bot" : "js: sendData failed");
    }, { passive: true });

    q("btnOpenBot")?.addEventListener("click", () => {
      const ok = sendToBot({ type: "nav", action: "open_bot_menu" });
      setHealth(ok ? "js: nav → bot" : "js: sendData failed");
    }, { passive: true });
  }

  function init(){
    safe(() => TG?.ready?.());
    safe(() => TG?.expand?.());
    safe(() => window.BCO_TG?.hideChrome?.());

    bindNav();
    bindButtons();

    window.__BCO_JS_OK__ = true;
    setHealth("js: OK (app alive)");
    log("app init ok");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
