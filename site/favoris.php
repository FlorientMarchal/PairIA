<?php
session_start();
require_once 'includes/bd.php';

if (!isset($_SESSION['client_id'])) {
    header('Location: connexion.php');
    exit;
}

$client_id = $_SESSION['client_id'];

// ===== RECUP FAVORIS =====
$stmt = $pdo->prepare("
    SELECT a.* FROM favoris f
    JOIN articles a ON a.id_shoes = f.id_shoes
    WHERE f.id_client = ?
    ORDER BY f.id DESC
");
$stmt->execute([$client_id]);
$favoris = $stmt->fetchAll();

// ===== SPA =====
$is_ajax = isset($_GET['ajax']);
if (!$is_ajax) {
    header('Location: shell.php#favoris.php');
    exit;
}
?>

<title>PairIA — Mes favoris</title>

<div id="ajax-hero"></div>

<div id="ajax-content">
<div class="catalog-area">

  <div class="catalog-top">
    <div class="catalog-title">
      Mes favoris ❤️
      <span class="catalog-count"><?= count($favoris) ?> produit(s)</span>
    </div>
  </div>

  <?php if (empty($favoris)): ?>
    <div class="no-results" style="display:block">
      Aucun favori pour le moment 😢
      <br><br>
      <a href="index.php">Voir le catalogue</a>
    </div>
  <?php else: ?>

    <div class="catalog-grid">
      <?php foreach ($favoris as $a): ?>
        <div class="card">
          <a href="article.php?id=<?= $a['id_shoes'] ?>" class="card-link">
            
            <div class="card-img">
              <img src="<?= htmlspecialchars($a['url_image']) ?>">
            </div>

            <div class="card-body">
              <div class="card-cat"><?= htmlspecialchars($a['categorie']) ?></div>
              <div class="card-name"><?= htmlspecialchars($a['nom']) ?></div>

              <div class="card-foot">
                <span class="card-price">
                  <?= number_format($a['Prix'], 2, ',', ' ') ?> €
                </span>

                <div style="display:flex;gap:6px">
                  <button class="card-fav active"
                          onclick="event.preventDefault(); event.stopPropagation(); toggleFavCatalogue(<?= $a['id_shoes'] ?>, this)">
                    ❤️
                  </button>
                </div>
              </div>

            </div>
          </a>
        </div>
      <?php endforeach; ?>
    </div>

  <?php endif; ?>

</div>
</div>

<script>
async function toggleFavCatalogue(productId, btn) {
  try {
    const res = await fetch('favorites/toggle.php', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ product_id: productId })
    });
    const data = await res.json();

    const toast = document.createElement('div');
    toast.className = 'toast';

    if (!data.success) {
      toast.textContent = 'Connecte-toi pour ajouter aux favoris';
    } else if (data.action === 'removed') {
      // On est sur la page favoris : retire la carte du DOM
      const card = btn.closest('.card');
      if (card) card.remove();

      // Met à jour le compteur
      const counter = document.querySelector('.catalog-count');
      if (counter) {
        const next = (parseInt(counter.textContent) || 0) - 1;
        counter.textContent = next + ' produit(s)';
        if (next === 0) {
          const grid = document.querySelector('.catalog-grid');
          if (grid) grid.innerHTML = `
            <div class="no-results" style="display:block">
              Aucun favori pour le moment 😢<br><br>
              <a href="index.php">Voir le catalogue</a>
            </div>`;
        }
      }

      toast.textContent = 'Retiré des favoris';
    }

    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 2500);

  } catch(e) {
    console.error(e);
  }
}

requestAnimationFrame(() =>
  initFavorisContext(<?php
    $favoris_js = array_map(fn($f) => [
      'id'   => (int)$f['id_shoes'],
      'nom'  => $f['nom'],
      'prix' => (float)$f['Prix'],
    ], $favoris);
    echo json_encode($favoris_js, JSON_HEX_APOS | JSON_HEX_TAG);
  ?>)
);
</script>