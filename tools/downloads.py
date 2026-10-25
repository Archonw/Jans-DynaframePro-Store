"""Zeigt die Download-Zahlen aller Store-Packs, die als GitHub Release liegen.
Aufruf: python3 downloads.py [owner/repo]   (Standard: öffentlicher Store)
Braucht nur Python 3, keinen GitHub-Login (öffentliche API, 60 Abrufe/Stunde)."""
import json
import sys
import urllib.request
from collections import defaultdict

repo = sys.argv[1] if len(sys.argv) > 1 else "Archonw/Jans-DynaframePro-Store"
releases, page = [], 1
while True:
    url = f"https://api.github.com/repos/{repo}/releases?per_page=100&page={page}"
    with urllib.request.urlopen(url) as r:
        batch = json.load(r)
    releases += batch
    if len(batch) < 100:
        break
    page += 1

# Tag = <pack-id>-<version>; Summe pro Pack über alle Versionen
per_pack = defaultdict(lambda: [0, []])
for rel in releases:
    pack, _, version = rel["tag_name"].rpartition("-")
    n = sum(a["download_count"] for a in rel["assets"])
    per_pack[pack][0] += n
    per_pack[pack][1].append(f"{version}: {n}")

total = 0
for pack, (n, versions) in sorted(per_pack.items(), key=lambda x: -x[1][0]):
    total += n
    print(f"{pack:<36} {n:>6}   ({', '.join(sorted(versions))})")
print(f"{'Summe':<36} {total:>6}")
