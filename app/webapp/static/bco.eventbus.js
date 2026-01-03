// app/webapp/static/bco.eventbus.js
(() => {
  "use strict";

  const Bus = {
    _map: new Map(),

    on(evt, fn) {
      if (typeof fn !== "function") return () => {};
      const key = String(evt || "");
      if (!this._map.has(key)) this._map.set(key, new Set());
      this._map.get(key).add(fn);
      return () => { try { this._map.get(key)?.delete(fn); } catch {} };
    },

    emit(evt, payload) {
      const key = String(evt || "");
      const set = this._map.get(key);
      if (!set || !set.size) return 0;
      let n = 0;
      for (const fn of set) {
        try { fn(payload); n++; } catch {}
      }
      return n;
    }
  };

  window.BCO_BUS = Bus;
  console.log("[BCO_BUS] loaded");
})();
