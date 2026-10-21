/* WLAN für Gäste - ein Zusatzmodul für Dynaframe's Magic Mirror.
 * Nachbau von MMM-WiFiPassword (TeraTech, MIT). Den QR-Code rechnet
 * qrcode-generator (Kazuhiko Arase, MIT), das build.sh davor hängt; er wird
 * als SVG gezeichnet, damit er bei jeder Größe scharf bleibt. */
(function () {
  "use strict";
  const { esc, t } = window.MagicFrame.helpers;
  const TEXT = {
    network: { de: "Netzwerk", en: "Network", es: "Red" },
    password: { de: "Passwort", en: "Password", es: "Contraseña" },
    auth: { de: "Verschlüsselung", en: "Security", es: "Seguridad" },
    open: { de: "offen", en: "open", es: "abierta" },
    hint: { de: "Mit der Handykamera scannen", en: "Scan with your phone camera", es: "Escanea con la cámara del móvil" },
    missing: { de: "Trag Netzwerkname und Passwort ein.", en: "Enter network name and password.", es: "Introduce el nombre de la red y la contraseña." },
  };

  // Sonderzeichen im WIFI:-Text mit \ schützen (das Original konnte das nicht)
  const guard = (text) => String(text).replace(/([\;,:"])/g, "\\$1");

  function wifiText(c) {
    const auth = ["WPA", "WEP", "nopass"].includes(c.auth) ? c.auth : "WPA";
    let text = `WIFI:T:${auth};S:${guard(c.ssid)};`;
    if (auth !== "nopass") text += `P:${guard(c.password)};`;
    if (c.hidden) text += "H:true;";
    return text + ";";
  }

  function qrSvg(text) {
    const qr = qrcode(0, "M");
    qr.addData(text, "Byte");
    qr.make();
    const n = qr.getModuleCount();
    const quiet = 3;
    let path = "";
    for (let r = 0; r < n; r++) {
      for (let c = 0; c < n; c++) {
        if (qr.isDark(r, c)) path += `M${c + quiet},${r + quiet}h1v1h-1z`;
      }
    }
    const size = n + 2 * quiet;
    return `<svg viewBox="0 0 ${size} ${size}" shape-rendering="crispEdges" xmlns="http://www.w3.org/2000/svg">
      <rect width="${size}" height="${size}" fill="#fff"/><path d="${path}" fill="#000"/></svg>`;
  }

  window.MagicFrame.register("wifi", {
    render(el, ctx) {
      const c = ctx.config;
      if (!c.ssid || (c.auth !== "nopass" && !c.password)) {
        el.innerHTML = `<div class="xsmall dimmed">${esc(t(TEXT.missing))}</div>`;
        return true;
      }
      qrcode.stringToBytes = qrcode.stringToBytesFuncs["UTF-8"];
      let code;
      try { code = qrSvg(wifiText(c)); } catch (_) { code = ""; }
      const rows = [];
      if (c.showNetwork) rows.push([t(TEXT.network), c.ssid]);
      if (c.showPassword && c.auth !== "nopass") rows.push([t(TEXT.password), c.password]);
      if (c.showAuth) rows.push([t(TEXT.auth), c.auth === "nopass" ? t(TEXT.open) : c.auth]);
      const text = rows.map(([k, v]) => `<div class="wf-row"><span class="dimmed">${esc(k)}</span>
          <span class="bright wf-value">${esc(v)}</span></div>`).join("");
      el.innerHTML = `<div class="wf-box wf-${c.layout === "horizontal" ? "h" : "v"} wf-${esc(c.size || "medium")}">
          <div class="wf-qr">${code}</div>
          <div class="wf-text small">${text}
            ${c.showHint ? `<div class="xsmall dimmed wf-hint">${esc(t(TEXT.hint))}</div>` : ""}</div>
        </div>`;
    },
  });
})();
