#!/usr/bin/env python3
"""
Bouwt de statische website van Badass Rentals naar de map public/.

    python build.py            # bouwen
    python build.py --serve    # bouwen en lokaal bekijken op http://localhost:8000

Structuur:
  src/pages/*.html     pagina's (front matter + HTML). index.html = homepage,
                       overige bestanden worden /<bestandsnaam>/index.html
  src/photos/*.jpg     bronfoto's; worden automatisch omgezet naar WebP (meerdere breedtes)
  src/assets/          css, js, fonts, logo, pdf's -> /assets/
  src/root/            bestanden voor de webroot (.htaccess, robots.txt, verzenden.php ...)

Vereist: Python 3.9+ en Pillow (pip install pillow).
"""
import html
import json
import re
import shlex
import shutil
import sys
from datetime import date
from pathlib import Path

from PIL import Image, ImageOps


ROOT = Path(__file__).parent
SRC = ROOT / "src"
OUT = ROOT / "public"
SITE = "https://badassrentals.nl"

BUSINESS = {
    "name": "Badass Rentals",
    "phone": "+31850047700",
    "phone_display": "085 004 7700",
    "email": "info@badassrentals.nl",
    "street": "Beulakerweg 167",
    "postal": "8355 AG",
    "city": "Giethoorn",
    "location": "Restaurant Hollands Venetië",
    "facebook": "https://www.facebook.com/badassrentals",
    "instagram": "https://www.instagram.com/badassrentals.nl/",
    "maps": "https://www.google.com/maps/search/?api=1&query=Hollands+Veneti%C3%AB+Beulakerweg+167+Giethoorn",
}

# Web-app-URL van het Google Apps Script (tools/google-formulier/Code.gs), eindigt op /exec.
# Gevuld: formulieren gaan naar Google Sheets + e-mail, met verzenden.php als reserveroute.
# Leeg: formulieren gaan alleen via verzenden.php.
GOOGLE_FORM_URL = "https://script.google.com/macros/s/AKfycbyy8taGpWzmWdXBV3V5vTizZnZ5_H7fKKpLoQ_zpTNB_PTwJNP1NzUFsLWYy-Wiee66/exec"

# Links naar het boekingssysteem. Deze URL's niet wijzigen zonder de boekingsomgeving te controleren.
BOOK = {
    "root": "https://verhuur.badassrentals.nl/",
    "echopper": "https://verhuur.badassrentals.nl/product/E-chopper",
    "fatbike": "https://verhuur.badassrentals.nl/product/fat-bike",
    "ontdek": "https://verhuur.badassrentals.nl/product/ontdek-weerribben",
    "evening": "https://verhuur.badassrentals.nl/product/evening-chopper-tour",
    "cityescape": "https://verhuur.badassrentals.nl/product/city-escape-giethoorn",
}

# Het boekingssysteem heeft ook een Engelse (/en/) en Duitse (/de/) versie
BOOK_L = {"nl": BOOK}
for _l in ("en", "de"):
    BOOK_L[_l] = {k: v.replace("verhuur.badassrentals.nl/", f"verhuur.badassrentals.nl/{_l}/") for k, v in BOOK.items()}
BOOK_EN = BOOK_L["en"]
LANGS = ("nl", "en", "de")

NAV = [
    ("/e-chopper-huren-giethoorn/", "E-chopper"),
    ("/fat-bike-huren-in-giethoorn/", "Fatbike"),
    ("/arrangementen/", "Arrangementen"),
    ("/teamuitje-met-echopper/", "Bedrijfsuitjes"),
    ("/veelgestelde-vragen/", "Vragen"),
    ("/kom-in-contact/", "Contact"),
]
NAV_EN = [
    ("/en/e-chopper-rental-giethoorn/", "E-chopper"),
    ("/en/fat-bike-rental-giethoorn/", "Fat bike"),
    ("/en/tours/", "Tours"),
    ("/en/things-to-do-in-giethoorn/", "Things to do"),
    ("/en/faq/", "FAQ & contact"),
]
NAV_DE = [
    ("/de/e-chopper-mieten-giethoorn/", "E-Chopper"),
    ("/de/fatbike-mieten-giethoorn/", "Fatbike"),
    ("/de/touren/", "Touren"),
    ("/de/sehenswuerdigkeiten-giethoorn/", "Sehenswürdigkeiten"),
    ("/de/faq/", "FAQ & Kontakt"),
]
NAV_L = {"nl": NAV, "en": NAV_EN, "de": NAV_DE}

# Anderstalige pagina's staan in src/pages/<taal>/ en noemen hun Nederlandse tegenhanger in 'alternate:'.
# Tijdens de build gevuld: pad -> {"nl": pad, "en": pad, "de": pad} (voor hreflang en de taalwissel)
ALTERNATES = {}

IMG_WIDTHS = (480, 960, 1600, 2000)
PHOTO_DIMS = {}  # naam -> (breedte, hoogte, [beschikbare breedtes])


