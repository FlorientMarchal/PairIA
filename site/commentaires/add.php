<?php
ini_set('display_errors', 0);
error_reporting(E_ALL);

require_once '../includes/bd.php';
session_start();

header('Content-Type: application/json');

$data = json_decode(file_get_contents("php://input"), true);

if (!$data) {
    echo json_encode(['success' => false, 'error' => 'No data']);
    exit;
}

$id      = (int)$data['id'];
$note    = (int)$data['note'];
$contenu = trim($data['contenu'] ?? '');

if (!isset($_SESSION['client_id'])) {
    echo json_encode(['success' => false, 'error' => 'not_logged']);
    exit;
}

if ($note < 1 || $note > 5 || $contenu === '') {
    echo json_encode(['success' => false, 'error' => 'invalid_input']);
    exit;
}

// ── 1) LIMITE 300 CARACTÈRES ─────────────────────────────────────
if (mb_strlen($contenu) > 300) {
    echo json_encode(['success' => false, 'error' => 'too_long']);
    exit;
}

// ── 2) LISTE NOIRE LOCALE ────────────────────────────────────────
// Mots et expressions interdits (insultes, racisme, haine)
$blacklist = [
    // Insultes générales
    'connard','connasse','enculé','enculer','encule','fdp','fils de pute',
    'pute','putain','salope','batard','bâtard','merde','conne','con ',
    'imbécile','idiot','crétin','abruti','débile','nique','niquer',
    'va te faire','ta gueule','ferme ta gueule','mange','ntm',
    // Racisme / discrimination
    'nègre','négro','negro','bamboula','bougnoule','bougnoul',
    'raton','bicot','chinetoque','feuj','youpin','youpine',
    'juif de merde','sale arabe','sale noir','sale blanc',
    'sale juif','sale musulman','sale gay','sale pédé',
    'pédé','pédale','tapette','gouine','travelo',
    // Haine / violence
    'nazi','heil','hitler','kkk','génocide','viol','violer',
    'tuer','je vais te tuer','mort aux','crève','nique ta mère',
    'nique ta race','ta race','suicide','pendez',
    // Spam / hors-sujet évident
    'http://','https://','www.','bit.ly','whatsapp','telegram',
    'casino','bitcoin','crypto','gagner de l\'argent',
];

$contenuLower = mb_strtolower($contenu);
foreach ($blacklist as $mot) {
    if (str_contains($contenuLower, mb_strtolower($mot))) {
        echo json_encode([
            'success' => false,
            'error'   => 'contenu_inapproprie',
            'message' => 'Votre avis contient des termes non autorisés. Merci de rester respectueux.'
        ]);
        exit;
    }
}

// ── 3) ANALYSE IA (Groq) ─────────────────────────────────────────
$apiKey = defined('GROQ_API_KEY') ? GROQ_API_KEY : (getenv('GROQ_API_KEY') ?: '');

if ($apiKey) {
    $modPrompt = "Tu es un modérateur pour PairIA, boutique de chaussures.
Analyse ce commentaire client et réponds UNIQUEMENT en JSON valide.

Règles de refus :
- Insultes ou grossièretés
- Contenu raciste, discriminatoire ou haineux
- Menaces ou incitations à la violence
- Contenu sexuel explicite
- Spam ou publicité
- Tout ce qui n'a rien à avoir avec les chaussures, les livraisons ou le service client

Si le commentaire respecte les règles → {\"ok\": true}
Sinon → {\"ok\": false, \"raison\": \"explication courte en français\"}

Commentaire à analyser : \"" . addslashes($contenu) . "\"";

    $payload = json_encode([
        'model'       => 'llama-3.3-70b-versatile',
        'temperature' => 0,
        'max_tokens'  => 60,
        'messages'    => [
            ['role' => 'user', 'content' => $modPrompt]
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
        CURLOPT_TIMEOUT => 6,
    ]);

    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    if ($response && $httpCode === 200) {
        $apiData = json_decode($response, true);
        $raw     = trim($apiData['choices'][0]['message']['content'] ?? '');
        $raw     = preg_replace('/```json|```/i', '', $raw);
        $parsed  = json_decode(trim($raw), true);

        if (isset($parsed['ok']) && $parsed['ok'] === false) {
            echo json_encode([
                'success' => false,
                'error'   => 'contenu_inapproprie',
                'message' => $parsed['raison'] ?? 'Votre avis ne respecte pas notre charte. Merci de rester constructif.'
            ]);
            exit;
        }
    }
    // Si Groq ne répond pas → on laisse passer (fail open)
}

// ── 4) VÉRIFICATION ACHAT ────────────────────────────────────────
$stmt = $pdo->prepare("
    SELECT 1
    FROM lignes_commande lc
    JOIN commandes co ON co.id_commande = lc.id_commande
    WHERE lc.id_shoes = ? AND co.id_client = ?
    LIMIT 1
");
$stmt->execute([$id, $_SESSION['client_id']]);

if (!$stmt->fetch()) {
    echo json_encode(['success' => false, 'error' => 'not_purchased']);
    exit;
}

// ── 5) INSERTION ─────────────────────────────────────────────────
try {
    $stmt = $pdo->prepare("
        INSERT INTO commentaires (id_shoes, id_client, note, contenu, useful)
        VALUES (?, ?, ?, ?, 0)
        ON DUPLICATE KEY UPDATE note = VALUES(note), contenu = VALUES(contenu)
    ");
    $stmt->execute([$id, $_SESSION['client_id'], $note, $contenu]);
    echo json_encode(['success' => true]);
} catch (PDOException $e) {
    echo json_encode(['success' => false, 'error' => $e->getMessage()]);
}