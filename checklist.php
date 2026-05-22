<?php
// checklist.php — WWFT Checklist download handler
// Validates form, sends requester a download link, notifies info@finaxis.nl, redirects to /bedankt/

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    header('Location: /gids/wwft-checklist/');
    exit;
}

$naam      = htmlspecialchars(trim($_POST['naam']         ?? ''));
$email     = filter_var(trim($_POST['email']              ?? ''), FILTER_SANITIZE_EMAIL);
$organisatie = htmlspecialchars(trim($_POST['organisatie'] ?? ''));

if (empty($naam) || empty($email) || !filter_var($email, FILTER_VALIDATE_EMAIL)) {
    header('Location: /gids/wwft-checklist/?error=1');
    exit;
}

$pdf_url    = 'https://finaxis.nl/assets/downloads/wwft-checklist-2026.pdf';
$download_url = $pdf_url;

// ── Email to requester ────────────────────────────────────────────────────────
$subject_requester = 'Jouw WWFT Compliance Checklist 2026 — Finaxis';
$body_requester = 'Hallo ' . $naam . ',' . "\r\n\r\n"
    . 'Bedankt voor jouw download. Hieronder vind je de directe link naar de WWFT Compliance Checklist 2026:' . "\r\n\r\n"
    . $download_url . "\r\n\r\n"
    . 'De checklist bevat 17 controlepunten voor KYC, AML en CDD — direct toepasbaar in jouw organisatie.' . "\r\n\r\n"
    . 'Heb je vragen over WWFT-compliance, CDD/KYC of wil je bespreken hoe Finaxis jouw organisatie kan ondersteunen?' . "\r\n"
    . 'Neem dan gerust contact op via info@finaxis.nl of bel +31 6 25 00 95 05.' . "\r\n\r\n"
    . 'Met vriendelijke groet,' . "\r\n"
    . 'Alexander Gevorgyan' . "\r\n"
    . 'Finaxis Financial Services' . "\r\n"
    . 'https://finaxis.nl';

$headers_requester = 'From: info@finaxis.nl' . "\r\n"
    . 'Reply-To: info@finaxis.nl' . "\r\n"
    . 'Content-Type: text/plain; charset=UTF-8' . "\r\n"
    . 'X-Mailer: PHP/' . phpversion();

mail($email, $subject_requester, $body_requester, $headers_requester, '-f info@finaxis.nl');

// ── Notification to Finaxis ───────────────────────────────────────────────────
$subject_internal = 'Checklist download — ' . $naam . ' (' . $organisatie . ')';
$body_internal = 'Nieuwe download aanvraag via finaxis.nl/gids/wwft-checklist/' . "\r\n\r\n"
    . 'Naam:         ' . $naam . "\r\n"
    . 'E-mail:       ' . $email . "\r\n"
    . 'Organisatie:  ' . $organisatie . "\r\n\r\n"
    . 'Tijdstip: ' . date('Y-m-d H:i:s') . ' UTC';

$headers_internal = 'From: info@finaxis.nl' . "\r\n"
    . 'Reply-To: ' . $email . "\r\n"
    . 'Content-Type: text/plain; charset=UTF-8' . "\r\n"
    . 'X-Mailer: PHP/' . phpversion();

mail('info@finaxis.nl', $subject_internal, $body_internal, $headers_internal, '-f info@finaxis.nl');
mail('alex.g@live.nl',  $subject_internal, $body_internal, $headers_internal, '-f info@finaxis.nl');

// ── Redirect to thank-you page ────────────────────────────────────────────────
header('Location: /bedankt/');
exit;
