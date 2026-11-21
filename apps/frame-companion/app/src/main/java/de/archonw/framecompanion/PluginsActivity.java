package de.archonw.framecompanion;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.DialogInterface;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;

/** The frame's plugins like on the web UI's Plugins page: switch on/off, open settings, restart. */
public class PluginsActivity extends Activity {

    private Frame f;
    private final Handler main = new Handler(Looper.getMainLooper());
    private LinearLayout list;
    private TextView status;
    private EditText search;
    private int filter;   // 0 all, 1 on, 2 off
    private final List<JSONObject> plugins = new ArrayList<>();

    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        f = new Store(this).find(getIntent().getStringExtra("host"));
        if (f == null) { finish(); return; }
        LinearLayout root = Ui.page(this);
        status = Ui.header(this, root, getString(R.string.more_plugins), f.name + " · " + getString(R.string.connecting));
        search = searchField(this, root, R.string.plugins_search, new Runnable() { @Override public void run() { render(); } });
        root.addView(Ui.segmented(this, new String[]{getString(R.string.pl_seg_all), getString(R.string.plugins_on), getString(R.string.plugins_off)}, 0,
                new Ui.Segment() { @Override public void selected(int i) { filter = i; render(); } }), Ui.full(this, 10));
        list = Ui.column(this);
        root.addView(list);
        PullScroll.on(root, new Runnable() { @Override public void run() { load(); } });
        load();
    }

    /** Frosted search field; shared with the store page. */
    static EditText searchField(Activity a, LinearLayout root, int hint, final Runnable changed) {
        LinearLayout sr = Ui.row(a);
        android.graphics.drawable.GradientDrawable sg = new android.graphics.drawable.GradientDrawable();
        sg.setColor(android.graphics.Color.argb(30, 255, 255, 255));
        sg.setCornerRadius(Ui.dp(a, 12));
        sr.setBackground(sg);
        sr.setPadding(Ui.dp(a, 12), 0, Ui.dp(a, 12), 0);
        sr.addView(Ui.icon(a, Ui.I_SEARCH, 15, Ui.MUTED));
        EditText e = new EditText(a);
        e.setHint(hint);
        e.setHintTextColor(Ui.MUTED);
        e.setTextColor(Ui.TEXT);
        e.setTypeface(Ui.font(a, 0));
        e.setTextSize(16);
        e.setSingleLine(true);
        e.setBackground(null);
        e.setPadding(Ui.dp(a, 8), Ui.dp(a, 9), 0, Ui.dp(a, 9));
        e.addTextChangedListener(new android.text.TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int x, int y, int z) { }
            @Override public void onTextChanged(CharSequence s, int x, int y, int z) { }
            @Override public void afterTextChanged(android.text.Editable ed) { changed.run(); }
        });
        sr.addView(e, new LinearLayout.LayoutParams(0, -2, 1f));
        root.addView(sr, Ui.full(a, 12));
        return e;
    }

    private void load() {
        new Thread(new Runnable() {
            @Override public void run() {
                final Api api = new Api(f);
                try {
                    final JSONArray a = api.with(new Api.Call<JSONArray>() {
                        @Override public JSONArray run() throws IOException { return new Sources(f).plugins(); }
                    });
                    main.post(new Runnable() {
                        @Override public void run() {
                            plugins.clear();
                            for (int i = 0; i < a.length(); i++) if (a.optJSONObject(i) != null) plugins.add(a.optJSONObject(i));
                            Collections.sort(plugins, new Comparator<JSONObject>() {
                                @Override public int compare(JSONObject x, JSONObject y) { return name(x).compareToIgnoreCase(name(y)); }
                            });
                            int on = 0;
                            for (JSONObject p : plugins) if (p.optBoolean("enabled")) on++;
                            status.setText(f.name + " · " + getString(R.string.plugins_count, plugins.size(), on));
                            render();
                        }
                    });
                } catch (final IOException e) {
                    main.post(new Runnable() { @Override public void run() { status.setText(f.name + " · " + e.getMessage()); } });
                }
            }
        }).start();
    }

    private static String name(JSONObject p) {
        String n = p.optString("displayName", "");
        return n.isEmpty() ? p.optString("name") : n;
    }

    private void render() {
        list.removeAllViews();
        String q = search.getText().toString().trim().toLowerCase(Locale.ROOT);
        LinearLayout card = null;
        int shown = 0;
        for (final JSONObject p : plugins) {
            boolean on = p.optBoolean("enabled");
            if (filter == 1 && !on || filter == 2 && on) continue;
            if (!q.isEmpty() && !(name(p) + " " + p.optString("description")).toLowerCase(Locale.ROOT).contains(q)) continue;
            if (card == null) {
                card = Ui.column(this);
                card.setBackground(Ui.glass(this, 22));
                card.setPadding(Ui.dp(this, 14), Ui.dp(this, 2), Ui.dp(this, 12), Ui.dp(this, 2));
            }
            row(card, p);
            shown++;
        }
        if (card != null) list.addView(card, Ui.full(this, 8));
        if (shown == 0 && !plugins.isEmpty()) {
            TextView none = Ui.text(this, getString(R.string.plugins_none), 14, Ui.MUTED, false);
            none.setPadding(Ui.dp(this, 6), Ui.dp(this, 8), 0, 0);
            list.addView(none);
        }
    }

    private String state(JSONObject p) {
        if (!p.optBoolean("isCompatible", true)) return getString(R.string.plugin_incompatible);
        if (!p.optBoolean("enabled")) return getString(R.string.plugin_off);
        if (p.optBoolean("running") || p.optBoolean("ready")) return getString(R.string.plugin_running);
        String lc = p.optString("lifecycleState", "");
        return lc.isEmpty() ? getString(R.string.plugin_stopped) : lc;
    }

    private void row(LinearLayout card, final JSONObject p) {
        if (card.getChildCount() > 0) Ui.separator(this, card, 52);
        final String title = name(p);
        LinearLayout r = Ui.row(this);
        r.setPadding(0, Ui.dp(this, 10), 0, Ui.dp(this, 10));
        TextView tile = Ui.text(this, title.isEmpty() ? "?" : title.substring(0, 1).toUpperCase(Locale.ROOT), 17, Ui.ACCENT, true);
        tile.setGravity(android.view.Gravity.CENTER);
        android.graphics.drawable.GradientDrawable tg = new android.graphics.drawable.GradientDrawable();
        tg.setColor(android.graphics.Color.argb(40, 216, 161, 59));
        tg.setCornerRadius(Ui.dp(this, 10));
        tile.setBackground(tg);
        r.addView(tile, new LinearLayout.LayoutParams(Ui.dp(this, 40), Ui.dp(this, 40)));
        LinearLayout texts = Ui.column(this);
        texts.setPadding(Ui.dp(this, 12), 0, Ui.dp(this, 8), 0);
        TextView n = Ui.text(this, title, 16, Ui.TEXT, false);
        n.setSingleLine(true);
        n.setEllipsize(android.text.TextUtils.TruncateAt.END);
        texts.addView(n);
        String sub = p.optString("version", "") + " · " + state(p);
        TextView s = Ui.text(this, sub, 13, p.optBoolean("isCompatible", true) ? Ui.MUTED : Ui.BAD, false);
        s.setSingleLine(true);
        texts.addView(s);
        r.addView(texts, new LinearLayout.LayoutParams(0, -2, 1f));
        TextView gear = Ui.iconButton(this, Ui.I_GEAR, 18, Ui.MUTED);
        gear.setPadding(Ui.dp(this, 8), Ui.dp(this, 6), Ui.dp(this, 10), Ui.dp(this, 6));
        gear.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { WebActivity.open(PluginsActivity.this, f, Sources.pluginPage(p), title); }
        });
        r.addView(gear);
        Ui.Switch sw = new Ui.Switch(this, p.optBoolean("enabled"));
        sw.listener = new Ui.Switch.OnChange() {
            @Override public void changed(final boolean on) {
                try { p.put("enabled", on); } catch (Exception ignored) { }
                call(new Api.Call<Void>() {
                    @Override public Void run() throws IOException { new Api(f).setPluginEnabled(p.optString("name"), on); return null; }
                }, on ? R.string.plugin_turned_on : R.string.plugin_turned_off, title);
            }
        };
        r.addView(sw, new LinearLayout.LayoutParams(Ui.dp(this, 51), Ui.dp(this, 31)));
        r.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { details(p, title); }
        });
        card.addView(r);
    }

    private void details(final JSONObject p, final String title) {
        String msg = p.optString("description", "") + "\n\n" + getString(R.string.plugin_by, p.optString("author", "?"), p.optString("version", ""))
                + "\n" + state(p);
        new AlertDialog.Builder(this).setTitle(title).setMessage(msg.trim())
                .setPositiveButton(R.string.src_open_settings, new DialogInterface.OnClickListener() {
                    @Override public void onClick(DialogInterface d, int w) { WebActivity.open(PluginsActivity.this, f, Sources.pluginPage(p), title); }
                })
                .setNeutralButton(R.string.plugin_restart, new DialogInterface.OnClickListener() {
                    @Override public void onClick(DialogInterface d, int w) {
                        call(new Api.Call<Void>() {
                            @Override public Void run() throws IOException { new Api(f).restartPlugin(p.optString("name")); return null; }
                        }, R.string.plugin_restarted, title);
                    }
                })
                .setNegativeButton(R.string.cancel, null).show();
    }

    private void call(final Api.Call<Void> c, final int done, final String title) {
        new Thread(new Runnable() {
            @Override public void run() {
                try {
                    new Api(f).with(c);
                    main.post(new Runnable() { @Override public void run() { Ui.toast(PluginsActivity.this, getString(done, title)); } });
                    main.postDelayed(new Runnable() { @Override public void run() { if (!isFinishing()) load(); } }, 2500);
                } catch (final IOException e) {
                    main.post(new Runnable() {
                        @Override public void run() {
                            Ui.toast(PluginsActivity.this, getString(R.string.not_reachable_detail, e.getMessage()));
                            load();
                        }
                    });
                }
            }
        }).start();
    }
}
