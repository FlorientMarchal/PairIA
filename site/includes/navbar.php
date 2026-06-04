<?php
$current = basename($_SERVER['PHP_SELF'], '.php');
?>
<nav>
  <div class="logo">Pair<span>IA</span></div>

  <ul class="nav-links" id="nav-links">
    <li>
      <a href="index.php" class="<?= $current === 'index' ? 'active' : '' ?>">
        Catalogue
      </a>
    </li>
    <?php if (isset($_SESSION['client_id'])): ?>
    <li>
      <a href="compte.php?ajax=1" class="<?= $current === 'compte' ? 'active' : '' ?>">
        Mon compte
      </a>
    </li>
    <li>
    <a href="favoris.php"
       class="<?= $current === 'favoris' ? 'active' : '' ?>">
      ❤️ Favoris
    </a>
    </li>
    <?php endif; ?>
  </ul>

  <div class="nav-right">
    <?php if (!isset($_SESSION['client_id'])): ?>
      <a href="connexion.php" class="cart-btn" style="background:var(--dark);border:1px solid rgba(255,255,255,0.2)">
        Se connecter
      </a>
    <?php endif; ?>
    <a href="panier.php" class="cart-btn">
      Panier
      <span class="cart-count" id="cart-count">0</span>
    </a>
    <button class="burger" id="burger" aria-label="Menu">
      <span></span><span></span><span></span>
    </button>
  </div>
</nav>