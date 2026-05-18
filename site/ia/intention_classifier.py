# ia/intention_classifier.py
import torch
from transformers import CamembertTokenizer, CamembertForSequenceClassification

MODEL_DIR = "./modele_intention"
MAX_LEN   = 64
LABELS    = [
    "recherche",
    "suivi",
    "comparaison",
    "recommandation",  # ← nouveau
    "panier",
    "livraison",       # ← nouveau
    "hors_sujet",      # ← nouveau
]

print("[CLASSIFIER] Chargement du modèle d'intention...")
_tokenizer = CamembertTokenizer.from_pretrained(MODEL_DIR)
_model     = CamembertForSequenceClassification.from_pretrained(MODEL_DIR)
_model.eval()
print("[CLASSIFIER] Modèle chargé !")


def classifier_intention(question: str, seuil_confiance: float = 0.5) -> tuple[str, float]:
    """
    Classifie l'intention d'une question.
    Retourne (intention, confiance).

    - recherche      → nouvelle recherche produit → Qdrant requis
    - suivi          → question factuelle sur un produit (matière, taille, poids...)
    - comparaison    → comparer explicitement 2+ produits déjà présentés
    - recommandation → demande de conseil/avis
    - panier         → ajout au panier / achat
    - livraison      → question livraison / retour / stock
    - hors_sujet     → non lié aux chaussures

    Si confiance < seuil → fallback "recherche"
    """
    enc = _tokenizer(
        question,
        return_tensors="pt",
        truncation=True,
        max_length=MAX_LEN,
        padding=True,
    )

    with torch.no_grad():
        logits = _model(**enc).logits

    probs     = torch.softmax(logits, dim=1)[0]
    pred_idx  = probs.argmax().item()
    confiance = probs[pred_idx].item()
    intention = LABELS[pred_idx]

    print(f"[CLASSIFIER] {question!r} → {intention} ({confiance:.1%})")

    if confiance < seuil_confiance:
        print(f"[CLASSIFIER] Confiance faible ({confiance:.1%}) → fallback recherche")
        return "recherche", confiance

    return intention, confiance