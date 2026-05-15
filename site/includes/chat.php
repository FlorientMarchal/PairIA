<?php
// includes/chat.php

$page = basename($_SERVER['PHP_SELF'], '.php');

$product_name = isset($article['nom']) ? $article['nom'] : null;
$categorie    = isset($article['categorie']) ? $article['categorie'] : '';

/* MESSAGE D'ACCUEIL */
if ($page === 'article' && $product_name) {

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

    $det = isset($determinants[$categorie]) ? $determinants[$categorie] : 'le';

    $welcome = "Je vois que vous regardez {$det} <strong style='color:var(--accent)'>{$product_name}</strong>. Posez-moi n'importe quelle question sur ce modèle — taille, matériaux, comparaison !";

} elseif ($page === 'panier') {

    $welcome = "Votre sélection est prête 🛍 Puis-je vous suggérer des articles complémentaires ou avez-vous une question sur votre commande ?";

} else {

    $welcome = "Bonjour ! 👋 Je suis votre conseiller personnel. Décrivez-moi le style, l'usage ou le budget que vous recherchez et je trouve la paire parfaite pour vous.";
}

/* SUGGESTIONS */
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

  <!-- HEADER -->
  <div class="chat-panel-head">
    <div class="chat-avatar">
      <span class="chat-avatar-icon">✦</span>
      <span class="chat-online-dot"></span>
    </div>

    <div class="chat-head-info">
      <div class="chat-head-name">Conseiller PairIA</div>
      <div class="chat-head-status">Personal Shopper IA · En ligne</div>
    </div>

    <button class="chat-reset-btn" onclick="resetConversation()" title="Effacer la conversation">↺</button>
  </div>

  <!-- SUGGESTIONS -->
  <div class="chat-suggestions">
    <div class="chat-suggestions-label">Suggestions</div>

    <div class="chat-chips">
      <?php foreach ($chips as $chip): ?>
        <button class="chat-chip" data-msg="<?= htmlspecialchars($chip, ENT_QUOTES, 'UTF-8') ?>">
          <?= htmlspecialchars($chip, ENT_QUOTES, 'UTF-8') ?>
        </button>
      <?php endforeach; ?>
    </div>
  </div>

  <!-- MESSAGES -->
  <div class="chat-messages" id="messages">
    <div class="chat-msg bot">
      <div class="chat-bubble"><?= $welcome ?></div>
      <div class="chat-time">maintenant</div>
    </div>
  </div>

  <!-- INPUT -->
  <div class="chat-input-area">
    <div id="image-preview-bar"></div>

    <div class="chat-input-row">
      <input
        class="chat-input"
        id="chat-input"
        type="text"
        placeholder="Posez votre question..."
        onkeydown="if(event.key==='Enter'){ event.preventDefault(); sendFromInput(); }"
      >

      <button
        class="chat-voice-btn"
        id="voice-btn"
        type="button"
        onclick="toggleVoice()"
        title="Dicter un message"
        style="display:none">
        🎤
      </button>

      <button
        class="chat-image-btn"
        type="button"
        onclick="openImageSearch()"
        title="Rechercher par image">
        📷
      </button>

      <button
        class="chat-send-btn"
        type="button"
        onclick="sendFromInput()">
        →
      </button>
    </div>
  </div>

</div>

<!-- MOBILE -->
<div class="chat-overlay" id="chat-overlay" onclick="closeChatMobile()"></div>

<button class="chat-fab" id="chat-fab" onclick="toggleChatMobile()" aria-label="Ouvrir le conseiller">
  ✦
</button>