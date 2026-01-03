// app/webapp/static/zombies.runtime.js
// vNext runtime: orchestrates takeover, canvas mount, input pump, mode policy.
// UI visually unchanged: mounts only inside #zOverlayMount.
(() => {
  "use strict";

  const CFG = window.BCO_CFG || {};
  const ZC = CFG.ZOMBIES || {};
  const DEADZONE = ZC.DEADZONE || 0.10;
  const AIM_DEADZONE = ZC.AIM_DEADZONE || 0.06;

  const log = (...a) => { try { console.log("[Z_RUNTIME]", ...a); } catch {} };
  const warn = (...a) => { try { console.warn("[Z_RUNTIME]", ...a); } catch {} };

  const Engine = () => window.BCO_ENGINE || null;
  const Store = () => window.BCO_STORE || null;

  const TG = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;

  const STATE = {
    inGame: false,
    canvas: null,
    mount: null,
    // dual-stick state
    left: { active: false, id: -1, x0: 0, y0: 0, x: 0, y: 0 },
    right:{ active: false, id: -1, x0: 0, y0: 0, x: 0, y: 0 },
    // area split
    splitX: 0.5, // left/right half
  };

  function mountRoot() {
    if (STATE.mount) return STATE.mount;
    const m = document.getElementById("zOverlayMount");
    STATE.mount = m || null;
    return STATE.mount;
  }

  // Create canvas ONLY inside overlay mount (no visual layout changes to main UI)
  function ensureCanvas() {
    if (STATE.canvas) return STATE.canvas;

    const mount = mountRoot();
    if (!mount) return null;

    // try reuse existing
    let c = mount.querySelector("canvas#bcoZCanvas");
    if (!c) {
      c = document.createElement("canvas");
      c.id = "bcoZCanvas";
      c.setAttribute("aria-label", "Zombies canvas");
      // keep styling minimal, controlled by existing CSS/overlay; do not change overall UI
      c.style.width = "100%";
      c.style.height = "100%";
      c.style.display = "block";
      c.style.touchAction = "none";
      c.style.webkitUserSelect = "none";
      c.style.userSelect = "none";
      mount.appendChild(c);
    }
    STATE.canvas = c;
    return c;
  }

  function dz(x, y, d) {
    const L = Math.hypot(x, y) || 0;
    if (L < d) return { x: 0, y: 0, L };
    return { x: x / L, y: y / L, L };
  }

  function setTakeover(on) {
    STATE.inGame = !!on;

    // Tell Engine/Game for gesture guard logic
    try { Engine()?.setInGame?.(STATE.inGame); } catch {}

    // TG chrome hide/show is *allowed* as bugfix (fullscreen)
    try {
      if (STATE.inGame) window.BCO_TG?.hideChrome?.();
      else window.BCO_TG?.showChrome?.();
    } catch {}

    // Body flag (no visual redesign; helps CSS target if you already have it)
    try { document.body.classList.toggle("bco-in-game", STATE.inGame); } catch {}

    return STATE.inGame;
  }

  function isInGame() { return !!STATE.inGame; }

  function startGame({ mode, map } = {}) {
    const st = Store()?.load?.() || {};
    const z = st.zombies || {};

    const m = String(mode || z.mode || "arcade").toLowerCase();
    const useMode = (m.includes("rogue")) ? "roguelike" : "arcade";

    const useMap = String(map || z.map || "Ashes");
    const zoom = (z.zoom != null) ? Number(z.zoom) : 1.0;

    const character = String(z.character || "male");
    const skin = String(z.skin || "default");

    const canvas = ensureCanvas();
    if (!canvas) { warn("no mount/canvas"); return false; }

    // takeover first (prevents iOS scroll/zoom issues)
    setTakeover(true);

    // bind canvas to runner
    Engine()?.setCanvas?.(canvas);

    // core start uses css size
    const rect = canvas.getBoundingClientRect();
    const w = Math.max(1, Math.floor(rect.width || window.innerWidth || 1));
    const h = Math.max(1, Math.floor(rect.height || window.innerHeight || 1));

    const ok = Engine()?.start?.({
      mode: useMode,
      w, h,
      map: useMap,
      character,
      skin,
      zoom
    });

    if (!ok) { warn("core start failed"); return false; }

    // loop
    Engine()?.startLoop?.();

    // persist selected
    Store()?.patch?.((s) => {
      s.zombies = s.zombies || {};
      s.zombies.mode = useMode;
      s.zombies.map = useMap;
      s.zombies.zoom = Engine()?.getZoom?.() ?? zoom;
      s.zombies.character = character;
      s.zombies.skin = skin;
      return s;
    });

    log("startGame", useMode, useMap, "zoom:", Engine()?.getZoom?.());
    return true;
  }

  function stopGame() {
    try { Engine()?.stopLoop?.(); } catch {}
    try { Engine()?.stop?.(); } catch {}
    setTakeover(false);

    // clear stick states
    STATE.left.active = false; STATE.right.active = false;
    STATE.left.id = -1; STATE.right.id = -1;

    log("stopGame");
    return true;
  }

  // Dual-stick pointer assignment:
  // - left half => move stick
  // - right half => aim stick + shooting (hold)
  function installDualStick() {
    const PR = window.BCO_INPUT?.PointerRouter;
    if (!PR) return false;

    const sub = PR.install();
    const un = sub.on((p) => {
      if (!STATE.inGame) return;

      const w = window.innerWidth || 1;
      const isLeft = (p.x / w) < STATE.splitX;

      if (p.type === "down") {
        if (isLeft && !STATE.left.active) {
          STATE.left.active = true;
          STATE.left.id = p.pointerId;
          STATE.left.x0 = p.x; STATE.left.y0 = p.y;
          STATE.left.x = p.x; STATE.left.y = p.y;
          return;
        }
        if (!isLeft && !STATE.right.active) {
          STATE.right.active = true;
          STATE.right.id = p.pointerId;
          STATE.right.x0 = p.x; STATE.right.y0 = p.y;
          STATE.right.x = p.x; STATE.right.y = p.y;
          // right stick implies shooting hold
          try { Engine()?.setShooting?.(true); } catch {}
          return;
        }
      }

      if (p.type === "move") {
        if (STATE.left.active && p.pointerId === STATE.left.id) {
          STATE.left.x = p.x; STATE.left.y = p.y;
          return;
        }
        if (STATE.right.active && p.pointerId === STATE.right.id) {
          STATE.right.x = p.x; STATE.right.y = p.y;
          return;
        }
      }

      if (p.type === "up" || p.type === "cancel") {
        if (STATE.left.active && p.pointerId === STATE.left.id) {
          STATE.left.active = false;
          STATE.left.id = -1;
          try { Engine()?.setMove?.(0, 0); } catch {}
          return;
        }
        if (STATE.right.active && p.pointerId === STATE.right.id) {
          STATE.right.active = false;
          STATE.right.id = -1;
          try { Engine()?.setShooting?.(false); } catch {}
          return;
        }
      }
    });

    // pump to engine at animation cadence using requestAnimationFrame
    function pump() {
      if (STATE.inGame) {
        // Move
        if (STATE.left.active) {
          const dx = (STATE.left.x - STATE.left.x0);
          const dy = (STATE.left.y - STATE.left.y0);
          const n = dz(dx, dy, DEADZONE * 40); // scale deadzone for pixels
          try { Engine()?.setMove?.(n.x, n.y); } catch {}
        }

        // Aim
        if (STATE.right.active) {
          const dx = (STATE.right.x - STATE.right.x0);
          const dy = (STATE.right.y - STATE.right.y0);
          const n = dz(dx, dy, AIM_DEADZONE * 30);
          if (n.L > 0) {
            try { Engine()?.setAim?.(n.x, n.y); } catch {}
          }
        }
      }
      requestAnimationFrame(pump);
    }
    requestAnimationFrame(pump);

    log("dual-stick installed");
    return () => { try { un(); } catch {} };
  }

  // Zoom helpers (contract +0.5)
  function zoomIn() {
    const z = Engine()?.zoomIn?.();
    Store()?.patch?.((s) => { s.zombies = s.zombies || {}; s.zombies.zoom = z; return s; });
    return z;
  }
  function zoomOut() {
    const z = Engine()?.zoomOut?.();
    Store()?.patch?.((s) => { s.zombies = s.zombies || {}; s.zombies.zoom = z; return s; });
    return z;
  }

  // Public API
  window.BCO_Z_RUNTIME = {
    startGame,
    stopGame,
    isInGame,
    setTakeover,
    ensureCanvas,
    installDualStick,
    zoomIn,
    zoomOut
  };

  console.log("[Z_RUNTIME] loaded");
})();
