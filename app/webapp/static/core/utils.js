(() => {
  "use strict";

  function nowMs() { return Date.now(); }

  function clamp(v, a, b) {
    v = Number(v);
    if (!Number.isFinite(v)) return a;
    return Math.max(a, Math.min(b, v));
  }

  function safeJsonParse(s, fallback) {
    try { return JSON.parse(s); } catch { return fallback; }
  }

  function safeJsonStringify(obj, fallback = "{}") {
    try { return JSON.stringify(obj); } catch { return fallback; }
  }

  function uid(prefix = "id") {
    return `${prefix}_${Math.random().toString(16).slice(2)}_${Date.now().toString(16)}`;
  }

  function isIOS() {
    const ua = navigator.userAgent || "";
    const iOS = /iPad|iPhone|iPod/.test(ua);
    const iPadOS13 = (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
    return iOS || iPadOS13;
  }

  function getTelegram() {
    const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
    return tg;
  }

  function rafThrottle(fn) {
    let scheduled = false;
    let lastArgs = null;
    return function (...args) {
      lastArgs = args;
      if (scheduled) return;
      scheduled = true;
      requestAnimationFrame(() => {
        scheduled = false;
        fn(...(lastArgs || []));
      });
    };
  }

  window.BCO_UTILS = {
    nowMs, clamp, safeJsonParse, safeJsonStringify, uid, isIOS, getTelegram, rafThrottle,
  };
})();
