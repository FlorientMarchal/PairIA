<?php
require_once '../includes/auth_admin.php';
require_once '../../includes/bd.php';


$stmt = $pdo->query("
    SELECT a.id_shoes, a.nom, a.categorie, a.marque, a.genre, a.Prix,
           COALESCE(SUM(sc.stock), 0) AS stock_total
    FROM articles a
    LEFT JOIN size_color sc ON sc.id_shoes = a.id_shoes
    GROUP BY a.id_shoes
    ORDER BY a.categorie, a.nom
");


header('Content-Type: application/json');
echo json_encode($stmt->fetchAll(), JSON_UNESCAPED_UNICODE);
