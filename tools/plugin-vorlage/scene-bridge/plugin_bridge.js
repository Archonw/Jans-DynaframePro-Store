/*
 * plugin_bridge.js – Szene erreicht ihr Plugin auch bei DynaFrames eigenem HTTPS/Login.
 *
 * Seit DynaFrame 2026.11.14 (WebUI-Sicherheit an) antwortet die Weboberfläche auf dem
 * Rahmen selbst nicht mehr: 127.0.0.1:8003 gibt 403, Port 80 gibt 421/302. Die Szenen
 * laufen im Renderer unter http://127.0.0.1:8001 (Engine) und holten ihre Daten bisher
 * über /Plugins/Advanced/<Plugin>/ der Weboberfläche.
 *
 * Dieses Skript wird VOR den Szenen-Skripten geladen. Läuft die Szene auf dem Rahmen
 * (Ursprung = Engine auf Loopback), fragt es die Engine nach der lokalen Adresse der
 * Plugin-Seite (GET /plugins/<Plugin>/advanced-page -> localUrl, z. B.
 * http://127.0.0.1:45747/) und schreibt jede Adresse mit /Plugins/Advanced/<Plugin>/
 * darauf um: fetch, XMLHttpRequest, EventSource, src von Bildern/Video/Audio und
 * backgroundImage. Die Szenen-Endpunkte unserer Plugins schicken schon
 * Access-Control-Allow-Origin: *, das Plugin muss nichts ändern.
 *
 * Im Browser über die Weboberfläche (https, gleicher Ursprung) oder ohne DynaFrame-Login
 * tut das Skript nichts Sichtbares: Es schreibt nur um, wenn die Engine eine localUrl
 * liefert, und die gibt es nur auf dem Rahmen selbst.
 *
 * Startet das Plugin neu (neuer zufälliger Port), schlägt ein fetch fehl; dann wird die
 * Adresse neu geholt und der Aufruf einmal wiederholt. Alle 30 s wird sie aufgefrischt.
 *
 * Nach einem Neustart des Rahmens startet DynaFrame die Playlist nach ~40 s, die Plugins
 * aber erst nach 180 s und dann einzeln alle 30 s (appsettings Plugins.StartupDelaySeconds /
 * StartupBetweenPluginsDelaySeconds). Mit vielen Plugins kommt das eigene erst nach
 * Minuten dran, solange meldet die Szene "antwortet nicht" (Contact Sheet, 21.11.2026).
 * Darum: meldet advanced-page available:false und steht das Plugin in GET /plugins als
 * eingeschaltet, aber nicht laufend, bittet die Brücke die Engine mit
 * POST /plugins/<Plugin>/start, es sofort zu starten (höchstens alle 45 s je Plugin).
 * Ausgeschaltete Plugins werden nie gestartet. Solange das läuft, steht in
 * window.__dfrPluginBridge.starting[<Plugin>] die Zeit des Starts; Szenen können damit
 * "startet gerade …" statt "antwortet nicht" zeigen (bridge.isStarting(<Plugin>)).
 *
 * Einbau: tools/plugin-vorlage/scene-bridge/apply.py <pack>/dynamic/index.html
 */
