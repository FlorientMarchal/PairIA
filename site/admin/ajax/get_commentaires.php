<?php
require_once '../includes/auth_admin.php';
require_once '../../includes/bd.php';

$stmt = $pdo->query("
    SELECT cm.id_commentaire, cm.note, cm.contenu, cm.created_at,
           a.nom AS article, cl.nom AS client_nom, cl.prenom AS client_prenom
    FROM commentaires cm
    JOIN articles a  ON a.id_shoes   = cm.id_shoes
    JOIN clients cl  ON cl.id_client = cm.id_client
    ORDER BY cm.created_at DESC LIMIT 50
");
header('Content-Type: application/json');
echo json_encode($stmt->fetchAll(), JSON_UNESCAPED_UNICODE);
