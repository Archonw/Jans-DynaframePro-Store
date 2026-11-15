package de.archonw.remoteframetv;

import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.StateListDrawable;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.widget.TextView;

/** Small helpers for a TV-friendly look without extra libraries. */
final class Ui {
    static final int BG = Color.rgb(18, 21, 29);
    static final int CARD = Color.rgb(34, 39, 52);
    static final int FOCUS = Color.rgb(201, 162, 90);
    static final int TEXT = Color.rgb(240, 240, 240);
    static final int MUTED = Color.rgb(160, 166, 180);

    static int dp(Context c, float v) {
        return (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, c.getResources().getDisplayMetrics());
    }

    static TextView text(Context c, String s, float sp, int color, boolean bold) {
        TextView t = new TextView(c);
        t.setText(s);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        t.setTextColor(color);
        if (bold) t.setTypeface(Typeface.DEFAULT_BOLD);
        return t;
    }

    /** A focusable card: gold frame and lighter background when the remote is on it. */
    static TextView button(Context c, CharSequence s, float sp) {
        TextView t = new TextView(c);
        t.setText(s);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        t.setTextColor(new ColorStateList(
                new int[][]{{android.R.attr.state_focused}, {}},
                new int[]{Color.WHITE, TEXT}));
        t.setFocusable(true);
        t.setFocusableInTouchMode(false);
        t.setClickable(true);
        t.setGravity(Gravity.CENTER_VERTICAL);
        int ph = dp(c, 20), pv = dp(c, 14);
        t.setPadding(ph, pv, ph, pv);
        StateListDrawable bg = new StateListDrawable();
        bg.addState(new int[]{android.R.attr.state_focused}, card(c, Color.rgb(52, 58, 76), FOCUS));
        bg.addState(new int[]{android.R.attr.state_pressed}, card(c, Color.rgb(52, 58, 76), FOCUS));
        bg.addState(new int[]{}, card(c, CARD, Color.TRANSPARENT));
        t.setBackground(bg);
        t.setOnFocusChangeListener(new View.OnFocusChangeListener() {
            @Override public void onFocusChange(View v, boolean has) {
                v.animate().scaleX(has ? 1.03f : 1f).scaleY(has ? 1.03f : 1f).setDuration(120).start();
            }
        });
        return t;
    }

    private static GradientDrawable card(Context c, int fill, int stroke) {
        GradientDrawable g = new GradientDrawable();
        g.setColor(fill);
        g.setCornerRadius(dp(c, 12));
        g.setStroke(dp(c, 3), stroke);
        return g;
    }
}
