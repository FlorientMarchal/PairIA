<?php
// admin/ajax/get_commande_detail.php
require_once '../includes/auth_admin.php';
require_once '../../includes/bd.php';

header('Content-Type: application/json');

$id = (int)($_GET['id'] ?? 0);
if (!$id) { echo json_encode(null); exit; }

$stmt = $pdo->prepare("
    SELECT c.*, cl.nom, cl.prenom, cl.mail, cl.numero, cl.adresse
    FROM commandes c
    JOIN clients cl ON cl.id_client = c.id_client
    WHERE c.id_commande = ?
");
$stmt->execute([$id]);
$commande = $stmt->fetch();
if (!$commande) { echo json_encode(null); exit; }

$stmt2 = $pdo->prepare("
    SELECT lc.*, sc.couleur, sc.taille
    FROM lignes_commande lc
    LEFT JOIN size_color sc ON sc.id_variant = lc.id_variant
    WHERE lc.id_commande = ?
");
$stmt2->execute([$id]);
$commande['lignes'] = $stmt2->fetchAll();

echo json_encode($commande, JSON_UNESCAPED_UNICODE);
