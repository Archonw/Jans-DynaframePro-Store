/* Music Assistant - ein Zusatzmodul für Dynaframe's Magic Mirror.
 * Nachbau von MMM-MusicAssistant (egeekial, MIT). fetch.py fragt den Server
 * alle 10 Sekunden; dazwischen läuft der Fortschrittsbalken hier von selbst. */
(function () {
  "use strict";
  const { esc, t } = window.MagicFrame.helpers;
  const TEXT = {
    next: { de: "Als Nächstes", en: "Up next", es: "A continuación" },
    idle: { de: "Gerade läuft nichts.", en: "Nothing is playing.", es: "No suena nada." },
    paused: { de: "Pause", en: "Paused", es: "En pausa" },
    radio: { de: "Radio", en: "Radio", es: "Radio" },
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
    const bar = el.querySelector(".ma-fill");
    if (!bar) return;
    const at = position(d);
    bar.style.width = d.duration ? `${(100 * at / d.duration).toFixed(2)}%` : "0%";
    el.querySelector(".ma-elapsed").textContent = mmss(at);
    el.querySelector(".ma-remaining").textContent = d.duration ? `-${mmss(d.duration - at)}` : "";
  }

  window.MagicFrame.register("musicassistant", {
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
      const cover = d.image && layout !== "text" ? `<img class="ma-cover" src="${esc(d.image)}" alt="" onerror="this.remove()">` : "";
      const line2 = [d.artist, c.showAlbum && d.album ? d.album : ""].filter(Boolean);
      const status = [c.showPlayer && d.player ? d.player : "", d.state === "paused" ? t(TEXT.paused) : "",
        d.radio ? t(TEXT.radio) : ""].filter(Boolean);
      const bar = c.showProgress && d.duration ? `<div class="ma-progress">
          <div class="ma-track"><div class="ma-fill"></div></div>
          <div class="ma-times xsmall dimmed"><span class="ma-elapsed"></span><span class="ma-remaining"></span></div></div>` : "";
      const next = c.showNext && d.next && d.next.title ? `<div class="ma-next xsmall">
          <span class="dimmed">${esc(t(TEXT.next))}:</span> ${esc(d.next.title)}${d.next.artist ? ` <span class="dimmed">· ${esc(d.next.artist)}</span>` : ""}</div>` : "";
      el.innerHTML = `<div class="ma-box ma-${layout} ma-cover-${esc(c.cover || "medium")} ${d.state === "paused" ? "ma-paused" : ""}">
          ${layout === "background" && d.image ? `<div class="ma-bg" style="background-image:url('${esc(d.image).replace(/'/g, "%27")}')"></div>` : ""}
          ${cover}
          <div class="ma-info">
            ${status.length ? `<div class="xsmall dimmed ma-status">${esc(status.join(" · "))}</div>` : ""}
            <div class="medium bright ma-title">${esc(d.title || "–")}</div>
            ${line2.length ? `<div class="small normal ma-artist">${esc(line2.join(" · "))}</div>` : ""}
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