(function () {
  "use strict";
  if (window.__dfrPluginBridge) return;

  const loopback = /^(127\.\d+\.\d+\.\d+|localhost|\[::1\])$/i.test(location.hostname);
  const onEngine = location.protocol === "http:" && location.port === "8001";
  const bridge = window.__dfrPluginBridge = {
    active: false, urls: {}, starting: {}, rewrite: (u) => u,
    isStarting: (id) => Date.now() - (bridge.starting[id] || 0) < 120000
  };
  if (!loopback || !onEngine) return;

  const origFetch = window.fetch.bind(window);
  const MARK = /\/Plugins\/Advanced\/([A-Za-z0-9_.-]+)\/(.*)$/;
  const cache = bridge.urls;              // Plugin -> { url, at }
  const TTL = 30000;

  function lookupSync(id) {
    try {
      const xhr = new XMLHttpRequest();
      xhr.open("GET", `/plugins/${encodeURIComponent(id)}/advanced-page`, false);
      xhr.send();
      if (xhr.status !== 200) return "";
      const data = JSON.parse(xhr.responseText || "{}");
      const url = String(data.localUrl || data.LocalUrl || "");
      if (!url) wakePlugin(id, data);
      else delete bridge.starting[id];
      return /^http:\/\/(127\.\d+\.\d+\.\d+|localhost|\[::1\]):\d+\//i.test(url) ? url : "";
    } catch (_) {
      return "";
    }
  }

  async function lookupAsync(id) {
    try {
      const response = await origFetch(`/plugins/${encodeURIComponent(id)}/advanced-page`, { cache: "no-store" });
      if (!response.ok) return "";
      const data = await response.json();
      const url = String(data.localUrl || data.LocalUrl || "");
      if (!url) wakePlugin(id, data);
      else delete bridge.starting[id];
      return /^http:\/\/(127\.\d+\.\d+\.\d+|localhost|\[::1\]):\d+\//i.test(url) ? url : "";
    } catch (_) {
      return "";
    }
  }

  // Plugin noch nicht gestartet (Rahmen gerade neu gestartet): Engine bitten, es jetzt zu starten
  const woken = {};                       // Plugin -> Zeit des letzten Versuchs
  async function wakePlugin(id, page) {
    if (!page || page.available || (page.declared === false)) return;
    if (Date.now() - (woken[id] || 0) < 45000) return;
    woken[id] = Date.now();
    try {
      const response = await origFetch("/plugins", { cache: "no-store" });
      if (!response.ok) return;
      const list = await response.json();
      const rows = Array.isArray(list) ? list : (list.plugins || list.items || []);
      const lower = id.toLowerCase();
      const row = rows.find((r) => r && String(r.name || r.pluginName || r.id || "").toLowerCase() === lower);
      if (!row || row.enabled !== true || row.running === true) return;
      bridge.starting[id] = Date.now();
      const started = await origFetch(`/plugins/${encodeURIComponent(id)}/start`, { method: "POST", cache: "no-store" });
      console.info(`[plugin_bridge] ${id} war noch nicht gestartet, Start angefordert: ${started.status}`);
      if (!started.ok) delete bridge.starting[id];
    } catch (error) {
      console.warn(`[plugin_bridge] ${id} starten: ${error}`);
    }
  }

  function localFor(id) {
    const hit = cache[id];
    if (hit && hit.url && Date.now() - hit.at < TTL) return hit.url;
    if (hit && !hit.url && Date.now() - hit.at < 3000) return "";
    const url = lookupSync(id) || (hit && hit.url) || "";
    cache[id] = { url, at: Date.now() };
    if (url) bridge.active = true;
    return url;
  }

  function rewrite(input) {
    if (typeof input !== "string" || input.indexOf("/Plugins/Advanced/") < 0) return input;
    let absolute;
    try { absolute = new URL(input, location.href); } catch (_) { return input; }
    const match = absolute.href.match(MARK);
    if (!match) return input;
    const local = localFor(match[1]);
    return local ? local + match[2] : input;
  }
  bridge.rewrite = rewrite;

  // fetch: umschreiben, bei Netzfehler Adresse neu holen und einmal wiederholen
  window.fetch = async function (resource, init) {
    const isRequest = typeof Request !== "undefined" && resource instanceof Request;
    const raw = isRequest ? resource.url : String(resource);
    const target = rewrite(raw);
    if (target === raw) return origFetch(resource, init);
    const options = Object.assign({}, init || {});
    if (options.credentials === "include") options.credentials = "same-origin";
    const go = (url) => isRequest ? origFetch(new Request(url, resource), options) : origFetch(url, options);
    try {
      return await go(target);
    } catch (error) {
      const id = (new URL(raw, location.href).href.match(MARK) || [])[1];
      if (!id) throw error;
      const fresh = await lookupAsync(id);
      cache[id] = { url: fresh, at: Date.now() };
      if (!fresh) throw error;
      return go(rewrite(raw));
    }
  };

  // XMLHttpRequest / EventSource
  const origOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    return origOpen.call(this, method, rewrite(String(url)), ...rest);
  };
  if (window.EventSource) {
    const OrigES = window.EventSource;
    window.EventSource = function (url, config) { return new OrigES(rewrite(String(url)), config); };
    window.EventSource.prototype = OrigES.prototype;
    ["CONNECTING", "OPEN", "CLOSED"].forEach((k) => { window.EventSource[k] = OrigES[k]; });
  }

  // src von Bildern, Video, Audio, <source>, Iframes
  function hookSrc(proto) {
    const desc = proto && Object.getOwnPropertyDescriptor(proto, "src");
    if (!desc || !desc.set) return;
    Object.defineProperty(proto, "src", {
      configurable: true, enumerable: desc.enumerable,
      get() { return desc.get.call(this); },
      set(value) { desc.set.call(this, rewrite(String(value))); }
    });
  }
  [window.HTMLImageElement, window.HTMLMediaElement, window.HTMLSourceElement, window.HTMLIFrameElement, window.HTMLScriptElement]
    .forEach((C) => C && hookSrc(C.prototype));
  const origSetAttribute = Element.prototype.setAttribute;
  Element.prototype.setAttribute = function (name, value) {
    if (/^(src|href|poster)$/i.test(name)) value = rewrite(String(value));
    return origSetAttribute.call(this, name, value);
  };

  // CSS: style.backgroundImage = url("…/Plugins/Advanced/…")
  const cssUrls = (value) => typeof value === "string" && value.indexOf("/Plugins/Advanced/") >= 0
    ? value.replace(/url\((['"]?)([^'")]+)\1\)/g, (all, q, u) => `url(${q}${rewrite(u)}${q})`) : value;
  const styleProto = window.CSSStyleDeclaration && CSSStyleDeclaration.prototype;
  ["backgroundImage", "background", "content", "maskImage", "borderImageSource"].forEach((prop) => {
    let owner = styleProto;
    while (owner && !Object.getOwnPropertyDescriptor(owner, prop)) owner = Object.getPrototypeOf(owner);
    const desc = owner && Object.getOwnPropertyDescriptor(owner, prop);
    if (!desc || !desc.set) return;
    Object.defineProperty(owner, prop, {
      configurable: true, enumerable: desc.enumerable,
      get() { return desc.get.call(this); },
      set(value) { desc.set.call(this, cssUrls(value)); }
    });
  });
  if (styleProto && styleProto.setProperty) {
    const origSetProperty = styleProto.setProperty;
    styleProto.setProperty = function (name, value, priority) {
      return origSetProperty.call(this, name, cssUrls(value), priority);
    };
  }

  // Adressen im Hintergrund frisch halten
  setInterval(() => {
    Object.keys(cache).forEach(async (id) => {
      const url = await lookupAsync(id);
      if (url) cache[id] = { url, at: Date.now() };
    });
  }, TTL - 5000);
})();
