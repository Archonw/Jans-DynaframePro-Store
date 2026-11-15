package de.archonw.remoteframetv;

import android.content.Context;
import android.net.nsd.NsdManager;
import android.net.nsd.NsdServiceInfo;
import android.net.wifi.WifiManager;
import android.os.Handler;
import android.os.Looper;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.InterfaceAddress;
import java.net.NetworkInterface;
import java.net.URL;
import java.security.SecureRandom;
import java.security.cert.X509Certificate;
import java.util.ArrayDeque;
import java.util.Collections;
import java.util.Enumeration;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

import javax.net.ssl.HostnameVerifier;
import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLSocketFactory;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;

/**
 * Finds DynaFrames on the local network in two ways at once:
 * 1. asks every address of the TV's own subnet for DynaFrame's /engine-proxy/sync/status
 *    (the same check the Home Assistant integration uses),
 * 2. listens to mDNS (Bonjour) announcements and checks the hosts it hears about,
 *    which also finds frames in a larger network than a /24.
 */
final class Discovery {

    interface Listener {
        void onFrame(Frame f);   // called on the main thread
        void onDone();           // called on the main thread
        void onHint(String host, String name, String id);   // another frame told us about this one
    }

    private static final String[] MDNS_TYPES = {"_device-info._tcp.", "_smb._tcp.", "_http._tcp.", "_workstation._tcp."};

    private final Context ctx;
    private final Listener listener;
    private final Handler main = new Handler(Looper.getMainLooper());
    private final Set<String> probed = Collections.synchronizedSet(new HashSet<String>());
    private final AtomicBoolean stopped = new AtomicBoolean(false);
    private ExecutorService pool;
    private NsdManager nsd;
    private final Set<NsdManager.DiscoveryListener> nsdListeners = new HashSet<>();
    private final ArrayDeque<NsdServiceInfo> resolveQueue = new ArrayDeque<>();
    private boolean resolving;
    private WifiManager.MulticastLock lock;

    Discovery(Context ctx, Listener listener) {
        this.ctx = ctx.getApplicationContext();
        this.listener = listener;
    }

    void start(java.util.Collection<String> extraHosts) {
        pool = Executors.newFixedThreadPool(64);
        startMdns();
        final Set<String> hosts = new LinkedHashSet<>(extraHosts);
        hosts.addAll(subnetHosts());
        for (final String h : hosts) submitProbe(h);
        // Give mDNS a little longer than the subnet sweep, then report "done".
        new Thread(new Runnable() {
            @Override public void run() {
                try { Thread.sleep(9000); } catch (InterruptedException ignored) { }
                main.post(new Runnable() {
                    @Override public void run() {
                        if (!stopped.get()) listener.onDone();
                        stop();
                    }
                });
            }
        }).start();
    }

    void stop() {
        if (stopped.getAndSet(true)) return;
        if (pool != null) pool.shutdownNow();
        if (nsd != null) {
            for (NsdManager.DiscoveryListener l : nsdListeners) {
                try { nsd.stopServiceDiscovery(l); } catch (Exception ignored) { }
            }
        }
        if (lock != null && lock.isHeld()) {
            try { lock.release(); } catch (Exception ignored) { }
        }
    }

    private void submitProbe(final String host) {
        if (stopped.get() || !probed.add(host)) return;
        try {
            pool.execute(new Runnable() {
                @Override public void run() {
                    final java.util.List<String[]> hints = new java.util.ArrayList<>();
                    final Frame f = probe(host, 900, 1500, hints);
                    for (final String[] h : hints) {
                        main.post(new Runnable() {
                            @Override public void run() { if (!stopped.get()) listener.onHint(h[0], h[1], h[2]); }
                        });
                        submitProbe(h[0]);
                    }
                    if (f != null && !stopped.get()) {
                        main.post(new Runnable() {
                            @Override public void run() { if (!stopped.get()) listener.onFrame(f); }
                        });
                    }
                }
            });
        } catch (Exception ignored) {
        }
    }

    // ---------------------------------------------------------------- subnet

