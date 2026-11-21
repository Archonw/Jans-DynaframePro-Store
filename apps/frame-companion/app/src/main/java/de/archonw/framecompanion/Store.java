package de.archonw.framecompanion;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONArray;

import java.util.ArrayList;
import java.util.List;

/** Remembers frames (with API key and pinned certificate) and settings. App-private storage. */
final class Store {
    private final SharedPreferences p;

    Store(Context c) {
        p = c.getSharedPreferences("framecompanion", Context.MODE_PRIVATE);
    }

    List<Frame> saved() {
        List<Frame> out = new ArrayList<>();
        try {
            JSONArray a = new JSONArray(p.getString("frames", "[]"));
            for (int i = 0; i < a.length(); i++) out.add(Frame.from(a.getJSONObject(i)));
        } catch (Exception ignored) {
        }
        return out;
    }

    Frame find(String host) {
        if (host == null) return null;
        for (Frame f : saved()) if (f.host.equals(host)) return f;
        return null;
    }

    private static boolean same(Frame a, Frame b) {
        return a.host.equals(b.host) || (a.id != null && a.id.equals(b.id));
    }

    /** Saves f (new or changed); remembers it as the last used frame when last is true. */
    synchronized void save(Frame f, boolean last) {
        JSONArray a = new JSONArray();
        try {
            boolean done = false;
            if (last) { a.put(f.json()); done = true; }
            for (Frame o : saved()) {
                if (same(o, f)) {
                    if (!done) { a.put(f.json()); done = true; }
                } else {
                    a.put(o.json());
                }
            }
            if (!done) a.put(f.json());
        } catch (Exception ignored) {
        }
        f.saved = true;
        SharedPreferences.Editor e = p.edit().putString("frames", a.toString());
        if (last) e.putString("last", f.host);
        e.apply();
    }

    synchronized void forget(Frame f) {
        JSONArray a = new JSONArray();
        try {
            for (Frame o : saved()) if (!o.host.equals(f.host)) a.put(o.json());
        } catch (Exception ignored) {
        }
        SharedPreferences.Editor e = p.edit().putString("frames", a.toString());
        if (f.host.equals(last())) e.remove("last");
        e.apply();
    }

    String last() { return p.getString("last", null); }

    Frame lastFrame() { return find(last()); }

    boolean showNow() { return p.getBoolean("showNow", true); }

    void setShowNow(boolean on) { p.edit().putBoolean("showNow", on).apply(); }

    /** Playlists started from this app, newest first (ids, per frame). */
    List<Integer> recent(String host) {
        List<Integer> out = new ArrayList<>();
        try {
            JSONArray a = new JSONArray(p.getString("recent:" + host, "[]"));
            for (int i = 0; i < a.length(); i++) out.add(a.getInt(i));
        } catch (Exception ignored) {
        }
        return out;
    }

    void addRecent(String host, int id) {
        List<Integer> r = recent(host);
        r.remove(Integer.valueOf(id));
        r.add(0, id);
        JSONArray a = new JSONArray();
        for (int i = 0; i < Math.min(4, r.size()); i++) a.put(r.get(i));
        p.edit().putString("recent:" + host, a.toString()).apply();
    }

    boolean showPluginPlaylists() { return p.getBoolean("pluginPlaylists", false); }

    void setShowPluginPlaylists(boolean on) { p.edit().putBoolean("pluginPlaylists", on).apply(); }

    boolean preview() { return p.getBoolean("preview", true); }

    void setPreview(boolean on) { p.edit().putBoolean("preview", on).apply(); }

    String folder() { return p.getString("folder", null); }

    void setFolder(String f) { p.edit().putString("folder", f).apply(); }
}
