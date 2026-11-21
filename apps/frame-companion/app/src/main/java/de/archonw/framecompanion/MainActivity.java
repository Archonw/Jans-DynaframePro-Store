package de.archonw.framecompanion;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.DialogInterface;
import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.text.InputType;
import android.view.View;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Start screen: the frames in the home network. */
public class MainActivity extends Activity {

    private Store store;
    private FramePicker picker;

    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        store = new Store(this);
        LinearLayout root = Ui.page(this);
        // big title, search and add as round glass buttons
        LinearLayout head = Ui.row(this);
        head.setPadding(0, Ui.dp(this, 8), 0, Ui.dp(this, 18));
        head.addView(Ui.title(this, getString(R.string.frames_title), 34), new LinearLayout.LayoutParams(0, -2, 1f));
        TextView rescan = Ui.glassCircle(this, Ui.I_REFRESH, 17);
        rescan.setContentDescription(getString(R.string.rescan));
        rescan.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { picker.scan(); }
        });
        LinearLayout.LayoutParams cl = new LinearLayout.LayoutParams(Ui.dp(this, 42), Ui.dp(this, 42));
        cl.setMargins(Ui.dp(this, 10), 0, 0, 0);
        head.addView(rescan, cl);
        TextView manual = Ui.glassCircle(this, Ui.I_PLUS, 20);
        manual.setContentDescription(getString(R.string.add_manual));
        manual.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { askAddress(); }
        });
        head.addView(manual, new LinearLayout.LayoutParams(cl));
        root.addView(head);

        picker = new FramePicker(this, store, new FramePicker.OnPick() {
            @Override public void pick(Frame f) { open(f); }
        }, new FramePicker.OnPick() {
            @Override public void pick(Frame f) { menu(f); }
        });
        picker.onRemote = new FramePicker.OnRemote() {
            @Override public void pick(Frame f, String path, String title) { openRemote(f, path, title); }
        };
        root.addView(picker.view);
        PullScroll.on(root, new Runnable() { @Override public void run() { picker.scan(); } });

        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission("android.permission.POST_NOTIFICATIONS") != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"}, 1);
        }
        picker.scan();
    }

    @Override
    protected void onResume() {
        super.onResume();
        picker.reload();
    }

    @Override
    protected void onDestroy() {
        picker.stop();
        super.onDestroy();
    }

    private void open(final Frame f) {
        if (f.needsKey()) {
            Connect.show(this, f, new Runnable() {
                @Override public void run() { open(f); }
            });
            return;
        }
        store.save(f, true);
        startActivity(new Intent(this, FrameActivity.class).putExtra("host", f.host));
    }

    /** Show one of the frame's remote frames on the phone. */
    private void openRemote(final Frame f, final String path, final String title) {
        if (f.needsKey()) {
            Connect.show(this, f, new Runnable() {
                @Override public void run() { openRemote(f, path, title); }
            });
            return;
        }
        store.save(f, true);
        WebActivity.open(this, f, path, title);
    }

    private void menu(final Frame f) {
        new AlertDialog.Builder(this)
                .setTitle(f.name)
                .setItems(new CharSequence[]{getString(R.string.open), getString(R.string.login_settings), getString(R.string.remove)},
                        new DialogInterface.OnClickListener() {
                            @Override public void onClick(DialogInterface d, int which) {
                                if (which == 0) open(f);
                                else if (which == 1) Connect.show(MainActivity.this, f, new Runnable() {
                                    @Override public void run() { picker.reload(); }
                                });
                                else {
                                    store.forget(f);
                                    picker.frames.remove(f);
                                    picker.reload();
                                }
                            }
                        })
                .show();
    }

    private void askAddress() {
        final EditText in = new EditText(this);
        in.setHint(R.string.manual_hint);
        in.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        in.setSingleLine(true);
        LinearLayout box = Ui.column(this);
        int p = Ui.dp(this, 20);
        box.setPadding(p, 0, p, 0);
        box.addView(in);
        new AlertDialog.Builder(this)
                .setTitle(R.string.manual_title)
                .setView(box)
                .setPositiveButton(R.string.ok, new DialogInterface.OnClickListener() {
                    @Override public void onClick(DialogInterface d, int w) {
                        String host = in.getText().toString().trim()
                                .replaceAll("^https?://", "").replaceAll("/.*$", "");
                        if (host.isEmpty()) return;
                        Frame f = store.find(host);
                        if (f == null) f = new Frame(host, host);
                        store.save(f, true);
                        picker.reload();
                        picker.scan();
                    }
                })
                .setNegativeButton(R.string.cancel, null)
                .show();
    }
}
