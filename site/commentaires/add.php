<?php
require_once '../includes/bd.php';
session_start();

$data = json_decode(file_get_contents("php://input"), true);

$id = (int)$data['id'];
$note = (int)$data['note'];
$contenu = trim($data['contenu']);

if (!isset($_SESSION['client_id'])) exit(json_encode(['success'=>false]));

if ($note < 1 || $note > 5) exit(json_encode(['success'=>false]));

$stmt = $pdo->prepare("
    INSERT INTO commentaires (id_shoes, id_client, note, contenu)
    VALUES (?, ?, ?, ?)
    ON DUPLICATE KEY UPDATE note = VALUES(note), contenu = VALUES(contenu)
");
$stmt->execute([$id, $_SESSION['client_id'], $note, $contenu]);

echo json_encode(['success'=>true]);
