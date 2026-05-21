<?php
session_start();
header('Content-Type: application/json');
if (!isset($_SESSION['client_id'])) { echo json_encode(['success'=>false]); exit; }

$data  = json_decode(file_get_contents('php://input'), true);
$titre = isset($data['titre']) ? trim(mb_substr($data['titre'], 0, 150)) : 'Nouvelle conversation';

require_once '../includes/bd.php';
$stmt = $pdo->prepare("INSERT INTO chat_sessions (id_client, titre) VALUES (?, ?)");
$stmt->execute([$_SESSION['client_id'], $titre]);
echo json_encode(['success'=>true, 'session_id'=>$pdo->lastInsertId()]);