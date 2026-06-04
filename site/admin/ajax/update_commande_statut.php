<?php
// admin/ajax/update_commande_statut.php
require_once '../includes/auth_admin.php';
require_once '../../includes/bd.php';

header('Content-Type: application/json');

$data   = json_decode(file_get_contents('php://input'), true);
$id     = (int) ($data['id_commande'] ?? 0);
$statut = trim($data['statut'] ?? '');

$statuts_ok = ['en_attente', 'payée', 'expédiée', 'livrée', 'annulée'];

if (!$id || !in_array($statut, $statuts_ok)) {
    echo json_encode(['success' => false, 'message' => 'Paramètres invalides.']);
    exit;
}

$stmt = $pdo->prepare("UPDATE commandes SET statut = ? WHERE id_commande = ?");
$stmt->execute([$statut, $id]);

if ($stmt->rowCount() === 0) {
    echo json_encode(['success' => false, 'message' => 'Commande introuvable.']);
    exit;
}

echo json_encode(['success' => true, 'message' => "Statut mis à jour : $statut."]);
