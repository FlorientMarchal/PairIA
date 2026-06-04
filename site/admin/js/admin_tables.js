// admin/js/admin_tables.js — v3

// ── Carte complète des couleurs (identique à article.php) ─────────────────
const COULEUR_MAP = {
  'Noir':'#1A1410','Noir mat':'#2A2420','Noir vernis':'#0A0A0A','Charbon':'#3C3C3C',
  'Blanc':'#FFFFFF','Blanc cassé':'#F5F0E8','Crème':'#FFF8E7','Champagne':'#F7E7CE',
  'Naturel':'#EDE0C8','Gris':'#9E9E9E','Gris anthracite':'#424242','Gris ardoise':'#607D8B',
  'Gris chiné':'#A0A0A0','Gris foncé':'#616161','Gris taupe':'#8D8078',
  'Bleu':'#1E88E5','Bleu marine':'#1A237E','Marine':'#0D1B4B','Bleu nuit':'#0D1B4B',
  'Bleu pétrole':'#00695C','Bleu ciel':'#64B5F6','Bleu indigo':'#3949AB',
  'Bleu ardoise':'#5C6BC0','Bleu gris':'#78909C','Bleu océan':'#0277BD','Bleu électrique':'#0D47A1',
  'Rouge':'#E53935','Rouge vif':'#FF1744','Rouge carmin':'#B71C1C','Rouge bordeaux':'#880E4F',
  'Bordeaux':'#7B1022','Corail':'#FF6B4A','Terracotta':'#C0654A','Colorblock rouge-blanc':'#E53935',
  'Vert':'#43A047','Vert kaki':'#827717','Vert olive':'#558B2F','Vert forêt':'#1B5E20',
  'Vert hunter':'#2E7D32','Vert sauge':'#7E9E7E','Vert menthe':'#80CBC4',
  'Vert aqua':'#00BCD4','Vert fluo':'#76FF03','Menthe':'#98E8C8',
  'Rose':'#F48FB1','Rose poudré':'#F8BBD9','Rose gold':'#E8A598','Rose fluo':'#FF4081',
  'Lilas':'#CE93D8','Lavande':'#B39DDB','Pêche':'#FFAB91',
  'Jaune':'#FDD835','Jaune fluo':'#FFFF00','Orange':'#FB8C00','Orange sécurité':'#FF6F00',
  'Or':'#D4AF37','Argent':'#B0BEC5',
  'Marron':'#6D4C41','Marron foncé':'#3E2723','Beige':'#D7CCC8','Beige naturel':'#C8B89A',
  'Kaki':'#8D6E63','Camel':'#C8A96E','Cognac':'#9B4E1A','Sable':'#D2B48C','Nude':'#E8C9A0',
};

const TOUTES_COULEURS = Object.keys(COULEUR_MAP);

// Pointures standard
const TOUTES_TAILLES = [35,36,37,38,39,40,41,42,43,44,45,46,47,48];

