/* Fahrzeit - ein Zusatzmodul für Dynaframe's Magic Mirror. Zeigt, wie lange
 * die Fahrt mit dem Auto gerade dauert. fetch.py fragt Mapbox oder Google;
 * "Losfahren bis" rechnet tick() hier jede Sekunde nach. */
(function () {
  "use strict";
  const { esc, t, time, icon, nowSec, number } = window.MagicFrame.helpers;
  const TEXT = {
    min: { de: "Min.", en: "min", es: "min" },
    traffic: { de: "+{n} Min. Verkehr", en: "+{n} min traffic", es: "+{n} min de tráfico" },
    free: { de: "frei", en: "clear", es: "fluido" },
    via: { de: "über {via}", en: "via {via}", es: "por {via}" },
    leaveBy: { de: "Losfahren bis {time}", en: "Leave by {time}", es: "Sal antes de las {time}" },
    arrive: { de: "für {time}", en: "for {time}", es: "para las {time}" },
    alt: { de: "oder {via}: {n} Min.", en: "or {via}: {n} min", es: "o {via}: {n} min" },
    stale: { de: "Stand {time}", en: "As of {time}", es: "Datos de las {time}" },
  };

  const HHMM = /^\s*(\d{1,2})[:.](\d{2})\s*$/;

  function target(config) {
    const name = String(config.name || "").trim() || String(config.destination || "").split(",")[0].trim();
    return name.slice(0, 40);
  }

  // Bis wann losfahren, um zur Ankunftszeit da zu sein (heute); null wenn aus oder lange vorbei.
  function leaveBy(config, data) {
    const m = HHMM.exec(config.arriveBy || "");
    if (!m || !data || data.seconds == null) return null;
    const at = new Date();
    at.setHours(+m[1], +m[2], 0, 0);
    const leave = at.getTime() / 1000 - data.seconds;
    return leave - nowSec() > -300 ? { leave, arrive: at.getTime() / 1000 } : null;
  }

  function leaveHtml(config, data) {
    const l = leaveBy(config, data);
    if (!l) return "";
    const soon = l.leave - nowSec() < 600 ? " soon" : "";
    return `${icon("calendar")}<span><b class="tt-when${soon}">${esc(t(TEXT.leaveBy, { time: time(l.leave) }))}</b>
      <span class="dimmed">${esc(t(TEXT.arrive, { time: time(l.arrive) }))}</span></span>`;
  }

  function delayOf(d) {
    return Math.max(0, Math.round((d.seconds - (d.normalSeconds || d.seconds)) / 60));
  }

  const km = (v) => number(v || 0, v >= 100 ? 0 : 1);

  function updateLeave(el, ctx) {
    const box = el.querySelector(".tt-leave");
    if (!box) return;
    const html = leaveHtml(ctx.config, ctx.data);
    if (box.dataset.html !== html) { box.dataset.html = html; box.innerHTML = html; box.hidden = !html; }
  }

  window.MagicFrame.register("traveltime", {
    widget(type, ctx) {
      const d = ctx.data;
      if (!d || d.seconds == null) return null;
      const minutes = Math.round(d.seconds / 60);
      const delay = delayOf(d);
      const extra = delay > 0 ? t(TEXT.traffic, { n: delay }) : t(TEXT.free);
      const name = target(ctx.config);
      if (type === "values") {
        return { items: [{ label: name || t(TEXT.min), value: `${minutes} ${t(TEXT.min)}`, icon: "car" },
          { label: "", value: extra, icon: delay >= 3 ? "warn" : "car" }].slice(0, delay > 0 ? 2 : 1) };
      }
      return { text: `${name ? `${name}: ` : ""}${minutes} ${t(TEXT.min)} · ${extra}`, icon: "car" };
    },
    render(el, ctx) {
      const c = ctx.config;
      const d = ctx.data;
      if (!d || d.seconds == null) { el.innerHTML = '<div class="xsmall dimmed">…</div>'; return true; }
      const minutes = Math.round(d.seconds / 60);
      const delay = delayOf(d);
      const tone = delay >= 10 ? "bad" : delay >= 3 ? "warn" : "ok";
      const chip = `<span class="tt-chip ${tone}">${esc(delay > 0 ? t(TEXT.traffic, { n: delay }) : t(TEXT.free))}</span>`;
      const name = target(c);
      const route = c.showRoute !== false
        ? `<div class="small dimmed tt-sub">${km(d.km)} km${d.via ? ` · ${esc(t(TEXT.via, { via: d.via }))}` : ""}</div>` : "";
      const alt = c.showAlt !== false ? (d.alternatives || []).filter((a) => a.via).slice(0, 1)
        .map((a) => `<div class="xsmall dimmed tt-alt">${esc(t(TEXT.alt, { via: a.via, n: Math.round(a.seconds / 60) }))}</div>`).join("") : "";
      const events = (d.events || []).map((e) => `<li class="${e.kind === "closure" ? "closure" : ""}">${icon("warn")}
        <span><b>${esc(e.title)}</b> ${esc(e.text)}</span></li>`).join("");
      const old = d.at && nowSec() - d.at > 20 * 60 ? `<div class="xsmall dimmed">${esc(t(TEXT.stale, { time: time(d.at) }))}</div>` : "";
      const credit = `<div class="tt-credit">${d.provider === "google" ? "Google Maps" : "© Mapbox"}</div>`;
      const head = name ? `<div class="small normal tt-to">${icon("car")}<span>${esc(name)}</span></div>` : "";
      const main = c.layout === "line"
        ? `<div class="medium tt-line">${name ? "" : icon("car")}<b class="bright">${minutes} ${esc(t(TEXT.min))}</b>${chip}</div>`
        : `<div class="tt-big"><b class="bright">${minutes}</b><span class="dimmed">${esc(t(TEXT.min))}</span>${chip}</div>`;
      el.innerHTML = `<div class="tt-box tt-${c.layout === "line" ? "line-layout" : "big-layout"}">
          ${head}${main}${route}
          <div class="small tt-leave"></div>
          ${alt}${events ? `<ul class="tt-events xsmall">${events}</ul>` : ""}${old}${credit}
        </div>`;
      updateLeave(el, ctx);
    },
    tick: updateLeave,
  });
})();
