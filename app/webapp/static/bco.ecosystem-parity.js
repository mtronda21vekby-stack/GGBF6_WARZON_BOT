/* BLACK CROWN OPS v49 — Telegram Bot feature parity actions */
(() => {
  "use strict";
  if (window.__BCO_ECOSYSTEM_PARITY_V49_LOADED__) return;
  window.__BCO_ECOSYSTEM_PARITY_V49_LOADED__ = true;

  const $ = (q, root = document) => root.querySelector(q);
  const bridge = (payload) => {
    try { return window.BCO_BRIDGE?.send?.(payload) === true; } catch (_) { return false; }
  };
  const tap = (id) => { const node = document.getElementById(id); if (!node) return false; node.click(); return true; };

  function style() {
    if ($("#bcoParityV49Css")) return;
    const el = document.createElement("style");
    el.id = "bcoParityV49Css";
    el.textContent = `
      .b49-parity{padding:15px;border:1px solid var(--b49-line);border-radius:16px;background:var(--b49-panel)}
      .b49-parity__top{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.b49-parity__top h3{margin:3px 0 0;font-size:15px}.b49-parity__top p{margin:5px 0 0;font-size:10px;line-height:1.45;color:var(--b49-muted)}
      .b49-parity__grid{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:12px}.b49-parity__btn{min-height:45px;padding:8px;border:1px solid var(--b49-line);border-radius:11px;background:var(--b49-panel2);color:inherit;font-size:9px;font-weight:800}.b49-parity__btn.primary{border-color:rgba(217,184,111,.25);background:rgba(217,184,111,.08);color:var(--b49-gold2)}
      @media(max-width:390px){.b49-parity__grid{grid-template-columns:1fr 1fr}}
    `;
    document.head.appendChild(el);
  }

  function mount() {
    const more = $("#b49More");
    if (!more || $("#b49ParityV49")) return false;
    style();
    const section = document.createElement("section");
    section.id = "b49ParityV49"; section.className = "b49-parity";
    section.innerHTML = `<div class="b49-parity__top"><div><div class="b49-kicker">TELEGRAM PARITY</div><h3>Bot controls inside Mini App</h3><p>Same backend routes, same canonical account. No separate Mini App identity.</p></div></div><div class="b49-parity__grid"><button class="b49-parity__btn" data-action="console">BOT CONSOLE</button><button class="b49-parity__btn" data-action="training">TRAINING</button><button class="b49-parity__btn" data-action="vod">VOD LAB</button><button class="b49-parity__btn" data-action="zombies">ZOMBIES HQ</button><button class="b49-parity__btn primary" data-action="premium">PREMIUM HUB</button><button class="b49-parity__btn" data-action="sync">SYNC PROFILE</button></div>`;
    const premium = $("#b49Premium");
    if (premium?.parentElement) premium.parentElement.after(section); else more.appendChild(section);

    section.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-action]"); if (!button) return;
      const action = button.dataset.action;
      try { window.Telegram?.WebApp?.HapticFeedback?.selectionChanged?.(); } catch (_) {}
      if (action === "console") { if (!tap("btnOpenBot")) bridge({type:"nav",target:"menu"}); }
      else if (action === "training") window.BCO_ECOSYSTEM?.openModule?.("training");
      else if (action === "vod") window.BCO_ECOSYSTEM?.route?.("vod");
      else if (action === "zombies") { if (!tap("btnOpenZombies")) bridge({type:"nav",target:"zombies"}); }
      else if (action === "premium") { if (!tap("btnPremium")) bridge({type:"nav",target:"premium"}); }
      else if (action === "sync") { if (!tap("btnApplyProfile") && !tap("btnSync")) bridge({type:"sync_request"}); }
    });
    return true;
  }

  if (!mount()) { let tries=0; const timer=setInterval(()=>{tries+=1;if(mount()||tries>40)clearInterval(timer);},150); }
})();
