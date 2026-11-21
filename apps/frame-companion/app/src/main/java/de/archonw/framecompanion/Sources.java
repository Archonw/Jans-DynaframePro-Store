package de.archonw.framecompanion;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.IOException;
import java.net.URLEncoder;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * The frame's web UI routes for photo sources and the store, the same ones its own pages use:
 * /Nas/* (SMB shares, USB), /WebDav/* (WebDAV, Nextcloud), /Store/* and /Plugins/*.
 */
final class Sources {

    final Api api;
    private final Http http;

    Sources(Frame f) {
        api = new Api(f);
        http = api.http;
    }

    static String enc(String s) {
        try { return URLEncoder.encode(s == null ? "" : s, "UTF-8"); } catch (Exception e) { return ""; }
    }

    private Object call(final String method, final String path, final Object body, final int readMs) throws IOException {
        return api.with(new Api.Call<Object>() {
            @Override public Object run() throws IOException { return http.call(method, path, body, readMs); }
        });
    }

    private JSONObject obj(String method, String path, Object body, int readMs) throws IOException {
        Object o = call(method, path, body, readMs);
        return o instanceof JSONObject ? (JSONObject) o : new JSONObject();
    }

    static JSONArray list(Object o, String... keys) {
        if (o instanceof JSONArray) return (JSONArray) o;
        if (o instanceof JSONObject) for (String k : keys) {
            JSONArray a = ((JSONObject) o).optJSONArray(k);
            if (a != null) return a;
        }
        return new JSONArray();
    }

    static String s(JSONObject o, String... keys) {
        if (o == null) return "";
        for (String k : keys) if (o.has(k) && !o.isNull(k)) {
            String v = o.optString(k, "").trim();
            if (!v.isEmpty()) return v;
        }
        return "";
    }

    // ------------------------------------------------------------------ NAS (SMB)

    /** Hosts with their shares, found by mDNS (takes ~15 s). */
    JSONArray discover() throws IOException {
        return list(call("GET", "/Nas/Discover?mode=quick", null, 60000), "hosts", "Hosts");
    }

    /** Looks up a host typed in by hand; returns the host object or null. */
    JSONObject probe(String host) throws IOException {
        JSONObject r = obj("GET", "/Nas/Probe?host=" + enc(host), null, 30000);
        String job = s(r, "jobId", "JobId");
        if (job.isEmpty()) return r.has("host") || r.has("shares") ? r : r.optJSONObject("result");
        for (int i = 0; i < 150; i++) {
            try { Thread.sleep(400); } catch (InterruptedException e) { return null; }
            JSONObject st = obj("GET", "/Nas/ProbeStatus?id=" + enc(job), null, 15000);
            String state = s(st, "state", "State").toLowerCase(Locale.ROOT);
            if (state.equals("completed") || state.equals("complete")) {
                JSONObject h = st.optJSONObject("result");
                return h != null ? h : st.optJSONObject("Result");
            }
            if (state.equals("failed")) throw new IOException(s(st, "error", "message", "Error"));
        }
        return null;
    }

    static String credentialHost(JSONObject h) {
        String r = s(h, "requestedHost", "RequestedHost");
        return r.isEmpty() ? s(h, "host", "Host") : r;
    }

    boolean hasPassword(JSONObject h) {
        try {
            JSONObject r = obj("GET", "/Nas/GetCredentials?host=" + enc(credentialHost(h)), null, 15000);
            JSONObject c = r.optJSONObject("credentials");
            return c != null && c.optBoolean("hasPassword", false);
        } catch (IOException e) {
            return false;
        }
    }

    void saveCredentials(JSONObject h, String user, String password, String domain) throws IOException {
        JSONArray aliases = new JSONArray();
        for (String a : new String[]{s(h, "host", "Host"), s(h, "address", "Address"), s(h, "serverIdentity", "ServerIdentity")})
            if (!a.isEmpty()) aliases.put(a);
        JSONArray more = h.optJSONArray("aliases");
        if (more != null) for (int i = 0; i < more.length(); i++) aliases.put(more.optString(i));
        try {
            JSONObject b = new JSONObject().put("host", credentialHost(h)).put("username", user)
                    .put("password", password == null || password.isEmpty() ? JSONObject.NULL : password)
                    .put("domain", domain == null || domain.isEmpty() ? JSONObject.NULL : domain).put("aliases", aliases);
            JSONObject r = obj("POST", "/Nas/SaveCredentials", b, 20000);
            if (r.has("success") && !r.optBoolean("success")) throw new IOException(s(r, "message", "error"));
        } catch (org.json.JSONException e) {
            throw new IOException(e);
        }
    }

