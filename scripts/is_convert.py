#!/usr/bin/env python3
"""Convert the Althingi Lagasafn HTML zip (allt.zip) into LawCodex Markdown.

Usage: is_convert.py <extracted-html-dir> <repo-dir> [--retrieved YYYY-MM-DD]

Only the laws listed in lagas.nr.html (the laws in force in this edition) are converted;
the zip also contains stub pages for repealed laws, which are skipped.
"""
import argparse
import datetime
import html
import os
import re
import sys
import unicodedata

from bs4 import BeautifulSoup, NavigableString, Tag

MONTHS = {
    "janúar": 1, "febrúar": 2, "mars": 3, "apríl": 4, "maí": 5, "júní": 6, "júlí": 7,
    "ágúst": 8, "september": 9, "október": 10, "nóvember": 11, "desember": 12,
}
ALTHINGI = "https://www.althingi.is"
FOOTNOTE_SUP = re.compile(r"^\s*\d+\)\s*$")

# ---------------------------------------------------------------- helpers


def slugify(text, maxlen=80):
    tr = {"þ": "th", "Þ": "th", "ð": "d", "Ð": "d", "æ": "ae", "Æ": "ae", "ö": "o", "Ö": "o",
          "ø": "o", "Ø": "o", "å": "a", "Å": "a", "ß": "ss"}
    text = "".join(tr.get(c, c) for c in text)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    if len(text) > maxlen:
        text = text[:maxlen].rsplit("-", 1)[0]
    return text or "untitled"


def yaml_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def md_escape(text):
    text = text.replace("\\", "\\\\").replace("*", "\\*").replace("_", "\\_")
    text = text.replace("<", "&lt;").replace(">", "&gt;").replace("`", "\\`")
    return text


def escape_line_start(line):
    """Prevent text lines from being parsed as Markdown block syntax."""
    m = re.match(r"^(\s*)(\d+)([.)])(\s)", line)
    if m:
        return m.group(1) + m.group(2) + "\\" + m.group(3) + line[m.end(3):]
    m = re.match(r"^(\s*)([#>+\-=|])", line)
    if m:
        return m.group(1) + "\\" + line[len(m.group(1)):]
    return line


class Ctx:
    def __init__(self, in_force_ids, own_path):
        self.in_force = in_force_ids  # id -> repo-relative path
        self.own_dir = os.path.dirname(own_path)


def resolve_href(href, ctx):
    href = html.unescape(href or "").strip()
    if not href:
        return None
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("/"):
        return ALTHINGI + href
    # relative link to another law in the collection, e.g. 1993037.html#G4
    m = re.match(r"^([0-9a-z.]+)\.html(#.*)?$", href)
    if m:
        lid, frag = m.group(1), m.group(2) or ""
        if lid in ctx.in_force:
            return os.path.relpath(ctx.in_force[lid], ctx.own_dir)
        return f"{ALTHINGI}/lagas/nuna/{lid}.html{frag}"
    return f"{ALTHINGI}/lagas/nuna/{href}"


def inline(node, ctx):
    """Convert an inline HTML node (or list of nodes) into Markdown text."""
    if isinstance(node, list):
        return "".join(inline(n, ctx) for n in node)
    if isinstance(node, NavigableString):
        if type(node).__name__ in ("Comment", "Doctype", "Declaration", "ProcessingInstruction"):
            return ""
        return md_escape(re.sub(r"[\r\n\t]+", " ", str(node)))
    if not isinstance(node, Tag):
        return ""
    name = node.name.lower()
    if name in ("img", "script", "style", "meta", "title"):
        return ""
    if name == "br":
        return "<br>"
    inner = "".join(inline(c, ctx) for c in node.children)
    if name in ("b", "strong"):
        return wrap(inner, "**")
    if name in ("i", "em"):
        return wrap(inner, "*")
    if name == "sup":
        return f"<sup>{inner.strip()}</sup>" if inner.strip() else ""
    if name == "sub":
        return f"<sub>{inner.strip()}</sub>" if inner.strip() else ""
    if name == "a":
        url = resolve_href(node.get("href"), ctx)
        if not url or not inner.strip():
            return inner
        if url.startswith(ALTHINGI + "/altext/stjt/") and node.get("title") and inner.strip() == "…":
            # "…" marks omitted (spent/amending) provisions; keep the link to the original act
            return f"[…]({url})"
        return f"[{inner}]({url.replace(' ', '%20').replace(')', '%29')})"
    return inner


