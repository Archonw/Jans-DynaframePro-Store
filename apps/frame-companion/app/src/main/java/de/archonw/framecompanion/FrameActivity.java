package de.archonw.framecompanion;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ClipData;
import android.content.DialogInterface;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.MediaStore;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.SeekBar;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

/** One frame: send photos, control playback, screen, volume and playlists. */
public class FrameActivity extends Activity implements UploadService.Listener {

    private static final int PICK = 11;

    private Store store;
    private Frame f;
    private final Handler main = new Handler(Looper.getMainLooper());
    private TextView nowPlaying, folderBtn, uploadState, pauseBtn, loginBtn;
    private ProgressBar uploadBar;
    private SeekBar volume;
    private LinearLayout playlists;
    private boolean visible, busyVolume, paused;
    private final Runnable poll = new Runnable() {
        @Override public void run() {
            refresh();
            if (visible) main.postDelayed(this, 5000);
        }
    };

    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        store = new Store(this);
        f = store.find(getIntent().getStringExtra("host"));
        if (f == null) { finish(); return; }
        build();
        loadPlaylists();
    }

    @Override
    protected void onResume() {
        super.onResume();
        Frame fresh = store.find(f.host);
        if (fresh != null) f = fresh;
        setPickerText();
        visible = true;
        renderPlaylists();
        UploadService.listener = this;
        main.post(poll);
        main.post(tick);
    }

    @Override
    protected void onPause() {
        visible = false;
        main.removeCallbacks(poll);
        main.removeCallbacks(tick);
        if (UploadService.listener == this) UploadService.listener = null;
        super.onPause();
    }

    // ------------------------------------------------------------------ UI

    private static final int TAB_SEND = Ui.TAB_SEND, TAB_CONTROL = Ui.TAB_CONTROL, TAB_PLAYLISTS = Ui.TAB_PLAYLISTS;
    private android.widget.ScrollView scroll;
    private final LinearLayout[] tabs = new LinearLayout[3];
    private final TextView[] tabButtons = new TextView[Ui.TABS];
    private int tab = TAB_SEND;
    private TextView nowTitle, nowSub, previewBtn, previewNote, shuffleBtn, screenBtn, volText, muteBtn, timeLeft, timeRight;
    private LinearLayout previewEmpty;
    private TextView previewEmptyIcon;
    private android.widget.ImageView preview;
    private android.widget.FrameLayout stage;
    private ProgressBar progress;
    private String lastPreviewKey, shownKey, itemKey = "";
    private long lastPreviewAt, displaySeq = -1;
    private long itemSince;
    private int slideSeconds = 10;
    private boolean shuffle, screenOn = true, muted, running, previewFailed;
    private JSONObject currentItem;
    private String currentPlaylists = "";
    private int plFilter;   // 0 all, 1 playlists, 2 folders, 3 plugins
    private final Runnable tick = new Runnable() {
        @Override public void run() {
            updateProgress();
            if (visible) main.postDelayed(this, 250);
        }
    };

    private void updateProgress() {
        if (progress == null) return;
        boolean video = currentItem != null && "video".equalsIgnoreCase(str(currentItem, "mediaType"));
        if (!running || currentItem == null || video || slideSeconds <= 0) {
            progress.setProgress(0);
            timeLeft.setText(video ? getString(R.string.info_video) : "");
            timeRight.setText("");
            return;
        }
        long ms = paused ? pausedAt - itemSince : android.os.SystemClock.elapsedRealtime() - itemSince;
        ms = Math.max(0, Math.min(ms, slideSeconds * 1000L));
        progress.setProgress((int) (ms * 1000 / (slideSeconds * 1000L)));
        timeLeft.setText(clock(ms / 1000));
        timeRight.setText("-" + clock(slideSeconds - ms / 1000));
    }

    private long pausedAt;

    private static String clock(long s) { return (s / 60) + ":" + (s % 60 < 10 ? "0" : "") + (s % 60); }

    private boolean wasPaused;

    private void updatePreviewUi() {
        boolean on = store.preview();
        previewBtn.setText(Ui.ic(on ? Ui.I_EYE : Ui.I_EYE_SLASH));
        previewBtn.setTextColor(on ? Ui.TEXT : Ui.MUTED);
        if (!on) preview.setVisibility(View.GONE);
        boolean empty = preview.getVisibility() != View.VISIBLE;
        previewEmpty.setVisibility(empty ? View.VISIBLE : View.GONE);
        previewEmptyIcon.setText(Ui.ic(!screenOn ? Ui.I_MOON : Ui.I_IMAGE));
        previewNote.setText(!screenOn ? getString(R.string.screen_is_off) : !on ? getString(R.string.preview_off)
                : previewFailed ? getString(R.string.preview_failed) : "");
        previewNote.setVisibility(previewNote.length() == 0 ? View.GONE : View.VISIBLE);
        preview.setAlpha(screenOn ? 1f : 0.35f);
    }

    /** Loads the picture on screen when the item changed (and only when the preview is on). */
    private void loadPreview(final JSONObject item) {
        if (!store.preview()) { updatePreviewUi(); return; }
        long now = android.os.SystemClock.elapsedRealtime();
        // other tabs only need the blurred background: a new picture at most once a minute
        if (tab != TAB_CONTROL && lastPreviewKey != null && now - lastPreviewAt < 60000) return;
        String key = displaySeq >= 0 ? "seq:" + displaySeq : item == null ? "-" : item.optString("id", "") + "|" + str(item, "filePath") + "|" + str(item, "dynamicSceneId") + "|" + str(item, "fileName");
        if (key.equals(lastPreviewKey) && now - lastPreviewAt < 30000) return;
        lastPreviewKey = key;
        lastPreviewAt = now;
        // the renderer needs a moment to show the new item before its screenshot is right
        final boolean changed = !key.equals(shownKey);
        shownKey = key;
        bg(new Api.Call<byte[]>() {
            @Override public byte[] run() throws IOException {
                if (changed) { try { Thread.sleep(1200); } catch (InterruptedException ignored) { } }
                return api().screenPicture(item, 800);
            }
        }, new Done<byte[]>() {
            @Override public void done(byte[] b) {
                android.graphics.Bitmap bm = b == null ? null : android.graphics.BitmapFactory.decodeByteArray(b, 0, b.length);
                if (!store.preview()) preview.setVisibility(View.GONE);
                else if (bm != null) {
                    preview.setImageBitmap(bm);
                    preview.setVisibility(View.VISIBLE);
                    previewFailed = false;
                    fitStage(bm.getWidth(), bm.getHeight());
                    Backdrop.set(FrameActivity.this, bm);
                }
                else if (preview.getVisibility() != View.VISIBLE) previewFailed = true;
                updatePreviewUi();
            }
        });
    }

    /** The artwork takes the photo's shape (portrait taller, landscape flatter), within limits. */
    private void fitStage(int w, int h) {
        int width = stage.getWidth() > 0 ? stage.getWidth() : getResources().getDisplayMetrics().widthPixels - Ui.dp(this, 44);
        int target = Math.round(width * (float) h / Math.max(1, w));
        target = Math.max(Ui.dp(this, 190), Math.min(target, Ui.dp(this, 420)));
        LinearLayout.LayoutParams lp = (LinearLayout.LayoutParams) stage.getLayoutParams();
        if (lp.height != target) { lp.height = target; stage.setLayoutParams(lp); }
    }

    private EditText search;
    private List<JSONObject> allPlaylists = new ArrayList<>();
    private java.util.Set<String> active = new java.util.HashSet<>();
    private TextView framePicker, loginCircle;

    private void build() {
        Ui.edgeToEdge(this);
        android.widget.FrameLayout stack = new android.widget.FrameLayout(this);
        LinearLayout outer = Ui.column(this);
        stack.addView(outer, new android.widget.FrameLayout.LayoutParams(-1, -1));

        // header: frame picker "Kitchen ⌄" on the left, login + more as round glass buttons on the right
        LinearLayout head = Ui.column(this);
        int p = Ui.dp(this, 18);
        head.setPadding(p, Ui.dp(this, 10), p, Ui.dp(this, 4));
        LinearLayout tr = Ui.row(this);
        framePicker = Ui.text(this, "", 17, Ui.TEXT, true);
        framePicker.setPadding(Ui.dp(this, 14), Ui.dp(this, 8), Ui.dp(this, 14), Ui.dp(this, 8));
        framePicker.setBackground(pillBg());
        framePicker.setSingleLine(true);
        framePicker.setEllipsize(android.text.TextUtils.TruncateAt.END);
        framePicker.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { switchFrame(); }
        });
        setPickerText();
        tr.addView(framePicker, new LinearLayout.LayoutParams(android.view.ViewGroup.LayoutParams.WRAP_CONTENT, android.view.ViewGroup.LayoutParams.WRAP_CONTENT));
        tr.addView(new View(this), new LinearLayout.LayoutParams(0, 1, 1f));
        loginCircle = Ui.glassCircle(this, Ui.I_KEY, 16);
        loginCircle.setTextColor(Ui.ACCENT);
        loginCircle.setVisibility(View.GONE);
        loginCircle.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { login(); }
        });
        LinearLayout.LayoutParams cl = new LinearLayout.LayoutParams(Ui.dp(this, 40), Ui.dp(this, 40));
        cl.setMargins(Ui.dp(this, 8), 0, 0, 0);
        tr.addView(loginCircle, cl);
        TextView more = Ui.glassCircle(this, Ui.I_DOTS, 18);
        more.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { moreMenu(); }
        });
        tr.addView(more, new LinearLayout.LayoutParams(cl));
        head.addView(tr);
        nowPlaying = Ui.text(this, getString(R.string.connecting), 13, Ui.MUTED, false);
        nowPlaying.setSingleLine(true);
        nowPlaying.setEllipsize(android.text.TextUtils.TruncateAt.END);
        nowPlaying.setPadding(Ui.dp(this, 6), Ui.dp(this, 8), 0, 0);
        head.addView(nowPlaying);
        outer.addView(head);

        scroll = new PullScroll(this);
        scroll.setFillViewport(true);
        scroll.setClipToPadding(false);
        scroll.setVerticalScrollBarEnabled(false);
        LinearLayout body = Ui.column(this);
        body.setPadding(p, Ui.dp(this, 6), p, Ui.dp(this, 130));
        scroll.addView(body);
        ((PullScroll) scroll).setOnPull(body, new Runnable() {
            @Override public void run() { refresh(); loadPlaylists(); }
        });
        outer.addView(scroll, new LinearLayout.LayoutParams(android.view.ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        loginBtn = Ui.button(this, Ui.withIcon(this, Ui.I_KEY, getString(R.string.login_needed_tap)), 15, Ui.CARD2, Ui.ACCENT);
        loginBtn.setVisibility(View.GONE);
        loginBtn.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { login(); }
        });
        body.addView(loginBtn, Ui.full(this, 12));

        for (int i = 0; i < 3; i++) {
            tabs[i] = Ui.column(this);
            body.addView(tabs[i]);
        }
        buildSend(tabs[TAB_SEND]);
        buildControl(tabs[TAB_CONTROL]);
        buildPlaylists(tabs[TAB_PLAYLISTS]);

        // floating gold "play these playlists" pill, above the tab bar
        playSelection = Ui.primary(this, "");
        playSelection.setElevation(Ui.dp(this, 10));
        playSelection.setVisibility(View.GONE);
        playSelection.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { playSelected(); }
        });
        android.widget.FrameLayout.LayoutParams fl = new android.widget.FrameLayout.LayoutParams(android.view.ViewGroup.LayoutParams.WRAP_CONTENT,
                android.view.ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL);
        fl.setMargins(Ui.dp(this, 24), 0, Ui.dp(this, 24), Ui.dp(this, 104));
        stack.addView(playSelection, fl);

        // floating capsule tab bar
        LinearLayout bar = Ui.tabBar(this, f, TAB_SEND, new Ui.Tabs() {
            @Override public boolean show(int k) {
                if (k > TAB_PLAYLISTS) return false;
                showTab(k);
                return true;
            }
        }, tabButtons);
        android.widget.FrameLayout.LayoutParams bl = new android.widget.FrameLayout.LayoutParams(-1, android.view.ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.BOTTOM);
        bl.setMargins(Ui.dp(this, 16), 0, Ui.dp(this, 16), Ui.dp(this, 18));
        stack.addView(bar, bl);

        View all = Backdrop.wrap(this, stack);
        setContentView(all);
        Ui.insets(all, head, new View[]{body}, new View[]{bar, playSelection});
        showTab(getIntent().getIntExtra("tab", TAB_SEND));
    }

    private android.graphics.drawable.Drawable pillBg() {
        android.graphics.drawable.GradientDrawable g = new android.graphics.drawable.GradientDrawable();
        g.setColor(android.graphics.Color.argb(34, 255, 255, 255));
        g.setCornerRadius(Ui.dp(this, 30));
        g.setStroke(Ui.dp(this, 1), android.graphics.Color.argb(46, 255, 255, 255));
        return new android.graphics.drawable.RippleDrawable(android.content.res.ColorStateList.valueOf(android.graphics.Color.argb(60, 255, 255, 255)), g, null);
    }

    private void setPickerText() {
        android.text.SpannableStringBuilder sb = new android.text.SpannableStringBuilder(f.name + "  ");
        int s = sb.length();
        sb.append(Ui.ic(Ui.I_DOWN));
        sb.setSpan(new Ui.IconSpan(Ui.icons(this)), s, sb.length(), 0);
        sb.setSpan(new android.text.style.RelativeSizeSpan(0.7f), s, sb.length(), 0);
        sb.setSpan(new android.text.style.ForegroundColorSpan(Ui.ACCENT), s, sb.length(), 0);
        framePicker.setText(sb);
    }

    /** Other frames in one tap; "all frames" goes back to the search screen. */
    private void switchFrame() {
        final List<Frame> all = store.saved();
        final List<CharSequence> names = new ArrayList<>();
        for (Frame o : all) names.add((o.host.equals(f.host) ? "✓  " : "     ") + o.name);
        names.add(getString(R.string.all_frames));
        new AlertDialog.Builder(this).setTitle(R.string.choose_frame)
                .setItems(names.toArray(new CharSequence[0]), new DialogInterface.OnClickListener() {
                    @Override public void onClick(DialogInterface d, int w) {
                        if (w == all.size()) {
                            startActivity(new Intent(FrameActivity.this, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP));
                            finish();
                            return;
                        }
                        Frame o = all.get(w);
                        if (o.host.equals(f.host)) return;
                        store.save(o, true);
                        startActivity(new Intent(FrameActivity.this, FrameActivity.class).putExtra("host", o.host).putExtra("tab", tab));
                        overridePendingTransition(0, 0);
                        finish();
                    }
                }).show();
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        if (intent.hasExtra("tab")) showTab(intent.getIntExtra("tab", tab));
    }

    private void showTab(int k) {
        if (k < 0 || k > TAB_PLAYLISTS) k = TAB_SEND;
        tab = k;
        for (int i = 0; i < 3; i++) tabs[i].setVisibility(i == k ? View.VISIBLE : View.GONE);
        Ui.markTab(tabButtons, k);
        nowPlaying.setVisibility(k == TAB_PLAYLISTS ? View.VISIBLE : View.GONE);
        updatePlayButton();
        scroll.scrollTo(0, 0);
        if (k == TAB_CONTROL && nowPlaying != null && visible) refresh();
    }

    private void buildSend(LinearLayout t) {
        t.addView(Ui.title(this, getString(R.string.tab_send), 34), Ui.full(this, 18));
        LinearLayout card = Ui.card(this);
        TextView send = Ui.primary(this, Ui.withIcon(this, Ui.I_IMAGES, getString(R.string.send_photos)));
        send.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { pick(); }
        });
        card.addView(send, Ui.full(this, 10));

        uploadBar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        uploadBar.setMax(100);
        uploadBar.setProgressTintList(android.content.res.ColorStateList.valueOf(Ui.ACCENT));
        uploadBar.setProgressBackgroundTintList(android.content.res.ColorStateList.valueOf(Ui.CARD2));
        uploadBar.setVisibility(View.GONE);
        card.addView(uploadBar, Ui.full(this, 2));
        uploadState = Ui.text(this, "", 14, Ui.TEXT, false);
        uploadState.setVisibility(View.GONE);
        card.addView(uploadState, Ui.full(this, 8));

        Ui.switchRow(this, card, Ui.I_PLAY, getString(R.string.show_now_short), null, store.showNow(), new Ui.Switch.OnChange() {
            @Override public void changed(boolean on) { store.setShowNow(on); }
        });
        folderBtn = Ui.listRow(this, card, Ui.I_FOLDER, getString(R.string.folder_short), "", new View.OnClickListener() {
            @Override public void onClick(View v) { chooseFolder(); }
        }).findViewWithTag("value");
        t.addView(card, Ui.full(this, 12));
        updateFolder();
    }

    private void openSources() { Ui.go(this, f, Ui.TAB_SOURCES, null); }

    private TextView ctrl(int icon, float sp, int color) {
        TextView b = Ui.iconButton(this, icon, sp, color);
        b.setPadding(Ui.dp(this, 6), Ui.dp(this, 6), Ui.dp(this, 6), Ui.dp(this, 6));
        return b;
    }

    private void buildControl(LinearLayout t) {
        TextView lab = Ui.label(this, getString(R.string.now_playing));
        lab.setGravity(Gravity.CENTER);
        lab.setPadding(0, Ui.dp(this, 4), 0, Ui.dp(this, 16));
        t.addView(lab, new LinearLayout.LayoutParams(-1, -2));

        // artwork: the picture on the frame, eye (preview on/off) and i (details) in the corners
        stage = new android.widget.FrameLayout(this);
        android.graphics.drawable.GradientDrawable sg = new android.graphics.drawable.GradientDrawable();
        sg.setColor(android.graphics.Color.argb(40, 255, 255, 255));
        sg.setCornerRadius(Ui.dp(this, 26));
        stage.setBackground(sg);
        stage.setClipToOutline(true);
        stage.setElevation(Ui.dp(this, 22));
        preview = new android.widget.ImageView(this);
        preview.setScaleType(android.widget.ImageView.ScaleType.CENTER_CROP);
        preview.setVisibility(View.GONE);
        stage.addView(preview, new android.widget.FrameLayout.LayoutParams(-1, -1));
        previewEmpty = Ui.column(this);
        previewEmpty.setGravity(Gravity.CENTER);
        previewEmptyIcon = Ui.icon(this, Ui.I_IMAGE, 44, Ui.MUTED);
        previewEmpty.addView(previewEmptyIcon);
        previewNote = Ui.text(this, "", 13, Ui.MUTED, false);
        previewNote.setGravity(Gravity.CENTER);
        previewNote.setPadding(Ui.dp(this, 24), Ui.dp(this, 10), Ui.dp(this, 24), 0);
        previewEmpty.addView(previewNote);
        stage.addView(previewEmpty, new android.widget.FrameLayout.LayoutParams(-1, -1));
        previewBtn = Ui.glassCircle(this, Ui.I_EYE, 15);
        previewBtn.setContentDescription(getString(R.string.preview));
        previewBtn.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { togglePreview(); }
        });
        android.widget.FrameLayout.LayoutParams pl = new android.widget.FrameLayout.LayoutParams(Ui.dp(this, 36), Ui.dp(this, 36), Gravity.TOP | Gravity.START);
        pl.setMargins(Ui.dp(this, 12), Ui.dp(this, 12), 0, 0);
        stage.addView(previewBtn, pl);
        TextView info = Ui.glassCircle(this, Ui.I_INFO, 15);
        info.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { showInfo(); }
        });
        android.widget.FrameLayout.LayoutParams il = new android.widget.FrameLayout.LayoutParams(Ui.dp(this, 36), Ui.dp(this, 36), Gravity.TOP | Gravity.END);
        il.setMargins(0, Ui.dp(this, 12), Ui.dp(this, 12), 0);
        stage.addView(info, il);
        stage.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { if (!store.preview()) togglePreview(); }
        });
        LinearLayout.LayoutParams stl = new LinearLayout.LayoutParams(-1, Ui.dp(this, 270));
        stl.setMargins(Ui.dp(this, 4), 0, Ui.dp(this, 4), 0);
        t.addView(stage, stl);

        // title (what is on screen) and the playlist in gold
        nowTitle = Ui.title(this, f.name, 24);
        nowTitle.setSingleLine(true);
        nowTitle.setEllipsize(android.text.TextUtils.TruncateAt.END);
        nowTitle.setPadding(Ui.dp(this, 8), Ui.dp(this, 24), Ui.dp(this, 8), 0);
        t.addView(nowTitle);
        nowSub = Ui.text(this, "", 16, Ui.ACCENT, false);
        nowSub.setSingleLine(true);
        nowSub.setEllipsize(android.text.TextUtils.TruncateAt.END);
        nowSub.setPadding(Ui.dp(this, 8), Ui.dp(this, 3), Ui.dp(this, 8), 0);
        t.addView(nowSub);

        // thin progress line with times
        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(1000);
        progress.setProgressTintList(android.content.res.ColorStateList.valueOf(Ui.TEXT));
        progress.setProgressBackgroundTintList(android.content.res.ColorStateList.valueOf(android.graphics.Color.argb(80, 255, 255, 255)));
        LinearLayout.LayoutParams prl = new LinearLayout.LayoutParams(-1, Ui.dp(this, 4));
        prl.setMargins(Ui.dp(this, 8), Ui.dp(this, 20), Ui.dp(this, 8), Ui.dp(this, 6));
        t.addView(progress, prl);
        LinearLayout times = Ui.row(this);
        times.setPadding(Ui.dp(this, 8), 0, Ui.dp(this, 8), 0);
        timeLeft = Ui.text(this, "", 12, Ui.MUTED, true);
        times.addView(timeLeft, new LinearLayout.LayoutParams(0, -2, 1f));
        timeRight = Ui.text(this, "", 12, Ui.MUTED, true);
        times.addView(timeRight);
        t.addView(times);

        // shuffle · previous · play/pause · next · screen
        LinearLayout tr = Ui.row(this);
        tr.setGravity(Gravity.CENTER);
        tr.setPadding(Ui.dp(this, 8), Ui.dp(this, 14), Ui.dp(this, 8), 0);
        shuffleBtn = ctrl(Ui.I_SHUFFLE, 21, Ui.MUTED);
        shuffleBtn.setContentDescription(getString(R.string.set_shuffle));
        shuffleBtn.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { toggleShuffle(); }
        });
        TextView prev = ctrl(Ui.I_PREV, 34, Ui.TEXT);
        prev.setOnClickListener(new View.OnClickListener() { @Override public void onClick(View v) { act("previous"); } });
        pauseBtn = ctrl(Ui.I_PAUSE, 52, Ui.TEXT);
        pauseBtn.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) {
                boolean pausing = running && !paused;
                if (pausing) pausedAt = android.os.SystemClock.elapsedRealtime();
                else if (paused) itemSince += android.os.SystemClock.elapsedRealtime() - pausedAt;
                act(pausing ? "pause" : "resume");
            }
        });
        pauseBtn.setOnLongClickListener(new View.OnLongClickListener() {
            @Override public boolean onLongClick(View v) {
                act("stop");
                Toast.makeText(FrameActivity.this, R.string.state_stopped, Toast.LENGTH_SHORT).show();
                return true;
            }
        });
        TextView next = ctrl(Ui.I_NEXT, 34, Ui.TEXT);
        next.setOnClickListener(new View.OnClickListener() { @Override public void onClick(View v) { act("next"); } });
        screenBtn = ctrl(Ui.I_DISPLAY, 21, Ui.MUTED);
        screenBtn.setContentDescription(getString(R.string.sec_screen));
        screenBtn.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { display(!screenOn); }
        });
        View[] cs = {shuffleBtn, prev, pauseBtn, next, screenBtn};
        for (int i = 0; i < cs.length; i++) {
            tr.addView(cs[i], new LinearLayout.LayoutParams(-2, -2));
            if (i < cs.length - 1) tr.addView(new View(this), new LinearLayout.LayoutParams(0, 1, 1f));
        }
        t.addView(tr, new LinearLayout.LayoutParams(-1, -2));

        // volume: speaker (tap = mute) · slider · percent
        LinearLayout vr = Ui.row(this);
        vr.setPadding(Ui.dp(this, 8), Ui.dp(this, 18), Ui.dp(this, 8), 0);
        muteBtn = ctrl(Ui.I_VOL_DOWN, 17, Ui.MUTED);
        muteBtn.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { toggleMute(); }
        });
        vr.addView(muteBtn);
        volume = new SeekBar(this);
        volume.setMax(100);
        volume.setProgressTintList(android.content.res.ColorStateList.valueOf(Ui.TEXT));
        volume.setProgressBackgroundTintList(android.content.res.ColorStateList.valueOf(android.graphics.Color.argb(90, 255, 255, 255)));
        volume.setThumbTintList(android.content.res.ColorStateList.valueOf(Ui.TEXT));
        volume.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(SeekBar s, int p, boolean user) { volText.setText(p + "%"); }
            @Override public void onStartTrackingTouch(SeekBar s) { busyVolume = true; }
            @Override public void onStopTrackingTouch(final SeekBar s) {
                final int v = s.getProgress();
                bg(new Api.Call<Void>() {
                    @Override public Void run() throws IOException { api().setVolume(v); return null; }
                }, null);
                main.postDelayed(new Runnable() { @Override public void run() { busyVolume = false; } }, 1500);
            }
        });
        vr.addView(volume, new LinearLayout.LayoutParams(0, android.view.ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        volText = Ui.text(this, "", 13, Ui.MUTED, true);
        volText.setGravity(Gravity.END);
        vr.addView(volText, new LinearLayout.LayoutParams(Ui.dp(this, 42), android.view.ViewGroup.LayoutParams.WRAP_CONTENT));
        t.addView(vr, new LinearLayout.LayoutParams(-1, -2));

        // settings + more as two glass pills
        LinearLayout pills = Ui.row(this);
        pills.setPadding(0, Ui.dp(this, 22), 0, 0);
        TextView gear = Ui.button(this, Ui.withIcon(this, Ui.I_GEAR, getString(R.string.settings)), 15);
        gear.setGravity(Gravity.CENTER);
        gear.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) {
                startActivity(new Intent(FrameActivity.this, SettingsActivity.class).putExtra("host", f.host));
            }
        });
        pills.addView(gear, Ui.weight(this, 4));
        TextView pls = Ui.button(this, Ui.withIcon(this, Ui.I_PLAYLIST, getString(R.string.tab_playlists)), 15);
        pls.setGravity(Gravity.CENTER);
        pls.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { showTab(TAB_PLAYLISTS); }
        });
        pills.addView(pls, Ui.weight(this, 4));
        t.addView(pills, new LinearLayout.LayoutParams(-1, -2));
        updatePreviewUi();
    }

    private void togglePreview() {
        store.setPreview(!store.preview());
        lastPreviewKey = null;
        updatePreviewUi();
        if (store.preview()) loadPreview(currentItem);
    }

    private void showInfo() {
        JSONObject it = currentItem;
        StringBuilder sb = new StringBuilder();
        String state = getString(!running ? R.string.state_stopped : paused ? R.string.state_paused : R.string.state_playing);
        sb.append(state);
        if (!screenOn) sb.append(" · ").append(getString(R.string.screen_is_off));
        String name = str(it, "title");
        if (name.isEmpty()) name = str(it, "fileName");
        if (!name.isEmpty()) sb.append("\n\n").append(getString(R.string.info_file)).append(": ").append(name);
        String path = str(it, "filePath");
        if (path.isEmpty()) path = str(it, "path");
        int cut = path.lastIndexOf('/');
        if (cut > 0) sb.append("\n").append(getString(R.string.info_folder)).append(": ").append(path.substring(0, cut));
        String type = str(it, "mediaType");
        if (!type.isEmpty()) sb.append("\n").append(getString(R.string.info_type)).append(": ").append(type);
        if (!currentPlaylists.isEmpty()) sb.append("\n").append(getString(R.string.info_playlist)).append(": ").append(currentPlaylists);
        sb.append("\n\n").append(getString(R.string.info_stop_hint));
        new AlertDialog.Builder(this).setTitle(R.string.now_playing).setMessage(sb.toString())
                .setPositiveButton(R.string.ok, null).show();
    }

    private void setShuffleUi() { shuffleBtn.setTextColor(shuffle ? Ui.ACCENT : Ui.MUTED); }

    private void toggleShuffle() {
        final boolean want = !shuffle;
        shuffle = want;
        setShuffleUi();
        bg(new Api.Call<Void>() {
            @Override public Void run() throws IOException { api().setSlideshow("randomizeOrder", want); return null; }
        }, new Done<Void>() {
            @Override public void done(Void r) {
                Toast.makeText(FrameActivity.this, want ? R.string.shuffle_on : R.string.shuffle_off, Toast.LENGTH_SHORT).show();
            }
        });
    }

    private void setMuteUi() {
        muteBtn.setText(Ui.ic(muted ? Ui.I_VOL_MUTE : Ui.I_VOL_DOWN));
        muteBtn.setTextColor(muted ? Ui.ACCENT : Ui.MUTED);
    }

    private void toggleMute() {
        final boolean want = !muted;
        muted = want;
        setMuteUi();
        bg(new Api.Call<Void>() {
            @Override public Void run() throws IOException { api().setMute(want); return null; }
        }, null);
    }

    private void buildPlaylists(LinearLayout t) {
        t.addView(Ui.title(this, getString(R.string.tab_playlists), 34), Ui.full(this, 14));
        LinearLayout sr = Ui.row(this);
        android.graphics.drawable.GradientDrawable sg = new android.graphics.drawable.GradientDrawable();
        sg.setColor(android.graphics.Color.argb(30, 255, 255, 255));
        sg.setCornerRadius(Ui.dp(this, 12));
        sr.setBackground(sg);
        sr.setPadding(Ui.dp(this, 12), 0, Ui.dp(this, 12), 0);
        sr.addView(Ui.icon(this, Ui.I_SEARCH, 15, Ui.MUTED));
        search = new EditText(this);
        search.setHint(R.string.search_playlists);
        search.setHintTextColor(Ui.MUTED);
        search.setTextColor(Ui.TEXT);
        search.setTypeface(Ui.font(this, 0));
        search.setTextSize(16);
        search.setSingleLine(true);
        search.setBackground(null);
        search.setPadding(Ui.dp(this, 8), Ui.dp(this, 9), 0, Ui.dp(this, 9));
        search.addTextChangedListener(new android.text.TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int a, int b, int c) { }
            @Override public void onTextChanged(CharSequence s, int a, int b, int c) { }
            @Override public void afterTextChanged(android.text.Editable e) { renderPlaylists(); }
        });
        sr.addView(search, new LinearLayout.LayoutParams(0, android.view.ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        t.addView(sr, Ui.full(this, 12));
        t.addView(Ui.segmented(this, new String[]{getString(R.string.pl_seg_all), getString(R.string.tab_playlists), getString(R.string.mix_seg_folders), getString(R.string.pl_seg_plugins)},
                plFilter, new Ui.Segment() {
                    @Override public void selected(int i) { plFilter = i; renderPlaylists(); }
                }), Ui.full(this, 6));
        playlists = Ui.column(this);
        t.addView(playlists);
    }


    private void moreMenu() {
        new AlertDialog.Builder(this)
                .setItems(new CharSequence[]{getString(R.string.settings), getString(R.string.src_card_button), getString(R.string.tab_more),
                                getString(R.string.open_webui), getString(R.string.login_settings), getString(R.string.all_frames)},
                        new DialogInterface.OnClickListener() {
                            @Override public void onClick(DialogInterface d, int w) {
                                if (w == 0) { startActivity(new Intent(FrameActivity.this, SettingsActivity.class).putExtra("host", f.host)); return; }
                                if (w == 1) { openSources(); return; }
                                if (w == 2) { Ui.go(FrameActivity.this, f, Ui.TAB_MORE, null); return; }
                                if (w == 4) { login(); return; }
                                if (w == 5) {
                                    startActivity(new Intent(FrameActivity.this, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP));
                                    finish();
                                    return;
                                }
                                WebActivity.open(FrameActivity.this, f, "/", f.name);
                            }
                        }).show();
    }

    private void updateFolder() {
        String name = store.folder();
        if (name == null || name.isEmpty()) name = getString(R.string.default_folder);
        folderBtn.setText(name);
    }

    // ------------------------------------------------------------------ actions

    private Api api() { return new Api(f); }

    /** Runs a call in the background (with sign-in retry); done runs on the UI thread on success. */
    private <T> void bg(final Api.Call<T> call, final Done<T> done) {
        new Thread(new Runnable() {
            @Override public void run() {
                final Api a = new Api(f);
                try {
                    final T r = a.with(call);
                    if (a.pinIfNew()) store.save(f, false);
                    main.post(new Runnable() {
                        @Override public void run() {
                            loginBtn.setVisibility(View.GONE);
                            loginCircle.setVisibility(View.GONE);
                            if (done != null) done.done(r);
                        }
                    });
                } catch (final IOException e) {
                    main.post(new Runnable() { @Override public void run() { failed(e); } });
                }
            }
        }).start();
    }

    interface Done<T> { void done(T r); }

    private void failed(IOException e) {
        if (e instanceof Http.AuthException) {
            loginBtn.setVisibility(View.VISIBLE);
            loginCircle.setVisibility(View.VISIBLE);
            nowPlaying.setText(R.string.login_needed);
            nowSub.setText(R.string.login_needed);
        } else if (e instanceof Http.CertChangedException) {
            Connect.certChanged(this, f, ((Http.CertChangedException) e).fingerprint, new Runnable() {
                @Override public void run() { refresh(); loadPlaylists(); }
            });
        } else {
            nowPlaying.setText(getString(R.string.not_reachable_detail, String.valueOf(e.getMessage())));
            nowSub.setText(nowPlaying.getText());
        }
    }

    private void login() {
        Connect.show(this, f, new Runnable() {
            @Override public void run() {
                Frame fresh = store.find(f.host);
                if (fresh != null) f = fresh;
                setPickerText();
                refresh();
                loadPlaylists();
            }
        });
    }

    private void act(final String what) {
        bg(new Api.Call<Void>() {
            @Override public Void run() throws IOException { api().transport(what); return null; }
        }, new Done<Void>() {
            @Override public void done(Void r) { main.postDelayed(new Runnable() { @Override public void run() { refresh(); } }, 600); }
        });
    }

    private void display(final boolean on) {
        bg(new Api.Call<Void>() {
            @Override public Void run() throws IOException { api().setDisplay(on); return null; }
        }, new Done<Void>() {
            @Override public void done(Void r) {
                Toast.makeText(FrameActivity.this, on ? R.string.screen_on_done : R.string.screen_off_done, Toast.LENGTH_SHORT).show();
                main.postDelayed(new Runnable() { @Override public void run() { refresh(); } }, 800);
            }
        });
    }

    private static String str(JSONObject o, String k) {
        if (o == null || o.isNull(k)) return "";
        return o.optString(k, "").trim();
    }

    private void refresh() {
        bg(new Api.Call<Object[]>() {
            @Override public Object[] run() throws IOException {
                Api a = api();
                JSONObject st = a.status();
                JSONObject set = null;
                try { set = a.slideshowSettings(); } catch (IOException ignored) { }
                return new Object[]{st, a.displayPower(), a.volume(), a.activeSources(), set, a.muted()};
            }
        }, new Done<Object[]>() {
            @SuppressWarnings("unchecked")
            @Override public void done(Object[] r) {
                JSONObject st = (JSONObject) r[0];
                String power = (String) r[1];
                int vol = (Integer) r[2];
                java.util.Set<String> act = (java.util.Set<String>) r[3];
                JSONObject set = (JSONObject) r[4];
                Boolean mu = (Boolean) r[5];
                paused = st.optBoolean("isPaused", false);
                running = st.optBoolean("isRunning", false);
                pauseBtn.setText(Ui.ic(paused || !running ? Ui.I_PLAY : Ui.I_PAUSE));
                JSONObject item = st.optJSONObject("currentItem");
                currentItem = item;
                displaySeq = st.has("displaySequence") && !st.isNull("displaySequence") ? st.optLong("displaySequence", -1) : -1;
                String what = str(item, "title");
                if (what.isEmpty()) what = str(item, "fileName");
                if (what.isEmpty()) what = str(item, "sceneTitle");
                if (what.isEmpty()) what = str(item, "name");
                String key = item == null ? "" : item.optString("id", "") + "|" + str(item, "filePath") + "|" + what;
                if (!key.equals(itemKey)) { itemKey = key; itemSince = android.os.SystemClock.elapsedRealtime(); }
                String state = getString(!running ? R.string.state_stopped : paused ? R.string.state_paused : R.string.state_playing);
                boolean screenOff = "off".equals(power) || st.optBoolean("isSleeping", false);
                screenOn = !screenOff;
                String pl = playlistNames(act);
                currentPlaylists = pl;
                if (paused && !wasPaused) pausedAt = android.os.SystemClock.elapsedRealtime();
                wasPaused = paused;
                nowTitle.setText(what.isEmpty() ? (pl.isEmpty() ? f.name : pl) : what);
                String sub = what.isEmpty() || pl.isEmpty() ? state : pl;
                if (paused || !running) sub = pl.isEmpty() ? state : state + " · " + pl;
                if (screenOff) sub += " · " + getString(R.string.screen_is_off);
                nowSub.setText(sub);
                StringBuilder sb = new StringBuilder(state);
                if (!pl.isEmpty()) sb.append(" · ").append(pl);
                if (screenOff) sb.append(" · ").append(getString(R.string.screen_is_off));
                nowPlaying.setText(sb.toString());
                screenBtn.setText(Ui.ic(screenOff ? Ui.I_DISPLAY : Ui.I_DISPLAY_FILL));
                screenBtn.setTextColor(screenOff ? Ui.MUTED : Ui.ACCENT);
                if (set != null) {
                    if (set.has("randomizeOrder")) {
                        shuffle = set.optBoolean("randomizeOrder", false);
                        setShuffleUi();
                    }
                    int d = set.optInt("durationSeconds", 0);
                    if (d > 0) slideSeconds = d;
                }
                if (mu != null) { muted = mu; setMuteUi(); }
                updatePreviewUi();
                loadPreview(item);
                if (vol >= 0 && !busyVolume) { volume.setProgress(vol); volText.setText(vol + "%"); }
                if (!act.equals(active)) { active = act; renderPlaylists(); }
            }
        });
    }

    // ------------------------------------------------------------------ playlists + Quick Mix sources

    /** One thing that can be switched on in the Quick Mix: a saved playlist, a folder or a plugin source. */
    private static final class Src {
        String key, title, sub;
        boolean offline, takeover;
    }

    private List<JSONObject> folderSrc = new ArrayList<>(), pluginSrc = new ArrayList<>();

    private String playlistNames(java.util.Set<String> keys) {
        StringBuilder sb = new StringBuilder();
        for (Src s : allSources()) {
            if (keys.contains(s.key)) {
                if (sb.length() > 0) sb.append(" + ");
                sb.append(s.title);
            }
        }
        return sb.toString();
    }

    private void loadPlaylists() {
        bg(new Api.Call<Object[]>() {
            @Override public Object[] run() throws IOException {
                Api a = api();
                List<JSONObject> pl = a.playlists();
                List<JSONObject> fo = new ArrayList<>(), pg = new ArrayList<>();
                try { fo = a.folderSources(); } catch (IOException ignored) { }
                try { pg = a.pluginSources(); } catch (IOException ignored) { }
                return new Object[]{pl, fo, pg};
            }
        }, new Done<Object[]>() {
            @SuppressWarnings("unchecked")
            @Override public void done(Object[] r) {
                List<JSONObject> list = (List<JSONObject>) r[0];
                java.util.Collections.sort(list, new java.util.Comparator<JSONObject>() {
                    @Override public int compare(JSONObject a, JSONObject b) {
                        return a.optString("name").compareToIgnoreCase(b.optString("name"));
                    }
                });
                allPlaylists = list;
                folderSrc = (List<JSONObject>) r[1];
                pluginSrc = (List<JSONObject>) r[2];
                renderPlaylists();
            }
        });
    }

    /** Takeover playlists belong to plugins (they show news, scores… on their own); kept out of the way. */
    private static boolean isTakeover(JSONObject p) {
        String n = p.optString("name").toLowerCase();
        return n.endsWith("(takeover)") || n.endsWith("(übernahme)");
    }

    private List<Src> allSources() {
        List<Src> out = new ArrayList<>();
        for (JSONObject p : allPlaylists) {
            Src s = new Src();
            s.key = "pl:" + p.optInt("id");
            s.title = p.optString("name", "?").replaceAll("\\s*\\((takeover|Übernahme)\\)$", "");
            s.takeover = isTakeover(p);
            int c = count(p);
            s.sub = c >= 0 ? getResources().getQuantityString(R.plurals.pl_items, c, c) : "";
            out.add(s);
        }
        for (JSONObject o : folderSrc) {
            Src s = new Src();
            String path = o.optString("path", o.optString("Path"));
            s.key = "f:" + path;
            String label = o.optString("label", o.optString("Label", ""));
            if (label.isEmpty()) label = path.substring(path.lastIndexOf('/') + 1);
            s.title = label;
            int c = o.optInt("fileCount", o.optInt("FileCount", 0));
            s.offline = !"online".equalsIgnoreCase(o.optString("availability", o.optString("Availability", "online")));
            s.sub = s.offline ? getString(R.string.mix_offline) : getResources().getQuantityString(R.plurals.pl_items, c, c);
            out.add(s);
        }
        for (JSONObject o : pluginSrc) {
            Src s = new Src();
            s.key = "p:" + o.optString("name");
            String dn = o.optString("displayName", "");
            s.title = dn.isEmpty() ? o.optString("name") : dn;
            int c = o.has("playableItemCount") && !o.isNull("playableItemCount") ? o.optInt("playableItemCount") : o.optInt("cachedFileCount");
            s.sub = getResources().getQuantityString(R.plurals.pl_items, c, c);
            s.offline = c <= 0;
            out.add(s);
        }
        return out;
    }

    /** Sources switched on in the app (like the switches on DynaFrame's "Choose Playlist" page). */
    private java.util.Set<String> selected = new java.util.LinkedHashSet<>();
    private boolean selectionTouched;
    private TextView playSelection;

    private void renderPlaylists() {
        if (playlists == null) return;
        if (!selectionTouched) { selected.clear(); selected.addAll(active); }
        playlists.removeAllViews();
        String q = search == null ? "" : search.getText().toString().trim().toLowerCase();
        List<Src> chosen = new ArrayList<>(), pls = new ArrayList<>(), takeovers = new ArrayList<>(), folders = new ArrayList<>(), plugins = new ArrayList<>();
        for (Src s : allSources()) {
            if (!q.isEmpty() && !s.title.toLowerCase().contains(q)) continue;
            if (plFilter == 0 && selected.contains(s.key) && !s.takeover) { chosen.add(s); continue; }
            if (s.key.startsWith("pl:")) { if (s.takeover) takeovers.add(s); else pls.add(s); }
            else if (s.key.startsWith("f:")) folders.add(s);
            else plugins.add(s);
        }
        updatePlayButton();
        if (allPlaylists.isEmpty() && folderSrc.isEmpty() && pluginSrc.isEmpty()) {
            TextView none = Ui.text(this, getString(R.string.no_playlists), 14, Ui.MUTED, false);
            none.setPadding(Ui.dp(this, 6), Ui.dp(this, 14), 0, 0);
            playlists.addView(none);
            return;
        }
        if (plFilter == 0) {
            group(selectionTouched ? R.string.pl_selected : R.string.pl_playing, chosen);
            group(R.string.pl_all, pls);
            group(R.string.mix_folders, folders);
            group(R.string.mix_plugins, plugins);
        } else if (plFilter == 1) {
            group(0, pls);
        } else if (plFilter == 2) {
            group(0, folders);
        } else {
            group(R.string.mix_plugins, plugins);
            if (!takeovers.isEmpty()) {
                group(R.string.mix_takeover, takeovers);
                TextView note = Ui.text(this, getString(R.string.pl_plugins_note), 13, Ui.MUTED, false);
                note.setPadding(Ui.dp(this, 6), Ui.dp(this, 4), Ui.dp(this, 6), 0);
                playlists.addView(note);
            }
        }
    }

    private void updatePlayButton() {
        if (playSelection == null) return;
        boolean changed = selectionTouched && !selected.equals(active) && tab == TAB_PLAYLISTS;
        playSelection.setVisibility(changed ? View.VISIBLE : View.GONE);
        if (changed) {
            playSelection.setText(selected.isEmpty() ? Ui.withIcon(this, Ui.I_STOP, getString(R.string.pl_stop_all)) : Ui.withIcon(this, Ui.I_PLAY,
                    getResources().getQuantityString(R.plurals.mix_play_n, selected.size(), selected.size())));
        }
    }

    private static int count(JSONObject p) {
        for (String k : new String[]{"itemCount", "itemsCount", "mediaCount", "count", "totalItems"}) {
            if (p.has(k) && !p.isNull(k)) return p.optInt(k, -1);
        }
        org.json.JSONArray a = p.optJSONArray("items");
        return a == null ? -1 : a.length();
    }

    private void group(int title, List<Src> list) {
        if (list.isEmpty()) return;
        if (title != 0) playlists.addView(Ui.section(this, getString(title)));
        else playlists.addView(Ui.gap(this, 12));
        LinearLayout card = Ui.column(this);
        card.setBackground(Ui.glass(this, 22));
        card.setPadding(Ui.dp(this, 14), Ui.dp(this, 2), Ui.dp(this, 12), Ui.dp(this, 2));
        for (int i = 0; i < list.size(); i++) {
            final Src s = list.get(i);
            final boolean playing = active.contains(s.key);
            if (i > 0) Ui.separator(this, card, 52);
            LinearLayout row = Ui.row(this);
            row.setPadding(0, Ui.dp(this, 10), 0, Ui.dp(this, 10));
            // tile: first letter for playlists, folder / puzzle icon for the other sources
            TextView thumb;
            if (s.key.startsWith("pl:")) {
                thumb = Ui.text(this, s.title.isEmpty() ? "?" : s.title.substring(0, 1).toUpperCase(), 17, playing ? Ui.ON_ACCENT : Ui.ACCENT, true);
                thumb.setGravity(Gravity.CENTER);
            } else {
                thumb = Ui.icon(this, s.key.startsWith("f:") ? Ui.I_FOLDER : Ui.I_PUZZLE, 18, playing ? Ui.ON_ACCENT : Ui.ACCENT);
            }
            android.graphics.drawable.GradientDrawable tg = new android.graphics.drawable.GradientDrawable(
                    android.graphics.drawable.GradientDrawable.Orientation.TL_BR,
                    playing ? new int[]{Ui.ACCENT, android.graphics.Color.rgb(176, 120, 36)}
                            : new int[]{android.graphics.Color.argb(70, 216, 161, 59), android.graphics.Color.argb(25, 216, 161, 59)});
            tg.setCornerRadius(Ui.dp(this, 10));
            thumb.setBackground(tg);
            row.addView(thumb, new LinearLayout.LayoutParams(Ui.dp(this, 40), Ui.dp(this, 40)));
            LinearLayout texts = Ui.column(this);
            texts.setPadding(Ui.dp(this, 12), 0, Ui.dp(this, 8), 0);
            TextView n = Ui.text(this, s.title, 16, Ui.TEXT, false);
            n.setSingleLine(true);
            n.setEllipsize(android.text.TextUtils.TruncateAt.END);
            texts.addView(n);
            if (playing) {
                LinearLayout sr = Ui.row(this);
                sr.setPadding(0, Ui.dp(this, 3), 0, 0);
                sr.addView(Ui.pill(this, getString(R.string.pl_now)));
                if (!s.sub.isEmpty()) {
                    TextView st = Ui.text(this, s.sub, 13, Ui.MUTED, false);
                    st.setPadding(Ui.dp(this, 8), 0, 0, 0);
                    sr.addView(st);
                }
                texts.addView(sr);
            } else if (!s.sub.isEmpty()) texts.addView(Ui.text(this, s.sub, 13, s.offline ? Ui.BAD : Ui.MUTED, false));
            row.addView(texts, new LinearLayout.LayoutParams(0, android.view.ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
            TextView only = Ui.iconButton(this, Ui.I_PLAY_CIRCLE, 20, Ui.MUTED);
            only.setPadding(Ui.dp(this, 8), Ui.dp(this, 6), Ui.dp(this, 10), Ui.dp(this, 6));
            only.setContentDescription(getString(R.string.pl_play_only));
            only.setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View v) { startMix(java.util.Collections.singletonList(s.key), s.title); }
            });
            row.addView(only);
            final Ui.Switch sw = new Ui.Switch(this, selected.contains(s.key));
            sw.listener = new Ui.Switch.OnChange() {
                @Override public void changed(boolean on) {
                    selectionTouched = true;
                    if (on) selected.add(s.key); else selected.remove(s.key);
                    updatePlayButton();
                }
            };
            row.addView(sw, new LinearLayout.LayoutParams(Ui.dp(this, 51), Ui.dp(this, 31)));
            row.setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View v) { sw.toggle(); }
            });
            row.setOnLongClickListener(new View.OnLongClickListener() {
                @Override public boolean onLongClick(View v) { startMix(java.util.Collections.singletonList(s.key), s.title); return true; }
            });
            if (s.offline) row.setAlpha(0.65f);
            card.addView(row);
        }
        playlists.addView(card, Ui.full(this, 6));
    }

    private void stopAll() {
        bg(new Api.Call<Void>() {
            @Override public Void run() throws IOException { api().stopAll(); return null; }
        }, new Done<Void>() {
            @Override public void done(Void r) {
                selectionTouched = false;
                active = new java.util.HashSet<>();
                renderPlaylists();
                Toast.makeText(FrameActivity.this, R.string.pl_stopped_all, Toast.LENGTH_SHORT).show();
                main.postDelayed(new Runnable() { @Override public void run() { refresh(); } }, 1200);
            }
        });
    }

    /** Plays the given sources together, the way the web page's Quick Mix does. */
    private void startMix(final List<String> keys, final String name) {
        if (keys.isEmpty()) return;
        Toast.makeText(this, getString(R.string.starting, name), Toast.LENGTH_SHORT).show();
        final List<Integer> ids = new ArrayList<>();
        final List<String> folders = new ArrayList<>(), plugins = new ArrayList<>();
        for (String k : keys) {
            if (k.startsWith("pl:")) { try { ids.add(Integer.parseInt(k.substring(3))); } catch (NumberFormatException ignored) { } }
            else if (k.startsWith("f:")) folders.add(k.substring(2));
            else if (k.startsWith("p:")) plugins.add(k.substring(2));
        }
        for (int k = ids.size() - 1; k >= 0; k--) store.addRecent(f.host, ids.get(k));
        bg(new Api.Call<Void>() {
            @Override public Void run() throws IOException { api().startMix(folders, plugins, ids, name); return null; }
        }, new Done<Void>() {
            @Override public void done(Void r) {
                selectionTouched = false;
                active = new java.util.HashSet<>(keys);
                renderPlaylists();
                main.postDelayed(new Runnable() { @Override public void run() { refresh(); } }, 1500);
            }
        });
    }

    private void playSelected() {
        if (selected.isEmpty()) { stopAll(); return; }
        List<String> keys = new ArrayList<>(selected);
        String name = "Quick Mix";
        if (keys.size() == 1) for (Src s : allSources()) if (s.key.equals(keys.get(0))) name = s.title;
        startMix(keys, name);
    }


    private void chooseFolder() {
        bg(new Api.Call<List<String>>() {
            @Override public List<String> run() throws IOException { return api().folders(); }
        }, new Done<List<String>>() {
            @Override public void done(final List<String> paths) {
                final List<String> names = new ArrayList<>();
                String def = getString(R.string.default_folder);
                names.add(def);
                for (String p : paths) {
                    String n = p.substring(p.lastIndexOf('/') + 1);
                    if (!n.equals(def)) names.add(n);
                }
                names.add(getString(R.string.new_folder));
                new AlertDialog.Builder(FrameActivity.this)
                        .setTitle(R.string.folder_title)
                        .setItems(names.toArray(new CharSequence[0]), new DialogInterface.OnClickListener() {
                            @Override public void onClick(DialogInterface d, int w) {
                                if (w == names.size() - 1) newFolder();
                                else { store.setFolder(w == 0 ? null : names.get(w)); updateFolder(); }
                            }
                        }).show();
            }
        });
    }

    private void newFolder() {
        final EditText in = new EditText(this);
        in.setSingleLine(true);
        in.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        LinearLayout box = Ui.column(this);
        int p = Ui.dp(this, 20);
        box.setPadding(p, 0, p, 0);
        box.addView(in);
        new AlertDialog.Builder(this).setTitle(R.string.new_folder).setView(box)
                .setPositiveButton(R.string.ok, new DialogInterface.OnClickListener() {
                    @Override public void onClick(DialogInterface d, int w) {
                        String n = in.getText().toString().trim().replaceAll("[/\\\\]", "-");
                        if (n.isEmpty()) return;
                        store.setFolder(n);
                        updateFolder();
                    }
                }).setNegativeButton(R.string.cancel, null).show();
    }

    // ------------------------------------------------------------------ upload

    private void pick() {
        Intent i;
        if (Build.VERSION.SDK_INT >= 33) {
            i = new Intent(MediaStore.ACTION_PICK_IMAGES);
            i.putExtra(MediaStore.EXTRA_PICK_IMAGES_MAX, Math.min(100, MediaStore.getPickImagesMaxLimit()));
        } else {
            i = new Intent(Intent.ACTION_GET_CONTENT);
            i.setType("*/*");
            i.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{"image/*", "video/*"});
            i.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
            i.addCategory(Intent.CATEGORY_OPENABLE);
        }
        try {
            startActivityForResult(i, PICK);
        } catch (Exception e) {
            Toast.makeText(this, R.string.no_picker, Toast.LENGTH_LONG).show();
        }
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req != PICK || res != RESULT_OK || data == null) return;
        List<Uri> uris = new ArrayList<>();
        ClipData clip = data.getClipData();
        if (clip != null) for (int k = 0; k < clip.getItemCount(); k++) uris.add(clip.getItemAt(k).getUri());
        else if (data.getData() != null) uris.add(data.getData());
        if (uris.isEmpty()) return;
        startUpload(uris);
    }

    private void startUpload(List<Uri> uris) {
        if (UploadService.running) {
            Toast.makeText(this, R.string.upload_busy, Toast.LENGTH_LONG).show();
            return;
        }
        uploadBar.setVisibility(View.VISIBLE);
        uploadBar.setIndeterminate(true);
        uploadState.setVisibility(View.VISIBLE);
        uploadState.setTextColor(Ui.TEXT);
        uploadState.setText(getResources().getQuantityString(R.plurals.sending_n, uris.size(), uris.size()));
        try {
            UploadService.start(this, f, uris, store.showNow());
        } catch (SecurityException e) {
            uploadBar.setVisibility(View.GONE);
            uploadState.setText(getString(R.string.upload_error, f.name, String.valueOf(e.getMessage())));
        }
    }

    @Override
    public void onUploadState(final String host, final String text, final int percent, final boolean finished) {
        main.post(new Runnable() {
            @Override public void run() {
                if (!f.host.equals(host)) return;
                uploadState.setVisibility(View.VISIBLE);
                uploadState.setText(text);
                if (finished) {
                    uploadBar.setVisibility(View.GONE);
                    Frame fresh = store.find(f.host);
                    if (fresh != null) f = fresh;
                    refresh();
                } else {
                    uploadBar.setVisibility(View.VISIBLE);
                    uploadBar.setIndeterminate(percent < 0);
                    if (percent >= 0) uploadBar.setProgress(percent);
                }
            }
        });
    }
}
