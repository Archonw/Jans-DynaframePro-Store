package de.archonw.framecompanion;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.DialogInterface;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.View;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.IOException;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * "How do my photos get onto the frame?" The person ticks where their photos are; what DynaFrame
 * can do itself (NAS/SMB, WebDAV/Nextcloud, USB) is set up right here, everything else is looked
 * up in the frame's stores, installed as a plugin and its settings page opened.
 */
public class SourcesActivity extends Activity {

    /** One answer to "where are your photos?". */
    private static final class Wish {
        final String id; final int icon, title, sub; final boolean builtIn;
        final String[] packIds, keywords;
        Wish(String id, int icon, int title, int sub, boolean builtIn, String[] packIds, String[] keywords) {
            this.id = id; this.icon = icon; this.title = title; this.sub = sub; this.builtIn = builtIn; this.packIds = packIds; this.keywords = keywords;
        }
    }

    private static final int I_NAS = 0xf40d, I_CLOUD = 0xf2c1, I_USB = 0xf6f2, I_PHONE = 0xf4e7, I_SERVER = 0xf52c,
            I_SEND = 0xf6c0, I_CHECKSQ = 0xf26d, I_SQUARE = 0xf584, I_CLOUD_DOWN = 0xf295, I_PUZZLE = 0xf503, I_WARN = 0xf33b;

    private static final Wish[] WISHES = {
            new Wish("phone", I_PHONE, R.string.src_phone, R.string.src_phone_sub, true, null, null),
            new Wish("nas", I_NAS, R.string.src_nas, R.string.src_nas_sub, true, null, null),
            new Wish("webdav", I_CLOUD, R.string.src_webdav, R.string.src_webdav_sub, true, null, null),
            new Wish("usb", I_USB, R.string.src_usb, R.string.src_usb_sub, true, null, null),
            new Wish("immich", I_SERVER, R.string.src_immich, R.string.src_immich_sub, false, new String[]{"immich"}, new String[]{"immich"}),
            new Wish("icloud", I_CLOUD_DOWN, R.string.src_icloud, R.string.src_icloud_sub, false, new String[]{"cloud-folder-sync"}, new String[]{"icloud"}),
            new Wish("gdrive", I_CLOUD_DOWN, R.string.src_gdrive, R.string.src_gdrive_sub, false, new String[]{"cloud-folder-sync"}, new String[]{"google drive", "onedrive", "dropbox"}),
            new Wish("gphotos", I_CLOUD_DOWN, R.string.src_gphotos, R.string.src_gphotos_sub, false, null, new String[]{"google photos", "google fotos"}),
            new Wish("messenger", I_SEND, R.string.src_messenger, R.string.src_messenger_sub, false, new String[]{"telegram-photos"}, new String[]{"telegram"}),
    };

