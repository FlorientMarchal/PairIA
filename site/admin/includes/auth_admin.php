<?php
// admin/includes/auth_admin.php
// Vérifie simplement que le client connecté est admin.
// Plus besoin de session séparée.

if (session_status() === PHP_SESSION_NONE) session_start();

if (empty($_SESSION['client_id']) || empty($_SESSION['is_admin'])) {
    header('Location: ../connexion.php');
    exit;
}
