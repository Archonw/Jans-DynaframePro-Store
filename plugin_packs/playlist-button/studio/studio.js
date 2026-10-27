"use strict";

// Immer "./api/...": die Weboberfläche liefert diese Seite unter
// /Plugins/Advanced/PlaylistButtonPlugin/ aus, ohne <base>.

const el = (id) => document.getElementById(id);
const NUMBER_FIELDS = ["LongPressSeconds", "OverlayTimeoutSeconds", "FolderCacheSeconds",
  "FontSize", "VisibleLines", "AnchorLine"];
const CHECK_FIELDS = ["OnlyEnabledPlaylists", "ShowFolderPlaylists"];
const TEXT_FIELDS = ["GpioPin", "OverlayFileName"];
let current = null;
let editing = false;

// Texte der Seite auf Deutsch, Englisch und Spanisch. Die Sprache gilt auch
// für das Menü auf dem Rahmen.
const I18N = {
  eyebrow: ["Plugin-Seite", "Plugin page", "Página del plugin"],
  lede: ["Ein Taster am Rahmen wählt die Playlist: kurz drücken öffnet das Menü und springt weiter, lang drücken startet die markierte Playlist. Jede Änderung hier wird sofort gespeichert.",
    "A button on the frame picks the playlist: a short press opens the menu and moves down, a long press starts the marked playlist. Every change here is saved immediately.",
    "Un pulsador en el marco elige la lista: una pulsación corta abre el menú y baja una línea, una larga inicia la lista marcada. Cada cambio aquí se guarda al instante."],
  language: ["Sprache", "Language", "Idioma"],
  status: ["Status", "Status", "Estado"],
  show: ["Menü zeigen", "Show menu", "Mostrar menú"],
  factButton: ["Taster", "Button", "Pulsador"],
  factMenu: ["Menü", "Menu", "Menú"],
  factVersion: ["Version", "Version", "Versión"],
  showHint: ["„Menü zeigen“ wirkt wie ein kurzer Tastendruck. So siehst du Farbe und Größe auch ohne Taster.",
    "“Show menu” works like a short press. This way you can check colour and size without the button.",
    "«Mostrar menú» funciona como una pulsación corta. Así ves el color y el tamaño sin el pulsador."],
  buttonTitle: ["Taster", "Button", "Pulsador"],
  gpioPin: ["GPIO-Pin (BCM-Nummer)", "GPIO pin (BCM number)", "Pin GPIO (número BCM)"],
  longPress: ["Langer Druck ab … Sekunden", "Long press from … seconds", "Pulsación larga desde … segundos"],
  timeout: ["Menü schließt nach … Sekunden ohne Druck", "Menu closes after … seconds without a press", "El menú se cierra tras … segundos sin pulsar"],
  gpioHint: ["Nimm einen Pin, den kein anderes Plugin und kein anderes Gerät benutzt. Der Taster verbindet den Pin mit GND.",
    "Pick a pin that no other plugin or device uses. The button connects the pin to GND.",
    "Elige un pin que no use ningún otro plugin ni dispositivo. El pulsador conecta el pin con GND."],
  listTitle: ["Playlisten im Menü", "Playlists in the menu", "Listas en el menú"],
  onlyEnabled: ["Nur eingeschaltete Playlisten zeigen", "Only show playlists that are switched on", "Mostrar solo las listas activadas"],
  showFolders: ["Ordner-Playlisten auch zeigen", "Also show folder playlists", "Mostrar también las listas de carpetas"],
  folderCache: ["Ordnerliste merken für … Sekunden", "Remember the folder list for … seconds", "Recordar la lista de carpetas durante … segundos"],
  folderHint: ["Je länger die Ordnerliste gemerkt wird, desto schneller öffnet das Menü. Neue Ordner erscheinen dann erst nach dieser Zeit.",
    "The longer the folder list is remembered, the faster the menu opens. New folders then only appear after that time.",
    "Cuanto más tiempo se recuerde la lista, más rápido se abre el menú. Las carpetas nuevas aparecen pasado ese tiempo."],
  lookTitle: ["Aussehen", "Appearance", "Aspecto"],
  fontSize: ["Schriftgröße (px)", "Font size (px)", "Tamaño de letra (px)"],
  visibleLines: ["Sichtbare Zeilen", "Visible lines", "Líneas visibles"],
  anchorLine: ["Markierung bleibt in Zeile", "Marker stays in line", "El marcador se queda en la línea"],
  bgColor: ["Hintergrundfarbe", "Background colour", "Color de fondo"],
  bgOpacity: ["Deckkraft des Hintergrunds", "Background opacity", "Opacidad del fondo"],
  opacityHint: ["0 % ist unsichtbar, 100 % ist deckend. Bei etwa 50 bis 70 % scheint das Foto leicht durch.",
    "0 % is invisible, 100 % is solid. At about 50 to 70 % the photo shines through slightly.",
    "0 % es invisible, 100 % es opaco. Con un 50 a 70 % la foto se transparenta un poco."],
  advancedTitle: ["Erweitert", "Advanced", "Avanzado"],
  overlayFile: ["Overlay-Datei", "Overlay file", "Archivo de overlay"],
  overlayHint: ["Das Plugin legt dieses Overlay selbst an. Die Position des Menüs kannst du in der Weboberfläche unter Overlays verschieben; sie bleibt erhalten.",
    "The plugin creates this overlay itself. You can move the menu in the web interface under Overlays; the position is kept.",
    "El plugin crea este overlay él mismo. Puedes mover el menú en la interfaz web en Overlays; la posición se mantiene."],
  noPin: ["Kein Pin eingetragen", "No pin set", "Ningún pin"],
  ready: ["Bereit auf GPIO{pin}", "Ready on GPIO{pin}", "Listo en GPIO{pin}"],
  busy: ["GPIO{pin} ist belegt", "GPIO{pin} is taken", "GPIO{pin} está ocupado"],
  starting: ["Startet …", "Starting …", "Iniciando …"],
  menuOpen: ["Offen", "Open", "Abierto"],
  menuClosed: ["Geschlossen", "Closed", "Cerrado"],
  more: ["weitere", "more", "más"],
  active: ["aktiv", "active", "activa"],
  noAnswer: ["Das Plugin antwortet nicht – vermutlich wurde es neu gestartet. Lade die Seite neu.",
    "The plugin is not responding – it was probably restarted. Reload the page.",
    "El plugin no responde; probablemente se ha reiniciado. Recarga la página."],
  restarted: ["Das Plugin wurde neu gestartet (HTTP {status}). Lade die Seite neu.",
    "The plugin was restarted (HTTP {status}). Reload the page.",
    "El plugin se ha reiniciado (HTTP {status}). Recarga la página."],
  error: ["Fehler (HTTP {status})", "Error (HTTP {status})", "Error (HTTP {status})"],
  saved: ["Gespeichert.", "Saved.", "Guardado."],
  shown: ["Menü geöffnet bzw. eine Zeile weiter.", "Menu opened or moved one line down.", "Menú abierto o una línea más abajo."],
  badColor: ["Bitte einen Hex-Code wie #1E3A8A eingeben.", "Please enter a hex code such as #1E3A8A.", "Introduce un código hex como #1E3A8A."],
  supportAsk: ["Probleme, Fragen oder Wünsche?", "Problems, questions or feature requests?", "¿Problemas, preguntas o sugerencias?"],
  supportLink: ["Schreib ein Issue auf GitHub", "Open an issue on GitHub", "Abre una incidencia en GitHub"],
  supportTail: [", mit Plugin-Name und Version.", " with the plugin name and version.", " con el nombre y la versión del plugin."],
  back: ["← Zurück zu DynaFrame", "← Back to DynaFrame", "← Volver a DynaFrame"]
};
const LANGS = ["de", "en", "es"];
const SAMPLE = ["Familie", "Garten", "Herbst 2026", "Kunst", "Urlaub Italien", "Weihnachten", "Zoo"];
let lang = "de";

