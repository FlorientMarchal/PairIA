<?php
// cart/update.php
session_start();
header('Content-Type: application/json');

$data     = json_decode(file_get_contents('php://input'), true);
$key      = isset($data['key']) ? (int)$data['key'] : null;
$quantity = isset($data['quantity']) ? (int)$data['quantity'] : 0;

if (!$key || !isset($_SESSION['panier'][$key])) {
    echo json_encode(['success' => false]);
    exit;
}

// 🔒 sécurité quantité
$quantity = max(0, min($quantity, 10));

if ($quantity === 0) {

    // 🗑️ suppression session
    unset($_SESSION['panier'][$key]);

    if (isset($_SESSION['client_id'])) {
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

} else {

    // 🔄 update session
    $_SESSION['panier'][$key]['quantity'] = $quantity;

    if (isset($_SESSION['client_id'])) {
        require_once '../includes/bd.php';

        $stmt = $pdo->prepare("
            UPDATE panier 
            SET quantite = ? 
            WHERE id_client = ? AND id_variant = ?
        ");
        $stmt->execute([
            $quantity,
            $_SESSION['client_id'],
            $key
        ]);
    }
}

$count = isset($_SESSION['panier'])
    ? array_sum(array_column($_SESSION['panier'], 'quantity'))
    : 0;

echo json_encode([
    'success' => true,
    'count'   => $count
]);