/* app/webapp/static/bco.engine.js */
(() => {
  "use strict";

  const safe = (fn) => { try { return fn(); } catch (_) { return undefined; } };

  function pickZombies() {
    // поддерживаем любые твои текущие глобалы
    return window.BCO_ZOMBIES || window.BCO_ZOMBIES_CORE || window.BCO_Z || null;
  }

  const zombies = {
    setMode(mode) {
      const z = pickZombies();
      if (!z) return false;
      safe(() => z.setMode?.(mode));
      safe(() => z.mode?.(mode));
      return true;
    },
    enter({ map = "Ashes", mode = "arcade", onExit } = {}) {
      const z = pickZombies();
      if (!z) return false;

      // пробуем “лучшие” сигнатуры
      const ok =
        safe(() => z.enter?.({ map, mode, onExit })) ??
        safe(() => z.open?.({ map, mode, onExit })) ??
        safe(() => z.start?.({ map, mode, onExit })) ??
        safe(() => z.start?.(mode));

      // если движок умеет — зарегистрируем выход
      safe(() => z.onExit?.(onExit));
      safe(() => z.setOnExit?.(onExit));

      return ok !== false;
    }
  };

  window.BCO_ENGINE = {
    zombies
  };
})();
