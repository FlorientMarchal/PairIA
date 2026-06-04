<?php
// admin/index.php
require_once 'includes/auth_admin.php';
require_once '../includes/bd.php';

// Stats rapides pour le dashboard
$ca_total     = $pdo->query("SELECT COALESCE(SUM(total),0) FROM commandes WHERE statut != 'annulée'")->fetchColumn();
$nb_attente   = $pdo->query("SELECT COUNT(*) FROM commandes WHERE statut = 'en_attente'")->fetchColumn();
$nb_clients   = $pdo->query("SELECT COUNT(*) FROM clients")->fetchColumn();
$nb_articles  = $pdo->query("SELECT COUNT(*) FROM articles")->fetchColumn();
?>
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PairIA Admin</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700;1,600&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="styles/admin.css">
  <link rel="stylesheet" href="styles/admin_extra.css">

</head>
<body>

<!-- ── SIDEBAR ── -->
<aside class="sidebar" id="sidebar">
  <div class="sidebar-logo">
    <span class="logo-pair">Pair</span><span class="logo-ia">IA</span>
    <span class="logo-admin-badge">Admin</span>
  </div>

  <nav class="sidebar-nav">
    <div class="nav-section-label">Principal</div>
    <a href="#" class="nav-item active" data-section="dashboard">
      <span class="nav-icon">◈</span> Dashboard
    </a>
    <a href="#" class="nav-item" data-section="commandes">
      <span class="nav-icon">📦</span> Commandes
    </a>
    <a href="#" class="nav-item" data-section="catalogue">
      <span class="nav-icon">👟</span> Catalogue
    </a>
    <a href="#" class="nav-item" data-section="clients">
      <span class="nav-icon">👤</span> Clients
    </a>
    <a href="#" class="nav-item" data-section="commentaires">
      <span class="nav-icon">💬</span> Commentaires
    </a>

    <div class="nav-section-label" style="margin-top:1.5rem">Compte</div>
    <a href="deconnexion_admin.php" class="nav-item nav-logout">
      <span class="nav-icon">⎋</span> Déconnexion
    </a>
  </nav>

  <div class="sidebar-admin-info">
    <div class="admin-avatar">⚙</div>
    <div>
      <div class="admin-name"><?= htmlspecialchars(($_SESSION['client']['prenom'] ?? '') . ' ' . ($_SESSION['client']['nom'] ?? '')) ?></div>      <div class="admin-role">Administrateur</div>
    </div>
  </div>
</aside>