    /** All addresses of the TV's private IPv4 networks (at most a /24 each, like the HA integration). */
    static Set<String> subnetHosts() {
        Set<String> out = new LinkedHashSet<>();
        try {
            Enumeration<NetworkInterface> ifs = NetworkInterface.getNetworkInterfaces();
            while (ifs != null && ifs.hasMoreElements()) {
                NetworkInterface ni = ifs.nextElement();
                if (!ni.isUp() || ni.isLoopback()) continue;
                for (InterfaceAddress ia : ni.getInterfaceAddresses()) {
                    InetAddress a = ia.getAddress();
                    if (!(a instanceof Inet4Address) || !a.isSiteLocalAddress()) continue;
                    int prefix = Math.max(ia.getNetworkPrefixLength(), 24);
                    byte[] b = a.getAddress();
                    int ip = ((b[0] & 255) << 24) | ((b[1] & 255) << 16) | ((b[2] & 255) << 8) | (b[3] & 255);
                    int mask = prefix == 0 ? 0 : -1 << (32 - prefix);
                    int net = ip & mask;
                    int count = 1 << (32 - prefix);
                    // Own neighbourhood first, so nearby frames show up quickly.
                    for (int i = 1; i < count - 1; i++) {
                        int x = net | i;
                        if (x == ip) continue;
                        out.add(((x >>> 24) & 255) + "." + ((x >>> 16) & 255) + "." + ((x >>> 8) & 255) + "." + (x & 255));
                    }
                }
            }
        } catch (Exception ignored) {
        }
        return out;
    }

    // ---------------------------------------------------------------- mDNS

    private void startMdns() {
        try {
            WifiManager wm = (WifiManager) ctx.getSystemService(Context.WIFI_SERVICE);
            if (wm != null) {
                lock = wm.createMulticastLock("remoteframetv");
                lock.setReferenceCounted(false);
                lock.acquire();
            }
        } catch (Exception ignored) {
        }
        try {
            nsd = (NsdManager) ctx.getSystemService(Context.NSD_SERVICE);
        } catch (Exception e) {
            nsd = null;
        }
        if (nsd == null) return;
        for (String type : MDNS_TYPES) {
            NsdManager.DiscoveryListener l = new NsdManager.DiscoveryListener() {
                @Override public void onStartDiscoveryFailed(String t, int c) { }
                @Override public void onStopDiscoveryFailed(String t, int c) { }
                @Override public void onDiscoveryStarted(String t) { }
                @Override public void onDiscoveryStopped(String t) { }
                @Override public void onServiceLost(NsdServiceInfo s) { }
                @Override public void onServiceFound(NsdServiceInfo s) { queueResolve(s); }
            };
            try {
                nsd.discoverServices(type, NsdManager.PROTOCOL_DNS_SD, l);
                nsdListeners.add(l);
            } catch (Exception ignored) {
            }
        }
    }

    private synchronized void queueResolve(NsdServiceInfo s) {
        if (stopped.get()) return;
        resolveQueue.add(s);
        nextResolve();
    }

    @SuppressWarnings("deprecation")
    private synchronized void nextResolve() {
        if (resolving || stopped.get()) return;
        NsdServiceInfo s = resolveQueue.poll();
        if (s == null) return;
        resolving = true;
        try {
            nsd.resolveService(s, new NsdManager.ResolveListener() {
                @Override public void onResolveFailed(NsdServiceInfo i, int c) { done(); }
                @Override public void onServiceResolved(NsdServiceInfo i) {
                    InetAddress a = i.getHost();
                    if (a instanceof Inet4Address) submitProbe(a.getHostAddress());
                    done();
                }
                private void done() {
                    synchronized (Discovery.this) { resolving = false; }
                    nextResolve();
                }
            });
        } catch (Exception e) {
            resolving = false;
        }
    }

    // ---------------------------------------------------------------- probe

    /**
     * Checks whether host is a DynaFrame. Returns null when it is not one,
     * a Frame with state OFFLINE when it does not answer at all.
     */
    static Frame probe(String host, int connectMs, int readMs) { return probe(host, connectMs, readMs, null); }

    static Frame probe(String host, int connectMs, int readMs, java.util.List<String[]> hints) {
        boolean answered = false;
        String[] schemes = {"http", "https"};
        for (String scheme : schemes) {
            HttpURLConnection c = null;
            try {
                c = open(scheme + "://" + host + "/engine-proxy/sync/status", connectMs, readMs);
                int code = c.getResponseCode();
                answered = true;
                if (code == 200) {
                    JSONObject o = new JSONObject(readAll(c.getInputStream()));
                    String id = o.optString("frameId", "");
                    if (id.isEmpty()) return null;
                    Frame f = new Frame(host, o.optString("frameName", host));
                    f.id = id;
                    if (hints != null) collectHints(o.opt("discoveredFrames"), hints);
                    f.state = Frame.OK;
                    return f;
                }
                if (code >= 300 && code < 400) {
                    String loc = String.valueOf(c.getHeaderField("Location"));
                    if (loc.contains("/dfr-login") || loc.contains("/Connect") || loc.contains("/Account/Login")
                            || loc.contains("/Login")) {
                        Frame f = new Frame(host, host);
                        f.state = Frame.LOGIN;
                        f.secure = true;
                        return f;
                    }
                    if (loc.startsWith("https://")) continue;   // frame forces https: try that
                    return null;
                }
                if (code == 401 || code == 403) {
                    // A login-protected DynaFrame answers like this for API calls without a session.
                    if (isDynaFramePage(scheme, host, connectMs, readMs)) {
                        Frame f = new Frame(host, host);
                        f.state = Frame.LOGIN;
                        f.secure = true;
                        return f;
                    }
                }
                return null;
            } catch (java.net.SocketTimeoutException e) {
                if (!answered) break;          // nobody there: do not wait for https as well
                return null;
            } catch (java.net.ConnectException e) {
                // port closed: maybe the frame only speaks https
            } catch (Exception e) {
                if (answered) return null;
                break;                         // no route, TLS trouble, ...: not a frame we can show
            } finally {
                if (c != null) c.disconnect();
            }
        }
        if (!answered) {
            Frame f = new Frame(host, host);
            f.state = Frame.OFFLINE;
            return f;
        }
        return null;
    }

