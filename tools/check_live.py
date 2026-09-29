#!/usr/bin/env python3
"""
Controle na livegang: komen alle oude URL's (tools/old-urls.txt) op een werkende pagina uit?

    python tools/check_live.py                       # test https://badassrentals.nl
    python tools/check_live.py https://test.example  # andere omgeving

Volgt redirects (ook de doorverwijspagina's van GitHub Pages) en meldt elke URL die niet eindigt
op een werkende pagina. xmlrpc.php (WordPress) hoort een 404 te geven.
"""
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://badassrentals.nl").rstrip("/")
PATHS = (Path(__file__).parent / "old-urls.txt").read_text().split()
EXPECTED = {"/xmlrpc.php": 404}


def check(path, depth=0):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "badassrentals-check"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read(4000).decode("utf-8", "replace")
            final = r.geturl().replace(BASE, "")
            m = re.search(r'http-equiv="refresh" content="0; url=([^"]+)"', body)
            if m and depth < 3:  # doorverwijspagina: bestemming ook controleren
                return check(m.group(1), depth + 1)
            return r.status, final
    except urllib.error.HTTPError as e:
        return e.code, path
    except Exception as e:  # netwerkfout
        return str(e), path


bad = 0
for p in PATHS:
    status, final = check(p)
    ok = status == EXPECTED.get(p, 200)
    bad += not ok
    if not ok or final != p:
        print(f"{'OK  ' if ok else 'FOUT'} {status}  {p}" + (f"  ->  {final}" if final != p else ""))
print(f"\n{len(PATHS)} URL's getest, {bad} fout(en).")
sys.exit(1 if bad else 0)
