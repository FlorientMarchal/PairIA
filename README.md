# PairIA 👟
### AI Chatbot for Shoe E-Commerce | Chatbot IA pour boutique e-commerce de chaussures

---

## 🇬🇧 English

### What is PairIA?

PairIA is a complete e-commerce platform for shoe retail, coupled with an AI conversational assistant. The entire system runs locally — no external paid API is required. It was built as a proof of concept to demonstrate what can be achieved with open source AI models deployed on-premise.

### Features

#### 🛍️ E-Commerce Website
- **Product catalog** with filters (category, gender, brand, price, size, color)
- **Product pages** with descriptions, size/color selector, customer reviews and similar product suggestions
- **Shopping cart** with session management and database persistence for logged-in users
- **Secure checkout** via Stripe (3DS compliant)
- **Customer account**: registration, login, order history, profile management
- **Wishlist**: add/remove products from catalog, product pages and chat
- **Customer reviews**: star rating system with AI-assisted review generation
- **Admin interface**: manage products, orders, customers and reviews from a dashboard

#### 🤖 Customer Chatbot
- **Natural language search**: find products by usage, budget, color, size, style
- **Side-by-side comparison**: compare two products with a structured table
- **Image search**: upload a photo to find visually similar products (CLIP)
- **Voice input**: dictate your question via microphone (Whisper)
- **Multilingual**: supports 75 languages with automatic detection and translation — the customer chatbot automatically detects the language of the user and responds in the same language
- **Cart integration**: add products directly from the chat with size/color confirmation
- **Conversation history**: persistent history grouped by date for logged-in users
- **Proactive suggestions**: context-aware messages on product pages, cart and wishlist
- **Hesitation detection**: adapts tone based on number of visits to a product page
- **AI-assisted review writing**: generate a review from a few keywords

#### 🔧 Admin Chatbot
Manage the entire store in natural language using 25 available tools via function calling with qwen2.5. Here are some examples of what you can ask:

- *"Show me all pending orders"*
- *"Increase all running shoe prices by 10%"*
- *"Add a new product"* — upload a photo and the chatbot automatically generates the name, description and characteristics from the image
- *"Delete the customer review #5"*
- *"Show me the top 10 best-selling products"*
- *"Change order #12 status to shipped"*
- *"List products with low stock"*
- *"Show me the monthly revenue for the last 12 months"*

Confirmation is always required before irreversible actions such as deletions or batch price changes.

#### 🧠 AI Pipeline
- **RAG pipeline**: retrieval-augmented generation for accurate product responses
- **Intention classifier**: CamemBERT fine-tuned on 8 intent classes
- **Dynamic filters**: budget, color, size, brand, gender, category with fuzzy matching
- **Semantic search**: Qdrant vector database with cosine similarity
- **Local inference**: Ollama with llama3.1 and qwen2.5, no cloud dependency

---

### Tech Stack

| Component | Technology |
|-----------|-----------|
| LLM Server | Ollama |
| Customer LLM | LLaMA 3.1 (7B) |
| Admin LLM | Qwen 2.5 (7B) |
| Intent Classifier | CamemBERT (fine-tuned) |
| Text Embeddings | nomic-embed-text (768d) |
| Image Embeddings | CLIP ViT-B-32 (512d) |
| Vector Database | Qdrant |
| Backend API | FastAPI (Python 3.11) |
| Relational Database | MySQL 8 |
| Frontend | PHP 8.3 + JavaScript |
| Voice Transcription | Whisper (small) |
| Payment | Stripe |
| Deployment | Docker Compose |

---

### Installation

#### Prerequisites
- Install **Docker Desktop**: https://www.docker.com/products/docker-desktop
- Restart your PC after installation if prompted
- At least 20 GB of free disk space (for LLM models)

#### Step 1 — Get the project
```powershell
git pull
cd site
```

#### Step 2 — Create the `.env` file
Create a `.env` file in the `site/` folder with the following content:
```env
MYSQL_ROOT_PASSWORD=yourpassword
ADMIN_ACTION_TOKEN=pairia_admin_secret_change_me
```

#### Step 3 — Copy the database file
```powershell
cp ..\e_commmerce.sql .\init.sql
```

