package de.archonw.framecompanion;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URLEncoder;
import java.util.ArrayList;
import java.util.List;

/**
 * What the app asks a frame. Engine calls go through the web page's /engine-proxy/
 * (works with and without DynaFrame's login; with the login on only over HTTPS with an
 * API key). Uploads use the same resumable upload as DynaFrame's own Upload page.
 */
final class Api {

    final Frame f;
    final Http http;

    Api(Frame f) {
        this.f = f;
        this.http = new Http(f);
    }

    interface Call<T> { T run() throws IOException; }

    /** Runs c; when the frame asks for a login and a user name + password are saved, signs in once and retries. */
    <T> T with(Call<T> c) throws IOException {
        try {
            return c.run();
        } catch (Http.AuthException ex) {
            if (f.user == null || f.user.isEmpty() || f.password == null || !f.https) throw ex;
            http.login(f.user, f.password);
            return c.run();
        }
    }

    private String e(String p) { return "/engine-proxy" + p; }

    /** After a successful https call: remember the certificate the first time. */
    boolean pinIfNew() {
        if (f.https && (f.fingerprint == null || f.fingerprint.isEmpty()) && http.seenFingerprint != null) {
            f.fingerprint = http.seenFingerprint;
            return true;
        }
        return false;
    }

    // ------------------------------------------------------------------ info & control

    JSONObject info() throws IOException { return http.obj("GET", e("/sync/info"), null); }

    JSONObject status() throws IOException { return http.obj("GET", e("/slideshow/status?includeCurrentItem=true"), null); }

    /** Switches every playlist off and stops playback (web UI "Choose Playlist" with nothing selected). */
    void stopAll() throws IOException {
        try { http.call("POST", e("/playlists/disable-all-and-stop"), null); }
        catch (IOException ex) { if (ex instanceof Http.AuthException) throw ex; transport("stop"); }
    }

    void transport(String what) throws IOException { http.call("POST", e("/slideshow/" + what), null); }

    /** "on", "off" or "" when the display does not say. */
    String displayPower() {
        try {
            JSONObject o = http.obj("GET", e("/display/power"), null);
            String s = o.optString("state", o.optString("power", ""));
            if (s.isEmpty() && o.has("isOn")) s = o.optBoolean("isOn") ? "on" : "off";
            return s.toLowerCase();
        } catch (IOException ex) {
            return "";
        }
    }

    void setDisplay(boolean on) throws IOException {
        http.call("POST", e("/display/power"), new JSONObjectBuilder().put("state", on ? "on" : "off").put("source", "frame-companion").o);
    }

    int volume() {
        try {
            JSONObject o = http.obj("GET", e("/api/v1/system/volume"), null);
            if (o.has("value")) return o.optInt("value", -1);
            if (o.has("volume")) return o.optInt("volume", -1);
            return -1;
        } catch (IOException ex) {
            return -1;
        }
    }

    void setVolume(int v) throws IOException {
        http.call("POST", e("/api/v1/system/volume"), new JSONObjectBuilder().put("value", v).o);
    }

    List<JSONObject> playlists() throws IOException {
        JSONArray a = http.arr("GET", e("/playlists"), null);
        List<JSONObject> out = new ArrayList<>();
        for (int i = 0; i < a.length(); i++) {
            JSONObject o = a.optJSONObject(i);
            // Hide the runtime "quick mix" playlists the frame makes itself (like the HA integration).
            if (o != null && o.has("id") && !o.optString("description", "").contains("\"quick_mix\"")) out.add(o);
        }
        return out;
    }

    /** Ids of the saved playlists the frame is playing now (one or a mix). */
    java.util.Set<Integer> activePlaylists() {
        java.util.Set<Integer> out = new java.util.HashSet<>();
        try {
            JSONObject o = http.obj("GET", e("/playback-selection/state"), null);
            if (o.optInt("savedPlaylistId", 0) > 0) { out.add(o.optInt("savedPlaylistId")); return out; }
            JSONObject q = o.optJSONObject("quickMixState");
            JSONArray ids = q == null ? null : q.optJSONArray("enabledSavedPlaylistIds");
            if (ids != null) for (int i = 0; i < ids.length(); i++) out.add(ids.optInt(i));
        } catch (IOException ignored) {
        }
        return out;
    }

