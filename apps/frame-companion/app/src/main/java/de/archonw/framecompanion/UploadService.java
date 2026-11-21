package de.archonw.framecompanion;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.ClipData;
import android.content.ContentResolver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.database.Cursor;
import android.net.Uri;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;
import android.provider.OpenableColumns;
import android.webkit.MimeTypeMap;

import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Sends photos and videos to a frame in the background with a progress notification,
 * so the user can leave the app (or the gallery) right away.
 */
public class UploadService extends Service {

    static final String CHANNEL = "uploads";
    static final int NOTE_ID = 7;
    static final String ACTION_CANCEL = "de.archonw.framecompanion.CANCEL";

    /** Listeners in the app (frame screen) get progress too. */
    interface Listener { void onUploadState(String host, String text, int percent, boolean finished); }
    static volatile Listener listener;
    static volatile boolean running;

    private final AtomicBoolean cancel = new AtomicBoolean(false);
    private Thread worker;

    static void start(Context c, Frame f, List<Uri> uris, boolean showNow) {
        Intent i = new Intent(c, UploadService.class);
        i.putExtra("host", f.host);
        i.putExtra("showNow", showNow);
        ClipData clip = null;
        ArrayList<String> files = new ArrayList<>();
        for (Uri u : uris) {
            // Own cache copies travel as plain paths: file:// URIs in an intent are refused by Android.
            if ("file".equals(u.getScheme())) { files.add(u.getPath()); continue; }
            if (clip == null) clip = ClipData.newRawUri("media", u);
            else clip.addItem(new ClipData.Item(u));
        }
        i.putStringArrayListExtra("files", files);
        if (clip != null) {
            i.setClipData(clip);
            i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        }
        if (Build.VERSION.SDK_INT >= 26) c.startForegroundService(i);
        else c.startService(i);
    }

    /**
     * Copies shared files the service may not be allowed to read (some apps grant access only to
     * the activity that received them) into the app's cache. Runs on a background thread.
     */
    static List<Uri> copyToCache(Context c, List<Uri> uris) {
        List<Uri> out = new ArrayList<>();
        java.io.File dir = new java.io.File(c.getCacheDir(), "share");
        dir.mkdirs();
        java.io.File[] old = dir.listFiles();
        if (old != null) for (java.io.File o : old) if (System.currentTimeMillis() - o.lastModified() > 86400000L) o.delete();
        for (Uri u : uris) {
            String name = null;
            Cursor cur = null;
            try {
                cur = c.getContentResolver().query(u, new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null);
                if (cur != null && cur.moveToFirst()) name = cur.getString(0);
            } catch (Exception ignored) {
            } finally {
                if (cur != null) cur.close();
            }
            if (name == null || name.isEmpty()) {
                String mime = c.getContentResolver().getType(u);
                String ext = mime == null ? null : MimeTypeMap.getSingleton().getExtensionFromMimeType(mime);
                name = "shared-" + System.currentTimeMillis() + (ext == null ? "" : "." + ext);
            }
            name = name.replaceAll("[/\\\\]", "_");
            java.io.File sub = new java.io.File(dir, String.valueOf(System.nanoTime()));
            sub.mkdirs();
            java.io.File f = new java.io.File(sub, name);
            try (InputStream in = c.getContentResolver().openInputStream(u);
                 java.io.OutputStream o = new java.io.FileOutputStream(f)) {
                if (in == null) continue;
                byte[] buf = new byte[64 * 1024];
                int n;
                while ((n = in.read(buf)) > 0) o.write(buf, 0, n);
                out.add(Uri.fromFile(f));
            } catch (Exception ignored) {
            }
        }
        return out;
    }

