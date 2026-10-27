/* Bordcomputer-Skin für Dynaframe's Magic Mirror.
 *
 * Schwarzer Schirm, links eine Säule aus runden Balken, oben und unten je ein
 * Rahmen mit Bogen in eine waagrechte Leiste. Felder (data-slot): time, info,
 * main, a, b, c, ticker. Was darin steht, wählt man auf der Plugin-Seite.
 * Eigener Widget-Typ "stardate": Sternzeit = (Jahr - 2000) * 1000 + Anteil des
 * Jahres * 1000, also am 24.10.2026 etwa 26811.4. Fan-Design, kein offizielles Produkt.
 */
(function () {
  "use strict";

  const MF = window.MagicFrame;
  if (!MF || !MF.registerSkin) return;
  const h = MF.helpers;
  const { esc, t } = h;

  const TITLE = { de: "BORDCOMPUTER", en: "MAIN COMPUTER", es: "ORDENADOR CENTRAL" };
  const COLORS = ["--c1", "--c2", "--c3", "--c4", "--c5", "--c6"];

  // Sternzeit mit einer Nachkommastelle (ein Zehntel ist etwa 9 Stunden)
  function stardate(d = new Date()) {
    const y = d.getFullYear();
    const start = new Date(y, 0, 1).getTime();
    const part = (d.getTime() - start) / (new Date(y + 1, 0, 1).getTime() - start);
    return ((y - 2000) * 1000 + part * 1000).toFixed(1);
  }

  const num = () => `${String(Math.floor(Math.random() * 90) + 10)}-${String(Math.floor(Math.random() * 9000) + 1000)}`;
  const color = (i) => `var(${COLORS[i % COLORS.length]})`;
  const pills = (list) => list.map(([c, cls]) => `<div class="pill ${cls || ""}" style="--c:${color(c)}">${num()}</div>`).join("");
  const rail = (list) => `<div class="rail">${list.map(([c, f]) => `<i style="--c:${color(c)};--f:${f}"></i>`).join("")}</div>`;
  const elbow = (dir, c) => `<div class="elbow ${dir}" style="--c:${color(c)}"><span class="ec"></span><span class="eb"></span><span class="ei"></span><span class="num">${num()}</span></div>`;
  // Ein Feld mit Beschriftung; die Farbe der Linie wechselt von Feld zu Feld
  const panel = (id, c) => `<section class="panel s-${id}" style="--c:${color(c)}"><header><span data-caption="${id}"></span></header><div data-slot="${id}"></div></section>`;

  const STARDATE = {
    render(el, data, ctx) {
      el.innerHTML = `<div class="w w-stardate"><small>${esc(t({ de: "Sternzeit", en: "Stardate", es: "Fecha estelar" }))}</small><b></b><span></span></div>`;
      ctx.caption(t({ de: "Logbuch", en: "Log", es: "Bitácora" }));
      this.tick(el, data, ctx);
    },
    tick(el) {
      const d = new Date();
      const b = el.querySelector("b"), span = el.querySelector("span");
      const sd = stardate(d);
      if (b.textContent !== sd) b.textContent = sd;
      const day = `${h.weekday(d)} ${h.shortDate(d)} ${d.getFullYear()}`;
      if (span.textContent !== day) span.textContent = day;
    },
  };

  // Uhrzeit in großen schmalen Ziffern, Sekunden nur auf Wunsch
  const TIME = {
    render(el, data, ctx) {
      el.innerHTML = `<div class="w w-time"><span class="hm"></span><span class="ss"></span><span class="ap"></span></div>`;
      this.tick(el, data, ctx);
    },
    tick(el, data, ctx) {
      const p = h.clockParts(new Date(), ctx.clock24);
      const seconds = ctx.moduleConfig ? !!ctx.moduleConfig.seconds : ctx.config?.seconds === true;
      const set = (sel, v) => { const n = el.querySelector(sel); if (n.textContent !== v) n.textContent = v; };
      set(".hm", p.hm);
      set(".ss", seconds ? p.sec : "");
      set(".ap", p.ampm);
    },
  };

  MF.registerWidget("stardate", STARDATE);

  MF.registerSkin("bordcomputer", {
    render(root, ctx) {
      const cfg = ctx.config || {};
      const palette = ["classic", "blue", "red"].includes(cfg.palette) ? cfg.palette : "classic";
      const title = String(cfg.title || "").trim() || t(TITLE);
      root.innerHTML = `<div class="bc pal-${palette}">
        <div class="frame upper">
          <div class="side">${pills([[1], [2, "big"]])}${elbow("down", 0)}</div>
          <div class="body">
            <div class="title">${esc(title)}</div>
            ${panel("time", 0)}${panel("info", 1)}
          </div>
          ${rail([[0, 3], [3, 1], [1, 6], [2, .6], [0, 2]])}
        </div>
        <div class="frame lower">
          <div class="side">${elbow("up", 2)}${pills([[3, "big"], [0], [4], [1, "big"], [5, "cap"]])}</div>
          <div class="body">
            ${panel("main", 2)}${panel("a", 0)}${panel("b", 3)}${panel("c", 1)}${panel("ticker", 0)}
          </div>
          ${rail([[2, 1.4], [3, 5], [0, .8], [1, 2.5], [5, 1]])}
        </div>
      </div>`;
      root._blink = 0;
    },
    // Ab und zu leuchtet ein Balken auf und eine Zahl ändert sich, wie bei einem arbeitenden Rechner
    tick(root, ctx) {
      if (ctx.config?.blink === false) return;
      if (++root._blink % 3) return;
      const all = root.querySelectorAll(".pill:not(.cap), .elbow .num");
      if (!all.length) return;
      root.querySelectorAll(".pill.on").forEach((n) => n.classList.remove("on"));
      const pick = all[Math.floor(Math.random() * all.length)];
      if (pick.classList.contains("pill")) pick.classList.add("on");
      pick.textContent = num();
    },
    widgets: { time: TIME, stardate: STARDATE },
  });
})();
