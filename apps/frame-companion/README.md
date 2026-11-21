# Frame Companion

Android phone app for DynaFrame. It finds the frames in your home network by itself and makes the everyday things one tap away:

- **Send photos and videos**: pick several at once in the app, or select them in your gallery and use **Share → "Show on DynaFrame"**. The upload runs in the background with a progress notification; you can leave the app right away. Large videos are sent in pieces and resume after a Wi-Fi hiccup (DynaFrame's own resumable upload, the same one its Upload page uses).
- **Show right away** (on by default): the sent files appear on the frame at once; afterwards the frame goes back to its playlist.
- Files land in the folder **Phone Uploads** under the frame's Pictures folder (created automatically). Another folder or a new one can be chosen in the app.
- **Control**: the picture on the frame as large artwork (eye button switches the preview off to save data, i shows details), title and playlist, progress with times, shuffle / previous / play-pause / next / screen on-off, volume with mute. Hold play-pause to stop.
- **Playlists**: switches like on the web page's "Choose Playlist", a gold button plays the switched-on ones mixed, the play icon plays just one; search and All / Recent / Plugins (the plugins' own takeover playlists).
- **Photo sources** (Send tab → "Set up photo sources", or menu ⚙): tick where your photos are. What DynaFrame does itself is set up in the app with its own web UI routes: network drive / NAS over SMB (`/Nas/Discover`, `SaveCredentials`, `Map`, `BrowseExternalChildren`, `RegisterExternalFolders`), Nextcloud/ownCloud/WebDAV (`/WebDav/Test`, `Save`, `Children`, `Folders`, with the page's antiforgery token) and USB drives (`/Upload/DetectUsbDrives`, `/Nas/ConnectUsbSource`). For the rest (Immich, iCloud, Google Drive/OneDrive/Dropbox, Telegram) the app looks through all stores the frame knows (`/Store/GetStores`, `/Store/GetCatalog`), installs the plugin like the Store page does (`/Store/DownloadAndInstallPlugin` or `…Dynamic`, then `/Store/MarkPackInstalled`) and opens its settings page (`/Plugins/Advanced/<name>/`) inside the app.
- **Settings** (Control → Settings): time per picture, transition and its length, shuffle or order (file name, folder, date taken), overlays, how photos and videos fill the screen (original, fill/crop, whole picture, stretch, Ken Burns), several photos at once, video sound, play videos to the end, repeat short videos, live photos. Same engine calls as the web UI (`/settings/slideshow`, `/display/fitmode`, `/transition`).
- **More** tab: the frame at a glance (device, DynaFrame version, address, temperature, storage, library, update available → install), Plugins (switch on/off, settings page, restart; `/Plugins/GetPlugins`, engine `/plugins/<name>/enable|disable|restart`), Store (all stores the frame knows, install and update), restart DynaFrame / frame, shut down, and every other web UI page (current playlist, new playlist, media, overlays, automations, NFC, cast, sync, screen, audio, network, backup, Home Assistant, time zone, help) opened inside the app.
- **Finding frames** also works over VPN/Tailscale or mobile data: the app searches the network of every saved frame and asks logged-in frames which frames they know.
- Look ("glass", 0.5.0): the picture on the frame, blurred, behind every screen; frosted cards, iOS-style switches, a floating tab bar Send / Control / Playlists / Sources / More, DynaFrame's gold accent. Fonts: Inter (SIL OFL 1.1, `assets/Inter-*.otf`, subset to Latin); icons: Bootstrap Icons (MIT, `assets/bootstrap-icons.ttf`).
- Languages: German, English, Spanish (follows the phone).

## Frames with DynaFrame's own login (HTTPS)

When DynaFrame's WebUI login is switched on, the app needs a key once:

1. In DynaFrame's web page: **Settings → Security → Frame API Key**, scope **Full REST**, choose how many days it is valid.
2. In the app, tap the frame (it shows "login needed") and paste the key. The app then talks HTTPS only and sends the key as `Authorization: Bearer …`.
3. Alternatively enter DynaFrame's user name and password; the app signs in like the browser does.

The frame signs its HTTPS certificate itself. The app remembers the certificate the first time ("trust on first use") and asks before it accepts a different one. Key, password and certificate are stored only in the app's private storage (no backup).

## Install

Download the APK from the release (`frame-companion-<version>`, or always the newest: `releases/download/frame-companion-latest/FrameCompanion.apk`) on the phone and open it. Android asks once to allow installing from your browser or file manager. Android 7 or newer.

Updates: install the newer APK over the old one; saved frames and keys stay. The APK is signed with the same key as Remote Frame TV (GitHub secrets `RFTV_KEYSTORE_B64`, `RFTV_KEYSTORE_PASSWORD`).

## How it works (for developers)

- Search: every address of the phone's /24 network is asked for `/engine-proxy/sync/status` (like Remote Frame TV and the Home Assistant integration), plus mDNS hosts; a redirect to `/Connect` or 401 means "frame with login".
- Engine calls go through `/engine-proxy/…` on port 80 (no login) or 443 (login, with key).
- Upload: `POST /Upload/ResumableSessions` → `PUT …/{id}/Chunks` (raw bytes, `X-Upload-Offset`, 409 returns the right offset) → `POST …/{id}/Complete`; folders via `/Upload/GetDirectChildDirectories` and `/Upload/CreateFolder`.
- Show now: `POST /engine-proxy/playback/play-now` with the uploaded files; if that fails, `POST /Upload/PlayFolderNow`.
- Plain Java, no libraries, package `de.archonw.framecompanion`.

## Build

GitHub Actions workflow `Frame Companion` builds the APK on every push to `apps/frame-companion/` and creates the release `frame-companion-<versionName>` for a new version (`version.properties`; raise `versionCode` too).
