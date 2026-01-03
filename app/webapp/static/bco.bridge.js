/* app/webapp/static/bco.bridge.js */
(() => {
  "use strict";

  function safe(fn) { try { return fn(); } catch (_) { return undefined; } }

  const tg = safe(() => window.Telegram && window.Telegram.WebApp) || null;

  function getInitMeta() {
    const u = tg?.initDataUnsafe || {};
    return {
      user_id: u?.user?.id ?? null,
      chat_id: u?.chat?.id ?? null,
      platform: tg?.platform ?? null,
      colorScheme: tg?.colorScheme ?? null,
      viewport: {
        height: tg?.viewportHeight,
        stable: tg?.viewportStableHeight
      }
    };
  }

  function enrich(payload) {
    const base = {
      v: "bridge-1.0.0",
      t: Date.now(),
      meta: getInitMeta()
    };
    return Object.assign(base, payload || {});
  }

  function sendData(payload) {
    if (!tg?.sendData) {
      console.warn("[BCO BRIDGE] Telegram.WebApp.sendData not available");
      return false;
    }
    const data = enrich(payload);
    let s = "";
    try { s = JSON.stringify(data); }
    catch (e) {
      console.error("[BCO BRIDGE] JSON stringify failed", e);
      return false;
    }

    try {
      tg.sendData(s);
      return true;
    } catch (e) {
      console.error("[BCO BRIDGE] sendData failed", e);
      return false;
    }
  }

  function ready() {
    if (!tg) return false;
    safe(() => tg.ready());
    safe(() => tg.expand());
    return true;
  }

  window.BCO_BRIDGE = {
    tg,
    ready,
    sendData,
    enrich,
    getInitMeta
  };
})();