# --------------------------------------------------------------------------- afbeeldingen
def build_images():
    out = OUT / "assets" / "img"
    out.mkdir(parents=True, exist_ok=True)
    for src in sorted((SRC / "photos").glob("*.jpg")):
        name = src.stem
        im = None
        with Image.open(src) as probe:
            w, h = probe.size
        widths = sorted({min(x, w) for x in IMG_WIDTHS})
        PHOTO_DIMS[name] = (w, h, widths)
        targets = [(out / f"{name}-{x}.webp", x) for x in widths]
        og = out / f"{name}-og.jpg"
        if all(t.exists() and t.stat().st_mtime >= src.stat().st_mtime for t, _ in targets) and og.exists():
            continue
        im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
        for target, x in targets:
            r = im.resize((x, round(h * x / w)), Image.LANCZOS) if x != w else im
            q = 74 if x <= 960 else 66 if x <= 1600 else 60  # grote formaten iets sterker comprimeren
            r.save(target, "WEBP", quality=q, method=6)  # geen EXIF -> geen GPS-data online
        ImageOps.fit(im, (1200, 630), Image.LANCZOS).save(og, "JPEG", quality=80, optimize=True, progressive=True)
        print("  foto:", name)
    # Verouderde varianten (andere breedtes of verwijderde foto's) opruimen
    expected = {f"{n}-{x}.webp" for n, (_, _, ws) in PHOTO_DIMS.items() for x in ws} | {f"{n}-og.jpg" for n in PHOTO_DIMS}
    for f in out.iterdir():
        if f.name not in expected:
            f.unlink()


def img_tag(name, alt, sizes="100vw", cls="", eager=False):
    if name not in PHOTO_DIMS:
        raise SystemExit(f"Onbekende foto in pagina: {name} (bestaat src/photos/{name}.jpg?)")
    w, h, widths = PHOTO_DIMS[name]
    srcset = ", ".join(f"/assets/img/{name}-{x}.webp {x}w" for x in widths)
    fallback = f"/assets/img/{name}-{widths[min(1, len(widths) - 1)]}.webp"
    attrs = [
        f'src="{fallback}"', f'srcset="{srcset}"', f'sizes="{sizes}"',
        f'width="{w}"', f'height="{h}"', f'alt="{html.escape(alt)}"',
        'loading="eager" fetchpriority="high"' if eager else 'loading="lazy"',
        'decoding="async"',
    ]
    if cls:
        attrs.append(f'class="{cls}"')
    return "<img " + " ".join(attrs) + ">"


# --------------------------------------------------------------------------- shortcodes
def render_shortcodes(body, page):
    lang = page.get("lang", "nl")
    for k, v in BOOK_L[lang].items():
        body = body.replace("{{book.%s}}" % k, v)
    for k, v in BUSINESS.items():
        body = body.replace("{{biz.%s}}" % k, v)

    def img(m):
        parts = shlex.split(m.group(1))
        name, alt = parts[0], parts[1]
        opts = {"sizes": "100vw", "class": "", "eager": False}
        for p in parts[2:]:
            if p == "eager":
                opts["eager"] = True
            elif "=" in p:
                k, v = p.split("=", 1)
                opts[k] = v
        return img_tag(name, alt, opts["sizes"], opts["class"], opts["eager"])

    body = re.sub(r"\{%\s*img\s+(.+?)\s*%\}", img, body)

    def faq(m):
        items = re.findall(r"^Q:\s*(.+?)\n(?:A:\s*)(.+?)(?=^Q:|\Z)", m.group(1).strip() + "\n", re.S | re.M)
        out = ['<div class="faq">']
        for q, a in items:
            q, a = q.strip(), a.strip()
            anchor = ""
            m_id = re.match(r"\{#([\w-]+)\}\s*(.*)", q)  # optioneel anker: Q: {#naam} Vraag?
            if m_id:
                anchor, q = f' id="{m_id.group(1)}"', m_id.group(2)
            page.setdefault("_faq", []).append((q, a))
            out.append(f"<details{anchor}><summary>{q}</summary><div class=\"faq-a\">{a}</div></details>")
        out.append("</div>")
        return "\n".join(out)

    body = re.sub(r"\{%\s*faq\s*%\}(.*?)\{%\s*endfaq\s*%\}", faq, body, flags=re.S)

    body = re.sub(r"\{%\s*reviews\s*%\}", lambda m: reviews_html(), body)
    body = re.sub(r"\{%\s*cta\s*%\}", lambda m: cta_html(lang), body)
    body = re.sub(r"\{%\s*usps\s*%\}", lambda m: usps_html(lang), body)
    body = re.sub(r"\{%\s*news\s*(\d*)\s*%\}", lambda m: news_html(int(m.group(1)) if m.group(1) else None), body)
    return body


