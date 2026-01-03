(() => {
  "use strict";

  const { safeJsonParse, safeJsonStringify } = window.BCO_UTILS;

  function createStore(storageKey) {
    const tg = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;

    // CloudStorage wrapper (best-effort)
    const cloud = tg && tg.CloudStorage ? tg.CloudStorage : null;

    const mem = { data: null, loaded: false };

    function _readLocal() {
      const raw = localStorage.getItem(storageKey);
      return safeJsonParse(raw || "{}", {});
    }

    function _writeLocal(obj) {
      localStorage.setItem(storageKey, safeJsonStringify(obj, "{}"));
    }

    async function load() {
      if (mem.loaded) return mem.data;
      let base = _readLocal();

      if (cloud) {
        // best-effort merge: cloud overwrites local keys
        const p = new Promise((resolve) => {
          cloud.getItem(storageKey, (err, val) => {
            if (err || !val) return resolve(null);
            resolve(val);
          });
        });
        const cloudVal = await p;
        const cloudObj = cloudVal ? safeJsonParse(cloudVal, null) : null;
        if (cloudObj && typeof cloudObj === "object") {
          base = { ...base, ...cloudObj };
        }
      }

      mem.data = base;
      mem.loaded = true;
      return mem.data;
    }

    async function save() {
      if (!mem.loaded) await load();
      const obj = mem.data || {};
      _writeLocal(obj);

      if (cloud) {
        await new Promise((resolve) => {
          cloud.setItem(storageKey, safeJsonStringify(obj, "{}"), () => resolve());
        });
      }
    }

    async function get(path, fallback) {
      if (!mem.loaded) await load();
      const parts = String(path || "").split(".").filter(Boolean);
      let cur = mem.data || {};
      for (const k of parts) {
        if (!cur || typeof cur !== "object" || !(k in cur)) return fallback;
        cur = cur[k];
      }
      return cur ?? fallback;
    }

    async function set(path, value) {
      if (!mem.loaded) await load();
      const parts = String(path || "").split(".").filter(Boolean);
      if (parts.length === 0) return;
      let cur = mem.data || (mem.data = {});
      for (let i = 0; i < parts.length - 1; i++) {
        const k = parts[i];
        if (!cur[k] || typeof cur[k] !== "object") cur[k] = {};
        cur = cur[k];
      }
      cur[parts[parts.length - 1]] = value;
      await save();
    }

    async function patch(obj) {
      if (!mem.loaded) await load();
      if (!mem.data || typeof mem.data !== "object") mem.data = {};
      mem.data = { ...mem.data, ...(obj || {}) };
      await save();
    }

    return { load, save, get, set, patch };
  }

  window.BCO_STORE = createStore(window.BCO_CONFIG?.STORAGE_KEY || "bco_state_v1");
})();
