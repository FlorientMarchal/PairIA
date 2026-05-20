<?php
// shell.php — coquille SPA permanente
require_once 'includes/bd.php';
?>
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PairIA</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;1,400&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="styles/global.css">
  <link rel="stylesheet" href="styles/index.css">
  <link rel="stylesheet" href="styles/article.css">
  <link rel="stylesheet" href="styles/panier.css">
  <link rel="stylesheet" id="page-css">
</head>
<body>

<?php include 'includes/navbar.php'; ?>

<div class="page-layout">
  <div class="page-content" id="main-content">
    <div id="spa-hero"></div>
    <div id="spa-content">
      <!-- contenu chargé dynamiquement -->
      <div style="padding:2rem;text-align:center;color:#999">Chargement...</div>
    </div>
  </div>

  <?php include 'includes/chat.php'; ?>
</div>

<script src="js/global.js"></script>
<script src="js/chat.js"></script>
<script src="js/image_search.js"></script>
<script src="js/voice.js"></script>
<script src="js/spa.js"></script>
</body>
</html>