    /** Result of connecting a share. */
    static final class MapResult {
        String sourceId = "";
        boolean authFailed, mounted;
        String message = "";
    }

    MapResult map(JSONObject h, String share, String label) throws IOException {
        MapResult m = new MapResult();
        try {
            JSONObject b = new JSONObject().put("host", s(h, "host", "Host")).put("preferredHost", credentialHost(h))
                    .put("serverIdentity", nullable(s(h, "serverIdentity", "ServerIdentity")))
                    .put("lastKnownAddress", nullable(s(h, "address", "Address")))
                    .put("share", share).put("subPath", "").put("label", label).put("credentialScope", "host")
                    .put("protocol", "smb").put("deferFolderRegistration", true);
            JSONObject r;
            try {
                r = obj("POST", "/Nas/Map", b, 90000);
            } catch (Http.HttpException e) {
                r = e.json();
                String code = s(r, "code");
                if (e.code == 409 && code.equals("nas-source-already-mapped")) {
                    // already connected earlier: carry on with that source
                    JSONObject ex = r.optJSONObject("existingMapping");
                    String id = sourceForMapping(ex == null ? "" : s(ex, "MappingId", "mappingId"), share);
                    if (!id.isEmpty()) { m.sourceId = id; m.mounted = true; return m; }
                }
                if (e.code == 409 && code.equals("nas-label-in-use")) return map(h, share, label + " 2");
                if (r.length() == 0) throw e;
            }
            m.mounted = r.optBoolean("mounted", r.optBoolean("success"));
            m.message = s(r, "message", "error");
            m.authFailed = "authentication-failed".equals(s(r, "failureCode"));
            if (r.optBoolean("success", false)) m.sourceId = sourceId(r);
            return m;
        } catch (org.json.JSONException e) {
            throw new IOException(e);
        }
    }

    private static Object nullable(String v) { return v.isEmpty() ? JSONObject.NULL : v; }

    static String sourceId(JSONObject r) {
        String id = s(r, "sourceId", "SourceId", "externalSourceId", "ExternalSourceId");
        JSONObject src = r.optJSONObject("source");
        if (src == null) src = r.optJSONObject("Source");
        if (id.isEmpty() && src != null) id = s(src, "id", "Id");
        if (id.isEmpty()) id = s(r, "id", "Id");
        return id;
    }

    private String sourceForMapping(String mappingId, String share) throws IOException {
        JSONArray a = list(call("GET", "/Nas/GetExternalSources", null, 15000), "sources", "items");
        for (int i = 0; i < a.length(); i++) {
            JSONObject o = a.optJSONObject(i);
            if (o == null) continue;
            if ((!mappingId.isEmpty() && mappingId.equals(s(o, "nasMappingId"))) || share.equalsIgnoreCase(s(o, "displayName"))) return s(o, "id");
        }
        return "";
    }

    /** Sub folders of a connected NAS share or USB drive. Each entry: {name, path}. */
    List<String[]> externalFolders(String sourceId, String relativePath) throws IOException {
        List<String[]> out = new ArrayList<>();
        int offset = 0;
        for (int round = 0; round < 20; round++) {
            JSONObject r = obj("GET", "/Nas/BrowseExternalChildren?id=" + enc(sourceId) + "&relativePath=" + enc(relativePath)
                    + "&offset=" + offset + "&limit=100", null, 30000);
            JSONArray items = list(r, "items", "Items");
            for (int i = 0; i < items.length(); i++) {
                JSONObject it = items.optJSONObject(i);
                if (it == null || !(it.optBoolean("isDirectory", it.optBoolean("IsDirectory", false)))) continue;
                String name = s(it, "name", "Name", "displayName");
                String path = s(it, "path", "Path");
                if (path.isEmpty()) path = relativePath.isEmpty() ? name : relativePath + "/" + name;
                out.add(new String[]{name, path});
            }
            int total = r.optInt("total", r.optInt("Total", items.length()));
            offset += 100;
            if (items.length() == 0 || offset >= total) break;
        }
        return out;
    }

