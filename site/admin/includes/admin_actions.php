<?php
// admin/includes/admin_actions.php
// Fonctions PHP prédéfinies appelables par le chatbot admin.

require_once __DIR__ . '/../../includes/bd.php';

// ══════════════════════════════════════════════════════════════
// COMMANDES
// ══════════════════════════════════════════════════════════════

function admin_lister_commandes(?string $statut = null, int $limit = 20, ?string $depuis = null): array {
    global $pdo;
    $where = ['1=1']; $params = [];
    if ($statut) { $where[] = 'c.statut = ?'; $params[] = $statut; }
    if ($depuis) { $where[] = 'c.date_commande >= ?'; $params[] = $depuis . ' 00:00:00'; }
    $sql = "SELECT c.id_commande, c.date_commande, c.statut, c.total,
                   c.stripe_statut, cl.nom, cl.prenom, cl.mail
            FROM commandes c JOIN clients cl ON cl.id_client = c.id_client
            WHERE " . implode(' AND ', $where) . " ORDER BY c.date_commande DESC LIMIT ?";
    $params[] = $limit;
    $stmt = $pdo->prepare($sql); $stmt->execute($params);
    $rows = $stmt->fetchAll();
    return ['success' => true, 'message' => count($rows) . ' commande(s).', 'data' => $rows];
}

function admin_detail_commande(int $id_commande): array {
    global $pdo;
    $stmt = $pdo->prepare("SELECT c.*, cl.nom, cl.prenom, cl.mail, cl.numero FROM commandes c JOIN clients cl ON cl.id_client = c.id_client WHERE c.id_commande = ?");
    $stmt->execute([$id_commande]);
    $commande = $stmt->fetch();
    if (!$commande) return ['success' => false, 'message' => "Commande #$id_commande introuvable.", 'data' => null];
    $stmt2 = $pdo->prepare("SELECT * FROM lignes_commande WHERE id_commande = ?");
    $stmt2->execute([$id_commande]);
    $commande['lignes'] = $stmt2->fetchAll();
    return ['success' => true, 'message' => "Commande #$id_commande récupérée.", 'data' => $commande];
}

function admin_modifier_statut_commande(int $id_commande, string $nouveau_statut): array {
    global $pdo;
    $statuts_ok = ['en_attente', 'payée', 'expédiée', 'livrée', 'annulée'];
    if (!in_array($nouveau_statut, $statuts_ok)) {
        return ['success' => false, 'message' => "Statut '$nouveau_statut' invalide.", 'data' => null];
    }
    $stmt = $pdo->prepare("UPDATE commandes SET statut = ? WHERE id_commande = ?");
    $stmt->execute([$nouveau_statut, $id_commande]);
    if ($stmt->rowCount() === 0) return ['success' => false, 'message' => "Commande #$id_commande introuvable.", 'data' => null];
    return ['success' => true, 'message' => "Commande #$id_commande → « $nouveau_statut ».", 'data' => null];
}

function admin_detail_article(int $id_shoes): array {
    global $pdo;
    $stmt = $pdo->prepare("SELECT * FROM articles WHERE id_shoes = ?");
    $stmt->execute([$id_shoes]);
    $row = $stmt->fetch();
    if (!$row) return ['success' => false, 'message' => "Article #$id_shoes introuvable.", 'data' => null];
    return ['success' => true, 'message' => "Article #$id_shoes récupéré.", 'data' => $row];
}

function admin_modifier_statut_batch(array $ids, string $nouveau_statut): array {
    global $pdo;
    $statuts_ok = ['en_attente', 'payée', 'expédiée', 'livrée', 'annulée'];
    if (!in_array($nouveau_statut, $statuts_ok)) {
        return ['success' => false, 'message' => "Statut '$nouveau_statut' invalide.", 'data' => null];
    }
    if (empty($ids)) return ['success' => false, 'message' => 'Aucun ID fourni.', 'data' => null];
    $placeholders = implode(',', array_fill(0, count($ids), '?'));
    $params = array_merge([$nouveau_statut], array_map('intval', $ids));
    $stmt = $pdo->prepare("UPDATE commandes SET statut = ? WHERE id_commande IN ($placeholders)");
    $stmt->execute($params);
    return ['success' => true, 'message' => $stmt->rowCount() . " commande(s) passée(s) en « $nouveau_statut ».", 'data' => null];
}

