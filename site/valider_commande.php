<?php
session_start();
require_once 'includes/bd.php';        // ← site/ donc pas de ../
require_once 'includes/config.php';    // ← idem
require __DIR__ . '/../vendor/autoload.php';  // ← un seul niveau au-dessus

header('Content-Type: application/json');

if (!isset($_SESSION['client_id'])) {
    echo json_encode(['success' => false, 'error' => 'Non connecté']);
    exit;
}

$input             = json_decode(file_get_contents('php://input'), true);
$payment_intent_id = trim($input['payment_intent_id'] ?? '');
$client_id         = (int)$_SESSION['client_id'];

if (!$payment_intent_id) {
    echo json_encode(['success' => false, 'error' => 'payment_intent_id manquant']);
    exit;
}

\Stripe\Stripe::setApiKey(STRIPE_SECRET_KEY);

try {
    $intent = \Stripe\PaymentIntent::retrieve($payment_intent_id);
} catch (\Exception $e) {
    echo json_encode(['success' => false, 'error' => 'Impossible de vérifier le paiement : ' . $e->getMessage()]);
    exit;
}

if ($intent->status !== 'succeeded') {
    echo json_encode(['success' => false, 'error' => 'Paiement non confirmé (statut : ' . $intent->status . ')']);
    exit;
}

$check = $pdo->prepare("SELECT id_commande FROM commandes WHERE stripe_payment_intent = ?");
$check->execute([$payment_intent_id]);
if ($check->fetch()) {
    echo json_encode(['success' => false, 'error' => 'Ce paiement a déjà été enregistré.']);
    exit;
}

$stmt = $pdo->prepare("
    SELECT p.id_variant, p.quantite,
           sc.taille, sc.couleur, sc.stock,
           a.id_shoes, a.nom, a.Prix
    FROM panier p
    JOIN size_color sc ON sc.id_variant = p.id_variant
    JOIN articles a    ON a.id_shoes    = sc.id_shoes
    WHERE p.id_client = ?
");
$stmt->execute([$client_id]);
$panier = $stmt->fetchAll();

if (empty($panier)) {
    echo json_encode(['success' => false, 'error' => 'Panier vide ou expiré.']);
    exit;
}

$sous_total = array_sum(array_map(fn($i) => $i['Prix'] * $i['quantite'], $panier));
$livraison  = $sous_total >= 80 ? 0 : 10;
$total      = $sous_total + $livraison;

$stmtAdresse = $pdo->prepare("SELECT adresse FROM clients WHERE id_client = ?");
$stmtAdresse->execute([$client_id]);
$adresse = $stmtAdresse->fetchColumn() ?? '';

try {
    $pdo->beginTransaction();

    foreach ($panier as $item) {
        if ($item['quantite'] > $item['stock']) {
            throw new Exception("Stock insuffisant pour « {$item['nom']} » (taille {$item['taille']}).");
        }
    }

    $pdo->prepare("
        INSERT INTO commandes
            (id_client, date_commande, statut, sous_total, frais_livraison, total,
             adresse_livraison, stripe_payment_intent, stripe_statut)
        VALUES (?, NOW(), 'payée', ?, ?, ?, ?, ?, 'succeeded')
    ")->execute([$client_id, $sous_total, $livraison, $total, $adresse, $payment_intent_id]);

    $id_commande = (int)$pdo->lastInsertId();

    $stmtLigne = $pdo->prepare("
        INSERT INTO lignes_commande
            (id_commande, id_shoes, id_variant, nom_article, taille, couleur, prix_unitaire, quantite, sous_total)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ");
    foreach ($panier as $item) {
        $stmtLigne->execute([
            $id_commande, $item['id_shoes'], $item['id_variant'],
            $item['nom'], $item['taille'], $item['couleur'],
            $item['Prix'], $item['quantite'], $item['Prix'] * $item['quantite']
        ]);
    }

    $stmtStock = $pdo->prepare("UPDATE size_color SET stock = stock - ? WHERE id_variant = ? AND stock >= ?");
    foreach ($panier as $item) {
        $stmtStock->execute([$item['quantite'], $item['id_variant'], $item['quantite']]);
        if ($stmtStock->rowCount() === 0) {
            throw new Exception("Stock insuffisant (race condition) pour « {$item['nom']} ».");
        }
    }

    $stmtStockTotal = $pdo->prepare("
        UPDATE articles SET stock_total = (
            SELECT COALESCE(SUM(stock), 0) FROM size_color WHERE id_shoes = articles.id_shoes
        ) WHERE id_shoes = ?
    ");
    foreach (array_unique(array_column($panier, 'id_shoes')) as $id_shoes) {
        $stmtStockTotal->execute([$id_shoes]);
    }

    $pdo->prepare("DELETE FROM panier WHERE id_client = ?")->execute([$client_id]);
    unset($_SESSION['panier']);

    $pdo->commit();
    echo json_encode(['success' => true, 'id_commande' => $id_commande]);

} catch (Exception $e) {
    $pdo->rollBack();
    echo json_encode(['success' => false, 'error' => $e->getMessage()]);
}