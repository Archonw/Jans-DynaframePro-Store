/* Photo Mosaic - die Szene.
 *
 * Ein Foto entsteht aus hunderten eigenen kleinen Fotos. Das Plugin liefert
 * die Kacheln als wenige große Bögen (api/sheet) mit ihren Farben
 * (api/scene) und zu jedem Motiv das Bild samt Farben je Zelle (api/next).
 * Welche Kachel in welche Zelle kommt, rechnet die Szene selbst, in kleinen
 * Happen, während noch das vorige Bild steht.
 *
 * Ablauf "classic": Foto -> Kacheln legen sich darüber -> Mosaik -> langsame
 * Fahrt auf eine Kachel, die zum echten Foto wird -> zurück -> Überblendung
 * zum Original -> nächstes Motiv.
 * Ablauf "endless": wie oben, aber die Fahrt geht in die Kachel hinein, bis
 * sie den Schirm füllt; dieses Foto ist dann das nächste Motiv.
 *
 * Zum Ausprobieren: ?plugin=<URL der Plugin-Seite> &speed=4 &lang=de|en|es
 * &flow=classic|endless &tiles=40..130
 */
(function () {
  "use strict";

  const PLUGIN_ID = "PhotoMosaic";
  const MAX_SIDE = 1920;            // Auflösung der Leinwand; der Pi dankt es
  const MOSAIC_MAX = 3200;          // Breite des vorgezeichneten Mosaiks
  const params = new URLSearchParams(location.search);
  const SPEED = Math.max(0.1, Number(params.get("speed")) || 1);
  const advanced = `/Plugins/Advanced/${PLUGIN_ID}/`;
  const sameOrigin = (location.protocol === "http:" && (location.port === "" || location.port === "80"))
    || (location.protocol === "https:" && (location.port === "" || location.port === "443"));
  const pluginBases = params.get("plugin") ? [params.get("plugin").replace(/\/?$/, "/")] : [...new Set(sameOrigin ? [
    `${location.origin}${advanced}`,
    `${location.protocol}//${location.hostname}:8003${advanced}`
  ] : [
    `${location.protocol}//${location.hostname || "localhost"}:8003${advanced}`,
    `http://${location.hostname || "localhost"}${advanced}`
  ])];
  let baseIndex = 0;

  const TEXT = {
    de: { made: "Aus {n} eigenen Fotos", wait: "Photo Mosaic legt die Kacheln an …", none: "Photo Mosaic findet keine Fotos. Wähle auf der Plugin-Seite eine Quelle.",
      unreachable: "Photo Mosaic antwortet nicht.", login: "Bitte zuerst im Browser beim Rahmen anmelden.", of: "{a} von {b}" },
    en: { made: "Made of {n} of your photos", wait: "Photo Mosaic is preparing the tiles …", none: "Photo Mosaic finds no photos. Pick a source on the plugin page.",
      unreachable: "Photo Mosaic is not responding.", login: "Please sign in to the frame in the browser first.", of: "{a} of {b}" },
    es: { made: "Hecho con {n} de tus fotos", wait: "Photo Mosaic está preparando las teselas …", none: "Photo Mosaic no encuentra fotos. Elige una fuente en la página del plugin.",
      unreachable: "Photo Mosaic no responde.", login: "Inicia sesión primero en el marco desde el navegador.", of: "{a} de {b}" }
  };
  let lang = params.get("lang") || "en";
  const tx = (key, values) => {
    let text = (TEXT[lang] || TEXT.en)[key] || key;
    for (const [k, v] of Object.entries(values || {})) text = text.replace(`{${k}}`, v);
    return text;
  };

  const canvas = document.getElementById("stage");
  const ctx = canvas.getContext("2d");
  const note = document.getElementById("note");
  let W = 0;
  let H = 0;

  const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
  const lerp = (a, b, k) => a + (b - a) * k;
  const seg = (t, a, b) => clamp((t - a) / (b - a));
  const easeInOut = (k) => k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
  const smooth = (k) => k * k * (3 - 2 * k);
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  // ------------------------------------------------------------ Plugin

  async function api(path, asText) {
    let lastError = null;
    for (let i = 0; i < pluginBases.length; i += 1) {
      const base = pluginBases[(baseIndex + i) % pluginBases.length];
      try {
        const response = await fetch(base + path, { cache: "no-store", credentials: "same-origin" });
        if (response.redirected && /login/i.test(response.url)) throw new Error("login");
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const body = asText ? await response.text() : await response.json();
        baseIndex = (baseIndex + i) % pluginBases.length;
        return body;
      } catch (error) {
        lastError = error;
      }
    }
    throw lastError || new Error("unreachable");
  }

  function url(path) {
    return pluginBases[baseIndex] + path;
  }

  function loadImage(src) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.decoding = "async";
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error("image " + src));
      img.src = src;
    });
  }

  function report(message) {
    api("api/report?m=" + encodeURIComponent(String(message).slice(0, 180))).catch(() => {});
  }

  // DynaFrame wartet, bis die Szene meldet, dass sie steht; sonst bricht der
  // Fernseher nach einer Frist ab ("scene readiness deadline expired").
  let readySent = false;
  function ready() {
    if (readySent) return;
    readySent = true;
    try { window.DynaFrameScene?.ready?.(); } catch (_) { /* Vorschau im Browser */ }
  }

  function showNote(text) {
    if (text) ready();
    note.textContent = text || "";
    note.hidden = !text;
  }

  // ------------------------------------------------------------ Farben

  const LIN = new Float32Array(256);
  for (let i = 0; i < 256; i += 1) {
    const c = i / 255;
    LIN[i] = c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  }
  const fLab = (t) => t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116;

  function lab(r, g, b, out, at) {
    const R = LIN[r], G = LIN[g], B = LIN[b];
    const x = fLab((0.4124 * R + 0.3576 * G + 0.1805 * B) / 0.95047);
    const y = fLab(0.2126 * R + 0.7152 * G + 0.0722 * B);
    const z = fLab((0.0193 * R + 0.1192 * G + 0.9505 * B) / 1.08883);
    out[at] = 116 * y - 16;
    out[at + 1] = 500 * (x - y);
    out[at + 2] = 200 * (y - z);
  }

  // ------------------------------------------------------------ Kacheln

  const lib = {
    ver: -1, count: 0, sheets: [], grid: 16, tile: 96,
    lab: null,          // Float32Array(count * 12)
    info: []            // [datum, ort]
  };
  let config = { Tiles: "80", ColorBlend: 30, Ghost: 12, Flow: "classic", Tempo: "normal", Captions: true, ShowCount: false, PauseSeconds: 3, TourTiles: 5 };
  let progress = null;
  let lastScene = 0;

  async function refreshLibrary() {
    const data = await api(`api/scene?v=${lib.ver}`);
    lastScene = performance.now();
    if (!data || !data.success) return false;
    config = Object.assign(config, data.settings || {});
    if (params.get("flow")) config.Flow = params.get("flow");
    if (params.get("tiles")) config.Tiles = params.get("tiles");
    lang = params.get("lang") || config.Language || lang;
    document.documentElement.lang = lang;
    progress = data.progress;
    if (data.ver === lib.ver || !data.tiles) return lib.count > 0;
    const sheets = [];
    for (let n = 0; n < data.sheets; n += 1) {
      sheets.push(await loadImage(url(`api/sheet?v=${data.ver}&n=${n}`)));
    }
    const count = data.tiles.length;
    const labs = new Float32Array(count * 12);
    data.tiles.forEach((row, i) => {
      const f = row[0];
      for (let q = 0; q < 4; q += 1) lab(f[q * 3], f[q * 3 + 1], f[q * 3 + 2], labs, i * 12 + q * 3);
    });
    Object.assign(lib, { ver: data.ver, count, sheets, grid: data.grid, tile: data.tile, lab: labs,
      info: data.tiles.map((row) => [row[1], row[2]]) });
    return count > 0;
  }

  function drawTile(g, index, x, y, size) {
    const per = lib.grid * lib.grid;
    const sheet = lib.sheets[Math.floor(index / per)];
    if (!sheet) return;
    const slot = index % per;
    const T = lib.tile;
    // 1 px Rand weglassen: sonst färbt beim Vergrößern die Nachbarkachel im Bogen ab
    g.drawImage(sheet, (slot % lib.grid) * T + 1, Math.floor(slot / lib.grid) * T + 1, T - 2, T - 2, x, y, size, size);
  }

  // ------------------------------------------------------------ Raster und Zuordnung

  function layout() {
    const n = Math.max(8, Number(config.Tiles) || 80);
    let cols, rows, cell;
    if (W >= H) {
      cols = n; cell = W / cols; rows = Math.ceil(H / cell - 0.001);
    } else {
      rows = n; cell = H / rows; cols = Math.ceil(W / cell - 0.001);
    }
    return { cols, rows, cell, mw: cols * cell, mh: rows * cell };
  }

  /* Für jede Zelle die passendste Kachel: Abstand der vier Viertel in Lab,
   * dazu ein Aufschlag je Verwendung, und nie dieselbe Kachel im Umkreis von
   * zwei Zellen. Läuft in Happen von ~12 ms, damit die Animation weiterläuft. */
  async function matchCells(motif) {
    const { cols, rows } = motif;
    const N = cols * rows;
    const cellLab = new Float32Array(N * 12);
    const c = motif.cells;
    for (let i = 0; i < N; i += 1) {
      for (let q = 0; q < 4; q += 1) lab(c[i * 12 + q * 3], c[i * 12 + q * 3 + 1], c[i * 12 + q * 3 + 2], cellLab, i * 12 + q * 3);
    }
    const assign = new Int32Array(N).fill(-1);
    const score = new Float32Array(N);
    const uses = new Uint16Array(lib.count);
    const order = new Int32Array(N);
    for (let i = 0; i < N; i += 1) order[i] = i;
    for (let i = N - 1; i > 0; i -= 1) {
      const j = Math.floor(Math.random() * (i + 1));
      const t = order[i]; order[i] = order[j]; order[j] = t;
    }
    const T = lib.lab;
    const M = lib.count;
    const K = 8;
    const bestI = new Int32Array(K);
    const bestD = new Float32Array(K);
    // Aufschlag je Wiederholung: klein genug, dass gleichfarbige Flächen
    // (Himmel, Wand) die passenden Kacheln mehrfach nehmen dürfen
    const repeat = Number(params.get("repeat")) || 70;
    let k = 0;
    while (k < N) {
      const until = performance.now() + 12;
      while (k < N && performance.now() < until) {
        const cellIndex = order[k];
        const base = cellIndex * 12;
        const l0 = cellLab[base], l1 = cellLab[base + 1], l2 = cellLab[base + 2], l3 = cellLab[base + 3],
          l4 = cellLab[base + 4], l5 = cellLab[base + 5], l6 = cellLab[base + 6], l7 = cellLab[base + 7],
          l8 = cellLab[base + 8], l9 = cellLab[base + 9], l10 = cellLab[base + 10], l11 = cellLab[base + 11];
        bestD.fill(Infinity);
        bestI.fill(-1);
        for (let t = 0; t < M; t += 1) {
          const o = t * 12;
          let d = uses[t] * repeat;
          let e = T[o] - l0; d += e * e * 1.3; e = T[o + 1] - l1; d += e * e; e = T[o + 2] - l2; d += e * e;
          e = T[o + 3] - l3; d += e * e * 1.3; e = T[o + 4] - l4; d += e * e; e = T[o + 5] - l5; d += e * e;
          if (d >= bestD[K - 1]) continue;
          e = T[o + 6] - l6; d += e * e * 1.3; e = T[o + 7] - l7; d += e * e; e = T[o + 8] - l8; d += e * e;
          e = T[o + 9] - l9; d += e * e * 1.3; e = T[o + 10] - l10; d += e * e; e = T[o + 11] - l11; d += e * e;
          if (d >= bestD[K - 1]) continue;
          let p = K - 1;
          while (p > 0 && bestD[p - 1] > d) { bestD[p] = bestD[p - 1]; bestI[p] = bestI[p - 1]; p -= 1; }
          bestD[p] = d; bestI[p] = t;
        }
        // Die beste Kachel, die nicht schon in der Nähe liegt
        const cx = cellIndex % cols, cy = (cellIndex - cx) / cols;
        let pick = bestI[0], pickD = bestD[0];
        for (let b = 0; b < K && bestI[b] >= 0; b += 1) {
          let clash = false;
          for (let dy = -2; dy <= 2 && !clash; dy += 1) {
            const yy = cy + dy;
            if (yy < 0 || yy >= rows) continue;
            for (let dx = -2; dx <= 2; dx += 1) {
              const xx = cx + dx;
              if (xx >= 0 && xx < cols && assign[yy * cols + xx] === bestI[b]) { clash = true; break; }
            }
          }
          if (!clash) { pick = bestI[b]; pickD = bestD[b]; break; }
        }
        assign[cellIndex] = pick;
        score[cellIndex] = pickD;
        uses[pick] += 1;
        k += 1;
      }
      await sleep(0);
    }
    // Mittlere Farbe je Zelle für die Tönung
    const tint = new Array(N);
    for (let i = 0; i < N; i += 1) {
      let r = 0, g = 0, b = 0;
      for (let q = 0; q < 4; q += 1) { r += c[i * 12 + q * 3]; g += c[i * 12 + q * 3 + 1]; b += c[i * 12 + q * 3 + 2]; }
      tint[i] = `rgb(${Math.round(r / 4)},${Math.round(g / 4)},${Math.round(b / 4)})`;
    }
    const used = uses.reduce((n, u) => n + (u > 0 ? 1 : 0), 0);
    return { assign, score, tint, used };
  }

  // ------------------------------------------------------------ Ein Motiv

  async function loadMotif(tileIndex) {
    const g = layout();
    const query = `api/next?v=${lib.ver}&w=${Math.round(g.mw)}&cols=${g.cols}&rows=${g.rows}` +
      (tileIndex != null && tileIndex >= 0 ? `&tile=${tileIndex}` : "");
    const data = await api(query);
    if (!data || !data.success) throw new Error("no motif");
    const image = await loadImage(url(`api/target?id=${data.id}`));
    const motif = Object.assign(g, { id: data.id, cells: data.cells, image, taken: data.taken, place: data.place, own: Boolean(data.own),
      libVer: lib.ver, W, H });
    Object.assign(motif, await matchCells(motif));
    motif.mosaic = null;
    return motif;
  }

  // Das Mosaik vorgezeichnet in einer eigenen Leinwand
  function prepareCanvas(motif) {
    const ms = Math.max(8, Math.min(lib.tile, Math.floor(Math.min(MOSAIC_MAX, motif.mw * 2) / motif.cols)));
    const c = document.createElement("canvas");
    c.width = motif.cols * ms;
    c.height = motif.rows * ms;
    const g = c.getContext("2d");
    g.imageSmoothingQuality = "high";
    g.drawImage(motif.image, 0, 0, c.width, c.height);
    motif.mosaic = c;
    motif.mg = g;
    motif.ms = ms;
    // Reihenfolge, in der die Kacheln erscheinen: eine Welle von einem Punkt aus, etwas verrauscht
    const N = motif.cols * motif.rows;
    const fx = Math.random() * motif.cols, fy = Math.random() * motif.rows;
    const maxD = Math.hypot(Math.max(fx, motif.cols - fx), Math.max(fy, motif.rows - fy));
    const when = new Float32Array(N);
    for (let i = 0; i < N; i += 1) {
      const x = i % motif.cols, y = (i - x) / motif.cols;
      when[i] = clamp(0.75 * Math.hypot(x - fx, y - fy) / maxD + 0.25 * Math.random());
    }
    const order = Array.from({ length: N }, (_, i) => i).sort((a, b) => when[a] - when[b]);
    motif.revealOrder = order;
    motif.revealWhen = when;
    motif.revealed = 0;
  }

  function paintCell(motif, i) {
    const x = i % motif.cols, y = (i - x) / motif.cols;
    const s = motif.ms;
    drawTile(motif.mg, motif.assign[i], x * s, y * s, s);
    const blend = (Number(config.ColorBlend) || 0) / 100;
    if (blend > 0) {
      motif.mg.globalAlpha = blend;
      motif.mg.fillStyle = motif.tint[i];
      motif.mg.fillRect(x * s, y * s, s, s);
      motif.mg.globalAlpha = 1;
    }
  }

  function revealUntil(motif, k) {
    const order = motif.revealOrder;
    while (motif.revealed < order.length && motif.revealWhen[order[motif.revealed]] <= k) {
      paintCell(motif, order[motif.revealed]);
      motif.revealed += 1;
    }
  }

  function pickFocus(motif) {
    const { cols, rows } = motif;
    const rows_ = [];
    for (let y = Math.floor(rows * 0.2); y < Math.ceil(rows * 0.8); y += 1) {
      for (let x = Math.floor(cols * 0.2); x < Math.ceil(cols * 0.8); x += 1) {
        const i = y * cols + x;
        const t = motif.assign[i];
        const info = lib.info[t] || ["", ""];
        const bonus = (info[0] ? 0.85 : 1) * (info[1] ? 0.85 : 1);
        rows_.push([motif.score[i] * bonus, i]);
      }
    }
    rows_.sort((a, b) => a[0] - b[0]);
    const top = rows_.slice(0, Math.max(1, Math.floor(rows_.length * 0.25)));
    const choice = top[Math.floor(Math.random() * top.length)];
    return choice ? choice[1] : Math.floor(cols * rows / 2);
  }

  // ------------------------------------------------------------ Zeichnen

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let w = Math.round(window.innerWidth * dpr);
    let h = Math.round(window.innerHeight * dpr);
    const k = Math.min(1, MAX_SIDE / Math.max(w, h));
    w = Math.round(w * k);
    h = Math.round(h * k);
    if (w === W && h === H) return false;
    W = canvas.width = w;
    H = canvas.height = h;
    return true;
  }

  // Kamera: Mittelpunkt (cx, cy) in Mosaik-Pixeln, Zoom z
  function homeCam(m) {
    return { cx: m.mw / 2, cy: m.mh / 2, z: 1 };
  }

  function clampCam(m, cam) {
    const hw = W / (2 * cam.z), hh = H / (2 * cam.z);
    cam.cx = m.mw >= 2 * hw ? clamp(cam.cx, hw, m.mw - hw) : m.mw / 2;
    cam.cy = m.mh >= 2 * hh ? clamp(cam.cy, hh, m.mh - hh) : m.mh / 2;
    return cam;
  }

  function drawPhoto(m, cam, alpha) {
    if (alpha <= 0) return;
    const sw = W / cam.z, sh = H / cam.z;
    const kx = m.image.naturalWidth / m.mw;
    const ky = m.image.naturalHeight / m.mh;
    ctx.globalAlpha = alpha;
    ctx.drawImage(m.image, (cam.cx - sw / 2) * kx, (cam.cy - sh / 2) * ky, sw * kx, sh * ky, 0, 0, W, H);
    ctx.globalAlpha = 1;
  }

  function drawMosaic(m, cam, focus) {
    const cellOnScreen = m.cell * cam.z;
    const sw = W / cam.z, sh = H / cam.z;
    if (cellOnScreen <= m.ms * 1.3 || !m.mosaic) {
      const k = m.ms / m.cell;
      ctx.drawImage(m.mosaic, (cam.cx - sw / 2) * k, (cam.cy - sh / 2) * k, sw * k, sh * k, 0, 0, W, H);
    } else {
      // Nah dran: die sichtbaren Kacheln einzeln aus den Bögen, schärfer als das vorgezeichnete Mosaik
      const x0 = Math.max(0, Math.floor((cam.cx - sw / 2) / m.cell));
      const x1 = Math.min(m.cols - 1, Math.floor((cam.cx + sw / 2) / m.cell));
      const y0 = Math.max(0, Math.floor((cam.cy - sh / 2) / m.cell));
      const y1 = Math.min(m.rows - 1, Math.floor((cam.cy + sh / 2) / m.cell));
      const blend = (Number(config.ColorBlend) || 0) / 100;
      const size = cellOnScreen + 0.6;
      for (let y = y0; y <= y1; y += 1) {
        for (let x = x0; x <= x1; x += 1) {
          const i = y * m.cols + x;
          const sx = (x * m.cell - cam.cx) * cam.z + W / 2;
          const sy = (y * m.cell - cam.cy) * cam.z + H / 2;
          drawTile(ctx, m.assign[i], sx, sy, size);
          if (blend > 0) {
            ctx.globalAlpha = blend * (i === focus.index ? 1 - focus.real : 1);
            ctx.fillStyle = m.tint[i];
            ctx.fillRect(sx, sy, size, size);
            ctx.globalAlpha = 1;
          }
        }
      }
    }
    // Die Kachel im Fokus als echtes Foto
    if (focus.image && focus.real > 0) {
      const sx = ((focus.index % m.cols) * m.cell - cam.cx) * cam.z + W / 2;
      const sy = (Math.floor(focus.index / m.cols) * m.cell - cam.cy) * cam.z + H / 2;
      ctx.globalAlpha = focus.real;
      ctx.drawImage(focus.image, sx, sy, cellOnScreen + 0.6, cellOnScreen + 0.6);
      ctx.globalAlpha = 1;
    }
  }

  function pill(text, x, y, size, align) {
    if (!text) return;
    ctx.font = `600 ${Math.round(size)}px -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif`;
    const w = ctx.measureText(text).width;
    const pad = size * 0.7;
    const bx = align === "right" ? x - w - pad * 2 : align === "center" ? x - w / 2 - pad : x;
    const by = y - size * 1.05;
    ctx.fillStyle = "rgba(10,12,16,0.62)";
    const r = size * 0.9;
    const bw = w + pad * 2, bh = size * 2.1;
    ctx.beginPath();
    ctx.moveTo(bx + r, by);
    ctx.arcTo(bx + bw, by, bx + bw, by + bh, r);
    ctx.arcTo(bx + bw, by + bh, bx, by + bh, r);
    ctx.arcTo(bx, by + bh, bx, by, r);
    ctx.arcTo(bx, by, bx + bw, by, r);
    ctx.fill();
    ctx.fillStyle = "rgba(255,255,255,0.94)";
    ctx.textBaseline = "middle";
    ctx.fillText(text, bx + pad, by + bh / 2 + size * 0.04);
  }

  function caption(taken, place) {
    let when = "";
    if (taken && /^\d{4}-\d{2}/.test(taken)) {
      const d = new Date(Number(taken.slice(0, 4)), Number(taken.slice(5, 7)) - 1, 1);
      try {
        when = d.toLocaleDateString(lang, { month: "long", year: "numeric" });
      } catch (e) {
        when = taken.slice(0, 7);
      }
    }
    return [when, place || ""].filter(Boolean).join(" · ");
  }

  // ------------------------------------------------------------ Ablauf

  const BASE = {
    fade: 1.6, build: 7, hold: 3.5, zoomIn: 10, tile: 6, zoomOut: 8, reveal: 3.5, original: 8,
    dive: 15, settle: 2
  };
  function dur(name) {
    const k = config.Tempo === "slow" ? 1.5 : config.Tempo === "fast" ? 0.65 : 1;
    return BASE[name] * k / SPEED;
  }

  let current = null;        // Motiv, das gerade läuft
  let previous = null;       // für die Überblendung
  let pending = null;        // Promise auf das nächste Motiv
  let phase = "wait";
  let phaseStart = 0;
  let focus = { index: -1, image: null, real: 0, tile: -1 };
  let lastDraw = 0;
  let failures = 0;
  let tourCount = 0;         // Rundgang: wie viele Kacheln dieses Motivs schon dran waren

  // Rundgang: rein, raus, kurz warten, nächste Kachel. Nach TourTiles Kacheln
  // kommt das nächste Motiv (0 = beim Motiv bleiben).
  function tourGoesOn() {
    if (config.Flow !== "tour") return false;
    const most = Number(config.TourTiles) || 0;
    return most <= 0 || tourCount + 1 < most;
  }

  function setPhase(name) {
    phase = name;
    phaseStart = performance.now() / 1000;
  }

  function prefetchNext(tileIndex) {
    pending = loadMotif(tileIndex).catch((error) => {
      report("Motiv: " + error.message);
      return null;
    });
  }

  function startFocus(m) {
    const index = pickFocus(m);
    const tile = m.assign[index];
    focus = { index, tile, image: null, real: 0 };
    loadImage(url(`api/zoom?v=${lib.ver}&i=${tile}`)).then((img) => {
      if (focus.tile === tile) focus.image = img;
    }).catch(() => {});
    if (config.Flow === "endless") prefetchNext(tile);
  }

  async function begin(next) {
    previous = current;
    current = next;
    prepareCanvas(current);
    tourCount = 0;
    setPhase(previous ? "fade" : "build");
    ready();
  }

  async function advance() {
    // Das nächste Motiv abwarten; klappt es nicht, nochmal versuchen
    const next = pending ? await pending : null;
    pending = null;
    if (next && next.W === W && next.H === H && next.libVer === lib.ver) {
      failures = 0;
      await begin(next);
      return;
    }
    failures += 1;
    await sleep(Math.min(30000, 2000 * failures));
    prefetchNext(null);
    phase = current ? "original" : "wait";
    phaseStart = performance.now() / 1000;
    if (!current) waitForFirst();
  }

  let waiting = false;
  async function waitForFirst() {
    if (waiting) return;
    waiting = true;
    try {
      for (;;) {
        try {
          const ok = await refreshLibrary();
          if (ok) {
            showNote("");
            const m = await loadMotif(null);
            await begin(m);
            return;
          }
          if (progress && progress.phase) {
            const total = progress.total || 0;
            showNote(tx("wait") + (total ? "  " + tx("of", { a: progress.done, b: total }) : ""));
          } else {
            showNote(tx("none"));
          }
        } catch (error) {
          showNote(error && error.message === "login" ? tx("login") : tx("unreachable"));
        }
        await sleep(5000);
      }
    } finally {
      waiting = false;
    }
  }

  function frame() {
    requestAnimationFrame(frame);
    const nowMs = performance.now();
    if (resize() && current) {
      // Neue Größe: neues Raster beim nächsten Motiv
      pending = null;
      prefetchNext(null);
    }
    if (!current) {
      if (nowMs - lastDraw > 500) {
        ctx.fillStyle = "#0b0d11";
        ctx.fillRect(0, 0, W, H);
        lastDraw = nowMs;
      }
      return;
    }
    const t = nowMs / 1000 - phaseStart;
    const m = current;
    const endless = config.Flow === "endless";
    let cam = homeCam(m);
    const ghost = (Number(config.Ghost) || 0) / 100;

    switch (phase) {
      case "fade": {
        const k = seg(t, 0, dur("fade"));
        if (previous && previous.image) {
          drawPhoto(previous, previous.endCam || homeCam(previous), 1);
        }
        drawPhoto(m, cam, smooth(k));
        if (k >= 1) { previous = null; setPhase("build"); }
        break;
      }
      case "build": {
        const k = seg(t, 0, dur("build"));
        revealUntil(m, k);
        drawMosaic(m, cam, focus);
        drawPhoto(m, cam, lerp(0, ghost, k));
        if (k >= 1) { revealUntil(m, 2); setPhase("hold"); startFocus(m); }
        break;
      }
      case "hold": {
        drawMosaic(m, cam, focus);
        drawPhoto(m, cam, ghost);
        const a = seg(t, 0.3, 1.2) * (1 - seg(t, dur("hold") - 0.8, dur("hold")));
        if (config.ShowCount) {
          ctx.globalAlpha = a;
          pill(tx("made", { n: m.used.toLocaleString(lang) }), W - H * 0.04, H - H * 0.05, H * 0.026, "right");
          ctx.globalAlpha = 1;
        }
        if (t >= dur("hold")) setPhase(endless ? "dive" : "zoomIn");
        break;
      }
      case "zoomIn":
      case "zoomOut":
      case "tile":
      case "dive": {
        const fx = (focus.index % m.cols + 0.5) * m.cell;
        const fy = (Math.floor(focus.index / m.cols) + 0.5) * m.cell;
        const zTile = Math.max(1.5, (Math.min(W, H) * 0.42) / m.cell);
        const zFull = (Math.max(W, H) * 1.02) / m.cell;
        let e;
        let zEnd = zTile;
        if (phase === "zoomIn") e = easeInOut(seg(t, 0, dur("zoomIn")));
        else if (phase === "tile") e = 1;
        else if (phase === "zoomOut") e = 1 - easeInOut(seg(t, 0, dur("zoomOut")));
        else { e = easeInOut(seg(t, 0, dur("dive"))); zEnd = zFull; }
        const z = Math.exp(lerp(0, Math.log(zEnd), e));
        // Der Fokuspunkt wandert gleichmäßig zur Bildmitte, die Kamera folgt daraus
        const s0x = fx - m.mw / 2, s0y = fy - m.mh / 2;
        cam = { z, cx: fx - lerp(s0x, 0, e) / z, cy: fy - lerp(s0y, 0, e) / z };
        if (phase !== "dive") clampCam(m, cam);
        const near = clamp((m.cell * z - lib.tile) / (lib.tile * 1.5));
        if (phase === "tile") focus.real = smooth(seg(t, 0.2, 1.8)) * (focus.image ? 1 : 0);
        else if (phase === "zoomOut") focus.real = focus.image ? clamp(e * 1.4 - 0.4) : 0;
        else if (phase === "dive") focus.real = focus.image ? smooth(near) : 0;
        else focus.real = focus.image ? smooth(clamp((e - 0.75) * 4)) * 0.6 : 0;
        drawMosaic(m, cam, focus);
        drawPhoto(m, cam, ghost * (1 - focus.real * 0.85) * (phase === "dive" ? 1 - e : 1));
        // Bildunterschrift der Kachel
        const info = lib.info[focus.tile] || ["", ""];
        const text = config.Captions ? caption(info[0], info[1]) : "";
        if (text) {
          const size = m.cell * z;
          const sy = (fy - cam.cy) * z + H / 2 + size / 2;
          let a = phase === "tile" ? seg(t, 0.6, 1.6) : phase === "zoomOut" ? clamp((e - 0.85) * 6)
            : phase === "dive" ? clamp((size / H - 0.3) * 5) * (1 - clamp((size / H - 0.75) * 6)) : 0;
          if (a > 0 && sy + H * 0.06 < H) {
            ctx.globalAlpha = a;
            pill(text, (fx - cam.cx) * z + W / 2, sy + H * 0.045, H * 0.024, "center");
            ctx.globalAlpha = 1;
          }
        }
        if (phase === "zoomIn" && t >= dur("zoomIn")) {
          setPhase("tile");
          if (!tourGoesOn()) prefetchNext(null);   // rechnen, während das Bild steht
        }
        else if (phase === "tile" && t >= dur("tile")) setPhase("zoomOut");
        else if (phase === "zoomOut" && t >= dur("zoomOut")) {
          focus.real = 0;
          if (tourGoesOn()) {
            focus = { index: -1, image: null, real: 0, tile: -1 };
            setPhase("pause");
          } else setPhase("reveal");
        }
        else if (phase === "dive" && t >= dur("dive")) {
          m.endCam = cam;
          setPhase("handover");
          handover();
        }
        break;
      }
      case "handover": {
        // Endlos: die Kachel füllt den Schirm; gleich wird ihr Foto zum nächsten Motiv
        const c = m.endCam || cam;
        drawMosaic(m, c, focus);
        break;
      }
      case "pause": {
        // Rundgang: das ganze Mosaik kurz stehen lassen, dann zur nächsten Kachel
        drawMosaic(m, cam, focus);
        drawPhoto(m, cam, ghost);
        const wait = Math.max(0, Number(config.PauseSeconds) || 0);
        if (t >= wait) {
          tourCount += 1;
          startFocus(m);
          setPhase("zoomIn");
        }
        break;
      }
      case "reveal": {
        const k = seg(t, 0, dur("reveal"));
        drawMosaic(m, cam, focus);
        drawPhoto(m, cam, lerp(ghost, 1, smooth(k)));
        if (k >= 1) setPhase("original");
        break;
      }
      case "original": {
        drawPhoto(m, cam, 1);
        const text = config.Captions ? caption(m.taken, m.place) : "";
        const a = seg(t, 0.4, 1.4) * (1 - seg(t, dur("original") - 1, dur("original") - 0.2));
        if (text && a > 0) {
          ctx.globalAlpha = a;
          pill(text, H * 0.04, H - H * 0.05, H * 0.026, "left");
          ctx.globalAlpha = 1;
        }
        if (t >= dur("original")) {
          m.endCam = cam;
          setPhase("next");
          advance();
        }
        break;
      }
      case "next":
        drawPhoto(m, cam, 1);
        break;
      case "handIn": {
        // Endlos: von der Kachel, die den Schirm füllt, zum ganzen Foto
        const k = seg(t, 0, dur("fade") * 1.6);
        if (previous) drawMosaic(previous, previous.endCam, focus);
        const z = Math.exp(lerp(Math.log(1.6), 0, easeInOut(k)));
        drawPhoto(m, { cx: m.mw / 2, cy: m.mh / 2, z }, smooth(clamp(k * 1.6)));
        if (k >= 1) {
          previous = null;
          focus = { index: -1, image: null, real: 0, tile: -1 };
          setPhase("settle");
        }
        break;
      }
      case "settle":
        drawPhoto(m, cam, 1);
        if (t >= dur("settle")) {
          if (config.MotifKind === "upload" && !m.own) {
            m.endCam = cam;
            setPhase("next");
            advance();
          } else setPhase("build");
        }
        break;
      default:
        break;
    }
    lastDraw = nowMs;
    // Ab und zu nach neuen Einstellungen oder Kacheln fragen
    if (nowMs - lastScene > 60000 && (phase === "original" || phase === "next")) {
      lastScene = nowMs;
      refreshLibrary().catch(() => {});
    }
  }

  async function handover() {
    const next = pending ? await pending : null;
    pending = null;
    if (next && next.W === W && next.H === H && next.libVer === lib.ver) {
      // Das Foto der Kachel wird das nächste Motiv
      previous = current;
      current = next;
      prepareCanvas(current);
      setPhase("handIn");
      // Eigene Motive: nach der Kachel kommt wieder eins der eigenen Fotos
      if (config.MotifKind === "upload") prefetchNext(null);
      return;
    }
    prefetchNext(null);
    setPhase("reveal");
  }

  resize();
  window.addEventListener("resize", resize);
  requestAnimationFrame(frame);
  setTimeout(ready, 8000);   // falls das erste Bild länger braucht
  waitForFirst();
}());