# --------------------------------------------------------------------------- herbruikbare blokken
# 5-sterren Google-reviews (overgenomen van de oude site / Google Maps). Letterlijke tekst, alleen spaties opgeschoond.
GOOGLE_REVIEWS_URL = "https://www.google.com/maps/search/?api=1&query=Badass+Rentals+Giethoorn"
REVIEWS = [
    ("Anthonie", "Prachtige route in de Weerribben gereden met de E-choppers van Badass Rentals. Vriendelijk geholpen, geen druk om op tijd terug te zijn o.i.d., oplaadsnoer voor mijn telefoon gratis kunnen gebruiken op de E-chopper. Ik beveel dit bedrijf aan en zou er zeker terugkomen!"),
    ("Nancy Ook", "Een E-chopper gehuurd in Giethoorn en de Badass toer gevolgd op route.nl. Ontzettend leuk om te cruisen en door een prachtig dorpje gesjeest (Belt-Schutsloot) dat op mij een onuitwisbare indruk heeft gemaakt! Een E-chopper huren ga ik zeker nog eens doen. Was hartstikke leuk!!"),
    ("E. J. Ilgun", "Iedereen uit onze groep kon een aantal voertuigen proberen en zo de beste keuze maken. Geen gedoe en daarna een mooie route van ruim een uur door en om Giethoorn gereden op choppers, scooters en fat bike. Deze laatste is een aanrader!"),
    ("Arjen Paul", "Heerlijk zondagmiddag getoerd, goed weer en goed materiaal! Ik woon al heel wat jaar in de buurt, maar op een elektrische stille chopper de natuur verkennen is echt een aanrader. En na afloop heerlijk eten in Blokzijl! Top geregeld."),
    ("Sophie Markus", "Mega mega vriendelijke service, zetten absoluut de extra stap in service. Zeker een aanrader en super bedankt!"),
    ("Rianne Niemeijer", "Top! Vriendelijke mensen en echt genoten van onze tour!"),
    ("Marjolein Knoll-Veld", "Super leuke rit gemaakt. Vriendelijk en zeer behulpzaam personeel."),
    ("Henk Hetebrij", "Erg leuke ervaring, goed geregeld."),
    ("Rianne de Vries", "Hele leuke ervaring om te doen, vriendelijk personeel! Aanrader!"),
]


def reviews_html():
    cards = "".join(
        f'<figure class="review"><div class="stars" aria-label="5 sterren">★★★★★</div>'
        f"<blockquote>{html.escape(t)}</blockquote><figcaption>{html.escape(n)}"
        f'<span class="review-meta">Review op Google</span></figcaption></figure>'
        for n, t in REVIEWS
    )
    return (f'<div class="reviews">{cards}</div>'
            f'<p class="reviews-more"><a class="link-arrow" href="{GOOGLE_REVIEWS_URL}" rel="noopener">Bekijk alle reviews op Google</a></p>')


def usps_html(lang="nl"):
    items = {"de": [
        ("30+ E-Chopper & 15 Fatbikes", "Für Paare, Familien und Gruppen jeder Größe."),
        ("Panne? Wir kommen zu Ihnen", "Wir bringen sofort Ersatz, damit Sie schnell weiterfahren können."),
        ("Die schönsten Routen", "GPS-Routen durch Giethoorn und den Nationalpark Weerribben-Wieden."),
        ("Bestens gewartet", "Alle E-Chopper und Fatbikes werden regelmäßig geprüft und gewartet."),
    ], "en": [
        ("30+ e-choppers & 15 fat bikes", "For couples, families and groups of any size."),
        ("Breakdown? We come to you", "We bring a replacement right away, so you can keep going."),
        ("The best routes", "GPS routes through Giethoorn and Weerribben-Wieden National Park."),
        ("Well maintained", "Every e-chopper and fat bike is checked and serviced regularly."),
    ], "nl": [
        ("30+ e-choppers & 15 fatbikes", "Voor kleine en grote groepen; boven 30 personen met een wisselprogramma."),
        ("Pech onderweg? Wij komen eraan", "We regelen direct vervangend vervoer, zodat je snel weer verder kunt."),
        ("Mooiste routes", "GPS-routes door Giethoorn en Nationaal Park Weerribben-Wieden."),
        ("Goed onderhouden", "We controleren en onderhouden alle tweewielers periodiek."),
    ]}[lang]
    return '<ul class="usps">' + "".join(f"<li><strong>{a}</strong><span>{b}</span></li>" for a, b in items) + "</ul>"


def cta_html(lang="nl"):
    if lang == "de":
        return f"""<section class="cta-band">
  <div class="wrap cta-band-inner">
    <div>
      <h2>Bereit zum Cruisen?</h2>
      <p>Wählen Sie Datum und Uhrzeit und buchen Sie direkt online.</p>
    </div>
    <div class="btn-row">
      <a class="btn btn-accent" href="{BOOK_L['de']['echopper']}">E-Chopper buchen</a>
      <a class="btn btn-ghost-light" href="{BOOK_L['de']['fatbike']}">Fatbike buchen</a>
    </div>
  </div>
</section>"""
    if lang == "en":
        return f"""<section class="cta-band">
  <div class="wrap cta-band-inner">
    <div>
      <h2>Ready to ride?</h2>
      <p>Pick your date and time and book online.</p>
    </div>
    <div class="btn-row">
      <a class="btn btn-accent" href="{BOOK_EN['echopper']}">Book an e-chopper</a>
      <a class="btn btn-ghost-light" href="{BOOK_EN['fatbike']}">Book a fat bike</a>
    </div>
  </div>
</section>"""
    return f"""<section class="cta-band">
  <div class="wrap cta-band-inner">
    <div>
      <h2>Klaar om te cruisen?</h2>
      <p>Kies je datum en tijd en reserveer direct online.</p>
    </div>
    <div class="btn-row">
      <a class="btn btn-accent" href="{BOOK['echopper']}">Boek een e-chopper</a>
      <a class="btn btn-ghost-light" href="{BOOK['fatbike']}">Boek een fatbike</a>
    </div>
  </div>
</section>"""


