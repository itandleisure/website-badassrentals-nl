#!/usr/bin/env python3
"""
Eindcontrole van de live site (https://badassrentals.nl).

    python tools/live_audit.py

Haalt alle pagina's uit de sitemap op en controleert per pagina: status, titel, description,
canonical, H1, JSON-LD, en of alle interne links, afbeeldingen en boekingslinks werken.
"""
import html
import json
import re
import sys
import urllib.error
import urllib.request

SITE = "https://badassrentals.nl"
UA = {"User-Agent": "badassrentals-audit"}
cache = {}


def get(url, body=True):
    if url in cache and not body:
        return cache[url]
    req = urllib.request.Request(url, headers=UA, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            data = r.read().decode("utf-8", "replace") if body else ""
            res = (r.status, r.geturl(), data)
    except urllib.error.HTTPError as e:
        res = (e.code, url, "")
    except Exception as e:
        res = (str(e)[:60], url, "")
    cache[url] = res
    return res


problems = []


def check(ok, msg):
    if not ok:
        problems.append(msg)


# 1. Techniek
st, final, _ = get("http://www.badassrentals.nl/", body=False)
check(final.startswith("https://badassrentals.nl"), f"www/http stuurt niet door naar https://badassrentals.nl ({final})")
st, _, robots = get(SITE + "/robots.txt")
check(st == 200 and "Sitemap: https://badassrentals.nl/sitemap.xml" in robots, "robots.txt mist of verwijst niet naar de sitemap")
st, _, sm = get(SITE + "/sitemap.xml")
urls = re.findall(r"<loc>(.*?)</loc>", sm)
check(st == 200 and urls, "sitemap.xml niet bereikbaar of leeg")
st, _, _ = get(SITE + "/deze-pagina-bestaat-niet/", body=False)
check(st == 404, f"onbekende pagina geeft geen 404 maar {st}")
print(f"Techniek gecontroleerd. Sitemap: {len(urls)} pagina's.")

# 2. Alle pagina's
seen_titles, seen_desc = {}, {}
links_internal, links_external, images = set(), set(), set()
for u in urls:
    st, final, page = get(u)
    path = u.replace(SITE, "")
    if st != 200:
        problems.append(f"{path}: status {st}")
        continue
    t = html.unescape((re.search(r"<title>(.*?)</title>", page) or [None, ""])[1])
    d = html.unescape((re.search(r'name="description" content="(.*?)"', page) or [None, ""])[1])
    c = (re.search(r'rel="canonical" href="(.*?)"', page) or [None, ""])[1]
    check(t and len(t) <= 62, f"{path}: titel ontbreekt of te lang ({len(t)})")
    check(d and 50 <= len(d) <= 160, f"{path}: description ontbreekt of verkeerde lengte ({len(d)})")
    check(c == u, f"{path}: canonical {c}")
    check(len(re.findall(r"<h1", page)) == 1, f"{path}: aantal H1 is niet 1")
    check('name="robots" content="index' in page, f"{path}: staat niet op index")
    check('og:image' in page and 'name="viewport"' in page, f"{path}: og:image of viewport ontbreekt")
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S):
        try:
            json.loads(block)
        except Exception:
            problems.append(f"{path}: ongeldige JSON-LD")
    seen_titles.setdefault(t, []).append(path)
    seen_desc.setdefault(d, []).append(path)
    for h in re.findall(r'href="([^"#]+)', page):
        if h.startswith("/") and not h.startswith("//"):
            links_internal.add(h)
        elif "verhuur.badassrentals.nl" in h or "script.google.com" in h:
            links_external.add(h)
    for s in re.findall(r'(?:src|srcset)="([^"]+)"', page):
        for part in s.split(","):
            p = part.strip().split(" ")[0]
            if p.startswith("/"):
                images.add(p)
for t, ps in seen_titles.items():
    check(len(ps) == 1, f"dubbele titel op {ps}")
for d, ps in seen_desc.items():
    check(len(ps) == 1, f"dubbele description op {ps}")
print(f"Pagina's gecontroleerd. Interne links: {len(links_internal)}, bestanden: {len(images)}, externe links: {len(links_external)}.")

# 3. Interne links, bestanden, boekingslinks
for h in sorted(links_internal):
    st, _, _ = get(SITE + h, body=False)
    check(st == 200, f"interne link {h} geeft {st}")
for p in sorted(images):
    st, _, _ = get(SITE + p, body=False)
    check(st == 200, f"bestand {p} geeft {st}")
for h in sorted(links_external):
    st, _, _ = get(html.unescape(h), body=False)
    check(st in (200, 301, 302), f"externe link {h} geeft {st}")

print()
if problems:
    print(f"{len(problems)} probleem/problemen:")
    for p in problems:
        print("  -", p)
else:
    print("Geen problemen gevonden.")
sys.exit(1 if problems else 0)
