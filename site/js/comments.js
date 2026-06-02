window.currentRating = 0;
window.currentSort = "recent";

window.loadCommentsPremium = async function () {
  const res = await fetch(
    `./commentaires/list.php?id=${PRODUCT_ID}&sort=${currentSort}`,
  );
  const data = await res.json();

  document.getElementById("comments-list").innerHTML = data.list_html;
  document.getElementById("comments-summary").innerHTML = data.summary_html;
  document.getElementById("comments-histogram").innerHTML = data.histogram_html;
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
    body: JSON.stringify({
      id: PRODUCT_ID,
      note: currentRating,
      contenu: contenu,
    }),
  });

  const data = await res.json();

  if (data.success) {
    closeReviewModal();
    loadCommentsPremium();
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
