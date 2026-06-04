<?php
// admin/ajax/delete_article.php
require_once '../includes/auth_admin.php';
require_once '../../includes/bd.php';

header('Content-Type: application/json');

$data = json_decode(file_get_contents('php://input'), true);
$id   = (int)($data['id_shoes'] ?? 0);

if (!$id) {
    echo json_encode(['success' => false, 'message' => 'ID invalide.']);
    exit;
}

try {
    $stmt = $pdo->prepare("DELETE FROM articles WHERE id_shoes = ?");
    $stmt->execute([$id]);

    if ($stmt->rowCount() === 0) {
        echo json_encode(['success' => false, 'message' => "Article #$id introuvable."]);
        exit;
    }

    // Re-vectorisation complète après suppression
    $api_url = getenv('ADMIN_API_URL') ?: 'http://admin-api:8001';
    $token   = getenv('ADMIN_ACTION_TOKEN') ?: '';

    // Suppression dans Qdrant via le service api (qui a les dépendances)
    $ch = curl_init("http://api:8000/reindex/delete");
    curl_setopt_array($ch, [
        CURLOPT_POST           => true,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 5,
        CURLOPT_HTTPHEADER     => ["X-Admin-Token: $token", "Content-Type: application/json"],
        CURLOPT_POSTFIELDS     => json_encode(['article_id' => $id]),
    ]);
    curl_exec($ch);
    curl_close($ch);

    echo json_encode(['success' => true, 'message' => "Article #$id supprimé."]);

} catch (PDOException $e) {
    echo json_encode(['success' => false, 'message' => 'Erreur BDD : ' . $e->getMessage()]);
}
