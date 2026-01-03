/* app/webapp/static/bco.bridge.js */
/* eslint-disable no-var */
(function () {
  "use strict";

  function safe(fn) { try { return fn(); } catch (_) { return undefined; } }

  function isObj(x) { return x && typeof x === "object" && !Array.isArray(x); }

  function clampStr(x, n) {
    var s = (x == null) ? "" : String(x);
    if (!n || n <= 0) return "";
    return s.length <= n ? s : (s.slice(0, n - 1) + "…");
  }

  function tryParseJson(s) {
    if (typeof s !== "string") return null;
    var t = s.trim();
    if (!t) return null;
    if (t[0] !== "{" && t[0] !== "[") return null;
    return safe(function () { return JSON.parse(t); }) || null;
  }

  // нормализуем старые/кривые payload в формат, который ТВОЙ БОТ реально понимает
  function normalizePayload(input) {
    var obj = null;

    // sendData может прийти строкой JSON
    if (typeof input === "string") {
      obj = tryParseJson(input);
      if (!obj) {
        // если прислали просто текст — бот поймёт как {"type":"text","text":"..."} и пойдёт в brain
        return { type: "text", text: clampStr(input, 6000) };
      }
    } else if (isObj(input)) {
      obj = input;
    } else {
      return { type: "text", text: "" };
    }

    // если прислали не dict-объект
    if (!isObj(obj)) {
      return { type: "text", text: clampStr(String(obj), 6000) };
    }

    // 1) game_result ловится у бота по action="game_result" — не трогаем
    var action = String(obj.action || "").trim().toLowerCase();
    if (action === "game_result") return obj;

    // 2) if type missing but cmd present
    var type = String(obj.type || "").trim().toLowerCase();
    var cmd = String(obj.cmd || obj.command || "").trim().toLowerCase();

    // 3) Если type = cmd — это твоя текущая проблема
    //    Делаем маппинг cmd -> реальные type/fields, которые обрабатывает Router.
    if (type === "cmd" || (!type && cmd)) {
      // команда может храниться в obj.target / obj.page / obj.route / obj.to
      var target = String(obj.target || obj.page || obj.route || obj.to || "").trim().toLowerCase();

      // если cmd прямо содержит название раздела
      if (!target && cmd) target = cmd;

      // NAV
      // Router ждёт {type:"nav", target:"home|premium|training|vod|settings|zombies|..."}
      return {
        type: "nav",
        target: target || "home",
        profile: isObj(obj.profile) ? obj.profile : undefined
      };
    }

    // 4) Поддержка старого type="open" (часто ломает)
    //    Превращаем в nav.
    if (type === "open") {
      var t2 = String(obj.target || obj.to || obj.page || "home").trim().toLowerCase();
      return { type: "nav", target: t2 || "home", profile: isObj(obj.profile) ? obj.profile : undefined };
    }

    // 5) Поддержка type="profile" / "settings" -> set_profile
    if (type === "profile" || type === "settings") {
      var p = isObj(obj.profile) ? obj.profile : obj;
      return { type: "set_profile", profile: isObj(p) ? p : {} };
    }

    // 6) Если type уже нормальный — оставляем как есть
    //    (nav, set_profile, sync_request, one_line, training_plan, vod, zombies_open, zombies, pay)
    return obj;
  }

  // Главная отправка: объект -> JSON -> Telegram
  function send(payload) {
    var wa = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;
    var normalized = normalizePayload(payload);

    // чистим undefined чтобы не засорять
    var clean = {};
    for (var k in normalized) {
      if (Object.prototype.hasOwnProperty.call(normalized, k) && normalized[k] !== undefined) {
        clean[k] = normalized[k];
      }
    }

    var raw = "";
    try { raw = JSON.stringify(clean); }
    catch (_) { raw = JSON.stringify({ type: "text", text: "payload_json_error" }); }

    if (wa && typeof wa.sendData === "function") {
      wa.sendData(raw);
      return true;
    }
    // fallback: просто лог
    try { console.log("[BCO_BRIDGE] sendData fallback:", raw); } catch (_) {}
    return false;
  }

  // Патчим Telegram.WebApp.sendData, чтобы даже старый app.js работал без правок.
  function patchSendData() {
    var wa = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;
    if (!wa || typeof wa.sendData !== "function") return false;
    if (wa.__BCO_PATCHED__) return true;

    var original = wa.sendData.bind(wa);

    wa.sendData = function (data) {
      // data может быть строкой JSON или текстом
      var fixed = normalizePayload(data);
      var out = "";
      try { out = JSON.stringify(fixed); }
      catch (_) { out = JSON.stringify({ type: "text", text: "payload_json_error" }); }
      return original(out);
    };

    wa.__BCO_PATCHED__ = true;
    return true;
  }

  // экспорт
  window.BCO_BRIDGE = {
    normalizePayload: normalizePayload,
    send: send,
    patchSendData: patchSendData
  };

  // пытаемся пропатчить сразу и повторить чуть позже (иногда TG объект появляется позже)
  patchSendData();
  var tries = 0;
  var t = setInterval(function () {
    tries++;
    if (patchSendData() || tries >= 25) clearInterval(t);
  }, 120);
})();