function t(key, values = {}) {
  const row = I18N[key];
  const text = row ? (row[LANGS.indexOf(lang)] ?? row[0]) : key;
  return text.replace(/\{(\w+)\}/g, (_, name) => String(values[name] ?? ""));
}

function applyLanguage(next) {
  const chosen = LANGS.includes(next) ? next : "de";
  if (chosen === lang && document.documentElement.lang === chosen) return;
  lang = chosen;
  document.documentElement.lang = lang;
  for (const node of document.querySelectorAll("[data-i18n]")) node.textContent = t(node.dataset.i18n);
}

async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(path, { headers: { Accept: "application/json", "Content-Type": "application/json" }, ...options });
  } catch (_) {
    throw new Error(t("noAnswer"));
  }
  if ([502, 503, 504].includes(response.status)) {
    throw new Error(t("restarted", { status: response.status }));
  }
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.success === false) throw new Error(payload.error || t("error", { status: response.status }));
  return payload;
}

function setStatus(text, tone = "") {
  const node = el("statusNote");
  node.textContent = text;
  node.className = `status${tone ? " " + tone : ""}`;
}

function applyTheme(theme) {
  const id = (theme && theme.id) || "";
  const root = document.documentElement;
  const tag = document.getElementById("frameTheme");
  if (!tag || (root.dataset.theme || "") === id) return;
  tag.textContent = id ? `@import url("/themes/${id}/theme.css") layer(frame-theme);` : "";
  if (id) root.dataset.theme = id;
  else delete root.dataset.theme;
}

async function save(name, value) {
  try {
    await api("./api/settings", { method: "POST", body: JSON.stringify({ [name]: value }) });
    setStatus(t("saved"), "ok");
    await refresh();
  } catch (error) {
    setStatus(error.message, "bad");
  }
}

