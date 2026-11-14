/* Postcards - die Senden-Seite.
 *
 * Läuft an zwei Orten mit denselben Dateien:
 *  - im Internet (GitHub Pages) mit einem Link aus der Plugin-Seite:
 *      …/postcards/#t=<Thema>&k=<Schlüssel>&l=<Sprache>[&to=<An>][&s=<Relay>]
 *    Der Teil nach # geht nie an einen Server. Foto und Gruß werden hier im
 *    Browser mit AES-256-GCM verschlüsselt und als Anhang ins Thema des
 *    Relays (ntfy) gelegt. Nur der Rahmen hat den Schlüssel.
 *  - im WLAN direkt vom Plugin (http://<Rahmen>:8120/): ohne Relay, ohne
 *    Verschlüsselung, Upload an ./api/send.
 *
 * Format (wie postlib.py): Klartext = 4 Byte Länge + Kopf (JSON) + JPEG;
 * verschlüsselt = "PCv1" + 12 Byte IV + AES-GCM(Klartext, aad "postcards1").
 */
(function () {
  "use strict";

  const TEXT = {
    de: {
      kicker: "Postcards", title: "Eine Postkarte schicken", to: "an", broken: "Dieser Link ist unvollständig. Bitte lass dir den Link noch einmal schicken.",
      closed: "Postkarten schicken ist auf dem Rahmen gerade ausgeschaltet.",
      step1: "Foto aussuchen", pick: "Foto auswählen", pickHint: "aus deinen Fotos oder gleich eins aufnehmen", otherPhoto: "Anderes Foto nehmen",
      step2: "Gruß schreiben", textPh: "Ihr Lieben, viele Grüße aus …",
      name: "Dein Name", namePh: "z. B. Oma Hilde", city: "Von wo schreibst du?", cityPh: "z. B. Bremen", cityHint: "Der Ort steht im Poststempel.",
      send: "Postkarte abschicken", needPhoto: "Bitte zuerst ein Foto aussuchen.", reading: "Foto wird vorbereitet …",
      sending: "Wird verschickt …", sent: "Deine Postkarte ist unterwegs!", waitAck: "Gleich holt der Rahmen sie ab …",
      arrived: "Angekommen! Die Karte ist am Rahmen.", later: "Der Rahmen holt sie ab, sobald er online ist. Du kannst die Seite schließen.",
      lanDone: "Angekommen! Die Karte ist am Rahmen.", waiting: "Sie erscheint, sobald sie am Rahmen freigegeben wurde.",
      another: "Noch eine Postkarte schicken", badPhoto: "Dieses Foto kann der Browser nicht öffnen. Versuch ein anderes.",
      failed: "Das hat nicht geklappt: {e}. Bitte versuch es gleich noch einmal.", noCrypto: "Dieser Browser kann die Karte nicht verschlüsseln. Bitte öffne den Link in einem aktuellen Browser.",
      privacy: "Foto und Gruß werden auf diesem Handy verschlüsselt und lassen sich nur von dem Rahmen öffnen, zu dem der Link gehört.",
      privacyLan: "Foto und Gruß gehen direkt im WLAN an den Rahmen.", empty: "Hier steht dein Gruß …", stampTown: "Postcards", toDefault: "An alle zu Hause"
    },
    en: {
      kicker: "Postcards", title: "Send a postcard", to: "to", broken: "This link is incomplete. Please ask for the link again.",
      closed: "Sending postcards is switched off on the frame right now.",
      step1: "Choose a photo", pick: "Choose photo", pickHint: "from your photos or take a new one", otherPhoto: "Choose another photo",
      step2: "Write your greeting", textPh: "Dear all, greetings from …",
      name: "Your name", namePh: "e.g. Grandma Ruth", city: "Where are you writing from?", cityPh: "e.g. Bristol", cityHint: "The town appears in the postmark.",
      send: "Send postcard", needPhoto: "Please choose a photo first.", reading: "Preparing the photo …",
      sending: "Sending …", sent: "Your postcard is on its way!", waitAck: "The frame will pick it up in a moment …",
      arrived: "Delivered! The postcard is at the frame.", later: "The frame picks it up as soon as it is online. You can close this page.",
      lanDone: "Delivered! The postcard is at the frame.", waiting: "It appears once it has been approved at the frame.",
      another: "Send another postcard", badPhoto: "The browser cannot open this photo. Try another one.",
      failed: "That did not work: {e}. Please try again in a moment.", noCrypto: "This browser cannot encrypt the postcard. Please open the link in an up-to-date browser.",
      privacy: "Your photo and greeting are encrypted on this phone and can only be opened by the frame the link belongs to.",
      privacyLan: "Your photo and greeting go straight to the frame in the Wi-Fi.", empty: "Your greeting goes here …", stampTown: "Postcards", toDefault: "To everyone at home"
    },
    es: {
      kicker: "Postcards", title: "Enviar una postal", to: "para", broken: "Este enlace está incompleto. Pide que te lo envíen de nuevo.",
      closed: "El envío de postales está desactivado ahora mismo en el marco.",
      step1: "Elige una foto", pick: "Elegir foto", pickHint: "de tus fotos o haz una nueva", otherPhoto: "Elegir otra foto",
      step2: "Escribe tu saludo", textPh: "Queridos todos, saludos desde …",
      name: "Tu nombre", namePh: "p. ej. la abuela Carmen", city: "¿Desde dónde escribes?", cityPh: "p. ej. Sevilla", cityHint: "El lugar aparece en el matasellos.",
      send: "Enviar postal", needPhoto: "Primero elige una foto.", reading: "Preparando la foto …",
      sending: "Enviando …", sent: "¡Tu postal está en camino!", waitAck: "El marco la recogerá enseguida …",
      arrived: "¡Entregada! La postal está en el marco.", later: "El marco la recogerá en cuanto esté conectado. Puedes cerrar esta página.",
      lanDone: "¡Entregada! La postal está en el marco.", waiting: "Aparecerá cuando la aprueben en el marco.",
      another: "Enviar otra postal", badPhoto: "El navegador no puede abrir esta foto. Prueba con otra.",
      failed: "No ha funcionado: {e}. Inténtalo de nuevo en un momento.", noCrypto: "Este navegador no puede cifrar la postal. Abre el enlace en un navegador actualizado.",
      privacy: "La foto y el saludo se cifran en este móvil y solo puede abrirlos el marco al que pertenece el enlace.",
      privacyLan: "La foto y el saludo van directamente al marco por la wifi.", empty: "Aquí va tu saludo …", stampTown: "Postcards", toDefault: "Para todos en casa"
    }
  };
  const LOCALE = { de: "de-DE", en: "en-GB", es: "es-ES" };
  const MAX_EDGE = 1600;
  const DEFAULT_RELAY = "https://ntfy.sh";
  const ACK = "pc-ack ";

  const $ = (id) => document.getElementById(id);
  const hash = new URLSearchParams(location.hash.replace(/^#/, ""));
  const link = { topic: hash.get("t") || "", key: hash.get("k") || "", to: hash.get("to") || "",
    server: (hash.get("s") || DEFAULT_RELAY).replace(/\/+$/, ""), lang: hash.get("l") || "" };
  let mode = link.topic && link.key ? "relay" : "lan";
  const browserLang = (navigator.language || "").slice(0, 2).toLowerCase();
  let lang = TEXT[browserLang] ? browserLang : (TEXT[link.lang] ? link.lang : "en");
  let photo = null;          // {blob, w, h, url}
  let lanInfo = null;

  const t = (key, values) => {
    let text = (TEXT[lang] || TEXT.en)[key] || TEXT.en[key] || key;
    for (const [k, v] of Object.entries(values || {})) text = text.split(`{${k}}`).join(v);
    return text;
  };

  function applyTexts() {
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-t]").forEach((el) => { el.textContent = t(el.dataset.t); });
    document.querySelectorAll("[data-tp]").forEach((el) => { el.placeholder = t(el.dataset.tp); });
    document.querySelector(".foot p").textContent = mode === "lan" ? t("privacyLan") : t("privacy");
    document.title = `${t("title")} · Postcards`;
    const to = mode === "lan" ? (lanInfo?.to || "") : link.to;
    const line = $("toLine");
    if (to) {
      line.hidden = false;
      line.innerHTML = "";
      line.append(document.createTextNode(t("to") + " "));
      const b = document.createElement("b");
      b.textContent = to;
      line.append(b);
    }
    $("backTo").textContent = to || t("toDefault");
    updateBack();
  }

  // ---------------------------------------------------------------- Merken

  const store = {
    get(key) { try { return localStorage.getItem("postcards." + key) || ""; } catch (_) { return ""; } },
    set(key, value) { try { localStorage.setItem("postcards." + key, value); } catch (_) { /* privat */ } }
  };

  // ---------------------------------------------------------------- Foto

  function loadImage(file) {
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => resolve({ img, url });
      img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("decode")); };
      img.src = url;
    });
  }

  async function readPhoto(file) {
    const { img, url } = await loadImage(file);       // Browser drehen nach EXIF von selbst
    try {
      const w0 = img.naturalWidth, h0 = img.naturalHeight;
      if (!w0 || !h0) throw new Error("decode");
      const scale = Math.min(1, MAX_EDGE / Math.max(w0, h0));
      const w = Math.max(1, Math.round(w0 * scale)), h = Math.max(1, Math.round(h0 * scale));
      const canvas = document.createElement("canvas");
      canvas.width = w; canvas.height = h;
      const ctx = canvas.getContext("2d");
      ctx.fillStyle = "#fff";
      ctx.fillRect(0, 0, w, h);
      ctx.drawImage(img, 0, 0, w, h);
      const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.86));
      if (!blob) throw new Error("encode");
      return { blob, w, h, url: URL.createObjectURL(blob) };   // ohne EXIF: kein GPS
    } finally {
      URL.revokeObjectURL(url);
    }
  }

  async function onFile() {
    const file = $("file").files && $("file").files[0];
    if (!file) return;
    setStatus(t("reading"));
    try {
      const next = await readPhoto(file);
      if (photo?.url) URL.revokeObjectURL(photo.url);
      photo = next;
      $("preview").src = photo.url;
      $("preview").hidden = false;
      $("pickEmpty").hidden = true;
      $("pick").classList.add("has");
      $("again").hidden = false;
      setStatus("");
    } catch (_) {
      setStatus(t("badPhoto"), true);
    }
    $("file").value = "";
    updateButton();
  }

  // ---------------------------------------------------------------- Vorschau

  function stampDate() {
    return new Date().toLocaleDateString(LOCALE[lang] || "en-GB", { day: "2-digit", month: "2-digit", year: "2-digit" });
  }

  function updateBack() {
    const text = $("text").value.trim();
    const from = $("from").value.trim();
    const box = $("backText");
    box.classList.toggle("empty", !text);
    box.textContent = (text || t("empty")) + (from ? `\n— ${from}` : "");
    const mark = $("backMark");
    mark.textContent = "";
    const town = document.createElement("b");
    town.textContent = ($("city").value.trim() || t("stampTown")).slice(0, 18);
    mark.append(town, document.createElement("br"), document.createTextNode(stampDate()));
    $("count").textContent = String($("text").value.length);
  }

  function updateButton() {
    $("send").disabled = !photo;
  }

  function setStatus(text, error) {
    $("status").textContent = text || "";
    $("status").classList.toggle("error", !!error);
  }

  // ---------------------------------------------------------------- Senden

  function unb64url(text) {
    const s = text.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((text.length + 3) % 4);
    const bin = atob(s);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i += 1) out[i] = bin.charCodeAt(i);
    return out;
  }

  async function plainBytes() {
    const header = {
      v: 1, from: $("from").value.trim().slice(0, 40), city: $("city").value.trim().slice(0, 40),
      text: $("text").value.trim().slice(0, 300), sent: Date.now(), lang, w: photo.w, h: photo.h,
      tz: (Intl.DateTimeFormat().resolvedOptions().timeZone || "").slice(0, 40)
    };
    const head = new TextEncoder().encode(JSON.stringify(header));
    const jpeg = new Uint8Array(await photo.blob.arrayBuffer());
    const out = new Uint8Array(4 + head.length + jpeg.length);
    new DataView(out.buffer).setUint32(0, head.length, false);
    out.set(head, 4);
    out.set(jpeg, 4 + head.length);
    return out;
  }

  async function encrypt(plain) {
    const key = await crypto.subtle.importKey("raw", unb64url(link.key), { name: "AES-GCM" }, false, ["encrypt"]);
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const sealed = new Uint8Array(await crypto.subtle.encrypt(
      { name: "AES-GCM", iv, additionalData: new TextEncoder().encode("postcards1") }, key, plain));
    const out = new Uint8Array(4 + 12 + sealed.length);
    out.set(new TextEncoder().encode("PCv1"), 0);
    out.set(iv, 4);
    out.set(sealed, 16);
    return out;
  }

  async function sendRelay(plain) {
    const blob = await encrypt(plain);
    const url = `${link.server}/${encodeURIComponent(link.topic)}?filename=postcard.bin&message=${encodeURIComponent("Postcard")}`;
    const response = await fetch(url, { method: "PUT", body: blob, headers: { "Content-Type": "application/octet-stream" } });
    if (!response.ok) {
      let detail = `HTTP ${response.status}`;
      try { detail = (await response.json()).error || detail; } catch (_) { /* egal */ }
      throw new Error(detail);
    }
    const body = await response.json().catch(() => ({}));
    return body.id || "";
  }

  async function sendLan(plain) {
    const response = await fetch("./api/send", { method: "POST", body: plain, headers: { "Content-Type": "application/octet-stream" } });
    const body = await response.json().catch(() => ({}));
    if (!response.ok || !body.success) throw new Error(body.error || `HTTP ${response.status}`);
    return body;
  }

  async function waitForAck(id) {
    const until = Date.now() + 120000;
    while (Date.now() < until && !$("done").hidden) {
      await new Promise((r) => setTimeout(r, 4000));
      try {
        const response = await fetch(`${link.server}/${encodeURIComponent(link.topic)}/json?poll=1&since=${encodeURIComponent(id)}`, { cache: "no-store" });
        const text = await response.text();
        for (const line of text.split("\n")) {
          if (!line.trim()) continue;
          const msg = JSON.parse(line);
          if (msg.event === "message" && msg.message === ACK + id) return true;
        }
      } catch (_) { /* weiter probieren */ }
    }
    return false;
  }

  async function onSubmit(event) {
    event.preventDefault();
    if (!photo) { setStatus(t("needPhoto"), true); return; }
    store.set("from", $("from").value.trim());
    store.set("city", $("city").value.trim());
    $("send").disabled = true;
    setStatus(t("sending"));
    try {
      const plain = await plainBytes();
      if (mode === "relay") {
        const id = await sendRelay(plain);
        showDone(t("sent"), t("waitAck"));
        if (id) {
          const ok = await waitForAck(id);
          if (!$("done").hidden) {
            $("doneNote").textContent = ok ? t("arrived") : t("later");
            $("done").classList.toggle("arrived", ok);
          }
        } else {
          $("doneNote").textContent = t("later");
        }
      } else {
        const body = await sendLan(plain);
        showDone(t("lanDone"), body.waiting ? t("waiting") : "");
        $("done").classList.add("arrived");
      }
    } catch (error) {
      setStatus(t("failed", { e: error.message || String(error) }), true);
      updateButton();
    }
  }

  function showDone(title, note) {
    $("form").hidden = true;
    $("done").hidden = false;
    $("done").classList.remove("arrived");
    $("doneTitle").textContent = title;
    $("doneNote").textContent = note;
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function reset() {
    if (photo?.url) URL.revokeObjectURL(photo.url);
    photo = null;
    $("preview").hidden = true;
    $("preview").removeAttribute("src");
    $("pickEmpty").hidden = false;
    $("pick").classList.remove("has");
    $("again").hidden = true;
    $("text").value = "";
    setStatus("");
    updateBack();
    updateButton();
    $("done").hidden = true;
    $("form").hidden = false;
  }

  // ---------------------------------------------------------------- Start

  async function start() {
    $("from").value = store.get("from");
    $("city").value = store.get("city");
    if (mode === "relay") {
      if (!/^[A-Za-z0-9_-]{16,64}$/.test(link.topic) || unb64urlSafe(link.key) !== 32 || !/^(https:\/\/|http:\/\/(127\.0\.0\.1|localhost)[:/])/.test(link.server + "/")) {
        mode = "broken";
      } else if (!(window.crypto && crypto.subtle)) {
        applyTexts();
        $("broken").hidden = false;
        $("broken").querySelector("p").textContent = t("noCrypto");
        return;
      }
    } else {
      try {
        const response = await fetch("./api/info", { cache: "no-store" });
        lanInfo = await response.json();
        if (!lanInfo || !lanInfo.lan) throw new Error("no");
        if (!TEXT[browserLang] && TEXT[lanInfo.lang]) lang = lanInfo.lang;
      } catch (_) {
        mode = "broken";
      }
    }
    applyTexts();
    if (mode === "broken") { $("broken").hidden = false; return; }
    if (mode === "lan" && !lanInfo.open) { $("closed").hidden = false; return; }
    $("form").hidden = false;
    updateButton();
  }

  function unb64urlSafe(text) {
    try { return unb64url(text).length; } catch (_) { return 0; }
  }

  $("file").addEventListener("change", onFile);
  $("again").addEventListener("click", () => $("file").click());
  for (const id of ["text", "from", "city"]) $(id).addEventListener("input", updateBack);
  $("form").addEventListener("submit", onSubmit);
  $("another").addEventListener("click", reset);
  start();
})();
