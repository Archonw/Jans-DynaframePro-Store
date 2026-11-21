package de.archonw.framecompanion;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.DialogInterface;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.IOException;
import java.util.Locale;

/**
 * "More": the frame at a glance (model, version, temperature, storage, update), settings, plugins,
 * store, power, and every other web UI page opened right in the app.
 */
public class MoreActivity extends Activity {

    private Frame f;
    private final Handler main = new Handler(Looper.getMainLooper());
    private LinearLayout infoCard;

    /** Web UI pages that have no native screen (yet): label, icon, path. */
    private static final Object[][] WEB = {
            {R.string.web_current, Ui.I_PLAYLIST, "/CurrentPlaylist"},
            {R.string.web_create_playlist, Ui.I_PLUS, "/Playlist/Create"},
            {R.string.web_media, Ui.I_IMAGES, "/ManageMedia"},
            {R.string.web_overlays, Ui.I_LAYERS, "/Overlay/Select"},
            {R.string.web_automations, Ui.I_MAGIC, "/Automations"},
            {R.string.web_nfc, Ui.I_BROADCAST, "/Nfc"},
            {R.string.web_cast, Ui.I_DISPLAY, "/Cast"},
            {R.string.web_sync, Ui.I_REFRESH, "/Sync"},
            {R.string.web_screen, Ui.I_SUN, "/Settings/Screen"},
            {R.string.web_audio, Ui.I_VOL_UP, "/Settings/Audio"},
            {R.string.web_network, Ui.I_GLOBE, "/Settings/Networking"},
            {R.string.web_backup, Ui.I_FOLDER, "/Settings/BackupRestore"},
            {R.string.web_ha, Ui.I_HOUSE, "/Settings/HomeAssistant"},
            {R.string.web_system, Ui.I_GEAR, "/Settings/SystemSettings"},
            {R.string.web_help, Ui.I_INFO, "/Support/Help"},
    };

    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        f = new Store(this).find(getIntent().getStringExtra("host"));
        if (f == null) { finish(); return; }
        LinearLayout root = Ui.page(this, f, Ui.TAB_MORE);
        root.addView(Ui.title(this, getString(R.string.tab_more), 34));
        TextView sub = Ui.text(this, f.name, 14, Ui.MUTED, false);
        sub.setPadding(0, Ui.dp(this, 2), 0, Ui.dp(this, 14));
        root.addView(sub);

        // the frame at a glance
        infoCard = Ui.card(this);
        infoCard.setPadding(Ui.dp(this, 16), Ui.dp(this, 14), Ui.dp(this, 14), Ui.dp(this, 4));
        Ui.cardHead(this, infoCard, getString(R.string.more_frame));
        Ui.listRow(this, infoCard, Ui.I_DISPLAY, getString(R.string.connecting), "", null);
        root.addView(infoCard, Ui.full(this, 14));

        // set up the frame
        LinearLayout set = group(root, R.string.more_setup);
        Ui.listRow(this, set, Ui.I_SLIDERS, getString(R.string.settings), "", go(new Intent(this, SettingsActivity.class)));
        Ui.listRow(this, set, Ui.I_CLOUD_PLUS, getString(R.string.src_card_button), "", new View.OnClickListener() {
            @Override public void onClick(View v) { Ui.go(MoreActivity.this, f, Ui.TAB_SOURCES, null); }
        });
        Ui.listRow(this, set, Ui.I_PUZZLE, getString(R.string.more_plugins), "", go(new Intent(this, PluginsActivity.class)));
        Ui.listRow(this, set, Ui.I_SHOP, getString(R.string.more_store), "", go(new Intent(this, StoreActivity.class)));

        // the rest of the web UI, opened in the app
        LinearLayout web = group(root, R.string.more_web);
        for (final Object[] w : WEB) {
            Ui.listRow(this, web, (Integer) w[1], getString((Integer) w[0]), "", new View.OnClickListener() {
                @Override public void onClick(View v) { WebActivity.open(MoreActivity.this, f, (String) w[2], getString((Integer) w[0])); }
            });
        }
        Ui.listRow(this, web, Ui.I_LINK, getString(R.string.open_webui), "", new View.OnClickListener() {
            @Override public void onClick(View v) { WebActivity.open(MoreActivity.this, f, "/", f.name); }
        });