def wrap(inner, mark):
    if not inner.strip():
        return inner
    lead = inner[: len(inner) - len(inner.lstrip())]
    trail = inner[len(inner.rstrip()):]
    core = inner.strip()
    # avoid "****" when nesting identical marks
    if core.startswith(mark) and core.endswith(mark) and len(core) > 2 * len(mark):
        return inner
    return f"{lead}{mark}{core}{mark}{trail}"


def frag_to_nodes(fragment):
    soup = BeautifulSoup(f"<div>{fragment}</div>", "html.parser")
    return list(soup.div.children)


def frag_text(fragment):
    return BeautifulSoup(fragment, "html.parser").get_text().replace("\xa0", " ").strip()


def clean_md(s):
    s = s.replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s).strip()
    s = s.replace("<br>", "")
    return s


# ---------------------------------------------------------------- tables


def table_to_md(table_html, ctx):
    soup = BeautifulSoup(table_html, "html.parser")
    out = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        complex_ = any(td.get("colspan") or td.get("rowspan") for td in table.find_all(["td", "th"]))
        grid = []
        for tr in rows:
            cells = []
            for td in tr.find_all(["td", "th"]):
                txt = clean_md(inline(list(td.children), ctx).replace("<br>", " "))
                cells.append(txt.replace("|", "\\|"))
            grid.append(cells)
        grid = [r for r in grid if r]
        if not grid:
            continue
        width = max(len(r) for r in grid)
        if complex_:
            # keep HTML for spanning cells
            lines = ["<table>"]
            for tr in rows:
                lines.append("<tr>")
                for td in tr.find_all(["td", "th"]):
                    attrs = "".join(f' {a}="{td.get(a)}"' for a in ("colspan", "rowspan") if td.get(a))
                    txt = clean_md(inline(list(td.children), ctx).replace("<br>", " "))
                    lines.append(f"<td{attrs}>{txt}</td>")
                lines.append("</tr>")
            lines.append("</table>")
            out.append("\n".join(lines))
            continue
        grid = [r + [""] * (width - len(r)) for r in grid]
        md = ["| " + " | ".join(grid[0]) + " |", "|" + "---|" * width]
        for r in grid[1:]:
            md.append("| " + " | ".join(r) + " |")
        out.append("\n".join(md))
    return "\n\n".join(out)


# ---------------------------------------------------------------- body


HEAD_RANK = [
    (re.compile(r"^\W*(fylgiskjal|viðauki)\b", re.I), -1),
    (re.compile(r"\bbók\b|bálk", re.I), 0),
    (re.compile(r"\bhluti\b", re.I), 1),
    (re.compile(r"\bkafli\b|\bkap\.|\bkapítuli\b", re.I), 2),
]


def heading_rank(text):
    for rx, rank in HEAD_RANK:
        if rx.search(text):
            return rank
    return 3