NEWS = []  # gevuld tijdens build: (url, titel, beschrijving, foto, datum, onderwerp)

# Per onderwerp de belangrijkste pagina om naartoe te linken vanuit een artikel
TOPIC_LINKS = {
    "omgeving": ("/e-chopper-huren-giethoorn/", "e-chopper huren in Giethoorn", "/fat-bike-huren-in-giethoorn/", "een fatbike huren"),
    "groepen": ("/teamuitje-met-echopper/", "bedrijfsuitjes in Giethoorn", "/arrangementen/", "onze arrangementen"),
    "beleving": ("/e-chopper-huren-giethoorn/", "e-chopper huren in Giethoorn", "/arrangementen/", "onze arrangementen"),
}


def card_html(url, title, desc, photo):
    return (f'<a class="card" href="{url}">{img_tag(photo, "", "(max-width: 700px) 100vw, 33vw", "card-img")}'
            f'<div class="card-body"><h3>{html.escape(title)}</h3><p>{html.escape(desc)}</p>'
            f'<span class="link-arrow">Lees verder</span></div></a>')


def news_html(limit=None):
    items = sorted(NEWS, key=lambda n: n[4], reverse=True)[:limit]
    return '<div class="cards">' + "".join(card_html(u, t, d, p) for u, t, d, p, _, _ in items) + "</div>"


def related_html(path, topic):
    """'Lees ook' onder een artikel: eerst artikelen met hetzelfde onderwerp, aangevuld met de nieuwste."""
    # Binnen het onderwerp rouleren (de volgende 3 in de lijst), zodat elk artikel links krijgt
    same = sorted((n for n in NEWS if n[5] == topic), key=lambda n: n[0])
    i = next(k for k, n in enumerate(same) if n[0] == path)
    picks = [same[(i + k) % len(same)] for k in range(1, min(4, len(same)))]
    others = sorted((n for n in NEWS if n[0] != path and n not in picks), key=lambda n: n[4], reverse=True)
    picks += others[: 3 - len(picks)]
    a_url, a_txt, b_url, b_txt = TOPIC_LINKS.get(topic, TOPIC_LINKS["beleving"])
    return (f'<section class="section section-alt"><div class="wrap">'
            f'<p class="prose" style="margin:0 auto 36px;font-size:1.1rem">Zelf op pad? Lees alles over '
            f'<a href="{a_url}">{a_txt}</a> of bekijk <a href="{b_url}">{b_txt}</a>.</p>'
            f'<h2>Lees ook</h2><div class="cards">'
            + "".join(card_html(u, t, d, p) for u, t, d, p, _, _ in picks) + "</div></div></section>")


# --------------------------------------------------------------------------- layout
def nav_html(path, lang="nl"):
    items = []
    for href, label in NAV_L[lang]:
        cur = ' aria-current="page"' if path.startswith(href) else ""
        items.append(f'<li><a href="{href}"{cur}>{label}</a></li>')
    return "".join(items)


def local_business_schema():
    return {
        "@context": "https://schema.org",
        "@type": ["LocalBusiness", "TouristAttraction"],
        "@id": SITE + "/#business",
        "name": BUSINESS["name"],
        "description": "Verhuur van elektrische e-choppers en fatbikes in Giethoorn, plus arrangementen en teamuitjes in Nationaal Park Weerribben-Wieden.",
        "url": SITE + "/",
        "telephone": BUSINESS["phone"],
        "email": BUSINESS["email"],
        "image": SITE + "/assets/img/groep-e-choppers-fatbikes-giethoorn-og.jpg",
        "logo": SITE + "/assets/brand/icon-512.png",
        "priceRange": "€€",
        "address": {
            "@type": "PostalAddress",
            "streetAddress": BUSINESS["street"],
            "postalCode": BUSINESS["postal"],
            "addressLocality": BUSINESS["city"],
            "addressRegion": "Overijssel",
            "addressCountry": "NL",
        },
        "geo": {"@type": "GeoCoordinates", "latitude": 52.71593, "longitude": 6.07756},
        "areaServed": ["Giethoorn", "Weerribben-Wieden", "Steenwijkerland", "Kop van Overijssel"],
        "sameAs": [BUSINESS["facebook"], BUSINESS["instagram"]],
    }


