/* Jellyfin - ein Zusatzmodul für Dynaframe's Magic Mirror. Zeigt, was gerade
 * auf dem Jellyfin-Server läuft. fetch.py fragt den Server alle 10 Sekunden;
 * dazwischen läuft der Fortschrittsbalken hier von selbst. */
(function () {
  "use strict";
  const { esc, t } = window.MagicFrame.helpers;
  const TEXT = {
    next: { de: "Als Nächstes", en: "Up next", es: "A continuación" },
    idle: { de: "Gerade läuft nichts.", en: "Nothing is playing.", es: "No se reproduce nada." },
    paused: { de: "Pause", en: "Paused", es: "En pausa" },
    live: { de: "Live-TV", en: "Live TV", es: "TV en directo" },
  };

  const mmss = (s) => {
    s = Math.max(0, Math.floor(s));
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = String(s % 60).padStart(2, "0");
    return h ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${m}:${sec}`;
  };

  function position(d) {
    let at = Number(d.elapsed) || 0;
    if (d.state === "playing") at += Date.now() / 1000 - (Number(d.elapsedAt) || Date.now() / 1000);
    return d.duration ? Math.min(at, d.duration) : at;
  }

  function progress(el, d) {
    const bar = el.querySelector(".jf-fill");
    if (!bar) return;
    const at = position(d);
    bar.style.width = d.duration ? `${(100 * at / d.duration).toFixed(2)}%` : "0%";
    el.querySelector(".jf-elapsed").textContent = mmss(at);
    el.querySelector(".jf-remaining").textContent = d.duration ? `-${mmss(d.duration - at)}` : "";
  }

  window.MagicFrame.register("jellyfin", {
    render(el, ctx) {
      const c = ctx.config;
      const d = ctx.data;
      if (!d) { el.innerHTML = '<div class="xsmall dimmed">…</div>'; return true; }
      if (d.state === "idle") {
        if (c.hideIdle) return false;
        el.innerHTML = `<div class="xsmall dimmed">${esc(t(TEXT.idle))}</div>`;
        return true;
      }
      const layout = ["beside", "background", "text"].includes(c.layout) ? c.layout : "beside";
      const shape = ["square", "poster", "wide"].includes(d.shape) ? d.shape : "square";
      const cover = d.image && layout !== "text" ? `<img class="jf-cover" src="${esc(d.image)}" alt="" onerror="this.remove()">` : "";
      const line2 = [d.line2, c.showDetails !== false && d.line3 ? d.line3 : ""].filter(Boolean);
      const status = [c.showDevice ? [d.device, d.user].filter(Boolean).join(" · ") : "",
        d.state === "paused" ? t(TEXT.paused) : "", d.kind === "tv" ? t(TEXT.live) : ""].filter(Boolean);
      const bar = c.showProgress !== false && d.duration ? `<div class="jf-progress">
          <div class="jf-track"><div class="jf-fill"></div></div>
          <div class="jf-times xsmall dimmed"><span class="jf-elapsed"></span><span class="jf-remaining"></span></div></div>` : "";
      const next = c.showNext !== false && d.next && d.next.title ? `<div class="jf-next xsmall">
          <span class="dimmed">${esc(t(TEXT.next))}:</span> ${esc(d.next.title)}${d.next.artist ? ` <span class="dimmed">· ${esc(d.next.artist)}</span>` : ""}</div>` : "";
      el.innerHTML = `<div class="jf-box jf-${layout} jf-shape-${shape} jf-cover-${esc(c.cover || "medium")} ${d.state === "paused" ? "jf-paused" : ""}">
          ${layout === "background" && d.image ? `<div class="jf-bg" style="background-image:url('${esc(d.image).replace(/'/g, "%27")}')"></div>` : ""}
          ${cover}
          <div class="jf-info">
            ${status.length ? `<div class="xsmall dimmed jf-status">${esc(status.join(" · "))}</div>` : ""}
            <div class="medium bright jf-title">${esc(d.title || "–")}</div>
            ${line2.length ? `<div class="small normal jf-artist">${esc(line2.join(" · "))}</div>` : ""}
            ${bar}${next}
          </div>
        </div>`;
      progress(el, d);
    },
    tick(el, ctx) {
      if (ctx.data && ctx.data.state !== "idle") progress(el, ctx.data);
    },
  });
})();
