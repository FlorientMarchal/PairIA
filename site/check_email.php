<?php
require_once 'includes/bd.php';

$mail = $_POST['mail'] ?? '';

$stmt = $pdo->prepare("SELECT id_client FROM Clients WHERE mail = ?");
$stmt->execute([$mail]);

echo json_encode([
  "exists" => (bool)$stmt->fetch()
]);