// ══════════════════════════════════════════════════════════════
// COMMANDES
// ══════════════════════════════════════════════════════════════
async function loadCommandes() {
  const wrap   = document.getElementById("commandes-table-wrap");
  const statut = document.getElementById("filter-statut")?.value || "";
  wrap.innerHTML = `<div class="table-loading">Chargement…</div>`;

  try {
    const res  = await fetch(`ajax/get_commandes.php?statut=${encodeURIComponent(statut)}`);
    const rows = await res.json();
    if (!rows.length) { wrap.innerHTML = `<p class="table-empty">Aucune commande trouvée.</p>`; return; }

    wrap.innerHTML = `
      <table class="admin-table">
        <thead><tr><th>#</th><th>Client</th><th>Date</th><th>Total</th><th>Statut</th><th></th></tr></thead>
        <tbody>
          ${rows.map(r => `
            <tr id="commande-row-${r.id_commande}">
              <td><span class="order-id">#${r.id_commande}</span></td>
              <td>${esc(r.prenom + ' ' + r.nom)}<br><small style="color:#8a8178">${esc(r.mail)}</small></td>
              <td>${fmtDate(r.date_commande)}</td>
              <td class="order-total">${fmtMoney(r.total)}</td>
              <td>
                <select class="statut-select statut-${r.statut}"
                        data-id="${r.id_commande}" data-current="${r.statut}"
                        onchange="updateStatut(this)">
                  <option value="en_attente" ${r.statut==='en_attente'?'selected':''}>En attente</option>
                  <option value="payée"      ${r.statut==='payée'?'selected':''}>Payée</option>
                  <option value="expédiée"   ${r.statut==='expédiée'?'selected':''}>Expédiée</option>
                  <option value="livrée"     ${r.statut==='livrée'?'selected':''}>Livrée</option>
                  <option value="annulée"    ${r.statut==='annulée'?'selected':''}>Annulée</option>
                </select>
              </td>
              <td><button class="btn-action btn-edit" onclick="openCommandeDetail(${r.id_commande})" title="Voir le détail">🔍</button></td>
            </tr>`).join("")}
        </tbody>
      </table>`;
  } catch (e) {
    wrap.innerHTML = `<p class="table-empty table-error">Erreur de chargement.</p>`;
  }
}

async function updateStatut(selectEl) {
  const id = selectEl.dataset.id, newStatut = selectEl.value, oldStatut = selectEl.dataset.current;
  selectEl.disabled = true;
  try {
    const res  = await fetch("ajax/update_commande_statut.php", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ id_commande: id, statut: newStatut }),
    });
    const data = await res.json();
    if (data.success) {
      selectEl.dataset.current = newStatut;
      selectEl.className = `statut-select statut-${newStatut}`;
      showToast(`Commande #${id} → ${newStatut}`, "success");
    } else {
      selectEl.value = oldStatut;
      showToast(data.message || "Erreur.", "error");
    }
  } catch { selectEl.value = oldStatut; showToast("Erreur réseau.", "error"); }
  finally  { selectEl.disabled = false; }
}

// ── Détail commande ───────────────────────────────────────────────────────
async function openCommandeDetail(id) {
  const res      = await fetch(`ajax/get_commande_detail.php?id=${id}`);
  const commande = await res.json();
  if (!commande) { showToast("Commande introuvable.", "error"); return; }

  const modal = document.createElement("div");
  modal.className = "modal-overlay";
  modal.id = "commande-modal";

  const lignes = commande.lignes || [];
  modal.innerHTML = `
    <div class="modal-box" style="max-width:700px">
      <div class="modal-head">
        <h3>Commande #${commande.id_commande}</h3>
        <button class="modal-close" onclick="closeModal('commande-modal')">✕</button>
      </div>
      <div class="modal-body">

        <div class="detail-grid">
          <div class="detail-block">
            <div class="detail-label">Client</div>
            <div class="detail-value">${esc(commande.prenom + ' ' + commande.nom)}</div>
            <div class="detail-sub">${esc(commande.mail)}</div>
            <div class="detail-sub">${esc(commande.numero || '')}</div>
          </div>
          <div class="detail-block">
            <div class="detail-label">Date</div>
            <div class="detail-value">${fmtDate(commande.date_commande)}</div>
          </div>
          <div class="detail-block">
            <div class="detail-label">Statut</div>
            <div class="detail-value"><span class="status-badge status-${commande.statut}">${commande.statut}</span></div>
          </div>
          <div class="detail-block">
            <div class="detail-label">Adresse de livraison</div>
            <div class="detail-value" style="font-size:.85rem">${esc(commande.adresse_livraison || '—')}</div>
          </div>
        </div>

        <table class="admin-table" style="margin-top:1.25rem">
          <thead><tr><th>Article</th><th>Taille</th><th>Couleur</th><th>Qté</th><th>Prix unit.</th><th>Sous-total</th></tr></thead>
          <tbody>
            ${lignes.map(l => `
              <tr>
                <td><strong>${esc(l.nom_article)}</strong></td>
                <td>${l.taille || '—'}</td>
                <td>
                  ${l.couleur
                    ? `<span style="display:inline-flex;align-items:center;gap:.4rem">
                        <span style="width:14px;height:14px;border-radius:50%;background:${COULEUR_MAP[l.couleur]||'#ccc'};border:1px solid rgba(0,0,0,.15);display:inline-block"></span>
                        ${esc(l.couleur)}
                       </span>`
                    : '—'}
                </td>
                <td>${l.quantite}</td>
                <td>${fmtMoney(l.prix_unitaire)}</td>
                <td><strong>${fmtMoney(l.sous_total)}</strong></td>
              </tr>`).join("")}
          </tbody>
        </table>

        <div class="order-totals">
          <div class="order-total-line"><span>Sous-total</span><span>${fmtMoney(commande.sous_total)}</span></div>
          <div class="order-total-line"><span>Livraison</span><span>${fmtMoney(commande.frais_livraison)}</span></div>
          <div class="order-total-line order-total-final"><span>Total</span><span>${fmtMoney(commande.total)}</span></div>
        </div>

        ${commande.stripe_payment_intent ? `
          <div style="margin-top:1rem;font-size:.78rem;color:#8a8178">
            Stripe : ${esc(commande.stripe_payment_intent)} — ${esc(commande.stripe_statut || '')}
          </div>` : ''}
      </div>
      <div class="modal-foot">
        <button class="btn-cancel" onclick="closeModal('commande-modal')">Fermer</button>
      </div>
    </div>`;

  document.body.appendChild(modal);
  setTimeout(() => modal.classList.add("visible"), 10);
}

