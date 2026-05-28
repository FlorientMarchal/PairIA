<?php
session_start();
require_once 'includes/bd.php';
 
$panier = [];
 
if (isset($_SESSION['client_id'])) {
 
    $stmt = $pdo->prepare("
        SELECT 
            p.id_panier,
            p.id_variant,
            p.quantite,
            sc.taille,
            sc.couleur,
            a.id_shoes,
            a.nom,
            a.categorie,
            a.Prix,
            a.url_image
        FROM panier p
        JOIN size_color sc ON sc.id_variant = p.id_variant
        JOIN articles a ON a.id_shoes = sc.id_shoes
        WHERE p.id_client = ?
    ");
    $stmt->execute([$_SESSION['client_id']]);
    $rows = $stmt->fetchAll();
 
    foreach ($rows as $row) {
        $key = $row['id_variant'];
        $panier[$key] = [
            'id_variant'=> $row['id_variant'],
            'id'        => $row['id_shoes'],
            'nom'       => $row['nom'],
            'categorie' => $row['categorie'],
            'prix'      => (float)$row['Prix'],
            'image'     => $row['url_image'],
            'taille'    => $row['taille'],
            'couleur'   => $row['couleur'],
            'quantity'  => $row['quantite'],
        ];
    }
 
    $_SESSION['panier'] = $panier;
 
    // Récupérer l'adresse du client
    $stmtClient = $pdo->prepare("SELECT adresse, prenom, nom FROM clients WHERE id_client = ?");
    $stmtClient->execute([$_SESSION['client_id']]);
    $clientInfo = $stmtClient->fetch();
    $adresseLivraison = $clientInfo['adresse'] ?? '';
 
} else {
    $panier = $_SESSION['panier'] ?? [];
    $adresseLivraison = '';
    $clientInfo = null;
}
 
$sous_total  = 0;
foreach ($panier as $item) {
    $sous_total += $item['prix'] * $item['quantity'];
}
$livraison   = $sous_total >= 80 ? 0 : 10;
$total       = $sous_total + $livraison;
$nb_articles = array_sum(array_column($panier, 'quantity'));
 
$is_ajax = isset($_GET['ajax']);
if (!$is_ajax) {
    header('Location: shell.php');
    exit;
}
?>
<title>PairIA — Mon panier</title>
 
<div id="ajax-hero"></div>
 
<div id="ajax-content">
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
 
      <!-- Layout deux colonnes : articles + récapitulatif -->
      <div class="panier-layout">
 
        <!-- Colonne gauche : articles -->
        <div class="panier-left">
 
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
 
        </div>
 
        <!-- Colonne droite : récapitulatif -->
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
               <!-- Récap adresse dans le sidebar -->
          <div class="recap-row recap-adresse">
           <span>📍 Livraison à :</span>
              <span id="recap-adresse-value">
               <?= htmlspecialchars($adresseLivraison) ?>
              </span>
        </div>
 
          <div class="recap-free-shipping" id="free-shipping-msg"
            <?= $livraison === 0 ? 'style="display:none"' : '' ?>>
            Plus que <?= number_format(80 - $sous_total, 2, ',', ' ') ?> € pour la livraison gratuite !
          </div>
 
          <div class="recap-divider"></div>
 
          <div class="recap-row recap-total">
            <span>Total TTC :</span>
            <span id="total"><?= number_format($total, 2, ',', ' ') ?> €</span>
          </div>

 
          <button class="recap-checkout-btn" id="checkout-btn" onclick="finaliserCommande()">
            🛒 Finaliser la commande →
          </button>
 
          <div class="recap-garanties">
            <div class="recap-garantie-row">🔒 Paiement sécurisé via Stripe</div>
            <div class="recap-garantie-row">🔄 Retours gratuits 30 jours</div>
            <div class="recap-garantie-row">🚚 Livraison 3-5 jours</div>
          </div>
        </div>
 
      </div><!-- /panier-layout -->
 
    <?php endif; ?>
 
  </div>
</div>
 
<?php
$panier_js = [];
foreach ($panier as $key => $item) {
    $panier_js[] = [
        'nom'       => $item['nom'],
        'categorie' => $item['categorie'] ?? '',
        'prix'      => (float)$item['prix'],
        'quantity'  => (int)($item['quantity'] ?? 1),
    ];
}
?>
 
<style>
/* ── Layout panier deux colonnes ── */
.panier-layout {
  display: flex;
  gap: 24px;
  align-items: flex-start;
}
.panier-left {
  flex: 1;
  min-width: 0;
}
@media (max-width: 768px) {
  .panier-layout { flex-direction: column; }
}
</style>
 
<script>
requestAnimationFrame(() =>
    initPanierContext(<?php echo json_encode($panier_js, JSON_HEX_APOS | JSON_HEX_TAG); ?>)
);
var LIVRAISON_SEUIL = 80;
 
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
 
  const stEl  = document.getElementById('sous-total');
  const lvEl  = document.getElementById('livraison');
  const ttEl  = document.getElementById('total');
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
 
  setTimeout(() => {
    if (document.querySelectorAll('.panier-item').length === 0) {
      document.querySelector('.panier-layout')?.remove();
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
 
/* ── Finaliser la commande ── */
function finaliserCommande() {
  <?php if (!isset($_SESSION['client_id'])): ?>
    if (confirm('Vous devez être connecté pour finaliser votre commande. Se connecter ?')) {
      window.location.href = 'connexion.php';
    }
    return;
  <?php endif; ?>

  navigateTo('acheter.php');
}

 
/* ── Toast panier ── */
function showToastPanier(msg) {
  const t = document.createElement('div');
  t.className = 'toast';
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 2800);
}
 
/* ── Modale de confirmation ── */
function confirmerSuppression(callback) {
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `
    <div class="modal">
      <div class="modal-icon">🗑️</div>
      <div class="modal-title">Supprimer cet article ?</div>
      <div class="modal-sub">Cet article sera retiré de votre panier.</div>
      <div class="modal-actions">
        <button class="modal-btn-cancel" id="modal-cancel">Annuler</button>
        <button class="modal-btn-confirm" id="modal-confirm">Supprimer</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);
  document.getElementById('modal-cancel').onclick  = () => overlay.remove();
  document.getElementById('modal-confirm').onclick = () => { overlay.remove(); callback(); };
  overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
}
</script>
 