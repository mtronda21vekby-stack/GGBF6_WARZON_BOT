/* BLACK CROWN OPS — boot coordinator (ecosystem i18n + accumulated intelligence layers) */
(() => {
  "use strict";
  if (window.__BCO_APP_COORDINATOR__) return;
  window.__BCO_APP_COORDINATOR__ = true;
  const build = String(window.__BCO_BUILD__ || "dev");
  function loadScript(src, marker) {
    if (marker && window[marker]) return Promise.resolve(true);
    return new Promise((resolve,reject)=>{ const existing=document.querySelector(`script[data-bco-src="${src}"]`); if(existing){existing.addEventListener("load",()=>resolve(true),{once:true});existing.addEventListener("error",()=>reject(new Error(`Failed: ${src}`)),{once:true});return;} const script=document.createElement("script");script.src=`${src}?build=${encodeURIComponent(build)}`;script.async=false;script.dataset.bcoSrc=src;script.onload=()=>resolve(true);script.onerror=()=>reject(new Error(`Failed: ${src}`));document.body.appendChild(script); });
  }
  async function loadRuntimeFlags(){
    const controller=new AbortController(); const timeout=window.setTimeout(()=>controller.abort(),3500);
    try {
      const response=await fetch(`/webapp/api/runtime?build=${encodeURIComponent(build)}`, { method: "POST", cache: "no-store", credentials: "same-origin", signal: controller.signal });
      if(!response.ok) throw new Error(`runtime HTTP ${response.status}`);
      const payload=await response.json(); const flags=payload&&payload.webapp?payload.webapp:{}; window.__BCO_RUNTIME_FLAGS__=flags; return flags;
    } catch(error) {
      const fallback={live_stream:true,cinematic_ui:true,v18_overlay:true,transport:"ndjson",runtime_unavailable:true}; window.__BCO_RUNTIME_FLAGS__=fallback; console.warn("[BCO] runtime capability check unavailable",error); return fallback;
    } finally { window.clearTimeout(timeout); }
  }
  window.__BCO_APP_BOOT_PROMISE__ = loadScript("/webapp/bco.i18n.js","__BCO_I18N_V38_LOADED__")
    .catch((error)=>{console.warn("[BCO v38] i18n coordinator unavailable; base UI remains active",error);return false;})
    .then(()=>Promise.all([loadScript("/webapp/app.base.js","__BCO_APP_BASE_LOADED__"),loadRuntimeFlags()]))
    .then(([, flags]) => {
      window.__BCO_APP_BASE_LOADED__ = true;
      if (flags.v18_overlay === false) { window.__BCO_LIVE_LAYER_LOADED__=false; window.__BCO_V18_READY__=false; return false; }
      return loadScript("/webapp/bco.live.js", "__BCO_LIVE_LAYER_LOADED__");
    })
    .then((loaded)=>{ if(loaded!==false){window.__BCO_LIVE_LAYER_LOADED__=true;window.__BCO_V18_READY__=true;} return loadScript("/webapp/bco.crown-session.js","__BCO_CROWN_SESSION_V45_LOADED__").catch((error)=>{console.warn("[BCO v45] CROWN SESSION unavailable",error);return false;}); })
    .then(()=>loadScript("/webapp/bco.profile-projection.js","__BCO_PROFILE_PROJECTION_V49_LOADED__").catch((error)=>{console.warn("[BCO v49] profile projection unavailable",error);return false;}))
    .then(()=>loadScript("/webapp/bco.session-home.js","__BCO_SESSION_HOME_V45_LOADED__").catch(()=>false))
    .then(()=>loadScript("/webapp/bco.after-action.js","__BCO_AFTER_ACTION_V48_LOADED__").catch(()=>false))
    .then(()=>loadScript("/webapp/bco.operator.js","__BCO_OPERATOR_V25_LOADED__").catch(()=>false))
    .then(()=>loadScript("/webapp/bco.war-room.js","__BCO_WAR_ROOM_V44_LOADED__").catch(()=>false))
    .then(()=>loadScript("/webapp/bco.orchestrator.js","__BCO_MISSION_ORCHESTRATOR_V36_LOADED__").catch(()=>false))
    .then(()=>loadScript("/webapp/bco.deep-history.js","__BCO_DEEP_HISTORY_V29_LOADED__").catch(()=>false))
    .then(()=>loadScript("/webapp/bco.strategy.js","__BCO_STRATEGY_V35_LOADED__").catch(()=>false))
    .then(()=>loadScript("/webapp/bco.ecosystem-shell.js","__BCO_ECOSYSTEM_SHELL_V49_LOADED__").catch((error)=>{console.warn("[BCO v49] ecosystem shell unavailable",error);return false;}))
    .then(()=>loadScript("/webapp/bco.ecosystem-parity.js","__BCO_ECOSYSTEM_PARITY_V49_LOADED__").catch(()=>false))
    .then(()=>loadScript("/webapp/bco.aaa-surfaces.js","__BCO_AAA_SURFACES_V50__").catch((error)=>{console.warn("[BCO v50] AAA surfaces unavailable",error);return false;}))
    .then(()=>loadScript("/webapp/bco.home-v50.js","__BCO_HOME_V50__").catch((error)=>{console.warn("[BCO v50] cinematic home unavailable",error);return false;}))
    .then(()=>{try{window.BCO_I18N?.apply();}catch(_){}return true;})
    .catch((error)=>{window.__BCO_V18_READY__=false;console.error("[BCO] boot coordinator failed",error);throw error;});
})();
