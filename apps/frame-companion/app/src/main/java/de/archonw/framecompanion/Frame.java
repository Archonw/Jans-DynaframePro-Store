package de.archonw.framecompanion;

import org.json.JSONObject;

/** One DynaFrame on the network, with how to reach it. */
final class Frame {
    static final int OK = 0, LOGIN = 1, OFFLINE = 2, UNKNOWN = 3;

    final String host;      // IP or host name, optionally with :port
    String name;            // frameName from the frame, or the host
    String id;              // frameId, if known
    int state = UNKNOWN;
    boolean saved;          // remembered from an earlier start
    boolean https;          // talk https (DynaFrame's own login is on)
    String apiKey;          // DynaFrame "Full REST" API key, only needed with the login on
    String fingerprint;     // pinned SHA-256 of the frame's certificate
    String user, password;  // optional: DynaFrame admin sign-in instead of a key (app-private storage)

    Frame(String host, String name) {
        this.host = host;
        this.name = name == null || name.isEmpty() ? host : name;
    }

    boolean needsKey() {
        return state == LOGIN && !hasLogin();
    }

    boolean hasLogin() {
        return (apiKey != null && !apiKey.isEmpty()) || (user != null && !user.isEmpty() && password != null);
    }

    JSONObject json() throws Exception {
        JSONObject j = new JSONObject().put("host", host).put("name", name).put("https", https);
        if (id != null) j.put("id", id);
        if (apiKey != null) j.put("key", apiKey);
        if (fingerprint != null) j.put("fp", fingerprint);
        if (user != null) j.put("user", user);
        if (password != null) j.put("pw", password);
        return j;
    }

    static Frame from(JSONObject o) throws Exception {
        Frame f = new Frame(o.getString("host"), o.optString("name"));
        f.id = o.has("id") ? o.optString("id") : null;
        f.https = o.optBoolean("https", false);
        f.apiKey = o.has("key") ? o.optString("key") : null;
        f.fingerprint = o.has("fp") ? o.optString("fp") : null;
        f.user = o.has("user") ? o.optString("user") : null;
        f.password = o.has("pw") ? o.optString("pw") : null;
        f.saved = true;
        return f;
    }

    /** Takes over what discovery learned, keeping the saved login. */
    void merge(Frame found) {
        if (found.name != null && !found.name.equals(found.host)) name = found.name;
        if (found.id != null) id = found.id;
        if (found.state == LOGIN) https = true;
        state = found.state == LOGIN && hasLogin() ? OK : found.state;
    }
}