// ══════════════════════════════════════════════════════════════
// CATALOGUE
// ══════════════════════════════════════════════════════════════
async function loadCatalogue() {
  const wrap = document.getElementById("catalogue-table-wrap");
  wrap.innerHTML = `<div class="table-loading">Chargement…</div>`;
  try {
    const res  = await fetch("ajax/get_articles.php");
    const rows = await res.json();
    wrap.innerHTML = `
      <table class="admin-table">
        <thead><tr><th>ID</th><th>Nom</th><th>Catégorie</th><th>Marque</th><th>Prix</th><th>Stock</th><th>Actions</th></tr></thead>
        <tbody>
          ${rows.map(r => `
            <tr id="article-row-${r.id_shoes}" class="${r.stock_total < 50 ? 'row-warning':''}">
              <td>#${r.id_shoes}</td>
              <td><strong>${esc(r.nom)}</strong></td>
              <td>${esc(r.categorie)}</td>
              <td>${esc(r.marque)}</td>
              <td>${fmtMoney(r.Prix)}</td>
              <td><span class="${r.stock_total < 50 ? 'stock-low':'stock-ok'}">${r.stock_total}</span></td>
              <td>
                <button class="btn-action btn-edit"   onclick="openArticleModal(${r.id_shoes})" title="Modifier">✏️</button>
                <button class="btn-action btn-delete" onclick="deleteArticle(${r.id_shoes},'${esc(r.nom)}')" title="Supprimer">🗑️</button>
              </td>
            </tr>`).join("")}
        </tbody>
      </table>`;
  } catch { wrap.innerHTML = `<p class="table-empty table-error">Erreur de chargement.</p>`; }
}

// ── Modal article ─────────────────────────────────────────────────────────
let _variants = []; // [{couleur, taille, stock}]
let _imageUrl = '';

