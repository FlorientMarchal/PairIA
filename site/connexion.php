<?php
session_start();
require_once 'includes/bd.php';
$error = $_GET['error'] ?? null;
?>
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Connexion — PairIA</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;1,9..40,300&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/tabler-icons.min.css">
<link rel="stylesheet" href="styles/global.css">
<link rel="stylesheet" href="styles/auth.css">
</head>
<body>

<?php include 'includes/navbar.php'; ?>

<div class="auth-wrap">
  <div class="auth-card">

    <div class="auth-head">
      <div class="auth-badge">P</div>
      <h1 class="auth-title">Bon retour</h1>
      <p class="auth-sub">
        Pas encore de compte ?
        <a href="nouveau.php">Créer un compte</a>
      </p>
    </div>

    <?php if ($error): ?>
      <div class="auth-alert error">
        <i class="ti ti-alert-circle"></i>
        <span>
          <?php
            if ($error === 'email') echo "Adresse e-mail introuvable.";
            elseif ($error === 'password') echo "Mot de passe incorrect.";
            elseif ($error === 'empty') echo "Veuillez remplir tous les champs.";
            else echo "Une erreur est survenue, veuillez réessayer.";
          ?>
        </span>
      </div>
    <?php endif; ?>

    <form class="auth-form" action="connecter.php" method="post">
      <div class="auth-field">
        <label for="mail">Email</label>
        <input type="email" id="mail" name="mail" placeholder="vous@exemple.com" required>
      </div>

      <div class="auth-field">
        <label for="mdp">Mot de passe</label>
        <input type="password" id="mdp" name="mdp" placeholder="••••••••" required>
      </div>

      <button type="submit" class="auth-submit">Se connecter</button>
    </form>

    <div class="auth-foot">
      <a href="index.php">← Retour au catalogue</a>
    </div>

  </div>
</div>
<?php include 'includes/footer.php'; ?>
</body>
</html>
