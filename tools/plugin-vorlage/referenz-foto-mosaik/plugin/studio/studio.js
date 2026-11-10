"use strict";

// Immer "./api/...": die Weboberfläche liefert diese Seite unter
// /Plugins/Advanced/PhotoMosaic/ aus, ohne <base>.

const el = (id) => document.getElementById(id);
const NUMBER_FIELDS = ["MaxTiles", "ColorBlend", "Ghost", "RefreshHours", "PlaylistSeconds", "PauseSeconds", "TourTiles", "LastDays", "MinMegapixels", "MinFileKB"];
const CHECK_FIELDS = ["Captions", "ShowCount", "OnThisDay", "WithPeople", "CameraOnly", "NoScreenshots", "NotInAlbum"];
const SELECT_FIELDS = ["Tiles", "Flow", "Tempo", "MotifOrder", "Orientation"];
const FILTER_TEXT = ["City", "State", "Country", "TakenAfter", "TakenBefore", "Make", "Model", "Lens", "Description", "OcrText", "FileName", "SkipNames"];
const TEXT_FIELDS = ["ServerUrl", "Folders", "WebDavUrl", "WebDavUser"].concat(FILTER_TEXT);
// Listen zum Anhaken in den Immich-Filtern: Einstellung -> Liste
const PICKERS = { People: "people", SkipAlbums: "immich_album", SkipTags: "tags" };
const SOURCES = ["Tile", "Motif"];
let current = null;
let editing = false;
const lists = { playlist: null, immich_album: null, folders: null, people: null, tags: null };
const listErrors = { playlist: "", immich_album: "", folders: "", people: "", tags: "" };
const LIST_API = { playlist: ["./api/playlists", "playlists"], immich_album: ["./api/albums", "albums"], folders: ["./api/folders", "folders"], people: ["./api/people", "people"], tags: ["./api/tags", "tags"] };

