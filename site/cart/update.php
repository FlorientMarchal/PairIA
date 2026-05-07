<?php
// cart/update.php
session_start();
header('Content-Type: application/json');

$data     = json_decode(file_get_contents('php://input'), true);
$key      = isset($data['key'])      ? $data['key']      : null;
$quantity = isset($data['quantity']) ? (int)$data['quantity'] : 0;

if (!$key || !isset($_SESSION['panier'][$key])) {
    echo json_encode(['success' => false]);
    exit;
}

if ($quantity <= 0) {
    unset($_SESSION['panier'][$key]);
} else {
    $_SESSION['panier'][$key]['quantity'] = min($quantity, 10);
}

$count = isset($_SESSION['panier'])
    ? array_sum(array_column($_SESSION['panier'], 'quantity'))
    : 0;

echo json_encode(['success' => true, 'count' => $count]);