/* BLACK CROWN OPS — v18 boot coordinator */
(() => {
  "use strict";

  if (window.__BCO_APP_COORDINATOR__) return;
  window.__BCO_APP_COORDINATOR__ = true;

  const build = String(window.__BCO_BUILD__ || "dev");

  function loadScript(src, marker) {
    if (marker && window[marker]) return Promise.resolve(true);
    return new Promise((resolve, reject) => {
      const existing = document.querySelector(`script[data-bco-src="${src}"]`);
      if (existing) {
        existing.addEventListener("load", () => resolve(true), { once: true });
        existing.addEventListener("error", () => reject(new Error(`Failed: ${src}`)), { once: true });
        return;
      }
      const script = document.createElement("script");
      script.src = `${src}?build=${encodeURIComponent(build)}`;
      script.async = false;
      script.dataset.bcoSrc = src;
      script.onload = () => resolve(true);
      script.onerror = () => reject(new Error(`Failed: ${src}`));
      document.body.appendChild(script);
    });
  }

  window.__BCO_APP_BOOT_PROMISE__ = loadScript("/webapp/app.base.js", "__BCO_APP_BASE_LOADED__")
    .then(() => {
      window.__BCO_APP_BASE_LOADED__ = true;
      return loadScript("/webapp/bco.live.js", "__BCO_LIVE_LAYER_LOADED__");
    })
    .then(() => {
      window.__BCO_LIVE_LAYER_LOADED__ = true;
      window.__BCO_V18_READY__ = true;
      return true;
    })
    .catch((error) => {
      window.__BCO_V18_READY__ = false;
      console.error("[BCO v18] boot coordinator failed", error);
      throw error;
    });
})();
