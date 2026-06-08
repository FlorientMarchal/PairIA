<?php
// cart/add.php
session_start();
header('Content-Type: application/json');

if (!isset($_SESSION['client_id'])) {
    echo json_encode([
        'success' => false,
        'error'   => 'Vous devez être connecté pour ajouter au panier'
    ]);
    exit;
}

$data       = json_decode(file_get_contents('php://input'), true);
$product_id = isset($data['product_id']) ? (int)$data['product_id'] : 0;
$quantity   = isset($data['quantity'])   ? (int)$data['quantity']   : 1;
$taille     = isset($data['taille'])     ? trim($data['taille'])    : null;
$couleur    = isset($data['couleur'])    ? trim($data['couleur'])   : null;

// 🔒 Sécurité quantité
$quantity = max(1, min($quantity, 10));

if (!$product_id) {
    echo json_encode(['success' => false, 'error' => 'ID produit manquant']);
    exit;
}

if (empty($taille) || empty($couleur)) {
    echo json_encode(['success' => false, 'error' => 'Veuillez sélectionner taille et couleur']);
    exit;
}

require_once '../includes/bd.php';

// 🔎 Récupérer id_variant
$stmt = $pdo->prepare("
    SELECT id_variant 
    FROM size_color 
    WHERE id_shoes = ? AND taille = ? AND couleur = ?
");
$stmt->execute([$product_id, $taille, $couleur]);
$variant = $stmt->fetch();

if (!$variant) {
    echo json_encode([
        'success' => false,
        'error'   => 'Combinaison indisponible'
    ]);
    exit;
}

$id_variant = $variant['id_variant'];
$client_id  = $_SESSION['client_id'];

// 🧠 SESSION
if (!isset($_SESSION['panier'])) {
    $_SESSION['panier'] = [];
}

$key = $id_variant;

if (isset($_SESSION['panier'][$key])) {
    $_SESSION['panier'][$key]['quantity'] += $quantity;
} else {
    $stmt = $pdo->prepare("
        SELECT id_shoes, nom, categorie, Prix, url_image 
        FROM articles 
        WHERE id_shoes = ?
    ");
    $stmt->execute([$product_id]);
    $article = $stmt->fetch();

    if (!$article) {
        echo json_encode(['success' => false, 'error' => 'Produit introuvable']);
        exit;
    }

    $_SESSION['panier'][$key] = [
        'id_variant' => $id_variant,
        'id'         => $product_id,
        'nom'        => $article['nom'],
        'categorie'  => $article['categorie'],
        'prix'       => (float)$article['Prix'],
        'image'      => $article['url_image'],
        'taille'     => $taille,
        'couleur'    => $couleur,
        'quantity'   => $quantity,
    ];
}

// 🗄️ BDD (optimisé)
$stmt = $pdo->prepare("
    INSERT INTO panier (id_client, quantite, id_variant)
    VALUES (?, ?, ?)
    ON DUPLICATE KEY UPDATE quantite = quantite + VALUES(quantite)
");
$stmt->execute([$client_id, $quantity, $id_variant]);

$count = array_sum(array_column($_SESSION['panier'], 'quantity'));

echo json_encode([
    'success' => true,
    'count'   => $count
]);