function buttonText(code) {
  if (!code) return t("starting");
  if (code === "nopin") return t("noPin");
  const [kind, pin] = code.split(":");
  if (kind === "ready") return t("ready", { pin });
  if (kind === "busy") return t("busy", { pin });
  return code;
}

function hexToRgb(hex) {
  const value = /^#([0-9a-f]{6})$/i.exec(hex || "") ? hex.slice(1) : "000000";
  return [0, 2, 4].map((i) => parseInt(value.slice(i, i + 2), 16));
}

// Die Vorschau zeigt das Menü in halber Größe, ungefähr so wie auf dem Rahmen.
function renderPreview() {
  if (!current) return;
  const color = el("BackgroundColor").value;
  const opacity = Number(el("BackgroundOpacity").value);
  const fontSize = Number(el("FontSize").value) || 32;
  const lines = Math.max(1, Math.min(Number(el("VisibleLines").value) || 8, SAMPLE.length));
  const [r, g, b] = hexToRgb(color);
  const box = el("previewBox");
  box.style.background = `rgba(${r}, ${g}, ${b}, ${opacity / 100})`;
  box.style.fontSize = `${Math.max(9, Math.round(fontSize / 2))}px`;
  const text = [];
  for (let i = 0; i < lines; i++) {
    const marker = i === 1 ? "➤ " : "   ";
    const suffix = i === 3 ? `  (${t("active")})` : "";
    text.push(`${marker}${SAMPLE[i]}${suffix}`);
  }
  if (lines < SAMPLE.length) text.push(`   ↓ ${SAMPLE.length - lines} ${t("more")}`);
  box.textContent = text.join("\n");
  el("opacityValue").textContent = `${opacity} %`;
}

function render(state) {
  current = state;
  applyTheme(state.theme);
  const values = state.settings;
  applyLanguage(values.Language);
  el("Language").value = values.Language;
  el("factButton").textContent = buttonText(state.button);
  el("factButton").className = state.buttonOk ? "" : "warn";
  el("factMenu").textContent = state.menuVisible ? t("menuOpen") : t("menuClosed");
  el("factVersion").textContent = state.version || "—";
  if (!editing) {
    for (const name of [...NUMBER_FIELDS, ...TEXT_FIELDS]) el(name).value = values[name];
    el("BackgroundColor").value = values.BackgroundColor.toLowerCase();
    el("BackgroundColorText").value = values.BackgroundColor;
    el("BackgroundOpacity").value = values.BackgroundOpacity;
  }
  for (const name of CHECK_FIELDS) el(name).checked = !!values[name];
  el("FolderCacheSeconds").disabled = !values.ShowFolderPlaylists;
  renderPreview();
}

async function refresh() {
  try {
    render(await api("./api/state"));
  } catch (error) {
    setStatus(error.message, "bad");
  }
}

function trackEditing(input) {
  input.addEventListener("focus", () => { editing = true; });
  input.addEventListener("blur", () => { editing = false; });
}

for (const name of NUMBER_FIELDS) {
  const input = el(name);
  trackEditing(input);
  input.addEventListener("input", renderPreview);
  input.addEventListener("change", () => save(name, Number(input.value)));
}
for (const name of TEXT_FIELDS) {
  const input = el(name);
  trackEditing(input);
  input.addEventListener("change", () => save(name, input.value.trim()));
}
for (const name of CHECK_FIELDS) el(name).addEventListener("change", (e) => save(name, e.target.checked));

const colorPicker = el("BackgroundColor");
const colorText = el("BackgroundColorText");
trackEditing(colorPicker);
trackEditing(colorText);
colorPicker.addEventListener("input", () => {
  colorText.value = colorPicker.value.toUpperCase();
  renderPreview();
});
colorPicker.addEventListener("change", () => save("BackgroundColor", colorPicker.value));
colorText.addEventListener("change", () => {
  let value = colorText.value.trim();
  if (!value.startsWith("#")) value = `#${value}`;
  if (/^#[0-9a-f]{3}$/i.test(value)) value = `#${[...value.slice(1)].map((c) => c + c).join("")}`;
  if (!/^#[0-9a-f]{6}$/i.test(value)) {
    setStatus(t("badColor"), "bad");
    return;
  }
  colorPicker.value = value.toLowerCase();
  renderPreview();
  save("BackgroundColor", value);
});

const opacity = el("BackgroundOpacity");
trackEditing(opacity);
opacity.addEventListener("input", renderPreview);
opacity.addEventListener("change", () => save("BackgroundOpacity", Number(opacity.value)));

el("Language").addEventListener("change", (e) => {
  applyLanguage(e.target.value);
  renderPreview();
  save("Language", e.target.value);
});

el("showButton").addEventListener("click", async () => {
  try {
    await api("./api/show", { method: "POST" });
    setStatus(t("shown"), "ok");
    setTimeout(refresh, 1500);
  } catch (error) {
    setStatus(error.message, "bad");
  }
});

refresh();
setInterval(refresh, 5000);