    /** Adds folders of a NAS/USB source to the library; returns the scan job id (may be empty). */
    String registerExternal(String sourceId, List<String[]> folders) throws IOException {
        try {
            JSONArray fs = new JSONArray();
            for (String[] f : folders) fs.put(new JSONObject().put("relativePath", f[1]).put("displayName", f[0]).put("recursive", true));
            JSONObject r = obj("POST", "/Nas/RegisterExternalFolders?id=" + enc(sourceId),
                    new JSONObject().put("folders", fs).put("futureChildren", new JSONArray()), 60000);
            return s(r, "scanJobId", "ScanJobId");
        } catch (org.json.JSONException e) {
            throw new IOException(e);
        }
    }

    /** Progress of indexing: {state, percent, error}. */
    String[] externalJob(String jobId) throws IOException {
        JSONObject j = obj("GET", "/Nas/GetRescanJob?id=" + enc(jobId), null, 15000);
        return new String[]{s(j, "state", "status", "State", "Status").toLowerCase(Locale.ROOT),
                j.has("percentComplete") ? String.valueOf(j.optInt("percentComplete")) : "", s(j, "error", "Error")};
    }

    // ------------------------------------------------------------------ USB

    JSONArray usbDrives() throws IOException {
        return list(call("GET", "/Upload/DetectUsbDrives", null, 20000), "drives", "Drives");
    }

    String connectUsb(String deviceId) throws IOException {
        try {
            return sourceId(obj("POST", "/Nas/ConnectUsbSource", new JSONObject().put("deviceId", deviceId), 30000));
        } catch (org.json.JSONException e) {
            throw new IOException(e);
        }
    }

    // ------------------------------------------------------------------ WebDAV

    /** The WebDAV routes want the page's antiforgery token (and its cookie) like the web UI sends it. */
    private void webdavToken() throws IOException {
        if (http.antiForgery != null) return;
        Object page = call("GET", "/Upload", null, 30000);
        String html = String.valueOf(page);
        java.util.regex.Matcher m = java.util.regex.Pattern.compile("name=\"__RequestVerificationToken\"[^>]*value=\"([^\"]+)\"").matcher(html);
        if (!m.find()) m = java.util.regex.Pattern.compile("value=\"([^\"]+)\"[^>]*name=\"__RequestVerificationToken\"").matcher(html);
        if (m.find(0)) http.antiForgery = m.group(1);
    }

    private Object dav(String method, String route, Object body, int readMs) throws IOException {
        webdavToken();
        return call(method, "/WebDav/" + route, body, readMs);
    }

    /** Tests and saves a WebDAV connection; returns its id. */
    String webdavAdd(String name, String url, String user, String password) throws IOException {
        try {
            JSONObject b = new JSONObject().put("displayName", name).put("url", url).put("username", user).put("password", password);
            Object t = dav("POST", "Test", b, 60000);
            if (t instanceof JSONObject && ((JSONObject) t).has("success") && !((JSONObject) t).optBoolean("success"))
                throw new IOException(s((JSONObject) t, "error", "message"));
            Object r = dav("POST", "Save", b, 60000);
            String id = r instanceof JSONObject ? s((JSONObject) r, "id", "Id") : "";
            if (id.isEmpty()) throw new IOException("no id");
            return id;
        } catch (org.json.JSONException e) {
            throw new IOException(e);
        }
    }

    List<String[]> webdavFolders(String id, String path) throws IOException {
        List<String[]> out = new ArrayList<>();
        JSONArray a = list(dav("GET", "Children?id=" + enc(id) + "&path=" + enc(path), null, 60000), "items", "entries");
        for (int i = 0; i < a.length(); i++) {
            JSONObject o = a.optJSONObject(i);
            if (o == null || !o.optBoolean("isDirectory", false)) continue;
            out.add(new String[]{s(o, "name"), s(o, "relativePath")});
        }
        return out;
    }

