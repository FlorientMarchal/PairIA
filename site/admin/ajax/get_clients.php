<?php
// admin/ajax/get_clients.php
require_once '../includes/auth_admin.php';
require_once '../../includes/bd.php';

$q = trim($_GET['q'] ?? '');

if ($q !== '') {
    $like = '%' . $q . '%';
    $stmt = $pdo->prepare("
        SELECT id_client, nom, prenom, mail, numero,
               (SELECT COUNT(*) FROM commandes WHERE id_client = c.id_client) AS nb_commandes
        FROM clients c
        WHERE nom LIKE ? OR prenom LIKE ? OR mail LIKE ?
        ORDER BY nom LIMIT 50
    ");
    $stmt->execute([$like, $like, $like]);
} else {
    $stmt = $pdo->query("
        SELECT id_client, nom, prenom, mail, numero,
               (SELECT COUNT(*) FROM commandes WHERE id_client = c.id_client) AS nb_commandes
        FROM clients c
        ORDER BY id_client DESC LIMIT 50
    ");
}

header('Content-Type: application/json');
echo json_encode($stmt->fetchAll(), JSON_UNESCAPED_UNICODE);