def footer_nl():
    return f"""<footer class="site-footer">
  <div class="wrap footer-grid">
    <div>
      <img src="/assets/brand/logo-white.webp" width="72" height="72" alt="" loading="lazy">
      <p>E-choppers en fatbikes huren in Giethoorn. Cruise door Nationaal Park Weerribben-Wieden, met z'n tweeën of met je hele team.</p>
      <p class="social"><a href="{BUSINESS['facebook']}" rel="noopener">Facebook</a><a href="{BUSINESS['instagram']}" rel="noopener">Instagram</a></p>
    </div>
    <div>
      <h2>Huren &amp; boeken</h2>
      <ul>
        <li><a href="{BOOK['echopper']}">E-chopper reserveren</a></li>
        <li><a href="{BOOK['fatbike']}">Fatbike reserveren</a></li>
        <li><a href="{BOOK['ontdek']}">Arrangement Ontdek Giethoorn &amp; Weerribben</a></li>
        <li><a href="{BOOK['evening']}">Evening Chopper Tour</a></li>
      </ul>
    </div>
    <div>
      <h2>Ontdek</h2>
      <ul>
        <li><a href="/e-chopper-huren-giethoorn/">E-chopper huren in Giethoorn</a></li>
        <li><a href="/fat-bike-huren-in-giethoorn/">Fatbike huren in Giethoorn</a></li>
        <li><a href="/fiets-huren-giethoorn/">Fiets huren in Giethoorn</a></li>
        <li><a href="/sloep-huren-giethoorn/">Sloep en e-chopper</a></li>
        <li><a href="/wat-te-doen-in-giethoorn/">Wat te doen in Giethoorn</a></li>
        <li><a href="/teamuitje-met-echopper/">Bedrijfsuitje in Giethoorn</a></li>
        <li><a href="/vrijgezellenfeest-met-elektrische-scooters/">Vrijgezellenfeest</a></li>
        <li><a href="/samenwerking/">Samenwerken</a></li>
        <li><a href="/nieuws/">Nieuws</a></li>
      </ul>
    </div>
    <div>
      <h2>Contact</h2>
      <address>
        {BUSINESS['name']}<br>
        Startlocatie: {BUSINESS['location']}<br>
        {BUSINESS['street']}, {BUSINESS['postal']} {BUSINESS['city']}<br>
        <a href="tel:{BUSINESS['phone']}">{BUSINESS['phone_display']}</a><br>
        <a href="mailto:{BUSINESS['email']}">{BUSINESS['email']}</a>
      </address>
      <p><a class="link-arrow" href="{BUSINESS['maps']}" rel="noopener">Route plannen</a></p>
    </div>
  </div>
  <div class="wrap footer-bottom">
    <span>&copy; 2021 - {date.today().year} Badass Rentals</span>
    <span><a href="/algemene-voorwaarden/">Algemene voorwaarden</a><a href="/privacyverklaring/">Privacyverklaring</a><a href="/veelgestelde-vragen/">Veelgestelde vragen</a></span>
  </div>
</footer>"""


def footer_en():
    return f"""<footer class="site-footer">
  <div class="wrap footer-grid">
    <div>
      <img src="/assets/brand/logo-white.webp" width="72" height="72" alt="" loading="lazy">
      <p>E-chopper and electric fat bike rental in Giethoorn. Ride through Weerribben-Wieden National Park, just the two of you or with your whole group.</p>
      <p class="social"><a href="{BUSINESS['facebook']}" rel="noopener">Facebook</a><a href="{BUSINESS['instagram']}" rel="noopener">Instagram</a></p>
    </div>
    <div>
      <h2>Book online</h2>
      <ul>
        <li><a href="{BOOK_EN['echopper']}">Book an e-chopper</a></li>
        <li><a href="{BOOK_EN['fatbike']}">Book a fat bike</a></li>
        <li><a href="{BOOK_EN['ontdek']}">Discover Giethoorn &amp; Weerribben tour</a></li>
        <li><a href="{BOOK_EN['evening']}">Evening Chopper Tour</a></li>
      </ul>
    </div>
    <div>
      <h2>Explore</h2>
      <ul>
        <li><a href="/en/">E-chopper &amp; fat bike rental</a></li>
        <li><a href="/en/e-chopper-rental-giethoorn/">E-chopper rental in Giethoorn</a></li>
        <li><a href="/en/fat-bike-rental-giethoorn/">Fat bike rental in Giethoorn</a></li>
        <li><a href="/en/tours/">Giethoorn tours: e-chopper &amp; boat</a></li>
        <li><a href="/en/things-to-do-in-giethoorn/">Things to do in Giethoorn</a></li>
        <li><a href="/en/faq/">FAQ &amp; contact</a></li>
        <li><a href="/" hreflang="nl" lang="nl">Nederlandse website</a></li>
      </ul>
    </div>
    <div>
      <h2>Contact</h2>
      <address>
        {BUSINESS['name']}<br>
        Meeting point: {BUSINESS['location']}<br>
        {BUSINESS['street']}, {BUSINESS['postal']} {BUSINESS['city']}, the Netherlands<br>
        <a href="tel:{BUSINESS['phone']}">+31 85 004 7700</a><br>
        <a href="mailto:{BUSINESS['email']}">{BUSINESS['email']}</a>
      </address>
      <p><a class="link-arrow" href="{BUSINESS['maps']}" rel="noopener">Get directions</a></p>
    </div>
  </div>
  <div class="wrap footer-bottom">
    <span>&copy; 2021 - {date.today().year} Badass Rentals</span>
    <span><a href="/algemene-voorwaarden/" hreflang="nl">Terms and conditions (Dutch)</a><a href="/privacyverklaring/" hreflang="nl">Privacy policy (Dutch)</a><a href="/en/faq/">FAQ</a></span>
  </div>
</footer>"""


