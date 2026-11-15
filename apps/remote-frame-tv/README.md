# Remote Frame TV

Android TV / Fire TV app. It finds every DynaFrame on the home network by itself and shows the one you pick full screen, using DynaFrame's own browser view (`http://<frame>/RemoteFrame`).

- Search: asks every address of the TV's network for `/engine-proxy/sync/status` (like the Home Assistant integration) and listens to mDNS. Frames you opened before are remembered and checked first.
- Pick a frame with the remote and press OK. **Back** returns to the list.
- "Open last frame on start" (on by default): the app goes straight to the last frame.
- Long press OK (or the menu key) on a frame: remove it from the list.
- Frames with DynaFrame's WebUI security switched on: the app opens `https://<frame>/RemoteFrame`, DynaFrame shows its admin login once (user name + password with the remote's on-screen keyboard), the app keeps the session cookie and goes on to the frame view. DynaFrame has no viewer key, so after its session ends the login may appear again. The frame's own certificate (local DynaFrame CA) is accepted only for addresses in the home network.
- Remote frames must be switched on in the frame's settings (Settings → Remote frames); otherwise the page says "Remote frames disabled".
- Languages: German, English, Spanish (follows the TV's language).

## Install on a Fire TV Stick

1. Fire TV: Settings → My Fire TV → Developer options → "Install unknown apps": allow **Downloader** (install "Downloader" from the Amazon app store first). If Developer options are missing: Settings → My Fire TV → About → click the device name 7 times.
2. Open Downloader and enter the APK address of the latest release, currently
   `https://github.com/Archonw/Jans-DynaframePro-Store/releases/download/remote-frame-tv-0.1.3/RemoteFrameTV-0.1.3.apk`
3. Install, open. The app is listed under "Your apps & channels".

With adb instead: enable Developer options → ADB debugging, then `adb connect <TV-IP>:5555` and `adb install -r RemoteFrameTV-<version>.apk`.

## Install on Android TV / Google TV

Same as above with "Downloader" from the Play Store (or "Send files to TV"), or with adb. Allow "unknown sources" for the app you install from.

## Updates

Install the newer APK over the old one; saved frames and logins stay. All releases from 0.1.3 on are signed with the same private key (GitHub secret). 0.1.0–0.1.2 used another key: uninstall those once before installing 0.1.3.

## Build

GitHub Actions workflow `Remote Frame TV` builds the APK on every push to `apps/remote-frame-tv/` and creates the release `remote-frame-tv-<versionName>` for a new version (`version.properties`; raise `versionCode` too).
