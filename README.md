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
| `public/` | **De site die online moet.** Wordt automatisch uitgerold (zie Uitrollen) |

## Uitrollen (GitHub is leidend)

Elke push naar `main` met wijzigingen in `public/` zet de site automatisch op de Vimexx-hosting via
FTPS (`.github/workflows/deploy.yml`). Werkwijze: pas `src/` aan, draai `python build.py`, commit en push.

Eenmalig in GitHub instellen (Settings > Secrets and variables > Actions): `FTP_SERVER`, `FTP_USERNAME`,
`FTP_PASSWORD` en `FTP_DIR` (meestal `/domains/badassrentals.nl/public_html`).
Er wordt standaard niets verwijderd op de server. Oude bestanden opruimen: Actions > Deploy > Run workflow
met "opruimen" aangevinkt (huurovereenkomsten en caches blijven staan).

## Bouwen

```bash
pip install pillow
python build.py            # bouwt naar public/
python build.py --serve    # bouwen + bekijken op http://localhost:8000
```

### Lokaal testen met formulieren (PHP)

PHP 8.4 is lokaal geïnstalleerd (winget). `mail()` stuurt lokaal naar een test-mailserver,
er gaat dus niets echt de deur uit. Open twee terminals:

```bash
python tools/mailcatcher.py                 # vangt mails op in dev-mail/*.eml
php -S localhost:8000 -t public             # site mét werkende formulieren
```

Getekende huurovereenkomsten komen lokaal in `huurovereenkomsten/` (niet in git).

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

## Reviews

De reviews staan in `build.py` (lijst `REVIEWS`): echte 5-sterren Google-reviews. Nieuwe review toevoegen = regel toevoegen en opnieuw bouwen.

## QR-codes op voertuigen

De URL's `/algemene-voorwaarden/verhuur-e-chopper-nummer-X-met-kenteken-.../`, `/algemene-voorwaarden/verhuur-fatbikes-algemene-voorwaarden/`,
`/qrcode/`, `/qr-code-nederlands|engels|duits/` en `/instagram/` zijn exact behouden, zodat bestaande
QR-stickers en de Instagram-bio blijven werken. Nieuwe e-chopper? Voeg een regel toe aan `vehicles.py`.

## Controles

```bash
python tools/seo_audit.py                 # titels, descriptions, H1, alt, canonicals, sitemap, interne links
python tools/check_live.py                # na livegang: komen alle 107 oude URL's goed uit?
```

## Oude URL's

`src/root/.htaccess` stuurt alle oude WordPress-URL's met een 301 door naar de juiste nieuwe pagina.
