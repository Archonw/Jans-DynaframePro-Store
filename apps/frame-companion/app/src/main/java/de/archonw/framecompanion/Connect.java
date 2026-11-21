package de.archonw.framecompanion;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.DialogInterface;
import android.text.InputType;
import android.text.method.LinkMovementMethod;
import android.view.View;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.io.IOException;

/** Login for frames with DynaFrame's own HTTPS login: API key (recommended) or user name + password. */
final class Connect {

    static void show(final Activity a, final Frame f, final Runnable onSaved) {
        final Store store = new Store(a);
        LinearLayout box = Ui.column(a);
        int p = Ui.dp(a, 20);
        box.setPadding(p, Ui.dp(a, 8), p, 0);

        TextView how = new TextView(a);
        how.setText(R.string.key_help);
        how.setTextSize(14);
        how.setMovementMethod(LinkMovementMethod.getInstance());
        box.addView(how);

        final EditText key = new EditText(a);
        key.setHint(R.string.key_hint);
        key.setSingleLine(true);
        key.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD);
        if (f.apiKey != null) key.setText(f.apiKey);
        box.addView(key);

        TextView or = new TextView(a);
        or.setText(R.string.or_password);
        or.setTextSize(14);
        or.setPadding(0, Ui.dp(a, 14), 0, 0);
        box.addView(or);
        final EditText user = new EditText(a);
        user.setHint(R.string.user_hint);
        user.setSingleLine(true);
        if (f.user != null) user.setText(f.user);
        box.addView(user);
        final EditText pw = new EditText(a);
        pw.setHint(R.string.password_hint);
        pw.setSingleLine(true);
        pw.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        if (f.password != null) pw.setText(f.password);
        box.addView(pw);

        final CheckBox https = new CheckBox(a);
        https.setText(R.string.use_https);
        https.setChecked(true);
        box.addView(https);

        final TextView result = new TextView(a);
        result.setTextSize(14);
        result.setPadding(0, Ui.dp(a, 8), 0, Ui.dp(a, 8));
        box.addView(result);

        final AlertDialog d = new AlertDialog.Builder(a)
                .setTitle(a.getString(R.string.connect_title, f.name))
                .setView(new android.widget.ScrollView(a) {{ addView(box); }})
                .setPositiveButton(R.string.check_and_save, null)
                .setNegativeButton(R.string.cancel, null)
                .create();
        d.setOnShowListener(new DialogInterface.OnShowListener() {
            @Override public void onShow(DialogInterface di) {
                final Button ok = d.getButton(AlertDialog.BUTTON_POSITIVE);
                ok.setOnClickListener(new View.OnClickListener() {
                    @Override public void onClick(View v) {
                        final Frame t = copy(f);
                        t.https = https.isChecked();
                        t.apiKey = key.getText().toString().trim();
                        if (t.apiKey.isEmpty()) t.apiKey = null;
                        t.user = user.getText().toString().trim();
                        t.password = pw.getText().toString();
                        if (t.user.isEmpty()) { t.user = null; t.password = null; }
                        if (!t.https) t.fingerprint = null;
                        ok.setEnabled(false);
                        result.setTextColor(Ui.MUTED);
                        result.setText(R.string.checking);
                        new Thread(new Runnable() {
                            @Override public void run() {
                                String err = null;
                                final Api api = new Api(t);
                                try {
                                    org.json.JSONObject info = api.with(new Api.Call<org.json.JSONObject>() {
                                        @Override public org.json.JSONObject run() throws IOException { return api.info(); }
                                    });
                                    String name = info.optString("frameName", "");
                                    if (!name.isEmpty()) t.name = name;
                                    if (info.has("frameId")) t.id = info.optString("frameId");
                                    api.pinIfNew();
                                } catch (Http.AuthException e) {
                                    err = a.getString(R.string.err_key_refused);
                                } catch (Http.CertChangedException e) {
                                    // Explicit re-check in this dialog: the user is looking at it, trust the new one.
                                    t.fingerprint = e.fingerprint;
                                    err = a.getString(R.string.cert_renewed_retry);
                                } catch (IOException e) {
                                    err = String.valueOf(e.getMessage());
                                }
                                final String fe = err;
                                a.runOnUiThread(new Runnable() {
                                    @Override public void run() {
                                        ok.setEnabled(true);
                                        if (fe != null) {
                                            result.setTextColor(Ui.BAD);
                                            result.setText(fe);
                                            if (t.fingerprint != null) f.fingerprint = t.fingerprint;
                                            return;
                                        }
                                        apply(t, f);
                                        f.state = Frame.OK;
                                        store.save(f, true);
                                        d.dismiss();
                                        if (onSaved != null) onSaved.run();
                                    }
                                });
                            }
                        }).start();
                    }
                });
            }
        });
        d.show();
    }

    /** The frame shows another certificate than the one remembered. */
    static void certChanged(final Activity a, final Frame f, final String newFp, final Runnable onTrusted) {
        new AlertDialog.Builder(a)
                .setTitle(R.string.cert_title)
                .setMessage(a.getString(R.string.cert_text, f.name, short_(f.fingerprint), short_(newFp)))
                .setPositiveButton(R.string.cert_trust, new DialogInterface.OnClickListener() {
                    @Override public void onClick(DialogInterface d, int w) {
                        f.fingerprint = newFp;
                        new Store(a).save(f, false);
                        if (onTrusted != null) onTrusted.run();
                    }
                })
                .setNegativeButton(R.string.cancel, null)
                .show();
    }

    static String short_(String fp) {
        if (fp == null || fp.length() < 16) return String.valueOf(fp);
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < 16; i += 2) { if (i > 0) sb.append(':'); sb.append(fp.substring(i, i + 2)); }
        return sb.toString().toUpperCase() + "…";
    }

    private static Frame copy(Frame f) {
        Frame t = new Frame(f.host, f.name);
        t.id = f.id; t.https = f.https; t.apiKey = f.apiKey; t.fingerprint = f.fingerprint;
        t.user = f.user; t.password = f.password; t.state = f.state;
        return t;
    }

    private static void apply(Frame from, Frame to) {
        to.name = from.name; to.id = from.id; to.https = from.https; to.apiKey = from.apiKey;
        to.fingerprint = from.fingerprint; to.user = from.user; to.password = from.password;
    }
}