def footer_de():
    return f"""<footer class="site-footer">
  <div class="wrap footer-grid">
    <div>
      <img src="/assets/brand/logo-white.webp" width="72" height="72" alt="" loading="lazy">
      <p>E-Chopper und E-Fatbikes mieten in Giethoorn. Cruisen Sie durch den Nationalpark Weerribben-Wieden, zu zweit oder mit der ganzen Gruppe.</p>
      <p class="social"><a href="{BUSINESS['facebook']}" rel="noopener">Facebook</a><a href="{BUSINESS['instagram']}" rel="noopener">Instagram</a></p>
    </div>
    <div>
      <h2>Online buchen</h2>
      <ul>
        <li><a href="{BOOK_L['de']['echopper']}">E-Chopper buchen</a></li>
        <li><a href="{BOOK_L['de']['fatbike']}">Fatbike buchen</a></li>
        <li><a href="{BOOK_L['de']['ontdek']}">Tour: Giethoorn &amp; Weerribben entdecken</a></li>
        <li><a href="{BOOK_L['de']['evening']}">Evening Chopper Tour</a></li>
      </ul>
    </div>
    <div>
      <h2>Entdecken</h2>
      <ul>
        <li><a href="/de/">E-Chopper &amp; Fatbike mieten</a></li>
        <li><a href="/de/e-chopper-mieten-giethoorn/">E-Chopper mieten in Giethoorn</a></li>
        <li><a href="/de/fatbike-mieten-giethoorn/">Fatbike mieten in Giethoorn</a></li>
        <li><a href="/de/touren/">Touren: E-Chopper &amp; Boot</a></li>
        <li><a href="/de/sehenswuerdigkeiten-giethoorn/">Sehenswürdigkeiten in Giethoorn</a></li>
        <li><a href="/de/faq/">FAQ &amp; Kontakt</a></li>
        <li><a href="/" hreflang="nl" lang="nl">Nederlandse website</a></li>
      </ul>
    </div>
    <div>
      <h2>Kontakt</h2>
      <address>
        {BUSINESS['name']}<br>
        Treffpunkt: {BUSINESS['location']}<br>
        {BUSINESS['street']}, {BUSINESS['postal']} {BUSINESS['city']}, Niederlande<br>
        <a href="tel:{BUSINESS['phone']}">+31 85 004 7700</a><br>
        <a href="mailto:{BUSINESS['email']}">{BUSINESS['email']}</a>
      </address>
      <p><a class="link-arrow" href="{BUSINESS['maps']}" rel="noopener">Route planen</a></p>
    </div>
  </div>
  <div class="wrap footer-bottom">
    <span>&copy; 2021 - {date.today().year} Badass Rentals</span>
    <span><a href="/algemene-voorwaarden/" hreflang="nl">AGB (Niederländisch)</a><a href="/privacyverklaring/" hreflang="nl">Datenschutz (Niederländisch)</a><a href="/de/faq/">FAQ</a></span>
  </div>
</footer>"""


LABELS = {
    "nl": {"skip": "Direct naar de inhoud", "start": "Start bij", "in": "in", "home": "/", "crumbs": "Kruimelpad",
           "brand": "Badass Rentals, naar de homepage", "menu": "Hoofdmenu", "book": "Reserveren", "locale": "nl_NL"},
    "en": {"skip": "Skip to content", "start": "Meeting point:", "in": "in", "home": "/en/", "crumbs": "Breadcrumb",
           "brand": "Badass Rentals, to the homepage", "menu": "Main menu", "book": "Book now", "locale": "en_GB"},
    "de": {"skip": "Direkt zum Inhalt", "start": "Treffpunkt:", "in": "in", "home": "/de/", "crumbs": "Brotkrümelnavigation",
           "brand": "Badass Rentals, zur Startseite", "menu": "Hauptmenü", "book": "Jetzt buchen", "locale": "de_DE"},
}
FOOTERS = {"nl": lambda: footer_nl(), "en": lambda: footer_en(), "de": lambda: footer_de()}


