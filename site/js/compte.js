function loadCompteSection(section) {
  const container = document.getElementById("compte-content");

  if (section === "panier") {
    loadPage("panier.php?ajax=1"); // 🔥 réutilisation directe
    return;
  }

  if (section === "profil") {
    container.innerHTML = `
      <h2>Profil</h2>
      <p>Chargement...</p>
    `;

    fetch("user/get_client.php")
      .then((res) => res.json())
      .then((data) => {
        container.innerHTML = `
          <h2>Mes informations</h2>
          <p><strong>Nom :</strong> ${data.nom}</p>
          <p><strong>Prénom :</strong> ${data.prenom}</p>
          <p><strong>Email :</strong> ${data.email}</p>
        `;
      });
  }

  if (section === "params") {
    container.innerHTML = `
      <h2>Paramètres</h2>

      <form id="update-form">
        <input type="email" name="email" placeholder="Nouvel email" required>
        <input type="password" name="password" placeholder="Nouveau mot de passe">
        <button type="submit">Mettre à jour</button>
      </form>

      <div id="msg"></div>
    `;

    document.getElementById("update-form").onsubmit = async (e) => {
      e.preventDefault();

      const formData = new FormData(e.target);

      const res = await fetch("user/update_client.php", {
        method: "POST",
        body: formData,
      });

      const data = await res.json();
      document.getElementById("msg").innerText = data.message;
    };
  }
}
