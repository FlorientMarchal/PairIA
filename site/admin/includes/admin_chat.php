<?php
// admin/includes/admin_chat.php
?>
<div class="achat-panel" id="achat-panel">

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

  <div class="achat-chips-wrap" id="achat-chips-wrap">
    <div class="achat-chips">
      <button class="achat-chip" data-msg="Montre-moi les statistiques globales">📊 Stats</button>
      <button class="achat-chip" data-msg="Liste les commandes en attente">📦 En attente</button>
      <button class="achat-chip" data-msg="Quels sont les 10 articles les plus vendus ?">🔥 Top ventes</button>
      <button class="achat-chip" data-msg="Y a-t-il des articles avec un stock faible ?">⚠️ Stock faible</button>
      <button class="achat-chip" data-msg="Montre-moi le chiffre d'affaires des 12 derniers mois">💰 CA mensuel</button>
      <button class="achat-chip" data-msg="Ajoute un nouvel article au catalogue">➕ Ajouter article</button>
    </div>
  </div>

  <div class="achat-messages" id="achat-messages">
    <div class="achat-msg bot">
      <div class="achat-bubble">
        Bonjour <strong><?= htmlspecialchars($_SESSION['client']['prenom'] ?? 'Admin') ?></strong> 👋<br>
        Je suis votre assistant de gestion PairIA. Posez-moi n'importe quelle question sur vos commandes, votre catalogue, vos clients ou vos ventes.
      </div>
      <div class="achat-time"><?= date('H:i') ?></div>
    </div>
  </div>

  <!-- Zone image preview -->
  <div id="admin-image-preview" style="display:none;align-items:center;padding:.5rem 1rem;background:rgba(255,255,255,.05);gap:.5rem">
    <button onclick="clearImagePreview()" style="background:none;border:none;color:rgba(255,255,255,.5);cursor:pointer;font-size:1rem;flex-shrink:0">✕</button>
  </div>
  <div id="admin-upload-status" style="font-size:.72rem;color:rgba(255,255,255,.4);padding:0 1rem .25rem;min-height:1rem"></div>

  <div class="achat-input-area">
    <div class="achat-input-row">
      <!-- Bouton trombone upload image -->
      <label class="achat-attach-btn" title="Joindre une image">
        📎
        <input type="file" id="admin-image-input" accept="image/*" style="display:none">
      </label>

      <textarea
        class="achat-input"
        id="achat-input"
        placeholder="Posez votre question ou envoyez une image..."
        rows="1"
        onkeydown="if(event.key==='Enter' && !event.shiftKey){ event.preventDefault(); adminChatSend(); }"
        oninput="this.style.height='auto'; this.style.height=Math.min(this.scrollHeight,120)+'px';"
      ></textarea>
      <button class="achat-send-btn" type="button" onclick="adminChatSend()" title="Envoyer">→</button>
    </div>
    <div class="achat-hint">Entrée pour envoyer · Maj+Entrée pour saut de ligne</div>
  </div>

</div>