    /** Plays one saved playlist, the same way the frame's playlist page (and the HA integration) does it. */
    void startPlaylist(int id, String name) throws IOException {
        startPlaylists(java.util.Collections.singletonList(id), name);
    }

    /** Keys of what plays now: "pl:<id>", "f:<folder path>", "p:<plugin name>" (the web page's Quick Mix switches). */
    java.util.Set<String> activeSources() {
        java.util.Set<String> out = new java.util.HashSet<>();
        try {
            JSONObject o = http.obj("GET", e("/playback-selection/state"), null);
            if (o.optInt("savedPlaylistId", 0) > 0) { out.add("pl:" + o.optInt("savedPlaylistId")); return out; }
            JSONObject q = o.optJSONObject("quickMixState");
            if (q == null) q = o.optJSONObject("QuickMixState");
            if (q == null) return out;
            JSONArray ids = q.optJSONArray("enabledSavedPlaylistIds");
            if (ids != null) for (int i = 0; i < ids.length(); i++) out.add("pl:" + ids.optInt(i));
            JSONArray fo = q.optJSONArray("selectedFolders");
            if (fo != null) for (int i = 0; i < fo.length(); i++) out.add("f:" + fo.optString(i));
            JSONArray pl = q.optJSONArray("selectedPlugins");
            if (pl != null) for (int i = 0; i < pl.length(); i++) out.add("p:" + pl.optString(i));
        } catch (IOException ignored) {
        }
        return out;
    }

    /** Folder sources of the Quick Mix (engine /media/folder-catalog, like the web page). */
    List<JSONObject> folderSources() throws IOException {
        Object o = http.call("GET", e("/media/folder-catalog"), null);
        JSONArray a = o instanceof JSONArray ? (JSONArray) o : o instanceof JSONObject
                ? (((JSONObject) o).optJSONArray("sources") != null ? ((JSONObject) o).optJSONArray("sources") : ((JSONObject) o).optJSONArray("Sources")) : null;
        List<JSONObject> out = new ArrayList<>();
        if (a != null) for (int i = 0; i < a.length(); i++) {
            JSONObject s = a.optJSONObject(i);
            if (s != null && !s.optString("path", s.optString("Path", "")).isEmpty()) out.add(s);
        }
        java.util.Collections.sort(out, new java.util.Comparator<JSONObject>() {
            @Override public int compare(JSONObject x, JSONObject y) {
                return x.optString("label", x.optString("path")).compareToIgnoreCase(y.optString("label", y.optString("path")));
            }
        });
        return out;
    }

    /** Plugins that bring their own pictures (content service with playable items), like the web page lists them. */
    List<JSONObject> pluginSources() throws IOException {
        JSONArray a = plugins();
        List<JSONObject> out = new ArrayList<>();
        for (int i = 0; i < a.length(); i++) {
            JSONObject p = a.optJSONObject(i);
            if (p == null) continue;
            boolean alive = p.optBoolean("installed") || p.optBoolean("running") || p.optBoolean("ready");
            boolean content = false;
            JSONArray sv = p.optJSONArray("services");
            if (sv != null) for (int k = 0; k < sv.length(); k++) {
                JSONObject s = sv.optJSONObject(k);
                if (s != null && "content".equalsIgnoreCase(s.optString("type"))) content = true;
            }
            int n = p.has("playableItemCount") && !p.isNull("playableItemCount") ? p.optInt("playableItemCount") : p.optInt("cachedFileCount");
            if (alive && content && (p.optBoolean("hasCacheDirectory") || n > 0)) out.add(p);
        }
        java.util.Collections.sort(out, new java.util.Comparator<JSONObject>() {
            @Override public int compare(JSONObject x, JSONObject y) { return x.optString("name").compareToIgnoreCase(y.optString("name")); }
        });
        return out;
    }