#### Step 4 — Start the containers
```powershell
docker compose up -d
```
⚠️ The first launch may take a few minutes.

#### Step 5 — Download AI models (once only, ~7GB)
```powershell
docker exec pairia-ollama ollama pull llama3.1
docker exec pairia-ollama ollama pull nomic-embed-text
docker exec pairia-ollama ollama pull qwen2.5:7b
docker exec pairia-ollama ollama pull llava:7b
```

#### Step 6 — Index products
```powershell
docker exec pairia-api python embeeding.py
docker exec pairia-api python embeeding_images.py
```

#### Step 7 — Train the intention classifier (~20 minutes)
```powershell
docker exec pairia-api python finetune_intention.py
```

#### Stripe setup
```powershell
docker compose cp web:/var/www/html/vendor .
```

---

### Access

| Service | URL |
|---------|-----|
| Website | http://localhost |
| phpMyAdmin | http://localhost:8080 |
| Python API | http://localhost:8000 |

---

### Useful commands

Stop the containers:
```powershell
docker compose down
```

Restart the containers:
```powershell
docker compose up -d
```

View API logs:
```powershell
docker compose logs -f api
```

---

### Notes
- The `.env` and `init.sql` files are not in git — they need to be created for each new installation.
- Ollama models are persistent — no need to re-download them after a `docker compose down`.
- The intention classifier model (`modele_intention/`) is also persistent — no need to retrain unless you want to.

---

### Authors
**Florient Marchal** & **Kardiatou BA** — L3 MIASHS, Université de Montpellier  
Stage chez Dell Technologies Montpellier — 2026

---
---

## 🇫🇷 Français

### Qu'est-ce que PairIA ?

PairIA est une plateforme e-commerce complète de vente de chaussures, couplée à un assistant conversationnel IA. L'ensemble du système fonctionne entièrement en local — aucune API externe payante n'est requise. Le projet a été réalisé comme démonstrateur pour illustrer ce qu'il est possible de produire avec des modèles open source déployés sur site.

### Fonctionnalités

#### 🛍️ Site E-Commerce
- **Catalogue produits** avec filtres (catégorie, genre, marque, prix, pointure, couleur)
- **Fiches produit** avec description, sélecteur taille/couleur, avis clients et suggestions de produits similaires
- **Panier** avec gestion en session PHP et persistance en base pour les utilisateurs connectés
- **Paiement sécurisé** via Stripe (compatible 3DS)
- **Espace client** : inscription, connexion, historique des commandes, gestion du profil
- **Liste de favoris** : ajout/suppression depuis le catalogue, les fiches produit et le chat
- **Avis clients** : système de notation par étoiles avec génération d'avis assistée par IA
- **Interface administrateur** : gestion des produits, commandes, clients et avis depuis un tableau de bord

#### 🤖 Chatbot Client
- **Recherche en langage naturel** : trouver des produits par usage, budget, couleur, taille, style
- **Comparaison côte à côte** : comparer deux produits avec un tableau structuré
- **Recherche par image** : envoyer une photo pour trouver des produits visuellement similaires (CLIP)
- **Saisie vocale** : dicter sa question via le microphone (Whisper)
- **Multilingue** : supporte 75 langues avec détection et traduction automatiques — le chatbot détecte automatiquement la langue de l'utilisateur et répond dans la même langue
- **Ajout au panier depuis le chat** : ajouter un produit directement avec confirmation taille/couleur
- **Historique des conversations** : historique persistant groupé par date pour les utilisateurs connectés
- **Suggestions proactives** : messages contextuels sur les fiches produit, le panier et les favoris
- **Détection de l'hésitation** : adapte le ton selon le nombre de visites sur une fiche produit
- **Rédaction d'avis assistée** : générer un avis à partir de quelques mots-clés

#### 🔧 Chatbot Administrateur
Gérer toute la boutique en langage naturel grâce à 25 outils disponibles via function calling avec qwen2.5. Voici quelques exemples de ce qu'il est possible de demander :

- *"Montre-moi toutes les commandes en attente"*
- *"Augmente tous les prix des chaussures de running de 10%"*
- *"Ajoute un nouvel article"* — uploader une photo et le chatbot génère automatiquement le nom, la description et les caractéristiques à partir de l'image
- *"Supprime l'avis client n°5"*
- *"Montre-moi le top 10 des articles les plus vendus"*
- *"Change le statut de la commande n°12 à expédiée"*
- *"Liste les articles avec un stock faible"*
- *"Montre-moi le chiffre d'affaires mensuel sur les 12 derniers mois"*

