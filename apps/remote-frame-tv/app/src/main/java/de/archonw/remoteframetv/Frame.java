package de.archonw.remoteframetv;

/** One DynaFrame on the network. */
final class Frame {
    static final int OK = 0, LOGIN = 1, OFFLINE = 2, UNKNOWN = 3;

    final String host;      // IP or host name, optionally with :port
    String name;            // frameName from the frame, or the host
    String id;              // frameId, if known
    int state = UNKNOWN;
    boolean saved;          // remembered from an earlier start
    boolean secure;         // frame has DynaFrame's WebUI security on: talk https, log in once
    /** DynaFrame's remote frames on this frame (id + name); empty while unknown. */
    final java.util.List<Remote> remotes = new java.util.ArrayList<>();

    static final class Remote {
        final int id;
        final String name;
        Remote(int id, String name) { this.id = id; this.name = name; }
        String label() { return name == null || name.trim().isEmpty() ? "Remote Frame " + id : name; }
    }

    /** Reads frames[] of /remote-frame/settings; keeps only enabled ones. */
    static java.util.List<Remote> parseRemotes(String json) {
        java.util.List<Remote> out = new java.util.ArrayList<>();
        try {
            org.json.JSONArray a = new org.json.JSONObject(json).optJSONArray("frames");
            if (a == null) return out;
            for (int i = 0; i < a.length(); i++) {
                org.json.JSONObject o = a.optJSONObject(i);
                if (o == null || !o.has("id") || !o.optBoolean("enabled", true)) continue;
                out.add(new Remote(o.optInt("id"), o.optString("name", "")));
            }
        } catch (Exception ignored) {
        }
        return out;
    }

    Frame(String host, String name) {
        this.host = host;
        this.name = name == null || name.isEmpty() ? host : name;
    }

    /** Address of DynaFrame's own browser viewer (remote frame 0; older DynaFrames only know /RemoteFrame, see ViewerActivity). http redirects to https itself if the frame wants that. */
    String viewerUrl(int remote) {
        String h = host;
        if (h.startsWith("http://") || h.startsWith("https://")) {
            return h.replaceAll("/+$", "") + "/RemoteFrame/" + remote;
        }
        // With WebUI security, http only leads to the /Connect help page; the login lives on https.
        return (secure || state == LOGIN ? "https://" : "http://") + h + "/RemoteFrame/" + remote;
    }
}