def layout(page, body, path):
    title = page["title"]
    desc = page.get("description", "")
    canonical = SITE + path
    og_img = SITE + f"/assets/img/{page.get('image', 'groep-e-choppers-fatbikes-giethoorn')}-og.jpg"
    robots = "noindex, follow" if page.get("noindex") else "index, follow, max-image-preview:large"

    lang = page.get("lang", "nl")
    T = LABELS[lang]
    schemas = [local_business_schema()] if path == "/" else []
    if page.get("crumb") and path != "/":
        crumbs = [{"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"}]
        if page.get("parent"):
            p_url, p_name = page["parent"].split("|")
            crumbs.append({"@type": "ListItem", "position": 2, "name": p_name, "item": SITE + p_url})
        crumbs.append({"@type": "ListItem", "position": len(crumbs) + 1, "name": page["crumb"], "item": canonical})
        schemas.append({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": crumbs})
    if page.get("_faq") and page.get("faq_schema"):
        schemas.append({
            "@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": q,
                            "acceptedAnswer": {"@type": "Answer", "text": re.sub(r"<[^>]+>", "", a).strip()}}
                           for q, a in page["_faq"]],
        })
    if page.get("article"):
        schemas.append({
            "@context": "https://schema.org", "@type": "BlogPosting",
            "headline": page["h1"] if page.get("h1") else title, "description": desc,
            "image": og_img, "datePublished": page["date"], "dateModified": page.get("updated", page["date"]),
            "author": {"@type": "Organization", "name": "Badass Rentals"},
            "publisher": {"@id": SITE + "/#business"}, "mainEntityOfPage": canonical,
        })
    schema_html = "".join(
        f'<script type="application/ld+json">{json.dumps(s, ensure_ascii=False)}</script>' for s in schemas
    )
    crumb_html = ""
    if page.get("crumb") and path != "/":
        mid = ""
        if page.get("parent"):
            p_url, p_name = page["parent"].split("|")
            mid = f'<li><a href="{p_url}">{p_name}</a></li>'
        crumb_html = (f'<nav class="crumbs wrap" aria-label="{T["crumbs"]}"><ol><li><a href="{T["home"]}">Home</a></li>{mid}'
                      f'<li aria-current="page">{page["crumb"]}</li></ol></nav>')

    body_class = page.get("body_class", "")
    alt = ALTERNATES.get(path, {})
    hreflang = ""
    if len(alt) > 1:
        hreflang = "".join(f'<link rel="alternate" hreflang="{l}" href="{SITE}{alt[l]}">\n' for l in LANGS if l in alt)
        hreflang += f'<link rel="alternate" hreflang="x-default" href="{SITE}{alt["nl"]}">\n'
    names = {"nl": "Nederlands", "en": "English", "de": "Deutsch"}
    switch = "".join(
        f'<li><a class="lang-switch" href="{alt.get(l) or LABELS[l]["home"]}" title="{names[l]}" aria-label="{names[l]}" '
        f'hreflang="{l}" lang="{l}">{l.upper()}</a></li>' for l in LANGS if l != lang)
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<meta name="robots" content="{robots}">
<link rel="canonical" href="{canonical}">
{hreflang}<meta property="og:type" content="{'article' if page.get('article') else 'website'}">
<meta property="og:locale" content="{T["locale"]}">
<meta property="og:site_name" content="Badass Rentals">
<meta property="og:title" content="{html.escape(page.get('og_title', title))}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{og_img}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#111111">
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" href="/assets/brand/favicon-32.png" type="image/png" sizes="32x32">
<link rel="apple-touch-icon" href="/assets/brand/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
<link rel="preload" href="/assets/fonts/anton-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/assets/fonts/inter-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/css/site.css?v={VERSION}">
{schema_html}
</head>
<body class="{body_class}"{f' data-google-form="{GOOGLE_FORM_URL}"' if GOOGLE_FORM_URL else ""}>
<a class="skip" href="#main">{T["skip"]}</a>
<div class="topbar"><div class="wrap topbar-inner">
  <span>{T['start']} {BUSINESS['location']}, {BUSINESS['street']} {T['in']} {BUSINESS['city']}</span>
  <span class="topbar-links"><a href="tel:{BUSINESS['phone']}">{BUSINESS['phone_display']}</a><a href="mailto:{BUSINESS['email']}">{BUSINESS['email']}</a></span>
</div></div>
<header class="site-header">
  <div class="wrap header-inner">
    <a class="brand" href="{T["home"]}" aria-label="{T["brand"]}">
      <img src="/assets/brand/logo-white.webp" width="56" height="56" alt="Badass Rentals logo">
      <span>Badass<br>Rentals</span>
    </a>
    <button class="nav-toggle" aria-expanded="false" aria-controls="site-nav"><span></span><span class="sr">Menu</span></button>
    <nav id="site-nav" class="site-nav" aria-label="{T["menu"]}">
      <ul>{nav_html(path, lang)}{switch}</ul>
      <a class="btn btn-accent btn-sm" href="{BOOK_L[lang]['root']}">{T["book"]}</a>
    </nav>
  </div>