    /** Starts a Quick Mix of folders, plugin sources and saved playlists (web page "Choose Playlist"). */
    void startMix(List<String> folders, List<String> plugins, List<Integer> ids, String name) throws IOException {
        JSONArray fa = new JSONArray(), pa = new JSONArray(), ia = new JSONArray();
        for (String s : folders) fa.put(s);
        for (String s : plugins) pa.put(s);
        for (Integer i : ids) ia.put(i);
        JSONObject mix = new JSONObjectBuilder().put("selectedFolders", fa).put("selectedPlugins", pa).put("enabledSavedPlaylistIds", ia).o;
        http.call("POST", e("/playlists/play-selection"), new JSONObjectBuilder().put("requestId", java.util.UUID.randomUUID().toString())
                .put("startPlayback", true).put("playlistName", name).put("quickMixState", mix).o, 300000);
    }

    /** Plays several saved playlists mixed together (DynaFrame's "Choose Playlist" with several switched on). */
    void startPlaylists(List<Integer> ids, String name) throws IOException {
        JSONArray a = new JSONArray();
        for (Integer i : ids) a.put(i);
        JSONObject mix = new JSONObjectBuilder().put("selectedFolders", new JSONArray()).put("selectedPlugins", new JSONArray())
                .put("enabledSavedPlaylistIds", a).o;
        http.call("POST", e("/playlists/play-selection"), new JSONObjectBuilder().put("startPlayback", true)
                .put("playlistName", name).put("quickMixState", mix).o, 300000);
    }

    // ------------------------------------------------------------------ settings

    JSONObject slideshowSettings() throws IOException { return http.obj("GET", e("/settings/slideshow"), null); }

    /** The Engine takes single settings, e.g. {"durationSeconds": 30}. */
    void setSlideshow(String key, Object value) throws IOException {
        http.call("POST", e("/settings/slideshow"), new JSONObjectBuilder().put(key, value).o);
    }

    void setTransition(String name) throws IOException {
        http.call("POST", e("/transition"), new JSONObjectBuilder().put("transition", name).o);
    }

    /** Names of the transitions the frame offers. */
    List<String> transitions() {
        List<String> out = new ArrayList<>();
        try {
            Object o = http.call("GET", e("/transitions"), null);
            JSONArray a = o instanceof JSONArray ? (JSONArray) o : o instanceof JSONObject
                    ? ((JSONObject) o).optJSONArray("transitions") : null;
            if (a != null) for (int i = 0; i < a.length(); i++) {
                Object x = a.opt(i);
                String n = x instanceof JSONObject ? ((JSONObject) x).optString("name", ((JSONObject) x).optString("id", "")) : String.valueOf(x);
                if (!n.isEmpty() && !out.contains(n)) out.add(n);
            }
        } catch (IOException ignored) {
        }
        return out;
    }

    /** Mute state, or null when the frame does not say. */
    Boolean muted() {
        try {
            JSONObject o = http.obj("GET", e("/api/v1/system/mute"), null);
            if (o.has("muted")) return o.optBoolean("muted");
            if (o.has("isMuted")) return o.optBoolean("isMuted");
            if (o.has("value")) return o.optBoolean("value");
        } catch (Exception ignored) {
        }
        return null;
    }

    void setMute(boolean muted) throws IOException {
        http.call("POST", e("/api/v1/system/mute"), new JSONObjectBuilder().put("muted", muted).o);
    }

    // ---- display, system and plugins (same calls as the web UI's Settings, About and Plugins pages)

    /** {available_modes, image_fit_mode, video_fit_mode}. */
    JSONObject fitMode() throws IOException { return http.obj("GET", e("/display/fitmode"), null); }

    void setFitMode(String key, String mode) throws IOException {
        http.call("POST", e("/display/fitmode"), new JSONObjectBuilder().put(key, mode).o);
    }

    JSONObject about() throws IOException { return http.obj("GET", e("/system/about"), null); }

    JSONObject thermal() throws IOException { return http.obj("GET", e("/system/thermal/status"), null); }

    JSONObject storageSummary() throws IOException { return http.obj("GET", e("/system/storage-summary"), null); }

    /** Web UI: {status:{channel, updateAvailable, ...}}; null when the frame does not say. */
    JSONObject updatePresence() {
        try {
            JSONObject o = http.obj("GET", "/Update/PresenceStatus", null);
            JSONObject st = o.optJSONObject("status");
            if (st == null && o.optJSONObject("data") != null) st = o.optJSONObject("data").optJSONObject("status");
            return st;
        } catch (Exception e) { return null; }
    }