// ══════════════════════════════════════════════════════════════
// CATALOGUE
// ══════════════════════════════════════════════════════════════

function admin_lister_articles(?string $categorie = null): array {
    global $pdo;
    $sql = "SELECT a.id_shoes, a.nom, a.categorie, a.marque, a.genre, a.Prix,
                   COALESCE(SUM(sc.stock),0) AS stock_total
            FROM articles a LEFT JOIN size_color sc ON sc.id_shoes = a.id_shoes";
    $params = [];
    if ($categorie) { $sql .= " WHERE a.categorie = ?"; $params[] = $categorie; }
    $sql .= " GROUP BY a.id_shoes ORDER BY a.categorie, a.nom";
    $stmt = $pdo->prepare($sql); $stmt->execute($params);
    $rows = $stmt->fetchAll();
    return ['success' => true, 'message' => count($rows) . ' article(s).', 'data' => $rows];
}

function admin_lister_articles_stock_faible(int $seuil = 20): array {
    global $pdo;
    $stmt = $pdo->prepare("
        SELECT a.id_shoes, a.nom, a.categorie, a.marque, a.Prix,
               COALESCE(SUM(sc.stock),0) AS stock_total
        FROM articles a LEFT JOIN size_color sc ON sc.id_shoes = a.id_shoes
        GROUP BY a.id_shoes HAVING stock_total <= ? ORDER BY stock_total ASC
    ");
    $stmt->execute([$seuil]);
    $rows = $stmt->fetchAll();
    return ['success' => true, 'message' => count($rows) . " article(s) avec stock ≤ $seuil.", 'data' => $rows];
}

// Remplace la fonction admin_rechercher_article dans admin_actions.php

function admin_rechercher_article(string $query): array {
    // Essaie d'abord via le RAG sémantique (Qdrant)
    $api_url = getenv('CLIENT_API_URL') ?: 'http://api:8000';
    $token   = getenv('ADMIN_ACTION_TOKEN') ?: '';

    $ch = curl_init("$api_url/admin/search-article");
    curl_setopt_array($ch, [
        CURLOPT_POST           => true,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 30,
        CURLOPT_HTTPHEADER     => ["X-Admin-Token: $token", "Content-Type: application/json"],
        CURLOPT_POSTFIELDS     => json_encode(['query' => $query, 'limit' => 5]),
    ]);
    $response = curl_exec($ch);
    $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    if ($http_code === 200 && $response) {
        $data = json_decode($response, true);
        if ($data && $data['success'] && !empty($data['data'])) {
            return ['success' => true, 'message' => count($data['data']) . ' résultat(s).', 'data' => $data['data']];
        }
    }

    // Fallback SQL si le RAG échoue
    global $pdo;
    $like = '%' . $query . '%';
    $stmt = $pdo->prepare("
        SELECT a.id_shoes, a.nom, a.categorie, a.marque, a.Prix,
               COALESCE(SUM(sc.stock),0) AS stock_total
        FROM articles a LEFT JOIN size_color sc ON sc.id_shoes = a.id_shoes
        WHERE a.nom LIKE ? OR a.marque LIKE ? OR a.categorie LIKE ?
        GROUP BY a.id_shoes ORDER BY a.nom LIMIT 20
    ");
    $stmt->execute([$like, $like, $like]);
    $rows = $stmt->fetchAll();
    return ['success' => true, 'message' => count($rows) . ' résultat(s) (SQL).', 'data' => $rows];
}

function admin_modifier_prix(int $id_shoes, float $nouveau_prix): array {
    global $pdo;
    if ($nouveau_prix <= 0) return ['success' => false, 'message' => 'Prix invalide.', 'data' => null];
    $stmt = $pdo->prepare("UPDATE articles SET Prix = ? WHERE id_shoes = ?");
    $stmt->execute([$nouveau_prix, $id_shoes]);
    if ($stmt->rowCount() === 0) return ['success' => false, 'message' => "Article #$id_shoes introuvable.", 'data' => null];
    return ['success' => true, 'message' => "Prix de #$id_shoes mis à jour : {$nouveau_prix}€.", 'data' => null];
}

function admin_modifier_stock(int $id_shoes, int $nouveau_stock): array {
    global $pdo;
    if ($nouveau_stock < 0) return ['success' => false, 'message' => 'Stock invalide.', 'data' => null];
    $stmt = $pdo->prepare("UPDATE articles SET stock_total = ? WHERE id_shoes = ?");
    $stmt->execute([$nouveau_stock, $id_shoes]);
    if ($stmt->rowCount() === 0) return ['success' => false, 'message' => "Article #$id_shoes introuvable.", 'data' => null];
    return ['success' => true, 'message' => "Stock de #$id_shoes mis à jour : $nouveau_stock.", 'data' => null];
}

function admin_modifier_prix_batch(
    string $filtre_type,   // 'categorie' | 'marque' | 'genre' | 'tous'
    string $filtre_valeur, // valeur du filtre (ignoré si 'tous')
    string $type_modif,    // 'pourcentage' | 'fixe' | 'nouveau_prix'
    float  $valeur
): array {
    global $pdo;

    // Construction du WHERE
    $where = '1=1'; $params = [];
    if ($filtre_type !== 'tous' && $filtre_valeur) {
        $cols = ['categorie' => 'categorie', 'marque' => 'marque', 'genre' => 'genre'];
        if (!isset($cols[$filtre_type])) return ['success' => false, 'message' => "Filtre '$filtre_type' invalide.", 'data' => null];
        $where = $cols[$filtre_type] . ' = ?';
        $params[] = $filtre_valeur;
    }

    // Construction du SET
    if ($type_modif === 'pourcentage') {
        $set = 'Prix = ROUND(Prix * (1 + ? / 100), 2)';
    } elseif ($type_modif === 'fixe') {
        $set = 'Prix = ROUND(GREATEST(Prix + ?, 0.01), 2)';
    } elseif ($type_modif === 'nouveau_prix') {
        $set = 'Prix = ?';
    } else {
        return ['success' => false, 'message' => "Type de modification '$type_modif' invalide.", 'data' => null];
    }

    array_unshift($params, $valeur);
    $stmt = $pdo->prepare("UPDATE articles SET $set WHERE $where");
    $stmt->execute($params);

    $desc = $type_modif === 'pourcentage' ? ($valeur >= 0 ? "+$valeur%" : "$valeur%")
          : ($type_modif === 'fixe' ? ($valeur >= 0 ? "+{$valeur}€" : "{$valeur}€") : "{$valeur}€ fixe");
    $scope = $filtre_type === 'tous' ? 'tout le catalogue' : "$filtre_type = $filtre_valeur";

    return ['success' => true, 'message' => "{$stmt->rowCount()} article(s) modifié(s) — $scope → $desc.", 'data' => null];
}

function admin_modifier_article(int $id_shoes, array $champs): array {
    global $pdo;
    $allowed = ['nom', 'categorie', 'marque', 'genre', 'Prix', 'description',
                'caracteristiques', 'materiaux', 'usage', 'mots_cles', 'url_image'];
    $sets = []; $params = [];
    foreach ($champs as $k => $v) {
        if (!in_array($k, $allowed)) continue;
        $col = $k === 'Prix' ? 'Prix' : $k;
        $sets[] = "`$col` = ?";
        $params[] = $v;
    }
    if (empty($sets)) return ['success' => false, 'message' => 'Aucun champ valide fourni.', 'data' => null];
    $params[] = $id_shoes;
    $stmt = $pdo->prepare("UPDATE articles SET " . implode(', ', $sets) . " WHERE id_shoes = ?");
    $stmt->execute($params);
    if ($stmt->rowCount() === 0) return ['success' => false, 'message' => "Article #$id_shoes introuvable.", 'data' => null];
    return ['success' => true, 'message' => "Article #$id_shoes mis à jour.", 'data' => null];
}

function admin_ajouter_article(
    string $nom, string $categorie, string $marque, string $genre,
    float $prix, string $description = '', string $caracteristiques = '',
    string $materiaux = '', string $usage = '', string $mots_cles = '',
    string $url_image = '', array $variants = []
): array {
    global $pdo;
    if (!$nom || !$categorie || !$marque || $prix <= 0) {
        return ['success' => false, 'message' => 'Champs obligatoires manquants.', 'data' => null];
    }
    try {
        $pdo->beginTransaction();
        $stmt = $pdo->prepare("
            INSERT INTO articles (nom, categorie, marque, genre, Prix, stock_total, description,
                                  caracteristiques, materiaux, `usage`, mots_cles, url_image)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?)
        ");
        $stmt->execute([$nom, $categorie, $marque, $genre, $prix,
                        $description, $caracteristiques, $materiaux, $usage, $mots_cles, $url_image]);
        $id = (int)$pdo->lastInsertId();

        $stock_total = 0;
        if (!empty($variants)) {
            $max_id = (int)$pdo->query("SELECT COALESCE(MAX(id_variant),0) FROM size_color")->fetchColumn();
            $stmt_v = $pdo->prepare("INSERT INTO size_color (id_variant,id_shoes,taille,couleur,stock) VALUES (?,?,?,?,?)");
            foreach ($variants as $v) {
                $taille  = (int)($v['taille']  ?? 0);
                $couleur = trim($v['couleur']  ?? '');
                $stk     = (int)($v['stock']   ?? 10);
                if (!$taille || !$couleur) continue;
                $max_id++;
                $stmt_v->execute([$max_id, $id, $taille, $couleur, $stk]);
                $stock_total += $stk;
            }
            $pdo->prepare("UPDATE articles SET stock_total = ? WHERE id_shoes = ?")->execute([$stock_total, $id]);
        }
        $pdo->commit();
        return ['success' => true, 'message' => "Article « $nom » créé avec l'ID #$id.", 'data' => ['id_shoes' => $id]];
    } catch (PDOException $e) {
        $pdo->rollBack();
        return ['success' => false, 'message' => 'Erreur BDD : ' . $e->getMessage(), 'data' => null];
    }
}

function admin_supprimer_article(int $id_shoes): array {
    global $pdo;
    $pdo->prepare("DELETE FROM size_color WHERE id_shoes = ?")->execute([$id_shoes]);
    $stmt = $pdo->prepare("DELETE FROM articles WHERE id_shoes = ?");
    $stmt->execute([$id_shoes]);
    if ($stmt->rowCount() === 0) return ['success' => false, 'message' => "Article #$id_shoes introuvable.", 'data' => null];
    return ['success' => true, 'message' => "Article #$id_shoes supprimé.", 'data' => null];
}

// ══════════════════════════════════════════════════════════════
// CLIENTS
// ══════════════════════════════════════════════════════════════

function admin_lister_clients(int $limit = 50): array {
    global $pdo;
    $stmt = $pdo->prepare("
        SELECT c.id_client, c.nom, c.prenom, c.mail, c.numero,
               COUNT(cm.id_commande) AS nb_commandes,
               COALESCE(SUM(cm.total),0) AS ca_total
        FROM clients c LEFT JOIN commandes cm ON cm.id_client = c.id_client
        GROUP BY c.id_client ORDER BY ca_total DESC LIMIT ?
    ");
    $stmt->execute([$limit]);
    $rows = $stmt->fetchAll();
    return ['success' => true, 'message' => count($rows) . ' client(s).', 'data' => $rows];
}

function admin_rechercher_client(string $query): array {
    global $pdo;
    $like = '%' . $query . '%';
    $stmt = $pdo->prepare("
        SELECT id_client, nom, prenom, mail, numero
        FROM clients
        WHERE nom LIKE ? OR prenom LIKE ? OR mail LIKE ?
           OR CONCAT(prenom,' ',nom) LIKE ? OR CONCAT(nom,' ',prenom) LIKE ?
        ORDER BY nom LIMIT 20
    ");
    $stmt->execute([$like, $like, $like, $like, $like]);
    $rows = $stmt->fetchAll();
    return ['success' => true, 'message' => count($rows) . ' client(s).', 'data' => $rows];
}

function admin_commandes_client(int $id_client): array {
    global $pdo;
    $stmt = $pdo->prepare("SELECT id_commande,date_commande,statut,total FROM commandes WHERE id_client=? ORDER BY date_commande DESC");
    $stmt->execute([$id_client]);
    $rows = $stmt->fetchAll();
    return ['success' => true, 'message' => count($rows) . ' commande(s).', 'data' => $rows];
}

function admin_clients_top(int $limit = 10): array {
    global $pdo;
    $stmt = $pdo->prepare("
        SELECT c.id_client, c.nom, c.prenom, c.mail,
               COUNT(cm.id_commande) AS nb_commandes,
               COALESCE(SUM(cm.total),0) AS ca_total
        FROM clients c JOIN commandes cm ON cm.id_client = c.id_client
        WHERE cm.statut != 'annulée'
        GROUP BY c.id_client ORDER BY ca_total DESC LIMIT ?
    ");
    $stmt->execute([$limit]);
    $rows = $stmt->fetchAll();
    return ['success' => true, 'message' => "Top $limit clients.", 'data' => $rows];
}

// ══════════════════════════════════════════════════════════════
// COMMENTAIRES
// ══════════════════════════════════════════════════════════════

function admin_lister_commentaires(int $limit = 30): array {
    global $pdo;
    $stmt = $pdo->prepare("
        SELECT cm.id_commentaire, cm.note, cm.contenu, cm.created_at,
               a.nom AS article, cl.nom AS client_nom, cl.prenom AS client_prenom
        FROM commentaires cm
        JOIN articles a  ON a.id_shoes   = cm.id_shoes
        JOIN clients cl  ON cl.id_client = cm.id_client
        ORDER BY cm.created_at DESC LIMIT ?
    ");
    $stmt->execute([$limit]);
    $rows = $stmt->fetchAll();
    return ['success' => true, 'message' => count($rows) . ' commentaire(s).', 'data' => $rows];
}

function admin_supprimer_commentaire(int $id_commentaire): array {
    global $pdo;
    $stmt = $pdo->prepare("DELETE FROM commentaires WHERE id_commentaire = ?");
    $stmt->execute([$id_commentaire]);
    if ($stmt->rowCount() === 0) return ['success' => false, 'message' => "Commentaire #$id_commentaire introuvable.", 'data' => null];
    return ['success' => true, 'message' => "Commentaire #$id_commentaire supprimé.", 'data' => null];
}

function admin_supprimer_commentaires_article(int $id_shoes): array {
    global $pdo;
    $stmt = $pdo->prepare("DELETE FROM commentaires WHERE id_shoes = ?");
    $stmt->execute([$id_shoes]);
    return ['success' => true, 'message' => $stmt->rowCount() . " commentaire(s) supprimé(s) pour l'article #$id_shoes.", 'data' => null];
}

// ══════════════════════════════════════════════════════════════
// STATISTIQUES
// ══════════════════════════════════════════════════════════════

function admin_stats_globales(): array {
    global $pdo;
    $ca           = $pdo->query("SELECT COALESCE(SUM(total),0) FROM commandes WHERE statut != 'annulée'")->fetchColumn();
    $nb_commandes = $pdo->query("SELECT COUNT(*) FROM commandes")->fetchColumn();
    $nb_clients   = $pdo->query("SELECT COUNT(*) FROM clients")->fetchColumn();
    $nb_articles  = $pdo->query("SELECT COUNT(*) FROM articles")->fetchColumn();
    $stock_faible = $pdo->query("SELECT COUNT(*) FROM (SELECT id_shoes FROM size_color GROUP BY id_shoes HAVING SUM(stock) < 20) t")->fetchColumn();
    $par_statut   = $pdo->query("SELECT statut, COUNT(*) AS nb, SUM(total) AS ca FROM commandes GROUP BY statut")->fetchAll();
    return ['success' => true, 'message' => 'Statistiques globales.', 'data' => [
        'ca_total' => (float)$ca, 'nb_commandes' => (int)$nb_commandes,
        'nb_clients' => (int)$nb_clients, 'nb_articles' => (int)$nb_articles,
        'stock_faible' => (int)$stock_faible, 'par_statut' => $par_statut,
    ]];
}

function admin_stats_par_categorie(): array {
    global $pdo;
    $stmt = $pdo->query("
        SELECT a.categorie,
               COUNT(DISTINCT a.id_shoes) AS nb_articles,
               COALESCE(SUM(lc.quantite),0) AS total_vendu,
               COALESCE(SUM(lc.sous_total),0) AS ca
        FROM articles a
        LEFT JOIN lignes_commande lc ON lc.id_shoes = a.id_shoes
        LEFT JOIN commandes c ON c.id_commande = lc.id_commande AND c.statut != 'annulée'
        GROUP BY a.categorie ORDER BY ca DESC
    ");
    $rows = $stmt->fetchAll();
    return ['success' => true, 'message' => 'Stats par catégorie.', 'data' => $rows];
}

function admin_top_articles(int $limit = 10): array {
    global $pdo;
    $stmt = $pdo->prepare("
        SELECT lc.id_shoes, lc.nom_article, SUM(lc.quantite) AS total_vendu, SUM(lc.sous_total) AS ca
        FROM lignes_commande lc JOIN commandes c ON c.id_commande = lc.id_commande
        WHERE c.statut != 'annulée'
        GROUP BY lc.id_shoes, lc.nom_article ORDER BY total_vendu DESC LIMIT ?
    ");
    $stmt->execute([$limit]);
    $rows = $stmt->fetchAll();
    return ['success' => true, 'message' => "Top $limit articles.", 'data' => $rows];
}

function admin_ca_par_mois(): array {
    global $pdo;
    $stmt = $pdo->query("
        SELECT DATE_FORMAT(date_commande,'%Y-%m') AS mois,
               COUNT(*) AS nb_commandes, SUM(total) AS ca
        FROM commandes WHERE statut != 'annulée'
          AND date_commande >= DATE_SUB(NOW(), INTERVAL 12 MONTH)
        GROUP BY mois ORDER BY mois ASC
    ");
    $rows = $stmt->fetchAll();
    return ['success' => true, 'message' => 'CA sur 12 mois.', 'data' => $rows];
}

function admin_arrondir_prix(string $methode = 'nearest', ?string $filtre_type = null, ?string $filtre_valeur = null): array {
    global $pdo;
    // methode: 'nearest' (arrondi), 'up' (plafond), 'down' (plancher), 'half' (x.50)
    $formulas = [
        'nearest' => 'ROUND(Prix)',
        'up'      => 'CEILING(Prix)',
        'down'    => 'FLOOR(Prix)',
        'half'    => 'FLOOR(Prix) + 0.5',
        'nine'    => 'CEILING(Prix) - 0.01',  // ex: 79.99
    ];
    $formula = $formulas[$methode] ?? 'ROUND(Prix)';
    $where = '1=1'; $params = [];
    if ($filtre_type && $filtre_valeur && $filtre_type !== 'tous') {
        $where = "`$filtre_type` = ?";
        $params[] = $filtre_valeur;
    }
    $stmt = $pdo->prepare("UPDATE articles SET Prix = $formula WHERE $where");
    $stmt->execute($params);
    return ['success' => true, 'message' => $stmt->rowCount() . " article(s) arrondis ($methode).", 'data' => null];
}

// ══════════════════════════════════════════════════════════════
// DISPATCHER
// ══════════════════════════════════════════════════════════════

function dispatch_action(string $action, array $params = []): string {
    $fn_map = [
        'lister_commandes'              => 'admin_lister_commandes',
        'detail_commande'               => 'admin_detail_commande',
        'modifier_statut_commande'      => 'admin_modifier_statut_commande',
        'modifier_statut_batch'         => 'admin_modifier_statut_batch',
        'lister_articles'               => 'admin_lister_articles',
        'lister_articles_stock_faible'  => 'admin_lister_articles_stock_faible',
        'rechercher_article'            => 'admin_rechercher_article',
        'modifier_prix'                 => 'admin_modifier_prix',
        'modifier_stock'                => 'admin_modifier_stock',
        'modifier_prix_batch'           => 'admin_modifier_prix_batch',
        'modifier_article'              => 'admin_modifier_article',
        'ajouter_article'               => 'admin_ajouter_article',
        'supprimer_article'             => 'admin_supprimer_article',
        'lister_clients'                => 'admin_lister_clients',
        'rechercher_client'             => 'admin_rechercher_client',
        'commandes_client'              => 'admin_commandes_client',
        'clients_top'                   => 'admin_clients_top',
        'lister_commentaires'           => 'admin_lister_commentaires',
        'supprimer_commentaire'         => 'admin_supprimer_commentaire',
        'supprimer_commentaires_article'=> 'admin_supprimer_commentaires_article',
        'stats_globales'                => 'admin_stats_globales',
        'stats_par_categorie'           => 'admin_stats_par_categorie',
        'top_articles'                  => 'admin_top_articles',
        'ca_par_mois'                   => 'admin_ca_par_mois',
        'arrondir_prix'                 => 'admin_arrondir_prix',
        'detail_article'                => 'admin_detail_article',
    ];

    // Cast des types courants
    $int_params   = ['id_commande','id_shoes','id_client','id_commentaire','limit','nouveau_stock','seuil'];
    $float_params = ['nouveau_prix','valeur','prix'];
    foreach ($params as $k => $v) {
        if (in_array($k, $int_params))   $params[$k] = (int)$v;
        if (in_array($k, $float_params)) $params[$k] = (float)$v;
    }

    if (!isset($fn_map[$action])) {
        return json_encode(['success' => false, 'message' => "Action inconnue : $action", 'data' => null]);
    }

    $fn = $fn_map[$action];
    try {
        // Fonctions avec paramètres nommés complexes
        if ($action === 'modifier_prix_batch') {
            $result = admin_modifier_prix_batch(
                $params['filtre_type']   ?? 'tous',
                $params['filtre_valeur'] ?? '',
                $params['type_modif']    ?? 'pourcentage',
                $params['valeur']        ?? 0
            );
        } elseif ($action === 'modifier_article') {
            $champs = $params;
            unset($champs['id_shoes']);
            $result = admin_modifier_article((int)($params['id_shoes'] ?? 0), $champs);
        } elseif ($action === 'ajouter_article') {
            $result = admin_ajouter_article(
                $params['nom']              ?? '',
                $params['categorie']        ?? '',
                $params['marque']           ?? '',
                $params['genre']            ?? 'Mixte',
                (float)($params['prix']     ?? 0),
                $params['description']      ?? '',
                $params['caracteristiques'] ?? '',
                $params['materiaux']        ?? '',
                $params['usage']            ?? '',
                $params['mots_cles']        ?? '',
                $params['url_image']        ?? '',
                $params['variants']         ?? []
            );
        } elseif ($action === 'modifier_statut_batch') {
            $result = admin_modifier_statut_batch(
                $params['ids']            ?? [],
                $params['nouveau_statut'] ?? ''
            );
        } else {
            $result = call_user_func_array($fn, array_values($params));
        }
    } catch (Throwable $e) {
        $result = ['success' => false, 'message' => 'Erreur interne : ' . $e->getMessage(), 'data' => null];
    }
    return json_encode($result, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
}

// Point d'entrée HTTP
if (isset($_SERVER['REQUEST_METHOD']) && $_SERVER['REQUEST_METHOD'] === 'POST') {
    if (session_status() === PHP_SESSION_NONE) session_start();

    $token_attendu = getenv('ADMIN_ACTION_TOKEN') ?: '';
    $token_recu    = $_SERVER['HTTP_X_ADMIN_TOKEN'] ?? '';
    $token_ok      = $token_attendu && hash_equals($token_attendu, $token_recu);
    $session_ok    = !empty($_SESSION['is_admin']);

    if (!$token_ok && !$session_ok) {
        http_response_code(403);
        echo json_encode(['success' => false, 'message' => 'Non autorisé.']);
        exit;
    }

    $body   = json_decode(file_get_contents('php://input'), true) ?? [];
    $action = $body['action'] ?? '';
    $params = $body['params'] ?? [];

    header('Content-Type: application/json; charset=utf-8');
    echo dispatch_action($action, $params);
    exit;
}
