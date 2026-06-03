<?php
session_start();
require_once 'includes/bd.php';

$mail = $_POST['mail'] ?? '';
$mdp  = $_POST['mdp'] ?? '';

if (empty($mail) || empty($mdp)) {
    header("Location: connexion.php?error=empty");
    exit;
}

/* 1. chercher utilisateur */
$stmt = $pdo->prepare("SELECT * FROM clients WHERE mail = ?");
$stmt->execute([$mail]);
$client = $stmt->fetch();

if (!$client) {
    header("Location: connexion.php?error=email");
    exit;
}

/* 2. vérifier mot de passe */
if (!password_verify($mdp, $client['mdp'])) {
    header("Location: connexion.php?error=password");
    exit;
}

/* 3. créer session */
$_SESSION['client'] = [
    'id' => $client['id_client'],
    'nom' => $client['nom'],
    'prenom' => $client['prenom'],
    'mail' => $client['mail']
];

$_SESSION['client_id'] = $client['id_client'];

// Dans conecter.php, après avoir créé $_SESSION['client_id']
// Recharger le panier depuis la BDD
$stmt = $pdo->prepare("
    SELECT p.quantite, p.id_variant,
           a.id_shoes, a.nom, a.categorie, a.Prix, a.url_image,
           sc.taille, sc.couleur
    FROM panier p
    JOIN size_color sc ON sc.id_variant = p.id_variant
    JOIN articles a    ON a.id_shoes    = sc.id_shoes
    WHERE p.id_client = ?
");
$stmt->execute([$client['id_client']]);
$items = $stmt->fetchAll();

$_SESSION['panier'] = [];
foreach ($items as $item) {
    $key = $item['id_variant']; // 🔥 cohérent avec panier.php
    $_SESSION['panier'][$key] = [
        'id_variant'=> $item['id_variant'],
        'id'        => $item['id_shoes'],
        'nom'       => $item['nom'],
        'categorie' => $item['categorie'],
        'prix'      => (float)$item['Prix'],
        'image'     => $item['url_image'],
        'taille'    => $item['taille'],
        'couleur'   => $item['couleur'],
        'quantity'  => $item['quantite'],
    ];
}

header("Location: index.php");
exit;
