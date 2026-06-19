<?php
// admin/ajax/upload_image.php
require_once '../includes/auth_admin.php';

header('Content-Type: application/json');

if (!isset($_FILES['image']) || $_FILES['image']['error'] !== UPLOAD_ERR_OK) {
    echo json_encode(['success' => false, 'message' => 'Aucun fichier reçu.']);
    exit;
}

$file     = $_FILES['image'];
$ext      = strtolower(pathinfo($file['name'], PATHINFO_EXTENSION));
$allowed  = ['jpg', 'jpeg', 'jfif', 'png', 'webp', 'avif'];

if (!in_array($ext, $allowed)) {
    echo json_encode(['success' => false, 'message' => 'Format non autorisé. Utilisez JPG, PNG, WEBP ou AVIF.']);
    exit;
}

if ($file['size'] > 5 * 1024 * 1024) {
    echo json_encode(['success' => false, 'message' => 'Fichier trop lourd (max 5 Mo).']);
    exit;
}

// Dossier images relatif à la racine du site (pas du dossier admin)
$upload_dir = __DIR__ . '/../../images/';
if (!is_dir($upload_dir)) {
    mkdir($upload_dir, 0755, true);
}

// Nom unique basé sur le timestamp
$filename  = 'image_' . time() . '_' . bin2hex(random_bytes(4)) . '.' . $ext;
$dest      = $upload_dir . $filename;

if (!move_uploaded_file($file['tmp_name'], $dest)) {
    echo json_encode(['success' => false, 'message' => 'Erreur lors de la sauvegarde du fichier.']);
    exit;
}

echo json_encode([
    'success'   => true,
    'filename'  => $filename,
    'url_image' => 'images/' . $filename,
]);
