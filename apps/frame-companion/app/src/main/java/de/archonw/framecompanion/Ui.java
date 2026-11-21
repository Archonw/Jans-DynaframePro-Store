package de.archonw.framecompanion;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.res.ColorStateList;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.os.Build;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowInsets;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

/**
 * The "glass" look: the current photo blurred behind everything, frosted cards, a floating
 * tab bar, Inter type and the gold accent of DynaFrame's web UI. No extra libraries.
 */
final class Ui {
    // Gold accent and cream text from DynaFrame's web UI, frosted white glass on a dark, blurred photo.
    static final int BG = Color.rgb(16, 13, 10);
    static final int SOLID = Color.rgb(31, 27, 21);                 // opaque surface (dialogs, tab bar)
    static final int CARD = Color.argb(26, 255, 255, 255);          // glass card
    static final int CARD2 = Color.argb(40, 255, 255, 255);         // stronger glass (buttons, fields)
    static final int BORDER = Color.argb(36, 255, 255, 255);        // hairline around glass
    static final int LINE = Color.argb(24, 255, 255, 255);          // separators inside cards
    static final int ACCENT = Color.rgb(216, 161, 59);              // #D8A13B
    static final int ON_ACCENT = Color.rgb(28, 22, 12);
    static final int TEXT = Color.rgb(247, 241, 230);
    static final int MUTED = Color.argb(160, 247, 241, 230);
    static final int BAD = Color.rgb(239, 106, 112);
    static final int GOOD = Color.rgb(110, 200, 140);
    static final int ACTIVE = Color.argb(60, 216, 161, 59);
    static final int ACCENT_DIM = Color.argb(130, 216, 161, 59);

    // Bootstrap Icons (the icon font DynaFrame's web UI uses), MIT licence, assets/bootstrap-icons.ttf
    static final int I_HOUSE = 0xf425, I_UPLOAD = 0xf297, I_IMAGES = 0xf42b, I_PLAY_CIRCLE = 0xf4f3,
            I_PLAY = 0xf4f4, I_PAUSE = 0xf4c3, I_PREV = 0xf563, I_NEXT = 0xf557, I_STOP = 0xf592,
            I_DISPLAY = 0xf302, I_MOON = 0xf497, I_SUN = 0xf5a2, I_VOL_UP = 0xf611, I_VOL_DOWN = 0xf60b,
            I_PLAYLIST = 0xf2cb, I_SEARCH = 0xf52a, I_DOWN = 0xf282, I_RIGHT = 0xf285, I_GEAR = 0xf3e5,
            I_KEY = 0xf44f, I_FOLDER = 0xf3d7, I_CHECK = 0xf26a, I_RECENT = 0xf292, I_PLUG = 0xf4f7,
            I_REFRESH = 0xf130, I_PLUS = 0xf64d, I_GLOBE = 0xf3ee, I_LOCK = 0xf47b, I_SLIDERS = 0xf56b,
            I_LINK = 0xf1c5, I_BROADCAST = 0xf1d6, I_CIRCLE = 0xf28a, I_TOGGLE_ON = 0xf5d6, I_TOGGLE_OFF = 0xf5d5,
            I_IMAGE = 0xf42a, I_POWER = 0xf4ff, I_SHUFFLE = 0xf544, I_STOPWATCH = 0xf597, I_MAGIC = 0xf675,
            I_LAYERS = 0xf45b, I_FILM = 0xf3c3, I_RESTART = 0xf116, I_DISPLAY_FILL = 0xf301, I_EYE = 0xf341,
            I_EYE_SLASH = 0xf340, I_VOL_MUTE = 0xf60d, I_DOTS = 0xf5d4, I_CLOUD_PLUS = 0xf2b2, I_PUZZLE = 0xf503,
            I_INFO = 0xf431, I_BACK = 0xf12f, I_SHOP = 0xf54c, I_GRID = 0xf3fc, I_ARROW_DOWN_CIRCLE = 0xf11e;

