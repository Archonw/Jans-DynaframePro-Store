package de.archonw.framecompanion;

import android.app.Activity;
import android.content.ClipData;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Parcelable;
import android.widget.CheckBox;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import java.util.ArrayList;
import java.util.List;

/** Target of Android's "Share" menu: pick a frame with one tap, the upload runs in the background. */
public class ShareActivity extends Activity {

    private final List<Uri> uris = new ArrayList<>();
    private FramePicker picker;
    private Store store;

    @Override
    @SuppressWarnings("deprecation")
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        store = new Store(this);
        Intent in = getIntent();
        if (Intent.ACTION_SEND_MULTIPLE.equals(in.getAction())) {
            ArrayList<Parcelable> list = in.getParcelableArrayListExtra(Intent.EXTRA_STREAM);
            if (list != null) for (Parcelable p : list) if (p instanceof Uri) uris.add((Uri) p);
        } else {
            Parcelable p = in.getParcelableExtra(Intent.EXTRA_STREAM);
            if (p instanceof Uri) uris.add((Uri) p);
        }
        if (uris.isEmpty()) {
            ClipData clip = in.getClipData();
            if (clip != null) for (int k = 0; k < clip.getItemCount(); k++) if (clip.getItemAt(k).getUri() != null) uris.add(clip.getItemAt(k).getUri());
        }
        if (uris.isEmpty()) {
            Toast.makeText(this, R.string.nothing_to_send, Toast.LENGTH_LONG).show();
            finish();
            return;
        }

        LinearLayout root = Ui.page(this);
        root.addView(Ui.text(this, getResources().getQuantityString(R.plurals.send_to, uris.size(), uris.size()), 22, Ui.ACCENT, true));
        TextView sub = Ui.text(this, getString(R.string.tap_frame), 14, Ui.MUTED, false);
        sub.setPadding(0, Ui.dp(this, 4), 0, Ui.dp(this, 12));
        root.addView(sub);

        picker = new FramePicker(this, store, new FramePicker.OnPick() {
            @Override public void pick(Frame f) { send(f); }
        }, null);
        root.addView(picker.view);

        final CheckBox showNow = new CheckBox(this);
        showNow.setText(R.string.show_now);
        showNow.setTextColor(Ui.TEXT);
        showNow.setChecked(store.showNow());
        showNow.setOnCheckedChangeListener(new android.widget.CompoundButton.OnCheckedChangeListener() {
            @Override public void onCheckedChanged(android.widget.CompoundButton b, boolean on) { store.setShowNow(on); }
        });
        root.addView(showNow);
        String folder = store.folder();
        root.addView(Ui.text(this, getString(R.string.folder_is, folder == null ? getString(R.string.default_folder) : folder), 13, Ui.MUTED, false));

        picker.scan();
    }

    @Override
    protected void onDestroy() {
        if (picker != null) picker.stop();
        super.onDestroy();
    }

    private void send(final Frame f) {
        if (f.needsKey()) {
            Connect.show(this, f, new Runnable() {
                @Override public void run() { send(f); }
            });
            return;
        }
        if (UploadService.running) {
            Toast.makeText(this, R.string.upload_busy, Toast.LENGTH_LONG).show();
            return;
        }
        store.save(f, true);
        Toast.makeText(this, getResources().getQuantityString(R.plurals.sending_to, uris.size(), uris.size(), f.name), Toast.LENGTH_SHORT).show();
        try {
            UploadService.start(this, f, uris, store.showNow());
            finish();
        } catch (SecurityException e) {
            // The sharing app gave read access only to this screen: copy the files first.
            final android.content.Context app = getApplicationContext();
            final boolean now = store.showNow();
            new Thread(new Runnable() {
                @Override public void run() {
                    final List<Uri> copies = UploadService.copyToCache(app, uris);
                    runOnUiThread(new Runnable() {
                        @Override public void run() {
                            if (copies.isEmpty()) Toast.makeText(app, R.string.nothing_to_send, Toast.LENGTH_LONG).show();
                            else UploadService.start(app, f, copies, now);
                            finish();
                        }
                    });
                }
            }).start();
        }
    }
}
