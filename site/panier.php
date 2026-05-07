<?php
session_start();
require_once 'includes/bd.php';

$panier = isset($_SESSION['panier']) ? $_SESSION['panier'] : [];

$sous_total  = 0;
foreach ($panier as $item) {
    $sous_total += $item['prix'] * $item['quantity'];
}
$livraison   = $sous_total >= 80 ? 0 : 10;
$total       = $sous_total + $livraison;
$nb_articles = array_sum(array_column($panier, 'quantity'));

$premier_article = !empty($panier) ? array_values($panier)[0] : null;
?>
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PairIA — Mon panier</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;1,400&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="styles/global.css">
  <link rel="stylesheet" href="styles/panier.css">
</head>
<body>

<?php include 'includes/navbar.php'; ?>

<div class="page-layout">
  <div class="page-content">
    <div class="panier-area">

      <div class="panier-header">
        <h1 class="panier-title">Mon panier</h1>
        <?php if ($nb_articles > 0): ?>
          <span class="panier-count"><?= $nb_articles ?> article<?= $nb_articles > 1 ? 's' : '' ?></span>
        <?php endif; ?>
      </div>

      <?php if (empty($panier)): ?>

        <div class="panier-vide">
          <div class="panier-vide-icon">🛍</div>
          <div class="panier-vide-title">Votre panier est vide</div>
          <p class="panier-vide-sub">Demandez à notre conseiller de vous aider à trouver la paire parfaite !</p>
          <a href="index.php" class="panier-vide-btn">Voir le catalogue</a>
        </div>

      <?php else: ?>

        <div class="panier-items" id="panier-items">
          <?php foreach ($panier as $key => $item): ?>
            <div class="panier-item"
              id="item-<?= htmlspecialchars($key) ?>"
              data-prix="<?= $item['prix'] ?>">

              <div class="item-img">
                <?php if (!empty($item['image'])): ?>
                  <img src="<?= htmlspecialchars($item['image']) ?>"
                    alt="<?= htmlspecialchars($item['nom']) ?>"
                    onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">
                  <span class="item-emoji" style="display:none">👟</span>
                <?php else: ?>
                  <span class="item-emoji">👟</span>
                <?php endif; ?>
              </div>

              <div class="item-details">
                <div class="item-cat"><?= htmlspecialchars($item['categorie']) ?></div>
                <div class="item-name"><?= htmlspecialchars($item['nom']) ?></div>
                <?php if (!empty($item['taille'])): ?>
                  <div class="item-meta">Pointure : <?= htmlspecialchars($item['taille']) ?></div>
                <?php endif; ?>
                <?php if (!empty($item['couleur'])): ?>
                  <div class="item-meta">Couleur : <?= htmlspecialchars($item['couleur']) ?></div>
                <?php endif; ?>
              </div>

              <div class="item-right">
                <div class="item-price-wrap">
                  <div class="item-price" id="price-<?= htmlspecialchars($key) ?>">
                    <?= number_format($item['prix'] * $item['quantity'], 2, ',', ' ') ?> €
                  </div>
                  <div class="item-price-unit"><?= number_format($item['prix'], 2, ',', ' ') ?> € / unité</div>
                </div>
                <div class="item-qty-wrap">
                  <button class="item-qty-btn" onclick="changeItemQty('<?= htmlspecialchars($key) ?>', -1)">−</button>
                  <span class="item-qty-val" id="qty-<?= htmlspecialchars($key) ?>"><?= $item['quantity'] ?></span>
                  <button class="item-qty-btn" onclick="changeItemQty('<?= htmlspecialchars($key) ?>', 1)">+</button>
                </div>
                <button class="item-remove" onclick="removeItem('<?= htmlspecialchars($key) ?>')">
                  Supprimer
                </button>
              </div>

            </div>
          <?php endforeach; ?>
        </div>

        <div class="recap">
          <div class="recap-title">Récapitulatif</div>

          <div class="recap-row">
            <span>Sous Total :</span>
            <span id="sous-total"><?= number_format($sous_total, 2, ',', ' ') ?> €</span>
          </div>
          <div class="recap-row">
            <span>Livraison :</span>
            <span id="livraison" class="<?= $livraison === 0 ? 'livraison-gratuite' : '' ?>">
              <?= $livraison === 0 ? 'Gratuite' : number_format($livraison, 2, ',', ' ') . ' €' ?>
            </span>
          </div>

          <!-- Message livraison gratuite — toujours présent, affiché/masqué en JS -->
          <div class="recap-free-shipping" id="free-shipping-msg"
            <?= $livraison === 0 ? 'style="display:none"' : '' ?>>
            Plus que <?= number_format(80 - $sous_total, 2, ',', ' ') ?> € pour la livraison gratuite !
          </div>

          <div class="recap-divider"></div>

          <div class="recap-row recap-total">
            <span>Total TTC :</span>
            <span id="total"><?= number_format($total, 2, ',', ' ') ?> €</span>
          </div>

          <button class="recap-checkout-btn">Finaliser la commande →</button>

          <div class="recap-garanties">
            <div class="recap-garantie-row">🔒 Paiement sécurisé</div>
            <div class="recap-garantie-row">🔄 Retours gratuits 30 jours</div>
            <div class="recap-garantie-row">🚚 Livraison 3-5 jours</div>
          </div>
        </div>

      <?php endif; ?>

    </div>
  </div>

  <?php
  if ($premier_article) {
      $article = ['nom' => $premier_article['nom'], 'categorie' => $premier_article['categorie']];
  }
  include 'includes/chat.php';
  ?>