    private Frame f;
    private Store store;
    private final Handler main = new Handler(Looper.getMainLooper());
    private LinearLayout body;
    private final Set<String> chosen = new LinkedHashSet<>();
    private List<Sources.Pack> packs;
    private String packsError;

    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        store = new Store(this);
        f = store.find(getIntent().getStringExtra("host"));
        if (f == null) { finish(); return; }
        LinearLayout root = Ui.page(this, f, Ui.TAB_SOURCES);
        root.addView(Ui.title(this, getString(R.string.src_title), 34));
        TextView sub = Ui.text(this, f.name, 14, Ui.MUTED, false);
        sub.setPadding(0, Ui.dp(this, 2), 0, Ui.dp(this, 14));
        root.addView(sub);
        body = Ui.column(this);
        root.addView(body);
        showChoice();
        PullScroll.on(root, new Runnable() { @Override public void run() { loadPacks(); } });
        loadPacks();
    }

    // ------------------------------------------------------------------ helpers

    interface Job<T> { T run() throws Exception; }
    interface Then<T> { void done(T r); }

    private <T> void bg(final String waitText, final Job<T> job, final Then<T> then) {
        final AlertDialog wait = waitText == null ? null : waiting(waitText);
        new Thread(new Runnable() {
            @Override public void run() {
                try {
                    final T r = job.run();
                    main.post(new Runnable() { @Override public void run() { dismiss(wait); if (!isFinishing()) then.done(r); } });
                } catch (final Exception e) {
                    main.post(new Runnable() { @Override public void run() { dismiss(wait); if (!isFinishing()) error(e); } });
                }
            }
        }).start();
    }

    private static void dismiss(AlertDialog d) { try { if (d != null) d.dismiss(); } catch (Exception ignored) { } }

    private AlertDialog waiting(String text) {
        LinearLayout l = Ui.row(this);
        int p = Ui.dp(this, 22);
        l.setPadding(p, p, p, p);
        ProgressBar pb = new ProgressBar(this);
        pb.setIndeterminateTintList(android.content.res.ColorStateList.valueOf(Ui.ACCENT));
        l.addView(pb);
        TextView tv = Ui.text(this, text, 15, Ui.TEXT, false);
        tv.setPadding(Ui.dp(this, 16), 0, 0, 0);
        l.addView(tv, new LinearLayout.LayoutParams(0, -2, 1f));
        AlertDialog d = new AlertDialog.Builder(this).setView(l).setCancelable(false).create();
        d.show();
        return d;
    }

    private void error(Exception e) {
        String m = e instanceof Http.HttpException ? ((Http.HttpException) e).message() : e.getMessage();
        if (e instanceof Http.AuthException) m = getString(R.string.src_err_login);
        if (m == null || m.isEmpty()) m = e.getClass().getSimpleName();
        new AlertDialog.Builder(this).setTitle(R.string.src_err_title).setMessage(m).setPositiveButton(R.string.ok, null).show();
    }

    private void info(int title, String msg) {
        new AlertDialog.Builder(this).setTitle(title).setMessage(msg).setPositiveButton(R.string.ok, null).show();
    }

    private EditText field(LinearLayout box, int hint, String value, int type) {
        EditText e = new EditText(this);
        e.setHint(hint);
        e.setSingleLine(true);
        e.setInputType(type);
        if (value != null) e.setText(value);
        box.addView(e);
        return e;
    }

    private LinearLayout form() {
        LinearLayout box = Ui.column(this);
        int p = Ui.dp(this, 20);
        box.setPadding(p, Ui.dp(this, 8), p, 0);
        return box;
    }

    // ------------------------------------------------------------------ step 1: where are your photos?

    private void showChoice() {
        body.removeAllViews();
        // two glass lists: what DynaFrame can do itself, and what needs a plugin
        for (int pass = 0; pass < 2; pass++) {
            body.addView(Ui.section(this, getString(pass == 0 ? R.string.src_sec_builtin : R.string.src_sec_plugin)));
            LinearLayout card = Ui.column(this);
            card.setBackground(Ui.glass(this, 22));
            card.setPadding(Ui.dp(this, 14), Ui.dp(this, 2), Ui.dp(this, 12), Ui.dp(this, 2));
            for (final Wish w : WISHES) {
                if (w.builtIn != (pass == 0)) continue;
                if (card.getChildCount() > 0) Ui.separator(this, card, 52);
                LinearLayout r = Ui.row(this);
                r.setPadding(0, Ui.dp(this, 11), 0, Ui.dp(this, 11));
                TextView tile = Ui.tile(this, w.icon);
                tile.setTextSize(18);
                r.addView(tile, new LinearLayout.LayoutParams(Ui.dp(this, 38), Ui.dp(this, 38)));
                LinearLayout texts = Ui.column(this);
                texts.setPadding(Ui.dp(this, 14), 0, Ui.dp(this, 8), 0);
                texts.addView(Ui.text(this, getString(w.title), 16, Ui.TEXT, false));
                TextView sub = Ui.text(this, getString(w.sub), 13, Ui.MUTED, false);
                sub.setSingleLine(true);
                sub.setEllipsize(android.text.TextUtils.TruncateAt.END);
                texts.addView(sub);
                r.addView(texts, new LinearLayout.LayoutParams(0, -2, 1f));
                final TextView check = Ui.icon(this, 0, 22, Ui.MUTED);
                mark(check, chosen.contains(w.id));
                r.addView(check);
                r.setBackground(new android.graphics.drawable.RippleDrawable(android.content.res.ColorStateList.valueOf(android.graphics.Color.argb(40, 255, 255, 255)),
                        null, new android.graphics.drawable.ColorDrawable(android.graphics.Color.WHITE)));
                r.setOnClickListener(new View.OnClickListener() {
                    @Override public void onClick(View v) {
                        if (!chosen.remove(w.id)) chosen.add(w.id);
                        mark(check, chosen.contains(w.id));
                    }
                });
                card.addView(r);
            }
            body.addView(card, Ui.full(this, 6));
        }
        TextView next = Ui.primary(this, getString(R.string.src_next));
        next.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) {
                if (chosen.isEmpty()) { Ui.toast(SourcesActivity.this, getString(R.string.src_pick_one)); return; }
                showPlan();
            }
        });
        LinearLayout.LayoutParams lp = Ui.full(this, 12);
        lp.topMargin = Ui.dp(this, 16);
        body.addView(next, lp);
    }

    /** Filled gold check circle when chosen, empty circle otherwise. */
    private void mark(TextView t, boolean on) {
        t.setText(Ui.ic(on ? 0xf26a : Ui.I_CIRCLE));
        t.setTextColor(on ? Ui.ACCENT : Ui.MUTED);
    }

    // ------------------------------------------------------------------ step 2: what to do for each

    private void loadPacks() {
        new Thread(new Runnable() {
            @Override public void run() {
                List<Sources.Pack> p = null;
                String err = null;
                try { p = new Sources(f).storePacks(); } catch (Exception e) { err = e.getMessage(); }
                final List<Sources.Pack> fp = p;
                final String fe = err;
                main.post(new Runnable() {
                    @Override public void run() {
                        packs = fp;
                        packsError = fe;
                        if (body.getTag() != null) showPlan();
                    }
                });
            }
        }).start();
    }

    private void showPlan() {
        body.removeAllViews();
        body.setTag("plan");
        TextView back = Ui.text(this, Ui.withIcon(this, 0xf12f, getString(R.string.src_change)), 14, Ui.ACCENT, false);
        back.setPadding(Ui.dp(this, 4), 0, 0, Ui.dp(this, 12));
        back.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { body.setTag(null); showChoice(); }
        });
        body.addView(back);
        for (Wish w : WISHES) if (chosen.contains(w.id)) body.addView(planCard(w), Ui.full(this, 12));
        TextView done = Ui.text(this, getString(R.string.src_done_hint), 13, Ui.MUTED, false);
        done.setPadding(Ui.dp(this, 4), Ui.dp(this, 4), 0, Ui.dp(this, 16));
        body.addView(done);
    }

    private LinearLayout planCard(final Wish w) {
        LinearLayout c = Ui.card(this);
        c.addView(Ui.text(this, Ui.withIcon(this, w.icon, getString(w.title)), 17, Ui.TEXT, true));
        if (w.builtIn) {
            TextView how = Ui.text(this, getString(howText(w.id)), 14, Ui.MUTED, false);
            how.setPadding(0, Ui.dp(this, 6), 0, Ui.dp(this, 10));
            c.addView(how);
            TextView go = Ui.button(this, getString(w.id.equals("phone") ? R.string.src_to_send : R.string.src_setup), 16, Ui.ACCENT, Ui.ON_ACCENT);
            go.setGravity(android.view.Gravity.CENTER);
            go.setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View v) { startBuiltIn(w.id); }
            });
            c.addView(go);
            return c;
        }
        if (packs == null && packsError == null) {
            TextView s = Ui.text(this, getString(R.string.src_searching_store), 14, Ui.MUTED, false);
            s.setPadding(0, Ui.dp(this, 6), 0, 0);
            c.addView(s);
            return c;
        }
        List<Sources.Pack> hits = matches(w);
        if (hits.isEmpty()) {
            TextView s = Ui.text(this, Ui.withIcon(this, I_WARN, getString(noneText(w.id))), 14, Ui.MUTED, false);
            s.setPadding(0, Ui.dp(this, 6), 0, 0);
            c.addView(s);
            return c;
        }
        TextView s = Ui.text(this, getString(R.string.src_found_plugin), 14, Ui.MUTED, false);
        s.setPadding(0, Ui.dp(this, 6), 0, Ui.dp(this, 8));
        c.addView(s);
        for (final Sources.Pack p : hits) {
            android.text.SpannableStringBuilder sb = new android.text.SpannableStringBuilder(Ui.withIcon(this, I_PUZZLE, p.title + "  " + p.version));
            int st = sb.length();
            String d = p.description;
            if (d.length() > 170) d = d.substring(0, 167) + "…";
            sb.append("\n").append(d).append("\n").append(getString(R.string.src_from_store, p.storeName));
            sb.setSpan(new android.text.style.ForegroundColorSpan(Ui.MUTED), st, sb.length(), 0);
            sb.setSpan(new android.text.style.RelativeSizeSpan(0.8f), st, sb.length(), 0);
            TextView b = Ui.button(this, sb, 16, Ui.CARD2, Ui.TEXT);
            b.setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View v) { offerInstall(p); }
            });
            c.addView(b, Ui.full(this, 6));
        }
        return c;
    }

    private List<Sources.Pack> matches(Wish w) {
        List<Sources.Pack> out = new ArrayList<>();
        if (packs == null) return out;
        Set<String> seen = new LinkedHashSet<>();
        if (w.packIds != null) for (String id : w.packIds) for (Sources.Pack p : packs)
            if (p.id.equalsIgnoreCase(id) && seen.add(p.id.toLowerCase(Locale.ROOT))) out.add(p);
        if (w.keywords != null) for (Sources.Pack p : packs) {
            String hay = (p.title + " " + p.description).toLowerCase(Locale.ROOT);
            for (String k : w.keywords) {
                if (hay.contains(k) && p.description.length() > 0 && isSource(hay) && seen.add(p.id.toLowerCase(Locale.ROOT))) { out.add(p); break; }
            }
        }
        while (out.size() > 3) out.remove(out.size() - 1);
        return out;
    }

    /** Only plugins that bring photos in, not e.g. "now playing" displays that mention a service. */
    private static boolean isSource(String hay) {
        return hay.contains("photo") || hay.contains("foto") || hay.contains("picture") || hay.contains("image") || hay.contains("album") || hay.contains("folder");
    }

    private int howText(String id) {
        switch (id) {
            case "phone": return R.string.src_phone_how;
            case "nas": return R.string.src_nas_how;
            case "webdav": return R.string.src_webdav_how;
            default: return R.string.src_usb_how;
        }
    }

    private int noneText(String id) {
        return id.equals("gphotos") ? R.string.src_gphotos_none : R.string.src_none;
    }

    private void startBuiltIn(String id) {
        switch (id) {
            case "phone":
                startActivity(new Intent(this, FrameActivity.class).putExtra("host", f.host).putExtra("tab", 0)
                        .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP));
                finish();
                break;
            case "nas": nasDiscover(); break;
            case "webdav": webdavForm(null, null, null, null); break;
            default: usb(); break;
        }
    }

    // ------------------------------------------------------------------ NAS / SMB

    private void nasDiscover() {
        bg(getString(R.string.src_nas_searching), new Job<JSONArray>() {
            @Override public JSONArray run() throws Exception { return new Sources(f).discover(); }
        }, new Then<JSONArray>() {
            @Override public void done(JSONArray hosts) {
                final List<JSONObject> list = new ArrayList<>();
                List<String> names = new ArrayList<>();
                for (int i = 0; i < hosts.length(); i++) {
                    JSONObject h = hosts.optJSONObject(i);
                    if (h == null || isDynaFrame(h)) continue;
                    list.add(h);
                    names.add(Sources.s(h, "displayName", "host"));
                }
                names.add(getString(R.string.src_nas_manual));
                new AlertDialog.Builder(SourcesActivity.this).setTitle(R.string.src_nas_pick_host)
                        .setItems(names.toArray(new String[0]), new DialogInterface.OnClickListener() {
                            @Override public void onClick(DialogInterface d, int w) {
                                if (w < list.size()) nasHost(list.get(w), true);
                                else nasManual();
                            }
                        }).setNegativeButton(R.string.cancel, null).show();
            }
        });
    }

    /** Other frames share their own folders too; those are not what people mean here. */
    private static boolean isDynaFrame(JSONObject h) {
        JSONArray s = h.optJSONArray("shares");
        if (s == null) return false;
        for (int i = 0; i < s.length(); i++) if (s.optString(i).startsWith("Dynaframe_")) return true;
        return false;
    }

    private void nasManual() {
        LinearLayout box = form();
        final EditText host = field(box, R.string.src_nas_host_hint, null, InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        new AlertDialog.Builder(this).setTitle(R.string.src_nas_manual).setView(box)
                .setPositiveButton(R.string.ok, new DialogInterface.OnClickListener() {
                    @Override public void onClick(DialogInterface d, int w) {
                        final String h = host.getText().toString().trim().replaceFirst("^(smb:)?/*", "").replaceAll("/.*$", "");
                        if (h.isEmpty()) return;
                        bg(getString(R.string.src_nas_probing, h), new Job<JSONObject>() {
                            @Override public JSONObject run() throws Exception { return new Sources(f).probe(h); }
                        }, new Then<JSONObject>() {
                            @Override public void done(JSONObject r) {
                                if (r == null) { info(R.string.src_err_title, getString(R.string.src_nas_not_found, h)); return; }
                                nasHost(r, true);
                            }
                        });
                    }
                }).setNegativeButton(R.string.cancel, null).show();
    }

    /** Shows the shares of a host; asks for the sign-in first when there is none yet. */
    private void nasHost(final JSONObject h, final boolean checkLogin) {
        if (checkLogin) {
            bg(null, new Job<Boolean>() {
                @Override public Boolean run() { return new Sources(f).hasPassword(h); }
            }, new Then<Boolean>() {
                @Override public void done(Boolean has) {
                    if (has) nasShares(h);
                    else nasLogin(h, null);
                }
            });
            return;
        }
        nasShares(h);
    }

    private void nasLogin(final JSONObject h, final String afterShare) {
        LinearLayout box = form();
        TextView t = Ui.text(this, getString(R.string.src_nas_login_text, Sources.s(h, "displayName", "host")), 14, Ui.MUTED, false);
        box.addView(t);
        final EditText user = field(box, R.string.src_user, null, InputType.TYPE_CLASS_TEXT);
        final EditText pw = field(box, R.string.src_password, null, InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        new AlertDialog.Builder(this).setTitle(R.string.src_nas_login).setView(box)
                .setPositiveButton(R.string.ok, new DialogInterface.OnClickListener() {
                    @Override public void onClick(DialogInterface d, int w) {
                        final String u = user.getText().toString().trim(), p = pw.getText().toString();
                        bg(getString(R.string.src_saving), new Job<Boolean>() {
                            @Override public Boolean run() throws Exception {
                                Sources s = new Sources(f);
                                s.saveCredentials(h, u, p, null);
                                return true;
                            }
                        }, new Then<Boolean>() {
                            @Override public void done(Boolean r) {
                                if (afterShare != null) nasMap(h, afterShare, false);
                                else nasShares(h);
                            }
                        });
                    }
                })
                .setNeutralButton(R.string.src_nas_guest, new DialogInterface.OnClickListener() {
                    @Override public void onClick(DialogInterface d, int w) {
                        if (afterShare != null) nasMap(h, afterShare, false);
                        else nasShares(h);
                    }
                })
                .setNegativeButton(R.string.cancel, null).show();
    }

    private void nasShares(final JSONObject h) {
        final List<String> shares = new ArrayList<>();
        JSONArray a = h.optJSONArray("shares");
        if (a != null) for (int i = 0; i < a.length(); i++) {
            String s = a.optString(i);
            if (s.isEmpty() || s.endsWith("$") || s.equalsIgnoreCase("SMB1") || s.equalsIgnoreCase("nobody")) continue;
            shares.add(s);
        }
        if (shares.isEmpty()) {
            // some servers list their shares only after a sign-in: look again
            bg(getString(R.string.src_nas_probing, Sources.s(h, "displayName", "host")), new Job<JSONObject>() {
                @Override public JSONObject run() throws Exception { return new Sources(f).probe(Sources.s(h, "host")); }
            }, new Then<JSONObject>() {
                @Override public void done(JSONObject r) {
                    JSONArray s = r == null ? null : r.optJSONArray("shares");
                    if (s == null || s.length() == 0) { info(R.string.src_err_title, getString(R.string.src_nas_no_shares)); return; }
                    try { h.put("shares", s); } catch (Exception ignored) { }
                    nasShares(h);
                }
            });
            return;
        }
        new AlertDialog.Builder(this).setTitle(getString(R.string.src_nas_pick_share, Sources.s(h, "displayName", "host")))
                .setItems(shares.toArray(new String[0]), new DialogInterface.OnClickListener() {
                    @Override public void onClick(DialogInterface d, int w) { nasMap(h, shares.get(w), true); }
                }).setNegativeButton(R.string.cancel, null).show();
    }

    private void nasMap(final JSONObject h, final String share, final boolean firstTry) {
        bg(getString(R.string.src_nas_connecting, share), new Job<Sources.MapResult>() {
            @Override public Sources.MapResult run() throws Exception { return new Sources(f).map(h, share, share); }
        }, new Then<Sources.MapResult>() {
            @Override public void done(Sources.MapResult m) {
                if (!m.sourceId.isEmpty()) { pickFolders(share, m.sourceId, false); return; }
                if (m.authFailed && firstTry) { nasLogin(h, share); return; }
                info(R.string.src_err_title, m.message.isEmpty() ? getString(R.string.src_nas_failed) : m.message);
            }
        });
    }

    // ------------------------------------------------------------------ USB

    private void usb() {
        bg(getString(R.string.src_usb_looking), new Job<JSONArray>() {
            @Override public JSONArray run() throws Exception { return new Sources(f).usbDrives(); }
        }, new Then<JSONArray>() {
            @Override public void done(JSONArray drives) {
                final List<JSONObject> ok = new ArrayList<>();
                List<String> names = new ArrayList<>();
                for (int i = 0; i < drives.length(); i++) {
                    JSONObject d = drives.optJSONObject(i);
                    if (d == null || !d.optBoolean("canLink", true)) continue;
                    ok.add(d);
                    names.add(Sources.s(d, "name", "deviceId"));
                }
                if (ok.isEmpty()) { info(R.string.src_usb, getString(R.string.src_usb_none)); return; }
                new AlertDialog.Builder(SourcesActivity.this).setTitle(R.string.src_usb)
                        .setItems(names.toArray(new String[0]), new DialogInterface.OnClickListener() {
                            @Override public void onClick(DialogInterface di, int w) {
                                final JSONObject d = ok.get(w);
                                bg(getString(R.string.src_saving), new Job<String>() {
                                    @Override public String run() throws Exception { return new Sources(f).connectUsb(Sources.s(d, "deviceId")); }
                                }, new Then<String>() {
                                    @Override public void done(String id) {
                                        if (id.isEmpty()) { info(R.string.src_err_title, getString(R.string.src_usb_failed)); return; }
                                        pickFolders(Sources.s(d, "name", "deviceId"), id, false);
                                    }
                                });
                            }
                        }).setNegativeButton(R.string.cancel, null).show();
            }
        });
    }

    // ------------------------------------------------------------------ folder picker (NAS, USB, WebDAV)

    private void pickFolders(final String label, final String sourceId, final boolean webdav) {
        bg(getString(R.string.src_reading_folders), new Job<List<String[]>>() {
            @Override public List<String[]> run() throws Exception {
                Sources s = new Sources(f);
                return webdav ? s.webdavFolders(sourceId, "") : s.externalFolders(sourceId, "");
            }
        }, new Then<List<String[]>>() {
            @Override public void done(final List<String[]> folders) {
                final String[] items = new String[folders.size() + 1];
                final boolean[] on = new boolean[items.length];
                items[0] = getString(R.string.src_all_folders, label);
                for (int i = 0; i < folders.size(); i++) items[i + 1] = folders.get(i)[0];
                new AlertDialog.Builder(SourcesActivity.this).setTitle(R.string.src_pick_folders)
                        .setMultiChoiceItems(items, on, new DialogInterface.OnMultiChoiceClickListener() {
                            @Override public void onClick(DialogInterface d, int w, boolean c) { on[w] = c; }
                        })
                        .setPositiveButton(R.string.src_add, new DialogInterface.OnClickListener() {
                            @Override public void onClick(DialogInterface d, int w) {
                                final List<String[]> pick = new ArrayList<>();
                                if (on[0]) pick.add(new String[]{label, ""});
                                else for (int i = 0; i < folders.size(); i++) if (on[i + 1]) pick.add(folders.get(i));
                                if (pick.isEmpty()) { info(R.string.src_pick_folders, getString(R.string.src_pick_none)); return; }
                                register(label, sourceId, webdav, pick);
                            }
                        }).setNegativeButton(R.string.cancel, null).show();
            }
        });
    }

    private void register(final String label, final String sourceId, final boolean webdav, final List<String[]> pick) {
        bg(getString(R.string.src_saving), new Job<String>() {
            @Override public String run() throws Exception {
                Sources s = new Sources(f);
                return webdav ? s.webdavLink(sourceId, pick) : s.registerExternal(sourceId, pick);
            }
        }, new Then<String>() {
            @Override public void done(String job) {
                final AlertDialog d = new AlertDialog.Builder(SourcesActivity.this).setTitle(label)
                        .setMessage(getString(R.string.src_indexing_started, pick.size()))
                        .setPositiveButton(R.string.ok, null).show();
                if (job != null && !job.isEmpty()) follow(d, job, webdav, 0);
            }
        });
    }

    /** Shows the indexing progress in the open dialog for a while. */
    private void follow(final AlertDialog d, final String job, final boolean webdav, final int round) {
        if (round > 40 || !d.isShowing()) return;
        main.postDelayed(new Runnable() {
            @Override public void run() {
                if (!d.isShowing()) return;
                new Thread(new Runnable() {
                    @Override public void run() {
                        String[] st;
                        try {
                            Sources s = new Sources(f);
                            st = webdav ? s.webdavJob(job) : s.externalJob(job);
                        } catch (Exception e) {
                            st = null;
                        }
                        final String[] fs = st;
                        main.post(new Runnable() {
                            @Override public void run() {
                                if (fs == null || !d.isShowing()) { follow(d, job, webdav, round + 1); return; }
                                String state = fs[0];
                                if (state.startsWith("complete") || state.equals("succeeded") || state.equals("done")) {
                                    d.setMessage(getString(R.string.src_indexing_done));
                                    return;
                                }
                                if (state.equals("failed")) { d.setMessage(getString(R.string.src_indexing_failed, fs[2])); return; }
                                String n = fs[1].isEmpty() ? "" : (webdav ? fs[1] + " " + getString(R.string.src_files) : fs[1] + " %");
                                d.setMessage(getString(R.string.src_indexing_running, n));
                                follow(d, job, webdav, round + 1);
                            }
                        });
                    }
                }).start();
            }
        }, 2000);
    }

    // ------------------------------------------------------------------ WebDAV / Nextcloud

    private void webdavForm(String name, String url, String user, String error) {
        LinearLayout box = form();
        TextView t = Ui.text(this, error != null ? error : getString(R.string.src_webdav_form_text), 14, error != null ? Ui.BAD : Ui.MUTED, false);
        box.addView(t);
        final EditText n = field(box, R.string.src_webdav_name, name == null ? "Nextcloud" : name, InputType.TYPE_CLASS_TEXT);
        final EditText u = field(box, R.string.src_webdav_url, url, InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        final EditText us = field(box, R.string.src_user, user, InputType.TYPE_CLASS_TEXT);
        final EditText pw = field(box, R.string.src_webdav_password, null, InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        new AlertDialog.Builder(this).setTitle(R.string.src_webdav).setView(box)
                .setPositiveButton(R.string.src_connect, new DialogInterface.OnClickListener() {
                    @Override public void onClick(DialogInterface d, int w) {
                        final String nn = n.getText().toString().trim().isEmpty() ? "WebDAV" : n.getText().toString().trim();
                        String uu = u.getText().toString().trim();
                        if (!uu.isEmpty() && !uu.startsWith("http")) uu = "https://" + uu;
                        final String fu = uu, fus = us.getText().toString().trim(), fpw = pw.getText().toString();
                        if (fu.isEmpty()) { webdavForm(nn, fu, fus, getString(R.string.src_webdav_need_url)); return; }
                        new Thread(new Runnable() {
                            @Override public void run() {
                                try {
                                    final String id = new Sources(f).webdavAdd(nn, fu, fus, fpw);
                                    main.post(new Runnable() { @Override public void run() { pickFolders(nn, id, true); } });
                                } catch (final Exception e) {
                                    final String m = e instanceof Http.HttpException ? ((Http.HttpException) e).message() : e.getMessage();
                                    main.post(new Runnable() { @Override public void run() { webdavForm(nn, fu, fus, getString(R.string.src_webdav_failed, m)); } });
                                }
                            }
                        }).start();
                        Ui.toast(SourcesActivity.this, getString(R.string.src_webdav_testing));
                    }
                }).setNegativeButton(R.string.cancel, null).show();
    }

    // ------------------------------------------------------------------ plugins from the store

    private void offerInstall(final Sources.Pack p) {
        String msg = p.description + "\n\n" + getString(R.string.src_install_from, p.storeName, p.author.isEmpty() ? "?" : p.author)
                + (p.storeEnabled ? "" : "\n\n" + getString(R.string.src_store_off, p.storeName));
        new AlertDialog.Builder(this).setTitle(p.title + " " + p.version).setMessage(msg)
                .setPositiveButton(R.string.src_install, new DialogInterface.OnClickListener() {
                    @Override public void onClick(DialogInterface d, int w) { install(p); }
                }).setNegativeButton(R.string.cancel, null).show();
    }

    private void install(final Sources.Pack p) {
        bg(getString(R.string.src_installing, p.title), new Job<String[]>() {
            @Override public String[] run() throws Exception {
                Sources s = new Sources(f);
                String have = s.installedVersion(p.id);
                if (have == null || Api.newer(p.version, have)) s.install(p, have);
                // wait until the plugin is there (it starts in the background)
                String[] pl = null;
                for (int i = 0; i < 25; i++) {
                    pl = s.pluginFor(p);
                    if (pl != null && "1".equals(pl[2])) break;
                    Thread.sleep(2000);
                }
                return pl;
            }
        }, new Then<String[]>() {
            @Override public void done(final String[] pl) {
                if (pl == null) { info(R.string.src_installed, getString(R.string.src_installed_no_page, p.title)); return; }
                new AlertDialog.Builder(SourcesActivity.this).setTitle(R.string.src_installed)
                        .setMessage(getString(R.string.src_installed_text, p.title))
                        .setPositiveButton(R.string.src_open_settings, new DialogInterface.OnClickListener() {
                            @Override public void onClick(DialogInterface d, int w) { WebActivity.open(SourcesActivity.this, f, pl[1], p.title); }
                        }).setNegativeButton(R.string.src_later, null).show();
            }
        });
    }
}
