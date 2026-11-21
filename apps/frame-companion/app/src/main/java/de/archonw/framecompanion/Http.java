package de.archonw.framecompanion;

import org.json.JSONArray;
import org.json.JSONObject;
import org.json.JSONTokener;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.security.cert.CertificateException;
import java.security.cert.X509Certificate;

import javax.net.ssl.HostnameVerifier;
import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLSession;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;

/**
 * Talks to one frame. DynaFrame signs its HTTPS certificate itself, so instead of a CA check
 * the app remembers the certificate's SHA-256 the first time ("trust on first use") and
 * refuses a different one later until the user confirms it.
 */
final class Http {

    static final class AuthException extends IOException {
        AuthException(String m) { super(m); }
    }

    static final class CertChangedException extends IOException {
        final String fingerprint;
        CertChangedException(String fp) { super("certificate changed"); fingerprint = fp; }
    }

    static final class HttpException extends IOException {
        final int code;
        String body = "";
        HttpException(int code, String m) { super("HTTP " + code + (m == null || m.isEmpty() ? "" : ": " + m)); this.code = code; }
        /** The frame's own error text from a JSON answer, if any. */
        String message() {
            try {
                Object o = new JSONTokener(body).nextValue();
                if (o instanceof JSONObject) {
                    JSONObject j = (JSONObject) o;
                    for (String k : new String[]{"message", "error", "Message", "Error", "title"}) {
                        String v = j.isNull(k) ? "" : j.optString(k, "");
                        if (!v.isEmpty()) return v;
                    }
                }
            } catch (Exception ignored) {
            }
            return body.length() > 200 ? body.substring(0, 200) : body;
        }
        JSONObject json() {
            try { Object o = new JSONTokener(body).nextValue(); return o instanceof JSONObject ? (JSONObject) o : new JSONObject(); }
            catch (Exception e) { return new JSONObject(); }
        }
    }

    interface Progress { void onProgress(long done, long total); }

    private final Frame f;
    /** Antiforgery token of the web UI (WebDAV routes want it as a header). */
    volatile String antiForgery;
    /** Certificate the frame showed on the last https call (sha256 hex). */
    volatile String seenFingerprint;

    Http(Frame f) { this.f = f; }

    String base() { return (f.https ? "https://" : "http://") + f.host; }

    HttpURLConnection open(String path, String method, int readMs) throws IOException {
        HttpURLConnection c = (HttpURLConnection) new URL(base() + path).openConnection();
        c.setConnectTimeout(5000);
        c.setReadTimeout(readMs);
        c.setInstanceFollowRedirects(false);
        c.setRequestMethod(method);
        c.setRequestProperty("Accept", "application/json");
        c.setRequestProperty("User-Agent", "FrameCompanion/" + BuildConfig.VERSION_NAME);
        // Send the key only over https: DynaFrame refuses any Authorization header on plain http.
        if (f.https && f.apiKey != null && !f.apiKey.isEmpty()) c.setRequestProperty("Authorization", "Bearer " + f.apiKey);
        // Same-origin headers like the frame's own web page sends them (its write routes check this).
        c.setRequestProperty("Origin", base());
        c.setRequestProperty("Referer", base() + "/Upload");
        c.setRequestProperty("X-Requested-With", "XMLHttpRequest");
        if (antiForgery != null) c.setRequestProperty("RequestVerificationToken", antiForgery);
        if (c instanceof HttpsURLConnection) pin((HttpsURLConnection) c);
        return c;
    }

    static {
        // Keeps a DynaFrame login cookie (user name + password sign-in) for the app's lifetime.
        if (java.net.CookieHandler.getDefault() == null) {
            java.net.CookieHandler.setDefault(new java.net.CookieManager(null, java.net.CookiePolicy.ACCEPT_ORIGINAL_SERVER));
        }
    }

