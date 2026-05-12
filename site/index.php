<?php
require_once 'includes/bd.php';

$stmt = $pdo->query("
    SELECT
        a.*,
        GROUP_CONCAT(DISTINCT sc.taille ORDER BY sc.taille SEPARATOR ',') AS tailles,
        GROUP_CONCAT(DISTINCT sc.couleur ORDER BY sc.couleur SEPARATOR ',') AS couleurs
    FROM articles a
    LEFT JOIN size_color sc ON sc.id_shoes = a.id_shoes
    GROUP BY a.id_shoes
    ORDER BY a.id_shoes
");
$articles = $stmt->fetchAll();

$categories = $pdo->query("SELECT DISTINCT categorie FROM articles ORDER BY categorie")->fetchAll(PDO::FETCH_COLUMN);
$genres     = $pdo->query("SELECT DISTINCT genre FROM articles ORDER BY genre")->fetchAll(PDO::FETCH_COLUMN);
$marques    = $pdo->query("SELECT DISTINCT marque FROM articles ORDER BY marque")->fetchAll(PDO::FETCH_COLUMN);
$tailles    = $pdo->query("SELECT DISTINCT taille FROM size_color ORDER BY taille")->fetchAll(PDO::FETCH_COLUMN);
$couleurs   = $pdo->query("SELECT DISTINCT couleur FROM size_color ORDER BY couleur")->fetchAll(PDO::FETCH_COLUMN);
$prix_max   = (int) ceil($pdo->query("SELECT MAX(Prix) FROM articles")->fetchColumn());
?>
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PairIA — Catalogue</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;1,400&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="styles/global.css">
  <link rel="stylesheet" href="styles/index.css">
</head>
<body>

<?php include 'includes/navbar.php'; ?>

<!-- HERO -->
<div class="hero">
  <h1>Trouvez vos chaussures<br>en <em>décrivant</em> ce que vous voulez</h1>
  <p>Pas besoin de filtres — décrivez votre usage, budget et style et notre IA trouve la paire parfaite.</p>
  <div class="hero-search">
    <input id="hero-input" type="text"
      placeholder="Ex: Chaussures de rando imperméables pas trop chères..."
      onkeydown="if(event.key==='Enter'){ event.preventDefault(); heroSend(); }">
    <button type="button" onclick="heroSend()">Trouver →</button>
  </div>
  <div class="hero-chips">
    <!--
      ✅ CORRECTION : type="button" sur tous les boutons hero
      Sans type="button", un bouton dans une page peut déclencher
      un submit et recharger la page, réinitialisant conversationHistory
    -->
    <button class="hero-chip" type="button" onclick="heroQuestion('Chaussures imperméables')">Imperméables</button>
    <button class="hero-chip" type="button" onclick="heroQuestion('Moins de 80€')">− 80 €</button>
    <button class="hero-chip" type="button" onclick="heroQuestion('Pour le running')">Running</button>
    <button class="hero-chip" type="button" onclick="heroQuestion('Style casual')">Casual</button>
    <button class="hero-chip" type="button" onclick="heroQuestion('Pointure 42')">Pointure 42</button>
  </div>
</div>

<!-- LAYOUT -->
<div class="page-layout">
  <div class="page-content">
    <div class="catalog-area">

      <div class="catalog-top">
        <div class="catalog-title">
          Catalogue
          <span class="catalog-count" id="catalog-count"><?= count($articles) ?> produits</span>
        </div>

        <div class="filter-bar">

          <!-- Catégorie -->
          <div class="dropdown" id="dd-categorie">
            <button class="dd-btn" type="button" onclick="toggleDropdown('dd-categorie')">
              Catégorie <span class="dd-arrow">▾</span>
            </button>
            <div class="dd-menu">
              <?php foreach ($categories as $cat): ?>
                <label class="dd-item">
                  <input type="checkbox" data-filter="categorie" value="<?= htmlspecialchars($cat) ?>" onchange="applyFilters()">
                  <?= htmlspecialchars($cat) ?>
                </label>
              <?php endforeach; ?>
            </div>
          </div>

          <!-- Genre -->
          <div class="dropdown" id="dd-genre">
            <button class="dd-btn" type="button" onclick="toggleDropdown('dd-genre')">
              Genre <span class="dd-arrow">▾</span>
            </button>
            <div class="dd-menu">
              <?php foreach ($genres as $g): ?>
                <label class="dd-item">
                  <input type="checkbox" data-filter="genre" value="<?= htmlspecialchars($g) ?>" onchange="applyFilters()">
                  <?= htmlspecialchars($g) ?>
                </label>
              <?php endforeach; ?>
            </div>
          </div>

          <!-- Marque -->
          <div class="dropdown" id="dd-marque">
            <button class="dd-btn" type="button" onclick="toggleDropdown('dd-marque')">
              Marque <span class="dd-arrow">▾</span>
            </button>
            <div class="dd-menu">
              <?php foreach ($marques as $m): ?>
                <label class="dd-item">
                  <input type="checkbox" data-filter="marque" value="<?= htmlspecialchars($m) ?>" onchange="applyFilters()">
                  <?= htmlspecialchars($m) ?>
                </label>
              <?php endforeach; ?>
            </div>
          </div>

          <!-- Prix -->
          <div class="dropdown" id="dd-prix">
            <button class="dd-btn" type="button" onclick="toggleDropdown('dd-prix')">
              Prix <span class="dd-arrow">▾</span>
            </button>
            <div class="dd-menu dd-menu-prix">
              <div class="prix-label">Prix maximum : <strong id="prix-val"><?= $prix_max ?> €</strong></div>
              <input type="range" id="f-prix"
                min="0" max="<?= $prix_max ?>" value="<?= $prix_max ?>" step="5"
                oninput="updatePrix(this.value)">
              <div class="prix-range-labels">
                <span>0 €</span>
                <span><?= $prix_max ?> €</span>
              </div>
            </div>
          </div>

          <!-- Pointure -->
          <div class="dropdown" id="dd-taille">
            <button class="dd-btn" type="button" onclick="toggleDropdown('dd-taille')">
              Pointure <span class="dd-arrow">▾</span>
            </button>
            <div class="dd-menu">
              <?php foreach ($tailles as $t): ?>
                <label class="dd-item">
                  <input type="checkbox" data-filter="taille" value="<?= $t ?>" onchange="applyFilters()">
                  <?= $t ?>
                </label>
              <?php endforeach; ?>
            </div>
          </div>

          <!-- Couleur -->
          <div class="dropdown" id="dd-couleur">
            <button class="dd-btn" type="button" onclick="toggleDropdown('dd-couleur')">
              Couleur <span class="dd-arrow">▾</span>
            </button>
            <div class="dd-menu">
              <?php foreach ($couleurs as $c): ?>
                <label class="dd-item">
                  <input type="checkbox" data-filter="couleur" value="<?= htmlspecialchars($c) ?>" onchange="applyFilters()">
                  <?= htmlspecialchars($c) ?>
                </label>
              <?php endforeach; ?>
            </div>
          </div>

          <!-- Reset -->
          <button class="filter-reset-btn" id="filter-reset-btn" type="button" onclick="resetFilters()">
            ✕ Effacer
          </button>

        </div>
      </div>

      <!-- Grille produits -->
      <div class="catalog-grid" id="catalog-grid">
        <?php foreach ($articles as $a): ?>
          <div class="card"
            data-id="<?= $a['id_shoes'] ?>"
            data-categorie="<?= htmlspecialchars($a['categorie']) ?>"
            data-genre="<?= htmlspecialchars($a['genre']) ?>"
            data-marque="<?= htmlspecialchars($a['marque']) ?>"
            data-prix="<?= $a['Prix'] ?>"
            data-tailles="<?= htmlspecialchars($a['tailles'] ?? '') ?>"
            data-couleurs="<?= htmlspecialchars($a['couleurs'] ?? '') ?>">
            <a href="article.php?id=<?= $a['id_shoes'] ?>" class="card-link">
              <div class="card-img">
                <?php if (!empty($a['url_image'])): ?>
                  <img src="<?= htmlspecialchars($a['url_image']) ?>"
                    alt="<?= htmlspecialchars($a['nom']) ?>"
                    onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">
                  <span class="card-emoji" style="display:none">👟</span>
                <?php else: ?>
                  <span class="card-emoji">👟</span>
                <?php endif; ?>
              </div>
              <div class="card-body">
                <div class="card-cat"><?= htmlspecialchars($a['categorie']) ?></div>
                <div class="card-name"><?= htmlspecialchars($a['nom']) ?></div>
                <div class="card-foot">
                  <span class="card-price"><?= number_format($a['Prix'], 2, ',', ' ') ?> €</span>
                  <button class="card-add" type="button" onclick="ajouterPanier(<?= $a['id_shoes'] ?>, event)">+</button>
                </div>
              </div>
            </a>
          </div>
        <?php endforeach; ?>
      </div>

      <div class="no-results" id="no-results" style="display:none">
        Aucun produit ne correspond à vos filtres.
        <button type="button" onclick="resetFilters()">Réinitialiser</button>
      </div>

    </div>
  </div>

  <?php include 'includes/chat.php'; ?>
</div>

<script src="js/global.js"></script>
<script src="js/chat.js"></script>
<script src="js/image_search.js"></script>
<script>

const prixMaxAbsolu = <?= $prix_max ?>;
let prixMax = prixMaxAbsolu;

/* ── Dropdowns ── */
function toggleDropdown(id) {
  const dd = document.getElementById(id);
  const isOpen = dd.classList.contains('open');
  document.querySelectorAll('.dropdown').forEach(d => d.classList.remove('open'));
  if (!isOpen) dd.classList.add('open');
}

document.addEventListener('click', e => {
  if (!e.target.closest('.dropdown')) {
    document.querySelectorAll('.dropdown').forEach(d => d.classList.remove('open'));
  }
});

/* ── État visuel dropdown ── */
function updateDropdownState(id, count) {
  const btn = document.querySelector(`#${id} .dd-btn`);
  if (!btn) return;
  if (count > 0) {
    btn.style.background  = 'var(--accent)';
    btn.style.color       = 'white';
    btn.style.borderColor = 'var(--accent)';
  } else {
    btn.style.background  = '';
    btn.style.color       = '';
    btn.style.borderColor = '';
  }
}

/* ── Prix ── */
function updatePrix(val) {
  prixMax = parseFloat(val);
  document.getElementById('prix-val').textContent = Math.round(val) + ' €';
  const btn = document.querySelector('#dd-prix .dd-btn');
  if (prixMax < prixMaxAbsolu) {
    btn.style.background  = 'var(--accent)';
    btn.style.color       = 'white';
    btn.style.borderColor = 'var(--accent)';
  } else {
    btn.style.background  = '';
    btn.style.color       = '';
    btn.style.borderColor = '';
  }
  applyFilters();
}

/* ── Filtres ── */
function getChecked(filter) {
  return [...document.querySelectorAll(`input[data-filter="${filter}"]:checked`)]
    .map(i => i.value);
}

function applyFilters() {
  const cats     = getChecked('categorie');
  const genres   = getChecked('genre');
  const marques  = getChecked('marque');
  const tailles  = getChecked('taille');
  const couleurs = getChecked('couleur');

  updateDropdownState('dd-categorie', cats.length);
  updateDropdownState('dd-genre',     genres.length);
  updateDropdownState('dd-marque',    marques.length);
  updateDropdownState('dd-taille',    tailles.length);
  updateDropdownState('dd-couleur',   couleurs.length);

  const hasFilters = cats.length || genres.length || marques.length ||
                     tailles.length || couleurs.length || prixMax < prixMaxAbsolu;

  const resetBtn = document.getElementById('filter-reset-btn');
  resetBtn.style.opacity       = hasFilters ? '1' : '0.3';
  resetBtn.style.pointerEvents = hasFilters ? 'all' : 'none';
  resetBtn.style.color         = hasFilters ? 'var(--accent)' : 'var(--gray)';
  resetBtn.style.borderColor   = hasFilters ? '#E8D0C0' : 'var(--border)';

  let visible = 0;
  document.querySelectorAll('.card').forEach(card => {
    const tCard = card.dataset.tailles ? card.dataset.tailles.split(',') : [];
    const cCard = card.dataset.couleurs ? card.dataset.couleurs.split(',') : [];

    const ok =
      (!cats.length     || cats.includes(card.dataset.categorie)) &&
      (!genres.length   || genres.includes(card.dataset.genre)) &&
      (!marques.length  || marques.includes(card.dataset.marque)) &&
      (parseFloat(card.dataset.prix) <= prixMax) &&
      (!tailles.length  || tailles.some(t => tCard.includes(t))) &&
      (!couleurs.length || couleurs.some(c => cCard.includes(c)));

    card.style.display = ok ? 'block' : 'none';
    if (ok) visible++;
  });

  document.getElementById('catalog-count').textContent = visible + ' produit' + (visible > 1 ? 's' : '');
  document.getElementById('no-results').style.display = visible === 0 ? 'block' : 'none';
}

/* ── Reset ── */
function resetFilters() {
  document.querySelectorAll('.dd-menu input[type="checkbox"]').forEach(cb => cb.checked = false);
  prixMax = prixMaxAbsolu;
  document.getElementById('f-prix').value = prixMaxAbsolu;
  document.getElementById('prix-val').textContent = prixMaxAbsolu + ' €';

  ['dd-categorie','dd-genre','dd-marque','dd-prix','dd-taille','dd-couleur'].forEach(id => {
    const btn = document.querySelector(`#${id} .dd-btn`);
    if (btn) { btn.style.background = ''; btn.style.color = ''; btn.style.borderColor = ''; }
  });

  const resetBtn = document.getElementById('filter-reset-btn');
  resetBtn.style.opacity       = '0.3';
  resetBtn.style.pointerEvents = 'none';
  resetBtn.style.color         = 'var(--gray)';
  resetBtn.style.borderColor   = 'var(--border)';

  document.querySelectorAll('.card').forEach(c => c.style.display = 'block');
  document.getElementById('catalog-count').textContent = '<?= count($articles) ?> produits';
  document.getElementById('no-results').style.display = 'none';
}

/* ── Init ── */
document.addEventListener('DOMContentLoaded', () => {

  const resetBtn = document.getElementById('filter-reset-btn');
  resetBtn.style.opacity       = '0.3';
  resetBtn.style.pointerEvents = 'none';

  const params    = new URLSearchParams(window.location.search);
  const categorie = params.get('categorie');
  if (categorie) {
    const checkbox = document.querySelector(
      `input[data-filter="categorie"][value="${categorie}"]`
    );
    if (checkbox) {
      checkbox.checked = true;
      applyFilters();
    }
  }
});

/* ── Hero ── */
function heroSend() {
  const input = document.getElementById('hero-input');
  const text  = input?.value.trim();
  if (!text) return;
  input.value = '';
  sendMessage(text);
  document.querySelector('.page-layout')?.scrollIntoView({ behavior: 'smooth' });
  // ✅ AJOUT : focus sur le chat pour que l'utilisateur voie la réponse
  setTimeout(() => document.getElementById('chat-input')?.focus(), 300);
}

function heroQuestion(text) {
  sendMessage(text);
  document.querySelector('.page-layout')?.scrollIntoView({ behavior: 'smooth' });
  // ✅ AJOUT : focus sur le chat après envoi depuis le hero
  setTimeout(() => document.getElementById('chat-input')?.focus(), 300);
}

/* ── Panier ── */
async function ajouterPanier(id, event) {
  event.preventDefault();
  event.stopPropagation();
  await addToCart(id, 1);
  const btn = event.target;
  btn.textContent = '✓';
  btn.style.background = '#4CAF50';
  setTimeout(() => { btn.textContent = '+'; btn.style.background = ''; }, 1000);
}

</script>
</body>
</html>