const I18N = {
  eyebrow: ["Plugin-Seite", "Plugin page", "Página del plugin"],
  name: ["Foto Mosaik", "Foto Mosaik", "Foto Mosaik"],
  lede: ["Eines deiner Fotos, zusammengesetzt aus hunderten deiner eigenen Fotos. Die Kamera fährt langsam auf einzelne Kacheln zu, die dabei zum echten Foto werden. Jede Änderung hier wird sofort gespeichert.",
    "One of your photos, made of hundreds of your own photos. The camera slowly glides towards single tiles, which turn into the real photo. Every change here is saved immediately.",
    "Una de tus fotos, hecha con cientos de tus propias fotos. La cámara se acerca despacio a teselas sueltas, que se convierten en la foto real. Cada cambio aquí se guarda al instante."],
  language: ["Sprache", "Language", "Idioma"],
  status: ["Status", "Status", "Estado"],
  refresh: ["Fotos neu einlesen", "Read photos again", "Volver a leer las fotos"],
  playlist: ["Playlist anlegen", "Create playlist", "Crear lista"],
  factNow: ["Gerade", "Now", "Ahora"],
  factTiles: ["Kacheln", "Tiles", "Teselas"],
  factMotifs: ["Motive", "Motifs", "Motivos"],
  factRead: ["Zuletzt eingelesen", "Last read", "Última lectura"],
  factVersion: ["Version", "Version", "Versión"],
  nowIdle: ["Bereit", "Ready", "Listo"],
  nowList: ["Liest die Fotoliste", "Reading the photo list", "Leyendo la lista de fotos"],
  nowTiles: ["Macht Kacheln: {a} von {b}", "Making tiles: {a} of {b}", "Creando teselas: {a} de {b}"],
  nowSheets: ["Legt die Kachelbögen an", "Packing the tile sheets", "Preparando las hojas de teselas"],
  tilesTitle: ["Kacheln", "Tiles", "Teselas"],
  tilesHint: ["Aus diesen Fotos werden die kleinen Kacheln. Je mehr verschiedene Farben, desto besser wird das Mosaik.",
    "These photos become the small tiles. The more different colours, the better the mosaic.",
    "Estas fotos se convierten en las teselas pequeñas. Cuantos más colores distintos, mejor el mosaico."],
  motifsTitle: ["Motive", "Motifs", "Motivos"],
  motifsHint: ["Diese Fotos werden als Mosaik nachgebaut.", "These photos are rebuilt as a mosaic.", "Estas fotos se recrean como mosaico."],
  source: ["Quelle", "Source", "Fuente"],
  kindSame: ["Dieselben Fotos wie die Kacheln", "The same photos as the tiles", "Las mismas fotos que las teselas"],
  kindLibrary: ["Alle Fotos in DynaFrame", "All photos in DynaFrame", "Todas las fotos de DynaFrame"],
  kindPlaylist: ["Ausgewählte Playlists von DynaFrame", "Chosen DynaFrame playlists", "Listas elegidas de DynaFrame"],
  kindFolders: ["Ausgewählte Ordner in DynaFrame", "Chosen folders in DynaFrame", "Carpetas elegidas de DynaFrame"],
  kindUpload: ["Eigene Fotos, hier hochgeladen", "My own photos, uploaded here", "Mis fotos, subidas aquí"],
  playlistFilter: ["Playlist suchen …", "Search playlist …", "Buscar lista …"],
  folderFilter: ["Ordner suchen …", "Search folder …", "Buscar carpeta …"],
  noPlaylists: ["In DynaFrame gibt es keine Playlists.", "There are no playlists in DynaFrame.", "No hay listas en DynaFrame."],
  noFolders: ["DynaFrame kennt keine Fotos.", "DynaFrame knows no photos.", "DynaFrame no conoce fotos."],
  playlistNone: ["Hak mindestens eine Playlist an.", "Tick at least one playlist.", "Marca al menos una lista."],
  folderNone: ["Hak mindestens einen Ordner an.", "Tick at least one folder.", "Marca al menos una carpeta."],
  oneChosen: ["1 ausgewählt", "1 ticked", "1 marcado"],
  manyChosen: ["{n} ausgewählt", "{n} ticked", "{n} marcados"],
  uploadCount: ["{n} eigene Fotos", "{n} own photos", "{n} fotos propias"],
  uploadNone: ["Noch kein Foto hochgeladen.", "No photo uploaded yet.", "Todavía no has subido ninguna foto."],
  uploadPick: ["Fotos auswählen …", "Choose photos …", "Elegir fotos …"],
  uploadHint: ["Diese Fotos werden aus den Kacheln nachgebaut, immer wieder im Wechsel. Tipp: Mit „Klassisch“ kommt das Mosaik nach dem Zoom zu deinem Foto zurück, „Endlos“ taucht weiter in die Kacheln ein.",
    "These photos are rebuilt from the tiles, taking turns. Tip: with “Classic” the mosaic comes back to your photo after the zoom, “Endless” keeps diving into the tiles.",
    "Estas fotos se reconstruyen con las teselas, por turnos. Consejo: con “Clásico” el mosaico vuelve a tu foto tras el zoom, “Sin fin” sigue entrando en las teselas."],
  uploading: ["Lädt hoch … {a}/{b}", "Uploading … {a}/{b}", "Subiendo … {a}/{b}"],
  uploaded: ["Hochgeladen.", "Uploaded.", "Subidas."],
  remove: ["Entfernen", "Remove", "Quitar"],
  kindImmichAll: ["Alle Fotos in Immich", "All photos in Immich", "Todas las fotos de Immich"],
  kindImmichAlbum: ["Ausgewählte Alben in Immich", "Chosen albums in Immich", "Álbumes elegidos de Immich"],
  albumFilter: ["Album suchen …", "Search album …", "Buscar álbum …"],
  noAlbums: ["In Immich gibt es keine Alben.", "There are no albums in Immich.", "No hay álbumes en Immich."],
  albumsChosen: ["{n} Alben ausgewählt", "{n} albums ticked", "{n} álbumes marcados"],
  albumChosen: ["1 Album ausgewählt", "1 album ticked", "1 álbum marcado"],
  albumNone: ["Hak mindestens ein Album an (auch geteilte).", "Tick at least one album (shared ones too).", "Marca al menos un álbum (también compartidos)."],
  filterTitle: ["Welche Fotos aus Immich", "Which photos from Immich", "Qué fotos de Immich"],
  filterHint: ["Gilt für Kacheln und Motive aus Immich. Nach einer Änderung liest das Plugin die Fotos neu ein.",
    "Applies to tiles and motifs from Immich. After a change the plugin reads the photos again.",
    "Se aplica a las teselas y motivos de Immich. Tras un cambio el plugin vuelve a leer las fotos."],
  minRating: ["Sterne", "Stars", "Estrellas"],
  ratingAny: ["Egal", "Any", "Da igual"],
  rating1: ["Mindestens 1 Stern", "At least 1 star", "Al menos 1 estrella"],
  rating2: ["Mindestens 2 Sterne", "At least 2 stars", "Al menos 2 estrellas"],
  rating3: ["Mindestens 3 Sterne", "At least 3 stars", "Al menos 3 estrellas"],
  rating4: ["Mindestens 4 Sterne", "At least 4 stars", "Al menos 4 estrellas"],
  rating5: ["5 Sterne", "5 stars", "5 estrellas"],
  favoritesOnly: ["Favoriten", "Favourites", "Favoritos"],
  grpWhat: ["Was", "What", "Qué"],
  grpWho: ["Wer", "Who", "Quién"],
  grpWhere: ["Wo", "Where", "Dónde"],
  grpWhen: ["Wann", "When", "Cuándo"],
  grpCamera: ["Kamera", "Camera", "Cámara"],
  grpText: ["Text", "Text", "Texto"],
  grpJunk: ["Aussortieren", "Skip the junk", "Descartar"],
  grpSkip: ["Weglassen", "Leave out", "Excluir"],
  orientation: ["Ausrichtung", "Orientation", "Orientación"],
  landscape: ["Querformat", "Landscape", "Horizontal"],
  portrait: ["Hochformat", "Portrait", "Vertical"],
  squareShape: ["Quadratisch", "Square", "Cuadrada"],
  peopleHint: ["Keine angehakt: egal wer. Sonst nur Fotos, auf denen mindestens eine dieser Personen ist (aus der Gesichtserkennung von Immich).",
    "None ticked: anyone. Otherwise only photos with at least one of these people (from Immich's face recognition).",
    "Ninguna marcada: cualquiera. Si no, solo fotos con al menos una de estas personas (del reconocimiento facial de Immich)."],
  peopleFilter: ["Person suchen …", "Search person …", "Buscar persona …"],
  tagFilter: ["Tag suchen …", "Search tag …", "Buscar etiqueta …"],
  nothingHere: ["Keine gefunden.", "None found.", "No se encontró ninguno."],
  city: ["Stadt", "City", "Ciudad"],
  state: ["Bundesland", "State or province", "Estado o provincia"],
  country: ["Land", "Country", "País"],
  onThisDay: ["An diesem Tag: dasselbe Datum in früheren Jahren", "On this day: the same date in earlier years", "Este día: la misma fecha en años anteriores"],
  lastDays: ["Nur die letzten … Tage (0 = aus)", "Only the last … days (0 = off)", "Solo los últimos … días (0 = desactivado)"],
  takenAfter: ["Aufgenommen ab", "Taken after", "Tomada desde"],
  takenBefore: ["Aufgenommen bis", "Taken before", "Tomada hasta"],
  make: ["Hersteller", "Make", "Marca"],
  model: ["Modell", "Model", "Modelo"],
  lens: ["Objektiv", "Lens", "Objetivo"],
  description: ["Beschreibung enthält", "Description contains", "La descripción contiene"],
  ocrText: ["Text im Bild enthält", "Text in the image contains", "El texto de la imagen contiene"],
  fileName: ["Dateiname enthält", "File name contains", "El nombre del archivo contiene"],
  withPeople: ["Nur Fotos mit Personen", "Only photos with people in them", "Solo fotos con personas"],
  cameraOnly: ["Nur Fotos aus einer Kamera (ohne Screenshots und gespeicherte Bilder)", "Only photos taken with a camera (skips screenshots and saved images)", "Solo fotos de una cámara (sin capturas ni imágenes guardadas)"],
  noScreenshots: ["Dateinamen weglassen, die nach Bildschirmfoto aussehen", "Skip file names that look like screenshots", "Omitir nombres de archivo que parecen capturas"],
  notInAlbum: ["Nur Fotos, die in keinem Album sind", "Only photos that are not in any album", "Solo fotos que no están en ningún álbum"],
  minMegapixels: ["Mindestens … Megapixel", "At least … megapixels", "Al menos … megapíxeles"],
  minFileKB: ["Mindestens … KB Dateigröße", "File size at least … KB", "Tamaño de archivo de al menos … KB"],
  skipHint: ["Ein weggelassenes Album lässt alles darin weg, auch wenn es woanders noch vorkommt.", "Leaving out an album leaves out everything in it, wherever else it turns up.", "Excluir un álbum excluye todo lo que contiene, aunque aparezca en otro sitio."],
  skipAlbums: ["Alben weglassen", "Albums to leave out", "Álbumes a excluir"],
  skipTags: ["Tags weglassen", "Tags to leave out", "Etiquetas a excluir"],
  skipNames: ["Dateinamen weglassen (mit Komma getrennt)", "File names to leave out (separate with commas)", "Nombres de archivo a excluir (separados por comas)"],
  favAll: ["Alle Fotos", "All photos", "Todas las fotos"],
  favOnly: ["Nur Favoriten", "Only favourites", "Solo favoritos"],
  archived: ["Archivierte Fotos", "Archived photos", "Fotos archivadas"],
  archNo: ["Weglassen", "Leave out", "Excluir"],
  archYes: ["Auch verwenden", "Use them too", "Usarlas también"],
  pickPlaylist: ["Playlist", "Playlist", "Lista"],
  pickAlbum: ["Album", "Album", "Álbum"],
  pick: ["Bitte wählen …", "Please pick …", "Elige …"],
  loading: ["Lädt …", "Loading …", "Cargando …"],
  srcOk: ["{n} Fotos gefunden.", "{n} photos found.", "{n} fotos encontradas."],
  srcEmpty: ["Keine Fotos gefunden.", "No photos found.", "No se han encontrado fotos."],
  lookTitle: ["Mosaik", "Mosaic", "Mosaico"],
  tiles: ["Kacheln an der langen Seite", "Tiles along the long side", "Teselas en el lado largo"],
  tiles40: ["40 (grob)", "40 (coarse)", "40 (grueso)"],
  tiles60: ["60", "60", "60"],
  tiles80: ["80 (empfohlen)", "80 (recommended)", "80 (recomendado)"],
  tiles100: ["100", "100", "100"],
  tiles130: ["130 (sehr fein)", "130 (very fine)", "130 (muy fino)"],
  maxTiles: ["Höchstens so viele verschiedene Kacheln", "At most this many different tiles", "Como máximo tantas teselas distintas"],
  colorBlend: ["Kacheln zur Farbe tönen (%)", "Tint tiles towards the colour (%)", "Teñir teselas hacia el color (%)"],
  ghost: ["Original durchscheinen lassen (%)", "Let the original show through (%)", "Dejar ver el original (%)"],
  flow: ["Ablauf", "Flow", "Secuencia"],
  flowClassic: ["Klassisch: zur Kachel und zurück", "Classic: to a tile and back", "Clásica: a una tesela y de vuelta"],
  flowEndless: ["Endlos: in die Kachel hinein", "Endless: dive into the tile", "Infinita: entrar en la tesela"],
  flowTour: ["Rundgang: rein, raus, nächste Kachel", "Tour: in, out, next tile", "Recorrido: entrar, salir, otra tesela"],
  pauseSeconds: ["Pause zwischen den Kacheln (Sekunden)", "Pause between tiles (seconds)", "Pausa entre teselas (segundos)"],
  tourTiles: ["Kacheln je Motiv (0 = beim Motiv bleiben)", "Tiles per motif (0 = stay with the motif)", "Teselas por motivo (0 = quedarse en el motivo)"],
  tempo: ["Tempo", "Pace", "Ritmo"],
  tempoSlow: ["Gemächlich", "Leisurely", "Pausado"],
  tempoNormal: ["Normal", "Normal", "Normal"],
  tempoFast: ["Zügig", "Brisk", "Rápido"],
  motifOrder: ["Reihenfolge der Motive", "Order of the motifs", "Orden de los motivos"],
  orderRandom: ["Zufällig", "Random", "Aleatorio"],
  orderNewest: ["Die neuesten Fotos", "The newest photos", "Las fotos más recientes"],
  orderThisDay: ["Heute vor … Jahren", "On this day … years ago", "Tal día como hoy hace … años"],
  captions: ["Datum und Ort einblenden", "Show date and place", "Mostrar fecha y lugar"],
  showCount: ["„Aus … eigenen Fotos“ einblenden", "Show “Made of … of your photos”", "Mostrar “Hecho con … de tus fotos”"],
  lookHint: ["Mehr Kacheln an der langen Seite zeigen das Motiv genauer, jede einzelne Kachel ist dann aber kleiner. Tönen und Durchscheinen machen das Motiv deutlicher, sehen bei hohen Werten aber weniger nach echten Fotos aus.",
    "More tiles along the long side show the motif in more detail, but each tile gets smaller. Tinting and showing through make the motif clearer, but high values look less like real photos.",
    "Más teselas en el lado largo muestran el motivo con más detalle, pero cada tesela es más pequeña. Teñir y dejar ver el original hacen el motivo más claro, pero con valores altos parece menos fotos reales."],
  refreshHours: ["Neue Fotos suchen alle … Stunden", "Look for new photos every … hours", "Buscar fotos nuevas cada … horas"],
  playlistSeconds: ["Dauer in der Playlist (Sekunden)", "Duration in the playlist (seconds)", "Duración en la lista (segundos)"],
  serverTitle: ["Immich-Server", "Immich server", "Servidor Immich"],
  serverHint: ["Nur nötig, wenn Kacheln oder Motive von Immich kommen.", "Only needed if tiles or motifs come from Immich.", "Solo hace falta si las teselas o los motivos vienen de Immich."],
  serverUrl: ["Adresse", "Address", "Dirección"],
  apiKey: ["API-Schlüssel", "API key", "Clave API"],
  keySaved: ["gespeichert (leer lassen zum Behalten)", "saved (leave empty to keep)", "guardada (deja vacío para mantenerla)"],
  keyMissing: ["noch keiner", "none yet", "ninguna todavía"],
  test: ["Verbindung testen", "Test connection", "Probar conexión"],
  testing: ["Teste …", "Testing …", "Probando …"],
  keyHow: ["So bekommst du einen API-Schlüssel", "How to get an API key", "Cómo obtener una clave API"],
  keyHint: ["In Immich oben rechts auf dein Profilbild, dann <b>Kontoeinstellungen &gt; API-Schlüssel &gt; Neuer API-Schlüssel</b>. Als Berechtigung reichen <code>asset.read</code>, <code>asset.view</code> und <code>album.read</code>; mit <b>Alle</b> geht es auch. Der Schlüssel bleibt im Plugin auf dem Rahmen.",
    "In Immich click your profile picture at the top right, then <b>Account Settings &gt; API Keys &gt; New API Key</b>. The permissions <code>asset.read</code>, <code>asset.view</code> and <code>album.read</code> are enough; <b>All</b> works too. The key stays in the plugin on the frame.",
    "En Immich pulsa tu foto de perfil arriba a la derecha y luego <b>Ajustes de la cuenta &gt; Claves API &gt; Nueva clave API</b>. Bastan los permisos <code>asset.read</code>, <code>asset.view</code> y <code>album.read</code>; con <b>Todos</b> también funciona. La clave se queda en el plugin del marco."],
  davTitle: ["Volle Auflösung für WebDAV-Fotos", "Full resolution for WebDAV photos", "Resolución completa para fotos WebDAV"],
  davHint: ["Fotos aus einer WebDAV-Quelle (z. B. Nextcloud) gibt DynaFrame an Plugins nur als kleines Vorschaubild weiter. Mit eigenen Zugangsdaten lädt das Plugin für Motive und die Zoom-Kachel das Original. Freiwillig; ohne bleibt es beim Vorschaubild.",
    "DynaFrame only hands photos from a WebDAV source (e.g. Nextcloud) to plugins as a small preview. With its own login the plugin loads the original for motifs and the zoom tile. Optional; without it the preview is used.",
    "DynaFrame solo pasa a los plugins las fotos de una fuente WebDAV (p. ej. Nextcloud) como una vista previa pequeña. Con sus propios datos de acceso el plugin carga el original para los motivos y la tesela del zoom. Opcional; sin ellos se usa la vista previa."],
  davUrl: ["WebDAV-Adresse", "WebDAV address", "Dirección WebDAV"],
  davUser: ["Benutzer", "User", "Usuario"],
  davPassword: ["App-Passwort", "App password", "Contraseña de aplicación"],
  davHow: ["So bekommst du ein App-Passwort", "How to get an app password", "Cómo obtener una contraseña de aplicación"],
  davHowText: ["In Nextcloud oben rechts auf dein Profilbild, dann <b>Persönliche Einstellungen &gt; Sicherheit &gt; Neues App-Passwort erstellen</b>. Adresse und Benutzer sind dieselben wie in DynaFrame unter WebDAV. Das Passwort bleibt im Plugin auf dem Rahmen.",
    "In Nextcloud click your profile picture at the top right, then <b>Personal settings &gt; Security &gt; Create new app password</b>. Address and user are the same as in DynaFrame under WebDAV. The password stays in the plugin on the frame.",
    "En Nextcloud pulsa tu foto de perfil arriba a la derecha y luego <b>Configuración personal &gt; Seguridad &gt; Crear nueva contraseña de aplicación</b>. La dirección y el usuario son los mismos que en DynaFrame en WebDAV. La contraseña se queda en el plugin del marco."],
  foldersTitle: ["Weitere Ordner auf dem Rahmen", "More folders on the frame", "Más carpetas en el marco"],
  foldersHint: ["Für „Alle Fotos in DynaFrame“: Das Plugin fragt DynaFrame nach seiner Mediendatenbank und den Medienordnern. Liegen Fotos woanders (z. B. ein eingehängtes NAS), trag die Ordner hier ein, einen pro Zeile.",
    "For “All photos in DynaFrame”: the plugin asks DynaFrame for its media library and media folders. If photos are somewhere else (e.g. a mounted NAS), enter the folders here, one per line.",
    "Para “Todas las fotos de DynaFrame”: el plugin pide a DynaFrame su biblioteca y sus carpetas. Si hay fotos en otro sitio (p. ej. un NAS montado), escribe aquí las carpetas, una por línea."],
  noAnswer: ["Das Plugin antwortet nicht.", "The plugin does not answer.", "El plugin no responde."],
  restarted: ["Das Plugin startet gerade neu (HTTP {status}).", "The plugin is restarting (HTTP {status}).", "El plugin se está reiniciando (HTTP {status})."],
  error: ["Fehler (HTTP {status})", "Error (HTTP {status})", "Error (HTTP {status})"],
  oclock: ["{time} Uhr", "{time}", "{time}"],
  saved: ["Gespeichert.", "Saved.", "Guardado."],
  playlistTitle: ["Eine Playlist dafür", "A playlist for it", "Una lista para ello"],
  makePlaylist: ["Playlist „Foto Mosaik“ anlegen", "Create the playlist “Foto Mosaik”", "Crear la lista «Foto Mosaik»"],
  no: ["Nein", "No", "No"],
  yesCreate: ["Ja, anlegen", "Yes, create it for me", "Sí, créala"],
  playlistHint: ["Die Playlist enthält nur die Szene und ist eingeschaltet. Die Dauer gilt beim Anlegen; danach änderst du sie in der Playlist selbst. Du kannst die Szene auch selbst in jede Playlist aufnehmen.",
    "The playlist holds only the scene and is switched on. The duration applies when it is created; after that you change it in the playlist itself. You can also add the scene to any playlist yourself.",
    "La lista contiene solo la escena y está activada. La duración se aplica al crearla; después la cambias en la propia lista. También puedes añadir la escena a cualquier lista."],
  supportAsk: ["Probleme, Fragen oder Wünsche?", "Problems, questions or feature requests?", "¿Problemas, preguntas o sugerencias?"],
  supportLink: ["Schreib ein Issue auf GitHub", "Open an issue on GitHub", "Abre una incidencia en GitHub"],
  supportTail: [", mit Plugin-Name und Version.", " with the plugin name and version.", " con el nombre y la versión del plugin."],
};
const LANGS = ["de", "en", "es"];
const LOCALES = { de: "de-DE", en: "en-GB", es: "es-ES" };
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
  for (const node of document.querySelectorAll("[data-i18n-html]")) node.innerHTML = t(node.dataset.i18nHtml);
  for (const node of document.querySelectorAll("[data-i18n-placeholder]")) node.placeholder = t(node.dataset.i18nPlaceholder);
  if (current) {
    for (const prefix of SOURCES) renderRef(prefix, current.settings, true);
    renderPickers(current.settings);
  }
}

