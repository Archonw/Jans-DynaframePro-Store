package de.archonw.framecompanion;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.DialogInterface;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/** The stores the frame knows, like the web UI's Store page: install, update, open settings. */
public class StoreActivity extends Activity {

    private Frame f;
    private final Handler main = new Handler(Looper.getMainLooper());
    private LinearLayout list;
    private TextView status;
    private EditText search;
    private int filter;   // 0 all, 1 installed, 2 updates
    private List<Sources.Pack> packs = new ArrayList<>();
    private Map<String, String> installed = new HashMap<>();

    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        f = new Store(this).find(getIntent().getStringExtra("host"));
        if (f == null) { finish(); return; }
        LinearLayout root = Ui.page(this);
        status = Ui.header(this, root, getString(R.string.more_store), f.name + " · " + getString(R.string.store_loading));
        search = PluginsActivity.searchField(this, root, R.string.store_search, new Runnable() { @Override public void run() { render(); } });
        root.addView(Ui.segmented(this, new String[]{getString(R.string.pl_seg_all), getString(R.string.store_installed), getString(R.string.store_updates)}, 0,
                new Ui.Segment() { @Override public void selected(int i) { filter = i; render(); } }), Ui.full(this, 10));
        list = Ui.column(this);
        root.addView(list);
        PullScroll.on(root, new Runnable() { @Override public void run() { status.setText(f.name + " · " + getString(R.string.store_loading)); load(); } });
        load();
    }

    private void load() {
        new Thread(new Runnable() {
            @Override public void run() {
                final Api api = new Api(f);
                try {
                    final List<Sources.Pack> p = api.with(new Api.Call<List<Sources.Pack>>() {
                        @Override public List<Sources.Pack> run() throws java.io.IOException { return new Sources(f).storePacks(); }
                    });
                    final Map<String, String> inst = new Sources(f).installedPacks();
                    main.post(new Runnable() {
                        @Override public void run() {
                            // one entry per pack id: the first (enabled) store wins
                            Map<String, Sources.Pack> uniq = new java.util.LinkedHashMap<>();
                            for (Sources.Pack k : p) if (!uniq.containsKey(k.id.toLowerCase(Locale.ROOT))) uniq.put(k.id.toLowerCase(Locale.ROOT), k);
                            packs = new ArrayList<>(uniq.values());
                            Collections.sort(packs, new Comparator<Sources.Pack>() {
                                @Override public int compare(Sources.Pack a, Sources.Pack b) { return a.title.compareToIgnoreCase(b.title); }
                            });
                            installed = inst;
                            int upd = 0;
                            for (Sources.Pack k : packs) if (update(k)) upd++;
                            status.setText(f.name + " · " + getString(R.string.store_count, packs.size(), upd));
                            render();
                        }
                    });
                } catch (final Exception e) {
                    main.post(new Runnable() { @Override public void run() { status.setText(f.name + " · " + e.getMessage()); } });
                }
            }
        }).start();
    }

    private String have(Sources.Pack p) { return installed.get(p.id.toLowerCase(Locale.ROOT)); }

    private boolean update(Sources.Pack p) { String h = have(p); return h != null && !h.isEmpty() && Api.newer(p.version, h); }

    private void render() {
        list.removeAllViews();
        String q = search.getText().toString().trim().toLowerCase(Locale.ROOT);
        LinearLayout card = null;
        for (final Sources.Pack p : packs) {
            if (filter == 1 && have(p) == null || filter == 2 && !update(p)) continue;
            if (!q.isEmpty() && !(p.title + " " + p.description + " " + p.author).toLowerCase(Locale.ROOT).contains(q)) continue;
            if (card == null) {
                card = Ui.column(this);
                card.setBackground(Ui.glass(this, 22));
                card.setPadding(Ui.dp(this, 14), Ui.dp(this, 2), Ui.dp(this, 12), Ui.dp(this, 2));
            }
            row(card, p);
        }
        if (card != null) list.addView(card, Ui.full(this, 8));
        else if (!packs.isEmpty()) {
            TextView none = Ui.text(this, getString(R.string.plugins_none), 14, Ui.MUTED, false);
            none.setPadding(Ui.dp(this, 6), Ui.dp(this, 8), 0, 0);
            list.addView(none);
        }
    }

    private void row(LinearLayout card, final Sources.Pack p) {
        if (card.getChildCount() > 0) Ui.separator(this, card, 52);
        LinearLayout r = Ui.row(this);
        r.setPadding(0, Ui.dp(this, 11), 0, Ui.dp(this, 11));
        TextView tile = Ui.text(this, p.title.isEmpty() ? "?" : p.title.substring(0, 1).toUpperCase(Locale.ROOT), 17, Ui.ACCENT, true);
        tile.setGravity(Gravity.CENTER);
        android.graphics.drawable.GradientDrawable tg = new android.graphics.drawable.GradientDrawable();
        tg.setColor(android.graphics.Color.argb(40, 216, 161, 59));
        tg.setCornerRadius(Ui.dp(this, 10));
        tile.setBackground(tg);
        LinearLayout.LayoutParams tl = new LinearLayout.LayoutParams(Ui.dp(this, 40), Ui.dp(this, 40));
        tl.gravity = Gravity.TOP;
        r.addView(tile, tl);
        LinearLayout texts = Ui.column(this);
        texts.setPadding(Ui.dp(this, 12), 0, Ui.dp(this, 8), 0);
        TextView n = Ui.text(this, p.title, 16, Ui.TEXT, false);
        n.setSingleLine(true);
        n.setEllipsize(android.text.TextUtils.TruncateAt.END);
        texts.addView(n);
        if (!p.description.isEmpty()) {
            TextView d = Ui.text(this, p.description, 13, Ui.MUTED, false);
            d.setMaxLines(2);
            d.setEllipsize(android.text.TextUtils.TruncateAt.END);
            texts.addView(d);
        }
        TextView meta = Ui.text(this, p.version + " · " + p.storeName, 12, Ui.MUTED, false);
        meta.setSingleLine(true);
        meta.setPadding(0, Ui.dp(this, 2), 0, 0);
        texts.addView(meta);
        r.addView(texts, new LinearLayout.LayoutParams(0, -2, 1f));
        String h = have(p);
        boolean upd = update(p);
        TextView b = Ui.text(this, h == null ? getString(R.string.store_get) : upd ? getString(R.string.store_update) : getString(R.string.store_open), 13,
                h == null || upd ? Ui.ON_ACCENT : Ui.ACCENT, true);
        android.graphics.drawable.GradientDrawable bg = new android.graphics.drawable.GradientDrawable();
        bg.setCornerRadius(Ui.dp(this, 20));
        bg.setColor(h == null || upd ? Ui.ACCENT : android.graphics.Color.argb(40, 216, 161, 59));
        b.setBackground(bg);
        b.setPadding(Ui.dp(this, 14), Ui.dp(this, 6), Ui.dp(this, 14), Ui.dp(this, 6));
        b.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { if (have(p) == null || update(p)) confirm(p); else openSettings(p); }
        });
        r.addView(b);
        r.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { confirm(p); }
        });
        card.addView(r);
    }

    private void confirm(final Sources.Pack p) {
        final String h = have(p);
        boolean upd = update(p);
        String msg = p.description + "\n\n" + getString(R.string.src_install_from, p.storeName, p.author.isEmpty() ? "?" : p.author)
                + (h != null ? "\n" + getString(R.string.store_have, h) : "")
                + (p.storeEnabled ? "" : "\n\n" + getString(R.string.src_store_off, p.storeName));
        AlertDialog.Builder b = new AlertDialog.Builder(this).setTitle(p.title + " " + p.version).setMessage(msg);
        if (h == null || upd) b.setPositiveButton(h == null ? R.string.src_install : R.string.store_update, new DialogInterface.OnClickListener() {
            @Override public void onClick(DialogInterface d, int w) { install(p, h); }
        });
        if (h != null) b.setNeutralButton(R.string.src_open_settings, new DialogInterface.OnClickListener() {
            @Override public void onClick(DialogInterface d, int w) { openSettings(p); }
        });
        b.setNegativeButton(R.string.cancel, null).show();
    }

    private AlertDialog waiting(String text) {
        LinearLayout l = Ui.row(this);
        int pd = Ui.dp(this, 22);
        l.setPadding(pd, pd, pd, pd);
        ProgressBar pb = new ProgressBar(this);
        pb.setIndeterminateTintList(android.content.res.ColorStateList.valueOf(Ui.ACCENT));
        l.addView(pb);
        TextView tv = Ui.text(this, text, 15, Ui.TEXT, false);
        tv.setPadding(Ui.dp(this, 16), 0, 0, 0);
        l.addView(tv, new LinearLayout.LayoutParams(0, -2, 1f));
        // never lock the user in: the install keeps running on the frame, the dialog can be hidden
        AlertDialog d = new AlertDialog.Builder(this).setView(l).setCancelable(true)
                .setNegativeButton(R.string.store_hide, null).create();
        d.show();
        return d;
    }

    private void install(final Sources.Pack p, final String previous) {
        final AlertDialog wait = waiting(getString(R.string.src_installing, p.title));
        wait.setOnCancelListener(new DialogInterface.OnCancelListener() {
            @Override public void onCancel(DialogInterface d) { Ui.toast(StoreActivity.this, getString(R.string.store_background, p.title)); }
        });
        new Thread(new Runnable() {
            @Override public void run() {
                try {
                    final Api api = new Api(f);
                    api.with(new Api.Call<Void>() {
                        @Override public Void run() throws java.io.IOException { new Sources(f).install(p, previous); return null; }
                    });
                    String[] pl = null;
                    if (!"dynamic".equals(p.type)) for (int i = 0; i < 25; i++) {
                        pl = new Sources(f).pluginFor(p);
                        if (pl != null && "1".equals(pl[2])) break;
                        Thread.sleep(2000);
                    }
                    final String[] plugin = pl;
                    main.post(new Runnable() {
                        @Override public void run() {
                            boolean shown = wait.isShowing();
                            try { wait.dismiss(); } catch (Exception ignored) { }
                            installed.put(p.id.toLowerCase(Locale.ROOT), p.version);
                            render();
                            if (isFinishing() || !shown || plugin == null) { Ui.toast(StoreActivity.this, getString(R.string.store_done, p.title)); return; }
                            new AlertDialog.Builder(StoreActivity.this).setTitle(R.string.src_installed)
                                    .setMessage(getString(R.string.src_installed_text, p.title))
                                    .setPositiveButton(R.string.src_open_settings, new DialogInterface.OnClickListener() {
                                        @Override public void onClick(DialogInterface d, int w) { WebActivity.open(StoreActivity.this, f, plugin[1], p.title); }
                                    }).setNegativeButton(R.string.src_later, null).show();
                        }
                    });
                } catch (final Exception e) {
                    main.post(new Runnable() {
                        @Override public void run() {
                            try { wait.dismiss(); } catch (Exception ignored) { }
                            load();   // the frame may have finished anyway
                            if (isFinishing()) return;
                            new AlertDialog.Builder(StoreActivity.this).setTitle(R.string.src_err_title)
                                    .setMessage(getString(R.string.store_failed, p.title, String.valueOf(e.getMessage())))
                                    .setPositiveButton(R.string.ok, null).show();
                        }
                    });
                }
            }
        }).start();
    }

    private void openSettings(final Sources.Pack p) {
        new Thread(new Runnable() {
            @Override public void run() {
                String[] pl = null;
                try { pl = new Sources(f).pluginFor(p); } catch (Exception ignored) { }
                final String page = pl == null ? "/Plugins" : pl[1];
                main.post(new Runnable() {
                    @Override public void run() { WebActivity.open(StoreActivity.this, f, page, p.title); }
                });
            }
        }).start();
    }
}
