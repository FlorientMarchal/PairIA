<?php
session_start();
require_once 'includes/bd.php';

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

    if ($action === 'infos') {
        $nom    = trim($_POST['nom']    ?? '');
        $prenom = trim($_POST['prenom'] ?? '');
        $mail   = trim($_POST['mail']   ?? '');
        $tel    = trim($_POST['tel']    ?? '');
        if (empty($nom) || empty($prenom) || empty($mail)) {
            $error = 'Nom, prénom et email sont obligatoires.';
        } else {
            $check = $pdo->prepare("SELECT id_client FROM clients WHERE mail = ? AND id_client != ?");
            $check->execute([$mail, $client_id]);
            if ($check->fetch()) {
                $error = 'Cet email est déjà utilisé.';
            } else {
                $pdo->prepare("UPDATE clients SET nom=?, prenom=?, mail=?, numero=? WHERE id_client=?")
                    ->execute([$nom, $prenom, $mail, $tel, $client_id]);
                $_SESSION['client']['nom']    = $nom;
                $_SESSION['client']['prenom'] = $prenom;
                $_SESSION['client']['mail']   = $mail;
                $success = 'Informations mises à jour avec succès.';
            }
        }
    }

    elseif ($action === 'mdp') {
        $ancien  = $_POST['ancien_mdp']  ?? '';
        $nouveau = $_POST['nouveau_mdp'] ?? '';
        $confirm = $_POST['confirm_mdp'] ?? '';
        $stmt = $pdo->prepare("SELECT mdp FROM clients WHERE id_client = ?");
        $stmt->execute([$client_id]);
        $row = $stmt->fetch();
        if (!$row || !password_verify($ancien, $row['mdp'])) {
            $error = 'Mot de passe actuel incorrect.';
        } elseif (password_verify($nouveau, $row['mdp'])) {
            $error = 'Le nouveau mot de passe doit être différent de l\'ancien.';
        } elseif (strlen($nouveau) < 6) {
            $error = 'Le mot de passe doit contenir au moins 6 caractères.';
        } elseif ($nouveau !== $confirm) {
            $error = 'Les mots de passe ne correspondent pas.';
        } else {
            $pdo->prepare("UPDATE clients SET mdp=? WHERE id_client=?")
                ->execute([password_hash($nouveau, PASSWORD_DEFAULT), $client_id]);
            $success = 'Mot de passe modifié avec succès.';
        }
    }

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

