package de.archonw.framecompanion;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.DialogInterface;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

/**
 * The frame settings from the web UI's Slideshow and Display pages: time per picture, transition,
 * order, overlays, how photos and videos fill the screen, several photos at once, video sound,
 * live photos. Everything is saved right away, like on the web page.
 */
public class SettingsActivity extends Activity {

    private static final int[] DURATIONS = {5, 10, 15, 20, 30, 45, 60, 120, 300, 600};
    private static final int[] TRANSITION_MS = {300, 500, 800, 1000, 1500, 2000, 3000};
    private static final String[] ORDER = {"alphabetical-filename", "alphabetical-folder-filename", "reverse-alphabetical-filename",
            "reverse-alphabetical-folder-filename", "date-taken-newest", "date-taken-oldest"};
    private static final int[] ORDER_LABELS = {R.string.order_az, R.string.order_folder_az, R.string.order_za, R.string.order_folder_za,
            R.string.order_newest, R.string.order_oldest};
    private static final String[] FIT = {"original", "zoomtofill", "fill", "stretch", "kenburns"};
    private static final int[] FIT_LABELS = {R.string.fit_original, R.string.fit_zoom, R.string.fit_fill, R.string.fit_stretch, R.string.fit_kenburns};
    private static final String[] MULTI = {"disabled", "auto-2", "auto-3"};
    private static final int[] MULTI_LABELS = {R.string.multi_off, R.string.multi_2, R.string.multi_3};

