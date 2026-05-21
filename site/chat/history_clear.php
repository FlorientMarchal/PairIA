<?php
// chat/history_save.php
//Efface une session
session_start();
header('Content-Type: application/json');
if (!isset($_SESSION['client_id'])) { echo json_encode(['success'=>false]); exit; }

$data       = json_decode(file_get_contents('php://input'), true);
$session_id = $data['session_id'] ?? null;

require_once '../includes/bd.php';
if ($session_id) {
    $pdo->prepare("DELETE FROM chat_sessions WHERE id = ? AND id_client = ?")
        ->execute([$session_id, $_SESSION['client_id']]);
} else {
    // Efface tout
    $pdo->prepare("DELETE FROM chat_sessions WHERE id_client = ?")
        ->execute([$_SESSION['client_id']]);
}
echo json_encode(['success'=>true]);