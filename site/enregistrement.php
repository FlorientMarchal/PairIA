<?php
session_start();
require_once 'includes/bd.php';

function enregistrer($nom, $prenom, $adresse, $mail, $numero, $mdp)
{
    global $pdo;

    $check = $pdo->prepare("SELECT id_client FROM clients WHERE mail = ?");
    $check->execute([$mail]);

    if ($check->fetch()) {
        header("Location: nouveau.php?error=email_exists");
        exit;
    }

    $hash = password_hash($mdp, PASSWORD_DEFAULT);

    $stmt = $pdo->prepare("
        INSERT INTO Clients (nom, prenom, adresse, mail, numero, mdp)
        VALUES (?, ?, ?, ?, ?, ?)
    ");

    $stmt->execute([$nom, $prenom, $adresse, $mail, $numero, $hash]);
}

$nom     = $_POST['n'] ?? '';
$prenom  = $_POST['p'] ?? '';
$adresse = $_POST['adr'] ?? '';
$numero  = $_POST['num'] ?? '';
$mail    = $_POST['mail'] ?? '';
$mdp1    = $_POST['mdp1'] ?? '';
$mdp2    = $_POST['mdp2'] ?? '';

if (!empty($nom) && !empty($prenom) && !empty($adresse) &&
    !empty($numero) && !empty($mail) &&
    $mdp1 === $mdp2) {

    enregistrer($nom, $prenom, $adresse, $mail, $numero, $mdp1);

    header("Location: index.php");
    exit;

} else {
    die("Erreur données invalides");
}
?>