async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(path, { headers: { Accept: "application/json", "Content-Type": "application/json" }, ...options });
  } catch (_) {
    throw new Error(t("noAnswer"));
  }
  if ([503, 504].includes(response.status)) throw new Error(t("restarted", { status: response.status }));
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.success === false) throw new Error(payload.error || t("error", { status: response.status }));
  return payload;
}

function setStatus(text, tone = "", id = "statusNote") {
  const node = el(id);
  node.textContent = text;
  node.className = `status${tone ? " " + tone : ""}`;
}

function clock(epoch) {
  if (!epoch) return "—";
  const date = new Date(epoch * 1000);
  const sameDay = date.toDateString() === new Date().toDateString();
  const locale = LOCALES[lang];
  const time = t("oclock", { time: date.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" }) });
  return sameDay ? time : `${date.toLocaleDateString(locale, { day: "2-digit", month: "2-digit" })} ${time}`;
}

const esc = (text) => String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const fmt = (n) => Number(n || 0).toLocaleString(LOCALES[lang]);

function applyTheme(theme) {
  const id = (theme && theme.id) || "";
  const root = document.documentElement;
  const tag = document.getElementById("frameTheme");
  if (!tag || (root.dataset.theme || "") === id) return;
  tag.textContent = id ? `@import url("/themes/${id}/theme.css") layer(frame-theme);` : "";
  if (id) root.dataset.theme = id;
  else delete root.dataset.theme;
}

async function save(changes) {
  try {
    const result = await api("./api/settings", { method: "POST", body: JSON.stringify(changes) });
    setStatus(t("saved"), "ok");
    await refresh();
    return result.changed || [];
  } catch (error) {
    setStatus(error.message, "bad");
    return [];
  }
}

// ------------------------------------------------------------ Quellen

async function loadList(kind, force = false) {
  if (lists[kind] && !force) return;
  try {
    const result = await api(LIST_API[kind][0]);
    if (result.success === false) throw new Error(result.error || "?");
    lists[kind] = result[LIST_API[kind][1]] || [];
    listErrors[kind] = "";
  } catch (error) {
    lists[kind] = [];
    listErrors[kind] = error.message;
  }
  if (current) {
    for (const prefix of SOURCES) renderRef(prefix, current.settings, true);
    renderPickers(current.settings);
  }
}

// Playlists, Alben und Ordner: alle als Liste zum Anhaken
function chosenItems(prefix, s) {
  const kind = s[prefix + "Kind"];
  if (kind === "folders") return (s[prefix + "Dirs"] || "").split("\n").filter(Boolean);
  return (s[prefix + "Ref"] || "").split(",").filter(Boolean);
}

function saveChosen(prefix, ids) {
  const kind = current.settings[prefix + "Kind"];
  return save(kind === "folders" ? { [prefix + "Dirs"]: ids.join("\n") } : { [prefix + "Ref"]: ids.join(",") });
}

function renderChecks(prefix, s, listKind) {
  const items = lists[listKind];
  const box = el(prefix + "AlbumList");
  el(prefix + "AlbumFilter").placeholder = t(listKind === "playlist" ? "playlistFilter" : listKind === "folders" ? "folderFilter" : "albumFilter");
  if (!items) {
    box.innerHTML = `<p class="hint">${esc(t("loading"))}</p>`;
    box.dataset.html = "";
    loadList(listKind);
    return;
  }
  const chosen = new Set(chosenItems(prefix, s));
  const query = el(prefix + "AlbumFilter").value.trim().toLowerCase();
  // Angehaktes zuerst, damit es in einer langen Liste sichtbar bleibt
  const rows = items.filter((a) => !query || String(a.name).toLowerCase().includes(query))
    .sort((a, b) => (chosen.has(String(b.id)) - chosen.has(String(a.id))) || String(a.name).localeCompare(String(b.name)));
  const html = rows.map((a) => `<label title="${esc(a.name)}"><input type="checkbox" value="${esc(String(a.id))}" ${chosen.has(String(a.id)) ? "checked" : ""}>
      <span class="name">${esc(a.name)}</span>${a.count != null ? `<span class="count">${fmt(a.count)}</span>` : ""}</label>`).join("");
  if (box.dataset.html !== html) { box.innerHTML = html; box.dataset.html = html; }
  if (listErrors[listKind]) setStatus(listErrors[listKind], "bad", prefix + "Note");
  else if (!items.length) setStatus(t(listKind === "playlist" ? "noPlaylists" : listKind === "folders" ? "noFolders" : "noAlbums"), "warn", prefix + "Note");
}

function renderPickers(s) {
  for (const [name, listKind] of Object.entries(PICKERS)) {
    const items = lists[listKind];
    const box = el(name + "List");
    if (!items) {
      if (s.ServerUrl) loadList(listKind);
      continue;
    }
    const chosen = new Set((s[name] || "").split(",").filter(Boolean));
    const query = el(name + "Filter").value.trim().toLowerCase();
    // Lange Listen: angehakte und gesuchte zuerst, höchstens 200 zeigen
    const rows = items.filter((a) => chosen.has(String(a.id)) || !query || String(a.name).toLowerCase().includes(query))
      .sort((a, b) => (chosen.has(String(b.id)) - chosen.has(String(a.id))) || String(a.name).localeCompare(String(b.name)))
      .slice(0, Math.max(200, chosen.size));
    const html = rows.map((a) => `<label title="${esc(a.name)}"><input type="checkbox" value="${esc(String(a.id))}" ${chosen.has(String(a.id)) ? "checked" : ""}>
        <span class="name">${esc(a.name)}</span>${a.count != null ? `<span class="count">${fmt(a.count)}</span>` : ""}</label>`).join("");
    if (box.dataset.html !== html) { box.innerHTML = html; box.dataset.html = html; }
    const note = listErrors[listKind] || (!items.length ? t("nothingHere") : chosen.size ? t(chosen.size === 1 ? "oneChosen" : "manyChosen", { n: chosen.size }) : "");
    setStatus(note, listErrors[listKind] ? "bad" : "", name + "Note");
  }
}

function chosenNote(prefix, s) {
  const n = chosenItems(prefix, s).length;
  return n === 1 ? t("oneChosen") : n ? t("manyChosen", { n }) : "";
}

function renderRef(prefix, s) {
  const kind = s[prefix + "Kind"];
  const listKind = ["playlist", "immich_album", "folders"].includes(kind) ? kind : "";
  el(prefix + "RefField").hidden = true;
  el(prefix + "Albums").hidden = !listKind;
  if (prefix === "Motif") el("MotifUpload").hidden = kind !== "upload";
  if (listKind) renderChecks(prefix, s, listKind);
}

function sourceNote(prefix, state) {
  const key = prefix === "Tile" ? "tiles" : "motifs";
  const row = (state.status || {})[key] || {};
  if (prefix === "Motif" && state.settings.MotifKind === "same") {
    setStatus("", "", prefix + "Note");
    return;
  }
  const kind = state.settings[prefix + "Kind"];
  const listKind = ["playlist", "immich_album", "folders"].includes(kind) ? kind : "";
  const albums = listKind ? chosenNote(prefix, state.settings) : "";
  if (listKind && !albums) setStatus(t(kind === "playlist" ? "playlistNone" : kind === "folders" ? "folderNone" : "albumNone"), "warn", prefix + "Note");
  else if (listKind && listErrors[listKind]) setStatus(listErrors[listKind], "bad", prefix + "Note");
  else if (kind === "upload") setStatus(row.total ? t("uploadCount", { n: fmt(row.total) }) : t("uploadNone"), row.total ? "ok" : "warn", prefix + "Note");
  else if (row.state === "error") setStatus(row.error, "bad", prefix + "Note");
  else if (row.state === "ok") setStatus((albums ? albums + " · " : "") + (row.total ? t("srcOk", { n: fmt(row.total) }) : t("srcEmpty")), row.total ? "ok" : "warn", prefix + "Note");
  else if (row.state === "empty") setStatus(t("srcEmpty"), "warn", prefix + "Note");
  else setStatus("", "", prefix + "Note");
}

// ------------------------------------------------------------ Stand

function render(state) {
  current = state;
  applyTheme(state.theme);
  const s = state.settings;
  applyLanguage(s.Language);
  const p = state.progress || {};
  el("factNow").textContent = !state.busy ? t("nowIdle") : p.phase === "tiles" ? t("nowTiles", { a: fmt(p.done), b: fmt(p.total) })
    : p.phase === "sheets" ? t("nowSheets") : t("nowList");
  el("factTiles").textContent = state.tiles ? fmt(state.tiles) : "—";
  el("factMotifs").textContent = state.motifs ? fmt(state.motifs) : "—";
  el("factRead").textContent = clock(state.at);
  el("factVersion").textContent = state.version;
  if (document.activeElement !== el("MakePlaylist")) el("MakePlaylist").value = String(Boolean(state.settings.MakePlaylist));
  el("playlistNote").textContent = state.ownPlaylist || "";
  el("issueLink").href = "https://github.com/Archonw/Jans-DynaframePro-Store/issues/new?title=" +
    encodeURIComponent(`[Foto Mosaik ${state.version}] `);
  if (!editing) {
    for (const name of NUMBER_FIELDS.concat(TEXT_FIELDS)) {
      if (document.activeElement !== el(name)) el(name).value = s[name];
    }
    for (const name of CHECK_FIELDS) el(name).checked = Boolean(s[name]);
    for (const name of SELECT_FIELDS) el(name).value = s[name];
    el("MinRating").value = String(s.MinRating);
    for (const node of document.querySelectorAll(".tour-only")) node.hidden = s.Flow !== "tour";
    renderPickers(s);
    el("FavoritesOnly").value = String(Boolean(s.FavoritesOnly));
    el("IncludeArchived").value = String(Boolean(s.IncludeArchived));
    for (const prefix of SOURCES) el(prefix + "Kind").value = s[prefix + "Kind"];
    el("Language").value = lang;
    if (document.activeElement !== el("ApiKey")) {
      el("ApiKey").placeholder = state.secretsSet.ApiKey ? t("keySaved") : t("keyMissing");
    }
    if (document.activeElement !== el("WebDavPassword")) {
      el("WebDavPassword").placeholder = state.secretsSet.WebDavPassword ? t("keySaved") : t("keyMissing");
    }
    // Adresse und Benutzer der WebDAV-Quelle von DynaFrame als Vorschlag
    const guess = state.webdav || {};
    if (guess.url) el("WebDavUrl").placeholder = guess.url;
    if (guess.user) el("WebDavUser").placeholder = guess.user;
  }
  for (const prefix of SOURCES) {
    if (document.activeElement !== el(prefix + "Ref")) renderRef(prefix, s);
    sourceNote(prefix, state);
  }
}

async function refresh() {
  try {
    render(await api("./api/state"));
  } catch (error) {
    setStatus(error.message, "bad");
  }
}

for (const name of NUMBER_FIELDS.concat(TEXT_FIELDS, ["ApiKey", "WebDavPassword"])) {
  const input = el(name);
  input.addEventListener("focus", () => { editing = true; });
  input.addEventListener("blur", () => { editing = false; });
}
for (const name of NUMBER_FIELDS) el(name).addEventListener("change", (e) => save({ [name]: Number(e.target.value) }));
for (const name of CHECK_FIELDS) el(name).addEventListener("change", (e) => save({ [name]: e.target.checked }));
for (const name of SELECT_FIELDS) el(name).addEventListener("change", (e) => save({ [name]: e.target.value }));
for (const prefix of SOURCES) {
  el(prefix + "Kind").addEventListener("change", (e) => {
    el(prefix + "AlbumFilter").value = "";
    if (e.target.value === "folders") loadList("folders", true);
    save({ [prefix + "Kind"]: e.target.value, [prefix + "Ref"]: "" });
  });
}
for (const prefix of SOURCES) {
  el(prefix + "AlbumFilter").addEventListener("input", () => current && renderRef(prefix, current.settings));
  el(prefix + "AlbumList").addEventListener("change", () => {
    const list = el(prefix + "AlbumList");
    const ticked = [...list.querySelectorAll("input:checked")].map((box) => box.value);
    // Angehakte Alben behalten, die der Suchfilter gerade ausblendet
    const hidden = chosenItems(prefix, current.settings).filter((id) => !list.querySelector(`input[value="${CSS.escape(id)}"]`));
    saveChosen(prefix, [...hidden, ...ticked]);
  });
}
el("MinRating").addEventListener("change", (e) => save({ MinRating: Number(e.target.value) }));
for (const name of FILTER_TEXT) el(name).addEventListener("change", (e) => save({ [name]: e.target.value }));
for (const name of Object.keys(PICKERS)) {
  el(name + "Filter").addEventListener("input", () => current && renderPickers(current.settings));
  el(name + "List").addEventListener("change", () => {
    const list = el(name + "List");
    const ticked = [...list.querySelectorAll("input:checked")].map((box) => box.value);
    const hidden = (current.settings[name] || "").split(",").filter(Boolean)
      .filter((id) => !list.querySelector(`input[value="${CSS.escape(id)}"]`));
    save({ [name]: [...hidden, ...ticked].join(",") });
  });
}
for (const name of ["FavoritesOnly", "IncludeArchived"]) {
  el(name).addEventListener("change", (e) => save({ [name]: e.target.value === "true" }));
}
el("Folders").addEventListener("change", (e) => save({ Folders: e.target.value }));
el("Language").addEventListener("change", (e) => {
  applyLanguage(e.target.value);
  save({ Language: e.target.value });
});

async function saveServer() {
  const changes = { ServerUrl: el("ServerUrl").value };
  const key = el("ApiKey").value.trim();
  if (key) changes.ApiKey = key;
  const changed = await save(changes);
  el("ApiKey").value = "";
  if (changed.includes("ServerUrl") || changed.includes("ApiKey")) await testConnection();
}

async function testConnection() {
  setStatus(t("testing"), "busy", "testNote");
  try {
    const result = await api("./api/test", { method: "POST" });
    setStatus(result.message, result.ok ? "ok" : "bad", "testNote");
    if (result.ok) for (const kind of ["immich_album", "people", "tags"]) loadList(kind, true);
  } catch (error) {
    setStatus(error.message, "bad", "testNote");
  }
}

async function saveDav() {
  const guess = current?.webdav || {};
  const changes = {
    WebDavUrl: el("WebDavUrl").value.trim() || (el("WebDavPassword").value.trim() ? guess.url || "" : ""),
    WebDavUser: el("WebDavUser").value.trim() || (el("WebDavPassword").value.trim() ? guess.user || "" : ""),
  };
  const key = el("WebDavPassword").value.trim();
  if (key) changes.WebDavPassword = key;
  const changed = await save(changes);
  el("WebDavPassword").value = "";
  if (changed.length) await testDav();
}

async function testDav() {
  setStatus(t("testing"), "busy", "davNote");
  try {
    const result = await api("./api/webdavtest", { method: "POST" });
    setStatus(result.message, result.ok ? "ok" : "bad", "davNote");
  } catch (error) {
    setStatus(error.message, "bad", "davNote");
  }
}

for (const name of ["WebDavUrl", "WebDavUser", "WebDavPassword"]) el(name).addEventListener("change", saveDav);
el("davTestButton").addEventListener("click", async () => {
  const s = current?.settings || {};
  if (el("WebDavPassword").value.trim() || el("WebDavUrl").value !== (s.WebDavUrl || "") ||
      el("WebDavUser").value !== (s.WebDavUser || "")) await saveDav();
  else await testDav();
});

el("ServerUrl").addEventListener("change", saveServer);
el("ApiKey").addEventListener("change", saveServer);
el("testButton").addEventListener("click", async () => {
  if (el("ApiKey").value.trim() || el("ServerUrl").value !== (current?.settings.ServerUrl || "")) await saveServer();
  else await testConnection();
});
el("refreshButton").addEventListener("click", async () => {
  try {
    const result = await api("./api/refresh", { method: "POST" });
    setStatus(result.message || "", "busy");
    setTimeout(refresh, 1500);
  } catch (error) {
    setStatus(error.message, "bad");
  }
});
el("MakePlaylist").addEventListener("change", (e) => save({ MakePlaylist: e.target.value === "true" }));

refresh();
setInterval(refresh, 4000);

// ------------------------------------------------------------ Eigene Motive

async function loadUploads() {
  try {
    const result = await api("./api/uploads");
    const box = el("uploadList");
    box.innerHTML = (result.uploads || []).map((u) => `<figure class="upload">
        <img src="./api/upload?id=${u.id}" alt="" loading="lazy">
        <button type="button" class="remove" data-id="${u.id}" title="${esc(t("remove"))}" aria-label="${esc(t("remove"))}">×</button>
        <figcaption>${esc(u.name || "")}</figcaption></figure>`).join("");
  } catch (error) {
    setStatus(error.message, "bad", "uploadNote");
  }
}

// Im Browser auf höchstens 3200 px verkleinern: geht schneller übers WLAN.
// Kann der Browser das Bild nicht lesen (z. B. HEIC), geht die Datei unverändert.
async function shrink(file) {
  try {
    const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
    const scale = Math.min(1, 3200 / Math.max(bitmap.width, bitmap.height));
    if (scale === 1 && file.type === "image/jpeg" && file.size < 8e6) return file;
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    return await new Promise((resolve) => canvas.toBlob((blob) => resolve(blob || file), "image/jpeg", 0.9));
  } catch (_) {
    return file;
  }
}

el("uploadInput").addEventListener("change", async (e) => {
  const files = [...e.target.files];
  e.target.value = "";
  let done = 0;
  let failed = "";
  for (const file of files) {
    setStatus(t("uploading", { a: done + 1, b: files.length }), "busy", "uploadNote");
    try {
      // Bei JPEGs liest das Plugin das Aufnahmedatum aus dem Original
      const body = file.type === "image/jpeg" && file.size < 12e6 ? file : await shrink(file);
      const response = await fetch("./api/upload", { method: "POST", body, headers: { "X-File-Name": encodeURIComponent(file.name) } });
      const result = await response.json().catch(() => ({ success: false, error: `HTTP ${response.status}` }));
      if (!result.success) failed = `${file.name}: ${result.error || "?"}`;
      else done += 1;
    } catch (error) {
      failed = `${file.name}: ${error.message}`;
    }
  }
  setStatus(failed || t("uploaded"), failed ? "bad" : "ok", "uploadNote");
  await loadUploads();
  refresh();
});

el("uploadList").addEventListener("click", async (e) => {
  const button = e.target.closest("button.remove");
  if (!button) return;
  await api("./api/upload/delete", { method: "POST", body: JSON.stringify({ id: button.dataset.id }) });
  await loadUploads();
  refresh();
});

loadUploads();