def convert_body(body, ctx):
    """Return list of blocks: ('h', rank, text) | ('art', text) | ('p', text) | ('raw', text)."""
    tables = []

    def stash(m):
        tables.append(m.group(0))
        return f"<br>@@TABLE{len(tables) - 1}@@<br>"

    body = re.sub(r"<table.*?</table>", stash, body, flags=re.S | re.I)
    body = re.sub(r"</?(body|html)>", "", body, flags=re.I)
    blocks = []
    for frag in re.split(r"<br\s*/?>", body, flags=re.I):
        raw = frag.strip()
        if not raw:
            continue
        m = re.match(r"^@@TABLE(\d+)@@$", raw)
        if m:
            blocks.append(("raw", table_to_md(tables[int(m.group(1))], ctx)))
            continue
        if raw.lower() == "<hr>":
            blocks.append(("raw", "---"))
            continue
        nb = 0
        mm = re.match(r"^((?:&nbsp;|\s)*)", raw)
        if mm:
            nb = mm.group(1).count("&nbsp;")
        s = raw[mm.end():] if mm else raw
        s = re.sub(r"^<hr>", "", s, flags=re.I).strip()
        if not s:
            continue
        if "sk.jpg" in s[:200]:
            # article / provision heading: <b>label</b> optional <em>title</em> + rest
            s2 = re.sub(r"^.*?sk\.jpg[^>]*>\s*", "", s, flags=re.S)
            mb = re.match(r"^<b>(.*?)</b>\s*(?:<em>(.*?)</em>)?(.*)$", s2, flags=re.S)
            if mb:
                label = clean_md(inline(frag_to_nodes(mb.group(1)), ctx))
                title = clean_md(inline(frag_to_nodes(mb.group(2)), ctx)) if mb.group(2) else ""
                rest = clean_md(inline(frag_to_nodes(mb.group(3)), ctx))
                blocks.append(("art", label + (" " + title if title else "")))
                if rest:
                    blocks.append(("p", rest))
            else:
                blocks.append(("p", clean_md(inline(frag_to_nodes(s2), ctx))))
            continue
        if s.startswith("<IMG") and "hk.jpg" in s[:80]:
            blocks.append(("p", clean_md(inline(frag_to_nodes(s), ctx))))
            continue
        if re.match(r"^<i><small>\s*<sup", s, flags=re.I):
            txt = clean_md(inline(frag_to_nodes(s), ctx))
            txt = txt.strip("*").strip()
            blocks.append(("fn", txt))
            continue
        ml = re.match(r'^<span(?: id="[^"]*")?>(.*?)</span>\s*(.*)$', s, flags=re.S)
        if ml and len(frag_text(ml.group(1))) <= 12:
            label = clean_md(inline(frag_to_nodes(ml.group(1)), ctx))
            rest = clean_md(inline(frag_to_nodes(ml.group(2)), ctx))
            blocks.append(("li", max(0, nb // 3 - 1), f"{label} {rest}".strip()))
            continue
        # heading-only fragments: all bold, or all emphasis
        stripped = re.sub(r"<sup[^>]*>.*?</sup>", "", s, flags=re.S)
        if re.fullmatch(r"(\s*<b>.*?</b>\s*[\]\.]*)+", stripped, flags=re.S) and "<b>" in s:
            txt = clean_md(inline(frag_to_nodes(s), ctx))
            txt = re.sub(r"\*\*\s+\*\*", " ", txt)
            txt = txt.replace("**", "")
            blocks.append(("h", heading_rank(frag_text(s)), txt))
            continue
        if re.fullmatch(r"\s*<em>.*?</em>\s*", stripped, flags=re.S):
            txt = clean_md(inline(frag_to_nodes(s), ctx))
            blocks.append(("h", 4, txt.strip("*").strip()))
            continue
        txt = clean_md(inline(frag_to_nodes(s), ctx))
        if txt:
            blocks.append(("p", txt))
    return blocks


def render_blocks(blocks):
    ranks = sorted({b[1] for b in blocks if b[0] == "h"})
    level_of = {r: min(2 + i, 6) for i, r in enumerate(ranks)}
    art_level = min(2 + len(ranks), 6)
    out = []
    for b in blocks:
        kind = b[0]
        if kind == "h":
            out.append("#" * level_of[b[1]] + " " + b[2])
        elif kind == "art":
            if art_level <= 6:
                out.append("#" * art_level + " " + b[1])
        elif kind == "p":
            out.append(escape_line_start(b[1]))
        elif kind == "li":
            # nesting depth is conveyed by the item labels (a., 1., i.); indenting would
            # turn items into code blocks in Markdown
            out.append(escape_line_start(b[2]))
        elif kind == "fn":
            out.append("> " + b[1])
        else:
            out.append(b[1])
    return "\n\n".join(out)


# ---------------------------------------------------------------- per law


def parse_date(year, s):
    m = re.search(r"(\d{1,2})\.\s*([a-záéíóúýþæöð]+)", s)
    if m and m.group(2) in MONTHS and year.isdigit():
        try:
            return datetime.date(int(year), MONTHS[m.group(2)], int(m.group(1))).isoformat()
        except ValueError:
            return None
    return None


def law_type(title):
    t = title.lower()
    if t.startswith("stjórnarskrá"):
        return "constitution"
    if t.startswith(("tilskipun",)):
        return "ordinance"
    if t.startswith(("forsetaúrskurður", "konungsúrskurður")):
        return "decree"
    if t.startswith(("forsetabréf", "konungsbréf", "opið bréf", "kansellíbréf")):
        return "letter"
    if t.startswith(("alþjóðasamningur", "samningur", "félagsmálasáttmáli")):
        return "treaty"
    if t.startswith("auglýsing"):
        return "notice"
    if t.startswith("alþingissamþykkt"):
        return "resolution"
    return "act"


def split_header(doc):
    """Return (title, dateline, header_html, body_html)."""
    title = ""
    mt = re.search(r"<h2>(.*?)</h2>", doc, flags=re.S)
    if mt:
        title = re.sub(r"<sup[^>]*>.*?</sup>", "", mt.group(1), flags=re.S)
        title = html.unescape(re.sub(r"<[^>]+>", "", title)).replace("\xa0", " ").strip()
    md = re.search(r"</h2>\s*<p[^>]*>\s*<strong>(.*?)</strong>\s*</p>\s*<hr>", doc, flags=re.S)
    dateline = html.unescape(re.sub(r"<[^>]+>", "", md.group(1))).replace("\xa0", " ").strip() if md else ""
    rest = doc[md.end():] if md else doc[mt.end():]
    header = ""
    k = rest.find("<hr>")
    if k >= 0 and "sk.jpg" not in rest[:k] and "hk.jpg" not in rest[:k]:
        header, rest = rest[:k], rest[k + 4:]
    return title, dateline, header, rest


def render_header(header, ctx):
    if not header.strip():
        return ""
    parts = []
    # amendment list
    mb = re.search(r"<em>\s*Breytt með:\s*</em>(.*?)(<br>\s*)?</small>", header, flags=re.S)
    amend = []
    if mb:
        seg = mb.group(1)
        pieces = re.split(r"(?=<a\s)", seg)
        for p in pieces:
            t = clean_md(inline(frag_to_nodes(p), ctx))
            if t:
                amend.append(t)
        header = header[: mb.start()] + "</small>" + header[mb.end():]
    for frag in re.split(r"<br\s*/?>", header):
        t = clean_md(inline(frag_to_nodes(frag), ctx))
        if t:
            parts.append(escape_line_start(t))
    if amend:
        parts.append("*Breytt með:*")
        parts.append("\n".join("- " + a for a in amend))
    return "\n\n".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("repo")
    ap.add_argument("--retrieved", default=datetime.date.today().isoformat())
    args = ap.parse_args()

    def read(name):
        with open(os.path.join(args.src, name), encoding="iso-8859-1") as f:
            return f.read().replace("\r\n", "\n")

    index = read("lagas.nr.html")
    m = re.search(r"Íslensk lög (\d{1,2}\. \w+ \d{4}) \(útgáfa (\w+)\)", index)
    edition_date = parse_date(m.group(1).split()[-1], m.group(1)) if m else None
    edition = m.group(2) if m else ""
    ids = re.findall(r'<li><a href="([^"]+)\.html">', index)
    print(f"edition {edition} ({edition_date}): {len(ids)} laws in force", file=sys.stderr)

    # subject classification from the chapter pages (01.html .. NN.html)
    subjects = {}
    for fn in sorted(os.listdir(args.src)):
        if re.fullmatch(r"\d\d\.html", fn):
            doc = read(fn)
            cur = None
            for mm in re.finditer(r"<h3>(.*?)</h3>|<a href=\"([^\"]+)\.html\">", doc):
                if mm.group(1):
                    cur = html.unescape(re.sub(r"<[^>]+>", "", mm.group(1))).strip()
                elif cur:
                    subjects.setdefault(mm.group(2), cur)

    # first pass: titles and target paths
    meta = {}
    for lid in ids:
        doc = read(lid + ".html")
        title, dateline, header, body = split_header(doc)
        year = lid[:4]
        mnum = re.match(r"^\d{4}\s+(?:nr\.\s*)?(\d+)\s", dateline + " ")
        number = mnum.group(1) if mnum else ""
        suffix = lid.split(".", 1)[1] if "." in lid else ""
        if not re.fullmatch(r"\d{7}(\.\w+)?", lid):
            suffix = lid
        slug_title = re.sub(r"^Lög um\s+", "", title)
        parts = [year] + ([number] if number and number != "0" else []) + ([suffix] if suffix else [])
        name = "-".join(parts + [slugify(slug_title, 70)]) + ".md"
        if law_type(title) == "constitution":
            path = os.path.join("stjornarskra", name)
        else:
            path = os.path.join("log", year, name)
        meta[lid] = dict(title=title, dateline=dateline, header=header, body=body,
                         year=year, number=number, suffix=suffix, path=path)
    paths = {lid: m_["path"] for lid, m_ in meta.items()}
    assert len(set(paths.values())) == len(paths), "path collision"

    for d in ("log", "stjornarskra"):
        p = os.path.join(args.repo, d)
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in files:
                    if f.endswith(".md"):
                        os.remove(os.path.join(root, f))

    for lid in ids:
        m_ = meta[lid]
        ctx = Ctx(paths, m_["path"])
        title = m_["title"]
        date = parse_date(m_["year"], m_["dateline"])
        ident = f"{m_['number']}/{m_['year']}" if m_["number"] and m_["number"] != "0" else lid
        fm = ["---", f"title: {yaml_str(title)}", f"identifier: {yaml_str(ident)}",
              f"lagasafn_id: {yaml_str(lid)}", f"type: {law_type(title)}",
              "jurisdiction: is", "language: is"]
        if date:
            fm.append(f"date: {date}")
        if edition_date:
            fm.append(f"last_amended: {edition_date}  # consolidation date (Lagasafn {edition})")
        fm.append("status: in_force")
        if lid in subjects:
            fm.append(f"subject: {yaml_str(subjects[lid])}")
        fm.append(f'source: "{ALTHINGI}/lagas/{edition}/{lid}.html"')
        fm.append(f"retrieved: {args.retrieved}")
        fm.append("---")
        out = "\n".join(fm) + "\n\n# " + title + "\n\n"
        if m_["dateline"]:
            out += "**" + re.sub(r"\s+", " ", m_["dateline"]) + "**\n\n"
        hdr = render_header(m_["header"], ctx)
        if hdr:
            out += hdr + "\n\n"
        out += render_blocks(convert_body(m_["body"], ctx)) + "\n"
        out = re.sub(r"\n{3,}", "\n\n", out)
        dest = os.path.join(args.repo, m_["path"])
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8", newline="\n") as f:
            f.write(out)
    print(f"wrote {len(ids)} files", file=sys.stderr)


if __name__ == "__main__":
    main()
