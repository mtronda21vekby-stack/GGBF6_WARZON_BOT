// app/webapp/static/bco.eventbus.js
(() => {
  "use strict";

  window.BCO = window.BCO || {};

  function createBus() {
    const map = new Map();
    return {
      on(evt, fn) {
        const e = String(evt || "");
        if (!map.has(e)) map.set(e, new Set());
        map.get(e).add(fn);
        return () => map.get(e)?.delete(fn);
      },
      emit(evt, payload) {
        const e = String(evt || "");
        const set = map.get(e);
        if (!set || !set.size) return;
        for (const fn of set) {
          try { fn(payload); } catch (err) { console.error("[BCO_BUS]", e, err); }
        }
      }
    };
  }

  window.BCO.bus = window.BCO.bus || createBus();
})();
