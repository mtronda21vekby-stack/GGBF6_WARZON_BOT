// app/webapp/static/bco.bridge.js
(() => {
  "use strict";

  window.BCO = window.BCO || {};
  const CFG = window.BCO.CONFIG || window.BCO_CONFIG || {};

  const TG = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;

  function safe(fn) { try { return fn(); } catch (_) { return undefined; } }
  function log(...a) { safe(() => console.log("[BCO_BRIDGE]", ...a)); }
  function warn(...a) { safe(() => console.warn("[BCO_BRIDGE]", ...a)); }

  function tgReady() {
    if (!TG) return false;
    safe(() => TG.ready());
    safe(() => TG.expand());
    safe(() => TG.MainButton?.hide?.());
    safe(() => TG.BackButton?.hide?.());
    return true;
  }

  function initData() {
    // initData = криптоподписанная строка, нужна для серверной верификации
    return (TG && TG.initData) ? TG.initData : "";
  }

  function userUnsafe() {
    return (TG && TG.initDataUnsafe) ? TG.initDataUnsafe : {};
  }

  // --- BOT SYNC (fallback / side effects) ---
  function sendToBot(payloadObj) {
    if (!TG || typeof TG.sendData !== "function") return false;
    try {
      const p = { ...payloadObj, _src: "miniapp", _ts: Date.now() };
      TG.sendData(JSON.stringify(p));
      return true;
    } catch (e) {
      warn("sendToBot failed", e);
      return false;
    }
  }

  // --- HTTP BRIDGE (the real “bot inside mini app”) ---
  async function api(path, body) {
    const url = String(path || "").startsWith("/webapp/") ? path : ("/webapp/api/" + String(path || ""));
    const id = initData();
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        // сервер проверит подпись initData, это ключ к “одним целым”
        "X-TG-INITDATA": id
      },
      body: JSON.stringify(body || {})
    });
    const text = await res.text();
    let json = null;
    try { json = JSON.parse(text); } catch { json = { ok: false, error: "bad_json", raw: text }; }
    if (!res.ok) {
      return { ok: false, status: res.status, ...json };
    }
    return json;
  }

  function nav(key, payload) {
    // ✅ ВАЖНО: формат “nav” — стабильный (и сервер, и бот могут понимать)
    return api("nav", { type: "nav", nav: String(key || ""), payload: payload || {} });
  }

  function chat(text, payload) {
    return api("chat", { type: "chat", text: String(text || ""), payload: payload || {} });
  }

  // expose
  window.BCO.bridge = {
    TG,
    tgReady,
    initData,
    userUnsafe,
    api,
    nav,
    chat,
    sendToBot
  };

  log("loaded", { hasTG: !!TG });
})();