    @Override public IBinder onBind(Intent i) { return null; }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_CANCEL.equals(intent.getAction())) {
            cancel.set(true);
            return START_NOT_STICKY;
        }
        channel();
        Notification n = note(getString(R.string.upload_preparing), -1, false);
        if (Build.VERSION.SDK_INT >= 29) startForeground(NOTE_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
        else startForeground(NOTE_ID, n);
        if (intent == null || worker != null) {
            if (worker != null) post(getString(R.string.upload_busy), -1, false, intent != null ? intent.getStringExtra("host") : null);
            return START_NOT_STICKY;
        }
        final String host = intent.getStringExtra("host");
        final boolean showNow = intent.getBooleanExtra("showNow", true);
        final List<Uri> uris = new ArrayList<>();
        ClipData clip = intent.getClipData();
        if (clip != null) for (int k = 0; k < clip.getItemCount(); k++) uris.add(clip.getItemAt(k).getUri());
        ArrayList<String> files = intent.getStringArrayListExtra("files");
        if (files != null) for (String p : files) uris.add(Uri.fromFile(new java.io.File(p)));
        running = true;
        worker = new Thread(new Runnable() {
            @Override public void run() { work(host, uris, showNow); }
        }, "upload");
        worker.start();
        return START_NOT_STICKY;
    }

    private void work(String host, List<Uri> uris, boolean showNow) {
        PowerManager.WakeLock wl = null;
        try {
            PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
            wl = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "framecompanion:upload");
            wl.acquire(60 * 60 * 1000L);
        } catch (Exception ignored) {
        }
        Store store = new Store(this);
        Frame f = store.find(host);
        String text;
        boolean ok = false;
        try {
            if (f == null) throw new IOException(getString(R.string.err_unknown_frame));
            final Api api = new Api(f);
            String folderName = store.folder();
            if (folderName == null || folderName.isEmpty()) folderName = getString(R.string.default_folder);
            final String fn = folderName;
            final String folder = api.with(new Api.Call<String>() {
                @Override public String run() throws IOException { return api.ensureFolder(fn); }
            });
            if (api.pinIfNew()) store.save(f, false);
            final List<Api.Result> done = new ArrayList<>();
            int failed = 0;
            String lastError = null;
            for (int k = 0; k < uris.size(); k++) {
                if (cancel.get()) break;
                final Uri u = uris.get(k);
                final Meta m;
                try {
                    m = meta(u);
                } catch (IOException ex) {
                    failed++;
                    lastError = String.valueOf(ex.getMessage());
                    continue;
                }
                final int index = k;
                final int count = uris.size();
                final long[] lastPost = {0};
                try {
                    Api.Result r = api.with(new Api.Call<Api.Result>() {
                        @Override public Api.Result run() throws IOException {
                            return api.upload(folder, m.name, m.size, m.modified, false, new Api.Source() {
                                @Override public InputStream open(long offset) throws IOException {
                                    InputStream in = getContentResolver().openInputStream(u);
                                    if (in == null) throw new IOException("cannot read " + m.name);
                                    long skip = offset;
                                    while (skip > 0) {
                                        long s = in.skip(skip);
                                        if (s <= 0) { if (in.read() < 0) break; s = 1; }
                                        skip -= s;
                                    }
                                    return in;
                                }
                            }, new Http.Progress() {
                                @Override public void onProgress(long d, long t) {
                                    long now = System.currentTimeMillis();
                                    if (now - lastPost[0] < 400) return;
                                    lastPost[0] = now;
                                    int pct = (int) ((index * 100L + (t > 0 ? d * 100L / t : 0)) / count);
                                    post(getString(R.string.upload_progress, index + 1, count, m.name), pct, false, host);
                                }
                            }, cancel);
                        }
                    });
                    if (r.mediaType == null && m.mime != null) r.mediaType = m.mime.startsWith("video") ? "video" : "image";
                    done.add(r);
                } catch (Http.AuthException | Http.CertChangedException ex) {
                    throw ex;
                } catch (IOException ex) {
                    if (cancel.get()) break;
                    failed++;
                    lastError = m.name + ": " + ex.getMessage();
                }
            }
            if (cancel.get()) {
                text = getString(R.string.upload_cancelled, done.size());
            } else if (done.isEmpty()) {
                throw new IOException(lastError == null ? "nothing sent" : lastError);
            } else {
                String shown = "";
                if (showNow) {
                    try {
                        api.with(new Api.Call<Void>() {
                            @Override public Void run() throws IOException { api.playNow(done); return null; }
                        });
                        shown = " " + getString(R.string.upload_shown);
                    } catch (Http.AuthException ex) {
                        throw ex;
                    } catch (IOException ex) {
                        android.util.Log.w("FrameCompanion", "play-now failed, playing folder instead: " + ex.getMessage());
                        try {
                            api.playFolderNow(folder);
                            shown = " " + getString(R.string.upload_folder_shown);
                        } catch (IOException ex2) {
                            shown = " " + getString(R.string.upload_not_shown, ex2.getMessage());
                        }
                    }
                }
                text = getString(R.string.upload_done, done.size(), f.name, folder.substring(folder.lastIndexOf('/') + 1)) + shown;
                if (failed > 0) text += " " + getString(R.string.upload_failed_some, failed, lastError);
                ok = true;
            }
        } catch (Http.AuthException ex) {
            text = getString(R.string.err_login, f != null ? f.name : host);
        } catch (Http.CertChangedException ex) {
            text = getString(R.string.err_cert, f != null ? f.name : host);
        } catch (IOException ex) {
            text = getString(R.string.upload_error, f != null ? f.name : host, String.valueOf(ex.getMessage()));
        } finally {
            if (wl != null && wl.isHeld()) wl.release();
        }
        running = false;
        finish(text, ok, host);
    }

    private void finish(String text, boolean ok, String host) {
        stopForeground(true);
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        try { nm.notify(NOTE_ID + 1, note(text, ok ? 100 : -1, true)); } catch (Exception ignored) { }
        Listener l = listener;
        if (l != null) l.onUploadState(host, text, 100, true);
        worker = null;
        stopSelf();
    }

    private void post(String text, int pct, boolean done, String host) {
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        try { nm.notify(NOTE_ID, note(text, pct, done)); } catch (Exception ignored) { }
        Listener l = listener;
        if (l != null) l.onUploadState(host, text, pct, done);
    }

    private void channel() {
        if (Build.VERSION.SDK_INT < 26) return;
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        NotificationChannel ch = new NotificationChannel(CHANNEL, getString(R.string.channel_uploads), NotificationManager.IMPORTANCE_LOW);
        nm.createNotificationChannel(ch);
    }

    @SuppressWarnings("deprecation")
    private Notification note(String text, int pct, boolean finished) {
        Notification.Builder b = Build.VERSION.SDK_INT >= 26 ? new Notification.Builder(this, CHANNEL) : new Notification.Builder(this);
        b.setSmallIcon(R.drawable.ic_stat)
                .setContentTitle(getString(finished ? R.string.upload_title_done : R.string.upload_title))
                .setContentText(text)
                .setStyle(new Notification.BigTextStyle().bigText(text))
                .setOnlyAlertOnce(true)
                .setOngoing(!finished)
                .setAutoCancel(finished);
        Intent open = new Intent(this, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        int pf = Build.VERSION.SDK_INT >= 23 ? PendingIntent.FLAG_IMMUTABLE : 0;
        b.setContentIntent(PendingIntent.getActivity(this, 0, open, pf));
        if (!finished) {
            if (pct >= 0) b.setProgress(100, pct, false);
            else b.setProgress(0, 0, true);
            Intent c = new Intent(this, UploadService.class).setAction(ACTION_CANCEL);
            b.addAction(new Notification.Action.Builder(null, getString(R.string.cancel),
                    PendingIntent.getService(this, 1, c, pf)).build());
        }
        return b.build();
    }

    static final class Meta {
        String name;
        long size = -1;
        long modified;
        String mime;
    }

    private Meta meta(Uri u) throws IOException {
        Meta m = new Meta();
        ContentResolver cr = getContentResolver();
        m.mime = cr.getType(u);
        Cursor c = null;
        try {
            c = cr.query(u, null, null, null, null);
            if (c != null && c.moveToFirst()) {
                int ni = c.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                int si = c.getColumnIndex(OpenableColumns.SIZE);
                if (ni >= 0) m.name = c.getString(ni);
                if (si >= 0 && !c.isNull(si)) m.size = c.getLong(si);
                int mi = c.getColumnIndex("date_modified");
                if (mi >= 0 && !c.isNull(mi)) m.modified = c.getLong(mi) * 1000L;
                int ti = c.getColumnIndex("datetaken");
                if (ti >= 0 && !c.isNull(ti) && c.getLong(ti) > 0) m.modified = c.getLong(ti);
            }
        } catch (Exception ignored) {
        } finally {
            if (c != null) c.close();
        }
        if (m.name == null || m.name.isEmpty()) {
            String last = u.getLastPathSegment();
            m.name = last == null ? "photo" : last.replaceAll("[^A-Za-z0-9._-]", "_");
        }
        if (m.name.indexOf('.') < 0 && m.mime != null) {
            String ext = MimeTypeMap.getSingleton().getExtensionFromMimeType(m.mime);
            if (ext != null) m.name += "." + ext;
        }
        if (m.size < 0) {
            // Provider does not say: count the bytes once.
            InputStream in = cr.openInputStream(u);
            if (in == null) throw new IOException("cannot read " + m.name);
            long n = 0;
            byte[] buf = new byte[64 * 1024];
            int r;
            while ((r = in.read(buf)) > 0) n += r;
            in.close();
            m.size = n;
        }
        return m;
    }
}
