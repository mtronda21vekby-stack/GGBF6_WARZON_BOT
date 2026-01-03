// app/webapp/static/bco.engine.js
(() => {
  "use strict";

  const log = (...a) => { try { console.log("[BCO_ENGINE]", ...a); } catch {} };
  const CFG = window.BCO_CFG || {};
  const ZC = CFG.ZOMBIES || {};
  const ZOOM_BUMP = ZC.ZOOM_BUMP || 0.5;

  function core() { return window.BCO_ZOMBIES_CORE || null; }
  function game() { return window.BCO_ZOMBIES_GAME || null; }

  const Engine = {
    // lifecycle
    start({ mode, w, h, map, character, skin, weaponKey, zoom } = {}) {
      const C = core();
      if (!C || typeof C.start !== "function") return false;
      return !!C.start(mode, w, h, { map, character, skin, weaponKey, zoom });
    },

    stop() { try { return !!core()?.stop?.(); } catch { return false; } },

    resize(w, h) { try { return !!core()?.resize?.(w, h); } catch { return false; } },

    // canvas / loop
    setCanvas(canvas) { try { return !!game()?.setCanvas?.(canvas); } catch { return false; } },
    startLoop() { try { return !!game()?.startLoop?.(); } catch { return false; } },
    stopLoop() { try { return !!game()?.stopLoop?.(); } catch { return false; } },

    setInGame(on) { try { return !!game()?.setInGame?.(on); } catch { return false; } },
    isInGame() { try { return !!game()?.isInGame?.(); } catch { return false; } },

    // input
    setMove(x, y) { try { return !!core()?.setMove?.(x, y); } catch { return false; } },
    setAim(x, y) { try { return !!core()?.setAim?.(x, y); } catch { return false; } },
    setShooting(on) { try { return !!core()?.setShooting?.(on); } catch { return false; } },

    // shop passthrough (roguelike)
    buyUpgrade() { try { return !!core()?.buyUpgrade?.(); } catch { return false; } },
    rerollWeapon() { try { return !!core()?.rerollWeapon?.(); } catch { return false; } },
    buyReload() { try { return !!core()?.buyReload?.(); } catch { return false; } },
    buyPerk(id) { try { return !!core()?.buyPerk?.(id); } catch { return false; } },
    reload() { try { return !!core()?.reload?.(); } catch { return false; } },
    usePlate() { try { return !!core()?.usePlate?.(); } catch { return false; } },

    // zoom contract
    getZoom() { try { return core()?.getZoom?.() ?? 1.0; } catch { return 1.0; } },
    zoomIn() { try { return core()?.setZoomDelta?.(+ZOOM_BUMP) ?? this.getZoom(); } catch { return this.getZoom(); } },
    zoomOut() { try { return core()?.setZoomDelta?.(-ZOOM_BUMP) ?? this.getZoom(); } catch { return this.getZoom(); } },
    setZoomDelta(d) { try { return core()?.setZoomDelta?.(d) ?? this.getZoom(); } catch { return this.getZoom(); } },
    setZoomLevel(z) { try { return core()?.setZoomLevel?.(z) ?? this.getZoom(); } catch { return this.getZoom(); } },

    // snapshot
    getFrame() { try { return core()?.getFrameData?.() ?? null; } catch { return null; } },

    // send result (use GAME helper if exists)
    sendResult(reason) { try { return !!game()?.sendResult?.(reason); } catch { return false; } }
  };

  window.BCO_ENGINE = Engine;
  log("loaded");
})();
