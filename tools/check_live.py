#!/usr/bin/env python3
"""
Controle na livegang: komen alle oude URL's (tools/old-urls.txt) op een werkende pagina uit?

    python tools/check_live.py                       # test https://badassrentals.nl
    python tools/check_live.py https://test.example  # andere omgeving

Volgt redirects en meldt elke URL die niet eindigt op een 200 (xmlrpc.php hoort 410 te geven).
"""
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://badassrentals.nl").rstrip("/")
PATHS = (Path(__file__).parent / "old-urls.txt").read_text().split()
EXPECTED = {"/xmlrpc.php": 410}


def check(path):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "badassrentals-check"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.geturl().replace(BASE, "")
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
