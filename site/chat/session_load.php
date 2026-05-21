<?php
// chat/session_load.php
//charge les messages d'une session
session_start();
header('Content-Type: application/json');
if (!isset($_SESSION['client_id'])) { echo json_encode(['history'=>[]]); exit; }

$session_id = isset($_GET['session_id']) ? (int)$_GET['session_id'] : 0;
if (!$session_id) { echo json_encode(['history'=>[]]); exit; }

require_once '../includes/bd.php';
$stmt = $pdo->prepare("
    SELECT role, message, products, layout, silent, internal
    FROM conversations
    WHERE id_session = ? AND id_client = ?
    ORDER BY created_at ASC
");
$stmt->execute([$session_id, $_SESSION['client_id']]);
$rows = $stmt->fetchAll();

$history = array_map(fn($r) => [
    'role'     => $r['role'],
    'content'  => $r['message'],
    'products' => $r['products'] ? json_decode($r['products'], true) : [],
    'layout'   => $r['layout'],
    'silent'   => (bool)$r['silent'],
    'internal' => (bool)$r['internal'],
], $rows);

echo json_encode(['history' => $history]);