async function openArticleModal(id_shoes = null) {
  let article = null;
  if (id_shoes) {
    const res = await fetch(`ajax/get_article_detail.php?id=${id_shoes}`);
    article   = await res.json();
  }

  _variants = article?.variants?.map(v => ({ couleur: v.couleur, taille: parseInt(v.taille), stock: parseInt(v.stock) })) || [];
  _imageUrl = article?.url_image || '';

  const title = article ? `Modifier l'article #${article.id_shoes}` : "Nouvel article";
  const cats  = ["Baskets lifestyle","Baskets sport","Bottines","Danse","Espadrilles","Imperméables",
                 "Indoor","Marche","Minimalistes","Mocassins","Montantes légères","Randonnée",
                 "Running","Sabots","Sandales","Sécurité","Slip-on","Talons","Training","Vegan"];

  const modal = document.createElement("div");
  modal.className = "modal-overlay";
  modal.id = "article-modal";
  modal.innerHTML = `
    <div class="modal-box" style="max-width:760px">
      <div class="modal-head">
        <h3>${title}</h3>
        <button class="modal-close" onclick="closeModal('article-modal')">✕</button>
      </div>
      <div class="modal-body">

        <!-- Infos de base -->
        <div class="form-section-title">Informations générales</div>
        <div class="form-grid">
          <div class="form-group">
            <label>Nom *</label>
            <input id="f-nom" type="text" value="${esc(article?.nom||'')}" placeholder="ex: Nova Air Lifestyle">
          </div>
          <div class="form-group">
            <label>Catégorie *</label>
            <select id="f-categorie">${cats.map(c=>`<option ${article?.categorie===c?'selected':''}>${c}</option>`).join('')}</select>
          </div>
          <div class="form-group">
            <label>Marque *</label>
            <input id="f-marque" type="text" value="${esc(article?.marque||'')}" placeholder="ex: UrbanStep">
          </div>
          <div class="form-group">
            <label>Genre</label>
            <select id="f-genre">${['Mixte','Homme','Femme'].map(g=>`<option ${article?.genre===g?'selected':''}>${g}</option>`).join('')}</select>
          </div>
          <div class="form-group">
            <label>Prix (€) *</label>
            <input id="f-prix" type="number" step="0.01" min="0" value="${article?.Prix||''}">
          </div>
          
          <div class="form-group form-full">
            <label>Caractéristiques</label>
            <input id="f-caract" type="text" value="${esc(article?.caracteristiques||'')}" placeholder="Légères, Respirantes...">
          </div>
          <div class="form-group form-full">
            <label>Matériaux</label>
            <input id="f-materiaux" type="text" value="${esc(article?.materiaux||'')}" placeholder="Tige: Mesh; Semelle: EVA...">
          </div>
          <div class="form-group form-full">
            <label>Usage</label>
            <input id="f-usage" type="text" value="${esc(article?.usage||'')}" placeholder="Quotidien, Ville...">
          </div>
          <div class="form-group form-full">
            <label>Mots-clés</label>
            <input id="f-mots" type="text" value="${esc(article?.mots_cles||'')}" placeholder="confort, ville, léger...">
          </div>
          <div class="form-group form-full">
            <label>Description</label>
            <textarea id="f-desc" rows="3">${esc(article?.description||'')}</textarea>
          </div>
        </div>

        <!-- Image -->
        <div class="form-section-title" style="margin-top:1.5rem">Image</div>
        <div class="image-upload-zone" id="image-upload-zone">
          <div id="image-preview">
            ${_imageUrl
              ? `<img src="../../${esc(_imageUrl)}" style="max-height:120px;border-radius:8px">`
              : `<div class="image-placeholder">📷 Aucune image</div>`}
          </div>
          <div style="margin-top:.75rem;display:flex;gap:.75rem;align-items:center;flex-wrap:wrap">
            <label class="btn-upload-label">
              Choisir une image
              <input type="file" id="f-image-file" accept="image/*" style="display:none" onchange="previewAndUpload(this)">
            </label>
            <span style="font-size:.78rem;color:#8a8178">ou</span>
            <input id="f-image-url" type="text" value="${esc(_imageUrl)}"
                   placeholder="images/imageN.png"
                   style="flex:1;padding:.5rem .85rem;border:1.5px solid #e0d9ce;border-radius:8px;font-family:inherit;font-size:.85rem"
                   oninput="_imageUrl=this.value">
          </div>
          <div id="upload-status" style="font-size:.78rem;margin-top:.4rem"></div>
        </div>

        <!-- Variantes couleurs / tailles -->
        <div class="form-section-title" style="margin-top:1.5rem">Couleurs & Pointures disponibles</div>
        <div class="variants-builder">

          <div class="variants-add-row">
            <div class="form-group" style="flex:0 0 180px">
              <label>Couleur</label>
              <div class="color-picker-wrap">
                <div class="color-picker-preview" id="picker-preview" style="background:#ccc"></div>
                <select id="picker-couleur" onchange="updateColorPreview(this)">
                  <option value="">— choisir —</option>
                  ${TOUTES_COULEURS.map(c=>`<option value="${esc(c)}" style="background:${COULEUR_MAP[c]}">${c}</option>`).join('')}
                </select>
              </div>
            </div>
            <div class="form-group" style="flex:0 0 120px">
              <label>Pointure</label>
              <select id="picker-taille">
                <option value="">— choisir —</option>
                ${TOUTES_TAILLES.map(t=>`<option value="${t}">${t}</option>`).join('')}
              </select>
            </div>
            <div class="form-group" style="flex:0 0 100px">
              <label>Stock</label>
              <input id="picker-stock" type="number" min="0" value="10" placeholder="10">
            </div>
            <button class="btn-add-variant" onclick="addVariant()">+ Ajouter</button>
          </div>

          <div id="variants-list" class="variants-list"></div>
        </div>

        <div class="reindex-note">ℹ️ Après sauvegarde, le catalogue sera automatiquement re-vectorisé pour le chatbot client.</div>
      </div>
      <div class="modal-foot">
        <button class="btn-cancel" onclick="closeModal('article-modal')">Annuler</button>
        <button class="btn-save" id="btn-save-article" onclick="saveArticle(${id_shoes||'null'})">
          ${article ? 'Enregistrer' : "Créer l'article"}
        </button>
      </div>
    </div>`;

  document.body.appendChild(modal);
  setTimeout(() => modal.classList.add("visible"), 10);
  renderVariants();
}

