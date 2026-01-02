/* =========================================================
   BLACK CROWN OPS — ZOMBIES GAME (UI + RENDER + INPUT)  [LUX]
   File: app/webapp/static/zombies.game.js
   Requires:
     - zombies.core.js
     - zombies.render.js
     - zombies.assets.js (optional)
     - zombies.world.js (optional)
   Provides:
     - window.BCO_ZOMBIES_GAME

   LUX upgrades (NO UI redesign, only behavior/system fixes):
     ✅ iOS WebView hardening: no dead taps, stable pointer capture, no scroll/zoom/pinch
     ✅ Fullscreen Takeover helpers (best-effort): Telegram expand + scroll lock + viewport fit
     ✅ Dual-stick true: right stick = aim; FIRE = hold-to-shoot handled by stick; no “position bug”
     ✅ Roguelike actually works: uses CORE.setMode() if exists; start() uses CORE.start(mode,..) which sets mode
     ✅ Shop + upgrades always clickable (z-order/pointer-events fix), overlay never blocks
     ✅ HUD richer + 3D-ready snapshots access (CORE.getFrameData if exists)
     ✅ Backwards compatible: if CORE missing methods, soft fallback
     ✅ 3D-ready: exposes getSnapshot(), getInput(), setInput(), onSnapshot(cb), can be used by 3D renderer later
   ========================================================= */