    /** Links WebDAV folders; returns the indexing job id. */
    String webdavLink(String id, List<String[]> folders) throws IOException {
        try {
            JSONArray fs = new JSONArray();
            for (String[] f : folders) fs.put(new JSONObject().put("relativePath", f[1]).put("displayName", f[0]).put("recursive", true));
            Object r = dav("POST", "Folders?id=" + enc(id), new JSONObject().put("folders", fs), 60000);
            return r instanceof JSONObject ? s((JSONObject) r, "id", "Id", "jobId") : "";
        } catch (org.json.JSONException e) {
            throw new IOException(e);
        }
    }

    String[] webdavJob(String jobId) throws IOException {
        Object r = dav("GET", "Job?id=" + enc(jobId), null, 15000);
        JSONObject j = r instanceof JSONObject ? (JSONObject) r : new JSONObject();
        return new String[]{s(j, "status", "state").toLowerCase(Locale.ROOT), j.has("indexedFiles") ? String.valueOf(j.optInt("indexedFiles")) : "", s(j, "error")};
    }

    // ------------------------------------------------------------------ Store

    /** A pack found in one of the frame's stores. */
    static final class Pack {
        JSONObject json;
        String id, type, title, description, version, author, storeName, storeUrl;
        boolean storeEnabled;
    }

    /** All plugin/integration packs of all stores the frame knows (enabled stores first). */
    List<Pack> storePacks() throws IOException {
        List<Pack> out = new ArrayList<>();
        JSONArray stores = list(call("GET", "/Store/GetStores", null, 20000), "stores", "Stores");
        List<JSONObject> order = new ArrayList<>();
        for (int i = 0; i < stores.length(); i++) if (stores.optJSONObject(i) != null && stores.optJSONObject(i).optBoolean("isEnabled")) order.add(stores.optJSONObject(i));
        for (int i = 0; i < stores.length(); i++) if (stores.optJSONObject(i) != null && !stores.optJSONObject(i).optBoolean("isEnabled")) order.add(stores.optJSONObject(i));
        for (JSONObject st : order) {
            String url = s(st, "manifestUrl");
            if (url.isEmpty()) continue;
            JSONObject cat;
            try {
                cat = obj("GET", "/Store/GetCatalog?catalogUrl=" + enc(url) + "&forceRefresh=false", null, 30000);
            } catch (IOException e) {
                continue;
            }
            JSONArray packs = cat.optJSONArray("packs");
            if (packs == null) continue;   // old v1.0 catalogs are left out
            for (int i = 0; i < packs.length(); i++) {
                JSONObject p = packs.optJSONObject(i);
                if (p == null) continue;
                String type = s(p, "type").toLowerCase(Locale.ROOT);
                if (!type.equals("plugin") && !type.equals("integration") && !type.equals("dynamic")) continue;
                Pack k = new Pack();
                k.json = p;
                k.id = s(p, "id");
                k.type = type;
                k.title = s(p, "title");
                k.description = s(p, "description");
                k.version = s(p, "version");
                k.author = s(p, "author");
                k.storeName = s(st, "name");
                k.storeUrl = url;
                k.storeEnabled = st.optBoolean("isEnabled");
                out.add(k);
            }
        }
        return out;
    }

    /** Version of an installed pack, or null. */
    String installedVersion(String packId) throws IOException {
        JSONArray a = list(call("GET", "/Store/GetInstalledPacks", null, 20000), "packs", "Packs");
        for (int i = 0; i < a.length(); i++) {
            JSONObject o = a.optJSONObject(i);
            if (o != null && packId.equalsIgnoreCase(s(o, "packId", "PackId"))) return s(o, "version", "Version");
        }
        return null;
    }

    /** Installed packs: id (lower case) to version. */
    java.util.Map<String, String> installedPacks() throws IOException {
        java.util.Map<String, String> out = new java.util.HashMap<>();
        JSONArray a = list(call("GET", "/Store/GetInstalledPacks", null, 20000), "packs", "Packs");
        for (int i = 0; i < a.length(); i++) {
            JSONObject o = a.optJSONObject(i);
            if (o != null) out.put(s(o, "packId", "PackId").toLowerCase(Locale.ROOT), s(o, "version", "Version"));
        }
        return out;
    }

    /** All plugins as the web UI's plugin page lists them. */
    JSONArray plugins() throws IOException { return list(call("GET", "/Plugins/GetPlugins", null, 20000), "plugins", "items"); }