// ================= HISTORIQUE COMMANDES =================
$stmtCmds = $pdo->prepare("
    SELECT c.*,
           COUNT(lc.id_ligne) AS nb_articles
    FROM commandes c
    LEFT JOIN lignes_commande lc ON lc.id_commande = c.id_commande
    WHERE c.id_client = ?
    GROUP BY c.id_commande
    ORDER BY c.date_commande DESC
");
$stmtCmds->execute([$client_id]);
$commandes = $stmtCmds->fetchAll();

$is_ajax = isset($_GET['ajax']);
if (!$is_ajax) {
    header('Location: shell.php#compte.php');
    exit;
}

// Statut → label lisible
function statutLabel(string $statut): array {
    return match($statut) {
        'en_attente' => ['label' => 'En attente',    'color' => '#f59e0b', 'bg' => '#fffbeb'],
        'payée'      => ['label' => 'Payée ✓',        'color' => '#16a34a', 'bg' => '#f0fdf4'],
        'expédiée'   => ['label' => 'Expédiée 🚚',    'color' => '#2563eb', 'bg' => '#eff6ff'],
        'livrée'     => ['label' => 'Livrée ✓✓',      'color' => '#059669', 'bg' => '#ecfdf5'],
        'annulée'    => ['label' => 'Annulée',         'color' => '#dc2626', 'bg' => '#fef2f2'],
        default      => ['label' => ucfirst($statut), 'color' => '#6b7280', 'bg' => '#f9fafb'],
    };
}

$nbCommandes  = count($commandes);
$totalDepense = array_sum(array_column($commandes, 'total'));
?>

<title>PairIA — Mon compte</title>

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
    <div class="compte-hero-stats">
      <div>
        <span class="compte-hero-stat-val"><?= $nbCommandes ?></span>
        <span class="compte-hero-stat-lbl">Commandes</span>
      </div>
      <div>
        <span class="compte-hero-stat-val"><?= number_format($totalDepense, 0, ',', ' ') ?> €</span>
        <span class="compte-hero-stat-lbl">Total dépensé</span>
      </div>
    </div>
  </div>

  <!-- ALERTS -->
  <?php if ($success): ?>
    <div class="compte-alert success"><?= htmlspecialchars($success) ?></div>
  <?php endif; ?>
  <?php if ($error): ?>
    <div class="compte-alert error"><?= htmlspecialchars($error) ?></div>
  <?php endif; ?>

  <!-- PROFIL -->
  <div class="compte-section-title">Mon profil</div>
  <div class="compte-grid">

    <!-- Colonne gauche : Infos personnelles -->
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

    <!-- Colonne droite : Sécurité + Adresse empilées -->
    <div class="compte-grid-col">

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

    </div><!-- fin .compte-grid-col -->

  </div><!-- fin .compte-grid -->

  <!-- COMMANDES -->
  <div class="compte-section-title">Mes commandes</div>
  <div>

    <?php if (empty($commandes)): ?>
      <div class="compte-empty">
        <div class="compte-empty-icon">📦</div>
        <div class="compte-empty-title">Aucune commande pour le moment</div>
        <p>Vos achats apparaîtront ici après votre première commande.</p>
        <a href="index.php" class="compte-btn" style="display:inline-block;text-decoration:none">
          🛍 Découvrir le catalogue
        </a>
      </div>

    <?php else: ?>

      <div class="commandes-list">
        <?php foreach ($commandes as $cmd):
          $s = statutLabel($cmd['statut']);
        ?>
          <div class="commande-card" id="cmd-<?= $cmd['id_commande'] ?>">

            <div class="commande-header">
              <div class="commande-header-left">
                <div class="commande-num">Commande n°<?= $cmd['id_commande'] ?></div>
                <div class="commande-date">
                  <?= date('d/m/Y à H:i', strtotime($cmd['date_commande'])) ?>
                  · <?= $cmd['nb_articles'] ?> article<?= $cmd['nb_articles'] > 1 ? 's' : '' ?>
                </div>
              </div>
              <div class="commande-header-right">
                <span class="commande-statut"
                  style="color:<?= $s['color'] ?>;background:<?= $s['bg'] ?>">
                  <?= $s['label'] ?>
                </span>
                <div class="commande-total">
                  <?= number_format($cmd['total'], 2, ',', ' ') ?> €
                </div>
              </div>
            </div>

            <div class="commande-detail" id="detail-<?= $cmd['id_commande'] ?>" style="display:none">
              <?php
                $stmtL = $pdo->prepare("SELECT * FROM lignes_commande WHERE id_commande = ?");
                $stmtL->execute([$cmd['id_commande']]);
                $lignes = $stmtL->fetchAll();
              ?>
              <?php foreach ($lignes as $l): ?>
                <div class="commande-ligne">
                  <div class="commande-ligne-info">
                    <div class="commande-ligne-nom"><?= htmlspecialchars($l['nom_article']) ?></div>
                    <div class="commande-ligne-meta">
                      Pointure <?= htmlspecialchars($l['taille']) ?>
                      · <?= htmlspecialchars($l['couleur']) ?>
                      · Qté <?= (int)$l['quantite'] ?>
                    </div>
                  </div>
                  <div class="commande-ligne-prix">
                    <?= number_format($l['sous_total'], 2, ',', ' ') ?> €
                  </div>
                </div>
              <?php endforeach; ?>

              <?php if (!empty($cmd['adresse_livraison'])): ?>
                <div class="commande-adresse">
                  📍 <?= nl2br(htmlspecialchars($cmd['adresse_livraison'])) ?>
                </div>
              <?php endif; ?>
            </div>

            <button class="commande-toggle-btn"
              onclick="toggleCommande(<?= $cmd['id_commande'] ?>, this)">
              Voir le détail ▾
            </button>

          </div>
        <?php endforeach; ?>
      </div>

    <?php endif; ?>
  </div>

  <!-- DECONNEXION -->
  <div class="compte-actions" style="margin-top:40px;text-align:center;">
    <a href="deconnexion.php" class="compte-logout">Se déconnecter</a>
  </div>

</div>
</div>

<script>
function toggleCommande(id, btn) {
  const detail = document.getElementById('detail-' + id);
  if (!detail) return;
  const isOpen = detail.style.display !== 'none';
  detail.style.display = isOpen ? 'none' : 'block';
  btn.textContent = isOpen ? 'Voir le détail ▾' : 'Masquer le détail ▴';
}

document.querySelectorAll('.compte-card form').forEach(form => {
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        const formData = new FormData(this);
        document.querySelectorAll('.compte-alert').forEach(el => el.remove());
        try {
            const res  = await fetch('compte.php?ajax=1', { method: 'POST', body: formData });
            const html = await res.text();
            const parser = new DOMParser();
            const doc  = parser.parseFromString(html, 'text/html');
            const alert = doc.querySelector('.compte-alert');
            if (alert) {
                const area = document.querySelector('.compte-area');
                if (area) area.prepend(alert);
            }
        } catch(err) {
            console.error('Erreur AJAX compte:', err);
        }
    });
});
</script>