<?php
require_once '../includes/bd.php';
session_start();

header('Content-Type: application/json');

// Seuls les clients connectés peuvent utiliser l'autocomplétion
if (!isset($_SESSION['client_id'])) {
    echo json_encode(['success' => false, 'error' => 'not_logged']);
    exit;
}

$data    = json_decode(file_get_contents("php://input"), true);
$texte   = trim($data['texte']   ?? '');
$produit = trim($data['produit'] ?? '');
$note    = (int)($data['note']   ?? 0);

if (strlen($texte) < 2) {
    echo json_encode(['success' => false, 'error' => 'texte_trop_court']);
    exit;
}

// ── Clé API Groq ─────────────────────────────────────────────────
// Ajoute dans includes/bd.php : define('GROQ_API_KEY', 'gsk_...');
$apiKey = defined('GROQ_API_KEY') ? GROQ_API_KEY : (getenv('GROQ_API_KEY') ?: '');

if (!$apiKey) {
    echo json_encode(['success' => false, 'error' => 'api_key_manquante']);
    exit;
}

// ── Contexte selon la note ────────────────────────────────────────
$tonNote = '';
if ($note >= 4)      $tonNote = "Le client a donné une note élevée ({$note}/5) : suggestions enthousiastes.";
elseif ($note === 3) $tonNote = "Note moyenne (3/5) : suggestions nuancées mais constructives.";
elseif ($note > 0)   $tonNote = "Note basse ({$note}/5) : déception exprimée poliment et factuellement, sans insulte.";

// ── Prompt système ────────────────────────────────────────────────
$systemPrompt = "Tu es un assistant pour PairIA, boutique en ligne de chaussures haut de gamme.
Propose exactement 3 suggestions de continuation de phrase pour un avis client.

Règles ABSOLUES :
- Suggestions positives, bienveillantes et constructives
- Aucun mot vulgaire, insultant ou irrespectueux
- Toujours en lien avec les chaussures (confort, style, qualité, taille, livraison, matière, semelle, design…)
- Chaque suggestion continue naturellement le texte déjà écrit
- Entre 8 et 20 mots par suggestion
- Suggestions variées entre elles
- Réponds UNIQUEMENT en JSON valide, sans texte avant ou après, sans balises markdown

Format attendu (JSON pur) :
{\"suggestions\": [\"suggestion 1\", \"suggestion 2\", \"suggestion 3\"]}";

// ── Message utilisateur ───────────────────────────────────────────
$userMessage = "Texte déjà écrit par le client : \"{$texte}\"";
if ($produit) $userMessage .= "\nProduit concerné : {$produit}";
if ($tonNote) $userMessage .= "\nContexte : {$tonNote}";

// ── Appel API Groq (llama-3.3-70b-versatile) ─────────────────────
$payload = json_encode([
    'model'       => 'llama-3.3-70b-versatile',
    'temperature' => 0.7,
    'max_tokens'  => 300,
    'messages'    => [
        ['role' => 'system', 'content' => $systemPrompt],
        ['role' => 'user',   'content' => $userMessage]
    ]
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
    CURLOPT_TIMEOUT        => 8,
]);

$response = curl_exec($ch);
$httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);

if (!$response || $httpCode !== 200) {
    echo json_encode(['success' => false, 'error' => 'api_error', 'code' => $httpCode]);
    exit;
}

// ── Extraction du texte généré ────────────────────────────────────
$apiData = json_decode($response, true);
$rawText = $apiData['choices'][0]['message']['content'] ?? '';

// Nettoyage backticks éventuels
$rawText = preg_replace('/```json|```/i', '', $rawText);
$rawText = trim($rawText);

$parsed = json_decode($rawText, true);

if (!$parsed || !isset($parsed['suggestions']) || !is_array($parsed['suggestions'])) {
    echo json_encode(['success' => false, 'error' => 'parse_error', 'raw' => $rawText]);
    exit;
}

// Filtrage de sécurité : chaînes non vides uniquement
$suggestions = array_values(array_filter(
    array_map('trim', $parsed['suggestions']),
    fn($s) => strlen($s) > 3
));

echo json_encode(['success' => true, 'suggestions' => $suggestions]);