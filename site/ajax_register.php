<?php
session_start();
require_once 'includes/bd.php';

$nom = $_POST['n'] ?? '';
$prenom = $_POST['p'] ?? '';
$adr = $_POST['adr'] ?? '';
$num = $_POST['num'] ?? '';
$mail = $_POST['mail'] ?? '';
$mdp = $_POST['mdp1'] ?? '';

if (!$nom || !$prenom || !$adr || !$num || !$mail || !$mdp) {
  echo json_encode(["success"=>false, "message"=>"Champs manquants"]);
  exit;
}

if (!preg_match("/^[A-Za-zÀ-ÿ\s'-]+$/", $nom)) {
  echo json_encode(["success"=>false, "message"=>"Nom invalide"]);
  exit;
}

if (!preg_match("/^[A-Za-zÀ-ÿ\s'-]+$/", $prenom)) {
  echo json_encode(["success"=>false, "message"=>"Prénom invalide"]);
  exit;
}

$mdp = $_POST['mdp1'] ?? '';

if (!preg_match('/^(?=.*[A-Za-z])(?=.*\d)(?=.*[^A-Za-z0-9]).{10,}$/', $mdp)) {
  echo json_encode([
    "success" => false,
    "message" => "Mot de passe trop faible (min 10 caractères, 1 lettre, 1 chiffre, 1 spécial)"
  ]);
  exit;
}

/* check email */
$stmt = $pdo->prepare("SELECT id_client FROM Clients WHERE mail = ?");
$stmt->execute([$mail]);

if ($stmt->fetch()) {
  echo json_encode(["success"=>false, "message"=>"Email déjà utilisé"]);
  exit;
}

/* insert */
$hash = password_hash($mdp, PASSWORD_DEFAULT);

$stmt = $pdo->prepare("
  INSERT INTO Clients (nom, prenom, adresse, numero, mail, mdp)
  VALUES (?, ?, ?, ?, ?, ?)
");

$stmt->execute([$nom, $prenom, $adr, $num, $mail, $hash]);

$_SESSION['client'] = [
  'nom'=>$nom,
  'prenom'=>$prenom,
  'mail'=>$mail
];

echo json_encode(["success"=>true]);