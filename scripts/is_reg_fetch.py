#!/usr/bin/env python3
"""Fetch Icelandic regulations (reglugerðir) from the public island.is GraphQL endpoint.

Usage: is_reg_fetch.py <raw-dir> [--workers 2] [--delay 1.0]

1. Pages through getRegulations(type: newest) -> <raw-dir>/reg/list.json (all regulations,
   base and amending, current and repealed: metadata only).
2. For every *base* regulation that is not repealed, fetches the current consolidated
   version with getRegulation(viewType: current) -> <raw-dir>/reg/json/<NNNN-YYYY>.json.
   Cached files are not re-downloaded.

Note: api.reglugerd.is (the backend behind island.is) disallows all robots, so it is not
used; island.is itself has no robots.txt restrictions.
"""
import argparse
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

UA = "LawCodex/1.0 (+https://github.com/LawCodex)"
GQL = "https://island.is/api/graphql"
LIST_Q = "query($i:GetRegulationsInput!){getRegulations(input:$i)}"
REG_Q = "query($i:GetRegulationInput!){getRegulation(input:$i)}"

_local = threading.local()


def session():
    if not hasattr(_local, "s"):
        s = requests.Session()
        s.headers["User-Agent"] = UA
        s.headers["Content-Type"] = "application/json"
        _local.s = s
    return _local.s


def gql(query, variables, delay):
    last = None
    for attempt in range(6):
        try:
            r = session().post(GQL, json={"query": query, "variables": variables}, timeout=120)
            if r.status_code == 200:
                d = r.json()
                if d.get("data") is not None:
                    time.sleep(delay)
                    return d["data"]
                last = d.get("errors")
            else:
                last = f"HTTP {r.status_code}"
                if r.status_code in (403, 429):
                    print(f"{last}: backing off", file=sys.stderr)
        except (requests.RequestException, ValueError) as e:
            last = str(e)
        time.sleep(delay * 5 * (2 ** attempt))
    raise RuntimeError(f"failed {variables}: {last}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--refresh-list", action="store_true")
    args = ap.parse_args()
    base = os.path.join(args.raw, "reg")
    os.makedirs(os.path.join(base, "json"), exist_ok=True)
    lpath = os.path.join(base, "list.json")

    if args.refresh_list or not os.path.exists(lpath):
        items, page, total = [], 1, None
        while True:
            d = gql(LIST_Q, {"i": {"type": "newest", "page": page}}, args.delay)["getRegulations"]
            items.extend(d["data"])
            total = d["totalPages"]
            if page % 50 == 0:
                print(f"list page {page}/{total}", file=sys.stderr)
            if page >= total:
                break
            page += 1
        with open(lpath + ".part", "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False)
        os.replace(lpath + ".part", lpath)
    with open(lpath, encoding="utf-8") as f:
        items = json.load(f)
    todo = sorted({x["name"] for x in items if x.get("type") == "base" and not x.get("repealed")})
    odd = [n for n in todo if not re.fullmatch(r"\d{4}/\d{4}", n)]
    if odd:
        # the API only accepts NNNN-YYYY names (e.g. "162V/1998" cannot be fetched)
        print(f"skipping malformed names: {odd}", file=sys.stderr)
        todo = [n for n in todo if n not in odd]
    print(f"{len(items)} regulations listed; {len(todo)} base regulations in force", file=sys.stderr)

    done = [0]
    lock = threading.Lock()

    def fetch(name):
        slug = name.replace("/", "-")
        path = os.path.join(base, "json", slug + ".json")
        if os.path.exists(path):
            return
        d = gql(REG_Q, {"i": {"name": slug, "viewType": "current"}}, args.delay)["getRegulation"]
        with open(path + ".part", "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.replace(path + ".part", path)
        with lock:
            done[0] += 1
            if done[0] % 200 == 0:
                print(f"fetched {done[0]}", file=sys.stderr)

    errors = 0
    with ThreadPoolExecutor(max_workers=min(args.workers, 4)) as ex:
        for fut in [ex.submit(fetch, n) for n in todo]:
            try:
                fut.result()
            except Exception as e:  # keep going; re-run to retry
                errors += 1
                print(e, file=sys.stderr)
    print(f"done; {errors} errors", file=sys.stderr)


if __name__ == "__main__":
    main()
