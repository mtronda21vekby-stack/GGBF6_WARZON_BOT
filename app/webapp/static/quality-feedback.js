/* BLACK CROWN OPS — Answer Quality Feedback v7 */
(() => {
  "use strict";

  const API = "/webapp/api/feedback";
  const SKIP = ["🤝 Пиши сюда", "Mini App AI недоступен", "…"];

  function injectStyle() {
    if (document.getElementById("bcoFeedbackStyle")) return;
    const style = document.createElement("style");
    style.id = "bcoFeedbackStyle";
    style.textContent = `
      .bco-feedback{display:flex;align-items:center;gap:6px;margin-top:5px;opacity:.66;transition:opacity .15s ease}
      .chat-row.bot:hover .bco-feedback,.bco-feedback:focus-within{opacity:1}
      .bco-feedback-label{font-size:9px;color:rgba(255,255,255,.4);margin-right:2px}
      .bco-feedback-btn{min-width:34px;height:28px;padding:0 8px;border-radius:9px;border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.045);color:rgba(255,255,255,.72);font-size:12px;cursor:pointer;touch-action:manipulation}
      .bco-feedback-btn.selected{border-color:rgba(139,92,246,.4);background:rgba(139,92,246,.16);color:#fff}
      .bco-feedback-btn:disabled{opacity:.55;cursor:default}
    `;
    document.head.appendChild(style);
  }

  function initData() {
    try { return String(window.Telegram?.WebApp?.initData || "").trim(); }
    catch (_) { return ""; }
  }

  async function sha256(text) {
    const bytes = new TextEncoder().encode(String(text || "").trim());
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
  }

  async function submit(text, rating, controls) {
    const init = initData();
    if (!init) return;
    controls.querySelectorAll("button").forEach((b) => { b.disabled = true; });
    try {
      const responseHash = await sha256(text);
      const res = await fetch(API, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Telegram-Init-Data": init,
          "X-BCO-Version": "quality-7.0",
        },
        cache: "no-store",
        body: JSON.stringify({ rating, response_hash: responseHash, surface: "miniapp_chat" }),
      });
      if (!res.ok) throw new Error(`feedback ${res.status}`);
      controls.querySelectorAll("button").forEach((b) => b.classList.remove("selected"));
      const selected = controls.querySelector(`[data-rating="${rating}"]`);
      selected?.classList.add("selected");
      const label = controls.querySelector(".bco-feedback-label");
      if (label) label.textContent = "saved";
    } catch (_) {
      controls.querySelectorAll("button").forEach((b) => { b.disabled = false; });
      const label = controls.querySelector(".bco-feedback-label");
      if (label) label.textContent = "retry";
    }
  }

  function eligible(text) {
    const clean = String(text || "").trim();
    if (!clean || clean.length < 12) return false;
    return !SKIP.some((x) => clean.includes(x));
  }

  function decorate() {
    const log = document.querySelector("#chatLog");
    if (!log) return;
    log.querySelectorAll(".chat-row.bot").forEach((row) => {
      if (row.dataset.bcoFeedback === "1") return;
      const bubble = row.querySelector(".bubble");
      const text = bubble?.textContent?.trim() || "";
      if (!eligible(text)) return;
      row.dataset.bcoFeedback = "1";
      const controls = document.createElement("div");
      controls.className = "bco-feedback";
      controls.innerHTML = `
        <span class="bco-feedback-label">helpful?</span>
        <button type="button" class="bco-feedback-btn" data-rating="helpful" aria-label="Полезный ответ">👍</button>
        <button type="button" class="bco-feedback-btn" data-rating="not_helpful" aria-label="Неполезный ответ">👎</button>`;
      controls.querySelectorAll("button").forEach((button) => {
        button.addEventListener("click", () => submit(text, button.dataset.rating, controls));
      });
      (bubble.parentElement || row).appendChild(controls);
    });
  }

  injectStyle();
  const observer = new MutationObserver(() => queueMicrotask(decorate));
  const start = () => {
    const log = document.querySelector("#chatLog");
    if (!log) return setTimeout(start, 250);
    observer.observe(log, { childList: true, subtree: true });
    decorate();
  };
  start();
})();
