<?php
$host     = 'localhost';
$dbname   = 'pairia';       
$user     = 'root';          // utilisateur MySQL (MAMP = root)
$password = 'root';          // mot de passe MySQL (MAMP = root)
$charset  = 'utf8mb4';

$dsn = "mysql:host=$host;dbname=$dbname;charset=$charset";

$options = [
    PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,  // affiche les erreurs SQL
    PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,        // retourne des tableaux associatifs
    PDO::ATTR_EMULATE_PREPARES   => false,                   // requêtes préparées réelles
];

try {
    $pdo = new PDO($dsn, $user, $password, $options);
} catch (PDOException $e) {
    // En développement : affiche l'erreur
    // En production : remplacer par un message générique
    die('Erreur de connexion : ' . $e->getMessage());
}