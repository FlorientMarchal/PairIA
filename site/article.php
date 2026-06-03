<?php
require_once 'includes/bd.php';

$id = isset($_GET['id']) ? (int)$_GET['id'] : 0;
if (!$id) { header('Location: shell.php'); exit; }

$stmt = $pdo->prepare("SELECT * FROM articles WHERE id_shoes = ?");
$stmt->execute([$id]);
$article = $stmt->fetch();

$isFav = false;

if (isset($_SESSION['client_id'])) {
    $stmt = $pdo->prepare("SELECT 1 FROM favoris WHERE id_client = ? AND id_shoes = ?");
    $stmt->execute([$_SESSION['client_id'], $id]);
    $isFav = $stmt->fetch() ? true : false;
}

if (!$article) { header('Location: shell.php'); exit; }

$stmt = $pdo->prepare("SELECT id_variant, taille, couleur FROM size_color WHERE id_shoes = ? ORDER BY taille, couleur");
$stmt->execute([$id]);
$variants = $stmt->fetchAll();
$tailles  = array_unique(array_column($variants, 'taille'));
$couleurs = array_unique(array_column($variants, 'couleur'));
sort($tailles); sort($couleurs);

$stmt = $pdo->prepare("SELECT * FROM articles WHERE categorie = ? AND id_shoes != ? LIMIT 4");
$stmt->execute([$article['categorie'], $id]);
$similaires = $stmt->fetchAll();

$is_ajax = isset($_GET['ajax']);
if (!$is_ajax) {
    header('Location: shell.php');
    exit;
}