(() => {
  "use strict";

  const CORE = window.BCO_ZOMBIES_CORE;
  const RENDER = window.BCO_ZOMBIES_RENDER;

  if (!CORE || !RENDER) {
    console.error("[Z_GAME] core/render missing");
    return;
  }

  const tg = window.Telegram?.WebApp || null;

  const mount = () => document.getElementById("zOverlayMount") || document.body;

  // ---------------------------------------------------------
  // UI State
  // ---------------------------------------------------------
  let overlay = null;
  let canvas = null;
  let ctx = null;
  let raf = 0;
  let dpr = 1;

  // internal snapshot bus (3D-ready)
  let _snapCb = null;
  let _lastSnap = null;

  // input mirror (renderer/controls + 3D)
  const input = {
    moveX: 0, moveY: 0,
    aimX: 1, aimY: 0,
    firing: false
  };

  // ---------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------
  function haptic(type = "impact", style = "light") {
    try {
      if (!tg?.HapticFeedback) return;
      if (type === "impact") tg.HapticFeedback.impactOccurred(style);
      if (type === "notif") tg.HapticFeedback.notificationOccurred(style);
    } catch {}
  }

  function safeSendData(obj) {
    try {
      if (!tg?.sendData) return false;
      const s = JSON.stringify(obj);
      if (s.length > 15000) return false;
      tg.sendData(s);
      return true;
    } catch { return false; }
  }

  function cssSafe() {
    const top = `max(env(safe-area-inset-top), 0px)`;
    const bot = `max(env(safe-area-inset-bottom), 0px)`;
    const left = `max(env(safe-area-inset-left), 0px)`;
    const right = `max(env(safe-area-inset-right), 0px)`;
    return { top, bot, left, right };
  }

  // Prevent document scroll / overscroll (iOS dead taps fix)
  let _scrollLocked = false;
  let _prevOverflow = "";
  let _prevOverscroll = "";
  let _prevTouchAction = "";
  let _prevScrollY = 0;

  function lockScroll() {
    if (_scrollLocked) return;
    _scrollLocked = true;

    try {
      _prevOverflow = document.documentElement.style.overflow;
      _prevOverscroll = document.documentElement.style.overscrollBehavior;
      _prevTouchAction = document.documentElement.style.touchAction;
      _prevScrollY = window.scrollY || 0;

      document.documentElement.style.overflow = "hidden";
      document.documentElement.style.overscrollBehavior = "none";
      document.documentElement.style.touchAction = "none";

      document.body.style.overflow = "hidden";
      document.body.style.overscrollBehavior = "none";
      document.body.style.touchAction = "none";

      // keep page at top to avoid rubber band
      window.scrollTo(0, _prevScrollY);
    } catch {}
  }

  function unlockScroll() {
    if (!_scrollLocked) return;
    _scrollLocked = false;

    try {
      document.documentElement.style.overflow = _prevOverflow || "";
      document.documentElement.style.overscrollBehavior = _prevOverscroll || "";
      document.documentElement.style.touchAction = _prevTouchAction || "";

      document.body.style.overflow = "";
      document.body.style.overscrollBehavior = "";
      document.body.style.touchAction = "";

      window.scrollTo(0, _prevScrollY || 0);
    } catch {}
  }

  // Best-effort Telegram UI hide (no UI change; behavior only)
  function tgTakeoverOn() {
    try { tg?.ready?.(); } catch {}
    try { tg?.expand?.(); } catch {}
    try { tg?.setHeaderColor?.("#000000"); } catch {}
    try { tg?.setBackgroundColor?.("#000000"); } catch {}
    try { tg?.MainButton?.hide?.(); } catch {}
    try { tg?.BackButton?.show?.(); } catch {}
    try {
      tg?.BackButton?.onClick?.(() => {
        if (overlay) API.close();
      });
    } catch {}

    // try fullscreen on mobile
    try { tg?.requestFullscreen?.(); } catch {}
  }

  function tgTakeoverOff() {
    try { tg?.BackButton?.hide?.(); } catch {}
    // do NOT show MainButton here; app-level decides. We only hide in takeover.
    try { tg?.exitFullscreen?.(); } catch {}
  }

  // ---------------------------------------------------------
  // Overlay build
  // ---------------------------------------------------------
  function ensureOverlay() {
    if (overlay) return;

    const safe = cssSafe();

    overlay = document.createElement("div");
    overlay.id = "bco-z-game";
    overlay.style.cssText = `
      position:fixed; inset:0; z-index:999999;
      background:
        radial-gradient(1200px 800px at 50% 35%, rgba(255,255,255,.06), rgba(0,0,0,.75)),
        linear-gradient(180deg, rgba(6,6,10,.90), rgba(0,0,0,.94));
      overflow:hidden;
      touch-action:none;
      -webkit-user-select:none; user-select:none;
      padding-top:${safe.top};
      padding-bottom:${safe.bot};
      padding-left:${safe.left};
      padding-right:${safe.right};
      -webkit-tap-highlight-color: transparent;
      pointer-events:auto;
    `;

    // Canvas
    canvas = document.createElement("canvas");
    canvas.id = "bco-z-canvas";
    canvas.style.cssText = `
      position:absolute; inset:0; width:100%; height:100%;
      pointer-events:none; /* ✅ canvas never blocks UI taps */
    `;
    overlay.appendChild(canvas);
    ctx = canvas.getContext("2d", { alpha: true });

    // Top HUD
    const top = document.createElement("div");
    top.style.cssText = `
      position:absolute; left:0; right:0; top:0;
      height:68px; display:flex; align-items:center; justify-content:space-between;
      padding:10px 12px; box-sizing:border-box;
      pointer-events:auto;
      z-index:10;
      backdrop-filter: blur(14px);
      background: linear-gradient(180deg, rgba(0,0,0,.55), rgba(0,0,0,0));
      border-bottom:1px solid rgba(255,255,255,.08);
    `;

    const left = document.createElement("div");
    left.style.cssText = `display:flex; gap:10px; align-items:center;`;

    const badge = document.createElement("div");
    badge.textContent = "🧟";
    badge.style.cssText = `
      width:38px; height:38px; border-radius:12px;
      display:flex; align-items:center; justify-content:center;
      background: rgba(255,255,255,.08);
      border:1px solid rgba(255,255,255,.12);
    `;

    const title = document.createElement("div");
    title.innerHTML = `
      <div style="font:900 14px/1.1 Inter,system-ui; letter-spacing:.2px;">Zombies Survival</div>
      <div id="bco-z-sub" style="font:800 12px/1.1 Inter,system-ui; opacity:.72;">ARCADE • Ashes</div>
    `;

    left.appendChild(badge);
    left.appendChild(title);

    const right = document.createElement("div");
    right.style.cssText = `display:flex; gap:10px; align-items:center;`;

    const pill = document.createElement("div");
    pill.id = "bco-z-hud";
    pill.style.cssText = `
      padding:10px 12px; border-radius:14px;
      font:900 12px/1 Inter,system-ui;
      background: rgba(255,255,255,.08);
      border:1px solid rgba(255,255,255,.12);
      color: rgba(255,255,255,.92);
      white-space: nowrap;
      max-width: 78vw;
      overflow:hidden;
      text-overflow: ellipsis;
    `;
    pill.textContent = `❤️ 100 • ☠️ 0 • 💰 0 • 🔫 SMG`;

    const btnSend = document.createElement("button");
    btnSend.type = "button";
    btnSend.textContent = "Send";
    btnSend.style.cssText = `
      padding:12px 14px; border-radius:16px;
      border:1px solid rgba(255,255,255,.14);
      background: rgba(255,255,255,.08);
      color: rgba(255,255,255,.92);
      font:900 12px/1 Inter,system-ui;
      letter-spacing:.2px;
      touch-action: manipulation;
      -webkit-tap-highlight-color: transparent;
    `;
    btnSend.addEventListener("click", (e) => {
      e.preventDefault();
      sendResult("manual");
      haptic("notif", "success");
    }, { passive: false });

    const btnClose = document.createElement("button");
    btnClose.type = "button";
    btnClose.textContent = "✖";
    btnClose.style.cssText = `
      width:42px; height:42px; border-radius:14px;
      border:1px solid rgba(255,255,255,.14);
      background: rgba(255,255,255,.08);
      color: rgba(255,255,255,.92);
      font:900 16px/1 Inter,system-ui;
      touch-action: manipulation;
      -webkit-tap-highlight-color: transparent;
    `;
    btnClose.addEventListener("click", (e) => {
      e.preventDefault();
      API.close();
    }, { passive: false });

    right.appendChild(pill);
    right.appendChild(btnSend);
    right.appendChild(btnClose);

    top.appendChild(left);
    top.appendChild(right);
    overlay.appendChild(top);

    // Bottom controls layer
    const bottom = document.createElement("div");
    bottom.style.cssText = `
      position:absolute; left:0; right:0; bottom:0;
      height:240px;
      padding:10px 12px calc(10px + env(safe-area-inset-bottom));
      box-sizing:border-box;
      pointer-events:none;
      z-index:9;
      background: linear-gradient(0deg, rgba(0,0,0,.62), rgba(0,0,0,0));
    `;
    overlay.appendChild(bottom);

    // Dual sticks (big, iOS-friendly)
    const joyL = mkStick("left");
    const joyR = mkStick("right");
    bottom.appendChild(joyL.base);
    bottom.appendChild(joyR.base);

    // Right-side action stack (Reload/Plate)
    const action = document.createElement("div");
    action.id = "bco-z-actions";
    action.style.cssText = `
      position:absolute;
      right: 200px;
      bottom: calc(14px + env(safe-area-inset-bottom));
      display:flex;
      flex-direction:column;
      gap:10px;
      pointer-events:auto;
      z-index:30; /* ✅ above everything */
    `;
    bottom.appendChild(action);

    const btnReload = mkBtn("🔄 Reload", () => {
      if (typeof CORE.reload === "function") {
        const ok = CORE.reload();
        haptic("impact", ok ? "medium" : "light");
      } else {
        haptic("notif", "warning");
      }
    }, { w: 112 });

    const btnPlate = mkBtn("🛡 Plate", () => {
      if (typeof CORE.usePlate === "function") {
        const ok = CORE.usePlate();
        haptic("impact", ok ? "medium" : "light");
      } else {
        haptic("notif", "warning");
      }
    }, { w: 112 });

    action.appendChild(btnReload);
    action.appendChild(btnPlate);

    // Shop bar (roguelike)
    const shop = document.createElement("div");
    shop.id = "bco-z-shop";
    shop.style.cssText = `
      position:absolute;
      left:50%; transform:translateX(-50%);
      bottom: calc(14px + env(safe-area-inset-bottom));
      display:flex; gap:10px;
      pointer-events:auto;
      opacity:0;
      transition: opacity .18s ease, transform .18s ease;
      z-index:40; /* ✅ above sticks too */
    `;
    bottom.appendChild(shop);

    // Upgrade/Reroll row (roguelike)
    const upgrades = document.createElement("div");
    upgrades.id = "bco-z-upgrades";
    upgrades.style.cssText = `
      position:absolute;
      left:50%; transform:translateX(-50%);
      bottom: calc(74px + env(safe-area-inset-bottom));
      display:flex; gap:10px;
      pointer-events:auto;
      opacity:0;
      transition: opacity .18s ease, transform .18s ease;
      z-index:40;
    `;
    bottom.appendChild(upgrades);

    const btnUpg = mkBtn("⬆️ Upgrade", () => {
      // 3D-ready: upgrade belongs in CORE; here we keep compatibility helper
      let ok = false;
      try {
        // Prefer a proper API if core supports it
        if (typeof CORE.upgradeWeapon === "function") {
          ok = !!CORE.upgradeWeapon();
        } else if (CORE?.state?.weapon && typeof CORE?.state?.weapon?.upgrade === "number") {
          const S = CORE.state;
          const w = S.weapon;
          const cost = 8 + (w.upgrade | 0) * 6;
          if (CORE.meta.mode !== "roguelike") ok = false;
          else if ((S.coins | 0) >= cost) {
            S.coins -= cost;
            w.upgrade = Math.min(9, (w.upgrade | 0) + 1);
            if (typeof CORE.setWeapon === "function") CORE.setWeapon(CORE.meta.weaponKey);
            ok = true;
          }
        }
      } catch {}
      if (ok) haptic("notif", "success");
      else haptic("notif", "warning");
    }, { w: 126 });

    const btnReroll = mkBtn("🎲 Reroll", () => {
      // Prefer core reroll if exists
      let ok = false;
      try {
        if (typeof CORE.rerollWeapon === "function") {
          ok = !!CORE.rerollWeapon();
        } else if (CORE.meta.mode === "roguelike" && CORE?.cfg?.weapons && typeof CORE.setWeapon === "function") {
          const keys = Object.keys(CORE.cfg.weapons);
          if (keys.length) {
            const key = keys[(Math.random() * keys.length) | 0];
            const cost = 6;
            if ((CORE.state.coins | 0) >= cost) {
              CORE.state.coins -= cost;
              CORE.setWeapon(key);
              ok = true;
            }
          }
        }
      } catch {}
      if (ok) haptic("notif", "success");
      else haptic("notif", "warning");
    }, { w: 126 });

    upgrades.appendChild(btnUpg);
    upgrades.appendChild(btnReroll);

    // Shop buttons (perks)
    shop.appendChild(mkBtn("🧪 Jug (12)", () => { if (CORE.buyPerk("Jug")) haptic("notif","success"); else haptic("notif","warning"); }, { w: 120 }));
    shop.appendChild(mkBtn("⚡ Speed (10)", () => { if (CORE.buyPerk("Speed")) haptic("notif","success"); else haptic("notif","warning"); }, { w: 124 }));
    shop.appendChild(mkBtn("📦 Mag (8)", () => { if (CORE.buyPerk("Mag")) haptic("notif","success"); else haptic("notif","warning"); }, { w: 110 }));
    shop.appendChild(mkBtn("🛡 Armor (14)", () => { if (CORE.buyPerk("Armor")) haptic("notif","success"); else haptic("notif","warning"); }, { w: 128 }));

    function mkBtn(txt, on, opt = {}) {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = txt;
      const w = opt.w ? `${opt.w}px` : "auto";
      b.style.cssText = `
        min-width:${w};
        padding:12px 14px; border-radius:16px;
        border:1px solid rgba(255,255,255,.14);
        background: rgba(255,255,255,.08);
        color: rgba(255,255,255,.92);
        font:900 12px/1 Inter,system-ui;
        letter-spacing:.2px;
        touch-action: manipulation;
        -webkit-tap-highlight-color: transparent;
        pointer-events:auto;
      `;
      b.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        try { on?.(e); } catch {}
      }, { passive: false });
      return b;
    }

    function mkStick(side) {
      const base = document.createElement("div");
      base.style.cssText = `
        position:absolute;
        bottom: calc(12px + env(safe-area-inset-bottom));
        ${side === "left" ? "left" : "right"}: 12px;
        width: 170px; height: 170px;
        border-radius: 999px;
        background: rgba(255,255,255,.06);
        border: 1px solid rgba(255,255,255,.12);
        backdrop-filter: blur(10px);
        pointer-events:auto;
        touch-action:none;
        -webkit-tap-highlight-color: transparent;
        z-index:20;
      `;

      const knob = document.createElement("div");
      knob.style.cssText = `
        position:absolute; left:50%; top:50%;
        width: 66px; height: 66px;
        transform: translate(-50%,-50%);
        border-radius: 999px;
        background: rgba(255,255,255,.18);
        border: 1px solid rgba(255,255,255,.16);
        box-shadow: 0 16px 44px rgba(0,0,0,.45);
        pointer-events:none;
      `;
      base.appendChild(knob);

      return { base, knob, id: null, side, lastNX: 0, lastNY: 0 };
    }

    // Prevent scroll/pinch (overlay level)
    overlay.addEventListener("touchmove", (e) => e.preventDefault(), { passive: false });
    overlay.addEventListener("gesturestart", (e) => e.preventDefault(), { passive: false });
    overlay.addEventListener("gesturechange", (e) => e.preventDefault(), { passive: false });
    overlay.addEventListener("gestureend", (e) => e.preventDefault(), { passive: false });

    // Attach
    mount().appendChild(overlay);

    // Resize + wire
    resize();

    // Sticks
    wireStick(joyL, (x, y, active) => {
      input.moveX = x; input.moveY = y;
      if (typeof CORE.setMove === "function") CORE.setMove(x, y);
      // keep for 3D
    });

    // Right stick = aim + fire (hold-to-shoot)
    wireStick(joyR, (x, y, active) => {
      input.aimX = x || input.aimX;
      input.aimY = y || input.aimY;

      if (x || y) {
        if (typeof CORE.setAim === "function") CORE.setAim(x, y);
      }

      // fire only while active touch AND vector non-zero (prevents accidental firing)
      const firing = !!active && (Math.abs(x) + Math.abs(y) > 0.01);
      input.firing = firing;

      // Core compatibility:
      // - prefer setShooting
      // - else setFire
      // - else write to CORE.input.shooting
      try {
        if (typeof CORE.setShooting === "function") CORE.setShooting(firing);
        else if (typeof CORE.setFire === "function") CORE.setFire(firing);
        else if (CORE.input) CORE.input.shooting = firing;
      } catch {}
    });

    // Telegram takeover best-effort + scroll lock
    lockScroll();
    tgTakeoverOn();

    // show shop depending on mode
    setRogueUI((CORE.meta?.mode || "arcade") === "roguelike");

    // local refs
    overlay._bco = { shop, upgrades, action, joyL, joyR };
  }

  function setRogueUI(isRogue) {
    if (!overlay?._bco) return;
    const { shop, upgrades } = overlay._bco;

    const on = isRogue ? "1" : "0";
    shop.style.opacity = on;
    upgrades.style.opacity = on;

    shop.style.transform = `translateX(-50%) translateY(${isRogue ? "0px" : "10px"})`;
    upgrades.style.transform = `translateX(-50%) translateY(${isRogue ? "0px" : "10px"})`;
  }

  function destroyOverlay() {
    if (!overlay) return;
    try { overlay.remove(); } catch {}
    overlay = null;
    canvas = null;
    ctx = null;
  }

  // ---------------------------------------------------------
  // Stick math (premium: stable, deadzone)
  // ---------------------------------------------------------
  function wireStick(stick, onMove) {
    const dead = 0.10;
    const maxR = 56;

    const rect = () => stick.base.getBoundingClientRect();

    function setKnob(nx, ny) {
      stick.knob.style.transform =
        `translate(calc(-50% + ${nx * maxR}px), calc(-50% + ${ny * maxR}px))`;
    }

    function compute(e) {
      const r = rect();
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;

      const dx = e.clientX - cx;
      const dy = e.clientY - cy;

      const L = Math.hypot(dx, dy) || 1;
      let nx = dx / Math.max(L, 1);
      let ny = dy / Math.max(L, 1);

      const mag = Math.min(1, L / (r.width * 0.42));
      let m = mag < dead ? 0 : (mag - dead) / (1 - dead);

      nx *= m;
      ny *= m;

      // cache
      stick.lastNX = nx;
      stick.lastNY = ny;

      setKnob(nx, ny);
      return { nx, ny };
    }

    function down(e) {
      e.preventDefault();
      e.stopPropagation();
      stick.id = e.pointerId;
      try { stick.base.setPointerCapture?.(e.pointerId); } catch {}
      const { nx, ny } = compute(e);
      onMove(nx, ny, true);
      haptic("impact", "light");
    }

    function move(e) {
      if (stick.id !== e.pointerId) return;
      e.preventDefault();
      e.stopPropagation();
      const { nx, ny } = compute(e);
      onMove(nx, ny, true);
    }

    function up(e) {
      if (stick.id !== e.pointerId) return;
      e.preventDefault();
      e.stopPropagation();
      stick.id = null;
      stick.lastNX = 0;
      stick.lastNY = 0;
      setKnob(0, 0);
      onMove(0, 0, false);
    }

    stick.base.addEventListener("pointerdown", down, { passive: false });
    stick.base.addEventListener("pointermove", move, { passive: false });
    stick.base.addEventListener("pointerup", up, { passive: false });
    stick.base.addEventListener("pointercancel", up, { passive: false });
    stick.base.addEventListener("lostpointercapture", up, { passive: false });
  }

  // ---------------------------------------------------------
  // Resize (fix landscape / rotation)
  // ---------------------------------------------------------
  function resize() {
    if (!overlay || !canvas || !ctx) return;

    const r = overlay.getBoundingClientRect();
    dpr = Math.max(1, Math.min(3, window.devicePixelRatio || 1));

    canvas.width = Math.floor(r.width * dpr);
    canvas.height = Math.floor(r.height * dpr);

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    try { if (typeof CORE.resize === "function") CORE.resize(r.width, r.height); } catch {}
  }

  function scheduleResize() {
    resize();
    setTimeout(resize, 50);
    setTimeout(resize, 180);
  }

  window.addEventListener("resize", scheduleResize, { passive: true });
  window.addEventListener("orientationchange", scheduleResize, { passive: true });
  try {
    window.visualViewport?.addEventListener?.("resize", scheduleResize, { passive: true });
    window.visualViewport?.addEventListener?.("scroll", scheduleResize, { passive: true });
  } catch {}

  // ---------------------------------------------------------
  // Loop
  // ---------------------------------------------------------
  function loop(t) {
    raf = requestAnimationFrame(loop);
    if (!overlay || !ctx) return;

    try {
      if (CORE.running && typeof CORE.updateFrame === "function") CORE.updateFrame(t);
      else if (CORE.running && typeof CORE.step === "function") CORE.step(t);
    } catch {}

    const r = overlay.getBoundingClientRect();
    const view = { w: r.width, h: r.height };

    // render
    try {
      RENDER.render(ctx, CORE, CORE.input || CORE?.input || input, view);
    } catch (e) {
      // fail-safe: don't kill controls on renderer errors
      // eslint-disable-next-line no-console
      console.warn("[Z_GAME] render err", e);
    }

    // snapshot (3D-ready)
    try {
      _lastSnap = (typeof CORE.getFrameData === "function") ? CORE.getFrameData() : null;
      if (_lastSnap && typeof _snapCb === "function") _snapCb(_lastSnap);
    } catch {}

    updateHud();
    checkDeathAutoSend();
  }

  let _sentDeath = false;

  function checkDeathAutoSend() {
    if (!CORE.running) {
      if (!_sentDeath && CORE?.state?.player?.hp <= 0) {
        _sentDeath = true;
        sendResult("dead");
        haptic("notif", "error");
      }
    }
  }

  function updateHud() {
    const sub = document.getElementById("bco-z-sub");
    const hud = document.getElementById("bco-z-hud");

    const S = CORE.state || {};
    const P = S.player || { hp: 0, armor: 0, plates: 0 };

    // Prefer public snapshot for 3D readiness (consistent)
    const snap = (typeof CORE.getFrameData === "function") ? _lastSnap : null;
    const hudData = snap?.hud || null;

    // effective stats (if exposed)
    const st = (typeof CORE._effectiveStats === "function")
      ? CORE._effectiveStats()
      : { hpMax: 100, armorMax: 0, platesMax: 0 };

    const hp = Math.max(0, Math.min(P.hp | 0, st.hpMax | 0 || 100));
    const armor = Math.max(0, Math.min((P.armor | 0) || 0, (st.armorMax | 0) || 0));
    const plates = Math.max(0, Math.min((P.plates | 0) || 0, (st.platesMax | 0) || 0));

    const mode = String(CORE.meta?.mode || "arcade");
    const map = String(CORE.meta?.map || "Ashes");

    // weapon display
    const wName = hudData?.weapon?.name || S.weapon?.name || (CORE._weapon?.()?.name) || (CORE.cfg?.weapons?.[CORE.meta?.weaponKey]?.name) || "SMG";
    const mag = hudData?.weapon?.mag ?? (S.weapon && typeof S.weapon.mag === "number" ? (S.weapon.mag | 0) : null);
    const magMax = hudData?.weapon?.magMax ?? (S.weapon && typeof S.weapon.magMax === "number" ? (S.weapon.magMax | 0) : null);
    const reserve = hudData?.weapon?.reserve ?? (S.weapon && typeof S.weapon.reserve === "number" ? (S.weapon.reserve | 0) : null);

    const kills = hudData?.kills ?? (S.kills | 0);
    const wave = hudData?.wave ?? (S.wave | 0);
    const coins = hudData?.coins ?? (S.coins | 0);
    const lvl = hudData?.level ?? (S.level | 0);

    if (sub) sub.textContent = `${mode.toUpperCase()} • ${map}`;

    let s = `❤️ ${hp|0}/${(st.hpMax|0) || 100}`;
    if ((st.armorMax|0) > 0 || armor > 0) s += ` • 🛡 ${armor|0}/${(st.armorMax|0) || 0}`;
    if ((st.platesMax|0) > 0 || plates > 0) s += ` • 🧩 ${plates|0}`;
    s += ` • ☠️ ${kills|0} • 🌊 ${wave|0}`;
    if (mode === "roguelike") s += ` • 💰 ${coins|0} • 🧬 L${Math.max(1, lvl|0)}`;
    s += ` • 🔫 ${wName}`;
    if (mag !== null && magMax !== null) {
      s += ` • ${mag}/${magMax}`;
      if (reserve !== null) s += ` (${reserve})`;
    }
    if (hud) hud.textContent = s;

    // roguelike UI toggles
    setRogueUI(mode === "roguelike");

    // button hint state (plate/reload)
    try {
      const a = overlay?._bco?.action;
      if (a) {
        const btns = a.querySelectorAll("button");
        if (btns?.length >= 2) {
          const canReload =
            (typeof CORE.reload === "function") &&
            (S.weapon && (S.weapon.mag|0) < ((magMax|0) || 999)) &&
            ((S.weapon.reserve|0) > 0) &&
            !(S.reload?.active);

          btns[0].style.opacity = canReload ? "1" : "0.55";

          const canPlate =
            (typeof CORE.usePlate === "function") &&
            (mode === "roguelike") &&
            ((plates|0) > 0) &&
            ((armor|0) < ((st.armorMax|0) || 0)) &&
            !(P?.plating?.active);

          btns[1].style.opacity = canPlate ? "1" : "0.55";
        }
      }
    } catch {}
  }

  // ---------------------------------------------------------
  // Result payload
  // ---------------------------------------------------------
  function score() {
    const S = CORE.state || {};
    const P = S.player || {};
    const base = (S.kills | 0) * 100;
    const waveBonus = Math.max(0, (S.wave - 1) | 0) * 250;
    const timeSec = Math.max(1, ((S.timeMs || 0) / 1000));
    const pace = ((S.kills || 0) / timeSec) * 100;

    const perks = S.perks || {};
    const perkScore =
      (perks.Jug ? 150 : 0) +
      (perks.Speed ? 120 : 0) +
      (perks.Mag ? 80 : 0) +
      (perks.Armor ? 140 : 0) +
      (perks.Reload ? 110 : 0) +
      (perks.Crit ? 130 : 0) +
      (perks.Loot ? 120 : 0) +
      (perks.Sprint ? 90 : 0);

    const armorBonus = Math.min(180, Math.max(0, (P.armor | 0) || 0));
    const lvl = Math.max(1, (S.level | 0) || 1);
    const lvlBonus = Math.min(800, (lvl - 1) * 40);

    return Math.round(base + waveBonus + pace + perkScore + armorBonus + lvlBonus);
  }

  function sendResult(reason = "manual") {
    const S = CORE.state || {};
    const P = S.player || {};

    const payload = {
      action: "game_result",
      game: "zombies",
      mode: CORE.meta?.mode || "arcade",
      reason,

      map: CORE.meta?.map || "Ashes",
      wave: S.wave ?? null,
      kills: S.kills ?? null,
      coins: S.coins ?? null,
      duration_ms: Math.round(S.timeMs || 0),
      score: score(),

      character: CORE.meta?.character || null,
      skin: CORE.meta?.skin || null,
      loadout: { weapon: CORE.meta?.weaponKey || null },
      perks: { ...(S.perks || {}) },

      // extras
      hp: (P.hp ?? null),
      armor: (P.armor ?? null),
      plates: (P.plates ?? null),
      xp: (S.xp ?? null),
      level: (S.level ?? null),
      ammo: (S.weapon && typeof S.weapon.mag === "number") ? { mag: S.weapon.mag, reserve: S.weapon.reserve } : null
    };

    safeSendData(payload);
  }

  // ---------------------------------------------------------
  // Public API (3D-ready)
  // ---------------------------------------------------------
  const API = {
    open() {
      ensureOverlay();
      scheduleResize();
      if (!raf) raf = requestAnimationFrame(loop);
      haptic("impact", "medium");
      return true;
    },

    close() {
      if (raf) cancelAnimationFrame(raf);
      raf = 0;

      try { if (typeof CORE.stop === "function") CORE.stop(); } catch {}
      _sentDeath = false;

      tgTakeoverOff();
      unlockScroll();
      destroyOverlay();
      return true;
    },

    start(mode = "arcade", opts = {}) {
      ensureOverlay();
      scheduleResize();
      _sentDeath = false;

      const r = overlay.getBoundingClientRect();

      // ✅ IMPORTANT: Let CORE start decide mode (roguelike must be set inside core)
      // Prefer CORE.setMode if exists, then start
      try {
        if (typeof CORE.setMode === "function") CORE.setMode(mode);
      } catch {}

      try {
        CORE.start(mode, r.width, r.height, opts);
      } catch (e) {
        console.warn("[Z_GAME] CORE.start failed", e);
        return false;
      }

      if (!raf) raf = requestAnimationFrame(loop);

      setRogueUI((CORE.meta?.mode || "arcade") === "roguelike");

      haptic("notif", "success");
      return true;
    },

    stop(reason = "manual") {
      try { if (typeof CORE.stop === "function") CORE.stop(); } catch {}
      sendResult(reason);
      haptic("notif", "warning");
      return true;
    },

    setMode(mode) {
      // ✅ Prefer CORE.setMode (real rules), fallback to meta
      try {
        if (typeof CORE.setMode === "function") return CORE.setMode(mode);
      } catch {}
      const m = String(mode || "").toLowerCase();
      CORE.meta.mode = (m.includes("rogue")) ? "roguelike" : "arcade";
      setRogueUI(CORE.meta.mode === "roguelike");
      updateHud();
      return CORE.meta.mode;
    },

    setMap(mapName) {
      CORE.meta.map = String(mapName || "Ashes");
      updateHud();
      return CORE.meta.map;
    },

    setCharacter(character, skin) {
      if (character) CORE.meta.character = String(character);
      if (skin) CORE.meta.skin = String(skin);

      // assets module may support skins
      try {
        const A = window.BCO_ZOMBIES_ASSETS;
        if (A?.setPlayerSkin) A.setPlayerSkin(CORE.meta.skin);
      } catch {}

      return { character: CORE.meta.character, skin: CORE.meta.skin };
    },

    setWeapon(key) {
      if (typeof CORE.setWeapon === "function") return CORE.setWeapon(key);
      CORE.meta.weaponKey = String(key || CORE.meta.weaponKey || "SMG");
      return CORE.meta.weaponKey;
    },

    buyPerk(id) {
      if (typeof CORE.buyPerk !== "function") return false;
      const ok = CORE.buyPerk(id);
      if (ok) haptic("notif", "success");
      else haptic("notif", "warning");
      return ok;
    },

    reload() {
      if (typeof CORE.reload !== "function") return false;
      const ok = CORE.reload();
      if (ok) haptic("impact", "medium");
      else haptic("impact", "light");
      return ok;
    },

    usePlate() {
      if (typeof CORE.usePlate !== "function") return false;
      const ok = CORE.usePlate();
      if (ok) haptic("impact", "medium");
      else haptic("impact", "light");
      return ok;
    },

    sendResult(reason) {
      sendResult(reason || "manual");
      return true;
    },

    // -------- 3D-ready extras --------
    getSnapshot() {
      try {
        if (typeof CORE.getFrameData === "function") return CORE.getFrameData();
      } catch {}
      return _lastSnap;
    },
    onSnapshot(cb) {
      _snapCb = (typeof cb === "function") ? cb : null;
      return true;
    },
    getInput() {
      return { ...input };
    },
    setInput(obj) {
      const o = obj || {};
      if (typeof o.moveX === "number") input.moveX = clamp(o.moveX, -1, 1);
      if (typeof o.moveY === "number") input.moveY = clamp(o.moveY, -1, 1);
      if (typeof o.aimX === "number") input.aimX = clamp(o.aimX, -1, 1);
      if (typeof o.aimY === "number") input.aimY = clamp(o.aimY, -1, 1);
      if (typeof o.firing === "boolean") input.firing = o.firing;

      try { if (typeof CORE.setMove === "function") CORE.setMove(input.moveX, input.moveY); } catch {}
      try { if (typeof CORE.setAim === "function") CORE.setAim(input.aimX, input.aimY); } catch {}
      try {
        if (typeof CORE.setShooting === "function") CORE.setShooting(!!input.firing);
        else if (typeof CORE.setFire === "function") CORE.setFire(!!input.firing);
        else if (CORE.input) CORE.input.shooting = !!input.firing;
      } catch {}
      return true;
    }
  };

  window.BCO_ZOMBIES_GAME = API;
  console.log("[Z_GAME] ready (LUX | iOS hardened | 3D-ready)");
})();
