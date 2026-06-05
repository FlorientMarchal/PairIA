<?php
// includes/bd.php — Connexion à la base de données
// Lit la config depuis les variables d'environnement (Docker)
// avec fallback sur les valeurs locales pour le développement

$host     = getenv('MYSQL_HOST')     ?: 'localhost';
$dbname   = getenv('MYSQL_DATABASE') ?: 'e_commmerce';
$user     = getenv('MYSQL_USER')     ?: 'root';
$password = getenv('MYSQL_PASSWORD') ?: 'root';
$charset  = 'utf8mb4';

$dsn = "mysql:host=$host;dbname=$dbname;charset=$charset";

$options = [
    PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
    PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
    PDO::ATTR_EMULATE_PREPARES   => false,
];

try {
    $pdo = new PDO($dsn, $user, $password, $options);
} catch (PDOException $e) {
    // En production : message générique (ne pas exposer l'erreur)
    die('Erreur de connexion à la base de données.');
}

define('GROQ_API_KEY', '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');