    /**
     * Signs in like the browser does (DynaFrame's login form) and keeps the session cookie.
     * A successful admin sign-in also lets the frame trust this phone's address for a while.
     */
    void login(String user, String password) throws IOException {
        HttpURLConnection c = null;
        String page;
        try {
            c = open("/WebUiAccount/Login", "GET", 15000);
            c.setRequestProperty("Accept", "text/html");
            int code = c.getResponseCode();
            InputStream in = code >= 400 ? c.getErrorStream() : c.getInputStream();
            page = in == null ? "" : readAll(in);
        } catch (javax.net.ssl.SSLHandshakeException e) {
            throw certOr(e);
        } finally {
            if (c != null) c.disconnect();
        }
        StringBuilder form = new StringBuilder();
        java.util.regex.Matcher m = java.util.regex.Pattern.compile("<input[^>]*type=\"hidden\"[^>]*>", java.util.regex.Pattern.CASE_INSENSITIVE).matcher(page);
        while (m.find()) {
            String tag = m.group();
            String n = attr(tag, "name"), v = attr(tag, "value");
            if (n == null) continue;
            form.append(java.net.URLEncoder.encode(n, "UTF-8")).append('=').append(java.net.URLEncoder.encode(v == null ? "" : v, "UTF-8")).append('&');
        }
        form.append("userName=").append(java.net.URLEncoder.encode(user, "UTF-8"))
            .append("&password=").append(java.net.URLEncoder.encode(password, "UTF-8"));
        String action = "/WebUiAccount/Login";
        java.util.regex.Matcher fa = java.util.regex.Pattern.compile("<form[^>]*action=\"([^\"]*Login[^\"]*)\"", java.util.regex.Pattern.CASE_INSENSITIVE).matcher(page);
        if (fa.find()) action = fa.group(1).replace("&amp;", "&");
        if (!action.startsWith("/")) action = "/WebUiAccount/Login";
        try {
            c = open(action, "POST", 15000);
            c.setRequestProperty("Accept", "text/html");
            byte[] b = form.toString().getBytes("UTF-8");
            c.setDoOutput(true);
            c.setRequestProperty("Content-Type", "application/x-www-form-urlencoded");
            c.setFixedLengthStreamingMode(b.length);
            OutputStream o = c.getOutputStream();
            o.write(b);
            o.close();
            int code = c.getResponseCode();
            String loc = String.valueOf(c.getHeaderField("Location"));
            if (code >= 300 && code < 400 && !loc.contains("Login")) return;   // signed in, sent on
            throw new AuthException("login refused (HTTP " + code + ")");
        } catch (javax.net.ssl.SSLHandshakeException e) {
            throw certOr(e);
        } finally {
            if (c != null) c.disconnect();
        }
    }

    private static String attr(String tag, String name) {
        java.util.regex.Matcher m = java.util.regex.Pattern.compile("\\b" + name + "=\"([^\"]*)\"", java.util.regex.Pattern.CASE_INSENSITIVE).matcher(tag);
        return m.find() ? m.group(1).replace("&amp;", "&").replace("&quot;", "\"") : null;
    }

    private void pin(HttpsURLConnection c) throws IOException {
        try {
            SSLContext sc = SSLContext.getInstance("TLS");
            sc.init(null, new TrustManager[]{new X509TrustManager() {
                @Override public void checkClientTrusted(X509Certificate[] ch, String a) { }
                @Override public void checkServerTrusted(X509Certificate[] ch, String a) throws CertificateException {
                    if (ch == null || ch.length == 0) throw new CertificateException("no certificate");
                    String fp = sha256(ch[0].getEncoded());
                    seenFingerprint = fp;
                    String want = f.fingerprint;
                    if (want != null && !want.isEmpty() && !want.equalsIgnoreCase(fp)) {
                        throw new CertificateException("pin:" + fp);
                    }
                }
                @Override public X509Certificate[] getAcceptedIssuers() { return new X509Certificate[0]; }
            }}, new SecureRandom());
            c.setSSLSocketFactory(sc.getSocketFactory());
            c.setHostnameVerifier(new HostnameVerifier() {
                @Override public boolean verify(String h, SSLSession s) { return true; }   // pinned instead
            });
        } catch (Exception e) {
            throw new IOException(e);
        }
    }