</div>

<script src="js/global.js"></script>
<script src="js/chat.js"></script>
<script>

const LIVRAISON_SEUIL = 80;

/* ── Modifier la quantité ── */
async function changeItemQty(key, delta) {
  const qtyEl  = document.getElementById('qty-' + key);
  const newQty = parseInt(qtyEl.textContent) + delta;

  if (newQty <= 0) {
    confirmerSuppression(async () => {
      const res = await fetch('cart/update.php', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key, quantity: 0 })
      });
      const data = await res.json();
      supprimerItem(key);
      document.getElementById('cart-count').textContent = data.count;
      recalcTotal();
    });
    return;
  }

  const res = await fetch('cart/update.php', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ key, quantity: newQty })
  });
  const data = await res.json();
  if (data.success) {
    qtyEl.textContent = newQty;
    const item     = document.getElementById('item-' + key);
    const prixUnit = parseFloat(item.dataset.prix);
    const priceEl  = document.getElementById('price-' + key);
    if (priceEl) priceEl.textContent = (prixUnit * newQty).toFixed(2).replace('.', ',') + ' €';
    document.getElementById('cart-count').textContent = data.count;
    recalcTotal();
  }
}

/* ── Supprimer un article ── */
async function removeItem(key) {
  confirmerSuppression(async () => {
    const res = await fetch('cart/remove.php', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key })
    });
    const data = await res.json();
    supprimerItem(key);
    document.getElementById('cart-count').textContent = data.count;
    recalcTotal();
  });
}

/* ── Animation suppression ── */
function supprimerItem(key) {
  const item = document.getElementById('item-' + key);
  if (!item) return;
  item.style.transition = 'opacity .3s, transform .3s';
  item.style.opacity    = '0';
  item.style.transform  = 'translateX(20px)';
  setTimeout(() => item.remove(), 300);
}

/* ── Recalculer les totaux ── */
function recalcTotal() {
  let sousTotal = 0;

  document.querySelectorAll('.panier-item').forEach(item => {
    const key      = item.id.replace('item-', '');
    const prixUnit = parseFloat(item.dataset.prix || 0);
    const qtyEl    = document.getElementById('qty-' + key);
    const qty      = qtyEl ? parseInt(qtyEl.textContent) : 0;
    sousTotal += prixUnit * qty;
  });

  const livraison = sousTotal >= LIVRAISON_SEUIL ? 0 : 10;
  const total     = sousTotal + livraison;

  const stEl = document.getElementById('sous-total');
  const lvEl = document.getElementById('livraison');
  const ttEl = document.getElementById('total');
  const fsmEl = document.getElementById('free-shipping-msg');

  if (stEl) stEl.textContent = sousTotal.toFixed(2).replace('.', ',') + ' €';

  if (lvEl) {
    lvEl.textContent = livraison === 0 ? 'Gratuite' : livraison.toFixed(2).replace('.', ',') + ' €';
    lvEl.className   = livraison === 0 ? 'livraison-gratuite' : '';
  }

  if (ttEl) ttEl.textContent = total.toFixed(2).replace('.', ',') + ' €';

  if (fsmEl) {
    if (livraison === 0) {
      fsmEl.style.display = 'none';
    } else {
      fsmEl.style.display = 'block';
      fsmEl.textContent   = 'Plus que ' + (LIVRAISON_SEUIL - sousTotal).toFixed(2).replace('.', ',') + ' € pour la livraison gratuite !';
    }
  }

  // Panier vide
  setTimeout(() => {
    if (document.querySelectorAll('.panier-item').length === 0) {
      document.getElementById('panier-items')?.remove();
      document.querySelector('.recap')?.remove();
      const area = document.querySelector('.panier-area');
      if (area) {
        area.innerHTML += `
          <div class="panier-vide">
            <div class="panier-vide-icon">🛍</div>
            <div class="panier-vide-title">Votre panier est vide</div>
            <p class="panier-vide-sub">Demandez à notre conseiller de vous aider !</p>
            <a href="index.php" class="panier-vide-btn">Voir le catalogue</a>
          </div>`;
      }
    }
  }, 350);
}

/* ── Modale de confirmation ── */
function confirmerSuppression(callback) {
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `
    <div class="modal">
      <div class="modal-icon">🗑️</div>
      <div class="modal-title">Supprimer cet article ?</div>
      <div class="modal-sub">Cet article sera retiré de votre panier. Vous pourrez le rajouter depuis le catalogue.</div>
      <div class="modal-actions">
        <button class="modal-btn-cancel" id="modal-cancel">Annuler</button>
        <button class="modal-btn-confirm" id="modal-confirm">Supprimer</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);

  document.getElementById('modal-cancel').onclick = () => overlay.remove();
  document.getElementById('modal-confirm').onclick = () => {
    overlay.remove();
    callback();
  };
  overlay.addEventListener('click', e => {
    if (e.target === overlay) overlay.remove();
  });
}

</script>
</body>
</html>