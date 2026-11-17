// ------------------------------------------------------------ Aufklappen (tools/plugin-vorlage/accordion)
// Karten und Abschnitte auf- und zuklappen, damit lange Plugin-Seiten übersichtlich
// bleiben. Gesteuert nur über Attribute im HTML (Anleitung: accordion/README.md):
//   <section class="card" data-fold="immich" data-fold-when="uses:immich"> …
//   <h3 class="sub" data-fold="immichFilter" data-fold-start="closed" data-fold-badge="count">
// Eigene Texte (DE/EN/ES) stehen hier, die Sprache kommt aus <html lang>.
(() => {
  const TEXT = {
    open: ["Aufklappen", "Expand", "Desplegar"],
    close: ["Zuklappen", "Collapse", "Plegar"],
    active: ["{n} aktiv", "{n} active", "{n} activos"],
    none: ["Keine Filter", "No filters", "Sin filtros"],
    set: ["Eingerichtet", "Set up", "Configurado"],
    optional: ["Optional", "Optional", "Opcional"],
    lines: ["{n} eingetragen", "{n} entered", "{n} introducidos"],
    svcOk: ["Alles erreichbar", "All reachable", "Todo accesible"],
    svcBad: ["{n} Problem", "{n} problem", "{n} problema"],
    svcBads: ["{n} Probleme", "{n} problems", "{n} problemas"],
    svcWarn: ["Teilweise", "Partly", "Parcial"],
    svcWait: ["Wird geprüft", "Checking", "Comprobando"],
    "off:immich": ["Nur mit Immich als Quelle nötig", "Only needed with Immich as source", "Solo con Immich como fuente"],
    "off:dynaframe": ["Nur mit Fotos aus DynaFrame nötig", "Only needed with photos from DynaFrame", "Solo con fotos de DynaFrame"],
    "off:library": ["Nur mit „Alle Fotos in DynaFrame“ nötig", "Only needed with “All photos in DynaFrame”", "Solo con «Todas las fotos de DynaFrame»"],
    off: ["Gerade nicht gebraucht", "Not needed right now", "No se necesita ahora"],
  };
  const LANGS = ["de", "en", "es"];
  const say = (key, n) => {
    const row = TEXT[key] || TEXT.off;
    const i = Math.max(0, LANGS.indexOf(document.documentElement.lang));
    return (row[i] ?? row[0]).replace("{n}", String(n));
  };
  const store = (() => {
    try { return window.localStorage; } catch (_) { return null; }
  })();
  const keyOf = (id) => `fold:${location.pathname}:${id}`;
  const remembered = (id) => {
    try { return JSON.parse(store?.getItem(keyOf(id)) || "null"); } catch (_) { return null; }
  };
  const remember = (id, value) => {
    try { store?.setItem(keyOf(id), JSON.stringify(value)); } catch (_) { /* privat */ }
  };

  // Quellen-Auswahl: jedes <select>, das eine Immich-Option hat (auch Quellen-Zeilen, die studio.js erst später baut)
  const DF_KINDS = ["library", "folders", "playlist", "same"];
  function sourceValues() {
    const values = [];
    for (const select of document.querySelectorAll("select")) {
      if ([...select.options].some((o) => o.value.startsWith("immich"))) values.push(select.value);
    }
    return values;
  }
  function holds(rule) {
    // "uses:immich", "uses:dynaframe", "uses:library" oder "Feld=wert1,wert2", mehrere mit "|"
    return rule.split("|").some((part) => {
      part = part.trim();
      if (part.startsWith("uses:")) {
        const values = sourceValues();
        if (!values.length) return true; // keine Quellen-Auswahl auf der Seite: immer gebraucht
        const what = part.slice(5);
        if (what === "immich") return values.some((v) => v.startsWith("immich"));
        if (what === "dynaframe") return values.some((v) => DF_KINDS.includes(v));
        return values.includes(what);
      }
      const [id, list] = part.split("=");
      const field = document.getElementById(id);
      if (!field) return true;
      const value = field.type === "checkbox" ? String(field.checked) : field.value;
      return (list || "").split(",").map((v) => v.trim()).includes(value);
    });
  }

  // Wie viele Einstellungen in einem Bereich vom Standard abweichen (Felder mit Wert, Häkchen, Auswahl ≠ erste Option)
  function activeCount(nodes) {
    let n = 0;
    for (const node of nodes) {
      for (const field of node.querySelectorAll("input, select, textarea")) {
        if (field.closest(".checks") || field.type === "password" || field.type === "button") continue;
        if (field.type === "checkbox") n += field.checked ? 1 : 0;
        else if (field.tagName === "SELECT") n += field.selectedIndex > 0 ? 1 : 0;
        else n += field.value.trim() && field.value.trim() !== "0" ? 1 : 0;
      }
      for (const list of node.querySelectorAll(".checks")) n += list.querySelector("input:checked") ? 1 : 0;
    }
    return n;
  }

  function badgeFor(fold) {
    if (!fold.needed) return [say(`off:${fold.rule.replace(/^uses:/, "").split("|")[0]}`), "off"];
    const nodes = fold.body();
    switch (fold.badge) {
      case "count": {
        const n = activeCount(nodes);
        return n ? [say("active", n), "on"] : [say("none"), ""];
      }
      case "filled": {
        const filled = nodes.some((node) => [...node.querySelectorAll('input[type="url"], input[type="text"]')].some((f) => f.value.trim()));
        return filled ? [say("set"), "on"] : [say("optional"), ""];
      }
      case "lines": {
        const n = nodes.reduce((sum, node) => sum + [...node.querySelectorAll("textarea")]
          .reduce((s, area) => s + area.value.split("\n").filter((line) => line.trim()).length, 0), 0);
        return n ? [say("lines", n), "on"] : [say("optional"), ""];
      }
      case "services": {
        const bad = nodes.reduce((s, node) => s + node.querySelectorAll(".svc.bad").length, 0);
        const warn = nodes.reduce((s, node) => s + node.querySelectorAll(".svc.warn").length, 0);
        const ok = nodes.reduce((s, node) => s + node.querySelectorAll(".svc.ok").length, 0);
        if (bad) return [say(bad === 1 ? "svcBad" : "svcBads", bad), "bad"];
        if (warn) return [say("svcWarn"), "warn"];
        return ok ? [say("svcOk"), "ok"] : [say("svcWait"), ""];
      }
      default:
        return ["", ""];
    }
  }

  const folds = [];

  function setup(head, id, isCard) {
    const host = isCard ? head : head.parentElement;
    const title = isCard ? (head.querySelector(":scope > .card-head") || head.querySelector(":scope > h2")) : head;
    if (!title) return;
    const bar = document.createElement("div");
    bar.className = "fold-bar" + (isCard ? " fold-bar-card" : " fold-bar-sub");
    bar.setAttribute("role", "button");
    bar.tabIndex = 0;
    title.replaceWith(bar);
    bar.append(title);
    const badge = document.createElement("span");
    badge.className = "fold-badge";
    const chevron = document.createElement("span");
    chevron.className = "fold-chevron";
    chevron.setAttribute("aria-hidden", "true");
    bar.append(badge, chevron);
    let body = null;
    if (!isCard) {
      // Unterabschnitt: alles bis zum nächsten h3.sub / <details> / Kartenende
      body = document.createElement("div");
      body.className = "fold-body";
      let next = bar.nextElementSibling;
      while (next && !(next.matches("h3.sub, .fold-bar, details"))) {
        const after = next.nextElementSibling;
        body.append(next);
        next = after;
      }
      bar.after(body);
    }
    const src = head;
    const fold = {
      id, host, bar, body: () => (isCard ? [...host.children].filter((c) => c !== bar) : [body]),
      rule: src.dataset.foldWhen || "",
      startClosed: src.dataset.foldStart === "closed",
      badge: src.dataset.foldBadge || "", badgeEl: badge,
      needed: true, open: true, isCard, sub: body,
    };
    const toggle = (e) => {
      if (e.type === "click" && e.target.closest("button, a, input, select, textarea, label")) return;
      if (e.type === "keydown" && (e.target !== bar || (e.key !== "Enter" && e.key !== " "))) return;
      if (e.type === "keydown") e.preventDefault();
      show(fold, !fold.open);
      remember(id, { open: fold.open, needed: fold.needed });
    };
    bar.addEventListener("click", toggle);
    bar.addEventListener("keydown", toggle);
    folds.push(fold);
    if (fold.rule) show(fold, false); // erst entscheiden, wenn studio.js den Stand gesetzt hat
    else start(fold);
  }

  function start(fold) {
    const saved = remembered(fold.id);
    fold.needed = fold.rule ? holds(fold.rule) : true;
    fold.wasNeeded = fold.needed;
    fold.started = true;
    show(fold, saved && saved.needed === fold.needed ? saved.open : wanted(fold));
  }

  function wanted(fold) {
    if (!fold.needed) return false;
    if (fold.badge === "services") {
      const [, tone] = badgeFor(fold);
      if (tone === "bad") return true;
    }
    return !fold.startClosed;
  }

  function show(fold, open) {
    fold.open = open;
    fold.host.classList.toggle("fold-closed", fold.isCard && !open);
    if (fold.sub) fold.sub.hidden = !open;
    fold.bar.setAttribute("aria-expanded", String(open));
    fold.bar.title = say(open ? "close" : "open");
  }

  // Bereit, sobald studio.js den ersten Stand gezeigt hat (Version steht da) oder nach 5 s
  const born = Date.now();
  function stateShown() {
    const version = document.getElementById("factVersion");
    return !version || /\d/.test(version.textContent) || Date.now() - born > 5000;
  }

  function refresh() {
    const ready = stateShown();
    for (const fold of folds) {
      if (!fold.started) {
        if (!ready) continue;
        start(fold);
      }
      fold.needed = fold.rule ? holds(fold.rule) : true;
      if (fold.needed !== fold.wasNeeded) {
        // Quelle gewechselt: Karte auf- bzw. zuklappen, eigene Wahl vergessen
        fold.wasNeeded = fold.needed;
        remember(fold.id, null);
        show(fold, wanted(fold));
      }
      fold.host.classList.toggle("fold-unused", fold.isCard && !fold.needed);
      const [text, tone] = badgeFor(fold);
      // Verbindungen: bei einem neuen Problem von selbst aufklappen
      if (fold.badge === "services" && tone === "bad" && fold.lastTone !== "bad") show(fold, true);
      fold.lastTone = tone;
      if (fold.badgeEl.textContent !== text) fold.badgeEl.textContent = text;
      fold.badgeEl.className = "fold-badge" + (tone ? ` ${tone}` : "");
      fold.badgeEl.hidden = !text;
      fold.bar.title = say(fold.open ? "close" : "open");
    }
  }

  function init() {
    for (const card of document.querySelectorAll(".card[data-fold]")) setup(card, card.dataset.fold, true);
    for (const head of document.querySelectorAll("h3.sub[data-fold]")) setup(head, head.dataset.fold, false);
    refresh();
    document.addEventListener("change", refresh);
    document.addEventListener("input", refresh);
    setInterval(refresh, 1000); // studio.js setzt Werte beim Abfragen des Stands
  }

  window.Fold = { refresh, open: (id, value = true) => { const f = folds.find((x) => x.id === id); if (f) show(f, value); } };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