function updateColorPreview(sel) {
  document.getElementById("picker-preview").style.background = COULEUR_MAP[sel.value] || '#ccc';
}

function addVariant() {
  const couleur = document.getElementById("picker-couleur").value;
  const taille  = parseInt(document.getElementById("picker-taille").value);
  const stock   = parseInt(document.getElementById("picker-stock").value) || 0;
  if (!couleur || !taille) { showToast("Choisissez une couleur et une pointure.", "error"); return; }

  // Évite les doublons
  if (_variants.find(v => v.couleur === couleur && v.taille === taille)) {
    showToast("Cette combinaison existe déjà.", "error"); return;
  }
  _variants.push({ couleur, taille, stock });
  renderVariants();
}

function removeVariant(idx) {
  _variants.splice(idx, 1);
  renderVariants();
}

function renderVariants() {
  const container = document.getElementById("variants-list");
  if (!container) return;
  if (!_variants.length) {
    container.innerHTML = `<p style="font-size:.8rem;color:#8a8178;padding:.5rem 0">Aucune variante ajoutée.</p>`;
    return;
  }
  // Groupe par couleur pour l'affichage
  const byCouleur = {};
  _variants.forEach((v, i) => {
    if (!byCouleur[v.couleur]) byCouleur[v.couleur] = [];
    byCouleur[v.couleur].push({ ...v, idx: i });
  });

  container.innerHTML = Object.entries(byCouleur).map(([couleur, items]) => `
    <div class="variant-group">
      <div class="variant-color-head">
        <span class="variant-color-dot" style="background:${COULEUR_MAP[couleur]||'#ccc'}"></span>
        <strong>${esc(couleur)}</strong>
      </div>
      <div class="variant-sizes">
        ${items.map(v => `
          <div class="variant-tag">
            <span>T${v.taille}</span>
            <span class="variant-stock">${v.stock} unités</span>
            <button onclick="removeVariant(${v.idx})" title="Supprimer">✕</button>
          </div>`).join('')}
      </div>
    </div>`).join('');
}

