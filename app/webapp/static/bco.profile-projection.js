/* BLACK CROWN OPS v49 — server profile projection into legacy controls */
(() => {
  "use strict";
  if (window.__BCO_PROFILE_PROJECTION_V49_LOADED__) return;
  window.__BCO_PROFILE_PROJECTION_V49_LOADED__ = true;
  let applying = false;

  const roots = {
    game: "segGame",
    platform: "segPlatform",
    input: "segInput",
    difficulty: "segMode",
    voice: "segVoice",
    training_focus: "segFocus",
  };

  function normalize(field, value) {
    const text = String(value || "").trim();
    if (!text) return "";
    if (field === "difficulty") {
      const low = text.toLowerCase();
      if (low.includes("demon")) return "Demon";
      if (low.includes("pro")) return "Pro";
      return "Normal";
    }
    if (field === "training_focus") {
      const low = text.toLowerCase();
      if (low.includes("move")) return "movement";
      if (low.includes("pos")) return "position";
      return "aim";
    }
    return text;
  }

  function project(session) {
    if (applying || !session?.profile) return;
    applying = true;
    try {
      const profile = session.profile;
      Object.entries(roots).forEach(([field, rootId]) => {
        const root = document.getElementById(rootId);
        const expected = normalize(field, profile[field]);
        if (!root || !expected) return;
        const buttons = Array.from(root.querySelectorAll("button[data-value]"));
        const target = buttons.find(btn => String(btn.dataset.value || "").toLowerCase() === expected.toLowerCase());
        if (target && !target.classList.contains("active")) target.click();
      });
    } finally {
      applying = false;
    }
  }

  window.addEventListener("bco:crown-session", event => project(event.detail));
  const current = window.BCO_CROWN_SESSION?.getSnapshot?.();
  if (current) project(current);
  window.BCO_PROFILE_PROJECTION = { project };
})();
