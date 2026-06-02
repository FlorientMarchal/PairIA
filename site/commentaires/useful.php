<?php
require_once '../includes/bd.php';

session_start();

$id = (int)($_GET['id'] ?? 0);
$value = (int)($_GET['value'] ?? 1);

$stmt = $pdo->prepare("UPDATE commentaires SET useful = useful + ? WHERE id_commentaire = ?");
$stmt->execute([$value, $id]);

echo json_encode(['success'=>true]);
