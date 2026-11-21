package de.archonw.framecompanion;

import android.app.Activity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.List;

/** List of frames: saved ones first, then whatever the network search finds. */
final class FramePicker implements Discovery.Listener {

    interface OnPick { void pick(Frame f); }
    interface OnRemote { void pick(Frame f, String path, String title); }

    /** One of DynaFrame's remote frames (a browser/TV/Pi view of the frame); id -1 = older DynaFrame with a single /RemoteFrame. */
    static final class Remote {
        final int id; final String name; final boolean enabled;
        Remote(int id, String name, boolean enabled) { this.id = id; this.name = name; this.enabled = enabled; }
    }

    OnRemote onRemote;
    private final java.util.Map<String, List<Remote>> remotes = new java.util.LinkedHashMap<>();
    private final java.util.Set<String> remoteAsked = new java.util.HashSet<>();

    private final Activity a;
    private final Store store;
    private final OnPick onPick;
    private final OnPick onLong;
    final LinearLayout view;
    private final TextView status;
    private final LinearLayout list;
    final List<Frame> frames = new ArrayList<>();
    private Discovery discovery;
    private boolean scanning;

    FramePicker(Activity a, Store store, OnPick onPick, OnPick onLong) {
        this.a = a;
        this.store = store;
        this.onPick = onPick;
        this.onLong = onLong;
        view = Ui.column(a);
        list = Ui.column(a);
        view.addView(list);
        status = Ui.text(a, "", 14, Ui.MUTED, false);
        status.setPadding(Ui.dp(a, 4), Ui.dp(a, 2), 0, Ui.dp(a, 6));
        view.addView(status);
        reload();
    }

    void reload() {
        List<Frame> saved = store.saved();
        List<Frame> keep = new ArrayList<>();
        for (Frame s : saved) {
            for (Frame o : frames) if (o.host.equals(s.host)) { s.state = o.state; }
            keep.add(s);
        }
        for (Frame o : frames) {
            boolean known = false;
            for (Frame s : keep) if (s.host.equals(o.host) || (o.id != null && o.id.equals(s.id))) known = true;
            if (!known) keep.add(o);
        }
        frames.clear();
        frames.addAll(keep);
        render();
    }

    void scan() {
        if (scanning) return;
        scanning = true;
        remoteAsked.clear();
        status.setText(R.string.searching);
        for (Frame f : frames) if (f.state == Frame.OFFLINE) f.state = Frame.UNKNOWN;
        List<String> extra = new ArrayList<>();
        for (Frame f : frames) extra.add(f.host);
        discovery = new Discovery(a, this);
        discovery.start(extra);
        // Frames with a login answer the search only with "login needed"; ask them with the
        // saved key which other frames they know (DynaFrame keeps a list of its neighbours).
        for (final Frame f : new ArrayList<>(frames)) {
            if (!f.saved || !f.hasLogin()) continue;
            final Discovery d = discovery;
            new Thread(new Runnable() {
                @Override public void run() {
                    final Api api = new Api(f);
                    try {
                        org.json.JSONObject st = api.with(new Api.Call<org.json.JSONObject>() {
                            @Override public org.json.JSONObject run() throws java.io.IOException {
                                return api.http.obj("GET", "/engine-proxy/sync/status", null);
                            }
                        });
                        // the frame answered with the saved key: it is online, whatever the plain search says
                        String id = st.optString("frameId", "");
                        final Frame ok = new Frame(f.host, st.optString("frameName", f.name));
                        if (!id.isEmpty()) ok.id = id;
                        ok.state = Frame.OK;
                        ok.https = f.https;
                        a.runOnUiThread(new Runnable() { @Override public void run() { onFrame(ok); } });
                        List<String[]> hints = new ArrayList<>();
                        Discovery.collectHints(st.opt("discoveredFrames"), hints);
                        List<String> hosts = new ArrayList<>();
                        for (String[] h : hints) hosts.add(h[0]);
                        d.addHosts(hosts);
                    } catch (Exception ignored) {
                    }
                }
            }).start();
        }
        render();
    }

    void stop() {
        if (discovery != null) discovery.stop();
        scanning = false;
    }

    @Override public void onFrame(Frame found) {
        Frame known = null;
        for (Frame f : frames) {
            if (f.host.equals(found.host) || (found.id != null && found.id.equals(f.id))) { known = f; break; }
        }
        if (known == null) {
            if (found.state == Frame.OFFLINE) return;   // only show unknown hosts that are really frames
            frames.add(found);
        } else {
            known.merge(found);
            if (known.saved) store.save(known, false);
        }
        lookForRemotes(known == null ? found : known);
        render();
    }

