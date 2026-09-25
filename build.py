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
  vehicles.py          lijst met e-choppers (QR-huurovereenkomsten)

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

from vehicles import ECHOPPERS

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

# Links naar het boekingssysteem. Deze URL's niet wijzigen zonder de boekingsomgeving te controleren.
BOOK = {
    "root": "https://verhuur.badassrentals.nl/",
    "echopper": "https://verhuur.badassrentals.nl/product/E-chopper",
    "fatbike": "https://verhuur.badassrentals.nl/product/fat-bike",
    "ontdek": "https://verhuur.badassrentals.nl/product/ontdek-weerribben",
    "evening": "https://verhuur.badassrentals.nl/product/evening-chopper-tour",
    "cityescape": "https://verhuur.badassrentals.nl/product/city-escape-giethoorn",
}

NAV = [
    ("/e-chopper-huren-giethoorn/", "E-chopper"),
    ("/fat-bike-huren-in-giethoorn/", "Fatbike"),
    ("/arrangementen/", "Arrangementen"),
    ("/teamuitje-met-echopper/", "Teamuitjes"),
    ("/veelgestelde-vragen/", "Vragen"),
    ("/kom-in-contact/", "Contact"),
]

IMG_WIDTHS = (480, 960, 1600)
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
            r.save(target, "WEBP", quality=74, method=6)  # geen EXIF -> geen GPS-data online
        ImageOps.fit(im, (1200, 630), Image.LANCZOS).save(og, "JPEG", quality=80, optimize=True, progressive=True)
        print("  foto:", name)


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
    for k, v in BOOK.items():
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
    body = re.sub(r"\{%\s*cta\s*%\}", lambda m: cta_html(), body)
    body = re.sub(r"\{%\s*usps\s*%\}", lambda m: usps_html(), body)
    body = re.sub(r"\{%\s*news\s*%\}", lambda m: news_html(), body)
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


def usps_html():
    items = [
        ("30+ e-choppers & 15 fatbikes", "Voor kleine en grote groepen; boven 30 personen met een wisselprogramma."),
        ("Pech onderweg? Wij komen eraan", "We regelen direct vervangend vervoer, zodat je snel weer verder kunt."),
        ("Mooiste routes", "GPS-routes door Giethoorn en Nationaal Park Weerribben-Wieden."),
        ("Goed onderhouden", "We controleren en onderhouden alle tweewielers periodiek."),
    ]
    return '<ul class="usps">' + "".join(f"<li><strong>{a}</strong><span>{b}</span></li>" for a, b in items) + "</ul>"


def cta_html():
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


NEWS = []  # gevuld tijdens build: (url, titel, beschrijving, foto, datum)


def news_html():
    cards = []
    for url, title, desc, photo, d in sorted(NEWS, key=lambda n: n[4], reverse=True):
        cards.append(
            f'<a class="card" href="{url}">{img_tag(photo, "", "(max-width: 700px) 100vw, 33vw", "card-img")}'
            f'<div class="card-body"><h3>{html.escape(title)}</h3><p>{html.escape(desc)}</p>'
            f'<span class="link-arrow">Lees verder</span></div></a>'
        )
    return '<div class="cards">' + "".join(cards) + "</div>"


# --------------------------------------------------------------------------- layout
def nav_html(path):
    items = []
    for href, label in NAV:
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


