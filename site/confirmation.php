<?php
session_start();
require_once 'includes/bd.php';

if (!isset($_SESSION['client_id'])) {
    header('Location: connexion.php');
    exit;
}

$id_commande = (int)($_GET['commande'] ?? 0);
$client_id   = (int)$_SESSION['client_id'];

// Récupérer la commande (en s'assurant qu'elle appartient bien au client connecté)
$stmt = $pdo->prepare("
    SELECT c.*, cl.prenom, cl.nom
    FROM commandes c
    JOIN clients cl ON cl.id_client = c.id_client
    WHERE c.id_commande = ? AND c.id_client = ?
");
$stmt->execute([$id_commande, $client_id]);
$commande = $stmt->fetch();

if (!$commande) {
    header('Location: index.php');
    exit;
}

// Récupérer les lignes de commande
$stmtLignes = $pdo->prepare("
    SELECT * FROM lignes_commande WHERE id_commande = ?
");
$stmtLignes->execute([$id_commande]);
$lignes = $stmtLignes->fetchAll();

$is_ajax = isset($_GET['ajax']);
if (!$is_ajax) {
    header('Location: shell.php');
    exit;
}
?>
<title>PairIA — Commande confirmée ✓</title>

<div id="ajax-hero"></div>

<div id="ajax-content">
<div class="confirmation-area">

  <!-- Bannière succès -->
  <div class="confirmation-success-banner">
    <div class="confirmation-check">✓</div>
    <div>
      <h1>Votre commande a bien été enregistrée !</h1>
      <p>Un email de confirmation vous sera envoyé à l'adresse de votre compte.</p>
    </div>
  </div>

  <!-- Détails commande -->
  <div class="confirmation-layout">

    <div class="confirmation-card">
      <div class="confirmation-card-title">
        📦 Commande n°<?= $id_commande ?>
        <span class="confirmation-statut"><?= htmlspecialchars($commande['statut']) ?></span>
      </div>
      <div class="confirmation-date">
        Passée le <?= date('d/m/Y à H:i', strtotime($commande['date_commande'])) ?>
      </div>

      <!-- Lignes -->
      <?php foreach ($lignes as $l): ?>
        <div class="confirmation-item">
          <div class="confirmation-item-info">
            <div class="confirmation-item-name"><?= htmlspecialchars($l['nom_article']) ?></div>
            <div class="confirmation-item-meta">
              Pointure <?= htmlspecialchars($l['taille']) ?>
              · <?= htmlspecialchars($l['couleur']) ?>
              · Qté <?= (int)$l['quantite'] ?>
            </div>
          </div>
          <div class="confirmation-item-prix">
            <?= number_format($l['sous_total'], 2, ',', ' ') ?> €
          </div>
        </div>
      <?php endforeach; ?>

      <!-- Totaux -->
      <div class="confirmation-totaux">
        <div class="conf-total-row">
          <span>Sous-total</span>
          <span><?= number_format($commande['sous_total'], 2, ',', ' ') ?> €</span>
        </div>
        <div class="conf-total-row">
          <span>Livraison</span>
          <span>
            <?= $commande['frais_livraison'] == 0
                ? 'Gratuite'
                : number_format($commande['frais_livraison'], 2, ',', ' ') . ' €'
            ?>
          </span>
        </div>
        <div class="conf-total-row conf-grand-total">
          <span>Total payé</span>
          <span><?= number_format($commande['total'], 2, ',', ' ') ?> €</span>
        </div>
      </div>
    </div>

    <!-- Colonne droite -->
    <div>
      <!-- Adresse -->
      <?php if (!empty($commande['adresse_livraison'])): ?>
        <div class="confirmation-card" style="margin-bottom:16px">
          <div class="confirmation-card-title">📍 Livraison prévue</div>
          <div style="font-size:0.875rem;color:var(--dark,#1a1410);line-height:1.6;white-space:pre-line">
            <?= htmlspecialchars($commande['adresse_livraison']) ?>
          </div>
          <div style="margin-top:10px;font-size:0.8rem;color:var(--gray,#7a6f66)">
            🚚 Livraison estimée sous 3 à 5 jours ouvrés
          </div>
        </div>
      <?php endif; ?>

      <!-- Actions -->
      <div class="confirmation-actions">
        <a href="index.php" class="conf-btn-primary">🛍 Continuer mes achats</a>
        <a href="compte.php" class="conf-btn-secondary">📋 Voir mes commandes</a>
      </div>
    </div>

  </div>

</div>
</div>
