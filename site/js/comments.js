window.currentRating = 0;
window.currentSort = "recent";

window.loadCommentsPremium = async function () {
  const res = await fetch(
    `./commentaires/list.php?id=${PRODUCT_ID}&sort=${currentSort}`,
  );
  const data = await res.json();

  const section = document.getElementById("comments-premium");
  const right = document.querySelector(".comments-right");
  const filters = document.querySelector(".comments-filters");

  if (data.empty) {
    // Aucun avis : cache les avis et le tri
    document.getElementById("comments-list").innerHTML = "";
    document.getElementById("comments-summary").innerHTML = "";
    document.getElementById("comments-histogram").innerHTML = "";
    if (filters) filters.style.display = "none";

    // Bloc droit + section : visibles seulement si connecté
    // (pour que le bouton "Donner mon avis" reste accessible)
    if (right) right.style.display = data.is_logged ? "" : "none";
    section.style.display = data.is_logged ? "" : "none";
    return;
  }

  // Il y a des avis : tout afficher
  section.style.display = "";
  if (filters) filters.style.display = "";

  document.getElementById("comments-list").innerHTML = data.list_html;
  document.getElementById("comments-summary").innerHTML = data.summary_html;
  document.getElementById("comments-histogram").innerHTML = data.histogram_html;

  // Bloc droit : visible seulement si connecté
  if (right) right.style.display = data.is_logged ? "" : "none";
};

window.filterComments = function () {
  currentSort = document.getElementById("comments-sort").value;
  loadCommentsPremium();
};

window.openReviewModal = function () {
  document.getElementById("review-modal").style.display = "flex";
};

window.closeReviewModal = function () {
  document.getElementById("review-modal").style.display = "none";
  currentRating = 0;
  document
    .querySelectorAll(".rating-input span")
    .forEach((s) => s.classList.remove("active"));
};

document.addEventListener("click", function (e) {
  if (e.target.closest(".rating-input span")) {
    const v = parseInt(e.target.dataset.value);
    currentRating = v;
    document.querySelectorAll(".rating-input span").forEach((s) => {
      s.classList.toggle("active", parseInt(s.dataset.value) <= v);
    });
  }
});

window.submitReview = async function () {
  const contenu = document.getElementById("review-text").value;

  if (!currentRating || contenu.trim() === "") {
    alert("Veuillez sélectionner une note et écrire un avis.");
    return;
  }

  const res = await fetch("./commentaires/add.php", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id: PRODUCT_ID, note: currentRating, contenu }),
  });

  const text = await res.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch (e) {
    console.error("Réponse invalide du serveur :", text);
    alert("Erreur serveur — vérifiez les logs PHP.");
    return;
  }

  if (data.success) {
    closeReviewModal();
    loadCommentsPremium();
  } else if (data.error === "not_logged") {
    alert("Connecte-toi pour laisser un avis.");
  } else if (data.error === "not_purchased") {
    alert("Tu dois avoir acheté cette chaussure pour laisser un avis.");
  } else {
    alert("Erreur : " + (data.error || "inconnue"));
  }
};

window.markUseful = async function (id, value) {
  await fetch(`./commentaires/useful.php?id=${id}&value=${value}`);
  loadCommentsPremium();
};

window.deleteComment = async function (id) {
  if (!confirm("Supprimer cet avis ?")) return;
  await fetch(`./commentaires/delete.php?id=${id}`);
  loadCommentsPremium();
};
