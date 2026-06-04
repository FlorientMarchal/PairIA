<?php
// admin/includes/admin_chat.php
// Panneau chatbot admin — à inclure dans index.php admin
?>
<div class="achat-panel" id="achat-panel">

  <!-- EN-TÊTE -->
  <div class="achat-head">
    <div class="achat-avatar">
      <span class="achat-avatar-icon">⚙</span>
      <span class="achat-online-dot"></span>
    </div>
    <div class="achat-head-info">
      <div class="achat-head-name">Assistant Admin</div>
      <div class="achat-head-status">PairIA · Intelligence de gestion</div>
    </div>
    <button class="achat-clear-btn" onclick="adminChatReset()" title="Nouvelle conversation">↺</button>
  </div>

  <!-- SUGGESTIONS RAPIDES -->
  <div class="achat-chips-wrap" id="achat-chips-wrap">
    <div class="achat-chips">
      <button class="achat-chip" data-msg="Montre-moi les statistiques globales">📊 Stats</button>
      <button class="achat-chip" data-msg="Liste les commandes en attente">📦 Commandes en attente</button>
      <button class="achat-chip" data-msg="Quels sont les 10 articles les plus vendus ?">🔥 Top ventes</button>
      <button class="achat-chip" data-msg="Y a-t-il des articles avec un stock faible ?">⚠️ Stock faible</button>
      <button class="achat-chip" data-msg="Montre-moi le chiffre d'affaires des 12 derniers mois">💰 CA mensuel</button>
      <button class="achat-chip" data-msg="Liste les derniers commentaires clients">💬 Commentaires</button>
    </div>
  </div>

  <!-- ZONE MESSAGES -->
  <div class="achat-messages" id="achat-messages">
    <div class="achat-msg bot">
      <div class="achat-bubble">
      Bonjour <strong><?= htmlspecialchars($_SESSION['client']['prenom'] ?? 'Admin') ?></strong> 👋<br>        Je suis votre assistant de gestion PairIA. Posez-moi n'importe quelle question sur vos commandes, votre catalogue, vos clients ou vos ventes.
      </div>
      <div class="achat-time"><?= date('H:i') ?></div>
    </div>
  </div>

  <!-- ZONE DE SAISIE -->
  <div class="achat-input-area">
    <div class="achat-input-row">
      <textarea
        class="achat-input"
        id="achat-input"
        placeholder="Posez votre question à l'assistant..."
        rows="1"
        onkeydown="if(event.key==='Enter' && !event.shiftKey){ event.preventDefault(); adminChatSend(); }"
        oninput="this.style.height='auto'; this.style.height=Math.min(this.scrollHeight,120)+'px';"
      ></textarea>
      <button class="achat-send-btn" type="button" onclick="adminChatSend()" title="Envoyer">→</button>
    </div>
    <div class="achat-hint">Entrée pour envoyer · Maj+Entrée pour saut de ligne</div>
  </div>

</div><!-- fin .achat-panel -->
