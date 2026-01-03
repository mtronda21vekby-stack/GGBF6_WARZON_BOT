// app/webapp/static/bco.input.js
(() => {
  "use strict";

  // BCO INPUT (SAFE MODE)
  // Цель: 100% НЕ ЛОМАТЬ клики в Mini App.
  // - Никаких глобальных preventDefault на pointer/touch
  // - Никаких "ghost-click killer"
  // - Только helper: bindClick(id, fn) + iOS touchend fallback
  //
  // Контракт: UI не меняем. Сначала стабильно вернуть все кнопки.

  window.BCO = window.BCO || {};

  function safe(fn) { try { return fn(); } catch (_) { return undefined; } }

  function bindClick(el, fn) {
    if (!el || !fn) return () => {};

    const handler = (e) => safe(() => fn(e));

    // обычный click (главный)
    el.addEventListener("click", handler, { passive: true });

    // iOS fallback: touchend -> handler
    // ВАЖНО: НЕ preventDefault, иначе убьём скролл/клики.
    el.addEventListener("touchend", handler, { passive: true });

    return () => {
      el.removeEventListener("click", handler);
      el.removeEventListener("touchend", handler);
    };
  }

  function bindClickById(id, fn) {
    const el = document.getElementById(id);
    return bindClick(el, fn);
  }

  function mount() {
    // Ничего не ставим глобально. Только сообщаем, что модуль жив.
    safe(() => console.log("[BCO_INPUT] SAFE mounted (no global intercept)"));
    return true;
  }

  window.BCO.input = {
    mount,
    bindClick,
    bindClickById
  };

  // compatibility
  window.BCO_INPUT = window.BCO.input;
})();