    /** Ask a reachable frame which remote frames it offers (GET remote-frame/settings). */
    private void lookForRemotes(final Frame f) {
        boolean reach = f.state == Frame.OK || f.state == Frame.LOGIN && f.hasLogin();
        if (!reach || !remoteAsked.add(f.host)) return;
        new Thread(new Runnable() {
            @Override public void run() {
                final List<Remote> out = new ArrayList<>();
                try {
                    final Api api = new Api(f);
                    org.json.JSONObject o = api.with(new Api.Call<org.json.JSONObject>() {
                        @Override public org.json.JSONObject run() throws java.io.IOException {
                            return api.http.obj("GET", "/engine-proxy/remote-frame/settings", null);
                        }
                    });
                    org.json.JSONArray arr = o.optJSONArray("frames");
                    if (arr != null) {
                        for (int i = 0; i < arr.length(); i++) {
                            org.json.JSONObject r = arr.optJSONObject(i);
                            if (r == null || !r.has("id")) continue;
                            out.add(new Remote(r.optInt("id"), r.optString("name", "").trim(), r.optBoolean("enabled", true)));
                        }
                    } else if (o.has("enabled")) {
                        out.add(new Remote(-1, "", o.optBoolean("enabled")));
                    }
                } catch (Exception ignored) {
                }
                a.runOnUiThread(new Runnable() {
                    @Override public void run() {
                        if (out.isEmpty()) remotes.remove(f.host); else remotes.put(f.host, out);
                        render();
                    }
                });
            }
        }).start();
    }

    private Frame frameFor(String host) {
        for (Frame f : frames) if (f.host.equals(host)) return f;
        return null;
    }

    private void renderRemotes() {
        LinearLayout card = null;
        for (java.util.Map.Entry<String, List<Remote>> e : remotes.entrySet()) {
            final Frame f = frameFor(e.getKey());
            if (f == null) continue;
            for (final Remote rm : e.getValue()) {
                if (card == null) {
                    TextView h = Ui.text(a, a.getString(R.string.remote_frames), 13, Ui.MUTED, true);
                    h.setPadding(Ui.dp(a, 6), Ui.dp(a, 14), 0, Ui.dp(a, 8));
                    list.addView(h);
                    card = Ui.column(a);
                    card.setBackground(Ui.glass(a, 22));
                    card.setPadding(Ui.dp(a, 14), Ui.dp(a, 2), Ui.dp(a, 12), Ui.dp(a, 2));
                }
                if (card.getChildCount() > 0) Ui.separator(a, card, 54);
                final String title = !rm.name.isEmpty() ? rm.name
                        : rm.id < 0 ? a.getString(R.string.remote_frames) : a.getString(R.string.remote_name, rm.id);
                LinearLayout r = Ui.row(a);
                r.setPadding(0, Ui.dp(a, 12), 0, Ui.dp(a, 12));
                TextView tile = Ui.tile(a, Ui.I_LAYERS);
                tile.setTextSize(17);
                r.addView(tile, new LinearLayout.LayoutParams(Ui.dp(a, 40), Ui.dp(a, 40)));
                LinearLayout texts = Ui.column(a);
                texts.setPadding(Ui.dp(a, 14), 0, Ui.dp(a, 8), 0);
                TextView n = Ui.text(a, title, 16, Ui.TEXT, false);
                n.setSingleLine(true);
                n.setEllipsize(android.text.TextUtils.TruncateAt.END);
                texts.addView(n);
                String sub = a.getString(R.string.remote_on, f.name) + (rm.enabled ? "" : " · " + a.getString(R.string.remote_off));
                TextView s = Ui.text(a, sub, 13, Ui.MUTED, false);
                s.setSingleLine(true);
                texts.addView(s);
                r.addView(texts, new LinearLayout.LayoutParams(0, -2, 1f));
                TextView ch = Ui.icon(a, Ui.I_RIGHT, 13, Ui.MUTED);
                ch.setPadding(Ui.dp(a, 12), 0, Ui.dp(a, 2), 0);
                r.addView(ch);
                if (!rm.enabled) r.setAlpha(0.6f);
                r.setOnClickListener(new View.OnClickListener() {
                    @Override public void onClick(View v) {
                        if (onRemote != null) onRemote.pick(f, rm.id < 0 ? "/RemoteFrame" : "/RemoteFrame/" + rm.id, title);
                    }
                });
                card.addView(r);
            }
        }
        if (card != null) list.addView(card, Ui.full(a, 8));
    }

