<?php
ini_set('display_errors', 0);
error_reporting(E_ALL);
session_start();
require_once '../includes/bd.php';
require_once '../includes/config.php';
require __DIR__ . '/../../vendor/autoload.php';

header('Content-Type: application/json');

if (!isset($_SESSION['client_id'])) {
    http_response_code(401);
    echo json_encode(['error' => 'Non connecté']);
    exit;
}

$input  = json_decode(file_get_contents('php://input'), true);
$amount = (int)($input['amount'] ?? 0);

if ($amount < 50) {
    echo json_encode(['error' => 'Montant invalide — reçu : ' . $amount]);
    exit;
}

\Stripe\Stripe::setApiKey(STRIPE_SECRET_KEY);

try {
    $client_id = (int)$_SESSION['client_id'];

    $stmtCustomer = $pdo->prepare("
        SELECT stripe_customer_id, mail, prenom, nom 
        FROM clients 
        WHERE id_client = ?
    ");
    $stmtCustomer->execute([$client_id]);
    $clientRow = $stmtCustomer->fetch();

    $stripe_customer_id = $clientRow['stripe_customer_id'] ?? null;

    if (empty($stripe_customer_id)) {
        $customer = \Stripe\Customer::create([
            'email'    => $clientRow['mail'],
            'name'     => trim($clientRow['prenom'] . ' ' . $clientRow['nom']),
            'metadata' => ['client_id' => $client_id],
        ]);
        $stripe_customer_id = $customer->id;

        $pdo->prepare("
            UPDATE clients 
            SET stripe_customer_id = ? 
            WHERE id_client = ?
        ")->execute([$stripe_customer_id, $client_id]);
    }

    $intent = \Stripe\PaymentIntent::create([
        'amount'   => $amount,
        'currency' => 'eur',
        'customer' => $stripe_customer_id,
        'metadata' => ['client_id' => $client_id],
        'automatic_payment_methods' => ['enabled' => true],
    ]);

    echo json_encode(['client_secret' => $intent->client_secret]);

} catch (\Exception $e) {
    http_response_code(500);
    echo json_encode([
        'error'  => $e->getMessage(),
        'ligne'  => $e->getLine(),
        'detail' => get_class($e)
    ]);
}