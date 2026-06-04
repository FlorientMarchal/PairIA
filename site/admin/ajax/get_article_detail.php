<?php
// admin/ajax/get_article_detail.php
require_once '../includes/auth_admin.php';
require_once '../../includes/bd.php';

header('Content-Type: application/json');

$id = (int)($_GET['id'] ?? 0);
if (!$id) { echo json_encode(null); exit; }

$stmt = $pdo->prepare("SELECT * FROM articles WHERE id_shoes = ?");
$stmt->execute([$id]);
$article = $stmt->fetch();
if (!$article) { echo json_encode(null); exit; }

$stmt2 = $pdo->prepare("SELECT id_variant, taille, couleur, stock FROM size_color WHERE id_shoes = ? ORDER BY taille, couleur");
$stmt2->execute([$id]);
$article['variants'] = $stmt2->fetchAll();

echo json_encode($article, JSON_UNESCAPED_UNICODE);