Une confirmation est toujours demandée avant les actions irréversibles comme les suppressions ou les modifications de prix en lot.

#### 🧠 Pipeline IA
- **Pipeline RAG** : génération augmentée par récupération pour des réponses précises sur les produits
- **Classifieur d'intention** : CamemBERT fine-tuné sur 8 classes d'intention
- **Filtres dynamiques** : budget, couleur, taille, marque, genre, catégorie avec tolérance aux fautes
- **Recherche sémantique** : base vectorielle Qdrant avec similarité cosinus
- **Inférence locale** : Ollama avec llama3.1 et qwen2.5, sans dépendance cloud

---

### Stack technique

| Composant | Technologie |
|-----------|-------------|
| Serveur LLM | Ollama |
| LLM chatbot client | LLaMA 3.1 (7B) |
| LLM chatbot admin | Qwen 2.5 (7B) |
| Classifieur d'intention | CamemBERT (fine-tuné) |
| Embeddings texte | nomic-embed-text (768d) |
| Embeddings image | CLIP ViT-B-32 (512d) |
| Base vectorielle | Qdrant |
| API backend | FastAPI (Python 3.11) |
| Base relationnelle | MySQL 8 |
| Frontend | PHP 8.3 + JavaScript |
| Transcription vocale | Whisper (small) |
| Paiement | Stripe |
| Déploiement | Docker Compose |

---

### Installation

#### Prérequis
- Installer **Docker Desktop** : https://www.docker.com/products/docker-desktop
- Redémarrer le PC après l'installation si demandé
- Au moins 20 Go d'espace disque disponible (pour les modèles LLM)

#### Étape 1 — Récupérer le projet
```powershell
git pull
cd site
```

#### Étape 2 — Créer le fichier `.env`
Créer un fichier `.env` dans le dossier `site/` avec le contenu suivant :
```env
MYSQL_ROOT_PASSWORD=tonmotdepasse
ADMIN_ACTION_TOKEN=pairia_admin_secret_change_me
```

#### Étape 3 — Copier la base de données
```powershell
cp ..\e_commmerce.sql .\init.sql
```

#### Étape 4 — Lancer les conteneurs
```powershell
docker compose up -d
```
⚠️ Le premier lancement peut prendre quelques minutes.

#### Étape 5 — Télécharger les modèles IA (une seule fois, ~7Go)
```powershell
docker exec pairia-ollama ollama pull llama3.1
docker exec pairia-ollama ollama pull nomic-embed-text
docker exec pairia-ollama ollama pull qwen2.5:7b
docker exec pairia-ollama ollama pull llava:7b
```

#### Étape 6 — Indexer les produits
```powershell
docker exec pairia-api python embeeding.py
docker exec pairia-api python embeeding_images.py
```

#### Étape 7 — Entraîner le classifieur d'intention (~20 minutes)
```powershell
docker exec pairia-api python finetune_intention.py
```

#### Configuration Stripe
```powershell
docker compose cp web:/var/www/html/vendor .
```

---

### Accès

| Service | URL |
|---------|-----|
| Site | http://localhost |
| phpMyAdmin | http://localhost:8080 |
| API Python | http://localhost:8000 |

---

### Commandes utiles

Arrêter les conteneurs :
```powershell
docker compose down
```

Relancer les conteneurs :
```powershell
docker compose up -d
```

Voir les logs de l'API :
```powershell
docker compose logs -f api
```

---

### Notes
- Le fichier `.env` et `init.sql` ne sont pas dans le git — ils doivent être créés à chaque nouvelle installation.
- Les modèles Ollama sont persistants — pas besoin de les retélécharger après un `docker compose down`.
- Le modèle d'intention (`modele_intention/`) est aussi persistant — pas besoin de relancer le fine-tuning sauf si vous souhaitez le réentraîner.

---

### Auteurs
**Florient Marchal** & **Kardiatou BA** — L3 MIASHS, Université de Montpellier  
Stage chez Dell Technologies Montpellier — 2026
