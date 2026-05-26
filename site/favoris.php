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

                  <!-- ❤️ ACTIF -->
                  <button class="card-fav active"
                          onclick="toggleFavCatalogue(<?= $a['id_shoes'] ?>, this)">
                    ❤️
                  </button>

                  <button class="card-add"
                          onclick="ajouterPanier(<?= $a['id_shoes'] ?>, event)">
                    +
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