    private static final java.util.regex.Pattern IPV4 =
            java.util.regex.Pattern.compile("\\b(\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3})\\b");

    /** sync/status lists the other frames a frame knows; take their IP, name and id, whatever the keys are called. */
    static void collectHints(Object list, java.util.List<String[]> out) {
        if (!(list instanceof org.json.JSONArray)) return;
        org.json.JSONArray a = (org.json.JSONArray) list;
        for (int i = 0; i < a.length(); i++) {
            JSONObject o = a.optJSONObject(i);
            if (o == null) continue;
            String ip = null, name = null, id = null;
            java.util.Iterator<String> keys = o.keys();
            while (keys.hasNext()) {
                String k = keys.next();
                Object v = o.opt(k);
                if (!(v instanceof String)) continue;
                String sv = (String) v;
                String lk = k.toLowerCase();
                if (ip == null) {
                    java.util.regex.Matcher m = IPV4.matcher(sv);
                    if (m.find() && !m.group(1).startsWith("127.")) ip = m.group(1);
                }
                if (name == null && (lk.equals("framename") || lk.equals("name") || lk.equals("displayname"))) name = sv;
                if (id == null && (lk.equals("frameid") || lk.equals("id"))) id = sv;
            }
            if (ip != null) out.add(new String[]{ip, name, id});
        }
    }

    private static boolean isDynaFramePage(String scheme, String host, int connectMs, int readMs) {
        HttpURLConnection c = null;
        try {
            c = open(scheme + "://" + host + "/RemoteFrame", connectMs, readMs);
            c.setInstanceFollowRedirects(true);
            int code = c.getResponseCode();
            InputStream in = code >= 400 ? c.getErrorStream() : c.getInputStream();
            String body = in == null ? "" : readAll(in);
            String l = body.toLowerCase();
            return l.contains("dynaframe");
        } catch (Exception e) {
            return false;
        } finally {
            if (c != null) c.disconnect();
        }
    }

    private static HttpURLConnection open(String url, int connectMs, int readMs) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(connectMs);
        c.setReadTimeout(readMs);
        c.setInstanceFollowRedirects(false);
        c.setRequestProperty("Accept", "application/json");
        c.setRequestProperty("User-Agent", "RemoteFrameTV");
        if (c instanceof HttpsURLConnection) {
            // Frames on the LAN use self-signed certificates; we only read the public status here.
            ((HttpsURLConnection) c).setSSLSocketFactory(trustAll());
            ((HttpsURLConnection) c).setHostnameVerifier(new HostnameVerifier() {
                @Override public boolean verify(String h, javax.net.ssl.SSLSession s) { return true; }
            });
        }
        return c;
    }

    private static SSLSocketFactory trustAllFactory;

    private static synchronized SSLSocketFactory trustAll() throws Exception {
        if (trustAllFactory == null) {
            SSLContext sc = SSLContext.getInstance("TLS");
            sc.init(null, new TrustManager[]{new X509TrustManager() {
                @Override public void checkClientTrusted(X509Certificate[] c, String a) { }
                @Override public void checkServerTrusted(X509Certificate[] c, String a) { }
                @Override public X509Certificate[] getAcceptedIssuers() { return new X509Certificate[0]; }
            }}, new SecureRandom());
            trustAllFactory = sc.getSocketFactory();
        }
        return trustAllFactory;
    }

    static String readAll(InputStream in) throws Exception {
        ByteArrayOutputStream bo = new ByteArrayOutputStream();
        byte[] buf = new byte[8192];
        int n;
        int total = 0;
        while ((n = in.read(buf)) > 0 && total < 512 * 1024) {
            bo.write(buf, 0, n);
            total += n;
        }
        in.close();
        return bo.toString("UTF-8");
    }

}
