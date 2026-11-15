package de.archonw.remoteframetv;

import android.content.Context;

final class BuildConfigCompat {
    static String version(Context c) {
        try {
            return c.getPackageManager().getPackageInfo(c.getPackageName(), 0).versionName;
        } catch (Exception e) {
            return "?";
        }
    }
}
