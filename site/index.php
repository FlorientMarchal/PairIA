<?php
require_once 'includes/bd.php';

// Filtre par catégorie
$categorie = $_GET['categorie'] ?? 'tous';

if ($categorie === 'tous') {
    $stmt = $pdo->query('SELECT * FROM articles ORDER BY id_shoes');
} else {
    $stmt = $pdo->prepare('SELECT * FROM articles WHERE categorie = ? ORDER BY id_shoes');
    $stmt->execute([$categorie]);
}

$articles = $stmt->fetchAll();

// Catégories distinctes pour les filtres
$cats = $pdo->query('SELECT DISTINCT categorie FROM articles ORDER BY categorie')->fetchAll();
?>
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PairIA — Catalogue</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;1,400&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="styles/global.css">
  <link rel="stylesheet" href="styles/index.css">
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
      <button class="hero-chip" onclick="heroQuestion('Pour le running')">Running</button>
      <button class="hero-chip" onclick="heroQuestion('Style casual')">Casual</button>
      <button class="hero-chip" onclick="heroQuestion('Chaussures de sport')">Sport</button>
    </div>
  </div>
</div>

<!-- LAYOUT -->
<div class="layout">

  <div class="main">
    <div class="catalog-area">

      <!-- Filtres par catégorie -->
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
              <?= htmlspecialchars($cat['categorie']) ?>
            </a>
          <?php endforeach; ?>
        </div>
      </div>

      <!-- Grille produits -->
      <div class="catalog-grid">
        <?php if (empty($articles)): ?>
          <div class="no-results">Aucun produit trouvé.</div>
        <?php else: ?>
          <?php foreach ($articles as $a): ?>
            <div class="card" data-id="<?= $a['id_shoes'] ?>">
              <a href="article.php?id=<?= $a['id_shoes'] ?>" class="card-link">

                <div class="card-img">
                  <?php if (!empty($a['url_image'])): ?>
                    <img
                      src="<?= htmlspecialchars($a['url_image']) ?>"
                      alt="<?= htmlspecialchars($a['nom']) ?>"
                      onerror="this.style.display='none'"
                    >
                  <?php else: ?>
                    <span class="card-emoji">👟</span>
                  <?php endif; ?>
                </div>

                <div class="card-body">
                  <div class="card-cat"><?= htmlspecialchars($a['categorie']) ?></div>
                  <div class="card-name"><?= htmlspecialchars($a['nom']) ?></div>
                  <div class="card-meta"><?= htmlspecialchars($a['marque']) ?> · <?= htmlspecialchars($a['genre']) ?></div>
                  <div class="card-foot">
                    <span class="card-price"><?= number_format($a['Prix'], 2, ',', ' ') ?> €</span>
                    <button class="add-btn" onclick="ajouterPanier(<?= $a['id_shoes'] ?>, event)">+</button>
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