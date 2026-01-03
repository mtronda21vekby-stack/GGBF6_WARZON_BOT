(() => {
  "use strict";

  const TG = window.Telegram?.WebApp || null;

  let currentMap = "Ashes";
  let currentMode = "arcade";

  function qs(id){ return document.getElementById(id); }

  function hideTG(){
    try{
      TG?.ready();
      TG?.expand();
      TG?.MainButton?.hide();
      TG?.BackButton?.hide();
    }catch{}
  }

  function startGame(){
    hideTG();

    const mount = qs("zOverlayMount");
    if (!mount) return;

    mount.style.position = "fixed";
    mount.style.left = "0";
    mount.style.top = "0";
    mount.style.width = "100vw";
    mount.style.height = "100vh";
    mount.style.zIndex = "9999";

    const tms = performance.now();

    // 🔥 КАК БЫЛО: прямой старт CORE
    BCO_ZOMBIES_CORE.start(
      currentMode,
      window.innerWidth,
      window.innerHeight,
      { map: currentMap },
      tms
    );
  }

  function sendResult(){
    try{
      const snap = BCO_ZOMBIES_CORE.getFrameData();
      if (!snap) return;

      TG?.sendData(JSON.stringify({
        action: "game_result",
        game: "zombies",
        mode: currentMode,
        map: currentMap,
        wave: snap.hud?.wave || 0,
        kills: snap.hud?.kills || 0
      }));
    }catch{}
  }

  // ---- UI BIND ----
  qs("btnZMapAshes")?.addEventListener("click",()=>currentMap="Ashes");
  qs("btnZMapAstra")?.addEventListener("click",()=>currentMap="Astra");

  qs("btnZModeArcade")?.addEventListener("click",()=>currentMode="arcade");
  qs("btnZModeRogue")?.addEventListener("click",()=>currentMode="roguelike");

  qs("btnZStart")?.addEventListener("click", startGame);
  qs("btnZSend")?.addEventListener("click", sendResult);

  window.__BCO_JS_OK__ = true;
})();