    @Override public void onHint(String host, String name, String id) { }

    @Override public void onDone() {
        scanning = false;
        int n = 0;
        for (Frame f : frames) if (f.state == Frame.OK || f.state == Frame.LOGIN) n++;
        status.setText(n == 0 ? a.getString(R.string.found_none) : a.getResources().getQuantityString(R.plurals.found_n, n, n));
        if (n == 0) { status.setVisibility(View.VISIBLE); }
        for (Frame f : frames) if (f.state == Frame.UNKNOWN) f.state = Frame.OFFLINE;
        render();
    }

    void render() {
        list.removeAllViews();
        if (frames.isEmpty()) {
            if (scanning) status.setText(R.string.searching);
            status.setVisibility(View.VISIBLE);
            return;
        }
        LinearLayout card = Ui.column(a);
        card.setBackground(Ui.glass(a, 22));
        card.setPadding(Ui.dp(a, 14), Ui.dp(a, 2), Ui.dp(a, 12), Ui.dp(a, 2));
        for (final Frame f : frames) {
            if (card.getChildCount() > 0) Ui.separator(a, card, 54);
            LinearLayout r = Ui.row(a);
            r.setPadding(0, Ui.dp(a, 13), 0, Ui.dp(a, 13));
            TextView tile = Ui.tile(a, Ui.I_DISPLAY);
            tile.setTextSize(18);
            r.addView(tile, new LinearLayout.LayoutParams(Ui.dp(a, 40), Ui.dp(a, 40)));
            LinearLayout texts = Ui.column(a);
            texts.setPadding(Ui.dp(a, 14), 0, Ui.dp(a, 8), 0);
            TextView n = Ui.text(a, f.name, 17, Ui.TEXT, true);
            n.setSingleLine(true);
            n.setEllipsize(android.text.TextUtils.TruncateAt.END);
            texts.addView(n);
            // second line only when something needs attention
            String note = null;
            int noteColor = Ui.MUTED;
            if (f.state == Frame.LOGIN && !f.hasLogin()) { note = a.getString(R.string.login_needed); noteColor = Ui.ACCENT; }
            else if (f.state == Frame.OFFLINE) note = a.getString(R.string.not_reachable);
            if (note != null) texts.addView(Ui.text(a, note, 13, noteColor, false));
            r.addView(texts, new LinearLayout.LayoutParams(0, -2, 1f));
            // status dot: green online, grey offline, gold login, dim while checking
            View dot = new View(a);
            android.graphics.drawable.GradientDrawable g = new android.graphics.drawable.GradientDrawable();
            g.setShape(android.graphics.drawable.GradientDrawable.OVAL);
            boolean on = f.state == Frame.OK || f.state == Frame.LOGIN && f.hasLogin();
            g.setColor(on ? Ui.GOOD : f.state == Frame.LOGIN ? Ui.ACCENT : f.state == Frame.OFFLINE ? Ui.BAD : Ui.MUTED);
            dot.setBackground(g);
            if (!on && f.state != Frame.OFFLINE && f.state != Frame.LOGIN) dot.setAlpha(0.5f);
            r.addView(dot, new LinearLayout.LayoutParams(Ui.dp(a, 9), Ui.dp(a, 9)));
            TextView ch = Ui.icon(a, Ui.I_RIGHT, 13, Ui.MUTED);
            ch.setPadding(Ui.dp(a, 12), 0, Ui.dp(a, 2), 0);
            r.addView(ch);
            if (f.state == Frame.OFFLINE) r.setAlpha(0.6f);
            r.setBackground(new android.graphics.drawable.RippleDrawable(android.content.res.ColorStateList.valueOf(android.graphics.Color.argb(40, 255, 255, 255)),
                    null, new android.graphics.drawable.ColorDrawable(android.graphics.Color.WHITE)));
            r.setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View v) { onPick.pick(f); }
            });
            if (onLong != null) r.setOnLongClickListener(new View.OnLongClickListener() {
                @Override public boolean onLongClick(View v) { onLong.pick(f); return true; }
            });
            card.addView(r);
        }
        list.addView(card, Ui.full(a, 8));
        renderRemotes();
        // the "found n frames" line only while searching or when nothing answered
        boolean any = false;
        for (Frame f : frames) if (f.state == Frame.OK || f.state == Frame.LOGIN) any = true;
        status.setVisibility(scanning || !any ? View.VISIBLE : View.GONE);
    }
}
