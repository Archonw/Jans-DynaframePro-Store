package de.archonw.framecompanion;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.net.http.SslCertificate;
import android.net.http.SslError;
import android.os.Build;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.JavascriptInterface;
import android.webkit.SslErrorHandler;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Shows one of the frame's own web pages (e.g. a plugin's settings page) inside the app.
 * With DynaFrame's login on, the app signs the page's requests itself: GETs are loaded through
 * the app with the API key, and fetch/XHR of the page get the key added by a small script.
 * The frame's self-signed certificate is accepted only if it matches the pinned one.
 */
public class WebActivity extends Activity {

    static void open(Context c, Frame f, String path, String title) {
        c.startActivity(new Intent(c, WebActivity.class).putExtra("host", f.host).putExtra("path", path).putExtra("title", title));
    }

    private Frame f;
    private Http http;
    private WebView web;
    private ProgressBar bar;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        f = new Store(this).find(getIntent().getStringExtra("host"));
        if (f == null) { finish(); return; }
        http = new Http(f);
        getWindow().setStatusBarColor(Ui.BG);
        getWindow().setNavigationBarColor(Ui.BG);

        LinearLayout root = Ui.column(this);
        root.setBackgroundColor(Ui.BG);
        LinearLayout head = Ui.row(this);
        int p = Ui.dp(this, 12);
        head.setPadding(p, Ui.dp(this, 10), p, Ui.dp(this, 10));
        TextView back = Ui.icon(this, 0xf12f, 22, Ui.TEXT);   // arrow-left
        back.setPadding(Ui.dp(this, 6), Ui.dp(this, 4), Ui.dp(this, 14), Ui.dp(this, 4));
        back.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { onBackPressed(); }
        });
        head.addView(back);
        String t = getIntent().getStringExtra("title");
        TextView title = Ui.text(this, t == null ? f.name : t, 18, Ui.TEXT, true);
        title.setSingleLine(true);
        head.addView(title, new LinearLayout.LayoutParams(0, -2, 1f));
        TextView ext = Ui.icon(this, 0xf1c5, 20, Ui.MUTED);     // open in browser
        ext.setPadding(Ui.dp(this, 12), Ui.dp(this, 4), Ui.dp(this, 6), Ui.dp(this, 4));
        ext.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) {
                try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(web.getUrl() != null ? web.getUrl() : url()))); }
                catch (Exception ignored) { }
            }
        });
        head.addView(ext);
        root.addView(head);
        bar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        bar.setMax(100);
        bar.setProgressTintList(android.content.res.ColorStateList.valueOf(Ui.ACCENT));
        root.addView(bar, new LinearLayout.LayoutParams(-1, Ui.dp(this, 3)));
        web = new WebView(this);
        web.setBackgroundColor(Ui.BG);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE);
        root.addView(web, new LinearLayout.LayoutParams(-1, 0, 1f));
        setContentView(root);

        copyCookies();
        if (useKey()) web.addJavascriptInterface(new Bridge(), "DFApp");
        web.setWebChromeClient(new WebChromeClient() {
            @Override public void onProgressChanged(WebView v, int n) {
                bar.setProgress(n);
                bar.setVisibility(n >= 100 ? View.INVISIBLE : View.VISIBLE);
            }
        });
        web.setWebViewClient(new WebViewClient() {
            @Override public void onReceivedSslError(WebView v, SslErrorHandler h, SslError e) {
                String fp = fingerprint(e.getCertificate());
                if (fp != null && f.fingerprint != null && fp.equalsIgnoreCase(f.fingerprint) && sameHost(e.getUrl())) h.proceed();
                else h.cancel();
            }

            @Override public WebResourceResponse shouldInterceptRequest(WebView v, WebResourceRequest r) {
                if (!useKey() || !"GET".equalsIgnoreCase(r.getMethod()) || !sameHost(r.getUrl().toString())) return null;
                return load(r);
            }

            @Override public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                if (sameHost(r.getUrl().toString())) return false;
                try { startActivity(new Intent(Intent.ACTION_VIEW, r.getUrl())); } catch (Exception ignored) { }
                return true;
            }
        });
        String path = getIntent().getStringExtra("path");
        web.loadUrl(url() + (path == null ? "/" : path));
    }

    @Override
    public void onBackPressed() {
        if (web != null && web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }

    private String url() { return http.base(); }

    private boolean useKey() { return f.https && f.apiKey != null && !f.apiKey.isEmpty(); }

    private boolean sameHost(String u) {
        try {
            Uri a = Uri.parse(u), b = Uri.parse(url());
            return a.getHost() != null && a.getHost().equalsIgnoreCase(b.getHost());
        } catch (Exception e) {
            return false;
        }
    }

    /** User + password sign-in: hand the app's session cookie to the web view. */
    private void copyCookies() {
        try {
            java.net.CookieHandler h = java.net.CookieHandler.getDefault();
            if (!(h instanceof java.net.CookieManager)) return;
            CookieManager cm = CookieManager.getInstance();
            cm.setAcceptCookie(true);
            for (java.net.HttpCookie c : ((java.net.CookieManager) h).getCookieStore().get(new java.net.URI(url())))
                cm.setCookie(url(), c.getName() + "=" + c.getValue() + "; path=/");
        } catch (Exception ignored) {
        }
    }

    /** Loads a GET through the app (with the key and the pinned certificate). */
    private WebResourceResponse load(WebResourceRequest r) {
        HttpURLConnection c = null;
        try {
            Uri u = r.getUrl();
            String path = u.getEncodedPath() + (u.getEncodedQuery() != null ? "?" + u.getEncodedQuery() : "");
            if (path.startsWith("null")) path = "/";
            c = http.open(path, "GET", 30000);
            c.setInstanceFollowRedirects(true);
            Map<String, String> rh = r.getRequestHeaders();
            if (rh != null) for (Map.Entry<String, String> e : rh.entrySet()) {
                String k = e.getKey();
                if (k.equalsIgnoreCase("Authorization") || k.equalsIgnoreCase("Origin") || k.equalsIgnoreCase("Referer")
                        || k.equalsIgnoreCase("Accept-Encoding")) continue;
                c.setRequestProperty(k, e.getValue());
            }
            String ck = CookieManager.getInstance().getCookie(url());
            if (ck != null) c.setRequestProperty("Cookie", ck);
            int code = c.getResponseCode();
            InputStream in = code >= 400 ? c.getErrorStream() : c.getInputStream();
            ByteArrayOutputStream bo = new ByteArrayOutputStream();
            if (in != null) {
                byte[] buf = new byte[16384];
                int n;
                while ((n = in.read(buf)) > 0) bo.write(buf, 0, n);
                in.close();
            }
            String type = c.getContentType() == null ? "application/octet-stream" : c.getContentType();
            String mime = type.split(";")[0].trim();
            String charset = "UTF-8";
            int ci = type.toLowerCase().indexOf("charset=");
            if (ci >= 0) charset = type.substring(ci + 8).trim();
            byte[] body = bo.toByteArray();
            if (mime.equals("text/html")) body = inject(new String(body, charset)).getBytes(charset);
            Map<String, String> headers = new HashMap<>();
            for (Map.Entry<String, List<String>> e : c.getHeaderFields().entrySet()) {
                if (e.getKey() == null || e.getValue() == null || e.getValue().isEmpty()) continue;
                String k = e.getKey();
                if (k.equalsIgnoreCase("Content-Length") || k.equalsIgnoreCase("Content-Encoding") || k.equalsIgnoreCase("Transfer-Encoding")
                        || k.equalsIgnoreCase("Content-Security-Policy")) continue;
                if (k.equalsIgnoreCase("Set-Cookie")) {
                    for (String sc : e.getValue()) CookieManager.getInstance().setCookie(url(), sc);
                    continue;
                }
                headers.put(k, e.getValue().get(0));
            }
            String reason = c.getResponseMessage();
            if (reason == null || reason.isEmpty()) reason = code < 400 ? "OK" : "Error";
            if (code >= 300 && code < 400) code = 200;   // redirects were followed already
            return new WebResourceResponse(mime, charset, code, reason, headers, new ByteArrayInputStream(body));
        } catch (Exception e) {
            return null;
        } finally {
            if (c != null) c.disconnect();
        }
    }

    /**
     * The page's own POST/PUT/DELETE calls (saving settings, "test connection") cannot get the key from
     * the web view, so the injected script hands them to the app, which sends them with the key.
     */
    final class Bridge {
        @JavascriptInterface
        public String request(String method, String url, String headersJson, String body) {
            org.json.JSONObject out = new org.json.JSONObject();
            HttpURLConnection c = null;
            try {
                if (!sameHost(url)) throw new java.io.IOException("other host");
                Uri u = Uri.parse(url);
                String path = (u.getEncodedPath() == null ? "/" : u.getEncodedPath()) + (u.getEncodedQuery() != null ? "?" + u.getEncodedQuery() : "");
                c = http.open(path, method.toUpperCase(java.util.Locale.ROOT), 120000);
                c.setInstanceFollowRedirects(true);
                c.setRequestProperty("Referer", url);
                if (headersJson != null && !headersJson.isEmpty()) {
                    org.json.JSONObject h = new org.json.JSONObject(headersJson);
                    java.util.Iterator<String> it = h.keys();
                    while (it.hasNext()) {
                        String k = it.next();
                        String lk = k.toLowerCase(java.util.Locale.ROOT);
                        if (lk.equals("authorization") || lk.equals("origin") || lk.equals("referer") || lk.equals("host") || lk.equals("content-length")) continue;
                        c.setRequestProperty(k, h.optString(k));
                    }
                }
                String ck = CookieManager.getInstance().getCookie(url());
                if (ck != null) c.setRequestProperty("Cookie", ck);
                if (body != null && !"GET".equalsIgnoreCase(method) && !"HEAD".equalsIgnoreCase(method)) {
                    byte[] b = body.getBytes("UTF-8");
                    c.setDoOutput(true);
                    if (c.getRequestProperty("Content-Type") == null) c.setRequestProperty("Content-Type", "text/plain;charset=UTF-8");
                    c.setFixedLengthStreamingMode(b.length);
                    java.io.OutputStream o = c.getOutputStream();
                    o.write(b);
                    o.close();
                }
                int code = c.getResponseCode();
                InputStream in = code >= 400 ? c.getErrorStream() : c.getInputStream();
                String text = in == null ? "" : Http.readAll(in);
                org.json.JSONObject hs = new org.json.JSONObject();
                for (Map.Entry<String, List<String>> e : c.getHeaderFields().entrySet()) {
                    if (e.getKey() == null || e.getValue() == null || e.getValue().isEmpty()) continue;
                    if (e.getKey().equalsIgnoreCase("Set-Cookie")) {
                        for (String sc : e.getValue()) CookieManager.getInstance().setCookie(url(), sc);
                        continue;
                    }
                    if (e.getKey().equalsIgnoreCase("Content-Type")) hs.put("Content-Type", e.getValue().get(0));
                }
                out.put("status", code).put("statusText", c.getResponseMessage() == null ? "" : c.getResponseMessage())
                        .put("headers", hs).put("body", text);
            } catch (Exception e) {
                try { out.put("error", String.valueOf(e.getMessage())); } catch (Exception ignored) { }
            } finally {
                if (c != null) c.disconnect();
            }
            return out.toString();
        }
    }

    /** Adds the key to the page's own calls: GETs come through the app anyway, the rest go via the bridge. */
    private String inject(String html) {
        String key = f.apiKey.replace("\\", "\\\\").replace("'", "\\'");
        String js = "<script>(function(){var K='Bearer " + key + "';"
                + "function mine(u){u=String(u);return u.indexOf('http')!==0||u.indexOf(location.origin)===0;}"
                + "var B=window.DFApp,of=window.fetch;"
                + "if(of)window.fetch=function(i,o){o=o||{};try{"
                + "var u=(typeof i==='string')?i:(i&&i.url);var m=String(o.method||(i&&i.method)||'GET').toUpperCase();var b=o.body;"
                + "if(B&&mine(u)&&m!=='GET'&&m!=='HEAD'&&(typeof i==='string'||i instanceof URL)&&(b==null||typeof b==='string'||b instanceof URLSearchParams)){"
                + "var h={};try{new Headers(o.headers||{}).forEach(function(v,k){h[k]=v;});}catch(e){}"
                + "if(b instanceof URLSearchParams){if(!h['content-type'])h['content-type']='application/x-www-form-urlencoded;charset=UTF-8';b=b.toString();}"
                + "var abs=new URL(String(u),location.href).href;"
                + "return new Promise(function(res,rej){setTimeout(function(){try{var r=JSON.parse(B.request(m,abs,JSON.stringify(h),b==null?null:b));"
                + "if(r.error){rej(new TypeError(r.error));return;}"
                + "var nb=(r.status===204||r.status===205||r.status===304)?null:r.body;"
                + "res(new Response(nb,{status:r.status,statusText:r.statusText||'',headers:r.headers||{}}));}catch(e){rej(e);}},0);});}"
                + "if(mine(u)){var hh=new Headers(o.headers||(typeof i!=='string'&&i&&i.headers)||{});if(!hh.has('Authorization'))hh.set('Authorization',K);o.headers=hh;}"
                + "}catch(e){}return of.call(this,i,o);};"
                + "var oo=XMLHttpRequest.prototype.open,os=XMLHttpRequest.prototype.send;"
                + "XMLHttpRequest.prototype.open=function(m,u){this.__df=mine(u);return oo.apply(this,arguments);};"
                + "XMLHttpRequest.prototype.send=function(){if(this.__df){try{this.setRequestHeader('Authorization',K);}catch(e){}}return os.apply(this,arguments);};"
                + "})();</script>";
        // a page-level CSP would block the inline script
        html = html.replaceAll("(?i)<meta[^>]+http-equiv=[\"']?content-security-policy[^>]*>", "");
        int i = html.toLowerCase().indexOf("<head");
        if (i >= 0) {
            int j = html.indexOf('>', i);
            if (j > 0) return html.substring(0, j + 1) + js + html.substring(j + 1);
        }
        return js + html;
    }

    private static String fingerprint(SslCertificate c) {
        try {
            X509Certificate x;
            if (Build.VERSION.SDK_INT >= 29) x = c.getX509Certificate();
            else {
                byte[] b = SslCertificate.saveState(c).getByteArray("x509-certificate");
                x = (X509Certificate) CertificateFactory.getInstance("X.509").generateCertificate(new ByteArrayInputStream(b));
            }
            return x == null ? null : Http.sha256(x.getEncoded());
        } catch (Exception e) {
            return null;
        }
    }
}
