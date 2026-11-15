package de.archonw.remoteframetv;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.DialogInterface;
import android.content.Intent;
import android.os.Bundle;
import android.text.InputType;
import android.text.SpannableStringBuilder;
import android.text.Spanned;
import android.text.style.ForegroundColorSpan;
import android.text.style.RelativeSizeSpan;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.List;

/** Frame list: finds DynaFrames on the network and lets the remote pick one. */
public class MainActivity extends Activity implements Discovery.Listener {

    private Store store;
    private final List<Frame> frames = new ArrayList<>();
    private LinearLayout list;
    private TextView status;
    private TextView autostartBtn;
    private Discovery discovery;
    private boolean scanning;

    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        store = new Store(this);
        buildUi();
        frames.addAll(store.saved());
        render();

        String last = store.last();
        if (saved == null && store.autostart() && last != null
                && !getIntent().getBooleanExtra("noAutostart", false)) {
            for (Frame f : frames) {
                if (f.host.equals(last)) {
                    open(f);
                    break;
                }
            }
        }
        scan();
    }

    @Override
    protected void onDestroy() {
        if (discovery != null) discovery.stop();
        super.onDestroy();
    }

    // ------------------------------------------------------------------ UI

    private void buildUi() {
        int pad = Ui.dp(this, 40);
        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(Ui.BG);
        scroll.setFillViewport(true);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(pad, Ui.dp(this, 28), pad, pad);
        scroll.addView(root);

        root.addView(Ui.text(this, getString(R.string.app_name), 30, Ui.FOCUS, true));
        TextView sub = Ui.text(this, getString(R.string.subtitle), 17, Ui.TEXT, false);
        sub.setPadding(0, Ui.dp(this, 4), 0, Ui.dp(this, 4));
        root.addView(sub);
        status = Ui.text(this, "", 15, Ui.MUTED, false);
        status.setPadding(0, 0, 0, Ui.dp(this, 16));
        root.addView(status);

        list = new LinearLayout(this);
        list.setOrientation(LinearLayout.VERTICAL);
        root.addView(list, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        LinearLayout actions = new LinearLayout(this);
        actions.setOrientation(LinearLayout.HORIZONTAL);
        actions.setPadding(0, Ui.dp(this, 20), 0, 0);
        root.addView(actions);

        TextView rescan = Ui.button(this, getString(R.string.rescan), 16);
        rescan.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { scan(); }
        });
        actions.addView(rescan, spaced());

        TextView manual = Ui.button(this, getString(R.string.add_manual), 16);
        manual.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { askAddress(); }
        });
        actions.addView(manual, spaced());

        autostartBtn = Ui.button(this, "", 16);
        autostartBtn.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) {
                store.setAutostart(!store.autostart());
                updateAutostart();
            }
        });
        actions.addView(autostartBtn, spaced());
        updateAutostart();

        setContentView(scroll);
    }

    private LinearLayout.LayoutParams spaced() {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, 0, Ui.dp(this, 14), 0);
        return lp;
    }

    private void updateAutostart() {
        autostartBtn.setText(getString(R.string.autostart,
                getString(store.autostart() ? R.string.on : R.string.off)));
    }

    private void render() {
        View focused = getCurrentFocus();
        String focusedHost = focused != null && focused.getTag() instanceof String ? (String) focused.getTag() : null;
        list.removeAllViews();
        View refocus = null;
        for (final Frame f : frames) {
            SpannableStringBuilder sb = new SpannableStringBuilder(f.name);
            int start = sb.length();
            String detail = "   " + f.host;
            if (f.state == Frame.LOGIN) detail += " · " + getString(R.string.login_needed);
            else if (f.state == Frame.OFFLINE) detail += " · " + getString(R.string.not_reachable);
            else if (f.state == Frame.UNKNOWN && f.saved) detail += " · " + getString(R.string.saved);
            sb.append(detail);
            sb.setSpan(new ForegroundColorSpan(Ui.MUTED), start, sb.length(), Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
            sb.setSpan(new RelativeSizeSpan(0.75f), start, sb.length(), Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);

            TextView b = Ui.button(this, sb, 22);
            b.setTag(f.host);
            b.setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View v) { open(f); }
            });
            b.setOnLongClickListener(new View.OnLongClickListener() {
                @Override public boolean onLongClick(View v) { frameMenu(f); return true; }
            });
            b.setOnKeyListener(new View.OnKeyListener() {
                @Override public boolean onKey(View v, int code, KeyEvent e) {
                    if (code == KeyEvent.KEYCODE_MENU && e.getAction() == KeyEvent.ACTION_UP) {
                        frameMenu(f);
                        return true;
                    }
                    return false;
                }
            });
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            lp.setMargins(0, 0, 0, Ui.dp(this, 12));
            list.addView(b, lp);
            if (f.host.equals(focusedHost)) refocus = b;
        }
        if (refocus != null) refocus.requestFocus();
        else if (focused == null && list.getChildCount() > 0) list.getChildAt(0).requestFocus();
        else if (focused == null) autostartBtn.post(new Runnable() {
            @Override public void run() { if (getCurrentFocus() == null && list.getChildCount() == 0) autostartBtn.requestFocus(); }
        });
    }

    // ------------------------------------------------------------------ discovery

    private void scan() {
        if (scanning) return;
        scanning = true;
        status.setText(R.string.searching);
        for (Frame f : frames) if (f.state != Frame.OK && f.state != Frame.LOGIN) f.state = Frame.UNKNOWN;
        List<String> extra = new ArrayList<>();
        for (Frame f : frames) extra.add(f.host);
        discovery = new Discovery(this, this);
        discovery.start(extra);
    }

    @Override
    public void onFrame(Frame found) {
        Frame known = null;
        for (Frame f : frames) {
            if (f.host.equals(found.host) || (found.id != null && found.id.equals(f.id))) {
                known = f;
                break;
            }
        }
        if (found.state == Frame.OFFLINE) {
            if (known != null) {
                known.state = Frame.OFFLINE;
                render();
            }
            return;
        }
        String[] hint = hints.get(found.host);
        if (hint != null) {
            if (hint[0] != null && !hint[0].isEmpty() && found.name.equals(found.host)) found.name = hint[0];
            if (found.id == null) found.id = hint[1];
        }
        if (known == null) {
            frames.add(found);
        } else {
            if (found.id != null) known.id = found.id;
            if (!found.name.equals(found.host)) known.name = found.name;
            known.state = found.state;
            known.secure = found.secure;
            if (known.saved) store.refresh(known);
        }
        render();
        status.setText(getString(R.string.found_n, countOnline()));
    }

    private int countOnline() {
        int n = 0;
        for (Frame f : frames) if (f.state == Frame.OK || f.state == Frame.LOGIN) n++;
        return n;
    }

    private final java.util.Map<String, String[]> hints = new java.util.HashMap<>();

    @Override
    public void onHint(String host, String name, String id) {
        hints.put(host, new String[]{name, id});
        for (Frame f : frames) {
            if (f.host.equals(host)) {
                if (name != null && !name.isEmpty() && f.name.equals(f.host)) f.name = name;
                if (f.id == null) f.id = id;
                render();
            }
        }
    }

    @Override
    public void onDone() {
        scanning = false;
        int n = countOnline();
        status.setText(n == 0 ? getString(R.string.found_none) : getString(R.string.found_n, n));
        for (Frame f : frames) if (f.state == Frame.UNKNOWN) f.state = Frame.OFFLINE;
        render();
    }

    // ------------------------------------------------------------------ actions

    private void open(Frame f) {
        String last = store.last();
        store.remember(f);
        f.saved = true;
        Intent i = new Intent(this, ViewerActivity.class);
        i.putExtra("url", f.viewerUrl());
        i.putExtra("host", f.host);
        i.putExtra("name", f.name);
        startActivity(i);
        if (last == null || !last.equals(f.host)) {
            frames.remove(f);
            frames.add(0, f);
            render();
        }
    }

    private void frameMenu(final Frame f) {
        new AlertDialog.Builder(this)
                .setTitle(f.name)
                .setItems(new CharSequence[]{getString(R.string.open), getString(R.string.remove)},
                        new DialogInterface.OnClickListener() {
                            @Override public void onClick(DialogInterface d, int which) {
                                if (which == 0) {
                                    open(f);
                                } else {
                                    store.forget(f);
                                    frames.remove(f);
                                    render();
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
        new AlertDialog.Builder(this)
                .setTitle(R.string.manual_title)
                .setView(in)
                .setPositiveButton(R.string.ok, new DialogInterface.OnClickListener() {
                    @Override public void onClick(DialogInterface d, int w) {
                        String host = in.getText().toString().trim()
                                .replaceAll("/+$", "").replaceAll("/RemoteFrame$", "");
                        if (host.isEmpty()) return;
                        Frame f = null;
                        for (Frame o : frames) if (o.host.equals(host)) f = o;
                        if (f == null) {
                            f = new Frame(host, host);
                            frames.add(0, f);
                        }
                        open(f);
                    }
                })
                .setNegativeButton(R.string.cancel, null)
                .show();
    }
}