    /** Starts the same update as the web UI's "Update" button; returns the request id for the progress page. */
    String startUpdate(String ring) throws IOException {
        String id = java.util.UUID.randomUUID().toString();
        http.call("POST", "/Update/InitiateChannelUpdate", new JSONObjectBuilder().put("ring", ring).put("requestId", id).o);
        return id;
    }

    /** restart-dynaframe, restart-system or shutdown-system. */
    void power(String action) throws IOException { http.call("POST", e("/api/v1/system/power/" + action), null); }

    /** All plugins with state (web UI list). */
    JSONArray plugins() throws IOException { return http.arr("GET", "/Plugins/GetPlugins", null); }

    void setPluginEnabled(String name, boolean on) throws IOException {
        http.call("POST", e("/plugins/" + enc(name) + (on ? "/enable" : "/disable")), null);
    }

    void restartPlugin(String name) throws IOException { http.call("POST", e("/plugins/" + enc(name) + "/restart"), null); }

    void restartFrame() throws IOException { http.call("POST", e("/api/v1/system/power/restart-system"), null); }

    /**
     * What the frame shows right now. Tries the renderer screenshot the web UI's Home page uses
     * (GET /Home/CaptureRendererPreview), then the guest page's thumbnail, then the media thumbnail.
     */
    byte[] screenPicture(JSONObject item, int maxDim) throws IOException {
        byte[] b = image("/Home/CaptureRendererPreview", 0);
        if (b == null) b = image("/GuestPlayback/Thumbnail", 0);
        if (b == null && item != null) b = thumbnail(item, maxDim);
        return b;
    }

    /** GET an image; follows a JSON answer that carries a data: URL or a link to the picture. */
    private byte[] image(String path, int depth) throws IOException {
        HttpURLConnection c = null;
        try {
            c = http.open(path, "GET", 15000);
            c.setRequestProperty("Accept", "image/*, application/json");
            int code = c.getResponseCode();
            // 401/403 here only means this route is closed for us (e.g. guest access off): try the next source
            if (code != 200) { android.util.Log.w("FrameCompanion", "picture " + path + " -> HTTP " + code); return null; }
            String type = String.valueOf(c.getContentType()).toLowerCase(java.util.Locale.ROOT);
            java.io.ByteArrayOutputStream bo = new java.io.ByteArrayOutputStream();
            InputStream in = c.getInputStream();
            byte[] buf = new byte[16384];
            int n;
            while ((n = in.read(buf)) > 0 && bo.size() < 8 * 1024 * 1024) bo.write(buf, 0, n);
            in.close();
            byte[] body = bo.toByteArray();
            if (type.startsWith("image/")) return body;
            String s = new String(body, "UTF-8").trim();
            if (!s.startsWith("{") && !s.startsWith("\"")) return looksLikeImage(body) ? body : null;
            String found = findPicture(s.startsWith("{") ? new JSONObject(s) : (Object) new org.json.JSONTokener(s).nextValue());
            if (found == null) { android.util.Log.w("FrameCompanion", "picture " + path + ": no image in " + s.substring(0, Math.min(200, s.length()))); return null; }
            if (found.startsWith("data:")) {
                int comma = found.indexOf(',');
                return comma < 0 ? null : android.util.Base64.decode(found.substring(comma + 1), android.util.Base64.DEFAULT);
            }
            if (depth > 0) return null;
            if (found.startsWith("http")) { java.net.URL u = new java.net.URL(found); found = u.getFile(); }
            return image(found, depth + 1);
        } catch (org.json.JSONException ex) {
            return null;
        } catch (javax.net.ssl.SSLHandshakeException ex) {
            throw http.certOr(ex);
        } finally {
            if (c != null) c.disconnect();
        }
    }

    private static boolean looksLikeImage(byte[] b) {
        return b.length > 4 && ((b[0] == (byte) 0xFF && b[1] == (byte) 0xD8) || (b[0] == (byte) 0x89 && b[1] == 'P')
                || (b[0] == 'R' && b[1] == 'I') || (b[0] == 'G' && b[1] == 'I'));
    }