function getCouleurCSS($couleur) {
  $map = ['Noir'=>'#1A1410','Noir mat'=>'#2A2420','Noir vernis'=>'#0A0A0A','Charbon'=>'#3C3C3C','Blanc'=>'#FFFFFF','Blanc cassé'=>'#F5F0E8','Crème'=>'#FFF8E7','Champagne'=>'#F7E7CE','Naturel'=>'#EDE0C8','Gris'=>'#9E9E9E','Gris anthracite'=>'#424242','Gris ardoise'=>'#607D8B','Gris chiné'=>'#A0A0A0','Gris foncé'=>'#616161','Gris taupe'=>'#8D8078','Bleu'=>'#1E88E5','Bleu marine'=>'#1A237E','Marine'=>'#0D1B4B','Bleu nuit'=>'#0D1B4B','Bleu pétrole'=>'#00695C','Bleu ciel'=>'#64B5F6','Bleu indigo'=>'#3949AB','Bleu ardoise'=>'#5C6BC0','Bleu gris'=>'#78909C','Bleu océan'=>'#0277BD','Bleu électrique'=>'#0D47A1','Rouge'=>'#E53935','Rouge vif'=>'#FF1744','Rouge carmin'=>'#B71C1C','Rouge bordeaux'=>'#880E4F','Bordeaux'=>'#7B1022','Corail'=>'#FF6B4A','Terracotta'=>'#C0654A','Colorblock rouge-blanc'=>'#E53935','Vert'=>'#43A047','Vert kaki'=>'#827717','Vert olive'=>'#558B2F','Vert forêt'=>'#1B5E20','Vert hunter'=>'#2E7D32','Vert sauge'=>'#7E9E7E','Vert menthe'=>'#80CBC4','Vert aqua'=>'#00BCD4','Vert fluo'=>'#76FF03','Menthe'=>'#98E8C8','Rose'=>'#F48FB1','Rose poudré'=>'#F8BBD9','Rose gold'=>'#E8A598','Rose fluo'=>'#FF4081','Lilas'=>'#CE93D8','Lavande'=>'#B39DDB','Pêche'=>'#FFAB91','Jaune'=>'#FDD835','Jaune fluo'=>'#FFFF00','Orange'=>'#FB8C00','Orange sécurité'=>'#FF6F00','Or'=>'#D4AF37','Marron'=>'#6D4C41','Marron foncé'=>'#3E2723','Beige'=>'#D7CCC8','Beige naturel'=>'#C8B89A','Kaki'=>'#8D6E63','Camel'=>'#C8A96E','Cognac'=>'#9B4E1A','Sable'=>'#D2B48C','Nude'=>'#E8C9A0','Argent'=>'#B0BEC5'];
  return $map[$couleur] ?? '#CCCCCC';
}
?>
<title>PairIA — <?= htmlspecialchars($article['nom']) ?></title>
<div id="ajax-hero"></div>
<div id="ajax-content">
  <div class="breadcrumb">
    <a href="index.php">Catalogue</a>
    <span class="bc-sep">›</span>
    <a href="index.php?categorie=<?= urlencode($article['categorie']) ?>"><?= htmlspecialchars($article['categorie']) ?></a>
    <span class="bc-sep">›</span>
    <span><?= htmlspecialchars($article['nom']) ?></span>
  </div>

  <div class="product">
    <div class="product-gallery">
      <div class="product-main-img">
        <?php if (!empty($article['url_image'])): ?>
          <img src="<?= htmlspecialchars($article['url_image']) ?>" alt="<?= htmlspecialchars($article['nom']) ?>" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">
          <span class="product-emoji" style="display:none">👟</span>
        <?php else: ?>
          <span class="product-emoji">👟</span>
        <?php endif; ?>
      </div>
    </div>

    <div class="product-info">
      <div class="product-cat"><?= htmlspecialchars($article['categorie']) ?></div>
      <h1 class="product-name"><?= htmlspecialchars($article['nom']) ?></h1>
      <button id="fav-btn" class="fav-btn <?= $isFav ? 'active' : '' ?>" onclick="toggleFavorite()">
          <?= $isFav ? '❤️ En favoris' : '♡ Ajouter aux favoris' ?>
      </button>
      <div class="product-price"><?= number_format($article['Prix'], 2, ',', ' ') ?> €</div>
      <div class="product-divider"></div>

      <?php if (!empty($article['description'])): ?>
        <div class="product-section">
          <div class="product-section-title">Description</div>
          <p class="product-desc"><?= htmlspecialchars($article['description']) ?></p>
        </div>
      <?php endif; ?>

      <?php if (!empty($tailles)): ?>
        <div class="product-section">
          <div class="product-section-title">Pointure</div>
          <div class="size-btns" id="size-btns">
            <?php foreach ($tailles as $t): ?>
              <button class="size-btn" data-size="<?= $t ?>" onclick="selectSize(this)"><?= $t ?></button>
            <?php endforeach; ?>
          </div>
        </div>
      <?php endif; ?>

      <?php if (!empty($couleurs)): ?>
        <div class="product-section">
          <div class="product-section-title">Couleur</div>
          <div class="color-btns" id="color-btns">
            <?php foreach ($couleurs as $c): ?>
              <button class="color-btn" data-color="<?= htmlspecialchars($c) ?>" title="<?= htmlspecialchars($c) ?>" onclick="selectColor(this)" style="background: <?= getCouleurCSS($c) ?>"></button>
            <?php endforeach; ?>
          </div>
        </div>
      <?php endif; ?>

      <div class="product-divider"></div>

      <div class="product-actions">
        <div class="qty-wrap">
          <button class="qty-btn" onclick="changeQty(-1)">−</button>
          <span class="qty-val" id="qty">1</span>
          <button class="qty-btn" onclick="changeQty(1)">+</button>
        </div>
        <button class="add-cart-btn" id="add-cart-btn" onclick="addToCartPage()">Ajouter au panier</button>
      </div>

      <div class="product-delivery">
        <div class="delivery-row">🚚 <span>Livraison gratuite dès 80€ — estimée sous 3-5 jours</span></div>
        <div class="delivery-row">🔄 <span>Retours gratuits sous 30 jours</span></div>
        <div class="delivery-row">🛡️ <span>Garantie 2 ans fabricant</span></div>
      </div>
    </div>
  </div>

  <?php if (!empty($similaires)): ?>
  <div class="similaires">
    <div class="similaires-title">Vous aimerez aussi</div>
    <div class="similaires-grid">
      <?php foreach ($similaires as $s): ?>
        <a href="article.php?id=<?= $s['id_shoes'] ?>" class="sim-card">
          <div class="sim-img">
            <?php if (!empty($s['url_image'])): ?>
              <img src="<?= htmlspecialchars($s['url_image']) ?>" alt="<?= htmlspecialchars($s['nom']) ?>" onerror="this.style.display='none'">
            <?php else: ?>
              <span>👟</span>
            <?php endif; ?>
          </div>
          <div class="sim-body">
            <div class="sim-cat"><?= htmlspecialchars($s['categorie']) ?></div>
            <div class="sim-name"><?= htmlspecialchars($s['nom']) ?></div>
            <div class="sim-price"><?= number_format($s['Prix'], 2, ',', ' ') ?> €</div>
          </div>
        </a>
      <?php endforeach; ?>
    </div>
  </div>
  <?php endif; ?>

  <!-- ════════════════════════════════════════
     COMMENTAIRES
