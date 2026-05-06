<?php
require_once 'bd.php';

// Récupération des produits depuis MySQL
// avec filtre par catégorie si demandé
$categorie = $_GET['categorie'] ?? 'tous';

if ($categorie === 'tous') {
    $stmt = $pdo->query('SELECT * FROM produits ORDER BY id');
} else {
    $stmt = $pdo->prepare('SELECT * FROM produits WHERE categorie = ? ORDER BY id');
    $stmt->execute([$categorie]);
}

$produits = $stmt->fetchAll();

// Catégories disponibles pour les filtres
$cats = $pdo->query('SELECT DISTINCT categorie FROM produits ORDER BY categorie')->fetchAll();
?>
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PairIA — Catalogue</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;1,400&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="css/global.css">
  <link rel="stylesheet" href="css/index.css">
</head>
<body>

<?php include 'includes/nav.php'; ?>

<!-- HERO -->
<div class="hero">
  <div class="hero-inner">
    <div class="hero-tag">
      <div class="hero-tag-dot"></div>
      Assistant IA disponible
    </div>
    <h1>Trouvez vos chaussures<br>en <em>décrivant</em> ce que vous voulez</h1>
    <p>Pas besoin de filtres — décrivez votre usage, budget et style. Notre IA trouve la paire parfaite.</p>
    <div class="hero-input-wrap">
      <input
        class="hero-input"
        id="hero-input"
        type="text"
        placeholder="Ex : chaussures de rando imperméables pas trop chères..."
        onkeydown="if(event.key==='Enter') heroSend()"
      >
      <button class="hero-btn" onclick="heroSend()">Trouver ma paire →</button>
    </div>
    <div class="hero-chips">
      <button class="hero-chip" onclick="heroQuestion('Chaussures imperméables')">Imperméables</button>
      <button class="hero-chip" onclick="heroQuestion('Moins de 100€')">− 100 €</button>
      <button class="hero-chip" onclick="heroQuestion('Pour la randonnée')">Randonnée</button>
      <button class="hero-chip" onclick="heroQuestion('Style casual')">Casual</button>
      <button class="hero-chip" onclick="heroQuestion('Soirée formelle')">Formel</button>
    </div>
  </div>
</div>

<!-- LAYOUT -->
<div class="layout">

  <div class="main">
    <div class="catalog-area">

      <!-- Filtres -->
      <div class="cat-top">
        <div class="cat-title">
          <small>Notre sélection</small>
          Catalogue
        </div>
        <div class="filters">
          <a href="index.php"
             class="filter-btn <?= $categorie === 'tous' ? 'active' : '' ?>">
            Tous
          </a>
          <?php foreach ($cats as $cat): ?>
            <a href="index.php?categorie=<?= urlencode($cat['categorie']) ?>"
               class="filter-btn <?= $categorie === $cat['categorie'] ? 'active' : '' ?>">
              <?= htmlspecialchars(ucfirst($cat['categorie'])) ?>
            </a>
          <?php endforeach; ?>
        </div>
      </div>

      <!-- Grille produits -->
      <div class="catalog-grid">
        <?php if (empty($produits)): ?>
          <div class="no-results">Aucun produit trouvé.</div>
        <?php else: ?>
          <?php foreach ($produits as $p): ?>
            <div class="card" data-id="<?= $p['id'] ?>">

              <a href="article.php?id=<?= $p['id'] ?>" class="card-link">
                <div class="card-img" style="background: <?= htmlspecialchars($p['couleur_bg'] ?? '#EEE8DC') ?>">
                  <?php if (!empty($p['badge'])): ?>
                    <span class="badge badge-<?= htmlspecialchars($p['badge']) ?>">
                      <?= $p['badge'] === 'new' ? 'Nouveau' : '−' . $p['remise'] . '%' ?>
                    </span>
                  <?php endif; ?>
                  <?php if (!empty($p['image'])): ?>
                    <img src="<?= htmlspecialchars($p['image']) ?>" alt="<?= htmlspecialchars($p['nom']) ?>">
                  <?php else: ?>
                    <span class="card-emoji"><?= htmlspecialchars($p['emoji'] ?? '👟') ?></span>
                  <?php endif; ?>
                </div>

                <div class="card-body">
                  <div class="card-cat"><?= htmlspecialchars($p['categorie']) ?></div>
                  <div class="card-name"><?= htmlspecialchars($p['nom']) ?></div>
                  <div class="card-foot">
                    <div>
                      <span class="card-price"><?= number_format($p['prix'], 0, ',', ' ') ?> €</span>
                      <?php if (!empty($p['prix_ancien'])): ?>
                        <span class="card-old"><?= number_format($p['prix_ancien'], 0, ',', ' ') ?> €</span>
                      <?php endif; ?>
                      <div class="card-stars">
                        <?= str_repeat('★', round($p['note'] ?? 4)) ?>
                        <?= str_repeat('☆', 5 - round($p['note'] ?? 4)) ?>
                      </div>
                    </div>
                    <button class="add-btn" onclick="ajouterPanier(<?= $p['id'] ?>, event)">+</button>
                  </div>
                </div>
              </a>

            </div>
          <?php endforeach; ?>
        <?php endif; ?>
      </div>

    </div>
  </div>

  <?php include 'includes/chat.php'; ?>

</div>

<script src="js/global.js"></script>
<script src="js/chat.js"></script>
<script>
  // Envoi depuis le hero vers le chat
  function heroSend() {
    const input = document.getElementById('hero-input');
    const text = input?.value.trim();
    if (!text) return;
    input.value = '';
    sendMessage(text);
    document.querySelector('.layout').scrollIntoView({ behavior: 'smooth' });
  }

  function heroQuestion(text) {
    sendMessage(text);
    document.querySelector('.layout').scrollIntoView({ behavior: 'smooth' });
  }

  // Ajout au panier depuis la grille
  async function ajouterPanier(id, event) {
    event.preventDefault();
    event.stopPropagation();
    await addToCart(id, 1);
    const btn = event.target;
    btn.textContent = '✓';
    btn.style.background = '#4CAF50';
    setTimeout(() => { btn.textContent = '+'; btn.style.background = ''; }, 1000);
  }
</script>

</body>
</html>