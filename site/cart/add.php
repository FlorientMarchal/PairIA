<?php
// cart/add.php
session_start();
header('Content-Type: application/json');

$data = json_decode(file_get_contents('php://input'), true);
$product_id = isset($data['product_id']) ? (int)$data['product_id'] : 0;
$quantity   = isset($data['quantity'])   ? (int)$data['quantity']   : 1;
$taille     = isset($data['taille'])     ? $data['taille']           : null;
$couleur    = isset($data['couleur'])    ? $data['couleur']          : null;

// Vérifier taille obligatoire
if ($taille === null || $taille === '') {
    echo json_encode([
        'success' => false,
        'error' => 'Veuillez sélectionner une pointure'
    ]);
    exit;
}

// Vérifier couleur obligatoire
if ($couleur === null || $couleur === '') {
    echo json_encode([
        'success' => false,
        'error' => 'Veuillez sélectionner une couleur'
    ]);
    exit;
}

if (!$product_id) {
    echo json_encode(['success' => false, 'error' => 'ID produit manquant']);
    exit;
}

// Initialiser le panier
if (!isset($_SESSION['panier'])) {
    $_SESSION['panier'] = [];
}

// Clé unique par produit + taille + couleur
$key = $product_id . '_' . ($taille ?? '') . '_' . ($couleur ?? '');

if (isset($_SESSION['panier'][$key])) {
    $_SESSION['panier'][$key]['quantity'] += $quantity;
} else {
    // Récupérer les infos du produit depuis MySQL
    require_once '../includes/bd.php';
    $stmt = $pdo->prepare("SELECT id_shoes, nom, categorie, Prix, url_image FROM articles WHERE id_shoes = ?");
    $stmt->execute([$product_id]);
    $article = $stmt->fetch();

    if (!$article) {
        echo json_encode(['success' => false, 'error' => 'Produit introuvable']);
        exit;
    }

    $_SESSION['panier'][$key] = [
        'id'       => $product_id,
        'nom'      => $article['nom'],
        'categorie'=> $article['categorie'],
        'prix'     => (float)$article['Prix'],
        'image'    => $article['url_image'],
        'taille'   => $taille,
        'couleur'  => $couleur,
        'quantity' => $quantity,
    ];
}

$count = array_sum(array_column($_SESSION['panier'], 'quantity'));
echo json_encode(['success' => true, 'count' => $count]);