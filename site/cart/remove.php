<?php
// cart/remove.php
session_start();
header('Content-Type: application/json');

$data = json_decode(file_get_contents('php://input'), true);
$key  = isset($data['key']) ? (int)$data['key'] : null;

if ($key && isset($_SESSION['panier'][$key])) {
    unset($_SESSION['panier'][$key]);
}

if ($key && isset($_SESSION['client_id'])) {
    require_once '../includes/bd.php';

    $stmt = $pdo->prepare("
        DELETE FROM panier 
        WHERE id_client = ? AND id_variant = ?
    ");
    $stmt->execute([
        $_SESSION['client_id'],
        $key
    ]);
}

$count = isset($_SESSION['panier'])
    ? array_sum(array_column($_SESSION['panier'], 'quantity'))
    : 0;

echo json_encode([
    'success' => true,
    'count'   => $count
]);