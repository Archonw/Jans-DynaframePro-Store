/* Spritpreise - ein Zusatzmodul für Dynaframe's Magic Mirror. Zeigt die
 * günstigsten Tankstellen in der Nähe (Tankerkönig) und ob es gerade günstig ist:
 * Vergleich mit dem Durchschnitt, Verlauf der letzten 24 Stunden und die
 * Uhrzeit, zu der es meist am billigsten ist. fetch.py holt und rechnet. */
(function () {
  "use strict";
  const { esc, t, time, number, nowSec } = window.MagicFrame.helpers;
  const NAMES = { e5: "Super E5", e10: "Super E10", diesel: { de: "Diesel", en: "Diesel", es: "Diésel" } };
  const SHORT = { e5: "E5", e10: "E10", diesel: { de: "Diesel", en: "Diesel", es: "Diésel" } };
  const TEXT = {
    title: { de: "Spritpreise", en: "Fuel prices", es: "Precios del combustible" },
    below: { de: "{n} ct unter Ø", en: "{n} ct below avg.", es: "{n} cts bajo la media" },
    above: { de: "{n} ct über Ø", en: "{n} ct above avg.", es: "{n} cts sobre la media" },
    same: { de: "wie Ø", en: "at average", es: "en la media" },
    learning: { de: "Ø ab dem 3. Tag", en: "avg. from day 3", es: "media desde el día 3" },
    cheap: { de: "Jetzt tanken", en: "Fill up now", es: "Reposta ahora" },
    avg: { de: "Ø {d} Tage {p} · {lo}–{hi}", en: "{d}-day avg. {p} · {lo}–{hi}", es: "media {d} días {p} · {lo}–{hi}" },
    tip: { de: "Meist am günstigsten um {h} (−{n} ct)", en: "Usually cheapest at {h} (−{n} ct)",
      es: "Suele ser más barato a las {h} (−{n} cts)" },
    more: { de: "+{n} gleich günstig", en: "+{n} same price", es: "+{n} al mismo precio" },
    none: { de: "Gerade keine offene Tankstelle mit dieser Sorte.", en: "No open station with this fuel right now.",
      es: "Ahora no hay ninguna gasolinera abierta con este combustible." },
    noStations: { de: "Keine Tankstelle gefunden. Vergrößere den Umkreis oder prüfe die Auswahl.",
      en: "No station found. Increase the radius or check the selection.",
      es: "No se encontró ninguna gasolinera. Amplía el radio o revisa la selección." },
    closed: { de: "zu", en: "closed", es: "cerrada" },
    stale: { de: "Stand {time}", en: "As of {time}", es: "Datos de las {time}" },
    h24: { de: "24 Std.", en: "24 h", es: "24 h" },
  };
  const FUEL_ICON = `<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"
    stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 20V5a1 1 0 0 1 1-1h7a1 1 0 0 1 1 1v15M4 20h11M5 10h9M14 8l3 2v7a1.5 1.5 0 0 0 3 0V9l-3-3"/></svg>`;
  const CLOCK_ICON = `<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"
    stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/></svg>`;

  const name = (fuel) => t(NAMES[fuel] || fuel);
  const short = (fuel) => t(SHORT[fuel] || fuel);

  // 1,669 -> "1,66" und die kleine 9 wie an der Preistafel
  function priceParts(p) {
    const tenth = Math.round(p * 1000);
    return { main: number(Math.floor(tenth / 10) / 100, 2), last: String(tenth % 10) };
  }
  const priceHtml = (p) => { const x = priceParts(p); return `${esc(x.main)}<sup>${x.last}</sup>`; };
  const priceText = (p) => number(p, 3);
  const cents = (a, b) => Math.round((a - b) * 100);
  const hour = (h) => { const d = new Date(); d.setHours(h, 0, 0, 0); return time(d.getTime() / 1000); };
  const km = (v) => `${number(v || 0, 1)} km`;
  const fuelsWithPrice = (d) => (d && d.fuels ? d.fuels.filter((f) => f.price != null) : []);

  function chip(f) {
    if (f.cheap) return `<span class="fp-chip hot">${esc(t(TEXT.cheap))}</span>`;
    if (f.avg == null) return `<span class="fp-chip dim">${esc(t(TEXT.learning))}</span>`;
    const diff = cents(f.price, f.avg);
    if (diff <= -1) return `<span class="fp-chip ok">${esc(t(TEXT.below, { n: -diff }))}</span>`;
    if (diff >= 1) return `<span class="fp-chip warn">${esc(t(TEXT.above, { n: diff }))}</span>`;
    return `<span class="fp-chip dim">${esc(t(TEXT.same))}</span>`;
  }

  // Kleine Kurve: billigster Preis jeder Stunde der letzten 24 Stunden, gestrichelt der Durchschnitt
  function chart(f) {
    const pts = f.curve || [];
    if (pts.length < 3) return "";
    const W = 240, H = 44, now = nowSec(), from = pts[pts.length - 1][0] - 23 * 3600;
    const values = pts.map((p) => p[1]).concat(f.avg != null ? [f.avg] : []);
    let lo = Math.min(...values), hi = Math.max(...values);
    if (hi - lo < 0.02) { const mid = (hi + lo) / 2; lo = mid - 0.01; hi = mid + 0.01; }
    const x = (at) => Math.max(0, Math.min(W - 5, ((at - from) / (23 * 3600)) * (W - 5)));
    const y = (p) => 4 + (1 - (p - lo) / (hi - lo)) * (H - 8);
    const line = pts.map((p, i) => `${i ? "L" : "M"}${x(p[0]).toFixed(1)} ${y(p[1]).toFixed(1)}`).join(" ");
    const last = pts[pts.length - 1];
    const avg = f.avg != null ? `<path class="fp-avg" d="M0 ${y(f.avg).toFixed(1)}H${W}"/>` : "";
    return `<div class="fp-chart"><div class="fp-plot"><svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">${avg}
      <path class="fp-line" d="${line}"/></svg>
      <i class="fp-dot" style="left:${(x(last[0]) / W * 100).toFixed(1)}%;top:${(y(last[1]) / H * 100).toFixed(1)}%"></i></div>
      <span class="fp-axis xsmall dimmed"><span>${esc(t(TEXT.h24))}</span><span>${esc(time(now))}</span></span></div>`;
  }

  function fuelBlock(f, c, single) {
    const head = `<div class="fp-head small">${FUEL_ICON}<span class="normal">${esc(name(f.fuel))}</span>${f.price != null ? chip(f) : ""}</div>`;
    if (f.price == null) return `<div class="fp-fuel">${head}<div class="xsmall dimmed">${esc(t(TEXT.none))}</div></div>`;
    const s = f.station || {};
    const where = [s.brand, s.street || s.place, s.km != null ? km(s.km) : ""].filter(Boolean).map(esc).join(" · ");
    const more = f.same > 0 ? ` <span class="dimmed">(${esc(t(TEXT.more, { n: f.same }))})</span>` : "";
    let tip = "";
    if (c.showTip !== false) {
      if (f.avg != null) tip += `<div class="xsmall dimmed">${esc(t(TEXT.avg, { d: f.avgDays, p: priceText(f.avg), lo: priceText(f.low), hi: priceText(f.high) }))}</div>`;
      if (f.cheapHour) tip += `<div class="xsmall fp-tip">${CLOCK_ICON}<span>${esc(t(TEXT.tip,
        { h: hour(f.cheapHour.hour), n: f.cheapHour.cents, x: hour(f.cheapHour.dearHour) }))}</span></div>`;
    }
    return `<div class="fp-fuel${f.cheap ? " cheap" : ""}">${head}
      <div class="fp-price ${single ? "one" : ""}"><b class="bright">${priceHtml(f.price)}</b><span class="dimmed">€</span></div>
      <div class="xsmall normal fp-where">${where}${more}</div>${tip}${c.showChart !== false ? chart(f) : ""}</div>`;
  }

  function listHtml(d) {
    const fuels = d.fuels.map((f) => f.fuel);
    const best = {};
    d.fuels.forEach((f) => { best[f.fuel] = f.price; });
    const rows = (d.stations || []).map((s) => {
      const cells = fuels.map((fuel) => {
        const p = s.prices[fuel];
        if (p == null) return '<td class="dimmed">–</td>';
        return `<td class="${s.open && p === best[fuel] ? "fp-best" : ""}">${priceHtml(p)}</td>`;
      }).join("");
      const where = esc(s.street || s.place || "");
      return `<tr class="${s.open ? "" : "fp-closed"}"><th><span class="normal">${esc(s.brand)}</span>
        <span class="xsmall dimmed">${where}${where ? " · " : ""}${esc(s.open ? km(s.km) : t(TEXT.closed))}</span></th>${cells}</tr>`;
    }).join("");
    if (!rows) return `<div class="xsmall dimmed">${esc(t(TEXT.noStations))}</div>`;
    return `<table class="fp-table small"><thead><tr><th></th>${fuels.map((f) => `<th class="xsmall dimmed">${esc(short(f))}</th>`).join("")}</tr></thead>
      <tbody>${rows}</tbody></table>`;
  }

  window.MagicFrame.register("fuelprices", {
    widget(type, ctx) {
      const d = ctx.data;
      const fuels = fuelsWithPrice(d);
      if (!fuels.length) return null;
      if (type === "list") {
        const first = d.fuels[0].fuel;
        return { title: t(TEXT.title), items: (d.stations || []).filter((s) => s.open).map((s) => ({
          title: s.brand, info: [s.street || s.place, km(s.km)].filter(Boolean).join(" · "),
          badge: s.prices[first] != null ? `${short(first)} ${priceText(s.prices[first])}` : "", icon: "car" })) };
      }
      if (type === "values") {
        return { items: fuels.map((f) => ({ label: name(f.fuel), value: `${priceText(f.price)} €`, icon: f.cheap ? "warn" : "car" })) };
      }
      return { text: fuels.map((f) => `${short(f.fuel)} ${priceText(f.price)} €`).join(" · "), icon: "car" };
    },
    render(el, ctx) {
      const c = ctx.config;
      const d = ctx.data;
      if (!d || !d.fuels) { el.innerHTML = '<div class="xsmall dimmed">…</div>'; return true; }
      const body = c.layout === "list" ? listHtml(d)
        : (d.stations || []).length || fuelsWithPrice(d).length
          ? `<div class="fp-fuels${d.fuels.length > 1 ? " many" : ""}">${d.fuels.map((f) => fuelBlock(f, c, d.fuels.length === 1)).join("")}</div>`
          : `<div class="xsmall dimmed">${esc(t(TEXT.noStations))}</div>`;
      const old = d.at && nowSec() - d.at > 30 * 60 ? `<div class="xsmall dimmed">${esc(t(TEXT.stale, { time: time(d.at) }))}</div>` : "";
      el.innerHTML = `<div class="fp-box fp-${c.layout === "list" ? "list" : "best"}">${body}${old}
        <div class="fp-credit">tankerkoenig.de · MTS-K · CC BY 4.0</div></div>`;
    },
  });
})();
