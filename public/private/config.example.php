<?php
// Kopieer dit bestand op de server naar private/config.php en vul de gegevens in.
// config.php staat bewust niet in git: de API-sleutel hoort niet in de repository.
return [
    // Google Cloud API-sleutel met "Places API (New)" ingeschakeld.
    // Beperk de sleutel in Google Cloud tot de Places API (en eventueel het IP-adres van de server).
    'google_api_key' => '',

    // Optioneel: Place ID van Badass Rentals. Leeg laten = automatisch zoeken op search_query.
    'google_place_id' => '',
    'search_query' => 'Badass Rentals Giethoorn',
];