════════════════════════════════════════ -->

<div id="comments-premium" class="comments-premium">

    <!-- COLONNE GAUCHE : LISTE DES AVIS -->
    <div class="comments-left">

        <!-- Zone de tri -->
        <div class="comments-filters">
            <select id="comments-sort" onchange="filterComments()">
                <option value="recent">Les plus récents</option>
                <option value="best">Les mieux notés</option>
                <option value="worst">Les moins bien notés</option>
                <option value="useful">Les plus utiles</option>
            </select>
        </div>

        <!-- Liste des avis -->
        <div id="comments-list"></div>
    </div>

    <!-- COLONNE DROITE : RÉSUMÉ + HISTOGRAMME -->
    <div class="comments-right">

        <!-- Résumé -->
        <div id="comments-summary"></div>

        <!-- Histogramme -->
        <div id="comments-histogram"></div>

        <!-- Bouton donner mon avis -->
        <button class="btn-review" onclick="openReviewModal()">Donner mon avis</button>
    </div>
</div>

<!-- ════════════════════════════════════════
     MODAL AJOUT D’AVIS
════════════════════════════════════════ -->
<div id="review-modal" class="review-modal" style="display:none;">
    <div class="review-modal-content">

        <h3>Laisser un avis</h3>

        <!-- Étoiles interactives -->
        <div class="rating-input">
            <span data-value="5">★</span>
            <span data-value="4">★</span>
            <span data-value="3">★</span>
            <span data-value="2">★</span>
            <span data-value="1">★</span>
        </div>

        <textarea id="review-text" placeholder="Votre avis..."></textarea>

        <div class="modal-actions">
            <button class="btn-cancel" onclick="closeReviewModal()">Annuler</button>
            <button class="btn-submit" onclick="submitReview()">Publier</button>
        </div>
    </div>
</div>


</div>

<script>
var variants = <?= json_encode($variants) ?>;

var PRODUCT_ID = <?= $id ?>;
var qty = 1, selectedSize = null, selectedColor = null;