// ── Upload image ──────────────────────────────────────────────────────────
async function previewAndUpload(input) {
  const file = input.files[0];
  if (!file) return;

  // Prévisualisation locale immédiate
  const reader = new FileReader();
  reader.onload = e => {
    document.getElementById("image-preview").innerHTML =
      `<img src="${e.target.result}" style="max-height:120px;border-radius:8px">`;
  };
  reader.readAsDataURL(file);

  // Upload vers le serveur
  const status = document.getElementById("upload-status");
  status.textContent = "Upload en cours…";
  status.style.color = "#8a8178";

  const form = new FormData();
  form.append("image", file);

  try {
    const res  = await fetch("ajax/upload_image.php", { method: "POST", body: form });
    const data = await res.json();
    if (data.success) {
      _imageUrl = data.url_image;
      document.getElementById("f-image-url").value = _imageUrl;
      status.textContent = "✓ Image uploadée : " + data.url_image;
      status.style.color = "#27ae60";
    } else {
      status.textContent = "✗ " + data.message;
      status.style.color = "#c0392b";
    }
  } catch {
    status.textContent = "✗ Erreur réseau.";
    status.style.color = "#c0392b";
  }
}

// ── Sauvegarde ────────────────────────────────────────────────────────────
async function saveArticle(id_shoes) {
  const btn = document.getElementById("btn-save-article");
  btn.disabled = true; btn.textContent = "Enregistrement…";

  // Récupère l'URL image (peut avoir été saisie manuellement)
  const manualUrl = document.getElementById("f-image-url")?.value.trim();
  if (manualUrl) _imageUrl = manualUrl;

  const payload = {
    id_shoes,
    nom:              document.getElementById("f-nom").value.trim(),
    categorie:        document.getElementById("f-categorie").value,
    marque:           document.getElementById("f-marque").value.trim(),
    genre:            document.getElementById("f-genre").value,
    prix:             parseFloat(document.getElementById("f-prix").value),
    stock: _variants.reduce((sum, v) => sum + (parseInt(v.stock) || 0), 0),
    url_image:        _imageUrl,
    caracteristiques: document.getElementById("f-caract").value.trim(),
    materiaux:        document.getElementById("f-materiaux").value.trim(),
    usage:            document.getElementById("f-usage").value.trim(),
    mots_cles:        document.getElementById("f-mots").value.trim(),
    description:      document.getElementById("f-desc").value.trim(),
    variants:         _variants,
  };

  if (!payload.nom || !payload.categorie || !payload.marque || !payload.prix) {
    showToast("Champs obligatoires manquants.", "error");
    btn.disabled = false;
    btn.textContent = id_shoes ? "Enregistrer" : "Créer l'article";
    return;
  }

  try {
    const res  = await fetch("ajax/save_article.php", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.success) {
      showToast(data.message + " Re-vectorisation en cours…", "success");
      closeModal("article-modal");
      loadCatalogue();
    } else {
      showToast(data.message || "Erreur.", "error");
      btn.disabled = false;
      btn.textContent = id_shoes ? "Enregistrer" : "Créer l'article";
    }
  } catch {
    showToast("Erreur réseau.", "error");
    btn.disabled = false;
  }
}