    static String sha256(byte[] b) {
        try {
            byte[] d = MessageDigest.getInstance("SHA-256").digest(b);
            StringBuilder sb = new StringBuilder();
            for (byte x : d) sb.append(String.format("%02x", x & 255));
            return sb.toString();
        } catch (Exception e) {
            return "";
        }
    }

    /** Calls the frame and returns the parsed JSON (JSONObject, JSONArray or String). */
    Object call(String method, String path, Object body) throws IOException {
        return call(method, path, body, 15000);
    }

    Object call(String method, String path, Object body, int readMs) throws IOException {
        HttpURLConnection c = null;
        try {
            c = open(path, method, readMs);
            if (body != null) {
                byte[] b = body.toString().getBytes("UTF-8");
                c.setDoOutput(true);
                c.setRequestProperty("Content-Type", "application/json");
                c.setFixedLengthStreamingMode(b.length);
                OutputStream o = c.getOutputStream();
                o.write(b);
                o.close();
            } else if (!"GET".equals(method) && !"DELETE".equals(method)) {
                c.setDoOutput(true);
                c.setRequestProperty("Content-Type", "application/json");
                c.setFixedLengthStreamingMode(2);
                OutputStream o = c.getOutputStream();
                o.write("{}".getBytes("UTF-8"));
                o.close();
            }
            return read(c);
        } catch (javax.net.ssl.SSLHandshakeException e) {
            throw certOr(e);
        } finally {
            if (c != null) c.disconnect();
        }
    }

    IOException certOr(IOException e) {
        String m = String.valueOf(e.getMessage());
        Throwable t = e;
        while (t != null) {
            String tm = String.valueOf(t.getMessage());
            int i = tm.indexOf("pin:");
            if (i >= 0) return new CertChangedException(tm.substring(i + 4).trim());
            t = t.getCause();
        }
        return e;
    }

    Object read(HttpURLConnection c) throws IOException {
        int code = c.getResponseCode();
        String loc = c.getHeaderField("Location");
        if (code == 401 || (code >= 300 && code < 400 && loc != null
                && (loc.contains("/Connect") || loc.contains("Login") || loc.contains("/dfr-login")))
                || (code == 403 && !f.https)) {
            throw new AuthException("HTTP " + code);
        }
        InputStream in = code >= 400 ? c.getErrorStream() : c.getInputStream();
        String s = in == null ? "" : readAll(in);
        if (code >= 400) {
            HttpException he = new HttpException(code, s.length() > 200 ? s.substring(0, 200) : s);
            he.body = s;
            throw he;
        }
        if (code >= 300) throw new HttpException(code, loc);
        String t = s.trim();
        if (t.startsWith("{") || t.startsWith("[")) {
            try {
                return new JSONTokener(t).nextValue();
            } catch (Exception ignored) {
            }
        }
        return s;
    }

    JSONObject obj(String method, String path, Object body) throws IOException {
        Object o = call(method, path, body);
        return o instanceof JSONObject ? (JSONObject) o : new JSONObject();
    }

    JSONArray arr(String method, String path, Object body) throws IOException {
        Object o = call(method, path, body);
        if (o instanceof JSONArray) return (JSONArray) o;
        if (o instanceof JSONObject) {
            JSONObject j = (JSONObject) o;
            for (String k : new String[]{"items", "data", "playlists", "results", "value"}) {
                if (j.optJSONArray(k) != null) return j.optJSONArray(k);
            }
        }
        return new JSONArray();
    }

    static String readAll(InputStream in) throws IOException {
        ByteArrayOutputStream bo = new ByteArrayOutputStream();
        byte[] buf = new byte[8192];
        int n;
        int total = 0;
        while ((n = in.read(buf)) > 0 && total < 4 * 1024 * 1024) {
            bo.write(buf, 0, n);
            total += n;
        }
        in.close();
        return bo.toString("UTF-8");
    }
}
