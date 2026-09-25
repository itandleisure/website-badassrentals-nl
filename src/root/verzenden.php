<?php
/**
 * Verwerkt alle formulieren van badassrentals.nl en mailt ze naar info@badassrentals.nl.
 *
 * Formuliertypes (hidden veld "form"):
 *   contact           Contactformulier
 *   teamuitje         Aanvraag teamuitje / arrangement op maat
 *   samenwerking      Samenwerkingsaanvraag (camping, hotel, B&B ...)
 *   huurovereenkomst  Digitale huurovereenkomst via QR-code op een voertuig
 *
 * Spambescherming: honeypot-veld "website" + minimale invultijd via "ts".
 * Werkt met PHP mail(). Komen mails niet aan? Laat de hoster SPF/DKIM voor
 * noreply@badassrentals.nl instellen of vervang send_mail() door SMTP (bijv. PHPMailer).
 */

declare(strict_types=1);

const RECIPIENT  = 'info@badassrentals.nl';
const FROM_EMAIL = 'noreply@badassrentals.nl';
const FROM_NAME  = 'Website Badass Rentals';

const FORMS = [
    'contact'          => ['subject' => 'Contactformulier',         'back' => '/kom-in-contact/',         'thanks' => '/bedankt/'],
    'teamuitje'        => ['subject' => 'Aanvraag teamuitje',       'back' => '/teamuitje-met-echopper/', 'thanks' => '/bedankt/'],
    'samenwerking'     => ['subject' => 'Aanvraag samenwerking',    'back' => '/samenwerking/',           'thanks' => '/bedankt/'],
    'huurovereenkomst' => ['subject' => 'Huurovereenkomst getekend','back' => null,                       'thanks' => '/huurovereenkomst-ontvangen/'],
];

function field(string $key, int $max = 2000): string
{
    $v = $_POST[$key] ?? '';
    if (is_array($v)) {
        $v = implode(', ', array_map('strval', $v));
    }
    $v = trim(str_replace("\0", '', (string) $v));
    return mb_substr($v, 0, $max);
}

function one_line(string $v): string
{
    return trim(preg_replace('/[\r\n\t]+/', ' ', $v));
}

function go(string $url): void
{
    header('Location: ' . $url, true, 303);
    exit;
}

function send_mail(string $subject, string $body, string $replyTo = '', string $replyName = ''): bool
{
    $headers = [
        'From: ' . mb_encode_mimeheader(FROM_NAME, 'UTF-8') . ' <' . FROM_EMAIL . '>',
        'MIME-Version: 1.0',
        'Content-Type: text/plain; charset=UTF-8',
        'Content-Transfer-Encoding: 8bit',
        'X-Mailer: badassrentals.nl',
    ];
    if ($replyTo !== '') {
        // Alleen letters, cijfers, spaties en . ' - in de weergavenaam (geen : , ; @ < > of aanhalingstekens)
        $clean = trim(preg_replace("/[^\\p{L}\\p{N} .'\\-]/u", '', one_line($replyName)));
        $name = $clean !== '' ? '"' . mb_encode_mimeheader($clean, 'UTF-8') . '" ' : '';
        $headers[] = 'Reply-To: ' . $name . '<' . $replyTo . '>';
    }
    return mail(
        RECIPIENT,
        mb_encode_mimeheader($subject, 'UTF-8'),
        $body,
        implode("\r\n", $headers),
        '-f' . FROM_EMAIL
    );
}

function store_agreement(array $row): void
{
    // Bewaar een kopie van getekende huurovereenkomsten buiten het zicht van bezoekers.
    $dir = dirname(__DIR__) . '/huurovereenkomsten';
    if (!is_dir($dir) && !@mkdir($dir, 0750, true)) {
        $dir = __DIR__ . '/private';
        if (!is_dir($dir)) {
            @mkdir($dir, 0750, true);
        }
    }
    $file = $dir . '/huurovereenkomsten-' . date('Y') . '.csv';
    $new = !file_exists($file);
    if ($fh = @fopen($file, 'ab')) {
        if ($new) {
            fputcsv($fh, array_keys($row), ';');
        }
        fputcsv($fh, array_values($row), ';');
        fclose($fh);
    }
}

// ---------------------------------------------------------------------------

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    go('/');
}
mb_internal_encoding('UTF-8');
date_default_timezone_set('Europe/Amsterdam');

