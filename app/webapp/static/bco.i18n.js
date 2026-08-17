/* BLACK CROWN OPS v38 — ecosystem RU/EN presentation authority */
(() => {
  "use strict";
  if (window.__BCO_I18N_V38_LOADED__) return;
  window.__BCO_I18N_V38_LOADED__ = true;

  const KEY = "bco_locale_v38";
  const RU = /[А-Яа-яЁё]/g;
  const EN = /[A-Za-z]/g;
  const tgLang = String(window.Telegram?.WebApp?.initDataUnsafe?.user?.language_code || "").toLowerCase();
  const browserLang = String(navigator.language || "").toLowerCase();
  const saved = (() => { try { return localStorage.getItem(KEY) || ""; } catch (_) { return ""; } })();
  let locale = saved === "ru" || saved === "en" ? saved : ((tgLang || browserLang).startsWith("ru") ? "ru" : "en");

  const exact = {
    en: {
      "Сообщение": "Message",
      "Меню": "Menu",
      "Настройки": "Settings",
      "Профиль": "Profile",
      "Тренировка": "Training",
      "Открыть": "Open",
      "Назад": "Back",
      "Готово": "Done",
      "Обновить": "Refresh",
      "Отправить": "Send",
      "Игра": "Game",
      "Режим": "Mode",
      "Платформа": "Platform",
      "Голос": "Voice",
      "Система": "System",
      "Премиум": "Premium",
      "Синтетический AI-голос · BLACK CROWN OPS": "Synthetic AI voice · BLACK CROWN OPS",
      "Нет подтверждённой слабости. Unknown остаётся unknown.": "No confirmed weakness. Unknown remains unknown.",
      "Собираем данные": "Collecting data",
      "таймкоды не указаны": "timestamps not provided"
    },
    ru: {}
  };

  const phrases = [
    ["Синтетический AI-голос", "Synthetic AI voice"],
    ["Русский", "Russian"],
    ["Английский", "English"],
    ["только текст", "text only"],
    ["Голос переключён", "Voice switched"],
    ["Озвучка сейчас недоступна", "Voice output is temporarily unavailable"],
    ["Пока нет AI-ответа, который можно озвучить", "There is no AI response to speak yet"],
    ["Сначала выбери", "Choose first"],
    ["Недостаточно", "Insufficient"],
    ["требуется свежая сессия", "a fresh session is required"],
    ["Unknown остаётся unknown", "Unknown remains unknown"]
  ];

  function detectText(text) {
    const s = String(text || "");
    const ru = (s.match(RU) || []).length;
    const en = (s.match(EN) || []).length;
    if (ru >= 2 && ru > en) return "ru";
    if (en >= 2 && en > ru) return "en";
    return null;
  }

  function translateString(value) {
    const s = String(value || "");
    if (locale === "ru") return s;
    if (exact.en[s]) return exact.en[s];
    let out = s;
    phrases.forEach(([ru, en]) => { out = out.split(ru).join(en); });
    return out;
  }

  function translateNode(node) {
    if (!node) return;
    const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach((n) => {
      const parent = n.parentElement;
      if (!parent || ["SCRIPT","STYLE","TEXTAREA","INPUT"].includes(parent.tagName)) return;
      const raw = n.nodeValue || "";
      const trimmed = raw.trim();
      if (!trimmed) return;
      const translated = translateString(trimmed);
      if (translated !== trimmed) n.nodeValue = raw.replace(trimmed, translated);
    });
    node.querySelectorAll?.("input[placeholder],textarea[placeholder]").forEach((el) => {
      const p = el.getAttribute("placeholder") || "";
      const t = translateString(p); if (t !== p) el.setAttribute("placeholder", t);
    });
  }

  function apply() {
    document.documentElement.lang = locale;
    document.documentElement.dataset.bcoLocale = locale;
    translateNode(document.body);
    window.dispatchEvent(new CustomEvent("bco:locale", { detail: { locale } }));
  }

  function setLocale(next, persist = true) {
    if (next !== "ru" && next !== "en") return;
    locale = next;
    if (persist) { try { localStorage.setItem(KEY, next); } catch (_) {} }
    apply();
  }

  function observeTypedLanguage() {
    document.addEventListener("input", (event) => {
      const el = event.target;
      if (!(el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement)) return;
      const detected = detectText(el.value);
      if (detected && !saved) setLocale(detected, false);
    }, true);
  }

  const observer = new MutationObserver((mutations) => {
    mutations.forEach((m) => m.addedNodes.forEach((n) => { if (n.nodeType === 1) translateNode(n); }));
  });
  if (document.body) { observer.observe(document.body, { childList: true, subtree: true }); apply(); }
  else document.addEventListener("DOMContentLoaded", () => { observer.observe(document.body, { childList: true, subtree: true }); apply(); }, { once: true });
  observeTypedLanguage();

  window.BCO_I18N = { get locale() { return locale; }, setLocale, detectText, t: translateString, apply };
})();
