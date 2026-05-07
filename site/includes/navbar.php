<?php
// includes/nav.php
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
  </ul>

  <div class="nav-right">
    <a href="panier.php" class="cart-btn">
      Panier
      <span class="cart-count" id="cart-count">0</span>
    </a>
    <button class="burger" id="burger" aria-label="Menu">
      <span></span><span></span><span></span>
    </button>
  </div>
</nav>