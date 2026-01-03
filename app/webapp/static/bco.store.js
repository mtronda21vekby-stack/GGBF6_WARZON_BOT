// app/webapp/static/bco.store.js
(() => {
  "use strict";

  const CFG = window.BCO_CFG || { STORAGE_KEY: "bco_state_v1" };

  function safeParse(s, fallback) {
    try { return JSON.parse(s); } catch { return fallback; }
  }

  const Store = {
    load() {
      const raw = localStorage.getItem(CFG.STORAGE_KEY);
      const st = safeParse(raw, null) || {};
      // minimal defaults (do not override user state)
      if (!st.profile) st.profile = {};
      if (!st.profile.voice) st.profile.voice = (CFG.DEFAULT_VOICE || "TEAMMATE");
      if (!st.profile.mode) st.profile.mode = "Normal";
      if (!st.profile.platform) st.profile.platform = "PC";
      if (!st.profile.input) st.profile.input = "Controller";
      if (!st.profile.game) st.profile.game = "Warzone";
      if (!st.profile.role) st.profile.role = "Flex";
      if (!st.profile.bf6_class) st.profile.bf6_class = "Assault";

      if (!st.zombies) st.zombies = {};
      if (!st.zombies.map) st.zombies.map = "Ashes";
      if (!st.zombies.mode) st.zombies.mode = "arcade";
      if (st.zombies.zoom == null) st.zombies.zoom = 1.0;
      if (!st.zombies.character) st.zombies.character = "male";
      if (!st.zombies.skin) st.zombies.skin = "default";

      return st;
    },

    save(state) {
      try {
        localStorage.setItem(CFG.STORAGE_KEY, JSON.stringify(state || {}));
        return true;
      } catch {
        return false;
      }
    },

    patch(mutator) {
      const st = Store.load();
      const next = (typeof mutator === "function") ? (mutator(st) || st) : st;
      Store.save(next);
      return next;
    }
  };

  window.BCO_STORE = Store;
  console.log("[BCO_STORE] loaded");
})();
