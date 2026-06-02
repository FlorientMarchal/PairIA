<?php
require_once '../includes/bd.php';
session_start();

$id = (int)($_GET['id'] ?? 0);
$sort = $_GET['sort'] ?? "recent";

if (!$id) exit(json_encode(['error' => 'ID manquant']));

/* ───────────────────────────────────────────────
   1) RÉSUMÉ DES NOTES
─────────────────────────────────────────────── */
$stmt = $pdo->prepare("SELECT AVG(note) AS avg_note, COUNT(*) AS total FROM commentaires WHERE id_shoes = ?");
$stmt->execute([$id]);
$stats = $stmt->fetch();

$avg = $stats['avg_note'] ? round($stats['avg_note'], 1) : 0;
$total = (int)$stats['total'];

$stars = str_repeat("★", floor($avg)) . str_repeat("☆", 5 - floor($avg));

$summary_html = "
    <div class='summary-note'>{$avg}</div>
    <div class='summary-stars'>{$stars}</div>
    <div class='summary-count'>{$total} avis</div>
";

/* ───────────────────────────────────────────────
   2) HISTOGRAMME
─────────────────────────────────────────────── */
$histogram_html = "";
for ($i = 5; $i >= 1; $i--) {
    $stmt = $pdo->prepare("SELECT COUNT(*) FROM commentaires WHERE id_shoes = ? AND note = ?");
    $stmt->execute([$id, $i]);
    $count = $stmt->fetchColumn();

    $percent = $total > 0 ? ($count / $total) * 100 : 0;

    $histogram_html .= "
        <div class='hist-row'>
            <div class='hist-label'>{$i}★</div>
            <div class='hist-bar'>
                <div class='hist-fill' style='width: {$percent}%;'></div>
            </div>
            <div class='hist-count'>{$count}</div>
        </div>
    ";
}

/* ───────────────────────────────────────────────
   3) TRI
─────────────────────────────────────────────── */
$order = "c.created_at DESC";

if ($sort === "best") $order = "c.note DESC";
if ($sort === "worst") $order = "c.note ASC";
if ($sort === "useful") $order = "c.useful DESC";

/* ───────────────────────────────────────────────
   4) LISTE DES AVIS
─────────────────────────────────────────────── */
$stmt = $pdo->prepare("
    SELECT c.*, cl.nom AS client_nom
    FROM commentaires c
    JOIN clients cl ON cl.id_client = c.id_client
    WHERE id_shoes = ?
    ORDER BY $order
");
$stmt->execute([$id]);
$comments = $stmt->fetchAll();

$list_html = "";

foreach ($comments as $c) {

    /* Vérifier achat vérifié */
    $stmt2 = $pdo->prepare("
        SELECT 1
        FROM lignes_commande lc
        JOIN commandes co ON co.id_commande = lc.id_commande
        WHERE lc.id_shoes = ? AND co.id_client = ?
    ");
    $stmt2->execute([$id, $c['id_client']]);
    $verified = $stmt2->fetch() ? "<div class='verified-badge'>Achat vérifié</div>" : "";

    /* Étoiles */
    $stars = str_repeat("★", $c['note']) . str_repeat("☆", 5 - $c['note']);

    /* Bouton supprimer */
    $deleteBtn = "";
    if (isset($_SESSION['client_id']) && $_SESSION['client_id'] == $c['id_client']) {
        $deleteBtn = "<button class='action-btn delete-btn' onclick='deleteComment({$c['id_commentaire']})'>Supprimer</button>";
    }

    $list_html .= "
        <div class='comment-card'>
            <div class='comment-header'>
                <div class='comment-author'>{$c['client_nom']}</div>
                <div class='comment-date'>{$c['created_at']}</div>
            </div>

            {$verified}

            <div class='comment-stars'>{$stars}</div>

            <div class='comment-content'>".nl2br(htmlspecialchars($c['contenu']))."</div>

            <div class='comment-actions'>
                <button class='action-btn' onclick='markUseful({$c['id_commentaire']}, 1)'>
                    Utile ({$c['useful']})
                </button>
                {$deleteBtn}
            </div>
        </div>
    ";
}

echo json_encode([
    "summary_html" => $summary_html,
    "histogram_html" => $histogram_html,
    "list_html" => $list_html
]);
