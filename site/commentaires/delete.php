<?php
require_once '../includes/bd.php';
session_start();

$id = (int)($_GET['id'] ?? 0);

$stmt = $pdo->prepare("DELETE FROM commentaires WHERE id_commentaire = ? AND id_client = ?");
$stmt->execute([$id, $_SESSION['client_id'] ?? 0]);

echo json_encode(['success'=>true]);
