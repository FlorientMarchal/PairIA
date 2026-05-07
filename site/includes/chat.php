<?php
// includes/chat.php
// Personal shopper IA — toujours visible à droite

$page = basename($_SERVER['PHP_SELF'], '.php');

// Sur la fiche article, $article est disponible depuis article.php
$product_name = isset($article['nom'])       ? $article['nom']       : null;
$categorie    = isset($article['categorie']) ? $article['categorie'] : '';

/* ══════════════════════════════════════
   MESSAGE D'ACCUEIL
══════════════════════════════════════ */
if ($page === 'article' && $product_name) {

    // Déterminant selon la catégorie
    $determinants = [
        'Baskets lifestyle'  => 'les',
        'Baskets sport'      => 'les',
        'Bottines'           => 'les',
        'Danse'              => 'les chaussures de danse',
        'Espadrilles'        => 'les',
        'Imperméables'       => 'les',
        'Indoor'             => 'les chaussures',
        'Marche'             => 'les chaussures de marche',
        'Minimalistes'       => 'les',
        'Mocassins'          => 'les',
        'Montantes légères'  => 'les',
        'Randonnée'          => 'les chaussures de randonnée',
        'Running'            => 'les chaussures de running',
        'Sabots'             => 'les',
        'Sandales'           => 'les',
        'Slip-on'            => 'les',
        'Sécurité'           => 'les chaussures de sécurité',
        'Talons'             => 'les',
        'Training'           => 'les chaussures de training',
        'Vegan'              => 'les',
    ];

    $det     = isset($determinants[$categorie]) ? $determinants[$categorie] : 'le';
    $welcome = "Je vois que vous regardez {$det} <strong style='color:var(--accent)'>{$product_name}</strong>. Posez-moi n'importe quelle question sur ce modèle — taille, matériaux, comparaison !";

} elseif ($page === 'panier') {
    $welcome = "Votre sélection est prête 🛍 Puis-je vous suggérer des articles complémentaires ou avez-vous une question sur votre commande ?";
} else {
    $welcome = "Bonjour ! 👋 Je suis votre conseiller personnel. Décrivez-moi le style, l'usage ou le budget que vous recherchez et je trouve la paire parfaite pour vous.";
}

/* ══════════════════════════════════════
   SUGGESTIONS RAPIDES
══════════════════════════════════════ */
if ($page === 'article' && $product_name) {
    $chips = [
        'Tailles disponibles ?',
        'Matériaux ?',
        'Comparer avec un autre modèle',
        'Alternatives moins chères',
    ];
} elseif ($page === 'panier') {
    $chips = [
        'Compléments',
        'Code promo ?',
        'Mon choix est bon ?',
    ];
} else {
    $chips = [
        'Chaussures imperméables',
        'Moins de 80€',
        'Pour le running',
        'Style casual',
        'Pointure 42',
    ];
}
?>

<div class="chat-panel" id="chat-panel">

  <!-- En-tête personal shopper -->
  <div class="chat-panel-head">
    <div class="chat-avatar">
      <span class="chat-avatar-icon">✦</span>
      <span class="chat-online-dot"></span>
    </div>
    <div class="chat-head-info">
      <div class="chat-head-name">Conseiller PairIA</div>
      <div class="chat-head-status">Personal Shopper IA · En ligne</div>
    </div>
  </div>

  <!-- Suggestions rapides -->
  <div class="chat-suggestions">
    <div class="chat-suggestions-label">Suggestions</div>
    <div class="chat-chips">
      <?php foreach ($chips as $chip): ?>
        <button class="chat-chip" onclick="sendMessage('<?= htmlspecialchars($chip) ?>')">
          <?= htmlspecialchars($chip) ?>
        </button>
      <?php endforeach; ?>
    </div>
  </div>

  <!-- Messages -->
  <div class="chat-messages" id="messages">
    <div class="chat-msg bot">
      <div class="chat-bubble"><?= $welcome ?></div>
      <div class="chat-time">maintenant</div>
    </div>
  </div>

  <!-- Input -->
  <div class="chat-input-area">
    <input
      class="chat-input"
      id="chat-input"
      type="text"
      placeholder="Posez votre question..."
      onkeydown="if(event.key==='Enter') sendFromInput()"
    >
    <button class="chat-send-btn" onclick="sendFromInput()">→</button>
  </div>

</div>

<!-- Overlay mobile -->
<div class="chat-overlay" id="chat-overlay" onclick="closeChatMobile()"></div>

<!-- Bouton flottant mobile -->
<button class="chat-fab" id="chat-fab" onclick="toggleChatMobile()" aria-label="Ouvrir le conseiller">
  ✦
</button>