        // frame and app
        LinearLayout pw = group(root, R.string.more_power);
        Ui.listRow(this, pw, Ui.I_RESTART, getString(R.string.more_restart_df), "", confirm(R.string.more_restart_df, R.string.more_restart_df_q, "restart-dynaframe"));
        Ui.listRow(this, pw, Ui.I_POWER, getString(R.string.set_restart), "", confirm(R.string.set_restart, R.string.set_restart_q, "restart-system"));
        Ui.listRow(this, pw, Ui.I_MOON, getString(R.string.more_shutdown), "", confirm(R.string.more_shutdown, R.string.more_shutdown_q, "shutdown-system"));
        Ui.listRow(this, pw, Ui.I_KEY, getString(R.string.login_settings), "", new View.OnClickListener() {
            @Override public void onClick(View v) { Connect.show(MoreActivity.this, f, new Runnable() { @Override public void run() { recreate(); } }); }
        });
        Ui.listRow(this, pw, Ui.I_GRID, getString(R.string.all_frames), "", new View.OnClickListener() {
            @Override public void onClick(View v) {
                startActivity(new Intent(MoreActivity.this, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP));
                finish();
            }
        });

        TextView ver = Ui.text(this, getString(R.string.app_name) + " " + BuildConfig.VERSION_NAME, 12, Ui.MUTED, false);
        ver.setPadding(Ui.dp(this, 6), Ui.dp(this, 4), 0, 0);
        root.addView(ver);
        PullScroll.on(root, new Runnable() { @Override public void run() { loadInfo(); } });
        loadInfo();
    }

    private LinearLayout group(LinearLayout root, int title) {
        LinearLayout c = Ui.card(this);
        c.setPadding(Ui.dp(this, 16), Ui.dp(this, 14), Ui.dp(this, 14), Ui.dp(this, 4));
        Ui.cardHead(this, c, getString(title));
        root.addView(c, Ui.full(this, 14));
        return c;
    }

    private View.OnClickListener go(final Intent i) {
        return new View.OnClickListener() {
            @Override public void onClick(View v) { startActivity(i.putExtra("host", f.host)); }
        };
    }

    private View.OnClickListener confirm(final int title, final int question, final String action) {
        return new View.OnClickListener() {
            @Override public void onClick(View v) {
                new AlertDialog.Builder(MoreActivity.this).setTitle(title).setMessage(getString(question, f.name))
                        .setPositiveButton(title, new DialogInterface.OnClickListener() {
                            @Override public void onClick(DialogInterface d, int w) {
                                run(new Api.Call<Void>() {
                                    @Override public Void run() throws IOException { new Api(f).power(action); return null; }
                                }, R.string.more_sent);
                            }
                        }).setNegativeButton(R.string.cancel, null).show();
            }
        };
    }

    private void run(final Api.Call<Void> c, final int done) {
        new Thread(new Runnable() {
            @Override public void run() {
                try {
                    new Api(f).with(c);
                    main.post(new Runnable() { @Override public void run() { Ui.toast(MoreActivity.this, getString(done)); } });
                } catch (final IOException e) {
                    main.post(new Runnable() {
                        @Override public void run() { Ui.toast(MoreActivity.this, getString(R.string.not_reachable_detail, e.getMessage())); }
                    });
                }
            }
        }).start();
    }

    // ------------------------------------------------------------------ frame info

    private void loadInfo() {
        new Thread(new Runnable() {
            @Override public void run() {
                final Api api = new Api(f);
                JSONObject about = null, thermal = null, storage = null, update = null;
                String err = null;
                try {
                    about = api.with(new Api.Call<JSONObject>() {
                        @Override public JSONObject run() throws IOException { return api.about(); }
                    });
                    try { thermal = api.thermal(); } catch (IOException ignored) { }
                    try { storage = api.storageSummary(); } catch (IOException ignored) { }
                    update = api.updatePresence();
                } catch (IOException e) { err = e.getMessage(); }
                final JSONObject a = about, t = thermal, s = storage, u = update;
                final String error = err;
                main.post(new Runnable() {
                    @Override public void run() { if (!isFinishing()) showInfo(a, t, s, u, error); }
                });
            }
        }).start();
    }

    private void showInfo(JSONObject about, JSONObject thermal, JSONObject storage, final JSONObject update, String error) {
        while (infoCard.getChildCount() > 1) infoCard.removeViewAt(1);
        if (about == null) {
            Ui.listRow(this, infoCard, Ui.I_DISPLAY, getString(R.string.not_reachable_detail, String.valueOf(error)), "", null);
            return;
        }
        Ui.listRow(this, infoCard, Ui.I_DISPLAY, getString(R.string.info_model), short_(about.optString("model", "–")), null);
        String ring = about.optString("ring", "");
        Ui.listRow(this, infoCard, Ui.I_INFO, getString(R.string.info_version), about.optString("version", "–") + (ring.isEmpty() ? "" : " · " + ring), null);
        Ui.listRow(this, infoCard, Ui.I_GLOBE, getString(R.string.info_address), about.optString("ipAddress", f.host), null);
        double temp = thermal != null ? thermal.optDouble("currentTempC", Double.NaN) : about.optDouble("cpuTemperatureC", Double.NaN);
        if (!Double.isNaN(temp)) {
            boolean warn = thermal != null && (thermal.optBoolean("shouldWarnUser") || thermal.optBoolean("throttledNow") || thermal.optBoolean("undervoltageNow"));
            String v = String.format(Locale.getDefault(), "%.0f °C", temp) + (warn ? " · " + thermal.optString("reason", "") : "");
            TextView val = (TextView) Ui.listRow(this, infoCard, Ui.I_SUN, getString(R.string.info_temp), v, null).findViewWithTag("value");
            if (warn) val.setTextColor(Ui.BAD);
        }
        if (storage != null) {
            JSONArray vols = storage.optJSONArray("volumes");
            if (vols != null) for (int i = 0; i < vols.length(); i++) {
                JSONObject vo = vols.optJSONObject(i);
                if (vo == null) continue;
                long free = vo.optLong("freeBytes", -1), total = vo.optLong("totalBytes", -1);
                if (total <= 0) continue;
                String lbl = "system".equals(vo.optString("type")) ? getString(R.string.info_storage) : vo.optString("label", vo.optString("mountPath"));
                Ui.listRow(this, infoCard, "system".equals(vo.optString("type")) ? Ui.I_FOLDER : 0xf40d, lbl,
                        getString(R.string.info_free, gb(free), gb(total)), null);
            }
            JSONObject lib = storage.optJSONObject("library");
            if (lib != null) {
                String v = getResources().getQuantityString(R.plurals.info_photos, lib.optInt("totalImages"), lib.optInt("totalImages"));
                if (lib.optInt("totalVideos") > 0) v += " · " + getResources().getQuantityString(R.plurals.info_videos, lib.optInt("totalVideos"), lib.optInt("totalVideos"));
                Ui.listRow(this, infoCard, Ui.I_IMAGES, getString(R.string.info_library), v, null);
            }
        }
        if (update != null && update.optBoolean("updateAvailable", false)) {
            final String channel = update.optString("channel", "golden");
            String latest = update.optString("latestVersion", update.optString("availableVersion", ""));
            LinearLayout r = Ui.listRow(this, infoCard, Ui.I_ARROW_DOWN_CIRCLE, getString(R.string.update_available), latest, new View.OnClickListener() {
                @Override public void onClick(View v) { confirmUpdate(channel); }
            });
            ((TextView) r.getChildAt(1)).setTextColor(Ui.ACCENT);
        } else if (update != null) {
            Ui.listRow(this, infoCard, Ui.I_CHECK, getString(R.string.update_none), "", new View.OnClickListener() {
                @Override public void onClick(View v) { WebActivity.open(MoreActivity.this, f, "/Update", getString(R.string.update_title)); }
            });
        }
    }

    private void confirmUpdate(final String channel) {
        new AlertDialog.Builder(this).setTitle(R.string.update_title).setMessage(getString(R.string.update_q, f.name))
                .setPositiveButton(R.string.update_install, new DialogInterface.OnClickListener() {
                    @Override public void onClick(DialogInterface d, int w) {
                        new Thread(new Runnable() {
                            @Override public void run() {
                                final Api api = new Api(f);
                                try {
                                    final String id = api.with(new Api.Call<String>() {
                                        @Override public String run() throws IOException { return api.startUpdate(channel); }
                                    });
                                    main.post(new Runnable() {
                                        @Override public void run() {
                                            WebActivity.open(MoreActivity.this, f, "/Update/Progress?jobId=" + id, getString(R.string.update_title));
                                        }
                                    });
                                } catch (final IOException e) {
                                    main.post(new Runnable() {
                                        @Override public void run() { Ui.toast(MoreActivity.this, getString(R.string.not_reachable_detail, e.getMessage())); }
                                    });
                                }
                            }
                        }).start();
                    }
                }).setNegativeButton(R.string.cancel, null).show();
    }

    private static String short_(String model) {
        return model.replace(" Model ", " ").replaceAll(" Rev [0-9.]+$", "");
    }

    private static String gb(long bytes) {
        double g = bytes / 1e9;
        return g >= 100 ? String.format(Locale.getDefault(), "%.0f GB", g) : String.format(Locale.getDefault(), "%.1f GB", g);
    }
}
