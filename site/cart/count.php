<?php
// cart/count.php
session_start();
header('Content-Type: application/json');

$count = 0;
if (isset($_SESSION['panier'])) {
    $count = array_sum(array_column($_SESSION['panier'], 'quantity'));
}

echo json_encode(['count' => $count]);