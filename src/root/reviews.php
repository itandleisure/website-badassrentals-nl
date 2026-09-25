<?php
/**
 * Levert Google-reviews van Badass Rentals als JSON voor de website.
 *
 * Haalt de gegevens op via de Google Places API (New) en bewaart ze 24 uur in een cache,
 * zodat Google maar ~1x per dag wordt aangeroepen (vrijwel kosteloos) en de site snel blijft.
 * De API-sleutel staat alleen op de server in private/config.php (niet in git).
 *
 * Instellen: kopieer private/config.example.php naar private/config.php en vul de sleutel in.
 * Zonder werkende config geeft dit script een 503 en toont de website de vaste reviews.
 */

declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');
header('X-Robots-Tag: noindex');

const CACHE_TTL   = 86400;      // 24 uur
const MIN_RATING  = 4;          // alleen reviews van 4-5 sterren met tekst tonen
const MAX_REVIEWS = 6;

$configFile = __DIR__ . '/private/config.php';
$cacheFile  = __DIR__ . '/private/google-reviews-cache.json';

function out(int $status, array $data): void
{
    http_response_code($status);
    if ($status === 200) {
        header('Cache-Control: public, max-age=3600');
    }
    echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function google(string $method, string $url, string $key, string $fieldMask, ?array $body = null): ?array
{
    $headers = "X-Goog-Api-Key: {$key}\r\nX-Goog-FieldMask: {$fieldMask}\r\n";
    $opts = ['method' => $method, 'timeout' => 8, 'ignore_errors' => true, 'header' => $headers];
    if ($body !== null) {
        $opts['header'] .= "Content-Type: application/json\r\n";
        $opts['content'] = json_encode($body);
    }
    $raw = @file_get_contents($url, false, stream_context_create(['http' => $opts]));
    if ($raw === false) {
        return null;
    }
    $json = json_decode($raw, true);
    return is_array($json) && !isset($json['error']) ? $json : null;
}

// Verse cache? Direct leveren.
$cache = is_file($cacheFile) ? json_decode((string) file_get_contents($cacheFile), true) : null;
if ($cache && (time() - ($cache['fetched'] ?? 0)) < CACHE_TTL) {
    out(200, $cache['data']);
}

$config = is_file($configFile) ? require $configFile : [];
$key = $config['google_api_key'] ?? '';
if ($key === '') {
    $cache ? out(200, $cache['data']) : out(503, ['error' => 'not_configured']);
}

// Place ID zoeken als die (nog) niet is ingesteld.
$placeId = $config['google_place_id'] ?? ($cache['place_id'] ?? '');
if ($placeId === '') {
    $found = google('POST', 'https://places.googleapis.com/v1/places:searchText', $key, 'places.id',
        ['textQuery' => $config['search_query'] ?? 'Badass Rentals Giethoorn', 'languageCode' => 'nl']);
    $placeId = $found['places'][0]['id'] ?? '';
}
if ($placeId === '') {
    $cache ? out(200, $cache['data']) : out(503, ['error' => 'place_not_found']);
}

$place = google(
    'GET',
    'https://places.googleapis.com/v1/places/' . rawurlencode($placeId) . '?languageCode=nl',
    $key,
    'rating,userRatingCount,googleMapsUri,reviews'
);
if (!$place) {
    // Google tijdelijk onbereikbaar: oude cache gebruiken als die er is.
    $cache ? out(200, $cache['data']) : out(503, ['error' => 'google_unavailable']);
}

$reviews = [];
foreach ($place['reviews'] ?? [] as $r) {
    $text = trim($r['originalText']['text'] ?? ($r['text']['text'] ?? ''));
    if (($r['rating'] ?? 0) < MIN_RATING || $text === '') {
        continue;
    }
    $reviews[] = [
        'author' => $r['authorAttribution']['displayName'] ?? 'Google-gebruiker',
        'author_url' => $r['authorAttribution']['uri'] ?? '',
        'rating' => (int) $r['rating'],
        'text' => mb_strlen($text) > 420 ? mb_substr($text, 0, 400) . '…' : $text,
        'when' => $r['relativePublishTimeDescription'] ?? '',
    ];
}

$data = [
    'rating' => $place['rating'] ?? null,
    'count' => $place['userRatingCount'] ?? null,
    'url' => $place['googleMapsUri'] ?? '',
    'reviews' => array_slice($reviews, 0, MAX_REVIEWS),
];

@file_put_contents($cacheFile, json_encode(['fetched' => time(), 'place_id' => $placeId, 'data' => $data],
    JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES), LOCK_EX);

out(200, $data);