def layout(page, body, path):
    title = page["title"]
    desc = page.get("description", "")
    canonical = SITE + path
    og_img = SITE + f"/assets/img/{page.get('image', 'groep-e-choppers-fatbikes-giethoorn')}-og.jpg"
    robots = "noindex, follow" if page.get("noindex") else "index, follow, max-image-preview:large"

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
        crumb_html = (f'<nav class="crumbs wrap" aria-label="Kruimelpad"><ol><li><a href="/">Home</a></li>{mid}'
                      f'<li aria-current="page">{page["crumb"]}</li></ol></nav>')

    body_class = page.get("body_class", "")
    return f"""<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<meta name="robots" content="{robots}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="{'article' if page.get('article') else 'website'}">
<meta property="og:locale" content="nl_NL">
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
<body class="{body_class}">
<a class="skip" href="#main">Direct naar de inhoud</a>
<div class="topbar"><div class="wrap topbar-inner">
  <span>Start bij {BUSINESS['location']}, {BUSINESS['street']} in {BUSINESS['city']}</span>
  <span class="topbar-links"><a href="tel:{BUSINESS['phone']}">{BUSINESS['phone_display']}</a><a href="mailto:{BUSINESS['email']}">{BUSINESS['email']}</a></span>
</div></div>
<header class="site-header">
  <div class="wrap header-inner">
    <a class="brand" href="/" aria-label="Badass Rentals, naar de homepage">
      <img src="/assets/brand/logo-white.webp" width="56" height="56" alt="Badass Rentals logo">
      <span>Badass<br>Rentals</span>
    </a>
    <button class="nav-toggle" aria-expanded="false" aria-controls="site-nav"><span></span><span class="sr">Menu</span></button>
    <nav id="site-nav" class="site-nav" aria-label="Hoofdmenu">
      <ul>{nav_html(path)}</ul>
      <a class="btn btn-accent btn-sm" href="{BOOK['root']}">Reserveren</a>
    </nav>
  </div>
</header>
{crumb_html}
<main id="main">
{body}
</main>
<footer class="site-footer">
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
        <li><a href="/teamuitje-met-echopper/">Teamuitje in Giethoorn</a></li>
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
    <span>&copy; {date.today().year} Badass Rentals</span>
    <span><a href="/algemene-voorwaarden/">Algemene voorwaarden</a><a href="/privacyverklaring/">Privacyverklaring</a><a href="/veelgestelde-vragen/">Veelgestelde vragen</a></span>
  </div>
</footer>
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


def vehicle_pages():
    """Digitale huurovereenkomsten achter de QR-codes op de voertuigen (URL's van de oude site)."""
    tpl = (SRC / "templates" / "huurovereenkomst.html").read_text(encoding="utf-8")
    pages = []
    for nr, plate in ECHOPPERS:
        slug = f"verhuur-e-chopper-nummer-{nr}-met-kenteken-{plate.lower()}"
        label = f"E-chopper nummer {nr} met kenteken {plate}"
        pages.append((slug, "E-chopper", label, "e-chopper"))
    pages.append(("verhuur-fatbikes-algemene-voorwaarden", "Fatbike", "Fatbike", "fatbike"))
    out = []
    for slug, kind, label, key in pages:
        body = (tpl.replace("{{kind}}", kind).replace("{{vehicle}}", label).replace("{{vehicle_key}}", key)
                .replace("{{kind_lower}}", kind.lower()))
        body = re.sub(r"\{%\s*if (\w+)\s*%\}(.*?)\{%\s*endif\s*%\}",
                      lambda m: m.group(2) if m.group(1) == key.replace("-", "") else "", body, flags=re.S)
        meta = {"title": f"Huurovereenkomst {label} | Badass Rentals",
                "description": f"Digitale huurovereenkomst voor {label.lower()} van Badass Rentals in Giethoorn.",
                "noindex": True, "body_class": "page-plain"}
        out.append((f"/{slug}/", meta, body))
    return out


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
    for f in sorted((SRC / "pages").glob("*.html")):
        meta, body = parse_page(f.read_text(encoding="utf-8"))
        pages.append((page_path(f), meta, body))
        if meta.get("article"):
            NEWS.append((page_path(f), meta.get("h1", meta["title"]), meta["description"], meta["image"], meta["date"]))
    pages += vehicle_pages()

    print("Pagina's...")
    sitemap = []
    for path, meta, body in pages:
        rendered = render_shortcodes(body, meta)
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
    print(f"Klaar: {len(pages)} pagina's, {len(sitemap)} in sitemap -> {OUT}")

    if "--serve" in sys.argv:
        import http.server
        import functools
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(OUT))
        print("Bekijk op http://localhost:8000  (Ctrl+C om te stoppen; PHP-formulieren werken hier niet)")
        http.server.ThreadingHTTPServer(("", 8000), handler).serve_forever()


if __name__ == "__main__":
    main()
