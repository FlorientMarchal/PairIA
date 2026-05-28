<?php
session_start();
require_once 'includes/bd.php';
require_once 'includes/config.php';

if (!isset($_SESSION['client_id'])) {
    header('Location: connexion.php');
    exit;
}

$client_id = $_SESSION['client_id'];

$stmt = $pdo->prepare("
    SELECT 
        p.id_panier, p.id_variant, p.quantite,
        sc.taille, sc.couleur, sc.stock,
        a.id_shoes, a.nom, a.categorie, a.Prix, a.url_image
    FROM panier p
    JOIN size_color sc ON sc.id_variant = p.id_variant
    JOIN articles a    ON a.id_shoes    = sc.id_shoes
    WHERE p.id_client = ?
");
$stmt->execute([$client_id]);
$rows = $stmt->fetchAll();

if (empty($rows)) {
    header('Location: panier.php');
    exit;
}

$stmtClient = $pdo->prepare("SELECT * FROM clients WHERE id_client = ?");
$stmtClient->execute([$client_id]);
$client = $stmtClient->fetch();

$adresse    = $client['adresse'] ?? '';
$sous_total = 0;
foreach ($rows as $row) { $sous_total += $row['Prix'] * $row['quantite']; }
$livraison  = $sous_total >= 80 ? 0 : 10;
$total      = $sous_total + $livraison;

$stock_errors = [];
foreach ($rows as $row) {
    if ($row['quantite'] > $row['stock']) {
        $stock_errors[] = "Stock insuffisant pour « {$row['nom']} » (taille {$row['taille']}) : {$row['stock']} disponible(s).";
    }
}

$is_ajax = isset($_GET['ajax']);
if (!$is_ajax) {
    header('Location: shell.php');
    exit;
}
?>
<title>PairIA — Finaliser ma commande</title>

<div id="ajax-hero"></div>
<div id="ajax-content">
<div class="acheter-area">

  <div class="breadcrumb">
    <a href="index.php">Catalogue</a>
    <span class="bc-sep">›</span>
    <a href="panier.php">Mon panier</a>
    <span class="bc-sep">›</span>
    <span>Finaliser la commande</span>
  </div>

  <h1 class="acheter-title">Finaliser ma commande</h1>

  <?php if (!empty($stock_errors)): ?>
    <div class="acheter-alert error">
      <strong>⚠️ Problème de stock :</strong><br>
      <?php foreach ($stock_errors as $err): ?>
        <?= htmlspecialchars($err) ?><br>
      <?php endforeach; ?>
      <a href="panier.php" style="color:inherit;text-decoration:underline">← Retour au panier</a>
    </div>
  <?php endif; ?>

  <?php if (empty($adresse)): ?>
    <div class="acheter-alert warning">
      ⚠️ Vous n'avez pas d'adresse de livraison enregistrée.
      <a href="compte.php" style="color:inherit;text-decoration:underline">En ajouter une →</a>
    </div>
  <?php endif; ?>

  <div class="acheter-layout">

    <!-- Récap commande -->
    <div class="acheter-recap">
      <div class="acheter-section-title">📦 Récapitulatif</div>

      <?php foreach ($rows as $row): ?>
        <div class="acheter-item">
          <div class="acheter-item-img">
            <?php if (!empty($row['url_image'])): ?>
              <img src="<?= htmlspecialchars($row['url_image']) ?>" alt="<?= htmlspecialchars($row['nom']) ?>" onerror="this.style.display='none'">
            <?php else: ?>
              <span>👟</span>
            <?php endif; ?>
          </div>
          <div class="acheter-item-info">
            <div class="acheter-item-name"><?= htmlspecialchars($row['nom']) ?></div>
            <div class="acheter-item-meta">
              Pointure <?= htmlspecialchars($row['taille']) ?> · <?= htmlspecialchars($row['couleur']) ?>
            </div>
            <div class="acheter-item-meta">Qté : <?= (int)$row['quantite'] ?></div>
          </div>
          <div class="acheter-item-prix">
            <?= number_format($row['Prix'] * $row['quantite'], 2, ',', ' ') ?> €
          </div>
        </div>
      <?php endforeach; ?>

      <div class="acheter-totaux">
        <div class="acheter-total-row">
          <span>Sous-total</span>
          <span><?= number_format($sous_total, 2, ',', ' ') ?> €</span>
        </div>
        <div class="acheter-total-row">
          <span>Livraison</span>
          <span><?= $livraison === 0 ? 'Gratuite' : number_format($livraison, 2, ',', ' ') . ' €' ?></span>
        </div>
        <div class="acheter-total-row acheter-grand-total">
          <span>Total TTC</span>
          <span><?= number_format($total, 2, ',', ' ') ?> €</span>
        </div>
      </div>

      <div class="acheter-adresse-recap">
        <div class="acheter-section-title" style="margin-top:0">📍 Livraison</div>
        <?php if (!empty($adresse)): ?>
          <div class="acheter-adresse-val"><?= nl2br(htmlspecialchars($adresse)) ?></div>
        <?php else: ?>
          <div style="color:var(--gray);font-size:0.85rem">Aucune adresse renseignée</div>
        <?php endif; ?>
      </div>
    </div>

    <!-- Formulaire paiement Stripe -->
    <div class="acheter-paiement">
      <div class="acheter-section-title">💳 Paiement sécurisé</div>

      <?php if (empty($stock_errors)): ?>
        <div class="stripe-form-wrap">
          <div class="stripe-secure-badge">🔒 Paiement chiffré SSL via Stripe</div>

          <div class="stripe-field-group">
            <label class="stripe-label">Numéro de carte</label>
            <div id="card-number-element" class="stripe-input"></div>
          </div>
          <div style="display:flex;gap:12px">
            <div class="stripe-field-group" style="flex:1">
              <label class="stripe-label">Expiration</label>
              <div id="card-expiry-element" class="stripe-input"></div>
            </div>
            <div class="stripe-field-group" style="flex:1">
              <label class="stripe-label">CVC</label>
              <div id="card-cvc-element" class="stripe-input"></div>
            </div>
          </div>

          <div id="card-errors" class="stripe-error" role="alert"></div>

          <button id="pay-btn" class="pay-btn" onclick="payerCommande()">
            <span id="pay-btn-text">Payer <?= number_format($total, 2, ',', ' ') ?> €</span>
            <span id="pay-btn-loader" style="display:none">⏳ Traitement en cours...</span>
          </button>

          <div class="stripe-cards-icons">
            <span title="Visa">VISA</span>
            <span title="Mastercard">MC</span>
            <span title="American Express">AMEX</span>
          </div>
        </div>
      <?php else: ?>
        <div style="text-align:center;padding:40px 20px;color:var(--gray)">
          <div style="font-size:2rem;margin-bottom:10px">⚠️</div>
          Corrigez les problèmes de stock avant de procéder au paiement.
          <br><a href="panier.php" class="pay-btn" style="display:inline-block;margin-top:16px;text-decoration:none">
            ← Retour au panier
          </a>
        </div>
      <?php endif; ?>
    </div>

  </div><!-- /acheter-layout -->
</div>
</div>

<?php if (empty($stock_errors)): ?>
<script>
// ── Garde SPA : évite la redéclaration si la page est rechargée en AJAX ──
if (typeof window._stripeInitialized === 'undefined') {
  window._stripeInitialized = true;

  // Charger le script Stripe de façon dynamique (évite les doublons)
  if (!document.querySelector('script[src*="js.stripe.com"]')) {
    var stripeScript = document.createElement('script');
    stripeScript.src = 'https://js.stripe.com/v3/';
    stripeScript.onload = initStripe;
    document.head.appendChild(stripeScript);
  } else {
    initStripe();
  }
}

function initStripe() {
  window._STRIPE_KEY   = '<?= STRIPE_PUBLIC_KEY ?>';
  window._TOTAL_CENTS  = <?= (int)round($total * 100) ?>;

  window._stripe   = Stripe(window._STRIPE_KEY);
  var elements = window._stripe.elements({
    fonts: [{ cssSrc: 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500&display=swap' }],
    locale: 'fr'
  });

  var style = {
    base: {
      color: '#1a1410',
      fontSize: '15px',
      fontFamily: 'Inter, sans-serif',
      '::placeholder': { color: '#b0a89e' }
    },
    invalid: { color: '#c0392b' }
  };

  window._cardNumber = elements.create('cardNumber', { style });
  window._cardExpiry = elements.create('cardExpiry', { style });
  window._cardCvc    = elements.create('cardCvc',    { style });

  window._cardNumber.mount('#card-number-element');
  window._cardExpiry.mount('#card-expiry-element');
  window._cardCvc.mount('#card-cvc-element');

  [window._cardNumber, window._cardExpiry, window._cardCvc].forEach(function(el) {
    el.addEventListener('change', function(e) {
      var err = document.getElementById('card-errors');
      if (err) err.textContent = e.error ? e.error.message : '';
    });
  });
}

async function payerCommande() {
  var btn    = document.getElementById('pay-btn');
  var label  = document.getElementById('pay-btn-text');
  var loader = document.getElementById('pay-btn-loader');
  var errEl  = document.getElementById('card-errors');

  btn.disabled         = true;
  label.style.display  = 'none';
  loader.style.display = 'inline';
  errEl.textContent    = '';

  try {
    // 1. Créer le PaymentIntent
    var piRes = await fetch('stripe/create_payment_intent.php', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ amount: window._TOTAL_CENTS })
    });
    var piData = await piRes.json();

    if (!piData.client_secret) {
      errEl.textContent = piData.error || 'Erreur lors de la création du paiement.';
      resetPayBtn(); return;
    }

    // 2. Confirmer le paiement avec Stripe
    var result = await window._stripe.confirmCardPayment(piData.client_secret, {
      payment_method: { card: window._cardNumber }
    });

    if (result.error) {
      errEl.textContent = result.error.message;
      resetPayBtn(); return;
    }

    if (result.paymentIntent.status === 'succeeded') {
      // 3. Valider côté serveur
      var cmdRes = await fetch('stripe/valider_commande.php', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ payment_intent_id: result.paymentIntent.id })
      });
      var cmdData = await cmdRes.json();

      if (cmdData.success) {
        // Navigation SPA vers confirmation
        if (typeof navigateTo === 'function') {
          navigateTo('confirmation.php?commande=' + cmdData.id_commande);
        } else {
          window.location.href = 'confirmation.php?commande=' + cmdData.id_commande;
        }
      } else {
        errEl.textContent = cmdData.error || 'Erreur lors de la validation.';
        resetPayBtn();
      }
    }

  } catch(e) {
    console.error(e);
    errEl.textContent = 'Erreur réseau. Veuillez réessayer.';
    resetPayBtn();
  }
}

function resetPayBtn() {
  var btn    = document.getElementById('pay-btn');
  var label  = document.getElementById('pay-btn-text');
  var loader = document.getElementById('pay-btn-loader');
  btn.disabled         = false;
  label.style.display  = 'inline';
  loader.style.display = 'none';
}
</script>
<?php endif; ?>
