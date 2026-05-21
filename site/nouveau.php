<?php
session_start();
?>

<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Nouveau Client</title>
<link rel="stylesheet" href="styles/index.css">

<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>

<style>
input {
  border: 2px solid #ccc;
  padding: 8px;
  border-radius: 6px;
  outline: none;
}

input.valid {
  border-color: green;
  background: #eaffea;
}

input.invalid {
  border-color: red;
  background: #ffecec;
}

.error-msg {
  color: red;
  font-size: 12px;
  margin-top: 3px;
}

.success-msg {
  color: green;
  text-align: center;
  margin-top: 10px;
  font-weight: bold;
}
</style>
</head>

<body>

<h2 style="text-align:center;">Créer un compte</h2>

<div id="server-msg"></div>

<form id="registerForm"
      style="max-width:400px;margin:20px auto;display:flex;flex-direction:column;gap:10px;">

  <input type="text" name="n" placeholder="Nom">
  <div class="error-msg"></div>

  <input type="text" name="p" placeholder="Prénom">
  <div class="error-msg"></div>

  <input type="text" name="adr" placeholder="Adresse">
  <div class="error-msg"></div>

  <input type="text" name="num" placeholder="Téléphone">
  <div class="error-msg"></div>

  <input type="email" name="mail" placeholder="Email">
  <div class="error-msg"></div>

  <input type="password" name="mdp1" placeholder="Mot de passe">
  <div class="error-msg"></div>

  <input type="password" name="mdp2" placeholder="Confirmer mot de passe">
  <div class="error-msg"></div>

  <button type="submit" id="submitBtn" disabled>S'inscrire</button>
</form>

<script>
$(document).ready(function(){

let valid = {
  n:false, p:false, adr:false, num:false, mail:false, mdp1:false, mdp2:false
};

function checkForm(){
  let ok = Object.values(valid).every(v => v === true);
  $('#submitBtn').prop('disabled', !ok);
}

/* =====================
   VALIDATION GENERALE
===================== */

function setState(input, state, msg="") {
  let next = $(input).next('.error-msg');

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

  // accepte : 0612345678 ou +33612345678
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

  if(!regex.test(email)){
    valid.mail = false;
    setState(this, false, "Email invalide");
    checkForm();
    return;
  }

  $.post('check_email.php', {mail: email}, function(res){
    if(res.exists){
      valid.mail = false;
      setState('input[name="mail"]', false, "Email déjà utilisé");
    } else {
      valid.mail = true;
      setState('input[name="mail"]', true);
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
/* =====================
   SUBMIT AJAX REGISTER
===================== */

$('#registerForm').on('submit', function(e){
  e.preventDefault();

  $.ajax({
    url: 'ajax_register.php',
    type: 'POST',
    data: $(this).serialize(),
    dataType: 'json',
    success: function(res){

      if(res.success){
        $('#server-msg')
          .html("<p class='success-msg'>Compte créé avec succès ✔</p>");

        setTimeout(() => {
          window.location.href = "index.php";
        }, 1000);

      } else {
        $('#server-msg')
          .html("<p style='color:red;text-align:center;'>"+res.message+"</p>");
      }
    }
  });
});

});
</script>

</body>
</html>