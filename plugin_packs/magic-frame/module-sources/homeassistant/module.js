/* Home Assistant - ein Zusatzmodul für Dynaframe's Magic Mirror.
 * Je nach Ansicht (config.view): Werte, Haus-Status, Raumklima, Anwesenheit
 * oder Müllabfuhr. Die Daten holt fetch.py. */
(function () {
  "use strict";
  const MF = window.MagicFrame;
  const h = MF.helpers;
  const { esc, t } = h;

  const TEXT = {
    ok: { de: "Alles in Ordnung", en: "All good", es: "Todo en orden" },
    since: { de: "seit {time}", en: "since {time}", es: "desde {time}" },
    today: { de: "Heute", en: "Today", es: "Hoy" },
    tomorrow: { de: "Morgen", en: "Tomorrow", es: "Mañana" },
    inDays: { de: "in {n} Tagen", en: "in {n} days", es: "en {n} días" },
    noWaste: { de: "Keine Abholung in Sicht.", en: "No collection coming up.", es: "No hay recogidas próximas." },
    nobody: { de: "Niemand zu Hause", en: "Nobody home", es: "Nadie en casa" },
    low: { de: "Akku {value}", en: "battery {value}", es: "batería {value}" },
  };

  // ------------------------------------------------------------ Zustände und Symbole

  const STATES = {
    on: { de: "an", en: "on", es: "encendido" }, off: { de: "aus", en: "off", es: "apagado" },
    unavailable: { de: "nicht erreichbar", en: "unavailable", es: "no disponible" },
    unknown: { de: "unbekannt", en: "unknown", es: "desconocido" },
    home: { de: "zu Hause", en: "home", es: "en casa" }, not_home: { de: "unterwegs", en: "away", es: "fuera" },
    open: { de: "offen", en: "open", es: "abierto" }, closed: { de: "zu", en: "closed", es: "cerrado" },
    opening: { de: "öffnet", en: "opening", es: "abriendo" }, closing: { de: "schließt", en: "closing", es: "cerrando" },
    locked: { de: "abgeschlossen", en: "locked", es: "cerrado con llave" }, unlocked: { de: "nicht abgeschlossen", en: "unlocked", es: "sin llave" },
    jammed: { de: "klemmt", en: "jammed", es: "atascada" },
    heat: { de: "heizt", en: "heating", es: "calentando" }, cool: { de: "kühlt", en: "cooling", es: "enfriando" },
    detected: { de: "ausgelöst", en: "triggered", es: "activado" },
  };
  const OPENING = ["window", "door", "garage_door", "opening"];
  const ALARM = ["smoke", "gas", "moisture", "carbon_monoxide", "problem", "safety", "tamper", "heat", "cold"];

  function haState(e) {
    let state = e.state;
    if (OPENING.includes(e.deviceClass) && (state === "on" || state === "off")) state = state === "on" ? "open" : "closed";
    if (ALARM.includes(e.deviceClass) && state === "on") state = "detected";
    if (e.deviceClass === "battery" && e.domain === "binary_sensor") state = state === "on" ? "low" : "ok";
    if (state === "low") return t({ de: "Akku schwach", en: "battery low", es: "batería baja" });
    if (STATES[state]) return t(STATES[state]);
    const n = Number(state);
    if (state !== "" && Number.isFinite(n)) return `${h.number(n, Math.abs(n) < 10 && !Number.isInteger(n) ? 1 : 0)}${e.unit ? ` ${e.unit}` : ""}`;
    return `${state}${e.unit ? ` ${e.unit}` : ""}`;
  }

  // Symbol je Gerät: eigenes mdi-Symbol, dann Geräteklasse, dann Domäne
  const HA_MDI = [[/washing|dishwasher|tumble/, "washer"], [/^car(-|$)|garage/, "car"], [/trash|delete/, "trash"],
    [/thermometer|thermostat|radiator/, "thermo"], [/water|humidity/, "droplet"], [/flash|lightning|meter-electric/, "bolt"],
    [/lightbulb|lamp|ceiling-light/, "bulb"], [/window/, "window"], [/door/, "door"], [/(^|-)lock/, "lock"], [/battery/, "battery"]];
  const HA_CLASS = { temperature: "thermo", humidity: "droplet", moisture: "droplet", power: "bolt", energy: "bolt",
    current: "bolt", voltage: "bolt", battery: "battery", window: "window", opening: "window", garage_door: "window",
    door: "door", motion: "walk", occupancy: "walk", presence: "walk", lock: "lock", illuminance: "sun",
    carbon_dioxide: "wind", co2: "wind", pm25: "wind", pm10: "wind", aqi: "wind", volatile_organic_compounds: "wind",
    smoke: "warn", gas: "warn", carbon_monoxide: "warn", safety: "warn", problem: "warn", tamper: "warn", pressure: "gauge",
    atmospheric_pressure: "gauge", plug: "plug", outlet: "plug", power_factor: "bolt", garage: "car", gate: "door" };
  const HA_DOMAIN = { light: "bulb", switch: "toggle", input_boolean: "toggle", lock: "lock", person: "person",
    device_tracker: "person", climate: "thermo", cover: "window", media_player: "music", sun: "sun", weather: "sun",
    vacuum: "home", fan: "wind" };

  function haIcon(e) {
    const mdi = String(e.icon || "").replace(/^mdi:/, "");
    const hit = mdi && HA_MDI.find(([re]) => re.test(mdi));
    if (hit) return hit[1];
    if (HA_CLASS[e.deviceClass]) return HA_CLASS[e.deviceClass];
    if (HA_DOMAIN[e.domain]) return HA_DOMAIN[e.domain];
    if (e.unit === "°C" || e.unit === "°F") return "thermo";
    if (/^k?W(h)?$/.test(e.unit || "")) return "bolt";
    return e.domain === "sensor" || e.unit ? "gauge" : "toggle";
  }

  const CHECK = `<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"
    stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.7 2.7L16 9.8"/></svg>`;

  function since(epoch) {
    if (!epoch) return "";
    const today = h.dayStart(h.nowSec());
    const time = h.dayStart(epoch) === today ? h.time(epoch) : `${h.dayName(epoch)} ${h.time(epoch)}`;
    return t(TEXT.since, { time });
  }

  // ------------------------------------------------------------ Werte

  function valuesHtml(d, c) {
    const icons = c.icons !== false;
    const sym = (e) => (icons ? `<td class="sym">${e ? h.icon(haIcon(e)) : ""}</td>` : "");
    return `<table class="small ha">${(d.entities || []).map((e) => e.missing
      ? `<tr>${sym(null)}<td class="dimmed">${esc(e.id)}</td><td class="dimmed">?</td></tr>`
      : `<tr class="${e.state === "on" && OPENING.includes(e.deviceClass) ? "alert" : ""}">${sym(e)}<td class="name">${esc(e.name)}</td><td class="state bright">${esc(haState(e))}</td></tr>`).join("")}</table>`;
  }

  // ------------------------------------------------------------ Haus-Status

  function alertIcon(a) {
    return a.kind === "safety" ? "warn" : a.kind === "battery" ? "battery" : haIcon(a);
  }

  function alertText(a) {
    return a.kind === "battery" && a.domain === "sensor" ? t(TEXT.low, { value: haState(a) }) : haState(a);
  }

  function statusHtml(d, c) {
    const alerts = d.alerts || [];
    if (!alerts.length) {
      return `<div class="ha-ok normal">${CHECK}<span>${esc(c.okText || t(TEXT.ok))}</span></div>`;
    }
    return `<table class="small ha ha-alerts">${alerts.map((a) => `<tr class="k-${esc(a.kind)}">
      <td class="sym">${h.icon(alertIcon(a))}</td>
      <td class="name bright">${esc(a.name)}</td>
      <td class="state">${esc(alertText(a))}${c.since !== false && a.changed ? `<div class="xsmall dimmed">${esc(since(a.changed))}</div>` : ""}</td>
    </tr>`).join("")}</table>`;
  }

  // ------------------------------------------------------------ Raumklima

  function deg(value) {
    return value == null ? "–" : `${h.number(value, 1)}°`;
  }

  function co2Class(v) {
    return v >= 1400 ? "bad" : v >= 1000 ? "warn" : "";
  }

  function climateHtml(d, c) {
    const rooms = d.rooms || [];
    const hum = (r) => (c.humidity !== false && r.humidity != null
      ? `<span class="${r.humidity >= 65 || r.humidity < 35 ? "warn" : ""}">${h.icon("droplet")} ${h.number(r.humidity)} %</span>` : "");
    const co2 = (r) => (c.co2 !== false && r.co2 != null
      ? `<span class="${co2Class(r.co2)}">CO₂ ${h.number(r.co2)}</span>` : "");
    if (c.layout === "list") {
      return `<table class="small ha ha-climate-list">${rooms.map((r) => `<tr><td class="name">${esc(r.name)}</td>
        <td class="state bright">${deg(r.temp)}</td><td class="extra dimmed">${hum(r)} ${co2(r)}</td></tr>`).join("")}</table>`;
    }
    return `<div class="ha-tiles">${rooms.map((r) => `<div class="ha-tile">
      <div class="xsmall dimmed ha-room">${esc(r.name)}${r.hvac === "heat" ? ` ${h.icon("sun", "heat")}` : ""}</div>
      <div class="large bright light ha-temp">${deg(r.temp)}</div>
      <div class="xsmall normal ha-extra">${hum(r)}${co2(r)}</div></div>`).join("")}</div>`;
  }

  // ------------------------------------------------------------ Anwesenheit

  // "iPhone von Sophie", "Handy-Christin", "Sophies iPhone" -> "Sophie", "Christin"
  const DEVICE = "i?phone|handy|smartphone|mobil(e|telefon)?|pixel|galaxy|samsung|xiaomi|redmi|oneplus|huawei|ipad|tablet";
  function personName(p) {
    let name = String(p.name || "");
    if (p.device) {
      const short = name.replace(new RegExp(`^(${DEVICE})(\\s*[a-z]?\\d+\\w*)?(\\s*(von|de|of|di|du)\\s*|[_-]+)`, "i"), "")
        .replace(new RegExp(`(['’]?s)?[\\s_-]*(${DEVICE})(\\s*[a-z]?\\d+\\w*)?$`, "i"), "").trim();
      // nur übernehmen, wenn ein Name übrig bleibt (kein "Pro", keine Modellnummer)
      if (short && short !== name && !/\\d|^(pro|max|plus|ultra|mini|lite)$/i.test(short)) name = short;
    }
    return name;
  }

  function initials(name) {
    return String(name || "?").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("")
      .replace(/[^\p{L}\p{N}]/gu, "") || "?";
  }

  function where(p) {
    const state = p.state === "unavailable" ? "unknown" : p.state;   // kurz halten, passt unter das Bild
    return STATES[state] ? t(STATES[state]) : state;
  }

  function presenceHtml(d, c) {
    let people = d.people || [];
    people = people.map((p) => ({ ...p, name: personName(p) }));
    if (c.onlyHome) people = people.filter((p) => p.state === "home");
    if (!people.length) return `<div class="small dimmed">${esc(t(TEXT.nobody))}</div>`;
    const face = (p) => `<span class="ha-face">${c.pictures !== false && p.picture
      ? `<img src="${esc(p.picture)}" alt="" referrerpolicy="no-referrer" onerror="this.replaceWith(document.createTextNode('${esc(initials(p.name))}'))">`
      : esc(initials(p.name))}</span>`;
    if (c.people === "list") {
      return `<table class="small ha ha-people-list">${people.map((p) => `<tr class="${p.state === "home" ? "home" : "away"}">
        <td class="sym">${face(p)}</td><td class="name">${esc(p.name)}</td><td class="state">${esc(where(p))}</td></tr>`).join("")}</table>`;
    }
    return `<div class="ha-people">${people.map((p) => `<div class="ha-person ${p.state === "home" ? "home" : "away"}">
      ${face(p)}<div class="xsmall normal ha-pname">${esc(p.name.split(/\s+/)[0])}</div>
      ${p.state === "home" ? "" : `<div class="xsmall dimmed">${esc(where(p))}</div>`}</div>`).join("")}</div>`;
  }

  // ------------------------------------------------------------ Müllabfuhr

  const BINS = [[/sonder|schadstoff|hazard|problem/i, "#e05a47"], [/sperr|bulky/i, "#9b6bd3"],
    [/bio|braun|organic|kompost|garden|grünschnitt|grunschnitt/i, "#a0703c"],
    [/gelb|plastik|verpackung|wertstoff|lvp|recycl|packaging|yellow/i, "#f2c94c"],
    [/papier|blau|pappe|paper|cardboard|blue/i, "#4a90e2"], [/glas|glass/i, "#5cb85c"],
    [/rest|haus|schwarz|grau|residual|general|black|grey|gray/i, "#9aa0a6"]];

  function binColor(title) {
    const hit = BINS.find(([re]) => re.test(title));
    return hit ? hit[1] : "currentColor";
  }

  function daysFrom(date) {
    const [y, m, d] = String(date).split("-").map(Number);
    const at = new Date(y, m - 1, d).getTime() / 1000;
    return { at, days: Math.round((at - h.dayStart(h.nowSec())) / 86400) };
  }

  function when(date) {
    const { at, days } = daysFrom(date);
    if (days === 0) return t(TEXT.today);
    if (days === 1) return t(TEXT.tomorrow);
    return new Date(at * 1000).toLocaleDateString(h.locale(), { weekday: "short", day: "numeric", month: "numeric" });
  }

  function wasteRows(d) {
    return (d.days || []).filter((r) => daysFrom(r.date).days >= 0);
  }

  function wasteHtml(d) {
    const rows = wasteRows(d);
    const texts = d.texts || [];
    if (!rows.length && !texts.length) return `<div class="small dimmed">${esc(t(TEXT.noWaste))}</div>`;
    return `<table class="small ha ha-waste">${rows.map((r) => {
      const soon = daysFrom(r.date).days <= 1;
      return `<tr class="${soon ? "soon" : ""}"><td class="when ${soon ? "bright" : "normal"}">${esc(when(r.date))}</td>
        <td class="bins">${r.types.map((type) => `<span class="ha-bin"><span style="color:${binColor(type)}">${h.icon("trash")}</span>${esc(type)}</span>`).join("")}</td></tr>`;
    }).join("")}${texts.map((x) => `<tr><td class="when normal">${esc(x.name)}</td><td class="bins">${esc(x.state)}</td></tr>`).join("")}</table>`;
  }

  // ------------------------------------------------------------ Anmeldung

  const VIEWS = { values: valuesHtml, status: statusHtml, climate: climateHtml, presence: presenceHtml, waste: wasteHtml };

  MF.register("homeassistant", {
    widget(type, ctx) {
      const d = ctx.data;
      if (!d) return null;
      const view = ctx.config.view || "values";
      if (view === "status") {
        const alerts = d.alerts || [];
        if (type === "text") return { text: alerts.length ? alerts.map((a) => `${a.name}: ${alertText(a)}`).join(" · ") : (ctx.config.okText || t(TEXT.ok)),
          icon: alerts.length ? "warn" : "home" };
        return { empty: ctx.config.okText || t(TEXT.ok), items: alerts.map((a) => ({ title: a.name, info: alertText(a), icon: alertIcon(a) })) };
      }
      if (view === "waste") {
        const rows = wasteRows(d);
        if (type === "text") return { text: rows.length ? `${when(rows[0].date)}: ${rows[0].types.join(", ")}` : t(TEXT.noWaste), icon: "trash" };
        return { empty: t(TEXT.noWaste), items: rows.map((r) => ({ title: r.types.join(", "), info: when(r.date), icon: "trash" })) };
      }
      if (view === "climate") {
        return { items: (d.rooms || []).map((r) => ({ label: r.name, value: deg(r.temp) + (r.humidity != null ? ` · ${h.number(r.humidity)} %` : ""), icon: "thermo" })) };
      }
      if (view === "presence") {
        return { items: (d.people || []).map((p) => ({ label: personName(p), value: where(p), icon: "person" })) };
      }
      return { items: (d.entities || []).filter((e) => !e.missing)
        .map((e) => ({ label: e.name, value: haState(e), icon: ctx.config.icons !== false ? haIcon(e) : "" })) };
    },
    render(el, ctx) {
      const d = ctx.data;
      const c = ctx.config;
      if (!d) { el.innerHTML = `<div class="xsmall dimmed">…</div>`; return true; }
      const view = c.view || "values";
      if (view === "status" && !(d.alerts || []).length && c.whenOk === "hide") return false;
      if (view === "waste" && c.onlySoon && !wasteRows(d).some((r) => daysFrom(r.date).days <= 1)) return false;
      el.innerHTML = (VIEWS[view] || valuesHtml)(d, c);
      return true;
    },
  });
})();
