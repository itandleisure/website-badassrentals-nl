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
| `build.py` | Bouwt alles naar `public/` |
| `public/` | **De site die online moet.** Wordt automatisch uitgerold (zie Uitrollen) |

## Uitrollen: GitHub Pages

De site draait op **GitHub Pages**. Elke push naar `main` met wijzigingen in `public/` zet de site automatisch
online (`.github/workflows/pages.yml`). Werkwijze: pas `src/` aan, draai `python build.py`, commit en push.

- Eenmalig: Settings > Pages > Source: **GitHub Actions**, Custom domain: `badassrentals.nl`, daarna **Enforce HTTPS**.
- Oude URL's: GitHub Pages kent geen `.htaccess`. Het buildscript maakt daarom op elk oud adres
  (tools/old-urls.txt + korte QR-adressen) een doorverwijspagina, met de bestemming uit `src/root/.htaccess`.
- PHP, `.htaccess` en `private/` worden niet mee geüpload. Formulieren lopen via Google Apps Script;
  lukt dat niet, dan ziet de bezoeker een melding met telefoonnummer en e-mailadres.
- `.htaccess` en `verzenden.php` blijven in de repository voor als de site ooit weer op eigen hosting komt.

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

**Google Sheets + e-mail (zoals bij coworkingcompeta.com).** Staat `GOOGLE_FORM_URL` in `build.py` ingevuld,
dan stuurt `site.js` elk formulier naar het Google Apps Script `tools/google-formulier/Code.gs`.
Dat zet de inzending in een eigen tabblad (Contact, Teamuitjes, Samenwerking)
en mailt info@badassrentals.nl. Opruimen gaat automatisch na 12 maanden.
Lukt Google niet, dan gaat het formulier automatisch via `verzenden.php` (hieronder).

Eenmalig instellen:
1. Maak een Google Sheet, bijv. "Badass Rentals formulieren". Extensies > Apps Script: plak `Code.gs`.
2. Kies de functie `installeer` en klik Uitvoeren (toestemming geven).
3. Implementeren > Nieuwe implementatie > Web-app, uitvoeren als: ik, toegang: iedereen.
4. Zet de /exec-URL in `GOOGLE_FORM_URL` in `build.py`, draai `python build.py`, commit en push.

Script later gewijzigd? Implementeren > Implementaties beheren > bewerken > Nieuwe versie (URL blijft gelijk).

**Reserveroute / zonder Google:**

Alle formulieren posten naar `/verzenden.php` en worden gemaild naar **info@badassrentals.nl**
(afzender `noreply@badassrentals.nl`, antwoorden gaan naar de invuller).
Spambescherming: honeypot + minimale invultijd.

Vereist PHP 7.4+ met werkende `mail()`. Zorg dat SPF/DKIM voor badassrentals.nl de webserver toestaat,
anders kunnen mails in spam belanden.

## Reviews

De reviews staan in `build.py` (lijst `REVIEWS`): echte 5-sterren Google-reviews. Nieuwe review toevoegen = regel toevoegen en opnieuw bouwen.

## QR-codes

De digitale huurovereenkomsten (QR-codes op de voertuigen) worden niet meer gebruikt. De oude adressen
(`/algemene-voorwaarden/verhuur-e-chopper-...`) sturen door naar de algemene voorwaarden.
`/qrcode/`, `/qr-code-nederlands|engels|duits/` en `/instagram/` bestaan nog wel.

## Controles

```bash
python tools/seo_audit.py                 # titels, descriptions, H1, alt, canonicals, sitemap, interne links
python tools/check_live.py                # na livegang: komen alle 107 oude URL's goed uit?
```

## Oude URL's

`src/root/.htaccess` stuurt alle oude WordPress-URL's met een 301 door naar de juiste nieuwe pagina.
