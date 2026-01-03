// app/webapp/static/bco.store.js
(() => {
  "use strict";

  window.BCO = window.BCO || {};
  const CFG = window.BCO.CONFIG || { STORAGE_KEY: "bco_state_v1" };
  const KEY = CFG.STORAGE_KEY;

  const safeParse = (s, fb) => { try { return JSON.parse(s); } catch { return fb; } };
  const safeStr = (o, fb = "{}") => { try { return JSON.stringify(o); } catch { return fb; } };

  function tg() {
    return (window.Telegram && Telegram.WebApp) ? Telegram.WebApp : null;
  }

  async function load() {
    let base = safeParse(localStorage.getItem(KEY) || "{}", {});
    const wa = tg();
    if (wa && wa.CloudStorage) {
      const cloudVal = await new Promise((resolve) => {
        wa.CloudStorage.getItem(KEY, (err, val) => resolve(err ? null : val));
      });
      const cloudObj = cloudVal ? safeParse(cloudVal, null) : null;
      if (cloudObj && typeof cloudObj === "object") base = { ...base, ...cloudObj };
    }
    return base;
  }

  async function save(obj) {
    localStorage.setItem(KEY, safeStr(obj, "{}"));
    const wa = tg();
    if (wa && wa.CloudStorage) {
      await new Promise((resolve) => {
        wa.CloudStorage.setItem(KEY, safeStr(obj, "{}"), () => resolve(true));
      });
    }
    return true;
  }

  function getPath(obj, path, fb) {
    const parts = String(path || "").split(".").filter(Boolean);
    let cur = obj;
    for (const k of parts) {
      if (!cur || typeof cur !== "object" || !(k in cur)) return fb;
      cur = cur[k];
    }
    return (cur === undefined) ? fb : cur;
  }

  function setPath(obj, path, value) {
    const parts = String(path || "").split(".").filter(Boolean);
    if (!parts.length) return obj;
    let cur = obj;
    for (let i = 0; i < parts.length - 1; i++) {
      const k = parts[i];
      if (!cur[k] || typeof cur[k] !== "object") cur[k] = {};
      cur = cur[k];
    }
    cur[parts[parts.length - 1]] = value;
    return obj;
  }

  const store = {
    async get(path, fb) {
      const obj = await load();
      return getPath(obj, path, fb);
    },
    async set(path, value) {
      const obj = await load();
      setPath(obj, path, value);
      await save(obj);
      return true;
    },
    async patch(p) {
      const obj = await load();
      const merged = { ...obj, ...(p || {}) };
      await save(merged);
      return true;
    }
  };

  window.BCO.store = store;
})();
