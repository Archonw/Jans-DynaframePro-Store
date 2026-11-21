package de.archonw.framecompanion;

import android.animation.ValueAnimator;
import android.content.Context;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.ViewConfiguration;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

/** ScrollView with "pull down to refresh": at the top, dragging down shows a turning arrow; letting go far enough runs the refresh. */
final class PullScroll extends ScrollView {

    private Runnable onPull;
    private TextView ind;
    private float downX, downY, startY = -1;
    private boolean pulling;
    private int height;
    private final int slop;

    PullScroll(Context c) {
        super(c);
        slop = ViewConfiguration.get(c).getScaledTouchSlop();
    }

    /** Turn the gesture on; the arrow sits above the first child of content. */
    void setOnPull(LinearLayout content, Runnable r) {
        onPull = r;
        if (ind == null) {
            ind = Ui.icon(getContext(), Ui.I_REFRESH, 20, Ui.ACCENT);
            ind.setGravity(Gravity.CENTER);
            ind.setAlpha(0f);
            content.addView(ind, 0, new LinearLayout.LayoutParams(-1, 0));
        }
    }

    private void setPull(int h) {
        height = Math.max(0, h);
        LinearLayout.LayoutParams lp = (LinearLayout.LayoutParams) ind.getLayoutParams();
        lp.height = height;
        ind.setLayoutParams(lp);
        ind.setAlpha(Math.min(1f, height / (float) Ui.dp(getContext(), 60)));
        ind.setRotation(height * 3f);
    }

    @Override
    public boolean onInterceptTouchEvent(MotionEvent ev) {
        if (onPull != null) {
            if (ev.getActionMasked() == MotionEvent.ACTION_DOWN) { downX = ev.getX(); downY = ev.getY(); }
            else if (ev.getActionMasked() == MotionEvent.ACTION_MOVE && getScrollY() == 0) {
                float dy = ev.getY() - downY, dx = Math.abs(ev.getX() - downX);
                if (dy > slop && dy > dx) { pulling = true; startY = ev.getY(); return true; }
            }
        }
        return super.onInterceptTouchEvent(ev);
    }

    @Override
    public boolean onTouchEvent(MotionEvent ev) {
        if (onPull == null) return super.onTouchEvent(ev);
        switch (ev.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
                downY = ev.getY();
                startY = getScrollY() == 0 ? ev.getY() : -1;
                break;
            case MotionEvent.ACTION_MOVE:
                if (startY < 0 && getScrollY() == 0) startY = ev.getY();
                if (startY >= 0 && getScrollY() == 0 && (pulling || ev.getY() - startY > slop)) {
                    float dy = ev.getY() - startY;
                    if (dy > 0) {
                        pulling = true;
                        setPull((int) Math.min(dy * 0.5f, Ui.dp(getContext(), 90)));
                        return true;
                    }
                    if (pulling) { pulling = false; setPull(0); }
                }
                break;
            case MotionEvent.ACTION_UP:
            case MotionEvent.ACTION_CANCEL:
                startY = -1;
                if (pulling) {
                    pulling = false;
                    if (ev.getActionMasked() == MotionEvent.ACTION_UP && height >= Ui.dp(getContext(), 55)) onPull.run();
                    ValueAnimator va = ValueAnimator.ofInt(height, 0).setDuration(220);
                    va.addUpdateListener(new ValueAnimator.AnimatorUpdateListener() {
                        @Override public void onAnimationUpdate(ValueAnimator a) { setPull((Integer) a.getAnimatedValue()); }
                    });
                    va.start();
                    return true;
                }
                break;
        }
        return super.onTouchEvent(ev);
    }

    /** Pull to refresh for a page made with Ui.page (root is the scroll's content). */
    static void on(LinearLayout root, Runnable r) {
        if (root.getParent() instanceof PullScroll) ((PullScroll) root.getParent()).setOnPull(root, r);
    }
}
