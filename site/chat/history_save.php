<?php
// chat/history_save.php
// Enregistre un message dans la base de données
session_start();
header('Content-Type: application/json');
if (!isset($_SESSION['client_id'])) { echo json_encode(['success'=>false]); exit; }

$data       = json_decode(file_get_contents('php://input'), true);
$role       = $data['role']       ?? null;
$message    = $data['message']    ?? '';
$session_id = $data['session_id'] ?? null;
$products   = isset($data['products']) ? json_encode($data['products']) : null;
$layout     = $data['layout']     ?? null;
$silent     = !empty($data['silent'])   ? 1 : 0;
$internal   = !empty($data['internal']) ? 1 : 0;

if (!$role || !$message || !$session_id) { echo json_encode(['success'=>false]); exit; }
if ($role === 'system') { echo json_encode(['success'=>true, 'skipped'=>true]); exit; }

require_once '../includes/bd.php';
$stmt = $pdo->prepare("
    INSERT INTO conversations (id_session, id_client, role, message, products, layout, silent, internal)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
");
$stmt->execute([$session_id, $_SESSION['client_id'], $role, $message, $products, $layout, $silent, $internal]);

// Met à jour updated_at de la session
$pdo->prepare("UPDATE chat_sessions SET updated_at = NOW() WHERE id = ?")->execute([$session_id]);

echo json_encode(['success'=>true]);