<!-- ── CONTENU PRINCIPAL ── -->
<main class="admin-main" id="admin-main">

  <!-- TOP BAR -->
  <header class="topbar">
    <button class="topbar-burger" onclick="toggleSidebar()" aria-label="Menu">☰</button>
    <div class="topbar-title" id="topbar-title">Dashboard</div>
    <div class="topbar-right">
      <a href="../index.php" class="topbar-link" target="_blank">← Voir la boutique</a>
    </div>
  </header>

  <!-- SECTION : DASHBOARD -->
  <section class="section active" id="section-dashboard">

    <div class="section-header">
      <h1 class="section-title">Tableau de bord</h1>
      <p class="section-sub">Vue d'ensemble de la boutique PairIA</p>
    </div>

    <!-- KPI CARDS -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-icon" style="background:#fff8f0;color:#d4854a">💰</div>
        <div class="kpi-body">
          <div class="kpi-value"><?= number_format((float)$ca_total, 2, ',', ' ') ?> €</div>
          <div class="kpi-label">Chiffre d'affaires total</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon" style="background:#fff3e0;color:#e67e22">📦</div>
        <div class="kpi-body">
          <div class="kpi-value"><?= (int)$nb_attente ?></div>
          <div class="kpi-label">Commandes en attente</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon" style="background:#e8f5e9;color:#27ae60">👤</div>
        <div class="kpi-body">
          <div class="kpi-value"><?= (int)$nb_clients ?></div>
          <div class="kpi-label">Clients inscrits</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon" style="background:#e8eaf6;color:#3949ab">👟</div>
        <div class="kpi-body">
          <div class="kpi-value"><?= (int)$nb_articles ?></div>
          <div class="kpi-label">Articles au catalogue</div>
        </div>
      </div>
    </div>

    <!-- INTRO CHATBOT -->
    <div class="chat-promo-banner">
      <div class="chat-promo-icon">⚙</div>
      <div class="chat-promo-text">
        <strong>Assistant Admin IA</strong>
        Posez une question en langage naturel : gérez commandes, catalogue, clients et stats sans naviguer dans des menus.
      </div>
      <button class="chat-promo-btn" onclick="focusChatInput()">Ouvrir l'assistant →</button>
    </div>

    <!-- DERNIÈRES COMMANDES -->
    <div class="table-card">
      <div class="table-card-head">
        <h2 class="table-card-title">Dernières commandes</h2>
        <a href="#" class="table-see-all" data-section="commandes">Voir tout →</a>
      </div>
      <div class="table-wrap">
        <table class="admin-table" id="recent-orders-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Client</th>
              <th>Date</th>
              <th>Total</th>
              <th>Statut</th>
            </tr>
          </thead>
          <tbody>
            <?php
            $stmt = $pdo->query("
                SELECT c.id_commande, c.date_commande, c.statut, c.total,
                       cl.nom, cl.prenom
                FROM commandes c
                JOIN clients cl ON cl.id_client = c.id_client
                ORDER BY c.date_commande DESC LIMIT 8
            ");
            foreach ($stmt->fetchAll() as $row): ?>
            <tr>
              <td><span class="order-id">#<?= $row['id_commande'] ?></span></td>
              <td><?= htmlspecialchars($row['prenom'] . ' ' . $row['nom']) ?></td>
              <td><?= date('d/m/Y H:i', strtotime($row['date_commande'])) ?></td>
              <td class="order-total"><?= number_format((float)$row['total'], 2, ',', ' ') ?> €</td>
              <td><span class="status-badge status-<?= $row['statut'] ?>"><?= $row['statut'] ?></span></td>
            </tr>
            <?php endforeach; ?>
          </tbody>
        </table>
      </div>
    </div>

  </section>

  <!-- SECTION : COMMANDES -->
  <section class="section" id="section-commandes">
    <div class="section-header">
      <h1 class="section-title">Commandes</h1>
      <p class="section-sub">Gérez les commandes via l'assistant ou directement</p>
    </div>
    <div class="chat-promo-banner">
      <div class="chat-promo-icon">💡</div>
      <div class="chat-promo-text">
        Essayez : <em>"Liste les commandes expédiées de cette semaine"</em> ou <em>"Passe la commande #42 en livrée"</em>
      </div>
      <button class="chat-promo-btn" onclick="adminChatAsk('Liste les commandes en attente')">Voir les commandes en attente →</button>
    </div>
    <div class="table-card" id="commandes-table-card">
      <div class="table-card-head">
        <h2 class="table-card-title">Toutes les commandes</h2>
        <div class="table-filters">
          <select id="filter-statut" onchange="loadCommandes()">
            <option value="">Tous les statuts</option>
            <option value="en_attente">En attente</option>
            <option value="payée">Payée</option>
            <option value="expédiée">Expédiée</option>
            <option value="livrée">Livrée</option>
            <option value="annulée">Annulée</option>
          </select>
        </div>
      </div>
      <div class="table-wrap" id="commandes-table-wrap">
        <div class="table-loading">Chargement...</div>
      </div>
    </div>
  </section>

  <!-- SECTION : CATALOGUE -->
  <section class="section" id="section-catalogue">
    <div class="section-header">
      <h1 class="section-title">Catalogue</h1>
      <p class="section-sub">Articles, prix et stocks</p>
    </div>
    <div class="chat-promo-banner">
      <div class="chat-promo-icon">💡</div>
      <div class="chat-promo-text">
        Essayez : <em>"Quel est le stock des Running ?"</em> ou <em>"Modifie le prix de l'article #12 à 129.90€"</em>
      </div>
      <button class="chat-promo-btn" onclick="adminChatAsk('Y a-t-il des articles avec un stock inférieur à 50 unités ?')">Vérifier le stock →</button>
    </div>
    <div class="table-card">
      <div class="table-card-head">
        <h2 class="table-card-title">Tous les articles</h2>
        <button class="btn-new-article" onclick="openArticleModal()">+ Nouvel article</button>
      </div>
      <div class="table-wrap" id="catalogue-table-wrap">
        <div class="table-loading">Chargement...</div>
      </div>
    </div>
  </section>

  <!-- SECTION : CLIENTS -->
  <section class="section" id="section-clients">
    <div class="section-header">
      <h1 class="section-title">Clients</h1>
      <p class="section-sub">Rechercher et consulter les profils</p>
    </div>
    <div class="chat-promo-banner">
      <div class="chat-promo-icon">💡</div>
      <div class="chat-promo-text">
        Essayez : <em>"Recherche le client Martin"</em> ou <em>"Quelles sont les commandes du client #5 ?"</em>
      </div>
    </div>
    <div class="table-card">
      <div class="table-card-head">
        <h2 class="table-card-title">Recherche client</h2>
        <div class="table-filters">
         <input type="text" id="client-search-input"
         placeholder="Nom, prénom ou email…"
         style="padding:.5rem .9rem;border:1.5px solid #e0d9ce;border-radius:8px;font-family:inherit;font-size:.85rem;"
         onkeydown="if(event.key==='Enter') loadClients()">
          <button onclick="loadClients()" style="padding:.5rem 1rem;background:var(--dark);color:#fff;border:none;border-radius:8px;cursor:pointer;font-family:inherit;">Rechercher</button>
        </div>
      </div>
      <div class="table-wrap" id="clients-table-wrap">
        <p style="text-align:center;color:#8a8178;padding:2rem">Entrez un nom, prénom ou email pour rechercher un client.</p>
      </div>
    </div>
  </section>

  <!-- SECTION : COMMENTAIRES -->
  <section class="section" id="section-commentaires">
    <div class="section-header">
      <h1 class="section-title">Commentaires</h1>
      <p class="section-sub">Modération des avis clients</p>
    </div>
    <div class="chat-promo-banner">
      <div class="chat-promo-icon">💡</div>
      <div class="chat-promo-text">
        Essayez : <em>"Liste les commentaires récents"</em> ou <em>"Supprime le commentaire #3"</em>
      </div>
    </div>
    <div class="table-card">
      <div class="table-card-head">
        <h2 class="table-card-title">Derniers commentaires</h2>
      </div>
      <div class="table-wrap" id="commentaires-table-wrap">
        <div class="table-loading">Chargement...</div>
      </div>
    </div>
  </section>

</main>

<!-- ── CHATBOT ADMIN (panneau latéral droit) ── -->
<?php include 'includes/admin_chat.php'; ?>

<!-- OVERLAY MOBILE -->
<div class="chat-overlay" id="chat-overlay" onclick="closeChatMobile()"></div>
<button class="chat-fab" id="chat-fab" onclick="toggleChatMobile()" aria-label="Assistant Admin">⚙</button>

<script src="js/admin_chat.js"></script>
<script src="js/admin_tables.js"></script>
<script>
  // Navigation entre sections
  document.querySelectorAll('[data-section]').forEach(el => {
    el.addEventListener('click', e => {
      e.preventDefault();
      const sec = el.dataset.section;
      showSection(sec);
    });
  });

  function showSection(name) {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.getElementById('section-' + name)?.classList.add('active');
    document.querySelector('[data-section="' + name + '"]')?.classList.add('active');
    document.getElementById('topbar-title').textContent =
      {dashboard:'Dashboard', commandes:'Commandes', catalogue:'Catalogue', clients:'Clients', commentaires:'Commentaires'}[name] || name;

    // Lazy-load des tableaux
    if (name === 'commandes')    loadCommandes();
    if (name === 'catalogue')    loadCatalogue();
    if (name === 'clients')      loadClients();
    if (name === 'commentaires') loadCommentaires();
  }

  function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
  }
  function focusChatInput() {
    document.getElementById('achat-input')?.focus();
  }
  function adminChatAsk(msg) {
    const input = document.getElementById('achat-input');
    if (input) { input.value = msg; adminChatSend(); }
  }
</script>
</body>
</html>
