# ══════════════════════════════════════════════════════════════
# README_ADMIN.md — Installation de la partie Admin PairIA
# ══════════════════════════════════════════════════════════════

## Structure des fichiers à ajouter

```
site/
└── admin/
    ├── connexion_admin.php        ← Page de login admin
    ├── connecter_admin.php        ← Traitement login
    ├── deconnexion_admin.php      ← Déconnexion
    ├── index.php                  ← Dashboard principal
    ├── includes/
    │   ├── auth_admin.php         ← Guard de sécurité (à inclure partout)
    │   ├── admin_actions.php      ← Fonctions PHP appelées par le chatbot
    │   └── admin_chat.php         ← HTML du panneau chatbot
    ├── ajax/
    │   ├── get_commandes.php
    │   ├── get_articles.php
    │   ├── get_clients.php
    │   └── get_commentaires.php
    ├── js/
    │   ├── admin_chat.js          ← Logique chatbot admin (indépendant de chat.js)
    │   └── admin_tables.js        ← Chargement des tableaux
    └── styles/
        └── admin.css              ← Styles admin

site/ia/
└── admin_main.py                  ← Serveur FastAPI chatbot admin (port 8001)
```

---

## 1. Base de données

Exécuter le fichier SQL :
```sql
-- Dans phpMyAdmin ou MySQL CLI :
source migration_admin.sql;
```

Cela crée :
- La table `admins`
- La table `admin_conversations` (historique chatbot)
- La table `admin_actions_log` (journal des actions)
- Un compte admin par défaut : `admin@pairia.fr` / `Admin1234!`

**⚠️ Changer le mot de passe immédiatement en production !**

---

## 2. Copier les fichiers

Copier le dossier `admin/` dans `site/` et `ia/admin_main.py` dans `site/ia/`.

---

## 3. Lancer le serveur chatbot admin

Le chatbot admin tourne sur le **port 8001** (séparé du chatbot client sur 8000) :

```bash
cd site/ia
uvicorn admin_main:app --port 8001 --workers 2
```

Ou dans docker-compose, ajouter ce service :

```yaml
admin-chatbot:
  build: ./ia
  command: uvicorn admin_main:app --host 0.0.0.0 --port 8001 --workers 2
  ports:
    - "8001:8001"
  environment:
    - OLLAMA_HOST=http://ollama:11434
    - ADMIN_ACTIONS_URL=http://php:80/admin/includes/admin_actions.php
    - ADMIN_ACTION_TOKEN=pairia_admin_secret_2024   # ← CHANGER EN PROD
  depends_on:
    - ollama
    - db
```

---

## 4. Variable d'environnement à ajouter dans `.env`

```env
ADMIN_ACTION_TOKEN=pairia_admin_secret_2024   # Token partagé PHP ↔ FastAPI
```

Et dans `docker-compose.yml` du service PHP :
```yaml
environment:
  - ADMIN_ACTION_TOKEN=pairia_admin_secret_2024
```

---

## 5. Accès

- URL admin : `http://votre-site/admin/connexion_admin.php`
- Identifiants par défaut : `admin@pairia.fr` / `Admin1234!`

---

## Ce que le chatbot admin peut faire

Le chatbot comprend les demandes en langage naturel et appelle les fonctions PHP
correspondantes. Il ne génère jamais de SQL arbitraire.

| Commande naturelle | Action déclenchée |
|---|---|
| "Liste les commandes en attente" | `lister_commandes(statut='en_attente')` |
| "Détail de la commande #42" | `detail_commande(42)` |
| "Passe la commande #42 en expédiée" | `modifier_statut_commande(42, 'expédiée')` |
| "Quel est le stock des Running ?" | `lister_articles(categorie='Running')` |
| "Modifie le prix de l'article #12 à 129.90€" | `modifier_prix(12, 129.90)` |
| "Recherche le client Dupont" | `rechercher_client('Dupont')` |
| "Statistiques globales" | `stats_globales()` |
| "Top 5 des ventes" | `top_articles(5)` |
| "CA des 12 derniers mois" | `ca_par_mois()` |

**Pour toute action de modification**, le chatbot demande confirmation avant d'agir.

---

## Sécurité

- L'accès à `/admin/` est protégé par `auth_admin.php` (session `admin_id`)
- Les actions PHP sont protégées par un token partagé `X-Admin-Token`
- Aucune requête SQL arbitraire n'est possible — seulement les 14 fonctions prédéfinies
- Les admins sont dans une table séparée des clients
