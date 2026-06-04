<?php
// admin/ajax/get_commandes.php
require_once '../includes/auth_admin.php';
require_once '../../includes/bd.php';

$statut = $_GET['statut'] ?? '';
$params = [];
$where  = '1=1';

if ($statut !== '') {
    $where    = 'c.statut = ?';
    $params[] = $statut;
}

$stmt = $pdo->prepare("
    SELECT c.id_commande, c.date_commande, c.statut, c.total,
           c.stripe_statut, cl.nom, cl.prenom, cl.mail
    FROM commandes c
    JOIN clients cl ON cl.id_client = c.id_client
    WHERE $where
    ORDER BY c.date_commande DESC
    LIMIT 100
");
$stmt->execute($params);

header('Content-Type: application/json');
echo json_encode($stmt->fetchAll(), JSON_UNESCAPED_UNICODE);