    /** Settings page of a plugin: its own page when it has one, else the web UI's settings dialog. */
    static String pluginPage(JSONObject plugin) {
        String name = s(plugin, "name");
        boolean advanced = plugin.optBoolean("advancedSettingsAvailable", false);
        JSONObject as = plugin.optJSONObject("advancedSettings");
        if (!advanced && as != null) advanced = as.optBoolean("Enabled", as.optBoolean("enabled", false));
        return advanced ? "/Plugins/Advanced/" + enc(name).replace("+", "%20") + "/" : "/Plugins?openSettings=" + enc(name);
    }

    private static String baseUrl(String catalogUrl) {
        int q = catalogUrl.indexOf('?');
        String u = q >= 0 ? catalogUrl.substring(0, q) : catalogUrl;
        int i = u.lastIndexOf('/');
        return i > 8 ? u.substring(0, i + 1) : u + "/";
    }

    /** Installs a pack the way the web UI's store page does. */
    void install(Pack p, String previousVersion) throws IOException {
        try {
            JSONObject j = p.json;
            String dl = s(j, "download_url");
            String direct = dl.startsWith("http") ? dl : dl.isEmpty()
                    ? baseUrl(p.storeUrl) + "plugin_packs/" + p.id + "/" + p.id + ".zip" : baseUrl(p.storeUrl) + dl.replaceFirst("^/+", "");
            String tracking = s(j, "tracking_url");
            String zip = tracking.startsWith("http") ? tracking : direct;
            boolean plugin = p.type.equals("plugin");
            JSONObject b = new JSONObject().put("packId", p.id).put("packTitle", p.title).put("zipUrl", zip).put("fallbackZipUrl", direct)
                    .put("version", p.version).put("checksum", s(j, "checksum")).put("sourceStore", p.storeUrl).put("downloadUrl", dl)
                    .put("security", j.has("security") ? j.opt("security") : JSONObject.NULL);
            if (plugin) b.put("installAction", previousVersion == null ? "install" : "update").put("previousVersion", previousVersion == null ? JSONObject.NULL : previousVersion);
            else b.put("packType", p.type);
            JSONObject r;
            try {
                r = obj("POST", plugin ? "/Store/DownloadAndInstallPlugin" : "/Store/DownloadAndInstallDynamic", b, 300000);
            } catch (Http.HttpException e) {
                throw new IOException(e.message());
            }
            if (!(r.optBoolean("success", false) || r.optBoolean("Success", false))) throw new IOException(s(r, "error", "Error", "message", "Message"));
            String path = s(r, "extractedPath", "ExtractedPath", "installPath", "InstallPath");
            JSONObject mark = new JSONObject().put("PackId", p.id).put("Type", p.type).put("Title", p.title).put("Author", p.author)
                    .put("Version", p.version).put("SourceStore", p.storeUrl).put("InstallPath", path)
                    .put("Checksum", s(j, "checksum")).put("Size", j.optLong("size_bytes", j.optLong("size", 0)));
            obj("POST", "/Store/MarkPackInstalled", mark, 30000);
        } catch (org.json.JSONException e) {
            throw new IOException(e);
        }
    }

    /** The installed plugin that came from this pack: {name, settings page path} or null. */
    String[] pluginFor(Pack p) throws IOException {
        JSONArray a = list(call("GET", "/Plugins/GetPlugins", null, 20000), "plugins", "items");
        JSONObject hit = null;
        String squashed = p.title.replaceAll("[^A-Za-z0-9]", "").toLowerCase(Locale.ROOT);
        for (int i = 0; i < a.length(); i++) {
            JSONObject o = a.optJSONObject(i);
            if (o == null) continue;
            JSONObject in = o.optJSONObject("installation");
            if (in != null && p.id.equalsIgnoreCase(s(in, "storePackId"))) { hit = o; break; }
            String n = s(o, "name").toLowerCase(Locale.ROOT);
            if (hit == null && (n.equals(squashed) || s(o, "displayName").equalsIgnoreCase(p.title))) hit = o;
        }
        if (hit == null) return null;
        String name = s(hit, "name");
        String page = pluginPage(hit);
        return new String[]{name, page, hit.optBoolean("ready", false) ? "1" : "0"};
    }
}
