/* BLACK CROWN OPS — v19 boot coordinator */
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
        if (existing.dataset.bcoLoaded === "1") return resolve(true);
        existing.addEventListener("load", () => resolve(true), { once: true });
        existing.addEventListener("error", () => reject(new Error(`Failed: ${src}`)), { once: true });
        return;
      }
      const script = document.createElement("script");
      script.src = `${src}?build=${encodeURIComponent(build)}`;
      script.async = false;
      script.dataset.bcoSrc = src;
      script.onload = () => {
        script.dataset.bcoLoaded = "1";
        resolve(true);
      };
      script.onerror = () => reject(new Error(`Failed: ${src}`));
      document.body.appendChild(script);
    });
  }

  async function loadRuntimeFlags() {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 3500);
    try {
      const response = await fetch(`/webapp/api/runtime?build=${encodeURIComponent(build)}`, {
        method: "POST",
        cache: "no-store",
        credentials: "same-origin",
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`runtime HTTP ${response.status}`);
      const payload = await response.json();
      const flags = payload && payload.webapp ? payload.webapp : {};
      window.__BCO_RUNTIME_FLAGS__ = flags;
      return flags;
    } catch (error) {
      // Fail open: each presentation layer has its own trusted server boundary
      // and stable fallback. Runtime flags can still disable it in production.
      const fallback = {
        live_stream: true,
        cinematic_ui: true,
        v18_overlay: true,
        adaptive_mission_control: true,
        transport: "ndjson",
        runtime_unavailable: true,
      };
      window.__BCO_RUNTIME_FLAGS__ = fallback;
      console.warn("[BCO v19] runtime capability check unavailable", error);
      return fallback;
    } finally {
      window.clearTimeout(timeout);
    }
  }

  window.__BCO_APP_BOOT_PROMISE__ = Promise.all([
    loadScript("/webapp/app.base.js", "__BCO_APP_BASE_LOADED__"),
    loadRuntimeFlags(),
  ])
    .then(async ([, flags]) => {
      window.__BCO_APP_BASE_LOADED__ = true;
      if (flags && flags.v18_overlay === false) {
        window.__BCO_LIVE_LAYER_LOADED__ = false;
        window.__BCO_V18_READY__ = false;
      } else {
        await loadScript("/webapp/bco.live.js", "__BCO_LIVE_LAYER_LOADED__");
        window.__BCO_LIVE_LAYER_LOADED__ = true;
        window.__BCO_V18_READY__ = true;
      }

      if (!flags || flags.adaptive_mission_control !== false) {
        await loadScript("/webapp/command-center.js", "__BCO_COMMAND_CENTER_V19_LOADED__");
        window.__BCO_COMMAND_CENTER_V19_LOADED__ = true;
      } else {
        window.__BCO_COMMAND_CENTER_V19_LOADED__ = false;
      }
      window.__BCO_V19_READY__ = true;
      return true;
    })
    .catch((error) => {
      window.__BCO_V19_READY__ = false;
      console.error("[BCO v19] boot coordinator failed", error);
      throw error;
    });
})();
