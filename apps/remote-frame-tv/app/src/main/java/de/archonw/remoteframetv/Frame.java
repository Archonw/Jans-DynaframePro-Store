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

    Frame(String host, String name) {
        this.host = host;
        this.name = name == null || name.isEmpty() ? host : name;
    }

    /** Address of DynaFrame's own browser viewer. http redirects to https itself if the frame wants that. */
    String viewerUrl() {
        String h = host;
        if (h.startsWith("http://") || h.startsWith("https://")) {
            return h.replaceAll("/+$", "") + "/RemoteFrame";
        }
        // With WebUI security, http only leads to the /Connect help page; the login lives on https.
        return (secure || state == LOGIN ? "https://" : "http://") + h + "/RemoteFrame";
    }
}
