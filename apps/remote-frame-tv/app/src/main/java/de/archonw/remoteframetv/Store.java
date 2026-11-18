package de.archonw.remoteframetv;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/** Remembers frames and settings between starts. */
final class Store {
    private final SharedPreferences p;

    Store(Context c) {
        p = c.getSharedPreferences("remoteframetv", Context.MODE_PRIVATE);
    }

    List<Frame> saved() {
        List<Frame> out = new ArrayList<>();
        try {
            JSONArray a = new JSONArray(p.getString("frames", "[]"));
            for (int i = 0; i < a.length(); i++) {
                JSONObject o = a.getJSONObject(i);
                Frame f = new Frame(o.getString("host"), o.optString("name"));
                f.id = o.optString("id", null);
                f.secure = o.optBoolean("secure", false) || p.getBoolean("secure:" + f.host, false);
                f.saved = true;
                f.remotes.addAll(remotes(f.host));
                out.add(f);
            }
        } catch (Exception ignored) {
        }
        return out;
    }

    private static JSONObject json(Frame f) throws Exception {
        JSONObject j = new JSONObject().put("host", f.host).put("name", f.name)
                .put("secure", f.secure || f.state == Frame.LOGIN);
        if (f.id != null) j.put("id", f.id);
        return j;
    }

    /** Saves f as the most recent frame (first in the list). */
    void remember(Frame f) {
        JSONArray a = new JSONArray();
        try {
            a.put(json(f));
            for (Frame o : saved()) {
                boolean same = o.host.equals(f.host) || (f.id != null && f.id.equals(o.id));
                if (!same) a.put(json(o));
            }
        } catch (Exception ignored) {
        }
        p.edit().putString("frames", a.toString()).putString("last", f.host).apply();
    }

    /** Updates name/id/https of a saved frame without changing the order or "last". */
    void refresh(Frame f) {
        JSONArray a = new JSONArray();
        try {
            for (Frame o : saved()) a.put(json(o.host.equals(f.host) ? f : o));
        } catch (Exception ignored) {
        }
        p.edit().putString("frames", a.toString()).apply();
    }

    void forget(Frame f) {
        JSONArray a = new JSONArray();
        try {
            for (Frame o : saved()) if (!o.host.equals(f.host)) a.put(json(o));
        } catch (Exception ignored) {
        }
        SharedPreferences.Editor e = p.edit().putString("frames", a.toString());
        if (f.host.equals(last())) e.remove("last");
        e.apply();
    }

    String last() { return p.getString("last", null); }

    int lastRemote(String host) { return p.getInt("remote:" + host, 0); }

    void setLastRemote(String host, int id) { p.edit().putInt("remote:" + host, id).apply(); }

    void saveRemotes(String host, List<Frame.Remote> list) {
        JSONArray a = new JSONArray();
        try {
            for (Frame.Remote r : list) a.put(new JSONObject().put("id", r.id).put("name", r.name).put("enabled", true));
            p.edit().putString("remotes:" + host, new JSONObject().put("frames", a).toString()).apply();
        } catch (Exception ignored) {
        }
    }

    List<Frame.Remote> remotes(String host) {
        return Frame.parseRemotes(p.getString("remotes:" + host, "{}"));
    }

    boolean autostart() { return p.getBoolean("autostart", true); }

    void setAutostart(boolean on) { p.edit().putBoolean("autostart", on).apply(); }
}
