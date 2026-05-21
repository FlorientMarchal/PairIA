<?php
session_start();
$error = $_GET['error'] ?? null;
?>

<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <title>Connexion</title>
  <link rel="stylesheet" href="styles/index.css">
</head>
<body>

<h2 style="text-align:center;">Connexion</h2>

<div style="text-align:center;">
  <a href="nouveau.php">Créer un compte</a>
</div>

<?php if ($error): ?>
  <p style="color:red; text-align:center;">
    <?php
      if ($error === 'email') echo "Adresse e-mail introuvable.";
      elseif ($error === 'password') echo "Mot de passe incorrect.";
      elseif ($error === 'empty') echo "Veuillez remplir tous les champs.";
    ?>
  </p>
<?php endif; ?>

<form action="connecter.php" method="post"
      style="max-width:400px;margin:20px auto;display:flex;flex-direction:column;gap:10px;">

  <input type="email" name="mail" placeholder="Email" required>
  <input type="password" name="mdp" placeholder="Mot de passe" required>

  <button type="submit">Se connecter</button>
</form>

</body>
</html>