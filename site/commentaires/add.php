<?php
ini_set('display_errors', 1);
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

// Vérifie que le client a bien acheté cette chaussure
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