window.selectSize = function selectSize(btn) {
  console.log("SIZE CLICK", btn.dataset.size);
  document.querySelectorAll('.size-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  selectedSize = btn.dataset.size;
}
window.selectColor = function selectColor(btn) {
  console.log("COLOR CLICK", btn.dataset.color);
  document.querySelectorAll('.color-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  selectedColor = btn.dataset.color;
}
function changeQty(delta) {
  qty = Math.max(1, Math.min(10, qty + delta));
  document.getElementById('qty').textContent = qty;
}
async function addToCartPage() {
  const btn = document.getElementById('add-cart-btn');

  //  Vérification taille
  if (document.querySelectorAll('.size-btn').length > 0 && !selectedSize) {
    shakeElement(document.getElementById('size-btns'));
    showSelectionError('Veuillez sélectionner une pointure');
    return;
  }

  //  Vérification couleur
  if (document.querySelectorAll('.color-btn').length > 0 && !selectedColor) {
    shakeElement(document.getElementById('color-btns'));
    showSelectionError('Veuillez sélectionner une couleur');
    return;
  }

  //  TROUVER LE BON VARIANT
  const variant = variants.find(v =>
    v.taille == selectedSize && v.couleur == selectedColor
  );

  if (!variant) {
    showSelectionError("Combinaison indisponible");
    return;
  }

  //  Appel API (on garde ton système existant)
  const result = await addToCart(PRODUCT_ID, qty, selectedSize, selectedColor);

  //  Animation succès
  if (result && result.success) {
    btn.textContent = '✓ Ajouté !';
    btn.style.background = '#4CAF50';

    setTimeout(() => {
      btn.textContent = 'Ajouter au panier';
      btn.style.background = '';
    }, 1500);
  }
}
function showSelectionError(message) {
  let existing = document.querySelector('.selection-error');
  if (existing) existing.remove();
  const error = document.createElement('div');
  error.className = 'selection-error'; error.textContent = message;
  const actions = document.querySelector('.product-actions');
  actions.parentNode.insertBefore(error, actions);
  setTimeout(() => error.remove(), 2500);
}
function shakeElement(el) {
  el.classList.add('shake');
  setTimeout(() => el.classList.remove('shake'), 400);
}

async function addToCart(product_id, quantity, taille, couleur) {
  try {
    const res = await fetch('cart/add.php', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        product_id: product_id,
        quantity: quantity,
        taille: taille,
        couleur: couleur
      })
    });

    const data = await res.json();

    if (!data.success) {
      showSelectionError(data.error || "Erreur lors de l'ajout");
      return null;
    }

    // 🔽 MAJ compteur panier (IMPORTANT)
    if (document.getElementById('cart-count')) {
      document.getElementById('cart-count').textContent = data.count;
    }

    return data;

  } catch (e) {
    console.error(e);
    showSelectionError("Erreur serveur");
    return null;
  }
}

// REMPLACE l'ancienne toggleFavorite par :
async function toggleFavorite(productId = null, btn = null) {
  try {
    if (!btn) btn = document.getElementById('fav-btn');
    if (!productId && typeof PRODUCT_ID !== "undefined") productId = PRODUCT_ID;
    if (!productId) return;

    const res = await fetch('favorites/toggle.php', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ product_id: productId })
    });

    const data = await res.json();

    if (!data.success) {
      // Pas connecté
      const toast = document.createElement('div');
      toast.className = 'toast';
      toast.textContent = 'Connecte-toi pour ajouter aux favoris';
      document.body.appendChild(toast);
      setTimeout(() => toast.remove(), 2500);
      return;
    }

    const toast = document.createElement('div');
    toast.className = 'toast';

    if (data.action === 'added') {
      if (btn) { btn.classList.add('active'); btn.textContent = '❤️ En favoris'; }
      toast.textContent = 'Ajouté aux favoris ❤️';
    } else if (data.action === 'removed') {
      if (btn) { btn.classList.remove('active'); btn.textContent = '♡ Ajouter aux favoris'; }
      toast.textContent = 'Retiré des favoris';
    }

    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 2500);

  } catch (e) {
    console.error(e);
  }
}

initProductContext({
  id:          <?= $id ?>,
  name:        "<?= htmlspecialchars($article['nom'], ENT_QUOTES) ?>",
  price:       <?= $article['Prix'] ?>,
  categorie:   "<?= htmlspecialchars($article['categorie'], ENT_QUOTES) ?>",
  marque:      "<?= htmlspecialchars($article['marque'] ?? '', ENT_QUOTES) ?>",
  url_image:   "<?= htmlspecialchars($article['url_image'] ?? '', ENT_QUOTES) ?>",
  description: "<?= htmlspecialchars($article['description'] ?? '', ENT_QUOTES) ?>",
  tailles:     <?= json_encode($tailles) ?>,
  couleurs:    <?= json_encode($couleurs) ?>,
  emoji:       "👟"
});

// CHARGEMENT AUTOMATIQUE AU RENDU SPA

loadCommentsPremium();
</script>