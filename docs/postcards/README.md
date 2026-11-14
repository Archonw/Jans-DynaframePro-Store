# Postcards: send page

The page family and friends open from a Postcards link (plugin "Postcards" for DynaFrame).
Served by GitHub Pages at https://archonw.github.io/Jans-DynaframePro-Store/postcards/.

The part of the link after `#` (relay topic and key) never leaves the browser. The photo and
greeting are encrypted here with AES-256-GCM and handed to the ntfy relay; only the frame can
open them. The same files ship inside the plugin (`plugin/send/`) for the Wi-Fi send page, so
keep both copies identical.
