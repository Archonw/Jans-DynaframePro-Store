package de.archonw.remoteframetv;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.graphics.Color;
import android.net.Uri;
import android.net.http.SslError;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.WindowManager;
import android.webkit.CookieManager;
import android.webkit.SslErrorHandler;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.TextView;
import android.widget.Toast;

import java.net.InetAddress;

/** Shows DynaFrame's /RemoteFrame page full screen. Back returns to the frame list. */
public class ViewerActivity extends Activity {

    private static final int RETRY_MS = 10000;

    private WebView web;
    private TextView overlay;
    private String url;
    private String name;
    private final Handler handler = new Handler();
    private boolean failed;

    private final Runnable retry = new Runnable() {
        @Override public void run() {
            failed = false;
            web.loadUrl(url);
        }
    };

    private final Runnable hideOverlay = new Runnable() {
        @Override public void run() { if (!failed) overlay.setVisibility(View.GONE); }
    };

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        url = getIntent().getStringExtra("url");
        name = getIntent().getStringExtra("name");
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON
                | WindowManager.LayoutParams.FLAG_FULLSCREEN);

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.BLACK);

        web = new WebView(this);
        web.setBackgroundColor(Color.BLACK);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);   // videos and music in scenes start by themselves
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        if (Build.VERSION.SDK_INT >= 21) s.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        s.setUserAgentString(s.getUserAgentString() + " RemoteFrameTV/" + BuildConfigCompat.version(this));
        CookieManager.getInstance().setAcceptCookie(true);
        if (Build.VERSION.SDK_INT >= 21) CookieManager.getInstance().setAcceptThirdPartyCookies(web, true);

        web.setWebChromeClient(new WebChromeClient());
        web.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedSslError(WebView view, SslErrorHandler h, SslError error) {
                // Frames use self-signed certificates. Accept them only for addresses in the home network.
                if (isLocal(error.getUrl())) h.proceed();
                else h.cancel();
            }

            @Override
            public void onPageFinished(WebView view, String u) {
                CookieManager.getInstance().flush();   // stay logged in after a restart
                if (steer(u)) return;
                if (u != null && u.contains("/RemoteFrame")) {
                    // The page's own full-screen button is useless on a TV and covers the scene.
                    view.evaluateJavascript("(function(){var s=document.createElement('style');"
                            + "s.textContent='.remote-frame-fullscreen,[class*=fullscreen-btn],[aria-label*=ullscreen]{display:none!important}';"
                            + "document.head.appendChild(s);})()", null);
                }
                if (!failed) handler.postDelayed(hideOverlay, 600);
            }

            @Override
            public void onReceivedHttpError(WebView view, WebResourceRequest req, android.webkit.WebResourceResponse resp) {
                // DynaFrame before 2026.11.18 has no numbered remote frames: /RemoteFrame/0 -> 404, use /RemoteFrame.
                if (req.isForMainFrame() && resp.getStatusCode() == 404 && url.endsWith("/RemoteFrame/0")) {
                    url = url.substring(0, url.length() - 2);
                    view.loadUrl(url);
                }
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest req, WebResourceError err) {
                if (req.isForMainFrame()) fail(String.valueOf(err.getDescription()));
            }

            @SuppressWarnings("deprecation")
            @Override
            public void onReceivedError(WebView view, int code, String desc, String failing) {
                if (Build.VERSION.SDK_INT < 23) fail(desc);
            }
        });

        root.addView(web, new FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT));

        overlay = Ui.text(this, getString(R.string.loading, name), 20, Color.WHITE, false);
        overlay.setGravity(Gravity.CENTER);
        overlay.setBackgroundColor(Color.BLACK);
        int p = Ui.dp(this, 48);
        overlay.setPadding(p, p, p, p);
        root.addView(overlay, new FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT));

        setContentView(root);
        immersive();
        web.requestFocus();
        web.loadUrl(url);
        Toast.makeText(this, R.string.back_hint, Toast.LENGTH_SHORT).show();
    }

    /**
     * Keeps the TV on the frame view:
     * - /Connect (http on a frame with WebUI security) -> the same view over https, which offers the login,
     * - after the login DynaFrame may land on its start page -> back to /RemoteFrame.
     */
    private boolean steer(String u) {
        if (u == null) return false;
        Uri now = Uri.parse(u);
        Uri want = Uri.parse(url);
        String path = now.getPath() == null ? "/" : now.getPath();
        if (now.getHost() == null || !now.getHost().equals(want.getHost())) return false;
        if (path.startsWith("/Connect")) {
            if (!"https".equals(now.getScheme())) {
                url = "https://" + want.getEncodedAuthority() + want.getPath();
                getSharedPreferences("remoteframetv", MODE_PRIVATE).edit().putBoolean("secure:" + want.getHost(), true).apply();
                web.loadUrl(url);
                return true;
            }
            return false;
        }
        if (path.startsWith("/RemoteFrame") || path.startsWith("/WebUiAccount") || path.startsWith("/WebUiSetup")) {
            if (path.startsWith("/WebUiAccount") || path.startsWith("/WebUiSetup")) {
                failed = false;
                overlay.setVisibility(View.GONE);   // login page: let the user type
            }
            return false;
        }
        // Any other page of this frame after the login: go to the frame view.
        if (u.startsWith("https://") && !path.startsWith("/engine-proxy")) {
            url = "https://" + now.getEncodedAuthority() + Uri.parse(url).getPath();
            web.loadUrl(url);
            return true;
        }
        return false;
    }

    private void fail(String why) {
        failed = true;
        overlay.setText(getString(R.string.error_retry, name, why));
        overlay.setVisibility(View.VISIBLE);
        handler.removeCallbacks(retry);
        handler.postDelayed(retry, RETRY_MS);
    }

    static boolean isLocal(String u) {
        try {
            String host = Uri.parse(u).getHost();
            if (host == null) return false;
            if (host.endsWith(".local") || host.endsWith(".lan") || host.endsWith(".fritz.box") || host.endsWith(".home.arpa")
                    || !host.contains(".")) return true;
            if (!host.matches("[0-9.]+")) return false;   // only literal IPs below, no DNS lookup on the UI thread
            InetAddress a = InetAddress.getByName(host);
            return a.isSiteLocalAddress() || a.isLinkLocalAddress() || a.isLoopbackAddress()
                    || host.startsWith("100.");          // Tailscale / CGNAT range
        } catch (Exception e) {
            return false;
        }
    }

    @SuppressWarnings("deprecation")
    private void immersive() {
        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
    }

    @Override
    public void onWindowFocusChanged(boolean has) {
        super.onWindowFocusChanged(has);
        if (has) immersive();
    }

    /** Back always returns to the frame list, even while a field of the login page has focus. */
    @Override
    public boolean dispatchKeyEvent(KeyEvent e) {
        if (e.getKeyCode() == KeyEvent.KEYCODE_BACK) {
            if (e.getAction() == KeyEvent.ACTION_UP) finish();
            return true;
        }
        return super.dispatchKeyEvent(e);
    }

    @Override
    protected void onResume() {
        super.onResume();
        web.onResume();
        web.resumeTimers();
    }

    @Override
    protected void onPause() {
        web.onPause();
        CookieManager.getInstance().flush();
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        web.stopLoading();
        if (web.getParent() instanceof android.view.ViewGroup) ((android.view.ViewGroup) web.getParent()).removeView(web);
        web.destroy();
        super.onDestroy();
    }
}
