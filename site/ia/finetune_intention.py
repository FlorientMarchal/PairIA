# ia/finetune_intention.py
# Fine-tuning de CamemBERT pour la classification d'intentions
# Lancer avec : python finetune_intention.py

import json
import os
import numpy as np
import torch
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from transformers import (
    CamembertTokenizer,
    CamembertForSequenceClassification,
    Trainer,
    TrainingArguments,
)
from torch.utils.data import Dataset
BASE_DIR = os.path.dirname(__file__)

# ── Config ──
MODEL_NAME = "camembert-base"
OUTPUT_DIR = os.path.join(BASE_DIR, "modele_intention")
DATASET_PATH = os.path.join(BASE_DIR, "dataset_intentions.json")

MAX_LEN = 64
BATCH_SIZE = 16
EPOCHS = 5
SEED = 42

LABELS = [
    "recherche",
    "suivi",
    "comparaison",
    "recommandation",
    "panier",
    "livraison",
    "salutation",   # ← ajout
    "hors_sujet",
]
LABEL2ID = {l: i for i, l in enumerate(LABELS)}
ID2LABEL = {i: l for i, l in enumerate(LABELS)}

print(f"Labels : {LABELS}")
print(f"Dispositif : {'GPU' if torch.cuda.is_available() else 'CPU'}")


# ── Dataset ──
class IntentionDataset(Dataset):
    def __init__(self, encodings, labels):
        self.encodings = encodings
        self.labels    = labels

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        item = {k: torch.tensor(v[idx]) for k, v in self.encodings.items()}
        item["labels"] = torch.tensor(self.labels[idx])
        return item


# ── Chargement données ──
print("\nChargement du dataset...")
with open(DATASET_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

texts  = [d["text"]  for d in data]
labels = [LABEL2ID[d["label"]] for d in data]

print(f"Total : {len(texts)} exemples")
for label, idx in LABEL2ID.items():
    count = labels.count(idx)
    print(f"  {label:<15} : {count}")

# ── Vérification équilibre des classes ──
from collections import Counter
counts = Counter(labels)
min_count = min(counts.values())
max_count = max(counts.values())
if max_count / min_count > 3:
    print(f"\n⚠️  Déséquilibre détecté (ratio {max_count/min_count:.1f}x) — "
          f"pensez à sur-échantillonner les classes minoritaires.")

# Split train/test
train_texts, test_texts, train_labels, test_labels = train_test_split(
    texts, labels, test_size=0.2, random_state=SEED, stratify=labels
)
print(f"\nTrain : {len(train_texts)} | Test : {len(test_texts)}")


# ── Tokenizer ──
print("\nChargement du tokenizer CamemBERT...")
tokenizer = CamembertTokenizer.from_pretrained(MODEL_NAME)

train_enc = tokenizer(train_texts, truncation=True, padding=True, max_length=MAX_LEN)
test_enc  = tokenizer(test_texts,  truncation=True, padding=True, max_length=MAX_LEN)

train_dataset = IntentionDataset(train_enc, train_labels)
test_dataset  = IntentionDataset(test_enc,  test_labels)


# ── Modèle ──
print("Chargement du modèle CamemBERT...")
model = CamembertForSequenceClassification.from_pretrained(
    MODEL_NAME,
    num_labels=len(LABELS),
    id2label=ID2LABEL,
    label2id=LABEL2ID,
)


# ── Métriques ──
def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=1)
    accuracy = (preds == labels).mean()
    # F1 macro utile quand les classes sont déséquilibrées
    from sklearn.metrics import f1_score
    f1 = f1_score(labels, preds, average="macro")
    return {"accuracy": accuracy, "f1_macro": f1}


# ── Entraînement ──
training_args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    num_train_epochs=EPOCHS,
    per_device_train_batch_size=BATCH_SIZE,
    per_device_eval_batch_size=BATCH_SIZE,
    warmup_steps=50,
    weight_decay=0.01,
    logging_dir="./logs",
    logging_steps=10,
    eval_strategy="epoch",
    save_strategy="epoch",
    load_best_model_at_end=True,
    metric_for_best_model="f1_macro",   # F1 macro plutôt qu'accuracy
    greater_is_better=True,
    seed=SEED,
    report_to="none",
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=test_dataset,
    compute_metrics=compute_metrics,
)

print("\nDémarrage du fine-tuning...")
trainer.train()


# ── Évaluation finale ──
print("\nÉvaluation finale...")
predictions = trainer.predict(test_dataset)
preds = np.argmax(predictions.predictions, axis=1)

print("\nRapport de classification :")
print(classification_report(
    test_labels,
    preds,
    target_names=LABELS,
    digits=3,
))


# ── Sauvegarde ──
print(f"\nSauvegarde du modèle dans {OUTPUT_DIR}...")
trainer.save_model(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)
print("Modèle sauvegardé !")


# ── Test rapide ──
print("\nTest rapide sur quelques phrases :")
phrases_test = [
    # recherche
    ("je cherche des baskets noires pointure 42",          "recherche"),
    ("vous avez des mocassins en cuir ?",                  "recherche"),
    # suivi
    ("ils taillent grand ?",                               "suivi"),
    ("c'est quoi la matière de la semelle ?",              "suivi"),
    ("combien pèse cette paire ?",                         "suivi"),
    # comparaison
    ("quelle est la différence entre le modèle A et B ?",  "comparaison"),
    ("tu peux les comparer ?",                             "comparaison"),
    # recommandation
    ("lequel tu conseillerais pour la randonnée ?",        "recommandation"),
    ("tu as un avis sur ce modèle ?",                      "recommandation"),
    # panier
    ("je le prends",                                       "panier"),
    ("ajoute au panier",                                   "panier"),
    # livraison
    ("vous livrez en combien de jours ?",                  "livraison"),
    ("est-ce que je peux retourner les chaussures ?",      "livraison"),
    ("il reste du stock ?",                                "livraison"),
    # hors_sujet
    ("c'est quoi la météo demain ?",                       "hors_sujet"),
    ("raconte-moi une blague",                             "hors_sujet"),
]

model.eval()
print(f"\n{'Phrase':<55} {'Prédit':<15} {'Attendu':<15} {'Confiance':>9}")
print("─" * 100)
for phrase, expected in phrases_test:
    enc = tokenizer(phrase, return_tensors="pt", truncation=True, max_length=MAX_LEN)
    with torch.no_grad():
        logits = model(**enc).logits
    pred_idx   = logits.argmax().item()
    pred_label = ID2LABEL[pred_idx]
    confidence = torch.softmax(logits, dim=1).max().item()
    ok = "✓" if pred_label == expected else "✗"
    print(f"{ok} {phrase:<53} {pred_label:<15} {expected:<15} {confidence:>8.1%}")