<?php
require_once '../includes/bd.php';
session_start();

header('Content-Type: application/json');

if (!isset($_SESSION['client_id'])) {
    echo json_encode(['success' => false, 'error' => 'not_logged']);
    exit;
}

$data    = json_decode(file_get_contents("php://input"), true);
$texte   = trim($data['texte']   ?? '');
$produit = trim($data['produit'] ?? '');
$note    = (int)($data['note']   ?? 0);
$mode    = trim($data['mode']    ?? 'ghost'); // "ghost" ou "rewrite"

if (strlen($texte) < 2) {
    echo json_encode(['success' => false, 'error' => 'texte_trop_court']);
    exit;
}

$apiKey = defined('GROQ_API_KEY') ? GROQ_API_KEY : (getenv('GROQ_API_KEY') ?: '');
if (!$apiKey) {
    echo json_encode(['success' => false, 'error' => 'api_key_manquante']);
    exit;
}

// ── Ton selon la note ────────────────────────────────────────────
$ton = "";
if ($note >= 4)      $ton = "Le client est très satisfait ({$note}/5).";
elseif ($note === 3) $ton = "Le client est moyennement satisfait (3/5).";
elseif ($note > 0)   $ton = "Le client est déçu ({$note}/5) mais reste poli.";

// ────────────────────────────────────────────────────────────────
// MODE REWRITE : mots-clés → phrase complète
// ────────────────────────────────────────────────────────────────
if ($mode === 'rewrite') {

    $prompt = "Tu es un assistant pour PairIA, boutique de chaussures haut de gamme.
L'utilisateur a donné des mots-clés. Génère UNE phrase complète, naturelle et fluide en français.
Règles :
- La phrase doit parler UNIQUEMENT de chaussures (confort, style, qualité, taille, matière, semelle, etc.)
- {$ton}
- Entre 8 et 25 mots
- Si l'utilisateur donne très peu de mots (moins de 4), génère quand même une phrase simple et naturelle.
- Pas de vulgarité, pas d'invention de détails non fournis
- Phrase directe à la 1ère personne (\"J'ai...\", \"Ces chaussures...\", etc.)
- Réponds UNIQUEMENT en JSON : {\"rewrite\": \"ta phrase ici\"}

Mots-clés : \"{$texte}\"" . ($produit ? "\nProduit : {$produit}" : "");

    $messages = [['role' => 'user', 'content' => $prompt]];

// ────────────────────────────────────────────────────────────────
// MODE GHOST : continuation inline
// ────────────────────────────────────────────────────────────────
} else {

    $system = "Tu es un assistant pour PairIA, boutique de chaussures haut de gamme.
Continue naturellement la phrase d'un avis client sur des chaussures.
Règles ABSOLUES :
- Continuation liée aux chaussures (confort, style, qualité, taille, livraison, semelle, matière…)
- {$ton}
- Entre 6 et 18 mots pour la continuation
- Pas de vulgarité ni d'insulte
- Variées et originales
- Réponds UNIQUEMENT en JSON : {\"suggestions\": [\"continuation 1\", \"continuation 2\", \"continuation 3\"]}";

    $messages = [
        ['role' => 'system', 'content' => $system],
        ['role' => 'user',   'content' => "Texte : \"{$texte}\"" . ($produit ? "\nProduit : {$produit}" : "")]
    ];
}

// ── Appel Groq ───────────────────────────────────────────────────
$payload = json_encode([
    'model'       => 'llama-3.3-70b-versatile',
    'temperature' => $mode === 'rewrite' ? 0.6 : 0.7,
    'max_tokens'  => $mode === 'rewrite' ? 120 : 300,
    'messages'    => $messages
]);

$ch = curl_init('https://api.groq.com/openai/v1/chat/completions');
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_POST           => true,
    CURLOPT_POSTFIELDS     => $payload,
    CURLOPT_HTTPHEADER     => [
        'Content-Type: application/json',
        'Authorization: Bearer ' . $apiKey
    ],
    CURLOPT_TIMEOUT => 8,
]);

$response = curl_exec($ch);
$httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);

if (!$response || $httpCode !== 200) {
    echo json_encode(['success' => false, 'error' => 'api_error', 'code' => $httpCode]);
    exit;
}

$apiData = json_decode($response, true);
$raw     = trim($apiData['choices'][0]['message']['content'] ?? '');
$raw     = preg_replace('/```json|```/i', '', $raw);
$parsed  = json_decode(trim($raw), true);

// ── Réponse selon le mode ────────────────────────────────────────
if ($mode === 'rewrite') {
    if (isset($parsed['rewrite']) && strlen(trim($parsed['rewrite'])) > 3) {
        echo json_encode(['success' => true, 'rewrite' => trim($parsed['rewrite'])]);
    } else {
        echo json_encode(['success' => false, 'error' => 'parse_error', 'raw' => $raw]);
    }
} else {
    $suggestions = array_values(array_filter(
        array_map('trim', $parsed['suggestions'] ?? []),
        fn($s) => strlen($s) > 3
    ));
    if ($suggestions) {
        echo json_encode(['success' => true, 'suggestions' => $suggestions]);
    } else {
        echo json_encode(['success' => false, 'error' => 'parse_error', 'raw' => $raw]);
    }
}