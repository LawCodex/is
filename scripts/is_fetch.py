#!/usr/bin/env python3
"""Download the latest Lagasafn edition (HTML zip) from althingi.is and extract it.

Usage: is_fetch.py <raw-dir> [--edition 158a]

Writes <raw-dir>/dl/allt-<edition>.zip and extracts it to <raw-dir>/html/.
Obeys robots.txt Crawl-delay (5 s) between requests; re-runs reuse the cached zip.
"""
import argparse
import os
import re
import shutil
import sys
import time
import zipfile

import requests

UA = "LawCodex/1.0 (+https://github.com/LawCodex)"
BASE = "https://www.althingi.is"
INDEX = BASE + "/lagasafn/zip-skra-af-lagasafni/"
DELAY = 5


def get(session, url, **kw):
    for attempt in range(5):
        try:
            r = session.get(url, timeout=120, **kw)
            if r.status_code == 200:
                return r
            print(f"HTTP {r.status_code} for {url}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"error {e} for {url}", file=sys.stderr)
        time.sleep(DELAY * (2 ** attempt))
    raise SystemExit(f"failed: {url}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw")
    ap.add_argument("--edition", help="edition code, e.g. 158a (default: newest)")
    args = ap.parse_args()
    s = requests.Session()
    s.headers["User-Agent"] = UA
    edition = args.edition
    if not edition:
        page = get(s, INDEX).text
        eds = re.findall(r'href="/lagasafn/zip/(\d+[a-z]?)/allt\.zip"', page)
        if not eds:
            raise SystemExit("no edition found on " + INDEX)
        edition = eds[0]
        time.sleep(DELAY)
    print("edition", edition, file=sys.stderr)
    dl = os.path.join(args.raw, "dl")
    os.makedirs(dl, exist_ok=True)
    zpath = os.path.join(dl, f"allt-{edition}.zip")
    if not (os.path.exists(zpath) and zipfile.is_zipfile(zpath)):
        r = get(s, f"{BASE}/lagasafn/zip/{edition}/allt.zip")
        with open(zpath + ".part", "wb") as f:
            f.write(r.content)
        os.replace(zpath + ".part", zpath)
    with zipfile.ZipFile(zpath) as z:
        bad = z.testzip()
        if bad:
            os.remove(zpath)
            raise SystemExit(f"corrupt zip member {bad}; deleted, re-run")
        out = os.path.join(args.raw, "html")
        shutil.rmtree(out, ignore_errors=True)
        os.makedirs(out)
        for name in z.namelist():
            if name.startswith("/") or ".." in name:
                continue
            z.extract(name, out)
    print(f"extracted {zpath} -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
