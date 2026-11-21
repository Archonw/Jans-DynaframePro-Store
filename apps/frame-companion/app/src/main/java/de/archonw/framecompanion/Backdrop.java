package de.archonw.framecompanion;

import android.app.Activity;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.ColorMatrix;
import android.graphics.ColorMatrixColorFilter;
import android.graphics.Paint;
import android.graphics.drawable.BitmapDrawable;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.view.View;
import android.widget.FrameLayout;
import android.widget.ImageView;

import java.io.File;
import java.io.FileOutputStream;
import java.lang.ref.WeakReference;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

/**
 * The picture that is on the frame right now, heavily blurred and darkened, behind every screen.
 * Kept as a tiny bitmap (and in the cache folder) so all screens can show it at once.
 */
final class Backdrop {

    private static Bitmap current;
    private static boolean loaded;
    private static final List<WeakReference<ImageView>> views = new ArrayList<>();

    private Backdrop() { }

    private static File file(Context c) { return new File(c.getCacheDir(), "backdrop.png"); }

    static Bitmap get(Context c) {
        if (!loaded) {
            loaded = true;
            try {
                File f = file(c);
                if (f.exists()) current = BitmapFactory.decodeFile(f.getPath());
                if (current != null && tooDark(current)) current = null;
            } catch (Throwable ignored) { }
        }
        return current;
    }

    /** New photo on the frame: blur it and show it behind all open screens. */
    static void set(final Context c, Bitmap src) {
        if (src == null || src.getWidth() < 2 || src.getHeight() < 2) return;
        final Bitmap b;
        try { b = blur(src); } catch (Throwable t) { return; }
        // a black screen (frame off, dark scene) would make every page plain black: keep the last picture / the warm glow
        if (tooDark(b)) return;
        current = b;
        loaded = true;
        for (Iterator<WeakReference<ImageView>> it = views.iterator(); it.hasNext(); ) {
            ImageView v = it.next().get();
            if (v == null) it.remove();
            else show(v, b);
        }
        final Context app = c.getApplicationContext();
        new Thread(new Runnable() {
            @Override public void run() {
                try (FileOutputStream out = new FileOutputStream(file(app))) {
                    b.compress(Bitmap.CompressFormat.PNG, 100, out);
                } catch (Throwable ignored) { }
            }
        }).start();
    }

    /** Puts the backdrop behind a screen's content. */
    static View wrap(Activity a, View content) {
        FrameLayout root = new FrameLayout(a);
        root.setBackgroundColor(Ui.BG);
        ImageView iv = new ImageView(a);
        iv.setScaleType(ImageView.ScaleType.CENTER_CROP);
        // warm glow when there is no photo yet
        GradientDrawable glow = new GradientDrawable(GradientDrawable.Orientation.TL_BR,
                new int[]{Color.rgb(74, 52, 26), Color.rgb(34, 26, 18), Color.rgb(14, 12, 10)});
        iv.setBackground(glow);
        if (Build.VERSION.SDK_INT >= 31) {
            float r = Ui.dp(a, 18);
            iv.setRenderEffect(android.graphics.RenderEffect.createBlurEffect(r, r, android.graphics.Shader.TileMode.CLAMP));
        }
        Bitmap b = get(a);
        if (b != null) show(iv, b);
        views.add(new WeakReference<>(iv));
        root.addView(iv, new FrameLayout.LayoutParams(-1, -1));
        View shade = new View(a);
        shade.setBackground(new GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM,
                new int[]{Color.argb(120, 10, 8, 6), Color.argb(150, 10, 8, 6), Color.argb(215, 10, 8, 6)}));
        root.addView(shade, new FrameLayout.LayoutParams(-1, -1));
        root.addView(content, new FrameLayout.LayoutParams(-1, -1));
        return root;
    }

    private static void show(ImageView v, Bitmap b) {
        BitmapDrawable d = new BitmapDrawable(v.getResources(), b);
        d.setFilterBitmap(true);
        v.setImageDrawable(d);
        v.setAlpha(0f);
        v.animate().alpha(1f).setDuration(600).start();
    }

    /** Average brightness below ~7 %: nothing to see behind the glass. */
    static boolean tooDark(Bitmap b) {
        int w = b.getWidth(), h = b.getHeight();
        int[] px = new int[w * h];
        b.getPixels(px, 0, w, 0, 0, w, h);
        long sum = 0;
        for (int c : px) sum += ((c >> 16) & 255) * 3 + ((c >> 8) & 255) * 6 + (c & 255);
        return sum / (10L * Math.max(1, px.length)) < 18;
    }

    /** Shrinks to ~40 px, boosts colour a little and box-blurs three times; scaled up it looks like frosted glass. */
    static Bitmap blur(Bitmap src) {
        int w = 40, h = Math.max(2, Math.round(src.getHeight() * 40f / src.getWidth()));
        if (h > 80) { h = 80; w = Math.max(2, Math.round(src.getWidth() * 80f / src.getHeight())); }
        Bitmap small = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888);
        Canvas c = new Canvas(small);
        Paint p = new Paint(Paint.FILTER_BITMAP_FLAG);
        ColorMatrix m = new ColorMatrix();
        m.setSaturation(1.3f);
        p.setColorFilter(new ColorMatrixColorFilter(m));
        c.drawBitmap(Bitmap.createScaledBitmap(src, w * 4, h * 4, true), null, new android.graphics.Rect(0, 0, w, h), p);
        int[] px = new int[w * h];
        small.getPixels(px, 0, w, 0, 0, w, h);
        for (int pass = 0; pass < 3; pass++) {
            px = boxH(px, w, h, 2);
            px = boxV(px, w, h, 2);
        }
        small.setPixels(px, 0, w, 0, 0, w, h);
        return small;
    }

    private static int[] boxH(int[] in, int w, int h, int r) {
        int[] out = new int[in.length];
        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                int rs = 0, gs = 0, bs = 0, n = 0;
                for (int k = -r; k <= r; k++) {
                    int xx = Math.min(w - 1, Math.max(0, x + k));
                    int c = in[y * w + xx];
                    rs += (c >> 16) & 255; gs += (c >> 8) & 255; bs += c & 255; n++;
                }
                out[y * w + x] = 0xff000000 | ((rs / n) << 16) | ((gs / n) << 8) | (bs / n);
            }
        }
        return out;
    }

    private static int[] boxV(int[] in, int w, int h, int r) {
        int[] out = new int[in.length];
        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                int rs = 0, gs = 0, bs = 0, n = 0;
                for (int k = -r; k <= r; k++) {
                    int yy = Math.min(h - 1, Math.max(0, y + k));
                    int c = in[yy * w + x];
                    rs += (c >> 16) & 255; gs += (c >> 8) & 255; bs += c & 255; n++;
                }
                out[y * w + x] = 0xff000000 | ((rs / n) << 16) | ((gs / n) << 8) | (bs / n);
            }
        }
        return out;
    }
}