    private static String findPicture(Object o) {
        if (o instanceof String) {
            String s = (String) o;
            if (s.startsWith("data:image")) return s;
            String l = s.toLowerCase(java.util.Locale.ROOT);
            if ((s.startsWith("/") || s.startsWith("http")) && (l.contains("thumb") || l.contains("preview") || l.contains("capture")
                    || l.endsWith(".jpg") || l.endsWith(".jpeg") || l.endsWith(".png") || l.endsWith(".webp"))) return s;
            return null;
        }
        if (o instanceof JSONObject) {
            JSONObject j = (JSONObject) o;
            java.util.Iterator<String> k = j.keys();
            String later = null;
            while (k.hasNext()) {
                String r = findPicture(j.opt(k.next()));
                if (r != null && r.startsWith("data:")) return r;
                if (r != null && later == null) later = r;
            }
            return later;
        }
        if (o instanceof JSONArray) {
            JSONArray a = (JSONArray) o;
            for (int i = 0; i < a.length(); i++) { String r = findPicture(a.opt(i)); if (r != null) return r; }
        }
        return null;
    }

    /** A small picture of the item on screen (Engine thumbnail; works with the API key). */
    byte[] thumbnail(JSONObject item, int maxDim) throws IOException {
        // like DynaFrame's media-thumbnail-resolver: mediaFileId (not the playlist entry id), then given URLs
        int mid = item.optInt("mediaFileId", 0);
        if (mid > 0) {
            byte[] b = image(e("/media/thumbnail/" + mid + "?purpose=preview"), 1);
            if (b != null) return b;
        }
        for (String k : new String[]{"sceneThumbnailUrl", "externalThumbnailUrl", "thumbnailUrl"}) {
            String u = item.isNull(k) ? "" : item.optString(k, "");
            if (u.isEmpty()) continue;
            if (u.startsWith("http")) { try { u = new java.net.URL(u).getFile(); } catch (Exception ex) { continue; } }
            if (!u.startsWith("/")) continue;
            byte[] b = image(u, 1);
            if (b == null && !u.startsWith("/engine-proxy")) b = image(e(u), 1);
            if (b != null) return b;
        }
        String path = null;
        int id = 0;
        String fp = item.isNull("filePath") ? "" : item.optString("filePath", "");
        if (fp.isEmpty() && !item.isNull("path")) fp = item.optString("path", "");
        if (id > 0) path = e("/media/thumbnail/" + id + "?purpose=preview");
        else if (fp.startsWith("/")) path = e("/media/thumbnail?path=" + enc(fp) + "&maxDimension=" + maxDim);
        else {
            String sid = item.isNull("dynamicSceneId") ? "" : item.optString("dynamicSceneId", item.optString("sceneId", ""));
            if (!sid.isEmpty() && !"null".equals(sid)) path = e("/dynamic-scenes/thumbnail/" + enc(sid));
        }
        if (path == null) return null;
        HttpURLConnection c = null;
        try {
            c = http.open(path, "GET", 15000);
            c.setRequestProperty("Accept", "image/*");
            int code = c.getResponseCode();
            if (code != 200) android.util.Log.w("FrameCompanion", "thumbnail " + path + " -> HTTP " + code);
            if (code != 200) return null;
            java.io.ByteArrayOutputStream bo = new java.io.ByteArrayOutputStream();
            InputStream in = c.getInputStream();
            byte[] buf = new byte[16384];
            int n;
            while ((n = in.read(buf)) > 0 && bo.size() < 6 * 1024 * 1024) bo.write(buf, 0, n);
            in.close();
            return bo.toByteArray();
        } catch (javax.net.ssl.SSLHandshakeException ex) {
            throw http.certOr(ex);
        } finally {
            if (c != null) c.disconnect();
        }
    }

    // ------------------------------------------------------------------ folders

    String basePath() throws IOException {
        JSONObject o = http.obj("GET", "/Upload/GetMediaPathInfo", null);
        return o.optString("basePath", "/home/pi/Pictures");
    }

    /** Direct sub folders of the media root (absolute paths on the frame). */
    List<String> folders() throws IOException {
        JSONObject o = http.obj("GET", "/Upload/GetDirectChildDirectories", null);
        JSONArray a = o.optJSONArray("directories");
        List<String> out = new ArrayList<>();
        if (a != null) for (int i = 0; i < a.length(); i++) out.add(a.optString(i));
        return out;
    }

