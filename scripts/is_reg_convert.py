#!/usr/bin/env python3
"""Convert regulations fetched by is_reg_fetch.py into LawCodex Markdown.

Usage: is_reg_convert.py <raw-dir> <repo-dir> [--retrieved YYYY-MM-DD]

Reads <raw-dir>/reg/json/*.json, writes <repo-dir>/reglugerdir/<year>/<year>-<nr>-<slug>.md.
Regulations for which island.is only returns a redirect to the legacy site
(www.reglugerd.is, consolidated text only as Word documents) have no text and are listed in
<raw-dir>/reg/no_text.json instead.
"""
import argparse
import datetime
import json
import os
import re
import sys

from markdownify import MarkdownConverter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from is_convert import slugify, yaml_str  # noqa: E402

SITE = "https://island.is/reglugerdir/nr/"


def roman(n):
    vals = [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"),
            (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]
    out = ""
    for v, s in vals:
        while n >= v:
            out += s
            n -= v
    return out


class Conv(MarkdownConverter):
    def convert_h2(self, el, text, parent_tags=None, **kw):
        return self._h(el, text, 2)

    def convert_h3(self, el, text, parent_tags=None, **kw):
        return self._h(el, text, 3)

    def convert_h4(self, el, text, parent_tags=None, **kw):
        return self._h(el, text, 4)

    def convert_h5(self, el, text, parent_tags=None, **kw):
        return self._h(el, text, 5)

    def convert_h6(self, el, text, parent_tags=None, **kw):
        return self._h(el, text, 6)

    def _h(self, el, text, level):
        level = min(level + self.options.get("shift", 0), 6)
        text = re.sub(r"\s+", " ", text.replace("*", "")).strip()
        if not text:
            return "\n\n"
        return "\n\n" + "#" * level + " " + text + "\n\n"

    def convert_li(self, el, text, parent_tags=None, **kw):
        parent = el.parent
        typ = parent.get("type") if parent is not None and parent.name == "ol" else None
        if typ in ("a", "A", "i", "I"):
            start = int(parent.get("start")) if str(parent.get("start") or "").isdigit() else 1
            idx = start + len(el.find_previous_siblings("li"))
            if typ in ("a", "A"):
                label = ""
                while idx > 0:
                    idx, r = divmod(idx - 1, 26)
                    label = chr(ord("a") + r) + label
            else:
                label = roman(idx)
            if typ.isupper():
                label = label.upper()
            text = (text or "").strip()
            if not text:
                return "\n"
            text = re.sub(r"\n(?=.)", "\n    ", text)
            return f"- {label}. {text}\n"
        return super().convert_li(el, text, parent_tags=parent_tags, **kw)

    def convert_img(self, el, text, parent_tags=None, **kw):
        src = el.get("src") or ""
        if src.startswith("data:"):
            return "[image]"
        return super().convert_img(el, text, parent_tags=parent_tags, **kw)


def to_md(html, shift=0):
    if not html:
        return ""
    md = Conv(heading_style="ATX", bullets="-", strip=["span"], shift=shift,
              escape_underscores=True, escape_asterisks=True).convert(html)
    md = md.replace("\xa0", " ")
    md = re.sub(r"[ \t]+\n", "\n", md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw")
    ap.add_argument("repo")
    ap.add_argument("--retrieved", default=datetime.date.today().isoformat())
    args = ap.parse_args()
    src = os.path.join(args.raw, "reg", "json")
    outdir = os.path.join(args.repo, "reglugerdir")
    if os.path.isdir(outdir):
        for root, _, files in os.walk(outdir):
            for f in files:
                if f.endswith(".md"):
                    os.remove(os.path.join(root, f))
    no_text, n = [], 0
    for fn in sorted(os.listdir(src)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(src, fn), encoding="utf-8") as f:
            d = json.load(f)
        if not d or not d.get("text"):
            no_text.append({k: (d or {}).get(k) for k in ("name", "title", "redirectUrl", "originalDoc")}
                           | {"file": fn})
            continue
        num, year = d["name"].split("/")
        num_i = int(num)
        title = re.sub(r"\s+", " ", d.get("title") or "").strip()
        slug_title = re.sub(r"^Reglugerð (um|fyrir|varðandi)\s+", "", title)
        name = f"{year}-{num_i}-{slugify(slug_title, 70)}.md"
        path = os.path.join(outdir, year, name)
        fm = ["---", f"title: {yaml_str(title)}", f'identifier: "{num_i}/{year}"',
              "type: regulation", "jurisdiction: is", "language: is"]
        date = d.get("signatureDate") or d.get("publishedDate")
        if date:
            fm.append(f"date: {date[:10]}")
        if d.get("publishedDate"):
            fm.append(f"published: {d['publishedDate'][:10]}")
        if d.get("effectiveDate"):
            fm.append(f"effective: {d['effectiveDate'][:10]}")
        if d.get("lastAmendDate"):
            fm.append(f"last_amended: {d['lastAmendDate'][:10]}")
        fm.append("status: in_force")
        if d.get("ministry") and d["ministry"].get("name"):
            fm.append(f"ministry: {yaml_str(d['ministry']['name'])}")
        if d.get("lawChapters"):
            fm.append("law_chapters:")
            for ch in d["lawChapters"]:
                fm.append(f"  - {yaml_str(ch.get('slug', '') + ' ' + ch.get('name', ''))}")
        fm.append(f'source: "{SITE}{num}-{year}"')
        if d.get("originalDoc"):
            fm.append(f'original_publication: "{d["originalDoc"]}"')
        fm.append(f"retrieved: {args.retrieved}")
        fm.append("---")
        body = to_md(d["text"])
        out = "\n".join(fm) + "\n\n# " + title + "\n\n"
        out += f"**Nr. {num_i}/{year}**\n\n"
        out += body + "\n"
        for i, ap_ in enumerate(d.get("appendixes") or [], 1):
            at = re.sub(r"\s+", " ", ap_.get("title") or f"Viðauki {i}").strip()
            out += f"\n## {at}\n\n" + to_md(ap_.get("text") or "", shift=1) + "\n"
        if d.get("comments"):
            out += "\n## Athugasemdir ritstjóra\n\n" + to_md(d["comments"], shift=1) + "\n"
        out = re.sub(r"\n{3,}", "\n\n", out)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.exists(path):
            raise SystemExit(f"collision: {path}")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(out)
        n += 1
    with open(os.path.join(args.raw, "reg", "no_text.json"), "w", encoding="utf-8") as f:
        json.dump(no_text, f, ensure_ascii=False, indent=1)
    print(f"wrote {n} regulations; {len(no_text)} without text (redirect to reglugerd.is)",
          file=sys.stderr)


if __name__ == "__main__":
    main()
