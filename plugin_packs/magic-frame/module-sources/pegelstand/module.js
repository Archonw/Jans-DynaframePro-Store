/* Pegelstand - ein Zusatzmodul für Dynaframe's Magic Mirror.
 * Meldet sich wie jedes Modul mit MagicFrame.register an. ctx.data ist,
 * was fetch.py zurückgibt; ctx.h sind die Helfer der Szene. */
(function () {
  "use strict";
  const { esc, t } = window.MagicFrame.helpers;
  const STATE = {
    low: { de: "niedrig", en: "low", es: "bajo" },
    normal: { de: "normal", en: "normal", es: "normal" },
    high: { de: "hoch", en: "high", es: "alto" },
  };
  window.MagicFrame.register("pegelstand", {
    render(el, ctx) {
      const d = ctx.data;
      if (!d) { el.innerHTML = '<div class="xsmall dimmed">…</div>'; return true; }
      const arrow = d.trend > 0 ? "↗" : d.trend < 0 ? "↘" : "→";
      const state = STATE[d.state] ? t(STATE[d.state]) : "";
      el.innerHTML = `<div class="${esc(ctx.config.size || "medium")} bright light">${ctx.h.number(d.cm)} cm
          <span class="dimmed">${arrow}</span></div>
        <div class="small normal">${esc(d.station)}${d.water ? ` · ${esc(d.water)}` : ""}</div>
        ${state ? `<div class="xsmall dimmed">${esc(state)}</div>` : ""}`;
    },
  });
})();