$type = field('form', 40);
if (!isset(FORMS[$type])) {
    go('/');
}
$cfg  = FORMS[$type];
$page = field('page', 200);
$back = $cfg['back'] ?? (preg_match('#^/[a-z0-9\-/]+$#', $page) ? $page : '/');

// Spam: honeypot gevuld of te snel verstuurd -> doen alsof het gelukt is.
$ts = (int) field('ts', 20);
if (field('website') !== '' || ($ts > 0 && time() - $ts < 3)) {
    go($cfg['thanks']);
}

$name  = one_line(field('naam', 120));
$email = one_line(field('email', 200));
$phone = one_line(field('telefoon', 40));

$errors = [];
if ($name === '') {
    $errors[] = 'naam';
}
if ($email === '' || !filter_var($email, FILTER_VALIDATE_EMAIL)) {
    $errors[] = 'email';
}

$lines = [];
switch ($type) {
    case 'contact':
        $lines = [
            'Naam'           => $name,
            'E-mail'         => $email,
            'Telefoon'       => $phone,
            'Vraag over'     => field('onderwerp', 500),
            'Bericht'        => field('bericht', 5000),
        ];
        if ($lines['Bericht'] === '') {
            $errors[] = 'bericht';
        }
        $subject = FORMS[$type]['subject'] . ': ' . $name;
        break;

    case 'teamuitje':
        $lines = [
            'Naam'             => $name,
            'Bedrijf / groep'  => one_line(field('bedrijf', 150)),
            'E-mail'           => $email,
            'Telefoon'         => $phone,
            'Interesse'        => field('interesse', 500),
            'Aantal personen'  => one_line(field('personen', 20)),
            'Gewenste datum'   => one_line(field('datum', 40)),
            'Bericht'          => field('bericht', 5000),
        ];
        $subject = FORMS[$type]['subject'] . ': ' . $name . ($lines['Aantal personen'] ? ' (' . $lines['Aantal personen'] . ' pers.)' : '');
        break;

    case 'samenwerking':
        $lines = [
            'Naam'            => $name,
            'Bedrijf'         => one_line(field('bedrijf', 150)),
            'Type bedrijf'    => one_line(field('type_bedrijf', 80)),
            'Website'         => one_line(field('site', 200)),
            'E-mail'          => $email,
            'Telefoon'        => $phone,
            'Bericht'         => field('bericht', 5000),
        ];
        $subject = FORMS[$type]['subject'] . ': ' . ($lines['Bedrijf'] ?: $name);
        break;

    case 'huurovereenkomst':
        $vehicle = one_line(field('voertuig', 120));
        $start   = one_line(field('start', 40));
        $akkoord = field('akkoord', 10) === 'ja';
        $afkoop  = field('afkoop', 10) === 'ja';
        if ($vehicle === '') {
            $errors[] = 'voertuig';
        }
        if ($phone === '') {
            $errors[] = 'telefoon';
        }
        if (!$akkoord) {
            $errors[] = 'akkoord';
        }
        $lines = [
            'Voertuig'                  => $vehicle,
            'Naam huurder'              => $name,
            'E-mail'                    => $email,
            'Telefoon'                  => $phone,
            'Start verhuur'             => $start,
            'Akkoord voorwaarden'       => $akkoord ? 'Ja' : 'Nee',
            'Afkoopregeling afgenomen'  => $afkoop ? 'Ja' : 'Nee',
            'Versie voorwaarden'        => one_line(field('versie', 40)),
            'Verstuurd op'              => date('d-m-Y H:i:s'),
            'IP-adres'                  => $_SERVER['REMOTE_ADDR'] ?? '',
        ];
        $subject = FORMS[$type]['subject'] . ': ' . $vehicle . ' - ' . $name;
        break;
}

if ($errors) {
    go($back . '?fout=velden#formulier');
}

$body = '';
foreach ($lines as $label => $value) {
    if ($value === '') {
        continue;
    }
    $body .= (strpos($value, "\n") !== false ? "{$label}:\n{$value}\n\n" : "{$label}: {$value}\n");
}
$body .= "\n--\nVerstuurd via " . ($page ?: $back) . ' op badassrentals.nl';

if ($type === 'huurovereenkomst') {
    store_agreement($lines);
}

$ok = send_mail(one_line($subject), $body, $email, $name);
go($ok ? $cfg['thanks'] : $back . '?fout=mail#formulier');
