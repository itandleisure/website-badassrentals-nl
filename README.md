# badassrentals.nl

Statische website van Badass Rentals (e-chopper- en fatbikeverhuur in Giethoorn).
Vervangt de oude WordPress-site. Reserveren gaat via het bestaande boekingssysteem op
https://verhuur.badassrentals.nl.

## Structuur

| Map / bestand | Inhoud |
|---|---|
| `src/pages/` | Pagina's: front matter (titel, meta description, afbeelding) + HTML |
| `src/photos/` | Bronfoto's (JPG, zonder EXIF/GPS). Worden automatisch WebP in 480/960/1600 px |
| `src/assets/` | CSS, JS, fonts (lokaal gehost), logo/favicons, voorwaarden-PDF's |
| `src/root/` | Webroot-bestanden: `.htaccess` (redirects, caching), `robots.txt`, `verzenden.php` |
| `src/templates/huurovereenkomst.html` | Sjabloon voor de QR-huurovereenkomst per voertuig |
| `vehicles.py` | Lijst e-choppers + kentekens (QR-pagina's) |
| `build.py` | Bouwt alles naar `public/` |
| `public/` | **De site die online moet.** Upload de inhoud naar de webroot |

## Bouwen

```bash
pip install pillow
python build.py            # bouwt naar public/
python build.py --serve    # bouwen + bekijken op http://localhost:8000
```

## Pagina bewerken

Open het bestand in `src/pages/`. Handige codes:

- `{% img naam "alt-tekst" %}` voegt een foto uit `src/photos/naam.jpg` in (opties: `eager`, `sizes="..."`, `class="..."`)
- `{{book.echopper}}`, `{{book.fatbike}}`, `{{book.ontdek}}`, `{{book.evening}}`, `{{book.cityescape}}`, `{{book.root}}`: boekingslinks (centraal in `build.py`)
- `{{biz.phone}}`, `{{biz.email}}` ...: bedrijfsgegevens
- `{% faq %} Q: vraag / A: <p>antwoord</p> {% endfaq %}`: uitklapbare vragen
- `{% cta %}`, `{% reviews %}`, `{% usps %}`, `{% news %}`: vaste blokken

Nieuw nieuwsbericht: kopieer een bestaand bericht, pas `date`, `title`, `description` en `image` aan.
Het verschijnt vanzelf op /nieuws/ en in de sitemap.

## Formulieren

Alle formulieren posten naar `/verzenden.php` en worden gemaild naar **info@badassrentals.nl**
(afzender `noreply@badassrentals.nl`, antwoorden gaan naar de invuller).
Spambescherming: honeypot + minimale invultijd. Getekende huurovereenkomsten worden daarnaast
als CSV bewaard in `../huurovereenkomsten/` (buiten de webroot) of anders in `private/` (afgeschermd).

Vereist PHP 7.4+ met werkende `mail()`. Zorg dat SPF/DKIM voor badassrentals.nl de webserver toestaat,
anders kunnen mails in spam belanden.

## QR-codes op voertuigen

De URL's `/verhuur-e-chopper-nummer-X-met-kenteken-.../`, `/verhuur-fatbikes-algemene-voorwaarden/`,
`/qrcode/`, `/qr-code-nederlands|engels|duits/` en `/instagram/` zijn exact behouden, zodat bestaande
QR-stickers en de Instagram-bio blijven werken. Nieuwe e-chopper? Voeg een regel toe aan `vehicles.py`.

## Oude URL's

`src/root/.htaccess` stuurt alle oude WordPress-URL's met een 301 door naar de juiste nieuwe pagina.
