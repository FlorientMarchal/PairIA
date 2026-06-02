<?php
require_once '../includes/bd.php';
session_start();

$id = (int)($_GET['id'] ?? 0);
if (!$id) exit(json_encode(['error' => 'ID manquant']));

/* ───────────────────────────────────────────────
   1) NOTE MOYENNE
─────────────────────────────────────────────── */
$stmt = $pdo->prepare("SELECT AVG(note) AS avg_note, COUNT(*) AS total FROM commentaires WHERE id_shoes = ?");
$stmt->execute([$id]);
$stats = $stmt->fetch();

$avg = $stats['avg_note'] ? round($stats['avg_note'], 1) : 0;
$total = (int)$stats['total'];

$stars = str_repeat("★", floor($avg)) . str_repeat("☆", 5 - floor($avg));

$summary_html = "
    <div class='rating-summary'>
        <div class='stars'>{$stars}</div>
        <div>{$avg}/5 — {$total} avis</div>
    </div>
";

/* ───────────────────────────────────────────────
   2) FORMULAIRE (si connecté + a acheté)
─────────────────────────────────────────────── */
$form_html = "<div>Connecte-toi pour laisser un commentaire.</div>";

if (isset($_SESSION['client_id'])) {

    // Vérifier si l'utilisateur a acheté ce produit
    $stmt = $pdo->prepare("
        SELECT 1
        FROM lignes_commande lc
        JOIN commandes c ON c.id_commande = lc.id_commande
        WHERE lc.id_shoes = ? AND c.id_client = ?
    ");
    $stmt->execute([$id, $_SESSION['client_id']]);
    $hasBought = $stmt->fetch();

    if ($hasBought) {
        $form_html = "
            <div class='comment-form'>
                <select id='comment-note'>
                    <option value='5'>5 ★</option>
                    <option value='4'>4 ★</option>
                    <option value='3'>3 ★</option>
                    <option value='2'>2 ★</option>
                    <option value='1'>1 ★</option>
                </select>
                <textarea id='comment-text' placeholder='Votre avis...'></textarea>
                <button onclick='addComment()'>Publier</button>
            </div>
        ";
    } else {
        $form_html = "<div>Tu dois avoir acheté ce produit pour laisser un avis.</div>";
    }
}

/* ───────────────────────────────────────────────
   3) LISTE DES COMMENTAIRES
─────────────────────────────────────────────── */
$stmt = $pdo->prepare("
    SELECT c.*, cl.nom AS client_nom
    FROM commentaires c
    JOIN clients cl ON cl.id_client = c.id_client
    WHERE id_shoes = ?
    ORDER BY created_at DESC
");
$stmt->execute([$id]);
$comments = $stmt->fetchAll();

$list_html = "";

foreach ($comments as $c) {

    // Vérifier si l'utilisateur a liké
    $liked = false;
    if (isset($_SESSION['client_id'])) {
        $stmt2 = $pdo->prepare("SELECT 1 FROM commentaire_likes WHERE id_commentaire = ? AND id_client = ?");
        $stmt2->execute([$c['id_commentaire'], $_SESSION['client_id']]);
        $liked = $stmt2->fetch() ? true : false;
    }

    $stars = str_repeat("★", $c['note']) . str_repeat("☆", 5 - $c['note']);

    $deleteBtn = "";
    if (isset($_SESSION['client_id']) && $_SESSION['client_id'] == $c['id_client']) {
        $deleteBtn = "<button class='delete-btn' onclick='deleteComment({$c['id_commentaire']})'>Supprimer</button>";
    }

    $list_html .= "
        <div class='comment-card'>
            <div class='comment-header'>
                <div class='comment-author'>{$c['client_nom']}</div>
                <div class='comment-date'>{$c['created_at']}</div>
            </div>
            <div class='stars'>{$stars}</div>
            <div class='comment-content'>".htmlspecialchars($c['contenu'])."</div>
            <div class='comment-actions'>
                <button class='like-btn' onclick='likeComment({$c['id_commentaire']})'>
                    ".($liked ? "❤️" : "🤍")."
                </button>
                {$deleteBtn}
            </div>
        </div>
    ";
}

echo json_encode([
    "summary_html" => $summary_html,
    "form_html" => $form_html,
    "list_html" => $list_html
]);
