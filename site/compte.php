<?php
session_start();
require_once 'includes/bd.php';

if (!isset($_SESSION['client_id'])) {
    header('Location: connexion.php');
    exit;
}

$client_id = $_SESSION['client_id'];
$success   = '';
$error     = '';

// Traitement formulaire modification
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $action = $_POST['action'] ?? '';

    if ($action === 'infos') {
        $nom    = trim($_POST['nom']    ?? '');
        $prenom = trim($_POST['prenom'] ?? '');
        $mail   = trim($_POST['mail']   ?? '');
        $tel    = trim($_POST['tel']    ?? '');
        $adresse= trim($_POST['adresse']?? '');

        if (empty($nom) || empty($prenom) || empty($mail)) {
            $error = 'Nom, prénom et email sont obligatoires.';
        } else {
            // Vérifie que l'email n'est pas déjà pris par un autre client
            $check = $pdo->prepare("SELECT id_client FROM clients WHERE mail = ? AND id_client != ?");
            $check->execute([$mail, $client_id]);
            if ($check->fetch()) {
                $error = 'Cet email est déjà utilisé par un autre compte.';
            } else {
                $pdo->prepare("
                    UPDATE clients SET nom=?, prenom=?, mail=?, numero=?, adresse=?
                    WHERE id_client=?
                ")->execute([$nom, $prenom, $mail, $tel, $adresse, $client_id]);

                // Met à jour la session
                $_SESSION['client']['nom']    = $nom;
                $_SESSION['client']['prenom'] = $prenom;
                $_SESSION['client']['mail']   = $mail;
                $success = 'Vos informations ont été mises à jour.';
            }
        }
    }

    if ($action === 'mdp') {
        $ancien  = $_POST['ancien_mdp']  ?? '';
        $nouveau = $_POST['nouveau_mdp'] ?? '';
        $confirm = $_POST['confirm_mdp'] ?? '';

        $stmt = $pdo->prepare("SELECT mdp FROM clients WHERE id_client = ?");
        $stmt->execute([$client_id]);
        $row = $stmt->fetch();

        if (!password_verify($ancien, $row['mdp'])) {
            $error = 'Mot de passe actuel incorrect.';
        } elseif (strlen($nouveau) < 6) {
            $error = 'Le nouveau mot de passe doit faire au moins 6 caractères.';
        } elseif ($nouveau !== $confirm) {
            $error = 'Les mots de passe ne correspondent pas.';
        } else {
            $pdo->prepare("UPDATE clients SET mdp=? WHERE id_client=?")
                ->execute([password_hash($nouveau, PASSWORD_DEFAULT), $client_id]);
            $success = 'Mot de passe modifié avec succès.';
        }
    }
}

// Charger les infos du client
$stmt = $pdo->prepare("SELECT * FROM clients WHERE id_client = ?");
$stmt->execute([$client_id]);
$client = $stmt->fetch();

$is_ajax = isset($_GET['ajax']);
if (!$is_ajax) {
    header('Location: shell.php');
    exit;
}
?>
<title>PairIA — Mon compte</title>

<div id="ajax-hero"></div>
<div id="ajax-content">
<div class="compte-area">

  <!-- HEADER STYLE HERO -->
  <div class="compte-hero">
    <div class="compte-avatar">
      <?= strtoupper(substr($client['prenom'], 0, 1)) ?>
    </div>

    <div class="compte-hero-info">
      <h1>Bonjour <?= htmlspecialchars($client['prenom']) ?></h1>
      <p><?= htmlspecialchars($client['mail']) ?></p>
    </div>
  </div>

  <?php if ($success): ?>
    <div class="compte-alert success"><?= htmlspecialchars($success) ?></div>
  <?php endif; ?>

  <?php if ($error): ?>
    <div class="compte-alert error"><?= htmlspecialchars($error) ?></div>
  <?php endif; ?>

  <!-- GRID CARDS -->
  <div class="compte-grid">

    <!-- INFOS -->
    <div class="compte-card">
      <div class="compte-card-title">Informations personnelles</div>

      <form method="POST" action="compte.php?ajax=1">
        <input type="hidden" name="action" value="infos">

        <div class="compte-field">
          <label>Prénom</label>
          <input type="text" name="prenom" value="<?= htmlspecialchars($client['prenom']) ?>">
        </div>

        <div class="compte-field">
          <label>Nom</label>
          <input type="text" name="nom" value="<?= htmlspecialchars($client['nom']) ?>">
        </div>

        <div class="compte-field">
          <label>Email</label>
          <input type="email" name="mail" value="<?= htmlspecialchars($client['mail']) ?>">
        </div>

        <button class="compte-btn">Sauvegarder</button>
      </form>
    </div>

    <!-- SECURITE -->
    <div class="compte-card">
      <div class="compte-card-title">Sécurité</div>

      <form method="POST" action="compte.php?ajax=1">
        <input type="hidden" name="action" value="mdp">

        <div class="compte-field">
          <label>Mot de passe actuel</label>
          <input type="password" name="ancien_mdp">
        </div>

        <div class="compte-field">
          <label>Nouveau mot de passe</label>
          <input type="password" name="nouveau_mdp">
        </div>

        <div class="compte-field">
          <label>Confirmation</label>
          <input type="password" name="confirm_mdp">
        </div>

        <button class="compte-btn">Modifier</button>
      </form>
    </div>

  </div>

  <!-- ACTIONS -->
  <div class="compte-actions">
    <a href="deconnexion.php" class="compte-logout">Se déconnecter</a>
  </div>

</div>