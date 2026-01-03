// app/webapp/static/zombies/economy.js
(() => {
  "use strict";

  window.BCO = window.BCO || {};
  const bus = window.BCO.bus;

  // This module does not change gameplay. It only provides safe wrappers for UI/hotkeys.
  function core() { return window.BCO_ZOMBIES_CORE || null; }

  function can() { return !!core(); }

  function buyUpgrade() { try { return !!core()?.buyUpgrade?.(); } catch { return false; } }
  function rerollWeapon() { try { return !!core()?.rerollWeapon?.(); } catch { return false; } }
  function buyReload() { try { return !!core()?.buyReload?.(); } catch { return false; } }
  function usePlate() { try { return !!core()?.usePlate?.(); } catch { return false; } }
  function buyPerk(id) { try { return !!core()?.buyPerk?.(id); } catch { return false; } }

  // Expose
  window.BCO.zombies = window.BCO.zombies || {};
  window.BCO.zombies.economy = { can, buyUpgrade, rerollWeapon, buyReload, usePlate, buyPerk };

  // Optional: hotkey buttons in HOME panel (your existing ids)
  function bindHotkeys() {
    const jug = document.getElementById("btnZBuyJug");
    const spd = document.getElementById("btnZBuySpeed");
    const ammo = document.getElementById("btnZBuyAmmo");

    jug?.addEventListener("click", () => {
      const ok = buyPerk("Jug");
      bus?.emit?.("zombies:perk", { id: "Jug", ok });
    }, { passive: true });

    spd?.addEventListener("click", () => {
      const ok = buyPerk("Speed");
      bus?.emit?.("zombies:perk", { id: "Speed", ok });
    }, { passive: true });

    ammo?.addEventListener("click", () => {
      const ok = buyReload();
      bus?.emit?.("zombies:reloadbuy", { ok });
    }, { passive: true });
  }

  window.BCO.zombies.economy._bind = bindHotkeys;
})();
