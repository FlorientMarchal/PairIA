<?php
// admin/includes/admin_actions.php
// Fonctions PHP prédéfinies appelables par le chatbot admin.
// Chaque fonction retourne un tableau ['success' => bool, 'message' => string, 'data' => mixed]
// Le chatbot ne peut appeler QUE ces fonctions — jamais de SQL arbitraire.

require_once __DIR__ . '/../../includes/bd.php';


// Au tout début de admin_actions.php, avant tout le reste
if (isset($_SERVER['REQUEST_METHOD']) && $_SERVER['REQUEST_METHOD'] === 'POST') {
    if (session_status() === PHP_SESSION_NONE) session_start();
    
    $token_attendu = getenv('ADMIN_ACTION_TOKEN') ?: '';
    $token_recu    = $_SERVER['HTTP_X_ADMIN_TOKEN'] ?? '';

    // Double vérification : token ET session admin
    $token_ok   = $token_attendu && hash_equals($token_attendu, $token_recu);
    $session_ok = !empty($_SESSION['is_admin']);

    // Autorisé si token valide (appel interne depuis admin-api)
    // OU session admin valide (appel direct depuis PHP)
    if (!$token_ok && !$session_ok) {
        http_response_code(403);
        echo json_encode(['success' => false, 'message' => 'Non autorisé.']);
        exit;
    }
   


// ══════════════════════════════════════════════════════════════
// COMMANDES
// ══════════════════════════════════════════════════════════════

/**
 * Lister les commandes avec filtres optionnels.
 * @param string|null $statut    Filtre sur le statut ('en_attente','payée','expédiée','livrée','annulée')
 * @param int         $limit     Nombre max de résultats (défaut 20)
 * @param string|null $depuis    Date ISO 'YYYY-MM-DD' — commandes à partir de cette date
 */
function admin_lister_commandes(?string $statut = null, int $limit = 20, ?string $depuis = null): array {
    global $pdo;
    $where = ['1=1'];
    $params = [];

    if ($statut) {
        $where[] = 'c.statut = ?';
        $params[] = $statut;
    }
    if ($depuis) {
        $where[] = 'c.date_commande >= ?';
        $params[] = $depuis . ' 00:00:00';
    }

    $sql = "
        SELECT c.id_commande, c.date_commande, c.statut, c.total,
               c.stripe_statut, cl.nom, cl.prenom, cl.mail
        FROM commandes c
        JOIN clients cl ON cl.id_client = c.id_client
        WHERE " . implode(' AND ', $where) . "
        ORDER BY c.date_commande DESC
        LIMIT ?
    ";
    $params[] = $limit;

    $stmt = $pdo->prepare($sql);
    $stmt->execute($params);
    $rows = $stmt->fetchAll();

    return ['success' => true, 'message' => count($rows) . ' commande(s) trouvée(s).', 'data' => $rows];
}

/**
 * Détail d'une commande (lignes incluses).
 */
function admin_detail_commande(int $id_commande): array {
    global $pdo;

    $stmt = $pdo->prepare("
        SELECT c.*, cl.nom, cl.prenom, cl.mail, cl.numero
        FROM commandes c
        JOIN clients cl ON cl.id_client = c.id_client
        WHERE c.id_commande = ?
    ");
    $stmt->execute([$id_commande]);
    $commande = $stmt->fetch();
    if (!$commande) return ['success' => false, 'message' => "Commande #$id_commande introuvable.", 'data' => null];

    $stmt2 = $pdo->prepare("SELECT * FROM lignes_commande WHERE id_commande = ?");
    $stmt2->execute([$id_commande]);
    $commande['lignes'] = $stmt2->fetchAll();

    return ['success' => true, 'message' => "Commande #$id_commande récupérée.", 'data' => $commande];
}

/**
 * Modifier le statut d'une commande.
 * Statuts autorisés : en_attente | payée | expédiée | livrée | annulée
 */
function admin_modifier_statut_commande(int $id_commande, string $nouveau_statut): array {
    global $pdo;
    $statuts_ok = ['en_attente', 'payée', 'expédiée', 'livrée', 'annulée'];
    if (!in_array($nouveau_statut, $statuts_ok)) {
        return ['success' => false, 'message' => "Statut '$nouveau_statut' invalide. Valeurs : " . implode(', ', $statuts_ok), 'data' => null];
    }

    $stmt = $pdo->prepare("UPDATE commandes SET statut = ? WHERE id_commande = ?");
    $stmt->execute([$nouveau_statut, $id_commande]);

    if ($stmt->rowCount() === 0) {
        return ['success' => false, 'message' => "Commande #$id_commande introuvable.", 'data' => null];
    }
    return ['success' => true, 'message' => "Statut de la commande #$id_commande mis à jour : « $nouveau_statut ».", 'data' => null];
}

// ══════════════════════════════════════════════════════════════
// CATALOGUE / ARTICLES
// ══════════════════════════════════════════════════════════════

/**
 * Lister tous les articles avec leur stock.
 */
function admin_lister_articles(?string $categorie = null): array {
    global $pdo;
    $sql = "SELECT id_shoes, nom, categorie, marque, genre, Prix, stock_total FROM articles";
    $params = [];
    if ($categorie) {
        $sql .= " WHERE categorie = ?";
        $params[] = $categorie;
    }
    $sql .= " ORDER BY categorie, nom";
    $stmt = $pdo->prepare($sql);
    $stmt->execute($params);
    $rows = $stmt->fetchAll();
    return ['success' => true, 'message' => count($rows) . ' article(s).', 'data' => $rows];
}

/**
 * Modifier le prix d'un article.
 */
function admin_modifier_prix(int $id_shoes, float $nouveau_prix): array {
    global $pdo;
    if ($nouveau_prix <= 0) return ['success' => false, 'message' => 'Le prix doit être positif.', 'data' => null];

    $stmt = $pdo->prepare("UPDATE articles SET Prix = ? WHERE id_shoes = ?");
    $stmt->execute([$nouveau_prix, $id_shoes]);
    if ($stmt->rowCount() === 0) return ['success' => false, 'message' => "Article #$id_shoes introuvable.", 'data' => null];

    return ['success' => true, 'message' => "Prix de l'article #$id_shoes mis à jour : {$nouveau_prix}€.", 'data' => null];
}

/**
 * Modifier le stock total d'un article.
 */
function admin_modifier_stock(int $id_shoes, int $nouveau_stock): array {
    global $pdo;
    if ($nouveau_stock < 0) return ['success' => false, 'message' => 'Le stock ne peut pas être négatif.', 'data' => null];

    $stmt = $pdo->prepare("UPDATE articles SET stock_total = ? WHERE id_shoes = ?");
    $stmt->execute([$nouveau_stock, $id_shoes]);
    if ($stmt->rowCount() === 0) return ['success' => false, 'message' => "Article #$id_shoes introuvable.", 'data' => null];

    return ['success' => true, 'message' => "Stock de l'article #$id_shoes mis à jour : $nouveau_stock unités.", 'data' => null];
}

/**
 * Rechercher un article par nom ou marque.
 */
function admin_rechercher_article(string $query): array {
    global $pdo;
    $like = '%' . $query . '%';
    $stmt = $pdo->prepare("
        SELECT id_shoes, nom, categorie, marque, Prix, stock_total
        FROM articles
        WHERE nom LIKE ? OR marque LIKE ? OR categorie LIKE ?
        ORDER BY nom LIMIT 20
    ");
    $stmt->execute([$like, $like, $like]);
    $rows = $stmt->fetchAll();
    return ['success' => true, 'message' => count($rows) . ' résultat(s).', 'data' => $rows];
}

// ══════════════════════════════════════════════════════════════
// CLIENTS
// ══════════════════════════════════════════════════════════════

/**
 * Rechercher un client par nom, prénom ou email.
 */
function admin_rechercher_client(string $query): array {
    global $pdo;
    $like = '%' . $query . '%';
    $stmt = $pdo->prepare("
        SELECT id_client, nom, prenom, mail, numero
        FROM clients
        WHERE nom LIKE ? OR prenom LIKE ? OR mail LIKE ?
        ORDER BY nom LIMIT 20
    ");
    $stmt->execute([$like, $like, $like]);
    $rows = $stmt->fetchAll();
    return ['success' => true, 'message' => count($rows) . ' client(s) trouvé(s).', 'data' => $rows];
}

/**
 * Voir les commandes d'un client.
 */
function admin_commandes_client(int $id_client): array {
    global $pdo;
    $stmt = $pdo->prepare("
        SELECT id_commande, date_commande, statut, total
        FROM commandes WHERE id_client = ?
        ORDER BY date_commande DESC
    ");
    $stmt->execute([$id_client]);
    $rows = $stmt->fetchAll();
    return ['success' => true, 'message' => count($rows) . ' commande(s).', 'data' => $rows];
}

// ══════════════════════════════════════════════════════════════
// COMMENTAIRES
// ══════════════════════════════════════════════════════════════

/**
 * Lister les commentaires récents.
 */
function admin_lister_commentaires(int $limit = 30): array {
    global $pdo;
    $stmt = $pdo->prepare("
        SELECT cm.id_commentaire, cm.note, cm.contenu, cm.created_at,
               a.nom AS article, cl.nom AS client_nom, cl.prenom AS client_prenom
        FROM commentaires cm
        JOIN articles a  ON a.id_shoes   = cm.id_shoes
        JOIN clients cl  ON cl.id_client = cm.id_client
        ORDER BY cm.created_at DESC
        LIMIT ?
    ");
    $stmt->execute([$limit]);
    $rows = $stmt->fetchAll();
    return ['success' => true, 'message' => count($rows) . ' commentaire(s).', 'data' => $rows];
}

/**
 * Supprimer un commentaire.
 */
function admin_supprimer_commentaire(int $id_commentaire): array {
    global $pdo;
    $stmt = $pdo->prepare("DELETE FROM commentaires WHERE id_commentaire = ?");
    $stmt->execute([$id_commentaire]);
    if ($stmt->rowCount() === 0) return ['success' => false, 'message' => "Commentaire #$id_commentaire introuvable.", 'data' => null];
    return ['success' => true, 'message' => "Commentaire #$id_commentaire supprimé.", 'data' => null];
}

// ══════════════════════════════════════════════════════════════
// STATISTIQUES
// ══════════════════════════════════════════════════════════════

/**
 * Résumé global du site : CA total, nb commandes, nb clients, stock faible.
 */
function admin_stats_globales(): array {
    global $pdo;

    $ca = $pdo->query("SELECT COALESCE(SUM(total),0) FROM commandes WHERE statut != 'annulée'")->fetchColumn();
    $nb_commandes = $pdo->query("SELECT COUNT(*) FROM commandes")->fetchColumn();
    $nb_clients   = $pdo->query("SELECT COUNT(*) FROM clients")->fetchColumn();
    $nb_articles  = $pdo->query("SELECT COUNT(*) FROM articles")->fetchColumn();
    $stock_faible = $pdo->query("SELECT COUNT(*) FROM articles WHERE stock_total < 50")->fetchColumn();

    $stmt = $pdo->query("
        SELECT statut, COUNT(*) AS nb, SUM(total) AS ca
        FROM commandes
        GROUP BY statut
    ");
    $par_statut = $stmt->fetchAll();

    return [
        'success' => true,
        'message' => 'Statistiques globales récupérées.',
        'data' => [
            'ca_total'        => (float)$ca,
            'nb_commandes'    => (int)$nb_commandes,
            'nb_clients'      => (int)$nb_clients,
            'nb_articles'     => (int)$nb_articles,
            'stock_faible'    => (int)$stock_faible,
            'par_statut'      => $par_statut,
        ]
    ];
}

/**
 * Top 10 articles les plus vendus.
 */
function admin_top_articles(int $limit = 10): array {
    global $pdo;
    $stmt = $pdo->prepare("
        SELECT lc.id_shoes, lc.nom_article, SUM(lc.quantite) AS total_vendu, SUM(lc.sous_total) AS ca
        FROM lignes_commande lc
        JOIN commandes c ON c.id_commande = lc.id_commande
        WHERE c.statut != 'annulée'
        GROUP BY lc.id_shoes, lc.nom_article
        ORDER BY total_vendu DESC
        LIMIT ?
    ");
    $stmt->execute([$limit]);
    $rows = $stmt->fetchAll();
    return ['success' => true, 'message' => "Top $limit articles.", 'data' => $rows];
}

/**
 * Chiffre d'affaires par mois (12 derniers mois).
 */
function admin_ca_par_mois(): array {
    global $pdo;
    $stmt = $pdo->query("
        SELECT DATE_FORMAT(date_commande,'%Y-%m') AS mois,
               COUNT(*) AS nb_commandes,
               SUM(total) AS ca
        FROM commandes
        WHERE statut != 'annulée'
          AND date_commande >= DATE_SUB(NOW(), INTERVAL 12 MONTH)
        GROUP BY mois
        ORDER BY mois ASC
    ");
    $rows = $stmt->fetchAll();
    return ['success' => true, 'message' => 'CA sur 12 mois.', 'data' => $rows];
}

// ══════════════════════════════════════════════════════════════
// DISPATCHER — appelé par le endpoint FastAPI
// ══════════════════════════════════════════════════════════════

/**
 * Dispatch une action nommée avec ses paramètres.
 * Retourne JSON.
 */
function dispatch_action(string $action, array $params = []): string {
    $fn_map = [
        'lister_commandes'          => 'admin_lister_commandes',
        'detail_commande'           => 'admin_detail_commande',
        'modifier_statut_commande'  => 'admin_modifier_statut_commande',
        'lister_articles'           => 'admin_lister_articles',
        'modifier_prix'             => 'admin_modifier_prix',
        'modifier_stock'            => 'admin_modifier_stock',
        'rechercher_article'        => 'admin_rechercher_article',
        'rechercher_client'         => 'admin_rechercher_client',
        'commandes_client'          => 'admin_commandes_client',
        'lister_commentaires'       => 'admin_lister_commentaires',
        'supprimer_commentaire'     => 'admin_supprimer_commentaire',
        'stats_globales'            => 'admin_stats_globales',
        'top_articles'              => 'admin_top_articles',
        'ca_par_mois'               => 'admin_ca_par_mois',
    ];

    if (!isset($fn_map[$action])) {
        return json_encode(['success' => false, 'message' => "Action inconnue : $action", 'data' => null]);
    }

    $fn = $fn_map[$action];
    try {
        $result = call_user_func_array($fn, array_values($params));
    } catch (Throwable $e) {
        $result = ['success' => false, 'message' => 'Erreur interne : ' . $e->getMessage(), 'data' => null];
    }
    return json_encode($result, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
}

// ── Point d'entrée HTTP (appelé par le serveur FastAPI via HTTP) ──────────────
if (isset($_SERVER['REQUEST_METHOD']) && $_SERVER['REQUEST_METHOD'] === 'POST') {
    // Sécurité minimale : token partagé avec FastAPI
    $token_attendu = getenv('ADMIN_ACTION_TOKEN') ?: 'pairia_admin_secret_2024';
    $token_recu    = $_SERVER['HTTP_X_ADMIN_TOKEN'] ?? '';

    if (!hash_equals($token_attendu, $token_recu)) {
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
}