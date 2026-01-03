// app/webapp/static/bco.eventbus.js
(() => {
  "use strict";

  function now() {
    return (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now();
  }

  const BUS = {
    _m: new Map(),        // event -> Set(fn)
    _any: new Set(),      // wildcard listeners
    _last: new Map(),     // event -> payload (for late subscribers)
    _stats: { emits: 0, subs: 0 },

    on(evt, fn, opts = {}) {
      if (typeof fn !== "function") return () => {};
      const e = String(evt || "");
      const replay = !!opts.replayLast;

      if (e === "*" || e === "any") {
        this._any.add(fn);
        this._stats.subs++;
        if (replay) {
          try {
            for (const [k, v] of this._last.entries()) fn({ type: k, payload: v, t: now(), replay: true });
          } catch {}
        }
        return () => { this._any.delete(fn); };
      }

      let set = this._m.get(e);
      if (!set) { set = new Set(); this._m.set(e, set); }
      set.add(fn);
      this._stats.subs++;

      if (replay && this._last.has(e)) {
        try { fn(this._last.get(e)); } catch {}
      }

      return () => {
        try {
          const s = this._m.get(e);
          if (s) s.delete(fn);
        } catch {}
      };
    },

    once(evt, fn) {
      const off = this.on(evt, (p) => { try { off(); } catch {} try { fn(p); } catch {} });
      return off;
    },

    emit(evt, payload) {
      const e = String(evt || "");
      this._stats.emits++;
      this._last.set(e, payload);

      const msgAny = { type: e, payload, t: now() };

      try {
        for (const fn of this._any) { try { fn(msgAny); } catch {} }
      } catch {}

      try {
        const set = this._m.get(e);
        if (!set) return true;
        for (const fn of set) { try { fn(payload); } catch {} }
      } catch {}

      return true;
    },

    last(evt) {
      const e = String(evt || "");
      return this._last.get(e);
    },

    stats() {
      return { ...this._stats, events: this._m.size, any: this._any.size };
    }
  };

  window.BCO_EVENTBUS = BUS;
  console.log("[BCO] eventbus ready");
})();
