<?php

// chat/session_list.php
//liste les sessions pour le panneau historique
session_start();
header('Content-Type: application/json');
if (!isset($_SESSION['client_id'])) { echo json_encode(['sessions'=>[]]); exit; }

require_once '../includes/bd.php';
$stmt = $pdo->prepare("
    SELECT id, titre, created_at, updated_at
    FROM chat_sessions
    WHERE id_client = ?
    ORDER BY updated_at DESC
    LIMIT 50
");
$stmt->execute([$_SESSION['client_id']]);
echo json_encode(['sessions' => $stmt->fetchAll()]);