    private static Typeface icons, regular, semi, display;

    static Typeface icons(Context c) {
        if (icons == null) {
            try { icons = Typeface.createFromAsset(c.getAssets(), "bootstrap-icons.ttf"); } catch (Exception e) { icons = Typeface.DEFAULT; }
        }
        return icons;
    }

    /** Inter (OFL): 0 = regular, 1 = semibold, 2 = display bold for big titles. */
    static Typeface font(Context c, int weight) {
        if (regular == null) {
            try {
                regular = Typeface.createFromAsset(c.getAssets(), "Inter-Regular.otf");
                semi = Typeface.createFromAsset(c.getAssets(), "Inter-SemiBold.otf");
                display = Typeface.createFromAsset(c.getAssets(), "InterDisplay-Bold.otf");
            } catch (Exception e) {
                regular = Typeface.DEFAULT; semi = Typeface.DEFAULT_BOLD; display = Typeface.DEFAULT_BOLD;
            }
        }
        return weight == 2 ? display : weight == 1 ? semi : regular;
    }

    static String ic(int code) { return new String(Character.toChars(code)); }

    /** A single icon as text. */
    static TextView icon(Context c, int code, float sp, int color) {
        TextView t = text(c, ic(code), sp, color, false);
        t.setTypeface(icons(c));
        t.setGravity(Gravity.CENTER);
        t.setIncludeFontPadding(false);
        return t;
    }

    /** A plain icon you can tap (round ripple, no background), like the player buttons. */
    static TextView iconButton(Context c, int code, float sp, int color) {
        TextView t = icon(c, code, sp, color);
        t.setClickable(true);
        t.setFocusable(true);
        t.setBackground(new RippleDrawable(ColorStateList.valueOf(Color.argb(50, 255, 255, 255)), null, null));
        return t;
    }

    /** Round frosted button with an icon (header buttons). */
    static TextView glassCircle(Context c, int code, float sp) {
        TextView t = icon(c, code, sp, TEXT);
        GradientDrawable g = new GradientDrawable();
        g.setShape(GradientDrawable.OVAL);
        g.setColor(Color.argb(34, 255, 255, 255));
        g.setStroke(dp(c, 1), Color.argb(46, 255, 255, 255));
        t.setBackground(new RippleDrawable(ColorStateList.valueOf(Color.argb(60, 255, 255, 255)), g, null));
        t.setClickable(true);
        t.setFocusable(true);
        return t;
    }

