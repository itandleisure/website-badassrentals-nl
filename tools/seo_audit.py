#!/usr/bin/env python3
"""
SEO-controle van de gebouwde site (public/).

    python tools/seo_audit.py

Controleert: sitemap vs. indexeerbare pagina's, dubbele titels/descriptions, H1's, alt-teksten,
canonicals, lengtes en het aantal inkomende interne links per pagina (buiten menu en footer).
"""
import collections
import html
import glob
import os
import re
from pathlib import Path

PUB = Path(__file__).resolve().parent.parent / "public"
SITE = "https://badassrentals.nl"


def main():
    os.chdir(PUB)
    pages = {}
    for f in glob.glob("**/index.html", recursive=True):
        s = open(f, encoding="utf-8").read()
        path = "/" + Path(f).parent.as_posix().strip(".") + "/"
        path = path.replace("//", "/")
        main_html = s.split('<main id="main">')[1].split("</main>")[0]
        pages[path] = dict(
            title=html.unescape(re.search(r"<title>(.*?)</title>", s).group(1)),
            desc=html.unescape(re.search(r'name="description" content="(.*?)"', s).group(1)),
            canon=re.search(r'rel="canonical" href="(.*?)"', s).group(1),
            noindex="noindex" in re.search(r'name="robots" content="(.*?)"', s).group(1),
            h1=len(re.findall(r"<h1", s)),
            noalt=len(re.findall(r"<img(?![^>]*alt=)", s)),
            emptyalt=len(re.findall(r'<img[^>]*alt=""', main_html)),
            links=set(re.findall(r'href="(/[^"#?]*)', main_html)),
            size=len(s.encode()),
        )

    idx = {p: d for p, d in pages.items() if not d["noindex"]}
    sm = set(re.findall(r"<loc>" + re.escape(SITE) + r"(.*?)</loc>", open("sitemap.xml", encoding="utf-8").read()))
    problems = 0

    def report(label, items):
        nonlocal problems
        print(f"{'OK  ' if not items else 'LET OP'} {label}: {items if items else '-'}")
        problems += bool(items)

    print(f"Indexeerbare pagina's: {len(idx)}, in sitemap: {len(sm)}")
    report("verschil sitemap/indexeerbaar", sorted(set(idx) ^ sm))
    for k in ("title", "desc"):
        c = collections.Counter(d[k] for d in idx.values())
        report(f"dubbele {k}", [v for v, n in c.items() if n > 1])
    report("aantal H1 niet 1", [p for p, d in pages.items() if d["h1"] != 1])
    report("img zonder alt", [p for p, d in pages.items() if d["noalt"]])
    report("canonical wijkt af", [p for p, d in idx.items() if d["canon"] != SITE + p])
    report("title > 62 of description > 160 tekens",
           [(p, len(d["title"]), len(d["desc"])) for p, d in idx.items() if len(d["title"]) > 62 or len(d["desc"]) > 160])
    report("interne link zonder slash", sorted({l for d in pages.values() for l in d["links"]
                                               if not l.endswith("/") and "." not in l.rsplit("/", 1)[-1]}))

    inbound = collections.Counter()
    for p, d in pages.items():
        for link in d["links"]:
            if link != p:
                inbound[link] += 1
    print("\nInkomende links vanuit de content (menu en footer niet meegeteld):")
    for p in sorted(idx, key=lambda x: inbound[x]):
        print(f"  {inbound[p]:3d}  {p}")
    print(f"\nGrootste HTML-pagina: {max((d['size'], p) for p, d in pages.items())}")
    print(f"\n{problems} aandachtspunt(en).")


if __name__ == "__main__":
    main()
