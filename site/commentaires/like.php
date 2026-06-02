<?php
require_once '../includes/bd.php';
session_start();

$id = (int)($_GET['id'] ?? 0);
$client = $_SESSION['client_id'] ?? 0;

if (!$client) exit(json_encode(['success'=>false]));

$stmt = $pdo->prepare("SELECT 1 FROM commentaire_likes WHERE id_commentaire = ? AND id_client = ?");
$stmt->execute([$id, $client]);

if ($stmt->fetch()) {
    $pdo->prepare("DELETE FROM commentaire_likes WHERE id_commentaire = ? AND id_client = ?")
        ->execute([$id, $client]);
} else {
    $pdo->prepare("INSERT INTO commentaire_likes (id_commentaire, id_client) VALUES (?, ?)")
        ->execute([$id, $client]);
}

echo json_encode(['success'=>true]);
