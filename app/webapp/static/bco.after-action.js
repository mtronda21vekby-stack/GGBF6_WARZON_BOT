/* BLACK CROWN OPS v47 — AFTER ACTION session-scoped evidence */
(() => {
  "use strict";
  if (window.__BCO_AFTER_ACTION_V47_LOADED__) return;
  window.__BCO_AFTER_ACTION_V47_LOADED__ = true;

  const $ = (q, root = document) => root.querySelector(q);
  const safe = (value, fallback = "—") => { const text = String(value ?? "").trim(); return text || fallback; };
  const initData = () => { try { return String(window.Telegram?.WebApp?.initData || "").trim(); } catch (_) { return ""; } };
  let currentMission = null;

  function css() {
    if ($("#bcoAfterActionCss")) return;
    const style = document.createElement("style");
    style.id = "bcoAfterActionCss";
    style.textContent = `
      .bco-aa{margin-top:10px;padding:15px;border:1px solid rgba(255,255,255,.07);border-radius:16px;background:rgba(0,0,0,.16)}
      .bco-aa__head{display:flex;justify-content:space-between;gap:10px;align-items:center}.bco-aa__head span{font-size:8px;letter-spacing:.16em;opacity:.5}.bco-aa__head b{font-size:9px;letter-spacing:.09em;color:#d9bb79}.bco-aa h3{margin:8px 0 4px;font-size:17px}.bco-aa p{margin:0;font-size:11px;line-height:1.5;opacity:.66}
      .bco-aa__inputs{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:11px}.bco-aa input{width:100%;box-sizing:border-box;min-height:40px;padding:9px 10px;border:1px solid rgba(255,255,255,.08);border-radius:11px;background:rgba(255,255,255,.035);color:inherit}.bco-aa label{font-size:8px;letter-spacing:.1em;opacity:.55}.bco-aa label input{display:block;margin-top:5px;opacity:1}
      .bco-aa__actions{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:10px}.bco-aa__actions button{min-height:41px;border-radius:11px;border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.045);color:inherit;font-weight:800;letter-spacing:.04em}.bco-aa__actions button[data-outcome="clean"]{border-color:rgba(155,220,170,.22)}.bco-aa__actions button[data-outcome="failed"]{border-color:rgba(230,130,130,.22)}
      .bco-aa__report{display:none;margin-top:12px;padding-top:12px;border-top:1px solid rgba(255,255,255,.07)}.bco-aa__report.active{display:block}.bco-aa__grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.bco-aa__cell{padding:10px;border:1px solid rgba(255,255,255,.055);border-radius:11px;background:rgba(255,255,255,.025)}.bco-aa__cell span{display:block;font-size:8px;letter-spacing:.13em;opacity:.45;margin-bottom:5px}.bco-aa__cell strong{font-size:12px;line-height:1.35}.bco-aa__status{margin-top:9px;font-size:9px;line-height:1.45;opacity:.44}
    `;
    document.head.appendChild(style);
  }

  function set(id, value, fallback = "—") { const el = $(id); if (el) el.textContent = safe(value, fallback); }

  function renderSession(session) {
    currentMission = session?.mission || null;
    const active = currentMission && String(currentMission.status || "").toLowerCase() === "active";
    set("#bcoAaMission", active ? currentMission.title : "NO ACTIVE MISSION");
    set("#bcoAaState", active ? "READY FOR REPORT" : "MISSION REQUIRED");
    document.querySelectorAll(".bco-aa__actions button").forEach((btn) => { btn.disabled = !active; });
    return true;
  }

  function renderReport(data) {
    $("#bcoAaReport")?.classList.add("active");
    const changed = data.what_changed || {};
    const weaknesses = Array.isArray(data.new_weaknesses) ? data.new_weaknesses : [];
    const next = data.next_mission || {};
    const vodRows = Array.isArray(data.linked_vod_evidence) ? data.linked_vod_evidence : [];
    const vod = vodRows[0] || {};
    const strategy = data.strategy_outcome?.latest || {};
    const cycle = data.crown_session || {};
    set("#bcoAaOutcome", String(data.mission_outcome?.outcome || "reported").toUpperCase());
    set("#bcoAaChanged", `${changed.operator_state_before || "unknown"} → ${changed.operator_state_after || "unknown"} • coverage ${Number(changed.coverage_before || 0)}% → ${Number(changed.coverage_after || 0)}%`);
    set("#bcoAaWeakness", weaknesses.length ? weaknesses.join(" • ") : "NO NEW PERSISTED WEAKNESS");
    set("#bcoAaVod", vodRows.length ? `${vod.classification || "evidence"} • ${vod.evidence_count || 0} signals • ${vod.confidence || "unknown"}` : "NO VOD EVIDENCE LINKED TO THIS SESSION");
    set("#bcoAaStrategy", strategy.verdict ? `${strategy.verdict} • association only` : "INSUFFICIENT FOLLOW-UP");
    set("#bcoAaNext", next.title || "CALIBRATING NEXT MISSION");
    set("#bcoAaStatus", cycle.id ? `AFTER ACTION committed • ${cycle.id} CLOSED • only session-matched VOD used.` : "AFTER ACTION committed • legacy untracked cycle • VOD was not auto-completed.");
  }

  async function submit(outcome) {
    if (!currentMission?.id || String(currentMission.status || "").toLowerCase() !== "active") return;
    const init = initData(); if (!init) { set("#bcoAaStatus", "trusted_telegram_context_required"); return; }
    document.querySelectorAll(".bco-aa__actions button").forEach((btn) => { btn.disabled = true; });
    const cleanRaw = String($("#bcoAaClean")?.value || "").trim();
    const deathCause = String($("#bcoAaDeath")?.value || "").trim();
    const metrics = {};
    if (cleanRaw !== "" && Number.isFinite(Number(cleanRaw)) && Number(cleanRaw) >= 0) metrics.clean_executions = Number(cleanRaw);
    if (deathCause) metrics.death_cause = deathCause.slice(0, 240);
    set("#bcoAaStatus", "Committing explicit mission outcome…");
    try {
      const response = await fetch("/webapp/api/crown-session/after-action", {method:"POST",headers:{"X-Telegram-Init-Data":init,"Content-Type":"application/json",accept:"application/json"},body:JSON.stringify({mission_id:currentMission.id,outcome,metrics}),cache:"no-store",credentials:"same-origin"});
      const payload = await response.json().catch(() => null);
      if (!response.ok || !payload?.ok || !payload?.data) throw new Error(payload?.detail || `after_action_http_${response.status}`);
      renderReport(payload.data);
      await window.BCO_CROWN_SESSION?.refresh?.(true).then(renderSession).catch(() => {});
      try { window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred?.(outcome === "failed" ? "warning" : "success"); } catch (_) {}
    } catch (error) {
      set("#bcoAaStatus", safe(error?.message, "AFTER ACTION unavailable"));
      renderSession(window.BCO_CROWN_SESSION?.getSnapshot?.());
      try { window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred?.("error"); } catch (_) {}
    }
  }

  function mount() {
    const home = $("#bcoSessionHomeV45"); if (!home || $("#bcoAfterActionV46")) return false; css();
    const section = document.createElement("section");
    section.id = "bcoAfterActionV46"; section.className = "bco-aa";
    section.innerHTML = `<div class="bco-aa__head"><span>AFTER ACTION</span><b id="bcoAaState">MISSION REQUIRED</b></div><h3 id="bcoAaMission">NO ACTIVE MISSION</h3><p>Close the loop with an explicit operator report. VOD may support evidence but never completes the mission automatically.</p><div class="bco-aa__inputs"><label>CLEAN EXECUTIONS<input id="bcoAaClean" type="number" min="0" max="100" inputmode="numeric" placeholder="optional"></label><label>DEATH CAUSE<input id="bcoAaDeath" maxlength="240" placeholder="optional evidence"></label></div><div class="bco-aa__actions"><button type="button" data-outcome="clean">CLEAN</button><button type="button" data-outcome="mixed">MIXED</button><button type="button" data-outcome="failed">FAILED</button></div><div class="bco-aa__report" id="bcoAaReport"><div class="bco-aa__grid"><div class="bco-aa__cell"><span>MISSION OUTCOME</span><strong id="bcoAaOutcome">—</strong></div><div class="bco-aa__cell"><span>WHAT CHANGED</span><strong id="bcoAaChanged">—</strong></div><div class="bco-aa__cell"><span>NEW WEAKNESS</span><strong id="bcoAaWeakness">—</strong></div><div class="bco-aa__cell"><span>SESSION VOD EVIDENCE</span><strong id="bcoAaVod">—</strong></div><div class="bco-aa__cell"><span>STRATEGY OUTCOME</span><strong id="bcoAaStrategy">—</strong></div><div class="bco-aa__cell"><span>NEXT MISSION</span><strong id="bcoAaNext">—</strong></div></div></div><div class="bco-aa__status" id="bcoAaStatus">Waiting for active mission.</div>`;
    const actions = home.querySelector(".bco-sh-actions"); if (actions) home.insertBefore(section, actions); else home.appendChild(section);
    section.querySelectorAll("button[data-outcome]").forEach((btn) => btn.addEventListener("click", () => submit(btn.dataset.outcome)));
    renderSession(window.BCO_CROWN_SESSION?.getSnapshot?.());
    window.addEventListener("bco:crown-session", (event) => renderSession(event.detail));
    return true;
  }

  if (!mount()) { let tries=0; const timer=setInterval(()=>{tries+=1;if(mount()||tries>30)clearInterval(timer);},200); }
  window.BCO_AFTER_ACTION = { renderSession, renderReport, submit };
})();
