<?php
//favorites/toggle.php — ajoute ou retire un favori
session_start();
require_once '../includes/bd.php';

header('Content-Type: application/json');

// Vérif connexion
if (!isset($_SESSION['client_id'])) {
    echo json_encode(['success' => false, 'error' => 'not_logged']);
    exit;
}

$data = json_decode(file_get_contents("php://input"), true);

$id_shoes  = (int)($data['product_id'] ?? 0);
$id_client = $_SESSION['client_id'];

if (!$id_shoes) {
    echo json_encode(['success' => false]);
    exit;
}

// Vérifie si déjà en favori
$stmt = $pdo->prepare("SELECT id FROM favoris WHERE id_client=? AND id_shoes=?");
$stmt->execute([$id_client, $id_shoes]);

if ($stmt->fetch()) {

    // SUPPRESSION
    $pdo->prepare("DELETE FROM favoris WHERE id_client=? AND id_shoes=?")
        ->execute([$id_client, $id_shoes]);

    echo json_encode(['success' => true, 'action' => 'removed']);

} else {

    // AJOUT
    $pdo->prepare("INSERT INTO favoris (id_client, id_shoes) VALUES (?, ?)")
        ->execute([$id_client, $id_shoes]);

    echo json_encode(['success' => true, 'action' => 'added']);
}