    /** "icon  label" with the icon in the icon font. */
    static CharSequence withIcon(Context c, int code, CharSequence label) {
        android.text.SpannableStringBuilder sb = new android.text.SpannableStringBuilder(ic(code));
        sb.setSpan(new IconSpan(icons(c)), 0, sb.length(), android.text.Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        sb.append("   ").append(label);
        return sb;
    }

    static final class IconSpan extends android.text.style.MetricAffectingSpan {
        private final Typeface tf;
        IconSpan(Typeface tf) { this.tf = tf; }
        @Override public void updateDrawState(android.text.TextPaint p) { p.setTypeface(tf); }
        @Override public void updateMeasureState(android.text.TextPaint p) { p.setTypeface(tf); }
    }

    /** A frosted card. */
    static LinearLayout card(Context c) {
        LinearLayout l = column(c);
        l.setBackground(glass(c, 22));
        int p = dp(c, 16);
        l.setPadding(p, p, p, p);
        return l;
    }

    static GradientDrawable glass(Context c, int radiusDp) {
        GradientDrawable g = new GradientDrawable();
        g.setColor(CARD);
        g.setCornerRadius(dp(c, radiusDp));
        g.setStroke(dp(c, 1), BORDER);
        return g;
    }

    static int dp(Context c, float v) {
        return (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, c.getResources().getDisplayMetrics());
    }

    static TextView text(Context c, CharSequence s, float sp, int color, boolean bold) {
        TextView t = new TextView(c);
        t.setText(s);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        t.setTextColor(color);
        t.setTypeface(font(c, bold ? 1 : 0));
        return t;
    }

    /** Big page title like on iOS ("Playlists"). */
    static TextView title(Context c, CharSequence s, float sp) {
        TextView t = text(c, s, sp, TEXT, false);
        t.setTypeface(font(c, 2));
        t.setLetterSpacing(-0.01f);
        return t;
    }

    /** Small uppercase label ("NOW PLAYING"). */
    static TextView label(Context c, String s) {
        TextView t = text(c, s.toUpperCase(), 12, MUTED, true);
        t.setLetterSpacing(0.12f);
        return t;
    }

    static GradientDrawable shape(Context c, int fill, int stroke) {
        GradientDrawable g = new GradientDrawable();
        g.setColor(fill);
        g.setCornerRadius(dp(c, 14));
        if (stroke != 0) g.setStroke(dp(c, 1), stroke);
        return g;
    }

    /** A tappable frosted button. */
    static TextView button(Context c, CharSequence s, float sp) {
        return button(c, s, sp, CARD2, TEXT);
    }

    /** The gold pill for the main action. */
    static TextView primary(Context c, CharSequence s) {
        TextView t = button(c, s, 17, ACCENT, ON_ACCENT);
        t.setTypeface(font(c, 1));
        t.setGravity(Gravity.CENTER);
        int p = dp(c, 16);
        t.setPadding(dp(c, 22), p, dp(c, 22), p);
        GradientDrawable g = new GradientDrawable();
        g.setColor(ACCENT);
        g.setCornerRadius(dp(c, 40));
        t.setBackground(new RippleDrawable(ColorStateList.valueOf(Color.argb(70, 255, 255, 255)), g, null));
        return t;
    }

    static TextView button(Context c, CharSequence s, float sp, int fill, int color) {
        TextView t = new TextView(c);
        t.setText(s);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        t.setTextColor(color);
        t.setTypeface(font(c, 0));
        t.setClickable(true);
        t.setFocusable(true);
        t.setGravity(Gravity.CENTER_VERTICAL);
        int ph = dp(c, 16), pv = dp(c, 14);
        t.setPadding(ph, pv, ph, pv);
        GradientDrawable g = shape(c, fill, fill == ACCENT ? 0 : BORDER);
        g.setCornerRadius(dp(c, 16));
        t.setBackground(new RippleDrawable(ColorStateList.valueOf(Color.argb(60, 216, 161, 59)), g, null));
        return t;
    }

    static LinearLayout.LayoutParams full(Context c, int bottomDp) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, 0, 0, dp(c, bottomDp));
        return lp;
    }

    static LinearLayout.LayoutParams weight(Context c, int marginDp) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        lp.setMargins(dp(c, marginDp), 0, dp(c, marginDp), 0);
        return lp;
    }

    static LinearLayout column(Context c) {
        LinearLayout l = new LinearLayout(c);
        l.setOrientation(LinearLayout.VERTICAL);
        return l;
    }

    static LinearLayout row(Context c) {
        LinearLayout l = new LinearLayout(c);
        l.setOrientation(LinearLayout.HORIZONTAL);
        l.setGravity(Gravity.CENTER_VERTICAL);
        return l;
    }

    // ------------------------------------------------------------------ list rows inside a glass card

    /** One settings-style row: icon tile, label, value, chevron. Returns the row (already added). */
    static LinearLayout listRow(Context c, LinearLayout card, int icon, CharSequence label, CharSequence value, View.OnClickListener click) {
        LinearLayout r = row(c);
        if (needsLine(card)) separator(c, card, icon != 0 ? 46 : 0);
        r.setPadding(0, dp(c, 11), 0, dp(c, 11));
        if (icon != 0) r.addView(tile(c, icon), new LinearLayout.LayoutParams(dp(c, 32), dp(c, 32)));
        TextView l = text(c, label, 16, TEXT, false);
        l.setPadding(dp(c, icon != 0 ? 14 : 0), 0, dp(c, 8), 0);
        r.addView(l, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        TextView v = text(c, value == null ? "" : value, 15, MUTED, false);
        v.setSingleLine(true);
        v.setEllipsize(android.text.TextUtils.TruncateAt.END);
        v.setMaxWidth(dp(c, 170));
        v.setTag("value");
        r.addView(v);
        if (click != null) {
            TextView ch = icon(c, I_RIGHT, 13, MUTED);
            ch.setPadding(dp(c, 8), 0, 0, 0);
            r.addView(ch);
            r.setOnClickListener(click);
            r.setBackground(new RippleDrawable(ColorStateList.valueOf(Color.argb(40, 255, 255, 255)), null, new android.graphics.drawable.ColorDrawable(Color.WHITE)));
        }
        card.addView(r);
        return r;
    }

    /** Row with an iOS-style switch. */
    static Switch switchRow(Context c, LinearLayout card, int icon, CharSequence label, CharSequence sub, boolean on, final Switch.OnChange change) {
        LinearLayout r = row(c);
        if (needsLine(card)) separator(c, card, icon != 0 ? 46 : 0);
        r.setPadding(0, dp(c, 10), 0, dp(c, 10));
        if (icon != 0) r.addView(tile(c, icon), new LinearLayout.LayoutParams(dp(c, 32), dp(c, 32)));
        LinearLayout texts = column(c);
        texts.setPadding(dp(c, icon != 0 ? 14 : 0), 0, dp(c, 10), 0);
        texts.addView(text(c, label, 16, TEXT, false));
        if (sub != null && sub.length() > 0) texts.addView(text(c, sub, 13, MUTED, false));
        r.addView(texts, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        final Switch s = new Switch(c, on);
        s.listener = change;
        r.addView(s, new LinearLayout.LayoutParams(dp(c, 51), dp(c, 31)));
        r.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { s.toggle(); }
        });
        card.addView(r);
        return s;
    }

    private static boolean needsLine(LinearLayout card) {
        return card.getChildCount() > 0 && !"head".equals(card.getChildAt(card.getChildCount() - 1).getTag());
    }

    /** Header inside a grouped card ("SLIDESHOW"). */
    static void cardHead(Context c, LinearLayout card, String title) {
        TextView h = label(c, title);
        h.setTag("head");
        h.setPadding(0, 0, 0, dp(c, 4));
        card.addView(h);
    }

    static void separator(Context c, LinearLayout card, int insetDp) {
        View line = new View(c);
        line.setBackgroundColor(LINE);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, Math.max(1, dp(c, 0.7f)));
        lp.setMargins(dp(c, insetDp), 0, 0, 0);
        card.addView(line, lp);
    }

    /** Small rounded icon tile in gold on dark glass. */
    static TextView tile(Context c, int icon) {
        TextView t = icon(c, icon, 16, ACCENT);
        GradientDrawable g = new GradientDrawable();
        g.setColor(Color.argb(40, 216, 161, 59));
        g.setCornerRadius(dp(c, 9));
        t.setBackground(g);
        return t;
    }

    /** iOS-style switch: gold track when on, white knob. */
    static final class Switch extends View {
        interface OnChange { void changed(boolean on); }
        boolean on;
        OnChange listener;
        private float pos;
        private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final RectF r = new RectF();

        Switch(Context c, boolean on) {
            super(c);
            this.on = on;
            pos = on ? 1 : 0;
            setClickable(true);
            setOnClickListener(new OnClickListener() {
                @Override public void onClick(View v) { toggle(); }
            });
        }

        void toggle() { set(!on, true); }

        void set(boolean value, boolean fire) {
            if (value == on) return;
            on = value;
            android.animation.ValueAnimator a = android.animation.ValueAnimator.ofFloat(pos, on ? 1 : 0);
            a.setDuration(180);
            a.addUpdateListener(new android.animation.ValueAnimator.AnimatorUpdateListener() {
                @Override public void onAnimationUpdate(android.animation.ValueAnimator v) { pos = (Float) v.getAnimatedValue(); invalidate(); }
            });
            a.start();
            if (fire && listener != null) listener.changed(on);
        }

        @Override protected void onDraw(Canvas c) {
            float w = getWidth(), h = getHeight();
            r.set(0, 0, w, h);
            int off = Color.argb(56, 255, 255, 255);
            paint.setColor(blend(off, ACCENT, pos));
            c.drawRoundRect(r, h / 2, h / 2, paint);
            float pad = h * 0.07f, d = h - 2 * pad;
            float x = pad + (w - 2 * pad - d) * pos;
            paint.setColor(Color.argb(60, 0, 0, 0));
            c.drawCircle(x + d / 2, pad + d / 2 + h * 0.03f, d / 2, paint);
            paint.setColor(Color.WHITE);
            c.drawCircle(x + d / 2, pad + d / 2, d / 2, paint);
        }

        private static int blend(int a, int b, float t) {
            return Color.argb((int) (Color.alpha(a) + (Color.alpha(b) - Color.alpha(a)) * t),
                    (int) (Color.red(a) + (Color.red(b) - Color.red(a)) * t),
                    (int) (Color.green(a) + (Color.green(b) - Color.green(a)) * t),
                    (int) (Color.blue(a) + (Color.blue(b) - Color.blue(a)) * t));
        }
    }

    /** Segmented control ("All | Recent | Plugins"). */
    static LinearLayout segmented(final Context c, String[] labels, int selected, final Segment listener) {
        final LinearLayout bar = row(c);
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(Color.argb(30, 255, 255, 255));
        bg.setCornerRadius(dp(c, 11));
        bar.setBackground(bg);
        int p = dp(c, 3);
        bar.setPadding(p, p, p, p);
        for (int i = 0; i < labels.length; i++) {
            final int k = i;
            TextView t = text(c, labels[i], 14, TEXT, true);
            t.setGravity(Gravity.CENTER);
            t.setPadding(0, dp(c, 7), 0, dp(c, 7));
            t.setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View v) { select(c, bar, k); listener.selected(k); }
            });
            bar.addView(t, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        }
        select(c, bar, selected);
        return bar;
    }

    interface Segment { void selected(int index); }

    static void select(Context c, LinearLayout bar, int k) {
        for (int i = 0; i < bar.getChildCount(); i++) {
            TextView t = (TextView) bar.getChildAt(i);
            if (i == k) {
                GradientDrawable g = new GradientDrawable();
                g.setColor(Color.argb(64, 255, 255, 255));
                g.setCornerRadius(dp(c, 8));
                t.setBackground(g);
                t.setTextColor(TEXT);
            } else {
                t.setBackground(null);
                t.setTextColor(MUTED);
            }
        }
    }

    /** Small gold pill ("playing"). */
    static TextView pill(Context c, String s) {
        TextView t = text(c, s, 11, ON_ACCENT, true);
        GradientDrawable g = new GradientDrawable();
        g.setColor(ACCENT);
        g.setCornerRadius(dp(c, 20));
        t.setBackground(g);
        t.setPadding(dp(c, 8), dp(c, 2), dp(c, 8), dp(c, 2));
        return t;
    }

    // ------------------------------------------------------------------ pages, tab bar, window

    static final int TAB_SEND = 0, TAB_CONTROL = 1, TAB_PLAYLISTS = 2, TAB_SOURCES = 3, TAB_MORE = 4, TABS = 5;
    private static final int[] TAB_ICONS = {I_UPLOAD, I_PLAY_CIRCLE, I_PLAYLIST, I_CLOUD_PLUS, I_DOTS};
    private static final int[] TAB_LABELS = {R.string.tab_send, R.string.tab_control, R.string.tab_playlists, R.string.tab_sources, R.string.tab_more};

    /** Called before switching to another screen; return true when the activity shows that tab itself. */
    interface Tabs { boolean show(int tab); }

    /** The floating capsule with the five tabs. */
    static LinearLayout tabBar(final Activity a, final Frame f, final int active, final Tabs local, final TextView[] out) {
        LinearLayout bar = row(a);
        GradientDrawable g = new GradientDrawable();
        g.setColor(Color.argb(228, 30, 26, 21));
        g.setCornerRadius(dp(a, 32));
        g.setStroke(dp(a, 1), Color.argb(40, 255, 255, 255));
        bar.setBackground(g);
        bar.setElevation(dp(a, 14));
        bar.setPadding(dp(a, 6), dp(a, 7), dp(a, 6), dp(a, 7));
        for (int i = 0; i < TABS; i++) {
            final int k = i;
            TextView b = new TextView(a);
            android.text.SpannableStringBuilder sb = new android.text.SpannableStringBuilder(ic(TAB_ICONS[i]));
            sb.setSpan(new IconSpan(icons(a)), 0, sb.length(), 0);
            sb.setSpan(new android.text.style.RelativeSizeSpan(1.75f), 0, sb.length(), 0);
            sb.append("\n").append(a.getString(TAB_LABELS[i]));
            b.setText(sb);
            b.setTypeface(font(a, 1));
            b.setGravity(Gravity.CENTER);
            b.setTextSize(10.5f);
            b.setSingleLine(false);
            b.setMaxLines(2);
            b.setLineSpacing(dp(a, 1), 1f);
            b.setTextColor(i == active ? ACCENT : MUTED);
            b.setBackground(new RippleDrawable(ColorStateList.valueOf(Color.argb(40, 255, 255, 255)), null, null));
            b.setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View v) {
                    if (k == active && local == null) return;   // already here
                    go(a, f, k, local);
                }
            });
            if (out != null) out[i] = b;
            bar.addView(b, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        }
        return bar;
    }

    static void markTab(TextView[] tabs, int active) {
        for (int i = 0; i < tabs.length; i++) if (tabs[i] != null) tabs[i].setTextColor(i == active ? ACCENT : MUTED);
    }

    static void go(Activity a, Frame f, int tab, Tabs local) {
        if (local != null && local.show(tab)) return;
        Intent i;
        if (tab == TAB_SOURCES) i = new Intent(a, SourcesActivity.class);
        else if (tab == TAB_MORE) i = new Intent(a, MoreActivity.class);
        else i = new Intent(a, FrameActivity.class).putExtra("tab", tab)
                    .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        i.putExtra("host", f.host);
        a.startActivity(i);
        a.overridePendingTransition(0, 0);
        if (!(a instanceof FrameActivity)) {
            a.finish();
            a.overridePendingTransition(0, 0);
        }
    }

    /** Draws behind status and navigation bar; the backdrop photo fills the whole screen. */
    static void edgeToEdge(Activity a) {
        Window w = a.getWindow();
        w.setStatusBarColor(Color.TRANSPARENT);
        w.setNavigationBarColor(Color.TRANSPARENT);
        if (Build.VERSION.SDK_INT >= 29) { w.setNavigationBarContrastEnforced(false); w.setStatusBarContrastEnforced(false); }
        w.getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION);
        w.setSoftInputMode(android.view.WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
    }

    /** Gives views room for status bar / navigation bar / keyboard. */
    static void insets(View root, final View top, final View[] bottomPadded, final View[] bottomMargined) {
        final int topBase = top == null ? 0 : top.getPaddingTop();
        final int[] padBase = new int[bottomPadded == null ? 0 : bottomPadded.length];
        for (int i = 0; i < padBase.length; i++) padBase[i] = bottomPadded[i].getPaddingBottom();
        final int[] marBase = new int[bottomMargined == null ? 0 : bottomMargined.length];
        for (int i = 0; i < marBase.length; i++) marBase[i] = ((ViewGroup.MarginLayoutParams) bottomMargined[i].getLayoutParams()).bottomMargin;
        root.setOnApplyWindowInsetsListener(new View.OnApplyWindowInsetsListener() {
            @Override public WindowInsets onApplyWindowInsets(View v, WindowInsets in) {
                if (top != null) top.setPadding(top.getPaddingLeft(), topBase + in.getSystemWindowInsetTop(), top.getPaddingRight(), top.getPaddingBottom());
                int b = in.getSystemWindowInsetBottom();
                for (int i = 0; i < padBase.length; i++) {
                    View p = bottomPadded[i];
                    p.setPadding(p.getPaddingLeft(), p.getPaddingTop(), p.getPaddingRight(), padBase[i] + b);
                }
                for (int i = 0; i < marBase.length; i++) {
                    ViewGroup.MarginLayoutParams lp = (ViewGroup.MarginLayoutParams) bottomMargined[i].getLayoutParams();
                    lp.bottomMargin = marBase[i] + b;
                    bottomMargined[i].setLayoutParams(lp);
                }
                return in.consumeSystemWindowInsets();
            }
        });
    }

    /** Scrolling glass page with padding; returns the column to fill. */
    static LinearLayout page(Activity a) {
        return page(a, null, -1);
    }

    /** Glass page; with a frame it also gets the floating tab bar (tab = the one to highlight). */
    static LinearLayout page(Activity a, Frame f, int tab) {
        edgeToEdge(a);
        FrameLayout stack = new FrameLayout(a);
        ScrollView scroll = new PullScroll(a);
        scroll.setFillViewport(true);
        scroll.setClipToPadding(false);
        scroll.setVerticalScrollBarEnabled(false);
        LinearLayout root = column(a);
        int p = dp(a, 18);
        root.setPadding(p, dp(a, 16), p, dp(a, f != null ? 120 : 28));
        scroll.addView(root);
        stack.addView(scroll, new FrameLayout.LayoutParams(-1, -1));
        View bar = null;
        if (f != null) {
            bar = tabBar(a, f, tab, null, null);
            FrameLayout.LayoutParams bl = new FrameLayout.LayoutParams(-1, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.BOTTOM);
            bl.setMargins(dp(a, 16), 0, dp(a, 16), dp(a, 18));
            stack.addView(bar, bl);
        }
        View all = Backdrop.wrap(a, stack);
        a.setContentView(all);
        insets(all, root, new View[]{root}, bar == null ? null : new View[]{bar});
        return root;
    }

    /** Back arrow + big title at the top of a sub page. */
    static TextView header(final Activity a, LinearLayout root, String title, String sub) {
        LinearLayout r = row(a);
        TextView back = glassCircle(a, I_BACK, 17);
        back.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { a.finish(); }
        });
        r.addView(back, new LinearLayout.LayoutParams(dp(a, 40), dp(a, 40)));
        root.addView(r, full(a, 14));
        root.addView(title(a, title, 32));
        TextView s = null;
        if (sub != null) {
            s = text(a, sub, 14, MUTED, false);
            s.setPadding(0, dp(a, 2), 0, 0);
            root.addView(s);
        }
        root.addView(gap(a, 14));
        return s;
    }

    static TextView section(Context c, String title) {
        TextView t = label(c, title);
        t.setPadding(dp(c, 6), dp(c, 18), 0, dp(c, 8));
        return t;
    }

    static void toast(Context c, CharSequence s) { android.widget.Toast.makeText(c, s, android.widget.Toast.LENGTH_SHORT).show(); }

    static View gap(Context c, int dp) {
        View v = new View(c);
        v.setLayoutParams(new LinearLayout.LayoutParams(1, dp(c, dp)));
        return v;
    }
}
