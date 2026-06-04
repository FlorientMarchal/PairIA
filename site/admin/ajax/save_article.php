<?php
// admin/ajax/save_article.php
require_once '../includes/auth_admin.php';
require_once '../../includes/bd.php';

header('Content-Type: application/json');

$data = json_decode(file_get_contents('php://input'), true);

$id               = isset($data['id_shoes']) ? (int)$data['id_shoes'] : null;
$nom              = trim($data['nom']              ?? '');
$categorie        = trim($data['categorie']        ?? '');
$marque           = trim($data['marque']           ?? '');
$genre            = trim($data['genre']            ?? '');
$prix             = (float)($data['prix']          ?? 0);
$description      = trim($data['description']      ?? '');
$caracteristiques = trim($data['caracteristiques'] ?? '');
$materiaux        = trim($data['materiaux']        ?? '');
$usage            = trim($data['usage']            ?? '');
$mots_cles        = trim($data['mots_cles']        ?? '');
$url_image        = trim($data['url_image']        ?? '');
$variants         = $data['variants']              ?? [];

// Stock calculé depuis les variants
$stock = 0;
foreach ($variants as $v) {
    $stock += (int)($v['stock'] ?? 0);
}

if (!$nom || !$categorie || !$marque || $prix <= 0) {
    echo json_encode(['success' => false, 'message' => 'Champs obligatoires manquants (nom, catégorie, marque, prix).']);
    exit;
}

try {
    $pdo->beginTransaction();

    if ($id) {
        if (!empty($variants)) {
            $pdo->prepare("DELETE FROM size_color WHERE id_shoes = ?")->execute([$id]);
        }

        if (!empty($variants)) {
            $max_id = (int)$pdo->query("SELECT COALESCE(MAX(id_variant), 0) FROM size_color")->fetchColumn();
            $stmt_v = $pdo->prepare("INSERT INTO size_color (id_variant, id_shoes, taille, couleur, stock) VALUES (?, ?, ?, ?, ?)");
            foreach ($variants as $v) {
                $taille  = (int)($v['taille']  ?? 0);
                $couleur = trim($v['couleur']  ?? '');
                $stk     = (int)($v['stock']   ?? 0);
                if (!$taille || !$couleur) continue;
                $max_id++;
                $stmt_v->execute([$max_id, $id, $taille, $couleur, $stk]);
            }
            $stock = (int)$pdo->query("SELECT COALESCE(SUM(stock), 0) FROM size_color WHERE id_shoes = $id")->fetchColumn();
        }

        $stmt = $pdo->prepare("
            UPDATE articles SET
                nom=?, categorie=?, marque=?, genre=?, Prix=?,
                stock_total=?, description=?, caracteristiques=?,
                materiaux=?, `usage`=?, mots_cles=?, url_image=?
            WHERE id_shoes=?
        ");
        $stmt->execute([$nom, $categorie, $marque, $genre, $prix,
                        $stock, $description, $caracteristiques,
                        $materiaux, $usage, $mots_cles, $url_image, $id]);
        $msg = "Article #$id mis à jour.";

    } else {
        $stmt = $pdo->prepare("
            INSERT INTO articles
                (nom, categorie, marque, genre, Prix, stock_total, description,
                 caracteristiques, materiaux, `usage`, mots_cles, url_image)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?)
        ");
        $stmt->execute([$nom, $categorie, $marque, $genre, $prix,
                        $description, $caracteristiques,
                        $materiaux, $usage, $mots_cles, $url_image]);
        $id = (int)$pdo->lastInsertId();

        if (!empty($variants)) {
            $max_id = (int)$pdo->query("SELECT COALESCE(MAX(id_variant), 0) FROM size_color")->fetchColumn();
            $stmt_v = $pdo->prepare("INSERT INTO size_color (id_variant, id_shoes, taille, couleur, stock) VALUES (?, ?, ?, ?, ?)");
            foreach ($variants as $v) {
                $taille  = (int)($v['taille']  ?? 0);
                $couleur = trim($v['couleur']  ?? '');
                $stk     = (int)($v['stock']   ?? 0);
                if (!$taille || !$couleur) continue;
                $max_id++;
                $stmt_v->execute([$max_id, $id, $taille, $couleur, $stk]);
            }
            $stock = (int)$pdo->query("SELECT COALESCE(SUM(stock), 0) FROM size_color WHERE id_shoes = $id")->fetchColumn();
            $pdo->prepare("UPDATE articles SET stock_total = ? WHERE id_shoes = ?")->execute([$stock, $id]);
        }

        $msg = "Article #$id créé.";
    }

    $pdo->commit();

    $api_url = getenv('ADMIN_API_URL') ?: 'http://admin-api:8001';
    $token   = getenv('ADMIN_ACTION_TOKEN') ?: '';
    $ch = curl_init("$api_url/admin/reindex");
    curl_setopt_array($ch, [
        CURLOPT_POST           => true,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 5,
        CURLOPT_HTTPHEADER     => ["X-Admin-Token: $token", "Content-Type: application/json"],
        CURLOPT_POSTFIELDS     => json_encode(['article_id' => $id]),
    ]);
    curl_exec($ch);
    curl_close($ch);

    echo json_encode(['success' => true, 'message' => $msg, 'id' => $id, 'stock_total' => $stock]);

} catch (PDOException $e) {
    $pdo->rollBack();
    echo json_encode(['success' => false, 'message' => 'Erreur BDD : ' . $e->getMessage()]);
}