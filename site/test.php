<?php
try {
    $pdo = new PDO('mysql:host=localhost;dbname=e_commmerce;charset=utf8mb4', 'root', 'root');
    $articles = $pdo->query('SELECT * FROM articles LIMIT 3')->fetchAll();
    var_dump($articles);
} catch (PDOException $e) {
    echo "Erreur : " . $e->getMessage();
}