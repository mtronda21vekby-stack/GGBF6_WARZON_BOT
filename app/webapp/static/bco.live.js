/* BLACK CROWN OPS v18 — Live Intelligence + Cinematic Runtime */
(() => {
  "use strict";

  if (window.__BCO_LIVE_RUNTIME__) return;
  window.__BCO_LIVE_RUNTIME__ = true;

  const BUILD = String(window.__BCO_BUILD__ || "dev");
  const STREAM_PATH = "/webapp/api/ask/stream";
  const FALLBACK_PATH = "/webapp/api/ask";
  const STORAGE_KEY = "bco_chat_live_v18";
  const LEGACY_STORAGE_KEY = "bco_chat_v1";
  const CHAT_LIMIT = 80;
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const safe = (fn, fallback) => { try { const value = fn(); return value === undefined ? fallback : value; } catch (_) { return fallback; } };
  const tg = safe(() => window.Telegram && window.Telegram.WebApp, null);

  const runtime = {
    history: [],
    streaming: false,
    requestId: "",
    input: null,
    send: null,
    clear: null,
    export: null,
    chatLog: null,
    status: null,
    streamBubble: null,
    streamMeta: null,
    boot: null,
    fullscreenArmed: false,
  };

  function now() { return Date.now(); }

  function injectCss() {
    if ($('link[data-bco-v18="cinematic"]')) return;
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.dataset.bcoV18 = "cinematic";
    link.href = `/webapp/bco.cinematic.css?build=${encodeURIComponent(BUILD)}`;
    document.head.appendChild(link);
  }

  function haptic(kind = "light") {
    safe(() => {
      const api = tg?.HapticFeedback;
      if (!api) return;
      if (kind === "success" || kind === "error" || kind === "warning") {
        api.notificationOccurred(kind);
      } else if (kind === "selection") {
        api.selectionChanged();
      } else {
        api.impactOccurred(kind);
      }
    });
  }

  function escapeText(value) {
    return String(value ?? "");
  }

  function fmtTime(ts) {
    const date = new Date(Number(ts || now()));
    if (Number.isNaN(date.getTime())) return "--:--";
    return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
  }

  function getInitData() {
    return String(safe(() => tg?.initData, "") || "").trim();
  }

  function getProfile() {
    const profile = safe(() => window.BCO_APP?.getProfile?.(), {}) || {};
    return {
      game: String(profile.game || "Warzone").slice(0, 40),
      platform: String(profile.platform || "PC").slice(0, 40),
      input: String(profile.input || "Controller").slice(0, 40),
      difficulty: String(profile.mode || profile.difficulty || "Normal").slice(0, 40),
      voice: String(profile.voice || "TEAMMATE").slice(0, 40),
      role: String(profile.role || "Flex").slice(0, 40),
      bf6_class: String(profile.bf6_class || "Assault").slice(0, 40),
      zombies_map: String(profile.zombies_map || "Ashes").slice(0, 40),
      training_focus: String(profile.focus || "aim").slice(0, 40),
    };
  }

  function loadHistory() {
    let parsed = null;
    for (const key of [STORAGE_KEY, LEGACY_STORAGE_KEY]) {
      try {
        const raw = localStorage.getItem(key);
        if (!raw) continue;
        const candidate = JSON.parse(raw);
        if (candidate && Array.isArray(candidate.history)) {
          parsed = candidate.history;
          break;
        }
      } catch (_) {}
    }
    runtime.history = (Array.isArray(parsed) ? parsed : [])
      .map((item) => ({
        role: item?.role === "assistant" ? "assistant" : "user",
        text: String(item?.text || item?.content || "").slice(0, 12000),
        ts: Number(item?.ts || now()),
      }))
      .filter((item) => item.text)
      .slice(-CHAT_LIMIT);
  }

  function saveHistory() {
    const payload = JSON.stringify({ history: runtime.history.slice(-CHAT_LIMIT), ts: now(), version: 18 });
    try { localStorage.setItem(STORAGE_KEY, payload); } catch (_) {}
    try { localStorage.setItem(LEGACY_STORAGE_KEY, payload); } catch (_) {}
  }

  function makeRow(message, streaming = false) {
    const row = document.createElement("div");
    row.className = `chat-row ${message.role === "assistant" ? "bot" : "me"}`;

    const stack = document.createElement("div");
    const bubble = document.createElement("div");
    bubble.className = `bubble${streaming ? " is-streaming" : ""}`;
    bubble.textContent = escapeText(message.text || (streaming ? "Synchronizing intelligence…" : ""));

    const meta = document.createElement("div");
    meta.className = "chat-meta";
    meta.textContent = `${message.role === "assistant" ? "BCO" : "YOU"} • ${fmtTime(message.ts)}`;

    stack.append(bubble, meta);
    row.append(stack);
    return { row, bubble, meta };
  }

  function renderHistory() {
    if (!runtime.chatLog) return;
    runtime.chatLog.innerHTML = "";
    if (!runtime.history.length) {
      const empty = makeRow({
        role: "assistant",
        text: "OPERATOR LINK READY. Опиши ситуацию — Intelligence Core начнёт анализ в реальном времени.",
        ts: now(),
      });
      runtime.chatLog.append(empty.row);
    } else {
      runtime.history.forEach((message) => runtime.chatLog.append(makeRow(message).row));
    }
    requestAnimationFrame(() => { runtime.chatLog.scrollTop = runtime.chatLog.scrollHeight; });
  }

  function appendMessage(role, text) {
    const message = { role, text: String(text || "").trim(), ts: now() };
    if (!message.text) return null;
    runtime.history.push(message);
    runtime.history = runtime.history.slice(-CHAT_LIMIT);
    saveHistory();
    if (runtime.chatLog) {
      const node = makeRow(message);
      runtime.chatLog.append(node.row);
      runtime.chatLog.scrollTop = runtime.chatLog.scrollHeight;
      return node;
    }
    return null;
  }

  function createStreamBubble() {
    if (!runtime.chatLog) return null;
    const message = { role: "assistant", text: "Synchronizing intelligence…", ts: now() };
    const node = makeRow(message, true);
    node.meta.textContent = "BCO • LIVE INTELLIGENCE";
    runtime.chatLog.append(node.row);
    runtime.chatLog.scrollTop = runtime.chatLog.scrollHeight;
    runtime.streamBubble = node.bubble;
    runtime.streamMeta = node.meta;
    return node;
  }

  function updateStreamBubble(text, phase, elapsedMs) {
    if (!runtime.streamBubble) createStreamBubble();
    if (runtime.streamBubble && text) runtime.streamBubble.textContent = String(text);
    if (runtime.streamMeta) {
      const phaseText = String(phase || "LIVE").replaceAll("_", " ").toUpperCase();
      const time = Number.isFinite(Number(elapsedMs)) ? ` • ${(Number(elapsedMs) / 1000).toFixed(1)}s` : "";
      runtime.streamMeta.textContent = `BCO • ${phaseText}${time}`;
    }
    if (runtime.chatLog) runtime.chatLog.scrollTop = runtime.chatLog.scrollHeight;
  }

  function finalizeStreamBubble(reply) {
    const text = String(reply || "").trim() || "No response payload.";
    if (runtime.streamBubble) {
      runtime.streamBubble.textContent = text;
      runtime.streamBubble.classList.remove("is-streaming");
    }
    if (runtime.streamMeta) runtime.streamMeta.textContent = `BCO • ${fmtTime(now())}`;
    runtime.history.push({ role: "assistant", text, ts: now() });
    runtime.history = runtime.history.slice(-CHAT_LIMIT);
    saveHistory();
    runtime.streamBubble = null;
    runtime.streamMeta = null;
    if (runtime.chatLog) runtime.chatLog.scrollTop = runtime.chatLog.scrollHeight;
  }

  function discardStreamBubble() {
    const bubble = runtime.streamBubble;
    if (bubble) bubble.closest(".chat-row")?.remove();
    runtime.streamBubble = null;
    runtime.streamMeta = null;
  }

  function ensureLiveStatus() {
    const shell = $(".chat-shell");
    const head = $(".chat-head", shell || document);
    if (!shell || !head) return;
    let status = $("#bcoLiveStatus");
    if (!status) {
      status = document.createElement("div");
      status.id = "bcoLiveStatus";
      status.className = "bco-live-status";
      status.innerHTML = `
        <span><span class="bco-live-bars"><i></i><i></i><i></i><i></i></span></span>
        <strong id="bcoLivePhase">INTELLIGENCE LINK IDLE</strong>
        <span id="bcoLiveLatency">0.0s</span>`;
      head.insertAdjacentElement("afterend", status);
    }
    runtime.status = status;
  }

  function setLiveStatus(active, phase = "INTELLIGENCE LINK IDLE", elapsedMs = 0) {
    ensureLiveStatus();
    runtime.status?.classList.toggle("is-active", !!active);
    const phaseEl = $("#bcoLivePhase");
    const latencyEl = $("#bcoLiveLatency");
    if (phaseEl) phaseEl.textContent = String(phase || "LIVE").replaceAll("_", " ").toUpperCase();
    if (latencyEl) latencyEl.textContent = `${(Number(elapsedMs || 0) / 1000).toFixed(1)}s`;
  }

  async function fallbackAsk(text, body, headers) {
    const response = await fetch(FALLBACK_PATH, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });
    const payload = await response.json().catch(() => null);
    if (!response.ok || !payload?.reply) throw new Error("fallback_unavailable");
    return String(payload.reply);
  }

  async function streamAsk(text, onEvent) {
    const initData = getInitData();
    const body = {
      text: String(text || "").trim(),
      profile: getProfile(),
      history: runtime.history.slice(-20).map((item) => ({
        role: item.role,
        content: String(item.text || "").slice(0, 2000),
      })),
      initData,
    };
    const headers = {
      "Content-Type": "application/json; charset=utf-8",
      "Accept": "application/x-ndjson",
      "X-BCO-Version": "command-center-live-18.0.0",
    };
    if (initData) headers["X-Telegram-Init-Data"] = initData;

    const response = await fetch(STREAM_PATH, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      cache: "no-store",
    });

    if (!response.ok || !response.body?.getReader) {
      return await fallbackAsk(text, body, headers);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let finalReply = "";

    const consumeLine = (line) => {
      const trimmed = String(line || "").trim();
      if (!trimmed) return;
      let event = null;
      try { event = JSON.parse(trimmed); } catch (_) { return; }
      onEvent?.(event);
      if (event?.type === "final") finalReply = String(event.reply || "");
      if (event?.type === "error") throw new Error(String(event.error || "generation_unavailable"));
    };

    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) consumeLine(line);
      if (done) break;
    }
    if (buffer.trim()) consumeLine(buffer);
    if (!finalReply) throw new Error("stream_ended_without_final");
    return finalReply;
  }

  function setSending(active) {
    runtime.streaming = !!active;
    if (runtime.send) runtime.send.disabled = !!active;
    if (runtime.input) runtime.input.disabled = !!active;
  }

  async function sendChat() {
    if (runtime.streaming) return;
    const text = String(runtime.input?.value || "").trim();
    if (!text) {
      haptic("warning");
      runtime.input?.focus();
      return;
    }

    appendMessage("user", text);
    if (runtime.input) runtime.input.value = "";
    createStreamBubble();
    setSending(true);
    setLiveStatus(true, "SYNCHRONIZING CONTEXT", 0);
    haptic("medium");
    const started = performance.now();

    try {
      const reply = await streamAsk(text, (event) => {
        const elapsed = performance.now() - started;
        if (event.type === "meta") {
          runtime.requestId = String(event.request_id || "");
          setLiveStatus(true, event.trusted ? "TRUSTED OPERATOR LINK" : "DEMO CONTEXT", elapsed);
        } else if (event.type === "partial") {
          const partial = String(event.text || "");
          updateStreamBubble(partial, event.phase, elapsed);
          setLiveStatus(true, event.phase || "LIVE ANALYSIS", elapsed);
        } else if (event.type === "pulse") {
          setLiveStatus(true, "LIVE ANALYSIS", event.elapsed_ms || elapsed);
        }
      });
      finalizeStreamBubble(reply);
      setLiveStatus(false, "INTELLIGENCE LINK READY", performance.now() - started);
      haptic("success");
    } catch (error) {
      discardStreamBubble();
      appendMessage(
        "assistant",
        "⚠️ Live Intelligence channel недоступен. Контекст сохранён; повтори запрос через несколько секунд.",
      );
      setLiveStatus(false, "RECOVERY REQUIRED", performance.now() - started);
      haptic("error");
      console.warn("[BCO v18] live chat failed", error);
    } finally {
      setSending(false);
      runtime.input?.focus();
    }
  }

  function clearChat() {
    runtime.history = [];
    saveHistory();
    renderHistory();
    haptic("success");
  }

  async function exportChat() {
    const text = runtime.history
      .map((item) => `${item.role === "assistant" ? "BCO" : "YOU"}: ${item.text}`)
      .join("\n\n") || "—";
    try {
      await navigator.clipboard.writeText(text);
      haptic("success");
    } catch (_) {
      haptic("error");
    }
  }

  function cloneControl(node, id) {
    if (!node) return null;
    const clone = node.cloneNode(true);
    clone.id = id;
    node.replaceWith(clone);
    return clone;
  }

  function mountLiveChat() {
    runtime.chatLog = $("#chatLog");
    const oldInput = $("#chatInput");
    const oldSend = $("#btnChatSend");
    const oldClear = $("#btnChatClear");
    const oldExport = $("#btnChatExport");
    if (!runtime.chatLog || !oldInput || !oldSend) return false;

    runtime.input = cloneControl(oldInput, "chatInputLive");
    runtime.input.placeholder = "Опиши файт: контекст · решение · результат";
    runtime.send = cloneControl(oldSend, "btnChatSendLive");
    runtime.send.setAttribute("aria-label", "Send live intelligence request");
    runtime.send.textContent = "➤";
    runtime.clear = cloneControl(oldClear, "btnChatClearLive");
    runtime.export = cloneControl(oldExport, "btnChatExportLive");

    runtime.send.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      sendChat();
    });
    runtime.input.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendChat();
      }
    });
    runtime.clear?.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      clearChat();
    });
    runtime.export?.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      exportChat();
    });

    loadHistory();
    renderHistory();
    ensureLiveStatus();
    return true;
  }

  function mountBrand() {
    const logo = $(".logo");
    if (logo) {
      logo.textContent = "";
      const mark = document.createElement("span");
      mark.className = "bco-core-mark";
      mark.setAttribute("aria-hidden", "true");
      logo.append(mark);
      logo.setAttribute("role", "button");
      logo.setAttribute("aria-label", "Open command palette");
      logo.tabIndex = 0;
    }
    const sub = $(".brand-sub");
    if (sub) sub.textContent = "ARTIFICIAL COMPETITIVE INTELLIGENCE";
  }

  function telemetryValue(label, value, signal = false) {
    const cell = document.createElement("div");
    cell.className = "bco-telemetry-cell";
    const small = document.createElement("small");
    small.textContent = label;
    const strong = document.createElement("strong");
    if (signal) {
      const dot = document.createElement("i");
      dot.className = "bco-signal-dot";
      strong.append(dot);
    }
    strong.append(document.createTextNode(String(value || "—")));
    cell.append(small, strong);
    return cell;
  }

  function mountTelemetry() {
    const header = $(".app-header");
    if (!header || $("#bcoTelemetry")) return;
    const rail = document.createElement("div");
    rail.id = "bcoTelemetry";
    rail.className = "bco-telemetry-rail";
    rail.append(
      telemetryValue("network", navigator.onLine ? "online" : "offline", true),
      telemetryValue("identity", getInitData() ? "verified" : "demo"),
      telemetryValue("core", "live v18"),
      telemetryValue("build", BUILD.slice(0, 8)),
    );
    header.append(rail);
  }

  function updateNetworkState() {
    document.documentElement.classList.toggle("bco-offline", !navigator.onLine);
    const cell = $("#bcoTelemetry .bco-telemetry-cell:first-child strong");
    if (cell) {
      const dot = $(".bco-signal-dot", cell);
      cell.textContent = "";
      if (dot) cell.append(dot);
      else {
        const freshDot = document.createElement("i");
        freshDot.className = "bco-signal-dot";
        cell.append(freshDot);
      }
      cell.append(document.createTextNode(navigator.onLine ? "online" : "offline"));
    }
  }

  function selectTab(name) {
    const button = $(`.nav-btn[data-tab="${name}"]`);
    button?.click();
  }

  function mountCommandPalette() {
    if ($("#bcoCommandPalette")) return;
    const palette = document.createElement("div");
    palette.id = "bcoCommandPalette";
    palette.className = "bco-command-palette";
    palette.innerHTML = `
      <div class="bco-command-panel" role="dialog" aria-modal="true" aria-label="BLACK CROWN command palette">
        <div class="bco-command-head"><div><strong>COMMAND PALETTE</strong><span>BLACK CROWN OPS // V18</span></div><button class="bco-command-close" type="button">✕</button></div>
        <div class="bco-command-grid">
          <button class="bco-command-action" data-action="ai" type="button">🧠 LIVE AI<small>focus intelligence input</small></button>
          <button class="bco-command-action" data-action="intel" type="button">◈ PLAYER INTEL<small>persistent analytics</small></button>
          <button class="bco-command-action" data-action="training" type="button">🎯 TRAINING<small>measurable protocol</small></button>
          <button class="bco-command-action" data-action="vod" type="button">🎬 VOD LAB<small>sampled-frame analysis</small></button>
          <button class="bco-command-action" data-action="settings" type="button">⚙ SYSTEM<small>operator configuration</small></button>
          <button class="bco-command-action" data-action="bot" type="button">◼ BOT CONSOLE<small>return to Telegram</small></button>
        </div>
      </div>`;
    document.body.append(palette);

    const close = () => {
      palette.classList.remove("is-open");
      haptic("selection");
    };
    const open = () => {
      palette.classList.add("is-open");
      haptic("medium");
    };

    $(".bco-command-close", palette)?.addEventListener("click", close);
    palette.addEventListener("click", (event) => {
      if (event.target === palette) return close();
      const action = event.target.closest?.("[data-action]")?.dataset.action;
      if (!action) return;
      close();
      if (action === "ai") {
        selectTab("home");
        setTimeout(() => runtime.input?.focus(), 120);
      } else if (action === "intel") {
        selectTab("intel");
      } else if (action === "training") {
        selectTab("coach");
      } else if (action === "vod") {
        selectTab("vod");
      } else if (action === "settings") {
        selectTab("settings");
      } else if (action === "bot") {
        safe(() => window.BCO_APP?.sendToBot?.({ type: "nav", target: "menu", profile: true }));
      }
    });

    const logo = $(".logo");
    logo?.addEventListener("click", open);
    logo?.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") open();
    });
    document.addEventListener("keydown", (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        palette.classList.contains("is-open") ? close() : open();
      }
      if (event.key === "Escape" && palette.classList.contains("is-open")) close();
    });
  }

  function mountBootSequence() {
    if ($("#bcoBootSequence")) return;
    const boot = document.createElement("div");
    boot.id = "bcoBootSequence";
    boot.className = "bco-boot-sequence";
    boot.innerHTML = `
      <div class="bco-boot-panel">
        <div class="bco-boot-brand"><span class="bco-boot-mark"></span><div><div class="bco-boot-title">BLACK CROWN OPS</div><div class="bco-boot-sub">Artificial Competitive Intelligence</div></div></div>
        <div class="bco-boot-modules">
          <div class="bco-boot-module" data-module="telegram"><i></i><span>Telegram secure context</span><span>checking</span></div>
          <div class="bco-boot-module" data-module="memory"><i></i><span>Persistent player memory</span><span>syncing</span></div>
          <div class="bco-boot-module" data-module="stream"><i></i><span>Live intelligence channel</span><span>arming</span></div>
          <div class="bco-boot-module" data-module="interface"><i></i><span>Cinematic interface</span><span>loading</span></div>
        </div>
        <div class="bco-boot-progress"><i></i></div>
      </div>`;
    document.body.append(boot);
    runtime.boot = boot;

    const modules = ["telegram", "memory", "stream", "interface"];
    modules.forEach((name, index) => {
      setTimeout(() => {
        const row = $(`[data-module="${name}"]`, boot);
        row?.classList.add("is-ready");
        const state = row?.querySelector("span:last-child");
        if (state) state.textContent = name === "telegram" && !getInitData() ? "demo" : "ready";
        const progress = $(".bco-boot-progress i", boot);
        if (progress) progress.style.width = `${((index + 1) / modules.length) * 100}%`;
        haptic("selection");
      }, 150 + index * 180);
    });
    setTimeout(() => {
      boot.classList.add("is-complete");
      setTimeout(() => boot.remove(), 650);
    }, 1050);
  }

  function configurePerformance() {
    document.documentElement.classList.add("bco-v18");
    const reduced = matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
    const cores = Number(navigator.hardwareConcurrency || 8);
    const memory = Number(navigator.deviceMemory || 8);
    const lowPower = !!reduced || cores <= 4 || memory <= 4;
    document.documentElement.classList.toggle("bco-low-power", lowPower);
  }

  function armFullscreenAndHaptics() {
    if (runtime.fullscreenArmed) return;
    runtime.fullscreenArmed = true;
    document.addEventListener("pointerup", (event) => {
      const button = event.target.closest?.("button, .chip, .nav-btn, .seg-btn");
      if (button) haptic(button.matches(".primary, .active") ? "medium" : "light");
      safe(() => tg?.expand?.());
      safe(() => tg?.disableVerticalSwipes?.());
    }, { capture: true, passive: true });
  }

  async function waitForBase(timeoutMs = 7000) {
    const started = now();
    while (now() - started < timeoutMs) {
      if (window.BCO_APP && $("#chatLog") && $("#chatInput") && $("#btnChatSend")) return true;
      await new Promise((resolve) => setTimeout(resolve, 70));
    }
    return false;
  }

  async function init() {
    injectCss();
    configurePerformance();
    mountBootSequence();
    const baseReady = await waitForBase();
    if (!baseReady) {
      console.warn("[BCO v18] base UI did not become ready in time");
      return;
    }

    mountBrand();
    mountTelemetry();
    updateNetworkState();
    mountCommandPalette();
    mountLiveChat();
    armFullscreenAndHaptics();

    window.addEventListener("online", updateNetworkState);
    window.addEventListener("offline", updateNetworkState);
    safe(() => tg?.ready?.());
    safe(() => tg?.expand?.());
    safe(() => tg?.setHeaderColor?.("#02070a"));
    safe(() => tg?.setBackgroundColor?.("#02070a"));

    window.BCO_LIVE = {
      send: sendChat,
      clear: clearChat,
      openPalette: () => $("#bcoCommandPalette")?.classList.add("is-open"),
      version: "18.0.0",
    };
    window.__BCO_LIVE_LAYER_LOADED__ = true;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
