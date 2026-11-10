"""Texte des Plugins auf Deutsch, Englisch und Spanisch.

Der deutsche Text ist zugleich der Schlüssel. t() sucht die Übersetzung in
der gewählten Sprache und füllt die Platzhalter; fehlt eine Übersetzung,
bleibt es beim deutschen Text.
"""

LANGUAGES = ("de", "en", "es")

_TEXTS = {
    "Dem API-Schlüssel fehlt eine Berechtigung ({path}).": (
        "The API key lacks a permission ({path}).",
        "A la clave API le falta un permiso ({path})."),
    "Der Rahmen hat die Playlist {name} nicht angelegt.": (
        "The frame did not create the playlist {name}.",
        "El marco no ha creado la lista {name}."),
    "Die Fotos werden neu eingelesen.": ("Reading the photos again.", "Volviendo a leer las fotos."),
    "Die Playlist gibt es nicht mehr.": ("That playlist no longer exists.", "Esa lista ya no existe."),
    "Die Playlist {name} gibt es schon.": ("The playlist {name} already exists.", "La lista {name} ya existe."),
    "Die Szene Foto Mosaik ist auf diesem Rahmen nicht installiert. Installiere das Paket noch einmal.": (
        "The Foto Mosaik scene is not installed on this frame. Install the package again.",
        "La escena Foto Mosaik no está instalada en este marco. Vuelve a instalar el paquete."),
    "Die Playlist {old} heißt jetzt {name}.": (
        "The playlist {old} is now called {name}.", "La lista {old} ahora se llama {name}."),
    "Deine Fotos, zusammengesetzt aus hunderten deiner Fotos.": (
        "Your photos, made of hundreds of your photos.",
        "Tus fotos, hechas de cientos de tus fotos."),
    "DynaFrame antwortet nicht: {exc}": ("DynaFrame does not answer: {exc}", "DynaFrame no responde: {exc}"),
    "Immich ist nicht erreichbar: {exc}": ("Immich cannot be reached: {exc}", "No se puede acceder a Immich: {exc}"),
    "Immich lehnt den API-Schlüssel ab.": ("Immich refuses the API key.", "Immich rechaza la clave API."),
    "Konnte die Playlist nicht anlegen: {exc}": (
        "Could not create the playlist: {exc}", "No se ha podido crear la lista: {exc}"),
    "Playlist {name} angelegt. Starte sie auf der Startseite des Rahmens oder nimm die Szene in eine andere Playlist auf.": (
        "Playlist {name} created. Start it on the frame's home page, or add the scene to another playlist.",
        "Lista {name} creada. Iníciala en la página principal del marco o añade la escena a otra lista."),
    "Trag die Adresse deines Immich-Servers ein.": (
        "Enter the address of your Immich server.", "Introduce la dirección de tu servidor Immich."),
    "Trag einen API-Schlüssel von Immich ein.": (
        "Enter an API key from Immich.", "Introduce una clave API de Immich."),
    "Unter dieser Adresse antwortet kein Immich-Server.": (
        "No Immich server answers at this address.", "Ningún servidor Immich responde en esta dirección."),
    "Verbunden als {user} (Immich {version}).": (
        "Connected as {user} (Immich {version}).", "Conectado como {user} (Immich {version})."),
    "Wähle ein Album.": ("Pick an album.", "Elige un álbum."),
    "Lade auf der Plugin-Seite mindestens ein Foto hoch.": (
        "Upload at least one photo on the plugin page.", "Sube al menos una foto en la página del plugin."),
    "Hak mindestens einen Ordner an.": ("Tick at least one folder.", "Marca al menos una carpeta."),
    "Dieses Immich kann nicht nach Text im Bild suchen.": (
        "This Immich cannot search for text in images.", "Este Immich no puede buscar texto en las imágenes."),
    "Die Datei ist leer.": ("The file is empty.", "El archivo está vacío."),
    "Die Datei ist zu groß.": ("The file is too large.", "El archivo es demasiado grande."),
    "Das ist kein Foto, das das Plugin lesen kann.": (
        "The plugin cannot read this file as a photo.", "El plugin no puede leer este archivo como foto."),
    "Adresse, Benutzer und Passwort fehlen noch.": (
        "Address, user and password are still missing.", "Faltan la dirección, el usuario y la contraseña."),
    "Verbunden. Motive kommen jetzt in voller Auflösung.": (
        "Connected. Motifs now come in full resolution.", "Conectado. Los motivos llegan ahora en resolución completa."),
    "Benutzer oder Passwort stimmt nicht (HTTP {status}).": (
        "User or password is wrong (HTTP {status}).", "El usuario o la contraseña no son correctos (HTTP {status})."),
    "Der Server antwortet mit HTTP {status}.": (
        "The server answers with HTTP {status}.", "El servidor responde con HTTP {status}."),
    "Wähle eine Playlist.": ("Pick a playlist.", "Elige una lista."),
}


def t(lang, template, **values):
    text = template
    if lang in LANGUAGES and lang != "de":
        row = _TEXTS.get(template)
        if row:
            text = row[LANGUAGES.index(lang) - 1]
    try:
        return text.format(**values) if values else text
    except (KeyError, IndexError, ValueError):
        return text
