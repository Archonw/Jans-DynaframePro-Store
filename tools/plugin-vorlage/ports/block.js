// Port-Block für Plugin-Seiten (tools/plugin-vorlage/ports). Eigene Texte DE/EN/ES.
// Einbau: HTML aus block.html (von apply_ui.py eingesetzt), <script src="./port_block.js"></script>
// vor studio.js, und in render(state): PortBlock.render(state.port, language).
// Speichert über POST ./api/port {"port": 8120 | ""}.
(function () {
  const T = {
    pbLabel: ["Port", "Port", "Puerto"],
    pbAuto: ["automatisch ({port})", "automatic ({port})", "automático ({port})"],
    pbHint: ["Leer lassen = automatisch: Ist der Port belegt, zum Beispiel von einem anderen Plugin, nimmt das Plugin den nächsten freien und zeigt ihn hier. Eine Zahl legt den Port fest. Ändert sich der Port, gilt der neue QR-Code; Kurzbefehle und Lesezeichen brauchen dann die neue Adresse.",
      "Leave empty = automatic: if the port is taken, for example by another plugin, the plugin uses the next free one and shows it here. A number fixes the port. If the port changes, the new QR code applies; shortcuts and bookmarks then need the new address.",
      "Vacío = automático: si el puerto está ocupado, por ejemplo por otro plugin, el plugin usa el siguiente libre y lo muestra aquí. Un número fija el puerto. Si el puerto cambia, vale el nuevo código QR; los atajos y marcadores necesitan entonces la nueva dirección."],
    pbRunning: ["Läuft auf Port {port}.", "Running on port {port}.", "Funciona en el puerto {port}."],
    pbMoved: ["Läuft auf Port {port} statt {default}.", "Running on port {port} instead of {default}.", "Funciona en el puerto {port} en lugar de {default}."],
    pbBusy: ["Port {list} war belegt.", "Port {list} was taken.", "El puerto {list} estaba ocupado."],
    pbBy: ["{port} von {who}", "{port} by {who}", "{port} por {who}"],
    pbManualBusy: ["Der festgelegte Port {manual} war belegt, darum vorübergehend {port}.", "The chosen port {manual} was taken, so {port} for now.", "El puerto elegido {manual} estaba ocupado, por eso {port} de momento."],
    pbNone: ["Kein freier Port gefunden, die Seite läuft nicht.", "No free port found, the page is not running.", "No hay puerto libre, la página no funciona."],
    pbBack: ["Zurück auf Port {default}", "Back to port {default}", "Volver al puerto {default}"],
    pbSaved: ["Gespeichert: Port {port}.", "Saved: port {port}.", "Guardado: puerto {port}."],
    pbWebLogin: ["Mit Web Login und strenger Firewall muss dieser Port freigegeben sein. Web Login zieht eine Freigabe mit, wenn das Plugin den Port wechselt.",
      "With Web Login and a strict firewall this port has to be allowed. Web Login moves the permission along when the plugin changes its port.",
      "Con Web Login y cortafuegos estricto este puerto debe estar permitido. Web Login traslada el permiso cuando el plugin cambia de puerto."],
  };
  const IDX = { de: 0, en: 1, es: 2 };
  let lang = "de";
  let applied = "";      // Sprache, in der die festen Texte gerade stehen
  let last = null;
  let message = "";
  const $ = (id) => document.getElementById(id);
  const t = (key, values = {}) => (T[key][IDX[lang] ?? 1]).replace(/\{(\w+)\}/g, (_m, k) => (values[k] ?? ""));

  function texts() {
    document.querySelectorAll("[data-pb]").forEach((node) => { node.textContent = t(node.dataset.pb); });
  }

  function render(status, language) {
    const root = $("portBlock");
    if (!root) return;
    if (language) lang = language;
    if (lang !== applied) { applied = lang; texts(); }
    if (!status) return;
    last = status;
    const input = $("pbInput");
    input.placeholder = t("pbAuto", { port: status.default });
    if (document.activeElement !== input) input.value = status.manual || "";
    const parts = [];
    if (!status.port) parts.push(t("pbNone"));
    else if (status.manualBusy) parts.push(t("pbManualBusy", { manual: status.manual, port: status.port }));
    else if (status.port !== status.default) parts.push(t("pbMoved", { port: status.port, default: status.default }));
    else parts.push(t("pbRunning", { port: status.port }));
    const busy = (status.busy || []).map((b) => (b.by ? t("pbBy", { port: b.port, who: b.by }) : String(b.port)));
    if (busy.length) parts.push(t("pbBusy", { list: busy.join(", ") }));
    const note = $("pbNote");
    note.textContent = message || parts.join(" ");
    note.className = "status" + (!status.port || status.manualBusy || (message && message.bad) ? " bad" : "");
    const back = $("pbBack");
    back.hidden = !status.port || status.port === status.default;
    back.textContent = t("pbBack", { default: status.default });
  }

  async function send(value) {
    try {
      const response = await fetch("./api/port", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ port: value }) });
      const result = await response.json();
      if (!result.success) {
        message = Object.assign(new String(result.error || "?"), { bad: true });
      } else {
        message = "";
        if (last) last = Object.assign({}, last, { port: result.port, manual: value ? Number(value) : null, manualBusy: false, busy: [] });
      }
    } catch (error) {
      message = Object.assign(new String(error.message), { bad: true });
    }
    render(last, lang);
    if (!message.bad) {
      const note = $("pbNote");
      if (last && last.port) note.textContent = t("pbSaved", { port: last.port });
    }
    setTimeout(() => { message = ""; }, 8000);
    if (typeof window.PortBlockChanged === "function") window.PortBlockChanged();
  }

  document.addEventListener("DOMContentLoaded", () => {
    const input = $("pbInput");
    if (!input) return;
    lang = (document.documentElement.lang || "de").slice(0, 2);
    input.addEventListener("change", () => send(input.value.trim()));
    $("pbBack").addEventListener("click", () => { input.value = ""; send(""); });
  });

  window.PortBlock = { render, texts: T };
})();