    private Frame f;
    private final Handler main = new Handler(Looper.getMainLooper());
    private LinearLayout body;
    private JSONObject cfg = new JSONObject();
    private JSONObject fit;
    private List<String> transitions = new ArrayList<>();
    private TextView status;

    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        f = new Store(this).find(getIntent().getStringExtra("host"));
        if (f == null) { finish(); return; }
        LinearLayout root = Ui.page(this);
        status = Ui.header(this, root, getString(R.string.settings), f.name + " · " + getString(R.string.connecting));
        body = Ui.column(this);
        root.addView(body);
        load();
    }

    private void load() {
        new Thread(new Runnable() {
            @Override public void run() {
                final Api api = new Api(f);
                try {
                    final JSONObject c = api.with(new Api.Call<JSONObject>() {
                        @Override public JSONObject run() throws IOException { return api.slideshowSettings(); }
                    });
                    JSONObject fm = null;
                    try { fm = api.fitMode(); } catch (IOException ignored) { }
                    final JSONObject fitMode = fm;
                    final List<String> tr = api.transitions();
                    main.post(new Runnable() {
                        @Override public void run() {
                            cfg = c;
                            fit = fitMode;
                            transitions = tr;
                            status.setText(f.name);
                            render();
                        }
                    });
                } catch (final IOException e) {
                    main.post(new Runnable() {
                        @Override public void run() { status.setText(f.name + " · " + e.getMessage()); }
                    });
                }
            }
        }).start();
    }

    private void render() {
        body.removeAllViews();

        // slideshow
        LinearLayout show = card(R.string.set_slideshow);
        final int dur = cfg.optInt("durationSeconds", 0);
        Ui.listRow(this, show, Ui.I_STOPWATCH, getString(R.string.set_duration), dur > 0 ? seconds(dur) : "–", click(new Runnable() {
            @Override public void run() { chooseDuration(dur); }
        }));
        final String tr = cfg.isNull("defaultTransition") ? "" : cfg.optString("defaultTransition", "");
        Ui.listRow(this, show, Ui.I_MAGIC, getString(R.string.set_transition), tr.isEmpty() ? "–" : "random".equals(tr) ? getString(R.string.set_transition_random) : pretty(tr), click(new Runnable() {
            @Override public void run() { chooseTransition(tr); }
        }));
        if (cfg.has("transitionDurationMs")) {
            final int ms = cfg.optInt("transitionDurationMs", 1000);
            Ui.listRow(this, show, Ui.I_SLIDERS, getString(R.string.set_transition_time), secondsMs(ms), click(new Runnable() {
                @Override public void run() { chooseTransitionTime(ms); }
            }));
        }
        toggle(show, Ui.I_SHUFFLE, R.string.set_shuffle, 0, "randomizeOrder", true);
        if (cfg.has("playbackOrderMode") && !cfg.optBoolean("randomizeOrder", false)) {
            final String om = cfg.optString("playbackOrderMode", ORDER[0]);
            Ui.listRow(this, show, Ui.I_LAYERS, getString(R.string.set_order), label(ORDER, ORDER_LABELS, om), click(new Runnable() {
                @Override public void run() { choose(R.string.set_order, ORDER, ORDER_LABELS, om, "playbackOrderMode"); }
            }));
        }
        toggle(show, Ui.I_LAYERS, R.string.set_overlays, 0, "overlaysEnabled", false);
        body.addView(show, Ui.full(this, 14));

        // how pictures fill the screen
        LinearLayout disp = card(R.string.set_display);
        if (fit != null) {
            final String im = fit.optString("image_fit_mode", "");
            Ui.listRow(this, disp, Ui.I_IMAGE, getString(R.string.set_fit_photos), label(FIT, FIT_LABELS, im), click(new Runnable() {
                @Override public void run() { chooseFit("imageFitMode", "image_fit_mode", FIT.length, im); }
            }));
            final String vm = fit.optString("video_fit_mode", "");
            Ui.listRow(this, disp, Ui.I_FILM, getString(R.string.set_fit_videos), label(FIT, FIT_LABELS, vm), click(new Runnable() {
                @Override public void run() { chooseFit("videoFitMode", "video_fit_mode", FIT.length - 1, vm); }
            }));
        }
        if (cfg.has("multiPhotoLayoutMode")) {
            final String mm = cfg.optString("multiPhotoLayoutMode", "disabled");
            boolean kb = fit != null && "kenburns".equals(fit.optString("image_fit_mode"));
            Ui.listRow(this, disp, Ui.I_GRID, getString(R.string.set_multi), kb ? getString(R.string.multi_kb) : label(MULTI, MULTI_LABELS, mm), kb ? null : click(new Runnable() {
                @Override public void run() { choose(R.string.set_multi, MULTI, MULTI_LABELS, mm, "multiPhotoLayoutMode"); }
            }));
        }
        if (disp.getChildCount() > 1) body.addView(disp, Ui.full(this, 14));

        // videos and live photos
        LinearLayout vid = card(R.string.set_videos);
        toggle(vid, Ui.I_VOL_UP, R.string.set_video_audio, 0, "playVideoAudio", false);
        toggle(vid, Ui.I_FILM, R.string.set_video_full, 0, "videoPlaysToCompletion", false);
        toggle(vid, Ui.I_RESTART, R.string.set_video_repeat, R.string.set_video_repeat_sub, "repeatShortVideos", false);
        if (cfg.has("livePhotoPlaybackMode")) {
            final boolean motion = "motion".equals(cfg.optString("livePhotoPlaybackMode"));
            Ui.switchRow(this, vid, Ui.I_PLAY_CIRCLE, getString(R.string.set_live), getString(R.string.set_live_sub), motion, new Ui.Switch.OnChange() {
                @Override public void changed(boolean on) { set("livePhotoPlaybackMode", on ? "motion" : "still", false); }
            });
        }
        body.addView(vid, Ui.full(this, 14));

        TextView more = Ui.text(this, Ui.withIcon(this, Ui.I_LINK, getString(R.string.set_more_web2)), 13, Ui.MUTED, false);
        more.setPadding(Ui.dp(this, 6), 0, Ui.dp(this, 6), 0);
        more.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { WebActivity.open(SettingsActivity.this, f, "/Settings/Slideshow", getString(R.string.settings)); }
        });
        body.addView(more);
    }

    private static View.OnClickListener click(final Runnable r) {
        return new View.OnClickListener() { @Override public void onClick(View v) { r.run(); } };
    }

    private LinearLayout card(int title) {
        LinearLayout c = Ui.card(this);
        c.setPadding(Ui.dp(this, 16), Ui.dp(this, 14), Ui.dp(this, 14), Ui.dp(this, 4));
        Ui.cardHead(this, c, getString(title));
        return c;
    }

    private void toggle(LinearLayout parent, int icon, int label, int sub, final String key, final boolean rerender) {
        if (!cfg.has(key)) return;   // this DynaFrame version does not have it
        Ui.switchRow(this, parent, icon, getString(label), sub == 0 ? null : getString(sub), cfg.optBoolean(key, false), new Ui.Switch.OnChange() {
            @Override public void changed(boolean on) { set(key, on, rerender); }
        });
    }

    private void set(final String key, final Object value, boolean rerender) {
        try { cfg.put(key, value); } catch (Exception ignored) { }
        if (rerender) render();
        call(new Api.Call<Void>() {
            @Override public Void run() throws IOException { new Api(f).setSlideshow(key, value); return null; }
        });
    }

    private void call(final Api.Call<Void> c) {
        new Thread(new Runnable() {
            @Override public void run() {
                final Api api = new Api(f);
                try {
                    api.with(c);
                } catch (final IOException e) {
                    main.post(new Runnable() {
                        @Override public void run() {
                            Toast.makeText(SettingsActivity.this, getString(R.string.not_reachable_detail, e.getMessage()), Toast.LENGTH_LONG).show();
                            load();
                        }
                    });
                }
            }
        }).start();
    }

    private String label(String[] values, int[] labels, String v) {
        for (int i = 0; i < values.length; i++) if (values[i].equals(v)) return getString(labels[i]);
        return v == null || v.isEmpty() ? "–" : pretty(v);
    }

    private void choose(int title, final String[] values, int[] labels, String current, final String key) {
        CharSequence[] items = new CharSequence[values.length];
        int sel = -1;
        for (int i = 0; i < values.length; i++) { items[i] = getString(labels[i]); if (values[i].equals(current)) sel = i; }
        new AlertDialog.Builder(this).setTitle(title)
                .setSingleChoiceItems(items, sel, new DialogInterface.OnClickListener() {
                    @Override public void onClick(DialogInterface d, int w) { d.dismiss(); set(key, values[w], true); }
                }).setNegativeButton(R.string.cancel, null).show();
    }

    /** Photo or video fit mode; Ken Burns (photos only) turns "several photos at once" off, like the web page. */
    private void chooseFit(final String key, final String readKey, int count, String current) {
        CharSequence[] items = new CharSequence[count];
        int sel = -1;
        for (int i = 0; i < count; i++) { items[i] = getString(FIT_LABELS[i]); if (FIT[i].equals(current)) sel = i; }
        new AlertDialog.Builder(this).setTitle(key.startsWith("image") ? R.string.set_fit_photos : R.string.set_fit_videos)
                .setSingleChoiceItems(items, sel, new DialogInterface.OnClickListener() {
                    @Override public void onClick(DialogInterface d, int w) {
                        d.dismiss();
                        final String mode = FIT[w];
                        try { fit.put(readKey, mode); } catch (Exception ignored) { }
                        final boolean kb = "kenburns".equals(mode) && !"disabled".equals(cfg.optString("multiPhotoLayoutMode", "disabled"));
                        if (kb) try { cfg.put("multiPhotoLayoutMode", "disabled"); } catch (Exception ignored) { }
                        render();
                        call(new Api.Call<Void>() {
                            @Override public Void run() throws IOException {
                                Api a = new Api(f);
                                a.setFitMode(key, mode);
                                if (kb) a.setSlideshow("multiPhotoLayoutMode", "disabled");
                                return null;
                            }
                        });
                    }
                }).setNegativeButton(R.string.cancel, null).show();
    }

    private String seconds(int s) {
        return s < 60 ? getString(R.string.n_seconds, s) : s % 60 == 0 ? getString(R.string.n_minutes, s / 60) : getString(R.string.n_seconds, s);
    }

    private String secondsMs(int ms) {
        return String.format(java.util.Locale.getDefault(), "%.1f s", ms / 1000f);
    }

    private static String pretty(String t) {
        String s = t.replace('_', ' ').replace('-', ' ');
        return s.isEmpty() ? s : Character.toUpperCase(s.charAt(0)) + s.substring(1);
    }

    private void chooseDuration(int current) {
        final CharSequence[] items = new CharSequence[DURATIONS.length];
        int sel = -1;
        for (int i = 0; i < DURATIONS.length; i++) {
            items[i] = seconds(DURATIONS[i]);
            if (DURATIONS[i] == current) sel = i;
        }
        new AlertDialog.Builder(this).setTitle(R.string.set_duration)
                .setSingleChoiceItems(items, sel, new DialogInterface.OnClickListener() {
                    @Override public void onClick(DialogInterface d, int w) { d.dismiss(); set("durationSeconds", DURATIONS[w], true); }
                }).setNegativeButton(R.string.cancel, null).show();
    }

    private void chooseTransitionTime(int current) {
        final CharSequence[] items = new CharSequence[TRANSITION_MS.length];
        int sel = -1;
        for (int i = 0; i < TRANSITION_MS.length; i++) {
            items[i] = secondsMs(TRANSITION_MS[i]);
            if (TRANSITION_MS[i] == current) sel = i;
        }
        new AlertDialog.Builder(this).setTitle(R.string.set_transition_time)
                .setSingleChoiceItems(items, sel, new DialogInterface.OnClickListener() {
                    @Override public void onClick(DialogInterface d, int w) { d.dismiss(); set("transitionDurationMs", TRANSITION_MS[w], true); }
                }).setNegativeButton(R.string.cancel, null).show();
    }

    private void chooseTransition(String current) {
        final List<String> names = new ArrayList<>();
        names.add("random");
        for (String t : transitions) if (!names.contains(t)) names.add(t);
        if (transitions.isEmpty()) {
            for (String t : new String[]{"crossfade", "none", "dreamyzoom", "cube", "directionalwipe", "ripple", "swirl", "soft_page_turn", "falling_polaroid", "kaleidoscope", "pixelate", "wind"}) names.add(t);
        }
        final CharSequence[] items = new CharSequence[names.size()];
        int sel = -1;
        for (int i = 0; i < names.size(); i++) {
            items[i] = "random".equals(names.get(i)) ? getString(R.string.set_transition_random) : pretty(names.get(i));
            if (names.get(i).equals(current)) sel = i;
        }
        new AlertDialog.Builder(this).setTitle(R.string.set_transition)
                .setSingleChoiceItems(items, sel, new DialogInterface.OnClickListener() {
                    @Override public void onClick(DialogInterface d, int w) {
                        d.dismiss();
                        final String n = names.get(w);
                        try { cfg.put("defaultTransition", n); } catch (Exception ignored) { }
                        render();
                        call(new Api.Call<Void>() {
                            @Override public Void run() throws IOException { new Api(f).setTransition(n); return null; }
                        });
                    }
                }).setNegativeButton(R.string.cancel, null).show();
    }

    @SuppressWarnings("unused")
    private static List<String> list(JSONArray a) {
        List<String> out = new ArrayList<>();
        if (a != null) for (int i = 0; i < a.length(); i++) out.add(a.optString(i));
        return out;
    }
}
