<?php
// favorites/list.php — retourne les favoris du client connecté
session_start();
require_once '../includes/bd.php';

header('Content-Type: application/json');

if (!isset($_SESSION['client_id'])) {
    echo json_encode(['success' => false, 'favoris' => []]);
    exit;
}

$stmt = $pdo->prepare("
    SELECT a.id_shoes, a.nom, a.Prix, a.url_image, a.categorie
    FROM favoris f
    JOIN articles a ON a.id_shoes = f.id_shoes
    WHERE f.id_client = ?
    ORDER BY f.id DESC
    LIMIT 5
");
$stmt->execute([$_SESSION['client_id']]);
$favoris = $stmt->fetchAll(PDO::FETCH_ASSOC);

echo json_encode(['success' => true, 'favoris' => $favoris]);