</header>
{crumb_html}
<main id="main">
{body}
</main>
{FOOTERS[lang]()}
<script src="/assets/js/site.js?v={VERSION}" defer></script>
</body>
</html>
"""


# --------------------------------------------------------------------------- pagina's
def parse_page(text):
    m = re.match(r"---\s*\n(.*?)\n---\s*\n(.*)", text, re.S)
    if not m:
        raise SystemExit("Pagina zonder front matter")
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            v = v.strip()
            meta[k.strip()] = {"true": True, "false": False}.get(v, v)
    return meta, m.group(2)


def page_path(file):
    return "/" if file.stem == "index" else f"/{file.stem}/"


def write_page(path, content):
    target = OUT / ("index.html" if path == "/" else path.strip("/") + "/index.html")
    if path == "/404/":
        target = OUT / "404.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def htaccess_rules():
    """Leest de 301-regels uit src/root/.htaccess (regels zonder RewriteCond)."""
    rules, cond = [], False
    for line in (SRC / "root" / ".htaccess").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("RewriteCond"):
            cond = True
        elif line.startswith("RewriteRule"):
            parts = line.split()
            if not cond and len(parts) >= 3:
                flags = parts[3] if len(parts) > 3 else ""
                rules.append((re.compile(parts[1], re.I if "NC" in flags else 0), parts[2]))
            cond = False
    return rules


def redirect_stubs():
    """GitHub Pages kent geen .htaccess: maak op elk oud adres een doorverwijspagina.
    De lijst oude adressen staat in tools/old-urls.txt; de bestemming komt uit .htaccess (één bron)."""
    rules = htaccess_rules()
    old = (ROOT / "tools" / "old-urls.txt").read_text().split()
    made = 0
    for path in dict.fromkeys(old):
        rel = path.lstrip("/")
        target_file = OUT / rel / "index.html" if path.endswith("/") else OUT / rel
        if path == "/" or target_file.exists():
            continue
        for rx, target in rules:
            m = rx.search(rel)
            if not m:
                continue
            if target == "-":
                break
            target = re.sub(r"\$(\d)", lambda g: m.group(int(g.group(1))) or "", target)
            src = OUT / target.lstrip("/")
            if not path.endswith("/"):
                # Bestanden (pdf, xml): een kopie op het oude adres
                if src.is_file():
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, target_file)
                    made += 1
                break
            url = SITE + target
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text(
                f'<!doctype html><html lang="nl"><head><meta charset="utf-8"><title>Doorverwijzing</title>'
                f'<meta name="robots" content="noindex"><link rel="canonical" href="{url}">'
                f'<meta http-equiv="refresh" content="0; url={target}">'
                f'<script>location.replace("{target}"+location.hash)</script></head>'
                f'<body><p>Deze pagina is verhuisd naar <a href="{target}">{url}</a>.</p></body></html>\n',
                encoding="utf-8")
            made += 1
            break
    return made


VERSION = date.today().strftime("%Y%m%d")


def main():
    if OUT.exists():
        for p in OUT.iterdir():
            if p.name == "assets":
                for sub in p.iterdir():
                    if sub.name != "img":  # afbeeldingen cachen
                        shutil.rmtree(sub) if sub.is_dir() else sub.unlink()
            else:
                shutil.rmtree(p) if p.is_dir() else p.unlink()
    OUT.mkdir(exist_ok=True)

    print("Afbeeldingen...")
    build_images()

    print("Assets...")
    for item in (SRC / "assets").iterdir():
        if item.name == "img":
            continue
        dst = OUT / "assets" / item.name
        shutil.copytree(item, dst) if item.is_dir() else shutil.copy2(item, dst)
    for item in (SRC / "root").iterdir():
        dst = OUT / item.name
        shutil.copytree(item, dst) if item.is_dir() else shutil.copy2(item, dst)
    shutil.copy2(SRC / "assets" / "brand" / "favicon.ico", OUT / "favicon.ico")

    pages = []
    for f in sorted((SRC / "pages").glob("*.html")) + [f for l in LANGS[1:] for f in sorted((SRC / "pages" / l).glob("*.html"))]:
        meta, body = parse_page(f.read_text(encoding="utf-8"))
        path = page_path(f)
        if f.parent.name in LANGS:
            lang = f.parent.name
            meta["lang"] = lang
            path = f"/{lang}" + path
            if meta.get("alternate"):
                group = ALTERNATES.setdefault(meta["alternate"], {"nl": meta["alternate"]})
                group[lang] = path
                ALTERNATES[path] = group
        pages.append((path, meta, body))
        if meta.get("article"):
            NEWS.append((page_path(f), meta.get("h1", meta["title"]), meta["description"], meta["image"], meta["date"],
                         meta.get("topic", "beleving")))

    print("Pagina's...")
    sitemap = []
    for path, meta, body in pages:
        if meta.get("article"):
            body += related_html(path, meta.get("topic", "beleving"))
        rendered = render_shortcodes(body, meta)
        if GOOGLE_FORM_URL:  # formulieren gaan naar Google Apps Script (GitHub Pages kent geen PHP)
            rendered = rendered.replace('action="/verzenden.php"', f'action="{GOOGLE_FORM_URL}"')
        write_page(path, layout(meta, rendered, path))
        if not meta.get("noindex"):
            sitemap.append((path, meta.get("updated") or meta.get("date") or date.today().isoformat(),
                            meta.get("priority", "0.6")))

    urls = "".join(
        f"<url><loc>{SITE}{p}</loc><lastmod>{d}</lastmod><priority>{pr}</priority></url>" for p, d, pr in sitemap
    )
    (OUT / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n',
        encoding="utf-8")
    stubs = redirect_stubs()
    (OUT / "CNAME").write_text("badassrentals.nl\n", encoding="utf-8")   # eigen domein voor GitHub Pages
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    print(f"Klaar: {len(pages)} pagina's, {len(sitemap)} in sitemap, {stubs} doorverwijzingen -> {OUT}")

    if "--serve" in sys.argv:
        import http.server
        import functools
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(OUT))
        print("Bekijk op http://localhost:8000  (Ctrl+C om te stoppen; PHP-formulieren werken hier niet)")
        http.server.ThreadingHTTPServer(("", 8000), handler).serve_forever()


if __name__ == "__main__":
    main()
