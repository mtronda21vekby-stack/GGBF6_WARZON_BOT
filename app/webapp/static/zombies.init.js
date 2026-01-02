/* =========================================================
   app/webapp/static/zombies.init.js
   ONE-LINE WORLD INIT
   ========================================================= */
(() => {
  if (!window.BCO_ZOMBIES || !window.BCO_ZOMBIES_WORLD) return;

  window.BCO_ZOMBIES.onStart = function (run) {
    run.map = run.map || "Ashes";
    run._bossSpawned = {};
    window.BCO_ZOMBIES_WORLD.load(run.map);
  };
})();
