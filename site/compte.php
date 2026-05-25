<?php
session_start();
require_once 'includes/bd.php';

// DEBUG (à enlever en prod)
ini_set('display_errors', 1);
error_reporting(E_ALL);

if (!isset($_SESSION['client_id'])) {
    header('Location: connexion.php');
    exit;
}

$client_id = $_SESSION['client_id'];
$success   = '';
$error     = '';

// ================= TRAITEMENT =================
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $action = $_POST['action'] ?? '';

    // ===== INFOS =====
    if ($action === 'infos') {
        $nom     = trim($_POST['nom']    ?? '');
        $prenom  = trim($_POST['prenom'] ?? '');
        $mail    = trim($_POST['mail']   ?? '');
        $tel     = trim($_POST['tel']    ?? '');

        if (empty($nom) || empty($prenom) || empty($mail)) {
            $error = 'Nom, prénom et email sont obligatoires.';
        } else {
            $check = $pdo->prepare("SELECT id_client FROM clients WHERE mail = ? AND id_client != ?");
            $check->execute([$mail, $client_id]);

            if ($check->fetch()) {
                $error = 'Cet email est déjà utilisé.';
            } else {
                $pdo->prepare("
                    UPDATE clients 
                    SET nom=?, prenom=?, mail=?, numero=? 
                    WHERE id_client=?
                ")->execute([$nom, $prenom, $mail, $tel, $client_id]);

                $_SESSION['client']['nom']    = $nom;
                $_SESSION['client']['prenom'] = $prenom;
                $_SESSION['client']['mail']   = $mail;

                $success = 'Informations mises à jour avec succès.';
            }
        }
    }

    // ===== MOT DE PASSE =====
    elseif ($action === 'mdp') {
        $ancien  = $_POST['ancien_mdp']  ?? '';
        $nouveau = $_POST['nouveau_mdp'] ?? '';
        $confirm = $_POST['confirm_mdp'] ?? '';

        $stmt = $pdo->prepare("SELECT mdp FROM clients WHERE id_client = ?");
        $stmt->execute([$client_id]);
        $row = $stmt->fetch();

        if (!$row || !password_verify($ancien, $row['mdp'])) {
            $error = 'Mot de passe actuel incorrect.';
        }
        elseif (password_verify($nouveau, $row['mdp'])) {
            $error = 'Le nouveau mot de passe doit être différent de l\'ancien.';
        }
        elseif (strlen($nouveau) < 6) {
            $error = 'Le mot de passe doit contenir au moins 6 caractères.';
        }
        elseif ($nouveau !== $confirm) {
            $error = 'Les mots de passe ne correspondent pas.';
        }
        else {
            $hash = password_hash($nouveau, PASSWORD_DEFAULT);

            $pdo->prepare("UPDATE clients SET mdp=? WHERE id_client=?")
                ->execute([$hash, $client_id]);

            $success = 'Mot de passe modifié avec succès.';
        }
    }

    // ===== ADRESSE =====
    elseif ($action === 'adresse') {
        $adresse = trim($_POST['adresse'] ?? '');

        if (empty($adresse)) {
            $error = "L'adresse ne peut pas être vide.";
        } else {
            $pdo->prepare("UPDATE clients SET adresse=? WHERE id_client=?")
                ->execute([$adresse, $client_id]);

            $success = "Adresse mise à jour avec succès.";
        }
    }
}

// ================= CHARGEMENT CLIENT =================
$stmt = $pdo->prepare("SELECT * FROM clients WHERE id_client = ?");
$stmt->execute([$client_id]);
$client = $stmt->fetch();

// ================= AJAX =================
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

  <!-- HERO -->
  <div class="compte-hero">
    <div class="compte-avatar">
      <?= strtoupper(substr($client['prenom'], 0, 1)) ?>
    </div>

    <div class="compte-hero-info">
      <h1>Bonjour <?= htmlspecialchars($client['prenom']) ?></h1>
      <p><?= htmlspecialchars($client['mail']) ?></p>
    </div>
  </div>

  <!-- ALERTS -->
  <?php if ($success): ?>
    <div class="compte-alert success"><?= htmlspecialchars($success) ?></div>
  <?php endif; ?>

  <?php if ($error): ?>
    <div class="compte-alert error"><?= htmlspecialchars($error) ?></div>
  <?php endif; ?>

  <!-- GRID -->
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

        <div class="compte-field">
          <label>Téléphone</label>
          <input type="text" name="tel" value="<?= htmlspecialchars($client['numero']) ?>">
        </div>

        <button class="compte-btn">Sauvegarder</button>
      </form>
    </div>

    <!-- MOT DE PASSE -->
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

    <!-- ADRESSE -->
    <div class="compte-card">
      <div class="compte-card-title">📍 Adresse de livraison</div>

      <form method="POST" action="compte.php?ajax=1">
        <input type="hidden" name="action" value="adresse">

        <div class="compte-field">
          <label>Adresse</label>
          <textarea name="adresse" rows="3"><?= htmlspecialchars($client['adresse'] ?? '') ?></textarea>
        </div>

        <button class="compte-btn">Mettre à jour</button>
      </form>
    </div>

  </div>

  <!-- ACTIONS -->
  <div class="compte-actions">
    <a href="deconnexion.php" class="compte-logout">Se déconnecter</a>
  </div>

</div>
</div>

<script>
// AJAX FORM
document.querySelectorAll('.compte-card form').forEach(form => {
    form.addEventListener('submit', async function(e) {
        e.preventDefault();

        const formData = new FormData(this);
        const action = formData.get('action');

        document.querySelectorAll('.compte-alert').forEach(el => el.remove());

        try {
            const res = await fetch('compte.php?ajax=1', {
                method: 'POST',
                body: formData
            });

            const html = await res.text();

            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');

            const alert = doc.querySelector('.compte-alert');
            if (alert) {
                const area = document.querySelector('.compte-area');
                const grid = document.querySelector('.compte-grid');
                area.insertBefore(alert, grid);
            }

            if (action === 'mdp') {
                this.querySelectorAll('input[type="password"]').forEach(i => i.value = '');
            }

        } catch(err) {
            console.error('Erreur AJAX compte:', err);
        }
    });
});
</script>