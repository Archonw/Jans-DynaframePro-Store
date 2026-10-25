"""Stellt jedes Pack im Katalog auf ein GitHub Release um (für Download-Zähler).

Für jedes Pack wird unter plugin_packs/ die ZIP gesucht, deren Größe und SHA-256
zum Katalogeintrag passen. Fehlt das Release <pack-id>-<version>, wird es mit
dieser ZIP angelegt. Zeigt download_url nicht auf genau dieses Release (z. B.
noch relativ, alte Version oder aus dem Test-Store kopiert), wird sie im
Katalog korrigiert und committet. Läuft im Test-Store und im öffentlichen Store.
"""
import glob
import hashlib
import json
import os
import subprocess
import sys

STORE = "DynaframPro/Jans-store" if os.path.isdir("DynaframPro/Jans-store") else "."
CATALOG = f"{STORE}/catalog.json"
REPO = os.environ.get("GITHUB_REPOSITORY", "Archonw/Jans-DynaframePro-Store")


def gh(*args):
    return subprocess.run(["gh", *args, "-R", REPO], capture_output=True, text=True)


def find_zip(pack):
    for cand in sorted(glob.glob(f"{STORE}/plugin_packs/**/*.zip", recursive=True)):
        if os.path.getsize(cand) != pack["size"]:
            continue
        if hashlib.sha256(open(cand, "rb").read()).hexdigest() == pack["checksum"]:
            return cand
    return None


def main():
    text = open(CATALOG, encoding="utf-8").read()
    failed = False
    for p in json.loads(text)["packs"]:
        tag = f"{p['id']}-{p['version']}"
        path = find_zip(p)
        if not path:
            print(f"{tag}: keine ZIP unter plugin_packs passt zu Größe/Checksumme", file=sys.stderr)
            failed = True
            continue
        name = os.path.basename(path)
        view = gh("release", "view", tag, "--json", "assets")
        if view.returncode == 0:
            assets = {a["name"]: a["size"] for a in json.loads(view.stdout)["assets"]}
            if assets.get(name) != p["size"]:
                print(f"{tag}: Release hat eine andere ZIP. Neue Inhalte brauchen eine höhere "
                      f"Version.", file=sys.stderr)
                failed = True
                continue
        else:
            r = gh("release", "create", tag, path, "--title", f"{p['title']} {p['version']}",
                   "--notes", f"Store-Paket {p['id']} {p['version']}")
            print(f"{tag}: Release angelegt {r.stdout.strip()}{r.stderr.strip()}")
            if r.returncode != 0:
                failed = True
                continue
        url = f"https://github.com/{REPO}/releases/download/{tag}/{name}"
        if p["download_url"] != url:
            old = f'"download_url": "{p["download_url"]}"'
            if text.count(old) != 1:
                print(f"{tag}: download_url nicht eindeutig im Katalog", file=sys.stderr)
                failed = True
                continue
            text = text.replace(old, f'"download_url": "{url}"')
            print(f"{tag}: download_url -> {url}")
    json.loads(text)
    if text != open(CATALOG, encoding="utf-8").read():
        open(CATALOG, "w", encoding="utf-8").write(text)
        if os.environ.get("GITHUB_ACTIONS"):
            git = lambda *a: subprocess.run(["git", *a], check=True)
            git("config", "user.name", "github-actions[bot]")
            git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
            git("commit", "-am", "Katalog: download_url auf GitHub Releases")
            git("push")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
