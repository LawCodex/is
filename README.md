# LawCodex — Iceland (Ísland)

Icelandic legislation in force — the Constitution (*Stjórnarskrá lýðveldisins Íslands*), every
law in the consolidated statute collection (*Lagasafn*) and the consolidated regulations
(*reglugerðir*) that are published as text in the official regulation collection — as Markdown,
one file per instrument. Texts are in Icelandic, the sole official language.

Part of [LawCodex](https://github.com/LawCodex): the legislation of every country, as plain
Markdown in git.

## Coverage

| Directory | Content | Files |
|---|---|---:|
| `stjornarskra/` | Stjórnarskrá lýðveldisins Íslands, nr. 33/1944 (consolidated) | 1 |
| `log/<year>/` | All other instruments in Lagasafn, edition **158a** (*Íslensk lög 1. október 2026*) | 916 |
| `reglugerdir/<year>/` | Base regulations in force with consolidated text on island.is | 2,916 |
| | **Total** | **3,833** |

`log/` breakdown by type (front matter `type:`): 880 acts (`act`), 12 letters (`letter`: konungsbréf, forsetabréf, opin bréf), 9 decrees (`decree`: forsetaúrskurðir, konungsúrskurður), 6 treaties (`treaty`), 5 ordinances (`ordinance`: tilskipanir), 3 notices (`notice`: auglýsingar), 1 resolution (`resolution`: alþingissamþykkt).
Besides ordinary acts (*lög*), Lagasafn keeps a few older instruments still in force — royal
ordinances (*tilskipanir*), royal and presidential letters and decrees (*konungsbréf,
forsetabréf, forsetaúrskurðir*), the medieval *Jónsbók* (1281; the provisions still in force, in four files) and
*Kristinréttur Árna biskups* (1275), and some treaties enacted as law (UN human-rights covenants,
European Social Charter...). All of them are included.

### Not covered

- **Repealed laws.** The Lagasafn zip contains ~830 stub pages for repealed laws (title + "Felld
  úr gildi"); they are skipped. Earlier Lagasafn editions are available from
  the same source but are not converted.
- **Amending acts** as such: Lagasafn integrates them into the consolidated laws; the
  as-enacted texts (*Stjórnartíðindi* A-deild) are not included.
- **Regulations without consolidated text**: of the 6,949 base regulations in force listed in
  the island.is collection, 4,032 (58%) are served by island.is only as a redirect to the legacy site
  www.reglugerd.is, which offers just a Word file of the *original* (unconsolidated) text. Those
  are not included, rather than presenting outdated text as current. One further entry
  (`162V/1998`) has a malformed number that the API rejects.
- **Amending regulations** (*breytingareglugerðir*, 7,699 in force) — their content is merged
  into the consolidated base regulations.
- Other secondary/administrative instruments (*auglýsingar, gjaldskrár, samþykktir* of
  municipalities, etc. in B-deild Stjórnartíðinda), court decisions, preparatory works.
- EU/EEA acts that Lagasafn publishes as linked PDFs (`.../lagasafn/pdf/158a/i3....pdf`) are kept
  as links, not converted.

## Sources and licence

- **Laws:** Alþingi, *Lagasafn* — whole collection as one zip of HTML files per edition:
  <https://www.althingi.is/lagasafn/zip-skra-af-lagasafni/> (file
  `https://www.althingi.is/lagasafn/zip/158a/allt.zip`). Online version:
  `https://www.althingi.is/lagas/158a/<id>.html` (the `source:` in front matter).
- **Regulations:** *Reglugerðasafn* on Ísland.is <https://island.is/reglugerdir>, retrieved
  through island.is's public GraphQL endpoint (`getRegulations`, `getRegulation` with
  `viewType: current`) — the same data the website renders. (The backend host
  `api.reglugerd.is` disallows all crawling in its robots.txt and was therefore not used.)
- **Copyright:** Under Article 9 of the Icelandic Copyright Act (*Höfundalög nr. 73/1972*), laws,
  administrative regulations, court judgments and similar official documents are not protected by
  copyright. The Markdown conversion here is offered under the same terms (public domain / CC0).
- This is **not** an official publication. Lagasafn itself is a consolidation prepared by
  Alþingi; legally authoritative are the texts published in *Stjórnartíðindi* (A-deild for laws,
  B-deild for regulations). Ísland.is notes that if the regulation collection and B-deild
  differ, B-deild prevails.

Retrieved 2026-10-12.

## File format

```
stjornarskra/1944-33-stjornarskra-lydveldisins-islands.md
log/1940/1940-19-almenn-hegningarlog.md
log/1281/1281-400-jonsbok.md
reglugerdir/2020/2020-100-rafraena-audkenningu-og-traustthjonustu-fyrir-rafraen-vidskipti.md
```

File names are `<year>-<number>-<slug>.md`, i.e. the official citation *nr. 19/1940* plus a slug
of the title (leading "Lög um" / "Reglugerð um" dropped; þ→th, ð→d, æ→ae, ö→o, accents
stripped). Instruments without a number use Lagasafn's internal id instead (e.g. Jónsbók chapters
`1281-400`). Directories are sharded by year (all well under 1,000 entries).

Front matter: `title`, `identifier` (`19/1940`), `lagasafn_id` (laws; Alþingi's id such as
`1940019`), `type`, `date` (date of the act / signature), `last_amended` (laws: the Lagasafn
consolidation date 2026-10-01; regulations: date of the last amendment incorporated),
`status: in_force`, `subject` (laws: Lagasafn subject chapter, e.g. `1.a. Stjórnskipunarlög`),
`ministry` and `law_chapters` (regulations), `source`, `retrieved`.

Laws keep Lagasafn's editorial apparatus, which is part of the consolidated text:

- a header with links to the parliamentary record (*Ferill málsins*, *Frumvarp*), entry into force
  (*Tók gildi*) and the list of amending acts (*Breytt með*);
- square brackets `[ ... ]` around amended text with a superscript note number (`<sup>1)</sup>`);
  the notes themselves (amending act and article) follow the paragraph as `> <sup>1)</sup>...`
  lines;
- `…` marks text that was repealed or omitted (spent amending provisions), linked to the
  original act where Lagasafn links it.

Headings: parts (*hluti*), chapters (*kafli*), sub-headings and articles (*gr.*) map to Markdown
heading levels in that order. Links between laws point to the corresponding file in this
repository when the target is in force, otherwise to althingi.is.

## Regenerating

```sh
pip install -r scripts/requirements.txt   # requests, beautifulsoup4, markdownify
python3 scripts/is_fetch.py ../_raw/is              # newest Lagasafn zip -> ../_raw/is/html (Crawl-delay 5 s)
python3 scripts/is_convert.py ../_raw/is/html .      # -> stjornarskra/, log/
python3 scripts/is_reg_fetch.py ../_raw/is           # regulations via island.is GraphQL (≤4 workers)
python3 scripts/is_reg_convert.py ../_raw/is .       # -> reglugerdir/
```

Lagasafn is republished several times a year (editions `157a`, `157b`, ... `158a`); pass
`--edition` to `is_fetch.py` to pick a specific one.
