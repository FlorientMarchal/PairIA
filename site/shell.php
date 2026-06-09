<?php
session_start();
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
  <link href="https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;1,9..40,300&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/tabler-icons.min.css">
  <link rel="stylesheet" href="styles/global.css">
  <link rel="stylesheet" href="styles/index.css">
  <link rel="stylesheet" href="styles/article.css">
  <link rel="stylesheet" href="styles/panier.css">
   <link rel="stylesheet" href="styles/acheter.css">
  <link rel="stylesheet" href="styles/confirmation.css">
</head>
<body>

<?php include 'includes/navbar.php'; ?>

<!-- Hero full-width, EN DEHORS du split content/chat -->
<div id="spa-hero"></div>

<!-- Split : contenu scrollable + chat fixe -->
<div class="page-layout">
  <div class="page-content" id="main-content">
    <div id="spa-content">
      <div class="loading-placeholder">Chargement…</div>
    </div>
  </div>
  <?php include 'includes/chat.php'; ?>
</div>

<script src="js/global.js"></script>
<script src="js/chat.js"></script>
<script src="js/image_search.js"></script>
<script src="js/voice.js"></script>
<script src="js/spa.js"></script>
<script src="js/comments.js" defer></script>
<script src="js/chat-review.js"></script>

</body>
</html>