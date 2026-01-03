(() => {
  "use strict";

  function createEventBus() {
    const map = new Map(); // event -> Set(fn)

    function on(event, fn) {
      if (!map.has(event)) map.set(event, new Set());
      map.get(event).add(fn);
      return () => off(event, fn);
    }

    function off(event, fn) {
      const set = map.get(event);
      if (!set) return;
      set.delete(fn);
      if (set.size === 0) map.delete(event);
    }

    function emit(event, payload) {
      const set = map.get(event);
      if (!set) return;
      for (const fn of Array.from(set)) {
        try { fn(payload); } catch (e) { (window.BCO_LOG || console).error("EventBus handler error", event, e); }
      }
    }

    return { on, off, emit };
  }

  window.BCO_EVENTBUS = createEventBus();
})();