    /** Creates a folder below the media root, returns its absolute path. */
    String createFolder(String name) throws IOException {
        JSONObject o = http.obj("POST", "/Upload/CreateFolder",
                new JSONObjectBuilder().put("folderName", name).put("parentFolder", basePath()).o);
        if (!o.optBoolean("success", false)) {
            String err = o.optString("error", "");
            // Already there is fine.
            if (!err.toLowerCase().contains("exist")) throw new IOException(err.isEmpty() ? "CreateFolder failed" : err);
            return basePath() + "/" + name;
        }
        return o.optString("folderPath", basePath() + "/" + name);
    }

    /** Makes sure the folder exists (name below the media root); returns its absolute path. */
    String ensureFolder(String name) throws IOException {
        for (String p : folders()) {
            if (p.endsWith("/" + name)) return p;
        }
        return createFolder(name);
    }

    // ------------------------------------------------------------------ upload

    interface Source {
        InputStream open(long offset) throws IOException;
    }

    static final class Result {
        String path;
        String mediaType;
        boolean imported;
    }

    Result upload(String folder, String fileName, long size, long lastModified, boolean resize,
                  Source src, Http.Progress progress, java.util.concurrent.atomic.AtomicBoolean cancel) throws IOException {
        JSONObject created = http.obj("POST", "/Upload/ResumableSessions", new JSONObjectBuilder()
                .put("targetFolder", folder)
                .put("fileName", fileName)
                .put("size", size)
                .put("lastModified", lastModified)
                .put("resizeMode", resize ? "resize-eligible" : "original")
                .put("frameWidth", 0).put("frameHeight", 0).o);
        if (!created.optBoolean("success", false)) {
            throw new IOException(created.optString("error", "upload session refused"));
        }
        JSONObject session = created.optJSONObject("session");
        if (session == null) throw new IOException("no upload session");
        String id = session.optString("id");
        long chunk = Math.max(64 * 1024, session.optLong("chunkSize", 1024 * 1024));
        long offset = session.optLong("offset", 0);
        int failures = 0;
        while (offset < size) {
            if (cancel != null && cancel.get()) {
                try { http.call("DELETE", "/Upload/ResumableSessions/" + enc(id), null); } catch (IOException ignored) { }
                throw new IOException("cancelled");
            }
            long len = Math.min(chunk, size - offset);
            try {
                offset = sendChunk(id, offset, len, src, progress, size);
                failures = 0;
            } catch (Http.AuthException | Http.CertChangedException ex) {
                throw ex;
            } catch (IOException ex) {
                if (++failures > 4) throw ex;
                try { Thread.sleep(500L << failures); } catch (InterruptedException ie) { throw new IOException("interrupted"); }
                // Ask the frame where it stands and go on from there.
                try {
                    JSONObject st = http.obj("GET", "/Upload/ResumableSessions/" + enc(id), null);
                    JSONObject s = st.optJSONObject("session");
                    if (s != null) offset = s.optLong("offset", offset);
                } catch (Http.AuthException a) {
                    throw a;
                } catch (IOException ignored) {
                }
            }
        }
        JSONObject done = http.obj("POST", "/Upload/ResumableSessions/" + enc(id) + "/Complete", null);
        if (!done.optBoolean("success", false)) throw new IOException(done.optString("error", "upload not completed"));
        Result r = new Result();
        JSONArray results = done.optJSONArray("results");
        JSONObject first = results != null ? results.optJSONObject(0) : null;
        if (first != null) {
            r.imported = first.optBoolean("importedToLibrary", false);
            for (String k : new String[]{"filePath", "path", "fullPath", "savedPath", "destinationPath", "finalPath"}) {
                String v = first.optString(k, "");
                if (v.startsWith("/")) { r.path = v; break; }
            }
            r.mediaType = first.optString("mediaType", null);
        }
        if (r.path == null) r.path = folder.replaceAll("/+$", "") + "/" + fileName;
        return r;
    }