async function deleteArticle(id_shoes, nom) {
  if (!confirm(`Supprimer "${nom}" (#${id_shoes}) ?\nCette action est irréversible.`)) return;
  try {
    const res  = await fetch("ajax/delete_article.php", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ id_shoes }),
    });
    const data = await res.json();
    if (data.success) {
      document.getElementById(`article-row-${id_shoes}`)?.remove();
      showToast(data.message + " Re-vectorisation en cours…", "success");
    } else { showToast(data.message || "Erreur.", "error"); }
  } catch { showToast("Erreur réseau.", "error"); }
}

// ══════════════════════════════════════════════════════════════
// CLIENTS
// ══════════════════════════════════════════════════════════════
async function loadClients() {
  const wrap  = document.getElementById("clients-table-wrap");
  const query = document.getElementById("client-search-input")?.value.trim() || "";
  wrap.innerHTML = `<div class="table-loading">Chargement…</div>`;
  try {
    const res  = await fetch(`ajax/get_clients.php?q=${encodeURIComponent(query)}`);
    const rows = await res.json();
    if (!rows.length) { wrap.innerHTML = `<p class="table-empty">Aucun client trouvé.</p>`; return; }
    wrap.innerHTML = `
      <table class="admin-table">
        <thead><tr><th>ID</th><th>Nom</th><th>Email</th><th>Téléphone</th><th>Commandes</th></tr></thead>
        <tbody>
          ${rows.map(r => `
            <tr>
              <td>#${r.id_client}</td>
              <td>${esc(r.prenom + ' ' + r.nom)}</td>
              <td>${esc(r.mail)}</td>
              <td>${esc(r.numero||'—')}</td>
              <td><span class="badge-commandes">${r.nb_commandes}</span></td>
            </tr>`).join("")}
        </tbody>
      </table>`;
  } catch { wrap.innerHTML = `<p class="table-empty table-error">Erreur de chargement.</p>`; }
}

// ══════════════════════════════════════════════════════════════
// COMMENTAIRES
// ══════════════════════════════════════════════════════════════
async function loadCommentaires() {
  const wrap = document.getElementById("commentaires-table-wrap");
  wrap.innerHTML = `<div class="table-loading">Chargement…</div>`;
  try {
    const res  = await fetch("ajax/get_commentaires.php");
    const rows = await res.json();
    if (!rows.length) { wrap.innerHTML = `<p class="table-empty">Aucun commentaire.</p>`; return; }
    wrap.innerHTML = `
      <table class="admin-table">
        <thead><tr><th>ID</th><th>Article</th><th>Client</th><th>Note</th><th>Commentaire</th><th>Date</th></tr></thead>
        <tbody>
          ${rows.map(r => `
            <tr>
              <td>#${r.id_commentaire}</td>
              <td>${esc(r.article)}</td>
              <td>${esc(r.client_prenom+' '+r.client_nom)}</td>
              <td class="stars">${"★".repeat(r.note)}${"☆".repeat(5-r.note)}</td>
              <td class="comment-cell">${esc(r.contenu)}</td>
              <td>${fmtDate(r.created_at)}</td>
            </tr>`).join("")}
        </tbody>
      </table>`;
  } catch { wrap.innerHTML = `<p class="table-empty table-error">Erreur de chargement.</p>`; }
}

// ══════════════════════════════════════════════════════════════
// HELPERS
// ══════════════════════════════════════════════════════════════
function closeModal(id) {
  const m = document.getElementById(id);
  if (m) { m.classList.remove("visible"); setTimeout(() => m.remove(), 250); }
}

function showToast(msg, type = "success") {
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.classList.add("visible"), 10);
  setTimeout(() => { el.classList.remove("visible"); setTimeout(() => el.remove(), 300); }, 3500);
}

function esc(s) {
  return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function fmtMoney(v) { return parseFloat(v).toLocaleString('fr-FR',{minimumFractionDigits:2})+' €'; }
function fmtDate(d) {
  if (!d) return '—';
  const dt = new Date(d);
  return dt.toLocaleDateString('fr-FR')+' '+dt.toLocaleTimeString('fr-FR',{hour:'2-digit',minute:'2-digit'});
}
