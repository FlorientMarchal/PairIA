<?php
session_start();
require_once 'includes/bd.php';
?>
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Créer un compte — PairIA</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;1,9..40,300&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/tabler-icons.min.css">
<link rel="stylesheet" href="styles/global.css">
<link rel="stylesheet" href="styles/auth.css">

<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
</head>
<body>

<?php include 'includes/navbar.php'; ?>

<div class="auth-wrap">
  <div class="auth-card auth-card--wide">

    <div class="auth-head">
      <div class="auth-badge">P</div>
      <h1 class="auth-title">Créer un compte</h1>
      <p class="auth-sub">
        Déjà inscrit·e ?
        <a href="connexion.php">Se connecter</a>
      </p>
    </div>

    <div id="server-msg" class="auth-server-msg"></div>

    <form id="registerForm" class="auth-form">

      <div class="auth-row">
        <div class="auth-field">
          <label for="n">Nom</label>
          <input type="text" id="n" name="n" placeholder="Dupont">
          <div class="auth-error-msg"></div>
        </div>

        <div class="auth-field">
          <label for="p">Prénom</label>
          <input type="text" id="p" name="p" placeholder="Camille">
          <div class="auth-error-msg"></div>
        </div>
      </div>

      <div class="auth-field">
        <label for="adr">Adresse</label>
        <input type="text" id="adr" name="adr" placeholder="12 rue des Lilas, 75000 Paris">
        <div class="auth-error-msg"></div>
      </div>

      <div class="auth-field">
        <label for="num">Téléphone</label>
        <input type="text" id="num" name="num" placeholder="0612345678">
        <div class="auth-error-msg"></div>
      </div>

      <div class="auth-field">
        <label for="mail">Email</label>
        <input type="email" id="mail" name="mail" placeholder="vous@exemple.com">
        <div class="auth-error-msg"></div>
      </div>

      <div class="auth-row">
        <div class="auth-field">
          <label for="mdp1">Mot de passe</label>
          <input type="password" id="mdp1" name="mdp1" placeholder="••••••••">
          <div class="auth-error-msg"></div>
        </div>

        <div class="auth-field">
          <label for="mdp2">Confirmer</label>
          <input type="password" id="mdp2" name="mdp2" placeholder="••••••••">
          <div class="auth-error-msg"></div>
        </div>
      </div>

      <button type="submit" id="submitBtn" class="auth-submit" disabled>S'inscrire</button>
    </form>

    <div class="auth-foot">
      <a href="index.php">← Retour au catalogue</a>
    </div>

  </div>
</div>

<script>
$(document).ready(function(){

let valid = {
  n:false, p:false, adr:false, num:false, mail:false, mdp1:false, mdp2:false
};

function checkForm(){
  let ok = Object.values(valid).every(v => v === true);
  $('#submitBtn').prop('disabled', !ok);
}

function setState(input, state, msg=""){
  let next = $(input).closest('.auth-field').find('.auth-error-msg');

  if(state === true){
    $(input).removeClass('invalid').addClass('valid');
    next.text("");
  } else {
    $(input).removeClass('valid').addClass('invalid');
    next.text(msg);
  }
}

/* NOM */
$('input[name="n"]').on('input', function(){
  let value = this.value.trim();
  let regex = /^[A-Za-zÀ-ÿ\s'-]+$/;

  if(value === ""){
    valid.n = false;
    setState(this, false, "Nom obligatoire");
  }
  else if(!regex.test(value)){
    valid.n = false;
    setState(this, false, "Le nom ne doit contenir que des lettres");
  }
  else {
    valid.n = true;
    setState(this, true);
  }

  checkForm();
});

/* PRENOM */
$('input[name="p"]').on('input', function(){
  let value = this.value.trim();
  let regex = /^[A-Za-zÀ-ÿ\s'-]+$/;

  if(value === ""){
    valid.p = false;
    setState(this, false, "Prénom obligatoire");
  }
  else if(!regex.test(value)){
    valid.p = false;
    setState(this, false, "Le prénom ne doit contenir que des lettres");
  }
  else {
    valid.p = true;
    setState(this, true);
  }

  checkForm();
});

/* ADRESSE */
$('input[name="adr"]').on('input', function(){
  valid.adr = this.value.trim() !== "";
  setState(this, valid.adr, "Adresse obligatoire");
  checkForm();
});

/* NUMERO */
$('input[name="num"]').on('input', function(){
  let value = this.value.trim();
  let regex = /^(0|\+33)[1-9](\d{8})$/;

  if(value === ""){
    valid.num = false;
    setState(this, false, "Numéro obligatoire");
  }
  else if(!regex.test(value)){
    valid.num = false;
    setState(this, false, "Numéro invalide (ex: 0612345678 ou +33612345678)");
  }
  else {
    valid.num = true;
    setState(this, true);
  }

  checkForm();
});

/* EMAIL + AJAX CHECK */
$('input[name="mail"]').on('input', function(){
  let email = this.value;
  let regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  let input = this;

  if(!regex.test(email)){
    valid.mail = false;
    setState(input, false, "Email invalide");
    checkForm();
    return;
  }

  $.post('check_email.php', {mail: email}, function(res){
    if(res.exists){
      valid.mail = false;
      setState(input, false, "Email déjà utilisé");
    } else {
      valid.mail = true;
      setState(input, true);
    }
    checkForm();
  }, 'json');
});

/* PASSWORD */
$('input[name="mdp1"]').on('input', function(){
  let v = this.value;
  let regex = /^(?=.*[A-Za-z])(?=.*\d)(?=.*[^A-Za-z0-9]).{10,}$/;

  if(v.trim() === ""){
    valid.mdp1 = false;
    setState(this, false, "Mot de passe obligatoire");
  }
  else if(!regex.test(v)){
    valid.mdp1 = false;
    setState(this, false, "Min 10 caractères + lettre + chiffre + caractère spécial");
  }
  else {
    valid.mdp1 = true;
    setState(this, true);
  }

  checkForm();
});

/* CONFIRM PASSWORD */
$('input[name="mdp2"]').on('input', function(){
  let mdp1 = $('input[name="mdp1"]').val();

  if(this.value !== mdp1){
    valid.mdp2 = false;
    setState(this, false, "Les mots de passe ne correspondent pas");
  }
  else {
    valid.mdp2 = true;
    setState(this, true);
  }

  checkForm();
});

$('#registerForm').on('submit', function(e){
  e.preventDefault();

  $.ajax({
    url: 'ajax_register.php',
    type: 'POST',
    data: $(this).serialize(),
    dataType: 'json',
    success: function(res){

      if(res.success){
        $('#server-msg').html(
          "<div class='auth-alert success'><i class='ti ti-circle-check'></i><span>Compte créé avec succès</span></div>"
        );

        setTimeout(() => {
          window.location.href = "index.php";
        }, 1000);

      } else {
        $('#server-msg').html(
          "<div class='auth-alert error'><i class='ti ti-alert-circle'></i><span>"+res.message+"</span></div>"
        );
      }
    }
  });
});

});
</script>
<?php include 'includes/footer.php'; ?>
</body>
</html>