    private long sendChunk(String id, long offset, long len, Source src, Http.Progress progress, long size) throws IOException {
        HttpURLConnection c = null;
        try {
            c = http.open("/Upload/ResumableSessions/" + enc(id) + "/Chunks", "PUT", 120000);
            c.setDoOutput(true);
            c.setRequestProperty("Content-Type", "application/octet-stream");
            c.setRequestProperty("X-Upload-Offset", String.valueOf(offset));
            c.setFixedLengthStreamingMode(len);
            InputStream in = src.open(offset);
            try {
                OutputStream out = c.getOutputStream();
                byte[] buf = new byte[64 * 1024];
                long sent = 0;
                while (sent < len) {
                    int n = in.read(buf, 0, (int) Math.min(buf.length, len - sent));
                    if (n < 0) throw new IOException("file ended early");
                    out.write(buf, 0, n);
                    sent += n;
                    if (progress != null) progress.onProgress(offset + sent, size);
                }
                out.close();
            } finally {
                in.close();
            }
            int code = c.getResponseCode();
            if (code == 409) {
                InputStream es = c.getErrorStream();
                JSONObject o = new JSONObject(es == null ? "{}" : Http.readAll(es));
                long server = o.has("offset") ? o.optLong("offset") : o.optJSONObject("session") != null
                        ? o.optJSONObject("session").optLong("offset", offset) : offset;
                return server;
            }
            Object r = http.read(c);
            if (r instanceof JSONObject) {
                JSONObject o = (JSONObject) r;
                if (o.has("offset")) return o.optLong("offset");
                JSONObject s = o.optJSONObject("session");
                if (s != null && s.has("offset")) return s.optLong("offset");
            }
            return offset + len;
        } catch (javax.net.ssl.SSLHandshakeException ex) {
            throw http.certOr(ex);
        } catch (org.json.JSONException ex) {
            throw new IOException(ex);
        } finally {
            if (c != null) c.disconnect();
        }
    }

    /** Shows the given uploaded files right away; the frame returns to its playlist afterwards. */
    void playNow(List<Result> files) throws IOException {
        JSONArray items = new JSONArray();
        for (Result r : files) {
            String name = r.path.substring(r.path.lastIndexOf('/') + 1);
            String type = r.mediaType != null && !r.mediaType.isEmpty() ? r.mediaType : (isVideo(name) ? "video" : "image");
            items.put(new JSONObjectBuilder().put("type", "file").put("path", r.path).put("filePath", r.path)
                    .put("fileName", name).put("mediaType", type).o);
        }
        http.call("POST", e("/playback/play-now"), new JSONObjectBuilder().put("items", items).o, 60000);
    }

    /** DynaFrame's own way: play the whole folder now. */
    void playFolderNow(String folder) throws IOException {
        http.call("POST", "/Upload/PlayFolderNow", new JSONObjectBuilder().put("targetFolder", folder).o, 60000);
    }

    static boolean isVideo(String name) {
        String n = name.toLowerCase();
        return n.endsWith(".mp4") || n.endsWith(".mov") || n.endsWith(".m4v") || n.endsWith(".mkv")
                || n.endsWith(".webm") || n.endsWith(".3gp") || n.endsWith(".avi");
    }

    private static String enc(String s) {
        try {
            return URLEncoder.encode(s, "UTF-8").replace("+", "%20");
        } catch (Exception e) {
            return s;
        }
    }

    /** JSONObject.put without checked exceptions. */
    static final class JSONObjectBuilder {
        final JSONObject o = new JSONObject();
        JSONObjectBuilder put(String k, Object v) {
            try { o.put(k, v); } catch (Exception ignored) { }
            return this;
        }
    }

    /** True when version a is newer than b (1.2.10 > 1.2.9). */
    static boolean newer(String a, String b) {
        String[] x = a.split("\\."), y = b.split("\\.");
        for (int i = 0; i < Math.max(x.length, y.length); i++) {
            int p = 0, q = 0;
            try { p = i < x.length ? Integer.parseInt(x[i].replaceAll("\\D.*", "")) : 0; } catch (Exception ignored) { }
            try { q = i < y.length ? Integer.parseInt(y[i].replaceAll("\\D.*", "")) : 0; } catch (Exception ignored) { }
            if (p != q) return p > q;
        }
        return false;
    }
}
