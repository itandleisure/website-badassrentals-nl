#!/usr/bin/env python3
"""
Dagelijkse positiecontrole in Google (via DataForSEO) voor badassrentals.nl.

    python tools/rank_check.py              # alle zoekwoorden, schrijft CSV + JSON
    python tools/rank_check.py --test       # alleen het eerste zoekwoord (kosten check)

- Zoekt per zoekwoord de positie van badassrentals.nl in de eerste 100 mobiele resultaten
  (Google Nederland, Nederlandstalig). Mobiel, omdat ~85% van de bezoekers mobiel zoekt.
- Voegt de uitkomst toe aan een CSV (voor Excel) en schrijft de metingen van vandaag als JSON,
  zodat ze in het dashboard gezet kunnen worden.
- Inloggegevens komen uit de Windows-gebruikersvariabelen DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD.
  Ze worden nooit getoond of opgeslagen.
"""
import base64
import csv
import json
import os
import sys
import urllib.request
from datetime import date
from pathlib import Path

DOMEIN = "badassrentals.nl"
ZOEKWOORDEN = [
    "e chopper giethoorn",
    "e chopper huren giethoorn",
    "e chopper huren",
    "scooter huren giethoorn",
    "fatbike huren",
    "fatbike huren giethoorn",
    "fiets huren giethoorn",
    "fietsverhuur giethoorn",
    "bedrijfsuitje giethoorn",
    "groepsuitje giethoorn",
    "vrijgezellenfeest giethoorn",
    "sloep huren giethoorn",
    "wat te doen in giethoorn",
    "arrangement giethoorn",
    "badass rentals",
]
MAP = Path(r"C:\Websites\badassrentals-posities")
CSV_BESTAND = MAP / "posities.csv"
API = "https://api.dataforseo.com/v3/serp/google/organic/live/regular"


def gebruikersvariabele(naam):
    waarde = os.environ.get(naam)
    if waarde:
        return waarde
    try:  # Windows: variabele is gezet na het starten van dit proces
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return winreg.QueryValueEx(k, naam)[0]
    except Exception:
        return None


MIN_RESULTATEN = 30  # minder organische resultaten = onvolledige pagina van Google: opnieuw opvragen
POGINGEN = 3


def zoek(zoekwoord, auth):
    body = json.dumps([{
        "keyword": zoekwoord, "location_code": 2528, "language_code": "nl",
        "device": "mobile", "depth": 100,
    }]).encode()
    kosten = 0.0
    for poging in range(POGINGEN):
        req = urllib.request.Request(API, data=body, method="POST", headers={
            "Authorization": "Basic " + auth, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=90) as r:
            d = json.load(r)
        kosten += d.get("cost", 0) or 0
        taak = d["tasks"][0]
        if taak["status_code"] != 20000:
            raise RuntimeError(f"{zoekwoord}: {taak['status_message']}")
        items = [i for i in (taak["result"][0].get("items") or []) if i.get("type") == "organic"]
        if len(items) >= MIN_RESULTATEN:
            break
    d["cost"] = kosten
    top1 = items[0]["domain"] if items else ""
    eigen = next((i for i in items if DOMEIN in (i.get("domain") or "")), None)
    return {
        "positie": eigen["rank_group"] if eigen else None,
        "url": (eigen["url"].replace("https://" + DOMEIN, "") or "/") if eigen else "",
        "top1": top1,
        "kosten": d.get("cost", 0),
    }


def main():
    login, wachtwoord = gebruikersvariabele("DATAFORSEO_LOGIN"), gebruikersvariabele("DATAFORSEO_PASSWORD")
    if not login or not wachtwoord:
        sys.exit("DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD niet ingesteld")
    auth = base64.b64encode(f"{login}:{wachtwoord}".encode()).decode()
    lijst = ZOEKWOORDEN[:1] if "--test" in sys.argv else ZOEKWOORDEN
    vandaag = date.today().isoformat()
    metingen, kosten = [], 0.0
    for z in lijst:
        r = zoek(z, auth)
        kosten += r.pop("kosten") or 0
        metingen.append({"datum": vandaag, "zoekwoord": z, **r})
        print(f"{str(r['positie'] or '-'):>4}  {z:32s} {r['url']:40s} nr.1: {r['top1']}")

    MAP.mkdir(parents=True, exist_ok=True)
    nieuw = not CSV_BESTAND.exists()
    with open(CSV_BESTAND, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        if nieuw:
            w.writerow(["datum", "zoekwoord", "positie", "pagina", "nummer 1 in Google"])
        for m in metingen:
            w.writerow([m["datum"], m["zoekwoord"], m["positie"] or "", m["url"], m["top1"]])
    uit = MAP / f"metingen-{vandaag}.json"
    uit.write_text(json.dumps(metingen, ensure_ascii=False, indent=1), encoding="utf-8")
    # één document per dag voor het dashboard (collectie "dagen", doc-id = datum)
    dag = {"datum": vandaag, "metingen": [
        {k: m[k] for k in ("zoekwoord", "positie", "url", "top1")} for m in metingen]}
    (MAP / f"dag-{vandaag}.json").write_text(json.dumps(dag, ensure_ascii=False), encoding="utf-8")
    print(f"\n{len(metingen)} zoekwoorden, kosten ${kosten:.4f}. CSV: {CSV_BESTAND}  JSON: {uit}")


if __name__ == "__main__":
    main()
